"""
Morning Briefing Engine v1 — a pre-market daily summary.

Runs ~9 AM. It does NOT forecast the day (before the 9:30 open there is no new
price data). It summarises the LATEST end-of-day scan across multiple timeframes
plus this morning's news, so the user walks in with context:

  - market pulse (verdict / breadth from the daily signal)
  - day / week / month / 200-day trend of the whole market (median move,
    % positive, % above MA50/MA200)
  - top movers over week / month / 200 days
  - the relatively strongest setups (top of the buy_probability ranking)
  - news sentiment snapshot

Reads only the pipeline's own JSON outputs (no SQLite, no model):
  reports/latest/all_stocks.json (per-stock returns + rank, from the screener),
  database/ai_learning/daily_signal.json, database/ai_learning/sentiment_cache.json.

HONESTY: everything here is analysis of past/【latest EOD】 data + news. It is NOT
a validated prediction of today's moves, and the rule edge is unproven.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALL_STOCKS = PROJECT_ROOT / "reports" / "latest" / "all_stocks.json"
DAILY_SIGNAL = PROJECT_ROOT / "database" / "ai_learning" / "daily_signal.json"
SENTIMENT = PROJECT_ROOT / "database" / "ai_learning" / "sentiment_cache.json"
OUT_PATH = PROJECT_ROOT / "reports" / "latest" / "morning_briefing.json"

TOP_N = 8


def _read_json(path: Path) -> dict:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _tf(df: pd.DataFrame, col: str) -> dict:
    s = pd.to_numeric(df.get(col), errors="coerce").dropna()
    if s.empty:
        return {"median_pct": None, "pct_positive": None, "count": 0}
    return {
        "median_pct": round(float(s.median()), 2),
        "pct_positive": round(float((s > 0).mean() * 100), 1),
        "count": int(s.size),
    }


def _movers(df: pd.DataFrame, col: str, ascending: bool, n: int = 5) -> list[dict]:
    s = df.dropna(subset=[col]).sort_values(col, ascending=ascending).head(n)
    out = s[["symbol", "company", "close", col, "final_decision"]].replace({np.nan: None})
    recs = out.to_dict(orient="records")
    for r in recs:
        for k, v in r.items():
            if isinstance(v, float):
                r[k] = round(v, 2)
    return recs


def build_briefing() -> dict:
    allx = _read_json(ALL_STOCKS)
    rows = allx.get("rows", [])
    df = pd.DataFrame(rows)
    signal = _read_json(DAILY_SIGNAL)
    sent = _read_json(SENTIMENT)

    as_of = allx.get("as_of_date") or signal.get("date")

    # --- market pulse ---
    market = {
        "verdict": signal.get("verdict"),
        "confidence": signal.get("confidence"),
        "reason": (signal.get("reasons") or [None])[0],
        "as_of_date": as_of,
    }

    # --- multi-timeframe market trend ---
    timeframes = {}
    movers = {}
    if not df.empty:
        for name, col in (("day", "change_pct"), ("week", "ret_1w"),
                          ("month", "ret_1m"), ("d200", "ret_200d")):
            timeframes[name] = _tf(df, col)
        if "above_ma50" in df:
            timeframes["week"]["pct_above_ma50"] = round(
                float(pd.Series(df["above_ma50"]).fillna(False).mean() * 100), 1
            )
        if "above_ma200" in df:
            timeframes["d200"]["pct_above_ma200"] = round(
                float(pd.Series(df["above_ma200"]).fillna(False).mean() * 100), 1
            )

        movers = {
            "week_gainers": _movers(df, "ret_1w", ascending=False),
            "week_losers": _movers(df, "ret_1w", ascending=True),
            "month_gainers": _movers(df, "ret_1m", ascending=False),
            "d200_gainers": _movers(df, "ret_200d", ascending=False),
        }

    # --- top relative setups (already ranked by buy_probability) ---
    setups = []
    for r in rows[:TOP_N]:
        setups.append({
            "rank": r.get("rank"), "tier": r.get("tier"), "symbol": r.get("symbol"),
            "company": r.get("company"), "close": r.get("close"),
            "buy_probability": r.get("buy_probability"), "ret_1w": r.get("ret_1w"),
            "ret_1m": r.get("ret_1m"), "ret_200d": r.get("ret_200d"),
            "final_decision": r.get("final_decision"),
        })

    # --- news ---
    tickers = sent.get("tickers", {}) or {}
    ranked_news = sorted(
        tickers.values(),
        key=lambda t: (-t.get("n_headlines", 0), -abs(t.get("sentiment_score", 0))),
    )[:5]
    news = {
        "tickers_with_news": sent.get("tickers_with_news", len(tickers)),
        "generated_at": sent.get("generated_at"),
        "top": [
            {"symbol": t.get("symbol"), "label": t.get("sentiment_label"),
             "score": t.get("sentiment_score"), "n": t.get("n_headlines")}
            for t in ranked_news
        ],
    }

    return {
        "engine_version": "morning_briefing_engine_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of_date": as_of,
        "market": market,
        "timeframes": timeframes,
        "movers": movers,
        "top_setups": setups,
        "news": news,
        "note": (
            f"Analysis of the latest end-of-day data ({as_of}) plus this morning's "
            "news. This is NOT a forecast of today's moves — the market opens 9:30 "
            "and there is no new price data before the open. The rule edge is "
            "unvalidated; 'top setups' are the relatively strongest, not sure things."
        ),
    }


def run_morning_briefing() -> dict:
    payload = build_briefing()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


if __name__ == "__main__":
    p = run_morning_briefing()
    m = p["market"]
    print(f"as_of {p['as_of_date']} | market {m.get('verdict')} ({m.get('confidence')})")
    for tf, d in p["timeframes"].items():
        print(f"  {tf:6} median={d.get('median_pct')}%  +ve={d.get('pct_positive')}%")
    print("  top setups:", ", ".join(s["symbol"] for s in p["top_setups"]))
