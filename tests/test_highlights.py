"""Tests for the Today's Highlights digest (pure aggregation, honest watch-list)."""

import json

import app.engines.highlights_engine_v1 as hl


def test_highlights_aggregates_sources(tmp_path, monkeypatch):
    (tmp_path / "scr.json").write_text(json.dumps({"as_of_date": "2026-08-11", "screeners": {
        "breakout_vol": {"count": 2, "rows": [{"symbol": "AAA"}, {"symbol": "BBB"}]},
        "top_gainers": {"count": 1, "rows": [{"symbol": "CCC"}]},
    }}), encoding="utf-8")
    (tmp_path / "sec.json").write_text(json.dumps({"sectors": [
        {"sector": "BANKS", "trend": "accelerating", "ret_1w": 5, "top_stocks": [{"symbol": "AAA"}]},
        {"sector": "OIL", "trend": "fading", "ret_1w": -2},
    ]}), encoding="utf-8")
    (tmp_path / "sig.json").write_text(json.dumps({"verdict": "BEARISH", "reasons": ["weak breadth"]}), encoding="utf-8")
    (tmp_path / "sent.json").write_text(json.dumps({"tickers": {"AAA": {
        "symbol": "AAA", "sentiment_label": "BULLISH", "sentiment_score": 0.5, "n_headlines": 2}}}), encoding="utf-8")
    for attr, name in [("SCREENERS", "scr.json"), ("SECTORS", "sec.json"),
                       ("DAILY_SIGNAL", "sig.json"), ("SENTIMENT", "sent.json"), ("OUT_PATH", "out.json")]:
        monkeypatch.setattr(hl, attr, tmp_path / name)

    p = hl.build_highlights()
    titles = [h["title"] for h in p["highlights"]]
    assert "Breakouts on volume" in titles
    assert "Accelerating sectors" in titles   # only BANKS (accelerating), not OIL
    assert "News with a lean" in titles
    assert p["market"]["verdict"] == "BEARISH"

    bo = next(h for h in p["highlights"] if h["title"] == "Breakouts on volume")
    assert bo["symbols"] == ["AAA", "BBB"]
    accel = next(h for h in p["highlights"] if h["title"] == "Accelerating sectors")
    assert [s["sector"] for s in accel["sectors"]] == ["BANKS"]
    # honest: a watch-list, not buy signals
    assert "not" in p["note"].lower()
