"""
Long-only, after-cost, walk-forward backtest of the model (#5).

The honest "would this have made money" test — realistic for a PSX retail user:
  - Every 10 trading days, rank all stocks by the model (fit ONLY on prior years).
  - Buy the top-N equal-weight, hold 10 trading days, then rebalance.
  - Charge a round-trip transaction cost on every rebalance.
  - Chain the periods into an equity curve; compare to the equal-weight market.

No shorting (you can't short easily on PSX). We report gross AND net at a couple
of cost levels, per-year and overall, plus max drawdown. Whatever it shows — good
or bad — is the honest answer.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "database" / "psx_terminal.db"
FEATURES = ["rvol_5", "rev_5", "vol_ratio", "mom_21", "rsi14", "dist_ma50", "dist_52w_high"]
HORIZON = 10
REBAL = 10          # rebalance every 10 trading days (non-overlapping)
MIN_PRICE = 2.0
MIN_OBS = 300


def load():
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


def feats(df):
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
    d = g["close"].transform(lambda s: s.diff())
    up = d.clip(lower=0).groupby(df["symbol"]).transform(lambda s: s.rolling(14).mean())
    dn = (-d.clip(upper=0)).groupby(df["symbol"]).transform(lambda s: s.rolling(14).mean())
    df["rsi14"] = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    df["fwd"] = g["close"].transform(lambda s: s.shift(-HORIZON) / s - 1) * 100.0
    # 20-day average traded value (PKR) — a liquidity proxy
    df["val20"] = (df["close"] * df["volume"]).groupby(df["symbol"]).transform(
        lambda s: s.rolling(20, min_periods=10).mean())
    df["year"] = df["date_parsed"].dt.year
    return df


def zsec(df):
    for c in FEATURES:
        gp = df.groupby("date_parsed")[c]
        df[c] = (df[c] - gp.transform("mean")) / gp.transform("std")
    df["fwd_ex"] = df["fwd"] - df.groupby("date_parsed")["fwd"].transform("mean")
    return df


def maxdd(equity):
    e = np.array(equity)
    return float((e / np.maximum.accumulate(e) - 1).min() * 100)


def run(top_n=10, cost=0.7, min_liq=0.0):
    df = zsec(feats(load())).replace([np.inf, -np.inf], np.nan).dropna(subset=FEATURES + ["fwd", "fwd_ex"])
    dates = np.sort(df["date_parsed"].unique())[::REBAL]
    coef_cache = {}
    strat, bench, eq, beq, yr_ret = [], [], [1.0], [1.0], {}
    for d in dates:
        y = pd.Timestamp(d).year
        if y not in coef_cache:
            tr = df[df["year"] < y]
            if len(tr) < 20000:
                continue
            coef_cache[y] = np.linalg.lstsq(tr[FEATURES].values, tr["fwd_ex"].values, rcond=None)[0]
        day = df[df["date_parsed"] == d]
        if min_liq > 0:
            day = day[day["val20"] >= min_liq]   # tradeable universe only
        if len(day) < 30:
            continue
        pred = day[FEATURES].values @ coef_cache[y]
        top = day.iloc[np.argsort(pred)[::-1][:top_n]]
        s_gross = float(top["fwd"].mean())
        b_gross = float(day["fwd"].mean())
        s_net = s_gross - cost
        strat.append(s_net); bench.append(b_gross)
        eq.append(eq[-1] * (1 + s_net / 100)); beq.append(beq[-1] * (1 + b_gross / 100))
        yr_ret.setdefault(y, []).append(s_net)

    n = len(strat)
    periods_per_year = 252 / REBAL
    cagr = (eq[-1] ** (periods_per_year / n) - 1) * 100 if n else 0
    bcagr = (beq[-1] ** (periods_per_year / n) - 1) * 100 if n else 0
    return {"top_n": top_n, "cost": cost, "n_trades": n,
            "total_return_pct": round((eq[-1] - 1) * 100, 1),
            "cagr_pct": round(cagr, 1), "bench_cagr_pct": round(bcagr, 1),
            "avg_net_per_rebal": round(float(np.mean(strat)), 2),
            "avg_bench_per_rebal": round(float(np.mean(bench)), 2),
            "win_rate_pct": round(float(np.mean(np.array(strat) > 0) * 100), 1),
            "max_drawdown_pct": round(maxdd(eq), 1),
            "by_year": {int(y): round(float(np.mean(v)), 2) for y, v in sorted(yr_ret.items())}}


def main():
    print(f"Long-only walk-forward backtest | hold/rebalance {REBAL}d | cost 0.7%\n")
    print("liquidity filter (20d avg traded value):")
    for label, min_liq in [("ALL stocks (incl. illiquid)", 0),
                           (">= 5m PKR/day", 5e6),
                           (">= 25m PKR/day (genuinely liquid)", 25e6),
                           (">= 100m PKR/day (very liquid)", 1e8)]:
        r = run(10, 0.7, min_liq)
        print(f"  {label:36} top10: CAGR {r['cagr_pct']:>6}% (mkt {r['bench_cagr_pct']:>5}%) "
              f"| net/rebal {r['avg_net_per_rebal']:>5}% vs {r['avg_bench_per_rebal']:>5}% "
              f"| maxDD {r['max_drawdown_pct']}% | {r['n_trades']} rebals")
    print("\nper-year net avg per rebalance (top10 @0.7%, >=25m PKR/day):")
    for y, v in run(10, 0.7, 25e6)["by_year"].items():
        print(f"  {y}: {v:+.2f}%")
    print("\nHonest read: the strategy is worth it only if net CAGR clearly beats the "
          "market AND drawdown is bearable AND it holds across years. Costs matter a lot.")


if __name__ == "__main__":
    main()
