"""Tests for the sector rotation engine (descriptive, honest 'where money flowed')."""

import pandas as pd

import app.engines.sector_rotation_engine_v1 as sr


def test_sector_rotation_ranks_and_labels(monkeypatch, tmp_path):
    df = pd.DataFrame([
        {"symbol": "A", "sector": "BANKS", "change_pct": 2, "ret_1w": 5, "ret_1m": 3,
         "ret_200d": 10, "rvol5": 1.5, "value_traded": 1000, "above_ma50": True, "as_of": "2026-08-11"},
        {"symbol": "B", "sector": "BANKS", "change_pct": 1, "ret_1w": 4, "ret_1m": 2,
         "ret_200d": 8, "rvol5": 1.2, "value_traded": 500, "above_ma50": True, "as_of": "2026-08-11"},
        {"symbol": "C", "sector": "OIL", "change_pct": -1, "ret_1w": -3, "ret_1m": -2,
         "ret_200d": -5, "rvol5": 0.8, "value_traded": 300, "above_ma50": False, "as_of": "2026-08-11"},
        {"symbol": "D", "sector": "OIL", "change_pct": -2, "ret_1w": -4, "ret_1m": -1,
         "ret_200d": -6, "rvol5": 0.7, "value_traded": 200, "above_ma50": False, "as_of": "2026-08-11"},
    ])
    monkeypatch.setattr(sr, "_merged_frame", lambda: df)
    monkeypatch.setattr(sr, "OUT_PATH", tmp_path / "sec.json")

    p = sr.build_sector_rotation()
    assert p["sector_count"] == 2
    # BANKS (higher week return) ranks first
    assert p["sectors"][0]["sector"] == "BANKS" and p["sectors"][0]["rank"] == 1
    assert p["sectors"][1]["sector"] == "OIL"
    # each sector carries top stocks and value share
    assert p["sectors"][0]["top_stocks"]
    assert p["sectors"][0]["value_share_pct"] is not None
    # honest note — descriptive, not a forecast
    assert "not a forecast" in p["note"].lower()
