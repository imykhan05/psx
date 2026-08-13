"""Tests for the local NLP assistant (no external AI — answers from JSON)."""

import json

import app.engines.local_assistant_v1 as la


def _seed(tmp_path, monkeypatch):
    r = tmp_path / "reports"
    ai = tmp_path / "ai"
    r.mkdir()
    ai.mkdir()
    (r / "all_stocks.json").write_text(json.dumps({"rows": [
        {"symbol": "HBL", "close": 300, "change_pct": 1.0, "ret_1w": 2, "ret_1m": 3,
         "ret_200d": 10, "final_decision": "AVOID", "buy_probability": 40, "rank": 5, "tier": "Top 10%"},
    ]}), encoding="utf-8")
    (r / "screeners.json").write_text(json.dumps({"screeners": {
        "top_gainers": {"count": 1, "rows": [{"symbol": "AAA", "change_pct": 5}], "note": "gainers"},
        "value_low_pe": {"count": 1, "rows": [{"symbol": "VVV", "pe_ttm": 3.0, "eps": 5}], "note": "value"},
    }}), encoding="utf-8")
    (ai / "daily_signal.json").write_text(json.dumps(
        {"date": "2026-08-12", "verdict": "NEUTRAL", "confidence": 0.54, "reasons": ["balanced breadth"]}),
        encoding="utf-8")
    monkeypatch.setattr(la, "R", r)
    monkeypatch.setattr(la, "AI", ai)


def test_market_signal(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    assert "NEUTRAL" in la.answer("market kaisa hai?")


def test_stock_lookup(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    out = la.answer("HBL ka kya haal hai")
    assert "HBL" in out and "AVOID" in out


def test_screener_intents(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    assert "AAA" in la.answer("top gainers dikhao")
    assert "VVV" in la.answer("value stocks batao")


def test_help_and_fallback(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    assert "pooch" in la.answer("help").lower() or "sakte" in la.answer("help")
    # unknown question -> fallback that offers help (never invents an answer)
    assert "try" in la.answer("qwerty zxcvb nonsense").lower()
