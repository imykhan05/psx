"""
Model Engine v1 — the honest, walk-forward-validated ranking model.

A plain linear cross-sectional factor model (numpy least-squares, no black box)
over features that were individually measured (docs/EDGE_VALIDATION.md):
  rvol_5, rev_5, vol_ratio, mom_21, rsi14, dist_ma50, dist_52w_high

Walk-forward out-of-sample (tools/build_model.py) it produced a top-minus-bottom
decile spread of ~+3.8%/10d (~+3.2% net of ~0.6% cost), positive in 7 of the last
8 years. That is a REAL edge — but read VALIDATION/CAVEATS below before trusting it.

This engine fits on ALL history and scores TODAY's stocks into a relative rank.
It is NOT an "80% buy this" oracle: the per-name signal is weak (IC ~0.08); the
edge shows up across a diversified BASKET of the top-ranked names over ~2 weeks,
and much of the measured spread is long-SHORT (shorting is impractical on PSX, so
a long-only user captures roughly half). Costs, liquidity and regime shifts can
erode it (2025 was flat).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "database" / "psx_terminal.db"
SCAN_CSV = PROJECT_ROOT / "reports" / "latest" / "full_market_scan.csv"
OUT_PATH = PROJECT_ROOT / "reports" / "latest" / "model_picks.json"

FEATURES = ["rvol_5", "rev_5", "vol_ratio", "mom_21", "rsi14", "dist_ma50", "dist_52w_high"]
FWD = 10
MIN_PRICE = 2.0
LOOKBACK_FIT_DAYS = 1500  # ~6y of history is plenty to fit 7 coefficients

# Measured out-of-sample track record (from tools/build_model.py, 2019-2026).
VALIDATION = {
    "method": "walk-forward out-of-sample, cross-sectional linear model",
    "horizon_days": FWD,
    "avg_longshort_spread_pct": 3.76,
    "avg_net_of_cost_pct": 3.16,
    "years_tested": 8,
    "years_beating_cost": 7,
    "worst_year": "2025 (net -0.3%)",
    "ic_range": "0.05-0.12",
}
CAVEATS = [
    "Diversified basket edge over ~2 weeks — NOT a per-stock 80% prediction (IC ~0.08).",
    "Much of the spread is long-SHORT; shorting is impractical on PSX, so long-only "
    "captures roughly half.",
    "Costs, slippage and low liquidity in small names can erode the net edge.",
    "One tested year (2025) was flat/negative — the edge is real on average, not every year.",
    "Past out-of-sample performance is not a guarantee of future results.",
]


def _load() -> pd.DataFrame:
    con = sqlite3.connect(DB_PATH)
    try:
        max_d = pd.read_sql_query("SELECT MAX(date_parsed) m FROM daily_prices", con)["m"].iloc[0]
        cutoff = (pd.Timestamp(max_d) - pd.Timedelta(days=int(LOOKBACK_FIT_DAYS * 1.5))).strftime("%Y-%m-%d")
        df = pd.read_sql_query(
            "SELECT date_parsed, symbol, high, low, close, volume FROM daily_prices "
            "WHERE date_parsed >= ?", con, params=[cutoff])
    finally:
        con.close()
    df["date_parsed"] = pd.to_datetime(df["date_parsed"], format="ISO8601", errors="coerce")
    for c in ("high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["date_parsed", "close"]).sort_values(["symbol", "date_parsed"])
    sym = df["symbol"].astype(str)
    df = df[~(sym.str.match(r"^P\d") | sym.str.contains("TFC", na=False))]
    return df[df["close"] >= MIN_PRICE].copy()


def _features(df: pd.DataFrame) -> pd.DataFrame:
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
    return df


def _xsec_z(df: pd.DataFrame, cols):
    out = df.copy()
    for c in cols:
        grp = out.groupby("date_parsed")[c]
        out[c] = (out[c] - grp.transform("mean")) / grp.transform("std")
    return out


def build_model_picks(top_n: int = 30) -> dict:
    raw = _features(_load())
    z = _xsec_z(raw, FEATURES)
    last_date = z["date_parsed"].max()

    # fit on everything that has a realized forward return (i.e. excludes the tail)
    grp = z.groupby("date_parsed")["fwd"]
    z["fwd_ex"] = z["fwd"] - grp.transform("mean")
    train = z.replace([np.inf, -np.inf], np.nan).dropna(subset=FEATURES + ["fwd_ex"])
    coef, *_ = np.linalg.lstsq(train[FEATURES].values, train["fwd_ex"].values, rcond=None)

    # score the latest date's stocks
    today = z[z["date_parsed"] == last_date].dropna(subset=FEATURES).copy()
    today["model_score"] = today[FEATURES].values @ coef
    today = today.sort_values("model_score", ascending=False).reset_index(drop=True)
    n = len(today)
    today["model_rank"] = range(1, n + 1)

    # attach company/sector/decision/price from the scan
    meta = {}
    if SCAN_CSV.exists():
        try:
            s = pd.read_csv(SCAN_CSV, encoding="utf-8-sig")
            for _, r in s.iterrows():
                meta[str(r.get("symbol"))] = {
                    "company": r.get("company"), "sector": r.get("sector"),
                    "close": r.get("close"), "change_pct": r.get("change_pct"),
                    "final_decision": r.get("final_decision"),
                }
        except Exception:
            pass

    def row(r):
        m = meta.get(r["symbol"], {})
        sc = None if pd.isna(r["model_score"]) else round(float(r["model_score"]), 3)
        return {"rank": int(r["model_rank"]), "symbol": r["symbol"],
                "company": m.get("company"), "sector": m.get("sector"),
                "close": m.get("close"), "change_pct": m.get("change_pct"),
                "final_decision": m.get("final_decision"), "model_score": sc}

    top = [row(r) for _, r in today.head(top_n).iterrows()]
    bottom = [row(r) for _, r in today.tail(min(top_n, 10)).iloc[::-1].iterrows()]

    return {
        "engine_version": "model_engine_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of_date": str(last_date.date()),
        "universe": n,
        "coefficients": {f: round(float(c), 4) for f, c in zip(FEATURES, coef)},
        "validation": VALIDATION,
        "caveats": CAVEATS,
        "note": ("Relative ranking from a walk-forward-validated linear model. The "
                 "top names, as a diversified basket, have historically beaten the "
                 "bottom over ~2 weeks out-of-sample. A real but SMALL edge — read the "
                 "caveats. Not financial advice."),
        "top": top,
        "bottom": bottom,
    }


def run_model_engine() -> dict:
    payload = build_model_picks()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


if __name__ == "__main__":
    p = run_model_engine()
    print(f"as_of {p['as_of_date']} | universe {p['universe']}")
    print("coefficients:", p["coefficients"])
    print("top 10 model picks:")
    for r in p["top"][:10]:
        print(f"  #{r['rank']:>2} {r['symbol']:8} score={r['model_score']} "
              f"{r.get('final_decision')}")
