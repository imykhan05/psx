"""
Edge validation (F1.3, honest version).

Question: do the technical signals the scoring engine relies on actually predict
forward returns on PSX? We answer it directly and cheaply from the full price
history (no engine replay needed), across ~2400 trading days and ~500 symbols.

Method (no look-ahead):
  - For every stock-day, compute signals from data up to that day:
      mom_21   trailing 21-day return  (1-month momentum)
      mom_63   trailing 63-day return  (3-month momentum)
      above_ma50 / above_ma200         trend
      vol_ratio  volume / 20-day avg
      rev_5   -(trailing 5-day return)  (short-term mean reversion)
  - Forward target: fwd_10 = the NEXT 10 trading days' return (strictly future).
  - Measure, pooled over all stock-days:
      * Spearman IC (rank correlation signal->fwd_10). |IC|>~0.03 is meaningful in equities.
      * Decile spread: mean fwd_10 of the top-signal decile minus the bottom decile.
  - Robustness: the same top-minus-bottom spread computed PER YEAR (does it persist
    out-of-sample, or is it one lucky period?).

A positive, persistent spread => the signal has real predictive value and it is
honest to build BUY logic on it. A ~zero or unstable spread => it does not predict,
and no threshold tweak can make a trustworthy BUY out of it. We report whatever we find.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "database" / "psx_terminal.db"
FWD = 10          # forward horizon in trading days
MIN_PRICE = 2.0   # ignore illiquid sub-2 penny prints
MIN_OBS = 300     # ignore symbols with too little history


def load() -> pd.DataFrame:
    con = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(
            "SELECT date_parsed, symbol, close, volume FROM daily_prices", con
        )
    finally:
        con.close()
    df["date_parsed"] = pd.to_datetime(df["date_parsed"], format="ISO8601", errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    df = df.dropna(subset=["date_parsed", "close"]).sort_values(["symbol", "date_parsed"])
    # keep symbols with enough history
    counts = df.groupby("symbol")["close"].transform("size")
    return df[(counts >= MIN_OBS) & (df["close"] >= MIN_PRICE)].copy()


def build(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("symbol", group_keys=False)
    df["mom_21"] = g["close"].transform(lambda s: s / s.shift(21) - 1)
    df["mom_63"] = g["close"].transform(lambda s: s / s.shift(63) - 1)
    df["ma50"] = g["close"].transform(lambda s: s.rolling(50, min_periods=50).mean())
    df["ma200"] = g["close"].transform(lambda s: s.rolling(200, min_periods=200).mean())
    df["above_ma50"] = (df["close"] > df["ma50"]).astype(float)
    df["above_ma200"] = (df["close"] > df["ma200"]).astype(float)
    df["vol_ratio"] = df["volume"] / g["volume"].transform(lambda s: s.rolling(20, min_periods=10).mean())
    df["rev_5"] = -(g["close"].transform(lambda s: s / s.shift(5) - 1))
    # strictly-future target
    df["fwd_10"] = g["close"].transform(lambda s: s.shift(-FWD) / s - 1) * 100.0
    df["year"] = df["date_parsed"].dt.year
    return df


def spearman_ic(sig: pd.Series, fwd: pd.Series) -> float:
    m = sig.notna() & fwd.notna()
    if m.sum() < 500:
        return np.nan
    return float(sig[m].rank().corr(fwd[m].rank()))


def decile_spread(sig: pd.Series, fwd: pd.Series) -> float:
    m = sig.notna() & fwd.notna()
    if m.sum() < 1000:
        return np.nan
    try:
        d = pd.qcut(sig[m].rank(method="first"), 10, labels=False)
    except ValueError:
        return np.nan
    grp = fwd[m].groupby(d).mean()
    return float(grp.iloc[-1] - grp.iloc[0])  # top decile minus bottom decile, in %


def main() -> int:
    print("loading price history...")
    df = build(load())
    n = int(df["fwd_10"].notna().sum())
    base = float(df["fwd_10"].mean())
    print(f"stock-days with a forward-{FWD}d return: {n:,} | market avg fwd_{FWD}d: {base:+.2f}%\n")

    signals = ["mom_21", "mom_63", "above_ma50", "above_ma200", "vol_ratio", "rev_5"]
    print(f"{'signal':11} {'IC':>7} {'top-bottom decile fwd_10 (%)':>30}")
    print("-" * 52)
    results = {}
    for s in signals:
        ic = spearman_ic(df[s], df["fwd_10"])
        spread = decile_spread(df[s], df["fwd_10"])
        results[s] = (ic, spread)
        print(f"{s:11} {ic:>7.3f} {spread:>28.2f}")

    # per-year robustness: momentum (engine's basis) vs mean-reversion (what works)
    print(f"\nper-year top-minus-bottom decile spread (fwd_{FWD}d %):")
    print(f"  {'year':6} {'mom_63':>9} {'rev_5':>9} {'vol_ratio':>10} {'market':>8}")
    for yr, sub in df.groupby("year"):
        m = decile_spread(sub["mom_63"], sub["fwd_10"])
        r = decile_spread(sub["rev_5"], sub["fwd_10"])
        v = decile_spread(sub["vol_ratio"], sub["fwd_10"])
        mk = float(sub["fwd_10"].mean())
        print(f"  {yr:<6} {m:>9.2f} {r:>9.2f} {v:>10.2f} {mk:>8.2f}")

    print("\nInterpretation: |IC| < ~0.02 and a small/unstable decile spread means the "
          "signal does NOT reliably predict returns — no threshold change makes an "
          "honest BUY out of it. A consistent positive spread across years means it does.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
