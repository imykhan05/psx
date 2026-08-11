"""
Daily Market Signal Engine (Phase 2 #2).

Combines the (F1.2-validated) rule-scoring output with the news sentiment signal
into a single daily market verdict: BULLISH / BEARISH / NEUTRAL, with a
confidence and three plain-English reasons.

Inputs (all read from disk, none fabricated):
  - reports/latest/full_market_scan.csv  (every scored stock: change_pct,
    final_decision, buy_probability, final_score, ...)
  - database/ai_learning/sentiment_cache.json  (per-ticker news sentiment)

Output:
  - database/ai_learning/daily_signal.json

HONESTY
  - Breadth is measured as advancers vs decliners from the actual scan
    (change_pct), not from any indicator we don't store. There is deliberately
    no "% above 20MA" reason because the report does not carry a moving-average
    column - inventing it would violate the no-fabrication rule.
  - Sentiment is weighted lightly: its predictive value is not yet validated
    (unlike the rule edge, which F1.2 measured). It tilts, it does not decide.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SCAN_FILE = Path("reports/latest/full_market_scan.csv")
TOP_BUYS_FILE = Path("reports/latest/top_buys.csv")
SENTIMENT_CACHE = Path("database/ai_learning/sentiment_cache.json")
OUTPUT_FILE = Path("database/ai_learning/daily_signal.json")

ENGINE_VERSION = "daily_signal_engine_v1"

ACTIONABLE = {"BUY", "STRONG BUY", "WATCH", "ACCUMULATE"}

BULLISH_CUTOFF = 0.56
BEARISH_CUTOFF = 0.44


def _load_scan() -> pd.DataFrame:
    path = SCAN_FILE if SCAN_FILE.exists() and SCAN_FILE.stat().st_size else TOP_BUYS_FILE
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    df = pd.read_csv(path, encoding="utf-8-sig")
    if "change_pct" in df.columns:
        df["change_pct"] = pd.to_numeric(df["change_pct"], errors="coerce")
    if "final_score" in df.columns:
        df["final_score"] = pd.to_numeric(df["final_score"], errors="coerce")
    return df


def _load_sentiment() -> dict:
    if not SENTIMENT_CACHE.exists() or SENTIMENT_CACHE.stat().st_size == 0:
        return {}
    try:
        return json.loads(SENTIMENT_CACHE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _resolve_date(df: pd.DataFrame) -> str:
    if not df.empty and "date" in df.columns:
        parsed = pd.to_datetime(df["date"].iloc[0], format="%d%b%Y", errors="coerce")
        if pd.isna(parsed):
            parsed = pd.to_datetime(df["date"].iloc[0], errors="coerce")
        if pd.notna(parsed):
            return parsed.strftime("%Y-%m-%d")
    return datetime.now().strftime("%Y-%m-%d")


def compute_breadth(df: pd.DataFrame) -> dict:
    if df.empty or "change_pct" not in df.columns:
        return {"total": 0, "advancers": 0, "decliners": 0, "flat": 0, "advance_ratio": 0.5}
    change = df["change_pct"].dropna()
    adv = int((change > 0).sum())
    dec = int((change < 0).sum())
    flat = int((change == 0).sum())
    directional = adv + dec
    return {
        "total": int(len(change)),
        "advancers": adv,
        "decliners": dec,
        "flat": flat,
        "advance_ratio": round(adv / directional, 4) if directional else 0.5,
    }


def compute_decisions(df: pd.DataFrame) -> dict:
    if df.empty or "final_decision" not in df.columns:
        return {"scored": 0, "actionable": 0, "actionable_ratio": 0.0, "distribution": {}}
    decisions = df["final_decision"].astype(str).str.upper().str.strip()
    actionable = int(decisions.isin(ACTIONABLE).sum())
    scored = int(len(decisions))
    return {
        "scored": scored,
        "actionable": actionable,
        "actionable_ratio": round(actionable / scored, 4) if scored else 0.0,
        "distribution": decisions.value_counts().to_dict(),
    }


def compute_sentiment(sentiment: dict) -> dict:
    tickers = sentiment.get("tickers", {}) if isinstance(sentiment, dict) else {}
    bull = [s for s, t in tickers.items() if t.get("sentiment_label") == "BULLISH"]
    bear = [s for s, t in tickers.items() if t.get("sentiment_label") == "BEARISH"]
    neut = [s for s, t in tickers.items() if t.get("sentiment_label") == "NEUTRAL"]
    total = len(tickers)
    net = round((len(bull) - len(bear)) / total, 4) if total else 0.0
    return {
        "bullish": len(bull),
        "bearish": len(bear),
        "neutral": len(neut),
        "bullish_tickers": bull,
        "bearish_tickers": bear,
        "net": net,
        "source": sentiment.get("source") if isinstance(sentiment, dict) else None,
    }


def _bullishness(breadth: dict, decisions: dict, sentiment: dict) -> float:
    """
    Composite in [0,1]. Breadth (advance ratio) is the primary driver; the
    rule engine's actionable ratio confirms upside when it fires (rare, but
    F1.2 showed it carries a real edge); sentiment is a light tilt.
    """
    score = breadth["advance_ratio"]
    score += 0.5 * decisions["actionable_ratio"]  # bonus when rules find buys
    # Light sentiment tilt only. Kept small (0.08) on purpose: sentiment's
    # predictive value is not yet validated, and a clearly directional breadth
    # day must not be flipped to a different verdict by news alone.
    score += 0.08 * sentiment["net"]
    return max(0.0, min(1.0, score))


def _verdict(bullishness: float) -> str:
    if bullishness >= BULLISH_CUTOFF:
        return "BULLISH"
    if bullishness <= BEARISH_CUTOFF:
        return "BEARISH"
    return "NEUTRAL"


def _confidence(bullishness: float) -> float:
    strength = abs(bullishness - 0.5) * 2  # 0..1
    return round(min(0.95, 0.5 + strength * 0.5), 2)


def _build_reasons(breadth: dict, decisions: dict, sentiment: dict, verdict: str) -> list[str]:
    reasons: list[str] = []

    # 1) Breadth
    total_dir = breadth["advancers"] + breadth["decliners"]
    if total_dir:
        adv_pct = breadth["advancers"] / total_dir * 100
        dec_pct = breadth["decliners"] / total_dir * 100
        if adv_pct >= dec_pct:
            reasons.append(
                f"{adv_pct:.0f}% of scanned stocks advanced today "
                f"({breadth['advancers']} up vs {breadth['decliners']} down) - positive breadth"
            )
        else:
            reasons.append(
                f"{dec_pct:.0f}% of scanned stocks declined today "
                f"({breadth['decliners']} down vs {breadth['advancers']} up) - weak breadth"
            )

    # 2) Rule decisions
    if decisions["scored"]:
        pct = decisions["actionable_ratio"] * 100
        if decisions["actionable"] > 0:
            reasons.append(
                f"{pct:.0f}% of scored stocks rated BUY or WATCH "
                f"({decisions['actionable']} of {decisions['scored']})"
            )
        else:
            reasons.append(
                f"0 of {decisions['scored']} scored stocks rated BUY or WATCH - "
                "the rules flag no opportunities today"
            )

    # 3) Sentiment
    if sentiment["bullish"] or sentiment["bearish"]:
        bits = []
        if sentiment["bullish"]:
            names = ", ".join(sentiment["bullish_tickers"][:3])
            bits.append(f"bullish on {names}")
        if sentiment["bearish"]:
            names = ", ".join(sentiment["bearish_tickers"][:3])
            bits.append(f"bearish on {names}")
        reasons.append("News sentiment " + "; ".join(bits))
    else:
        reasons.append("No directional news sentiment detected today")

    return reasons[:3]


def _top_opportunities(df: pd.DataFrame, sentiment: dict, limit: int = 5) -> list[str]:
    picks: list[str] = []

    if not df.empty and "final_decision" in df.columns and "final_score" in df.columns:
        decisions = df["final_decision"].astype(str).str.upper().str.strip()
        actionable = df[decisions.isin(ACTIONABLE)].sort_values("final_score", ascending=False)
        picks.extend(actionable["symbol"].astype(str).str.upper().tolist())

        if len(picks) < limit:
            ranked = df.sort_values("final_score", ascending=False)
            for sym in ranked["symbol"].astype(str).str.upper().tolist():
                if sym not in picks:
                    picks.append(sym)
                if len(picks) >= limit:
                    break

    # Surface bullish-sentiment names (dedup, keep order).
    for sym in sentiment.get("bullish_tickers", []):
        if sym.upper() not in picks:
            picks.insert(0, sym.upper())

    seen, ordered = set(), []
    for sym in picks:
        if sym not in seen:
            seen.add(sym)
            ordered.append(sym)
    return ordered[:limit]


def run_daily_signal_engine(output_file: Path = OUTPUT_FILE) -> dict:
    scan = _load_scan()
    sentiment_raw = _load_sentiment()

    breadth = compute_breadth(scan)
    decisions = compute_decisions(scan)
    sentiment = compute_sentiment(sentiment_raw)

    bullishness = _bullishness(breadth, decisions, sentiment)
    verdict = _verdict(bullishness)
    confidence = _confidence(bullishness)
    reasons = _build_reasons(breadth, decisions, sentiment, verdict)
    top_ops = _top_opportunities(scan, sentiment)

    payload = {
        "engine_version": ENGINE_VERSION,
        "date": _resolve_date(scan),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "verdict": verdict,
        "confidence": confidence,
        "bullishness": round(bullishness, 4),
        "reasons": reasons,
        "top_opportunities": top_ops,
        "sentiment_summary": {
            "bullish": sentiment["bullish"],
            "bearish": sentiment["bearish"],
            "neutral": sentiment["neutral"],
        },
        "breadth": breadth,
        "decisions": {k: v for k, v in decisions.items() if k != "distribution"},
        "inputs": {
            "scan_rows": int(len(scan)),
            "sentiment_source": sentiment.get("source"),
        },
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = run_daily_signal_engine()
    print(json.dumps(result, indent=2, ensure_ascii=False))
