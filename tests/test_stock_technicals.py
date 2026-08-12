"""Test the per-stock technical panel against a synthetic temp SQLite."""

import sqlite3
from datetime import date, timedelta

import app.engines.stock_technicals as st


def test_technicals_from_temp_db(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE daily_prices (date_parsed TEXT, symbol TEXT, open REAL, "
                "high REAL, low REAL, close REAL, volume REAL)")
    d0 = date(2025, 1, 1)
    rows = []
    for i in range(300):
        c = 100 + i  # steady uptrend
        rows.append(((d0 + timedelta(days=i)).isoformat(), "UP", c, c + 1, c - 1, c, 1000))
    con.executemany("INSERT INTO daily_prices VALUES (?,?,?,?,?,?,?)", rows)
    con.commit()
    con.close()
    monkeypatch.setattr(st, "DB_PATH", db)

    t = st.compute_technicals("UP")
    assert t["history_days"] == 300
    assert t["ret_1y"] is not None and t["ret_1y"] > 0     # uptrend
    assert t["ma50"] is not None and t["ma200"] is not None
    assert t["streak_days"] > 0                             # consecutive up days
    assert t["pct_from_52w_high"] is not None

    assert st.compute_technicals("NOPE") == {}              # unknown symbol -> empty
