"""
Tests for the morning briefing engine — builds from the pipeline's JSON outputs
(no SQLite / no model). Locks in the structure and the honest "not a forecast" note.
"""

import json

import app.engines.morning_briefing_engine_v1 as mb


def _seed(tmp_path, monkeypatch):
    allx = {
        "as_of_date": "2026-08-11",
        "rows": [
            {"symbol": "AAA", "company": "A Co", "close": 10, "change_pct": 2.0,
             "ret_1w": 5.0, "ret_1m": 10.0, "ret_200d": 50.0, "buy_probability": 40,
             "final_decision": "AVOID", "above_ma50": True, "above_ma200": True,
             "rank": 1, "tier": "Top 10%"},
            {"symbol": "BBB", "company": "B Co", "close": 5, "change_pct": -1.0,
             "ret_1w": -2.0, "ret_1m": -5.0, "ret_200d": -10.0, "buy_probability": 20,
             "final_decision": "AVOID", "above_ma50": False, "above_ma200": False,
             "rank": 2, "tier": "Bottom 50%"},
        ],
    }
    (tmp_path / "all.json").write_text(json.dumps(allx), encoding="utf-8")
    (tmp_path / "sig.json").write_text(json.dumps(
        {"verdict": "BEARISH", "confidence": 0.66, "date": "2026-08-11",
         "reasons": ["weak breadth"]}), encoding="utf-8")
    (tmp_path / "sent.json").write_text(json.dumps(
        {"tickers_with_news": 1, "tickers": {"AAA": {"symbol": "AAA",
         "sentiment_label": "BULLISH", "sentiment_score": 0.5, "n_headlines": 2}}}),
        encoding="utf-8")
    monkeypatch.setattr(mb, "ALL_STOCKS", tmp_path / "all.json")
    monkeypatch.setattr(mb, "DAILY_SIGNAL", tmp_path / "sig.json")
    monkeypatch.setattr(mb, "SENTIMENT", tmp_path / "sent.json")
    monkeypatch.setattr(mb, "OUT_PATH", tmp_path / "out.json")


def test_briefing_structure_and_honesty(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    p = mb.build_briefing()
    assert p["market"]["verdict"] == "BEARISH"
    # four timeframes present with real medians
    for tf in ("day", "week", "month", "d200"):
        assert p["timeframes"][tf]["median_pct"] is not None
    # top setups keep the buy_probability ranking order
    assert [s["symbol"] for s in p["top_setups"]] == ["AAA", "BBB"]
    # news + honest note
    assert p["news"]["tickers_with_news"] == 1
    assert "NOT a forecast" in p["note"]


def test_movers_computed(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)
    p = mb.build_briefing()
    assert p["movers"]["week_gainers"][0]["symbol"] == "AAA"
    assert p["movers"]["week_losers"][0]["symbol"] == "BBB"
