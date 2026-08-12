"""
Highlights Engine v1 — "Today's Highlights" digest.

One place for the day's most notable triggers, so the user doesn't have to open
each screener. Pure aggregation of what the pipeline already computed
(screeners.json, sector_rotation.json, daily_signal.json, sentiment_cache.json).

Everything here is FACT (what happened today) — a watch-list, not a prediction.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCREENERS = PROJECT_ROOT / "reports" / "latest" / "screeners.json"
SECTORS = PROJECT_ROOT / "reports" / "latest" / "sector_rotation.json"
DAILY_SIGNAL = PROJECT_ROOT / "database" / "ai_learning" / "daily_signal.json"
SENTIMENT = PROJECT_ROOT / "database" / "ai_learning" / "sentiment_cache.json"
OUT_PATH = PROJECT_ROOT / "reports" / "latest" / "highlights.json"

CAP = 8  # symbols shown per highlight

# (screener key, icon, title) pulled straight from screeners.json
FROM_SCREENERS = [
    ("breakout_vol", "🚀", "Breakouts on volume"),
    ("accumulation_radar", "📈", "Accumulation (sustained volume)"),
    ("near_52w_high", "⭐", "Near 52-week highs"),
    ("upper_circuit", "🔒", "Upper-lock today"),
    ("near_breakout", "🌀", "Coiling near breakout"),
    ("volume_spike", "🔊", "Volume spikes"),
    ("most_active", "💰", "Most active"),
    ("top_gainers", "🟢", "Top gainers"),
]


def _read(path: Path) -> dict:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def build_highlights() -> dict:
    scr = (_read(SCREENERS).get("screeners") or {})
    sectors = _read(SECTORS)
    signal = _read(DAILY_SIGNAL)
    sent = _read(SENTIMENT)
    as_of = _read(SCREENERS).get("as_of_date") or signal.get("date")

    highlights = []
    for key, icon, title in FROM_SCREENERS:
        block = scr.get(key)
        if not block or not block.get("rows"):
            continue
        syms = [r.get("symbol") for r in block["rows"][:CAP] if r.get("symbol")]
        if syms:
            highlights.append({
                "type": key, "icon": icon, "title": title,
                "count": block.get("count", len(syms)), "symbols": syms,
            })

    # accelerating sectors (with rising volume = strongest inflow first)
    accel = [s for s in sectors.get("sectors", []) if s.get("trend") == "accelerating"]
    accel.sort(key=lambda s: (s.get("ret_1w") is None, -(s.get("ret_1w") or -1e9)))
    if accel:
        highlights.append({
            "type": "sectors", "icon": "🔥", "title": "Accelerating sectors",
            "count": len(accel),
            "sectors": [
                {"sector": s["sector"], "ret_1w": s.get("ret_1w"),
                 "top": [t["symbol"] for t in (s.get("top_stocks") or [])[:3]]}
                for s in accel[:6]
            ],
        })

    # directional news
    tickers = sent.get("tickers", {}) or {}
    news = [t for t in tickers.values()
            if str(t.get("sentiment_label", "")).upper() in ("BULLISH", "BEARISH")]
    news.sort(key=lambda t: (-t.get("n_headlines", 0), -abs(t.get("sentiment_score", 0))))
    if news:
        highlights.append({
            "type": "news", "icon": "📰", "title": "News with a lean",
            "count": len(news),
            "news": [{"symbol": t.get("symbol"), "label": t.get("sentiment_label"),
                      "n": t.get("n_headlines")} for t in news[:6]],
        })

    return {
        "engine_version": "highlights_engine_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of_date": as_of,
        "market": {"verdict": signal.get("verdict"),
                   "reason": (signal.get("reasons") or [None])[0]},
        "highlights": highlights,
        "note": ("Everything that stood out today, in one place — breakouts, "
                 "accumulation, new highs, hot sectors, news. These are facts "
                 "(what happened), a watch-list — NOT buy signals or predictions."),
    }


def run_highlights_engine() -> dict:
    payload = build_highlights()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


if __name__ == "__main__":
    p = run_highlights_engine()
    print(f"as_of {p['as_of_date']} | market {p['market'].get('verdict')} | "
          f"{len(p['highlights'])} highlight groups")
    for h in p["highlights"]:
        if "symbols" in h:
            body = ", ".join(h["symbols"])
        elif "sectors" in h:
            body = ", ".join(s["sector"] for s in h["sectors"])
        else:
            body = ", ".join(n["symbol"] for n in h.get("news", []))
        print(f"  {h['title']} ({h['count']}): {body}")
