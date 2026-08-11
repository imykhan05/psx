"""
Tests for the screener engine (click-and-go stock lists).

Uses a tiny in-memory SQLite `daily_prices` table and a small scan CSV, so no
real DB or network is touched. Locks in: the technical screeners compute from
OHLC (upper-lock, MA, volume spike), scored screeners appear only when the scan
provides them, and every screener carries an honest `note`.
"""

import sqlite3
from datetime import date, timedelta

import pandas as pd
import pytest

import app.engines.screener_engine_v1 as se


@pytest.fixture
def wired(tmp_path, monkeypatch):
    # Build ~260 trading days for 2 symbols so MA200/52w have enough history.
    db = tmp_path / "t.db"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE daily_prices (date_parsed TEXT, symbol TEXT, company TEXT, "
        "open REAL, high REAL, low REAL, close REAL, volume REAL, prev_close REAL, change_pct REAL)"
    )
    rows = []
    d0 = date(2025, 1, 1)
    for i in range(260):
        d = (d0 + timedelta(days=i)).isoformat()
        # UPUP: steady uptrend, last bar an upper-lock (+7.5%, close==high)
        rows.append((d, "UPUP", "Up Co", 100, 100, 100, 100.0 + i, 1000, 100.0 + i, 0.5))
        # DOWN: flat then down today
        rows.append((d, "DOWN", "Down Co", 50, 50, 50, 50.0, 1000, 50.0, 0.0))
    # overwrite the final UPUP bar to be an upper-lock with a volume spike
    con.executemany(
        "INSERT INTO daily_prices VALUES (?,?,?,?,?,?,?,?,?,?)", rows
    )
    last_day = (d0 + timedelta(days=259)).isoformat()
    con.execute(
        "UPDATE daily_prices SET high=?, low=?, close=?, volume=?, change_pct=? "
        "WHERE symbol='UPUP' AND date_parsed=?",
        (400.0, 372.0, 400.0, 50000, 7.6, last_day),
    )
    con.commit()
    con.close()

    scan = tmp_path / "scan.csv"
    pd.DataFrame(
        [
            {"symbol": "UPUP", "company": "Up Co", "sector": "TECH",
             "final_decision": "BUY", "buy_probability": 70, "accumulation_score": 80,
             "smart_money_score": 75, "value_traded": 1e7, "stop_loss": 380,
             "target_1": 430, "target_2": 460},
            {"symbol": "DOWN", "company": "Down Co", "sector": "OIL",
             "final_decision": "AVOID", "buy_probability": 20, "accumulation_score": 10,
             "smart_money_score": 15, "value_traded": 1e5, "stop_loss": 47,
             "target_1": 55, "target_2": 60},
        ]
    ).to_csv(scan, index=False)

    monkeypatch.setattr(se, "DB_PATH", db)
    monkeypatch.setattr(se, "SCAN_CSV", scan)
    monkeypatch.setattr(se, "OUT_PATH", tmp_path / "screeners.json")
    return se.build_screeners()


def test_structure_and_notes(wired):
    assert wired["engine_version"] == "screener_engine_v1"
    assert wired["universe"] == 2
    assert wired["screeners"], "expected some screeners"
    for name, s in wired["screeners"].items():
        assert s["note"], f"{name} must carry an honest note"
        assert "rows" in s and "count" in s


def test_upper_lock_catches_the_locked_bar(wired):
    rows = wired["screeners"]["upper_circuit"]["rows"]
    assert any(r["symbol"] == "UPUP" for r in rows)


def test_ma_screeners_use_real_trend(wired):
    # UPUP is a clean uptrend -> above both MAs; DOWN is flat -> not above.
    above200 = [r["symbol"] for r in wired["screeners"]["above_ma200"]["rows"]]
    assert "UPUP" in above200
    assert "DOWN" not in above200


def test_scored_screeners_present_when_scan_has_them(wired):
    picks = [r["symbol"] for r in wired["screeners"]["top_picks"]["rows"]]
    assert picks == ["UPUP"]  # only the BUY row
    # accumulation note must flag it as a heuristic, not real holdings
    assert "NOT verified" in wired["screeners"]["accumulation"]["note"]


def test_top_picks_note_states_edge_unvalidated(wired):
    assert "NOT yet validated" in wired["screeners"]["top_picks"]["note"]


def test_all_stocks_ranked_and_honest(wired):
    a = se.build_all_stocks()
    assert a["count"] == 2
    # ranked by buy_probability desc: UPUP(70) before DOWN(20)
    assert [r["symbol"] for r in a["rows"]] == ["UPUP", "DOWN"]
    assert a["rows"][0]["rank"] == 1 and a["rows"][0]["tier"].startswith("Top")
    # multi-timeframe returns are present and the note refuses to claim "buy"
    assert "ret_1m" in a["rows"][0] and "ret_200d" in a["rows"][0]
    assert "NOT a validated buy" in a["note"]
