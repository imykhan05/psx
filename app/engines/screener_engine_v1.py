"""
Screener Engine v1 — "click-and-go" stock lists from real EOD data.

Produces a set of named screeners the user can browse (web UI / API). Every
screener is computed from data we actually have, and each carries an honest
`note` about what it does and does NOT mean:

  Technical (from SQLite daily_prices — OHLC/volume history, fully real):
    upper_circuit   near the +7.5% upper lock today (proxy from OHLC)
    top_gainers     biggest % gainers today
    top_losers      biggest % losers today
    most_active     highest traded value today
    above_ma50      trading above the 50-day moving average (short-term up)
    above_ma200     trading above the 200-day moving average (long-term up)
    ma_golden       close > MA50 > MA200 (aligned uptrend)
    volume_spike    volume >= 2x its 20-day average, price up (breakout/interest)
    near_52w_high   within 5% of the 52-week high (breakout candidates)

  Scored (from the rule pipeline's full_market_scan.csv):
    top_picks       rule decision = BUY / WATCH  (edge NOT yet validated)
    accumulation    high accumulation/institutional SIGNAL (inferred from
                    volume+price — NOT verified institutional holdings)
    down_but_strong down today but still above MA50 with a decent buy score

What this is NOT: it is not a fundamentals screen (we have no real fundamentals)
and not a price forecast. It flags setups from end-of-day data; acting on them is
the user's decision.
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
OUT_PATH = PROJECT_ROOT / "reports" / "latest" / "screeners.json"

# PSX normal circuit breaker is +/-7.5%; use a hair under as the "at upper lock".
UPPER_CIRCUIT_PCT = 7.4
LOOKBACK_DAYS = 420  # calendar days pulled to compute MA200 / 52-week levels
TOP_N = 30          # rows kept per screener


def _load_prices() -> pd.DataFrame:
    """Recent daily_prices with per-symbol MA50/MA200/avg-vol/52w levels."""
    con = sqlite3.connect(DB_PATH)
    try:
        max_date = pd.read_sql_query(
            "SELECT MAX(date_parsed) AS m FROM daily_prices", con
        )["m"].iloc[0]
        cutoff = (pd.Timestamp(max_date) - pd.Timedelta(days=LOOKBACK_DAYS)).strftime(
            "%Y-%m-%d"
        )
        df = pd.read_sql_query(
            """
            SELECT date_parsed, symbol, company, open, high, low, close,
                   volume, prev_close, change_pct
            FROM daily_prices
            WHERE date_parsed >= ?
            """,
            con,
            params=[cutoff],
        )
    finally:
        con.close()

    df["date_parsed"] = pd.to_datetime(df["date_parsed"], format="ISO8601", errors="coerce")
    df = df.sort_values(["symbol", "date_parsed"])
    for col in ("open", "high", "low", "close", "volume", "prev_close", "change_pct"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    g = df.groupby("symbol", group_keys=False)
    df["ma50"] = g["close"].transform(lambda s: s.rolling(50, min_periods=50).mean())
    df["ma200"] = g["close"].transform(lambda s: s.rolling(200, min_periods=200).mean())
    df["avg_vol20"] = g["volume"].transform(lambda s: s.rolling(20, min_periods=10).mean())
    df["hi52"] = g["high"].transform(lambda s: s.rolling(252, min_periods=30).max())
    df["lo52"] = g["low"].transform(lambda s: s.rolling(252, min_periods=30).min())

    latest = df.groupby("symbol").tail(1).copy()
    latest["as_of"] = latest["date_parsed"].dt.strftime("%Y-%m-%d")
    return latest


def _load_scores() -> pd.DataFrame:
    if not SCAN_CSV.exists() or SCAN_CSV.stat().st_size == 0:
        return pd.DataFrame()
    try:
        s = pd.read_csv(SCAN_CSV, encoding="utf-8-sig")
    except Exception:
        return pd.DataFrame()
    keep = [
        "symbol", "company", "sector", "final_decision", "buy_probability",
        "smart_money_score", "accumulation_score", "institutional_signal",
        "value_traded", "stop_loss", "target_1", "target_2",
    ]
    return s[[c for c in keep if c in s.columns]].copy()


def _rows(df: pd.DataFrame, extra: list[str]) -> list[dict]:
    """Serialise selected columns to clean JSON records (NaN -> None)."""
    base = ["symbol", "company", "sector", "close", "change_pct"]
    cols = base + [c for c in extra if c in df.columns and c not in base]
    out = df[cols].replace({np.nan: None})
    recs = out.to_dict(orient="records")
    for r in recs:  # round floats for compactness
        for k, v in r.items():
            if isinstance(v, float):
                r[k] = round(v, 2)
    return recs


def build_screeners() -> dict:
    px = _load_prices()
    scores = _load_scores()
    if not scores.empty:
        df = px.merge(scores, on="symbol", how="left", suffixes=("", "_scan"))
        # prefer scan company/sector when present
        for c in ("company", "sector"):
            sc = f"{c}_scan"
            if sc in df.columns:
                df[c] = df[sc].where(df[sc].notna(), df.get(c))
                df.drop(columns=[sc], inplace=True)
    else:
        df = px
        for c in ("final_decision", "buy_probability", "smart_money_score",
                  "accumulation_score", "institutional_signal", "value_traded",
                  "stop_loss", "target_1", "target_2"):
            df[c] = np.nan

    df["above_ma50"] = df["close"] > df["ma50"]
    df["above_ma200"] = df["close"] > df["ma200"]
    df["vol_ratio"] = df["volume"] / df["avg_vol20"]
    df["pct_to_52w_high"] = (df["hi52"] - df["close"]) / df["hi52"] * 100.0

    as_of = df["as_of"].dropna().max() if "as_of" in df else None
    S: dict[str, dict] = {}

    def add(name, label, note, subset, sort_col, ascending, extra):
        sub = subset.sort_values(sort_col, ascending=ascending).head(TOP_N)
        S[name] = {"label": label, "note": note, "count": int(len(sub)),
                   "rows": _rows(sub, extra)}

    add("upper_circuit", "Upper-lock (closed at day's high)",
        "Big gain today AND closed at/near the day's high — typically upper-circuit "
        "locked. The standard PSX band is +7.5%, but rights letters (R), SPACs and "
        "some securities have wider bands, so larger moves can appear here.",
        df[(df["change_pct"] >= UPPER_CIRCUIT_PCT) & (df["close"] >= df["high"] * 0.999)],
        "change_pct", False, ["volume", "final_decision"])

    add("top_gainers", "Top gainers today", "Biggest positive % change today.",
        df[df["change_pct"] > 0], "change_pct", False, ["volume", "final_decision"])

    add("top_losers", "Top losers today", "Biggest negative % change today.",
        df[df["change_pct"] < 0], "change_pct", True, ["volume", "final_decision"])

    add("most_active", "Most active (value traded)", "Highest traded value today.",
        df[df["value_traded"].notna()], "value_traded", False, ["value_traded", "change_pct"])

    add("above_ma200", "Above 200-day MA (long-term uptrend)",
        "Close above the 200-day moving average.",
        df[df["above_ma200"]], "change_pct", False, ["ma200", "buy_probability", "final_decision"])

    add("above_ma50", "Above 50-day MA (short-term uptrend)",
        "Close above the 50-day moving average.",
        df[df["above_ma50"]], "change_pct", False, ["ma50", "buy_probability", "final_decision"])

    add("ma_golden", "Aligned uptrend (Close > MA50 > MA200)",
        "Price above both averages and MA50 above MA200 — a clean uptrend structure.",
        df[df["above_ma50"] & df["above_ma200"] & (df["ma50"] > df["ma200"])],
        "change_pct", False, ["ma50", "ma200", "final_decision"])

    add("volume_spike", "Volume spike (>= 2x avg, price up)",
        "Volume at least 2x its 20-day average with price up — unusual interest.",
        df[(df["vol_ratio"] >= 2.0) & (df["change_pct"] > 0)],
        "vol_ratio", False, ["vol_ratio", "volume", "final_decision"])

    add("near_52w_high", "Near 52-week high (breakout candidates)",
        "Within 5% of the 52-week high.",
        df[(df["pct_to_52w_high"] >= 0) & (df["pct_to_52w_high"] <= 5)],
        "pct_to_52w_high", True, ["hi52", "pct_to_52w_high", "final_decision"])

    # ---- scored screeners (only if the scan provided the columns) ----
    if df["final_decision"].notna().any():
        picks = df[df["final_decision"].astype(str).str.upper().isin(["BUY", "WATCH"])]
        add("top_picks", "Rule picks (BUY / WATCH)",
            "The rule pipeline's own BUY/WATCH calls. NOTE: this edge is NOT yet "
            "validated to beat the market — treat as a starting list, not a promise.",
            picks, "buy_probability", False,
            ["buy_probability", "final_decision", "stop_loss", "target_1", "target_2"])

    if df["accumulation_score"].notna().any():
        add("accumulation", "Accumulation signal (inferred)",
            "High accumulation/smart-money SIGNAL, inferred from volume+price. This "
            "is NOT verified institutional holdings data — it is a heuristic proxy.",
            df[df["accumulation_score"].notna()], "accumulation_score", False,
            ["accumulation_score", "smart_money_score", "final_decision"])

    if df["buy_probability"].notna().any():
        add("down_but_strong", "Down today but strong setup",
            "Red today yet still above the 50-day MA with a decent buy score — "
            "possible pullbacks in an uptrend. A setup, not a forecast.",
            df[(df["change_pct"] < 0) & (df["above_ma50"]) & (df["buy_probability"] >= 40)],
            "buy_probability", False, ["buy_probability", "ma50", "final_decision"])

    return {
        "engine_version": "screener_engine_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of_date": as_of,
        "universe": int(df["symbol"].nunique()),
        "screeners": S,
    }


def run_screener_engine() -> dict:
    payload = build_screeners()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


if __name__ == "__main__":
    p = run_screener_engine()
    print(f"as_of {p['as_of_date']} | universe {p['universe']}")
    for name, s in p["screeners"].items():
        print(f"  {name:16} {s['count']:4}  {s['label']}")
