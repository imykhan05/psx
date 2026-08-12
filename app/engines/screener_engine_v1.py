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
ALL_STOCKS_PATH = PROJECT_ROOT / "reports" / "latest" / "all_stocks.json"

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
    # Drop government paper / debt (PIB & Sukuk like 'P01GHS...', Term Finance
    # Certificates '...TFC...') — these are not equities and clutter stock screeners.
    sym = df["symbol"].astype(str)
    df = df[~(sym.str.match(r"^P\d") | sym.str.contains("TFC", na=False))]
    df = df.sort_values(["symbol", "date_parsed"])
    for col in ("open", "high", "low", "close", "volume", "prev_close", "change_pct"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    g = df.groupby("symbol", group_keys=False)
    df["ma50"] = g["close"].transform(lambda s: s.rolling(50, min_periods=50).mean())
    df["ma200"] = g["close"].transform(lambda s: s.rolling(200, min_periods=200).mean())
    df["avg_vol20"] = g["volume"].transform(lambda s: s.rolling(20, min_periods=10).mean())
    # Sustained relative volume (5-day avg vs 20-day avg) — the one accumulation
    # footprint that stayed weakly predictive in 2024-26 (see docs/EDGE_VALIDATION.md).
    df["rvol5"] = g["volume"].transform(lambda s: s.rolling(5, min_periods=3).mean()) / df["avg_vol20"]
    df["hi52"] = g["high"].transform(lambda s: s.rolling(252, min_periods=30).max())
    df["lo52"] = g["low"].transform(lambda s: s.rolling(252, min_periods=30).min())
    df["hi20"] = g["high"].transform(lambda s: s.rolling(20, min_periods=15).max())
    df["lo20"] = g["low"].transform(lambda s: s.rolling(20, min_periods=15).min())
    # N-trading-days-ago close for multi-timeframe returns (1w=5, 1m=21, 200d).
    df["c_1w"] = g["close"].transform(lambda s: s.shift(5))
    df["c_1m"] = g["close"].transform(lambda s: s.shift(21))
    df["c_200"] = g["close"].transform(lambda s: s.shift(200))

    latest = df.groupby("symbol").tail(1).copy()
    latest["as_of"] = latest["date_parsed"].dt.strftime("%Y-%m-%d")
    latest["ret_1w"] = (latest["close"] / latest["c_1w"] - 1.0) * 100.0
    latest["ret_1m"] = (latest["close"] / latest["c_1m"] - 1.0) * 100.0
    latest["ret_200d"] = (latest["close"] / latest["c_200"] - 1.0) * 100.0
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


def _merged_frame() -> pd.DataFrame:
    """Latest per-symbol technicals (SQLite) merged with scan scores (CSV)."""
    px = _load_prices()
    scores = _load_scores()
    if not scores.empty:
        df = px.merge(scores, on="symbol", how="left", suffixes=("", "_scan"))
        for c in ("company", "sector"):  # prefer scan company/sector when present
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
    df["dist_hi20"] = (df["hi20"] - df["close"]) / df["close"] * 100.0
    df["range20"] = (df["hi20"] - df["lo20"]) / df["lo20"] * 100.0
    # real fundamentals (P/E, EPS) if scraped (tools/fetch_fundamentals.py)
    try:
        from app.engines.fundamentals_store import load_all as _load_fund
        fund = _load_fund()
    except Exception:
        fund = {}
    df["pe_ttm"] = df["symbol"].map(lambda s: (fund.get(s) or {}).get("pe_ttm"))
    df["eps"] = df["symbol"].map(lambda s: (fund.get(s) or {}).get("eps"))
    return df


def build_all_stocks(df: pd.DataFrame | None = None) -> dict:
    """
    EVERY stock, ranked by the engine's real buy_probability, with a relative
    tier and multi-timeframe returns. This is deliberately NOT a buy list: it
    surfaces differentiation even when the engine rates everything AVOID (it
    shows the true probability + where each stock ranks, not a fake BUY).
    """
    if df is None:
        df = _merged_frame()
    d = df.copy()
    d["buy_probability"] = pd.to_numeric(d.get("buy_probability"), errors="coerce")
    d = d.sort_values("buy_probability", ascending=False, na_position="last").reset_index(drop=True)
    n = len(d)
    d["rank"] = range(1, n + 1)

    def tier(rank: int) -> str:
        p = rank / max(n, 1)
        if p <= 0.10:
            return "Top 10%"
        if p <= 0.25:
            return "Top 25%"
        if p <= 0.50:
            return "Top 50%"
        return "Bottom 50%"

    d["tier"] = d["rank"].map(tier)

    cols = ["rank", "tier", "symbol", "company", "sector", "close", "change_pct",
            "ret_1w", "ret_1m", "ret_200d", "buy_probability", "final_decision",
            "above_ma50", "above_ma200", "stop_loss", "target_1", "target_2"]
    out = d[[c for c in cols if c in d.columns]].replace({np.nan: None})
    rows = out.to_dict(orient="records")
    for r in rows:
        for k, v in r.items():
            if isinstance(v, float):
                r[k] = round(v, 2)
            elif isinstance(v, bool):
                r[k] = bool(v)

    as_of = d["as_of"].dropna().max() if "as_of" in d else None
    return {
        "engine_version": "screener_engine_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of_date": as_of,
        "count": n,
        "note": "Ranked by the engine's real buy_probability. A high rank means "
                "'relatively strongest today', NOT a validated buy — the whole "
                "market may still be rated AVOID, and the rule edge is unproven.",
        "rows": rows,
    }


def build_screeners(df: pd.DataFrame | None = None) -> dict:
    if df is None:
        df = _merged_frame()

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

    add("accumulation_radar", "Accumulation radar (sustained volume)",
        "Sustained unusually high volume: the 5-day average volume is >= 1.5x the "
        "20-day average — a footprint of large buyers accumulating over days. This is "
        "the ONE accumulation signal that stayed (weakly) predictive in 2024-26: "
        "~+0.5-1% edge over the next week (see docs/EDGE_VALIDATION.md). Small and thin "
        "after costs — a lead to watch, NOT a guaranteed buy.",
        df[df["rvol5"] >= 1.5], "rvol5", False,
        ["rvol5", "vol_ratio", "change_pct", "final_decision"])

    add("near_52w_high", "Near 52-week high (breakout candidates)",
        "Within 5% of the 52-week high.",
        df[(df["pct_to_52w_high"] >= 0) & (df["pct_to_52w_high"] <= 5)],
        "pct_to_52w_high", True, ["hi52", "pct_to_52w_high", "final_decision"])

    # ---- patterns & levels (#9) ----
    add("breakout_vol", "Breakout on volume (new 20-day high)",
        "Closed at a new 20-day high WITH sustained volume (5d avg >= 1.3x the 20d) "
        "— the classic accumulation-then-breakout. A setup to watch, not a "
        "guaranteed continuation.",
        df[(df["close"] >= df["hi20"] * 0.999) & (df["rvol5"] >= 1.3)],
        "rvol5", False, ["rvol5", "change_pct", "hi20", "final_decision"])

    add("near_breakout", "Near breakout (just under 20-day high)",
        "Coiling within 3% below its 20-day high — a break above (ideally on volume) "
        "could trigger a move. Watch, don't assume.",
        df[(df["dist_hi20"] >= 0.1) & (df["dist_hi20"] <= 3.0)],
        "dist_hi20", True, ["dist_hi20", "rvol5", "change_pct", "final_decision"])

    coil_thr = float(df["range20"].quantile(0.20)) if df["range20"].notna().any() else None
    if coil_thr is not None:
        add("coil", "Tight consolidation (coiling)",
            "20-day price range is in the tightest ~20% of the market — a "
            "low-volatility 'coil' that sometimes precedes a bigger move (either "
            "direction). Direction is not predicted.",
            df[(df["range20"] <= coil_thr) & (df["range20"] > 0)],
            "range20", True, ["range20", "rvol5", "change_pct", "final_decision"])

    add("pullback_uptrend", "Pullback to MA50 in an uptrend",
        "Above the 200-day MA (long-term up) and now within ~4% of the 50-day MA — "
        "a pullback to support inside an uptrend. A setup, not a guarantee.",
        df[df["above_ma200"] & (df["close"] >= df["ma50"]) & (df["close"] <= df["ma50"] * 1.04)],
        "buy_probability", False, ["ma50", "change_pct", "final_decision"])

    # ---- fundamentals (real PSX data, if scraped) ----
    df["pe_ttm"] = pd.to_numeric(df.get("pe_ttm"), errors="coerce")
    if df["pe_ttm"].notna().any():
        add("value_low_pe", "Value — low P/E (real fundamentals)",
            "Low trailing P/E, using REAL fundamentals scraped from the PSX company "
            "pages. Low P/E can mean genuinely cheap OR a troubled business — a "
            "starting point for research, not a buy signal.",
            df[(df["pe_ttm"] > 0) & (df["pe_ttm"] < 8)], "pe_ttm", True,
            ["pe_ttm", "eps", "change_pct", "final_decision"])

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
    df = _merged_frame()
    payload = build_screeners(df)
    all_stocks = build_all_stocks(df)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    ALL_STOCKS_PATH.write_text(json.dumps(all_stocks, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


if __name__ == "__main__":
    p = run_screener_engine()
    print(f"as_of {p['as_of_date']} | universe {p['universe']}")
    for name, s in p["screeners"].items():
        print(f"  {name:16} {s['count']:4}  {s['label']}")
