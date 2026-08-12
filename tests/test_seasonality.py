"""Test the seasonality engine against a synthetic temp SQLite."""

import sqlite3
from datetime import date, timedelta

import app.engines.seasonality_engine_v1 as se


def test_seasonality_structure(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE daily_prices (date_parsed TEXT, symbol TEXT, close REAL)")
    d0 = date(2022, 1, 3)  # a Monday
    rows = []
    c = 100.0
    for i in range(600):
        day = d0 + timedelta(days=i)
        if day.weekday() < 5:  # trading days
            c *= 1.005 if day.weekday() == 4 else 1.0  # Fridays drift up
            rows.append((day.isoformat(), "AAA", round(c, 2)))
    con.executemany("INSERT INTO daily_prices VALUES (?,?,?)", rows)
    con.commit()
    con.close()
    monkeypatch.setattr(se, "DB_PATH", db)
    monkeypatch.setattr(se, "OUT_PATH", tmp_path / "out.json")

    p = se.build_seasonality()
    assert len(p["weekday"]) == 5
    assert 1 <= len(p["month"]) <= 12
    assert p["best_weekday"] and p["worst_weekday"]
    # Fridays were engineered to drift up -> best weekday
    assert p["best_weekday"]["day"] == "Friday"
    assert "not a" in p["note"].lower()
