"""
Unit tests for the daily market signal engine (Phase 2 #2).

Pure-function tests (no files, no network): verdict thresholds, breadth
arithmetic, and the composite bullishness weighting.
"""

import pandas as pd

from app.engines.daily_signal_engine import (
    compute_breadth,
    compute_decisions,
    compute_sentiment,
    _bullishness,
    _verdict,
    _confidence,
)


def test_breadth_counts():
    df = pd.DataFrame({"change_pct": [1.0, 2.0, -1.0, 0.0, -3.0]})
    b = compute_breadth(df)
    assert b["advancers"] == 2
    assert b["decliners"] == 2
    assert b["flat"] == 1
    assert b["advance_ratio"] == 0.5


def test_decisions_actionable_ratio():
    df = pd.DataFrame({"final_decision": ["BUY", "AVOID", "WATCH", "AVOID"]})
    d = compute_decisions(df)
    assert d["actionable"] == 2
    assert d["actionable_ratio"] == 0.5


def test_verdict_thresholds():
    assert _verdict(0.60) == "BULLISH"
    assert _verdict(0.30) == "BEARISH"
    assert _verdict(0.50) == "NEUTRAL"


def test_bullish_day():
    breadth = {"advance_ratio": 0.70, "advancers": 70, "decliners": 30}
    decisions = {"actionable_ratio": 0.05}
    sentiment = {"net": 0.2}
    b = _bullishness(breadth, decisions, sentiment)
    assert _verdict(b) == "BULLISH"


def test_bearish_day_sentiment_does_not_flip():
    # Strong down breadth with a little positive news must stay BEARISH:
    # sentiment tilts, it does not decide.
    breadth = {"advance_ratio": 0.30, "advancers": 30, "decliners": 70}
    decisions = {"actionable_ratio": 0.0}
    sentiment = {"net": 1.0}  # maximally positive news
    b = _bullishness(breadth, decisions, sentiment)
    assert _verdict(b) == "BEARISH"


def test_confidence_scales_with_conviction():
    assert _confidence(0.50) == 0.5  # coin flip -> min confidence
    assert _confidence(0.90) > _confidence(0.60)  # stronger -> higher
    assert _confidence(1.0) <= 0.95  # capped


def test_sentiment_summary_shape():
    raw = {
        "tickers": {
            "MCB": {"sentiment_label": "BULLISH"},
            "OGDC": {"sentiment_label": "NEUTRAL"},
            "HBL": {"sentiment_label": "BEARISH"},
        }
    }
    s = compute_sentiment(raw)
    assert s["bullish"] == 1 and s["bearish"] == 1 and s["neutral"] == 1
    assert s["net"] == 0.0
