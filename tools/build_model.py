"""
Walk-forward cross-sectional model (F1.3 / the honest "real model").

Combines the features we measured into one linear factor model and tests it the
ONLY way that means anything: walk-forward, out-of-sample. Each test year, the
model is fit on data from BEFORE that year only, then used to rank stocks in the
(unseen) test year. We report the realized top-decile-minus-bottom-decile forward
return and rank IC per year — and a net-of-costs estimate.

No sklearn — a plain numpy least-squares linear model, cross-sectionally
standardised, so it is fully interpretable and light. Features:
  rvol_5, rev_5, vol_ratio, mom_21, rsi14, dist_ma50, dist_52w_high
Target: forward-10-day return, demeaned within each date (relative performance).

If the out-of-sample long-short spread stays clearly positive after ~0.6% round-
trip cost, the model has a real edge. If not, it does not — and we say so.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "database" / "psx_terminal.db"
FWD = 10
MIN_PRICE = 2.0
MIN_OBS = 300
COST_ROUNDTRIP = 0.6  # % — rough PSX commission+tax round-trip, for a net estimate
FEATURES = ["rvol_5", "rev_5", "vol_ratio", "mom_21", "rsi14", "dist_ma50", "dist_52w_high"]


def load() -> pd.DataFrame:
    con = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query("SELECT date_parsed, symbol, high, low, close, volume FROM daily_prices", con)
    finally:
        con.close()
    df["date_parsed"] = pd.to_datetime(df["date_parsed"], format="ISO8601", errors="coerce")
    for c in ("high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["date_parsed", "close"]).sort_values(["symbol", "date_parsed"])
    sym = df["symbol"].astype(str)
    df = df[~(sym.str.match(r"^P\d") | sym.str.contains("TFC", na=False))]
    counts = df.groupby("symbol")["close"].transform("size")
    return df[(counts >= MIN_OBS) & (df["close"] >= MIN_PRICE)].copy()


def features(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("symbol", group_keys=False)
    avg20 = g["volume"].transform(lambda s: s.rolling(20, min_periods=15).mean())
    df["rvol_5"] = g["volume"].transform(lambda s: s.rolling(5, min_periods=3).mean()) / avg20
    df["vol_ratio"] = df["volume"] / avg20
    df["rev_5"] = -(g["close"].transform(lambda s: s / s.shift(5) - 1))
    df["mom_21"] = g["close"].transform(lambda s: s / s.shift(21) - 1)
    ma50 = g["close"].transform(lambda s: s.rolling(50, min_periods=50).mean())
    hi52 = g["high"].transform(lambda s: s.rolling(252, min_periods=30).max())
    df["dist_ma50"] = df["close"] / ma50 - 1
    df["dist_52w_high"] = df["close"] / hi52 - 1
    delta = g["close"].transform(lambda s: s.diff())
    up = delta.clip(lower=0).groupby(df["symbol"]).transform(lambda s: s.rolling(14).mean())
    dn = (-delta.clip(upper=0)).groupby(df["symbol"]).transform(lambda s: s.rolling(14).mean())
    df["rsi14"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    df["fwd"] = g["close"].transform(lambda s: s.shift(-FWD) / s - 1) * 100.0
    df["year"] = df["date_parsed"].dt.year
    return df


def _xsec_z(df: pd.DataFrame, cols):
    """Cross-sectionally standardise each feature within each date."""
    out = df.copy()
    for c in cols:
        grp = out.groupby("date_parsed")[c]
        out[c] = (out[c] - grp.transform("mean")) / grp.transform("std")
    # demean target within date (relative performance)
    grp = out.groupby("date_parsed")["fwd"]
    out["fwd_ex"] = out["fwd"] - grp.transform("mean")
    return out


def _spread(pred, realized):
    m = ~(np.isnan(pred) | np.isnan(realized))
    if m.sum() < 1000:
        return np.nan, np.nan
    p, r = pred[m], realized[m]
    d = pd.qcut(pd.Series(p).rank(method="first"), 10, labels=False)
    grp = pd.Series(r).groupby(d.values).mean()
    spread = float(grp.iloc[-1] - grp.iloc[0])
    ic = float(pd.Series(p).rank().corr(pd.Series(r).rank()))
    return spread, ic


def main() -> int:
    print("loading + building features (this takes a moment)...")
    df = _xsec_z(features(load()), FEATURES)
    df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=FEATURES + ["fwd", "fwd_ex"])
    print(f"usable stock-days: {len(df):,}\n")

    years = sorted(y for y in df["year"].unique() if y >= 2019)
    print(f"{'test yr':7} {'OOS spread':>11} {'net(-0.6%)':>11} {'IC':>7} {'train n':>9}")
    print("-" * 50)
    spreads = []
    for y in years:
        tr = df[df["year"] < y]
        te = df[df["year"] == y]
        if len(tr) < 20000 or len(te) < 2000:
            continue
        X, yv = tr[FEATURES].values, tr["fwd_ex"].values
        coef, *_ = np.linalg.lstsq(X, yv, rcond=None)
        pred = te[FEATURES].values @ coef
        spread, ic = _spread(pred, te["fwd"].values)
        if not np.isnan(spread):
            spreads.append(spread)
            print(f"{y:<7} {spread:>10.2f}% {spread - COST_ROUNDTRIP:>10.2f}% {ic:>7.3f} {len(tr):>9,}")

    if spreads:
        avg = float(np.mean(spreads))
        pos = sum(1 for s in spreads if s > COST_ROUNDTRIP)
        print("-" * 50)
        print(f"avg OOS long-short spread: {avg:+.2f}% over {FWD}d "
              f"({avg - COST_ROUNDTRIP:+.2f}% net of ~{COST_ROUNDTRIP}% cost)")
        print(f"years beating cost: {pos}/{len(spreads)}")
        print("\nVERDICT: a small, real edge only if the NET spread is clearly "
              "positive in MOST years. A ~zero or unstable net = the model does not "
              "beat the market out-of-sample, and honesty means saying so.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
