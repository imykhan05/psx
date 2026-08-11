"""
Test the user's hypothesis: big buyers ("crocodiles"/institutions) accumulate a
stock over a few days, it runs for ~1 week, then they rotate to the next names.

We can't see real institutional holdings — but we CAN measure volume/price
footprints consistent with accumulation, and then check (no look-ahead) whether a
fresh footprint predicts the NEXT 5 and 10 trading days' return. If it does, this
is a real, honest edge to build on. If not, we say so.

Footprint signals (each computed from data up to day t only):
  rvol_5        mean(vol,5d) / mean(vol,20d prior)     — sustained unusual volume
  buy_pressure  up-day volume / total volume, last 10d — buyers vs sellers
  obv_norm      10-day On-Balance-Volume change / (20d avg vol) — net money flow
  close_str_5   mean of (close-low)/(high-low), 5d      — closing near highs
  accum         average z-score of the four above       — composite footprint

Targets: fwd_5 and fwd_10 (strictly future returns, %).
Report: Spearman IC + top-minus-bottom decile forward return, pooled and per year.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "database" / "psx_terminal.db"
MIN_PRICE = 2.0
MIN_OBS = 300


def load() -> pd.DataFrame:
    con = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(
            "SELECT date_parsed, symbol, open, high, low, close, volume FROM daily_prices", con
        )
    finally:
        con.close()
    df["date_parsed"] = pd.to_datetime(df["date_parsed"], format="ISO8601", errors="coerce")
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["date_parsed", "close"]).sort_values(["symbol", "date_parsed"])
    counts = df.groupby("symbol")["close"].transform("size")
    return df[(counts >= MIN_OBS) & (df["close"] >= MIN_PRICE)].copy()


def zscore(s: pd.Series) -> pd.Series:
    sd = s.std()
    return (s - s.mean()) / sd if sd and not np.isnan(sd) else s * 0.0


def build(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("symbol", group_keys=False)
    ret1 = g["close"].transform(lambda s: s / s.shift(1) - 1)
    df["ret1"] = ret1
    avg20 = g["volume"].transform(lambda s: s.rolling(20, min_periods=15).mean().shift(1))
    df["rvol_5"] = g["volume"].transform(lambda s: s.rolling(5, min_periods=3).mean()) / avg20

    up_vol = (df["volume"] * (ret1 > 0)).astype(float)
    tot_vol = df["volume"].astype(float)
    df["buy_pressure"] = (
        up_vol.groupby(df["symbol"]).transform(lambda s: s.rolling(10, min_periods=5).sum())
        / tot_vol.groupby(df["symbol"]).transform(lambda s: s.rolling(10, min_periods=5).sum())
    )

    signed_vol = np.sign(ret1.fillna(0)) * df["volume"]
    obv = signed_vol.groupby(df["symbol"]).transform(lambda s: s.cumsum())
    obv_chg = obv.groupby(df["symbol"]).transform(lambda s: s - s.shift(10))
    df["obv_norm"] = obv_chg / (avg20 * 10.0)

    rng = (df["high"] - df["low"]).replace(0, np.nan)
    cp = (df["close"] - df["low"]) / rng
    df["close_str_5"] = cp.groupby(df["symbol"]).transform(lambda s: s.rolling(5, min_periods=3).mean())

    df["accum"] = (
        zscore(df["rvol_5"]) + zscore(df["buy_pressure"])
        + zscore(df["obv_norm"]) + zscore(df["close_str_5"])
    ) / 4.0

    df["fwd_5"] = g["close"].transform(lambda s: s.shift(-5) / s - 1) * 100.0
    df["fwd_10"] = g["close"].transform(lambda s: s.shift(-10) / s - 1) * 100.0
    df["year"] = df["date_parsed"].dt.year
    return df


def ic(sig, fwd):
    m = sig.notna() & fwd.notna()
    return float(sig[m].rank().corr(fwd[m].rank())) if m.sum() >= 500 else np.nan


def spread(sig, fwd):
    m = sig.notna() & fwd.notna()
    if m.sum() < 1000:
        return np.nan
    try:
        d = pd.qcut(sig[m].rank(method="first"), 10, labels=False)
    except ValueError:
        return np.nan
    grp = fwd[m].groupby(d).mean()
    return float(grp.iloc[-1] - grp.iloc[0])


def main() -> int:
    print("loading + building accumulation footprints...")
    df = build(load())
    print(f"stock-days: {int(df['fwd_5'].notna().sum()):,} | "
          f"market avg fwd_5={df['fwd_5'].mean():+.2f}% fwd_10={df['fwd_10'].mean():+.2f}%\n")

    sigs = ["rvol_5", "buy_pressure", "obv_norm", "close_str_5", "accum"]
    print(f"{'signal':13} {'IC_5':>7} {'spread_5':>9} {'IC_10':>7} {'spread_10':>10}")
    print("-" * 50)
    for s in sigs:
        print(f"{s:13} {ic(df[s], df['fwd_5']):>7.3f} {spread(df[s], df['fwd_5']):>9.2f} "
              f"{ic(df[s], df['fwd_10']):>7.3f} {spread(df[s], df['fwd_10']):>10.2f}")

    print("\nper-year top-minus-bottom decile fwd_5 (%), by signal:")
    print(f"  {'year':6} {'rvol_5':>8} {'buy_prs':>8} {'obv':>8} {'accum':>8} {'market':>8}")
    for yr, sub in df.groupby("year"):
        print(f"  {yr:<6} {spread(sub['rvol_5'], sub['fwd_5']):>8.2f} "
              f"{spread(sub['buy_pressure'], sub['fwd_5']):>8.2f} "
              f"{spread(sub['obv_norm'], sub['fwd_5']):>8.2f} "
              f"{spread(sub['accum'], sub['fwd_5']):>8.2f} "
              f"{float(sub['fwd_5'].mean()):>8.2f}")

    print("\nRead: a signal with positive IC AND a positive, year-after-year decile "
          "spread (esp. recently) is a real accumulation edge worth building on.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
