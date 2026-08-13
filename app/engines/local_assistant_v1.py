"""
Local NLP assistant (v1) — answers questions about the PSX data with NO external
AI (no Gemini, no Claude, no API cost).

It is honest by construction: it understands a question via keyword/intent
matching, RETRIEVES the relevant facts from the pipeline's own JSON outputs, and
answers from them. It never invents numbers and never hallucinates — if it doesn't
have the answer it says so and lists what it can do. It is always current because
it reads the latest JSON each time (it "knows" today's data by reading it, not by
training a language model on it).

Understands English and Roman-Urdu phrasings. Unanswered questions are logged to
logs/assistant_unanswered.log so the intent patterns can be grown over time.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
R = PROJECT_ROOT / "reports" / "latest"
AI = PROJECT_ROOT / "database" / "ai_learning"
UNANSWERED_LOG = PROJECT_ROOT / "logs" / "assistant_unanswered.log"


def _load(path: Path) -> dict:
    try:
        if path.exists() and path.stat().st_size:
            return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _fnum(v, d=2):
    try:
        return f"{float(v):.{d}f}"
    except (TypeError, ValueError):
        return "—"


def _all_stocks() -> dict:
    return _load(R / "all_stocks.json")


def _symbol_index() -> dict:
    idx = {}
    for r in _all_stocks().get("rows", []):
        s = str(r.get("symbol", "")).upper()
        if s:
            idx[s] = r
    return idx


def _has(q: str, *words) -> bool:
    return any(w in q for w in words)


def _rows_line(rows, fields, n=8):
    out = []
    for r in rows[:n]:
        parts = []
        for label, key, dec in fields:
            v = r.get(key)
            parts.append(f"{label} {_fnum(v, dec) if isinstance(v, (int, float)) else (v if v is not None else '—')}")
        out.append("  • " + (str(r.get("symbol", "")) + ": " if r.get("symbol") else "") + ", ".join(parts))
    return "\n".join(out)


# ----------------------------- intent answers -----------------------------
def _help() -> str:
    return (
        "Main aap ke PSX data se seedha jawab deta hoon (bina kisi bahar ke AI ke). "
        "Aap yeh pooch sakte hain:\n"
        "  • Market kaisa hai? / aaj ka signal\n"
        "  • <SYMBOL> ka kya haal hai? (jaise: HBL, MCB)\n"
        "  • Top gainers / losers / most active\n"
        "  • Breakouts / accumulation / 52-week high / value (low P/E) stocks\n"
        "  • Kaunse sectors chal rahe hain?\n"
        "  • Model picks / kya khareedun? (honest caveat ke saath)\n"
        "  • Seasonality (best month/day) / aaj ki highlights"
    )


def _signal() -> str:
    d = _load(AI / "daily_signal.json")
    if not d:
        return "Abhi market signal available nahi. Scan chalne ke baad aata hai."
    reasons = "\n".join("  - " + str(x) for x in (d.get("reasons") or [])[:3])
    return (f"Market signal ({d.get('date','—')}): {d.get('verdict','—')} "
            f"(confidence {_fnum((d.get('confidence') or 0)*100,0)}%).\n{reasons}")


def _stock(sym: str) -> str:
    r = _symbol_index().get(sym)
    lines = [f"{sym}:"]
    if r:
        lines.append(f"  Close {_fnum(r.get('close'))}, aaj {_fnum(r.get('change_pct'))}% "
                     f"(1w {_fnum(r.get('ret_1w'))}%, 1m {_fnum(r.get('ret_1m'))}%, "
                     f"200d {_fnum(r.get('ret_200d'))}%)")
        lines.append(f"  Rule decision: {r.get('final_decision','—')} · buy_prob {_fnum(r.get('buy_probability'),1)} "
                     f"· rank #{r.get('rank','—')} ({r.get('tier','—')})")
    try:
        from app.engines.fundamentals_store import get_fundamentals
        f = get_fundamentals(sym)
        if f:
            lines.append(f"  Fundamentals: P/E {_fnum(f.get('pe_ttm'))}, EPS {_fnum(f.get('eps'))}, "
                         f"Free Float {_fnum(f.get('free_float_pct'),0)}%, 52w {_fnum(f.get('wk52_low'))}–{_fnum(f.get('wk52_high'))}")
    except Exception:
        pass
    if len(lines) == 1:
        return f"{sym} aaj ke scan mein nahi mila. Symbol theek hai? (jaise HBL, MCB, OGDC)"
    lines.append("  (Rule decision momentum-based hai — sirf info, buy signal nahi.)")
    return "\n".join(lines)


def _screener(name: str, title: str, fields, n=8) -> str:
    scr = (_load(R / "screeners.json").get("screeners") or {}).get(name)
    if not scr or not scr.get("rows"):
        return f"{title}: aaj koi stock is filter mein nahi."
    return f"{title} ({scr.get('count', len(scr['rows']))}):\n" + _rows_line(scr["rows"], fields, n) + \
           f"\n({scr.get('note','')[:120]})"


def _sectors() -> str:
    d = _load(R / "sector_rotation.json")
    rows = d.get("sectors", [])[:6]
    if not rows:
        return "Sector data abhi available nahi."
    body = "\n".join(f"  • {r['sector']}: 1w {_fnum(r.get('ret_1w'))}%, {r.get('trend','')}, "
                     f"top {', '.join(t['symbol'] for t in (r.get('top_stocks') or [])[:2])}" for r in rows)
    return "Sectors (is hafte ke leaders):\n" + body


def _model() -> str:
    d = _load(R / "model_picks.json")
    rows = d.get("top", [])[:8]
    if not rows:
        return "Model output abhi available nahi."
    body = "\n".join(f"  • {r['symbol']} (score {_fnum(r.get('model_score'))}, {r.get('final_decision','—')})" for r in rows)
    return ("Model ranking (top — CONTRARIAN research, buy list NAHI):\n" + body +
            "\n⚠️ Iska tradeable edge NONE hai — liquid stocks par market se peechay. "
            "Yeh sirf research ka starting point hai, guaranteed profit nahi.")


def _seasonality() -> str:
    d = _load(R / "seasonality.json")
    if not d:
        return "Seasonality data abhi available nahi."
    bw, ww = d.get("best_weekday", {}), d.get("worst_weekday", {})
    bm, wm = d.get("best_month", {}), d.get("worst_month", {})
    return (f"Seasonality (historical averages, guarantee nahi):\n"
            f"  • Best din: {bw.get('day','—')} ({_fnum(bw.get('avg_return'),3)}%), "
            f"worst: {ww.get('day','—')}\n"
            f"  • Best mahina: {bm.get('month','—')} ({_fnum(bm.get('avg_return'))}%), "
            f"worst: {wm.get('month','—')} ({_fnum(wm.get('avg_return'))}%)")


def _highlights() -> str:
    d = _load(R / "highlights.json")
    hs = d.get("highlights", [])
    if not hs:
        return "Aaj ki highlights abhi available nahi."
    out = ["Aaj ki highlights:"]
    for h in hs[:6]:
        if h.get("symbols"):
            out.append(f"  {h.get('title')}: {', '.join(h['symbols'][:6])}")
        elif h.get("sectors"):
            out.append(f"  {h.get('title')}: {', '.join(s['sector'] for s in h['sectors'][:4])}")
    return "\n".join(out)


def _log_unanswered(q: str):
    try:
        UNANSWERED_LOG.parent.mkdir(parents=True, exist_ok=True)
        with UNANSWERED_LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}\t{q}\n")
    except OSError:
        pass


# ----------------------------- main router -----------------------------
def answer(question: str) -> str:
    q = (question or "").lower().strip()
    if not q:
        return _help()

    # explicit symbol mention wins (e.g. "HBL ka kya haal")
    tokens = re.findall(r"[A-Za-z0-9]+", question.upper())
    idx = _symbol_index()
    for t in tokens:
        if t in idx and len(t) >= 2 and t not in ("PE", "EPS", "MA", "AI", "PSX"):
            return _stock(t)

    if _has(q, "help", "what can you", "kya kar", "commands", "madad", "options"):
        return _help()
    if _has(q, "buy", "khareed", "kharid", "kya lun", "kya lo", "recommend", "suggest", "best stock", "model pick", "model"):
        return _model()
    if _has(q, "market", "signal", "bullish", "bearish", "mood", "overall", "index", "kaisa hai", "kaisa hy"):
        return _signal()
    if _has(q, "gainer", "top up", "sabse zyada up", "chaṛh", "charh"):
        return _screener("top_gainers", "Top gainers", [("chg%", "change_pct", 2)])
    if _has(q, "loser", "top down", "gir ", "fall", "sabse zyada down"):
        return _screener("top_losers", "Top losers", [("chg%", "change_pct", 2)])
    if _has(q, "most active", "active", "turnover", "value traded"):
        return _screener("most_active", "Most active", [("chg%", "change_pct", 2)])
    if _has(q, "breakout", "break out", "new high"):
        return _screener("breakout_vol", "Breakouts on volume", [("relvol", "rvol5", 2), ("chg%", "change_pct", 2)])
    if _has(q, "accumulat", "institution", "big buyer", "crocodile"):
        return _screener("accumulation_radar", "Accumulation (sustained volume)", [("relvol", "rvol5", 2)])
    if _has(q, "52", "year high", "yearly high"):
        return _screener("near_52w_high", "Near 52-week high", [("%to52wH", "pct_to_52w_high", 2)])
    if _has(q, "value", "cheap", "sasta", "low pe", "low p/e", "p/e", "pe ratio", "fundamental"):
        return _screener("value_low_pe", "Value — low P/E (real fundamentals)", [("PE", "pe_ttm", 2), ("EPS", "eps", 2)])
    if _has(q, "upper", "circuit", "lock", "cap "):
        return _screener("upper_circuit", "Upper-lock (closed at high)", [("chg%", "change_pct", 2)])
    if _has(q, "coil", "consolidat", "tight range"):
        return _screener("coil", "Coiling (tight consolidation)", [("20dRange", "range20", 2)])
    if _has(q, "pullback", "dip"):
        return _screener("pullback_uptrend", "Pullback to MA50", [("chg%", "change_pct", 2)])
    if _has(q, "sector", "rotation"):
        return _sectors()
    if _has(q, "season", "month", "mahina", "which day", "din "):
        return _seasonality()
    if _has(q, "highlight", "today", "aaj kya", "what happened"):
        return _highlights()

    _log_unanswered(question)
    return ("Main is sawaal ka data nahi dhoondh paaya. Yeh try karein:\n" + _help())
