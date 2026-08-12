"""Smoke test the walk-forward model engine against a synthetic temp SQLite."""

import sqlite3
from datetime import date, timedelta

import app.engines.model_engine_v1 as me


def test_model_picks_structure(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE daily_prices (date_parsed TEXT, symbol TEXT, high REAL, "
                "low REAL, close REAL, volume REAL)")
    d0 = date(2024, 1, 1)
    rows = []
    for i in range(400):
        for j, sym in enumerate(["AAA", "BBB", "CCC"]):
            c = 100 + i * 0.1 + j * 5 + (3 if (i % 5 == j) else 0)
            rows.append(((d0 + timedelta(days=i)).isoformat(), sym, c + 1, c - 1, c, 1000 + i + j * 50))
    con.executemany("INSERT INTO daily_prices VALUES (?,?,?,?,?,?)", rows)
    con.commit()
    con.close()
    monkeypatch.setattr(me, "DB_PATH", db)
    monkeypatch.setattr(me, "SCAN_CSV", tmp_path / "no_scan.csv")
    monkeypatch.setattr(me, "OUT_PATH", tmp_path / "out.json")

    p = me.build_model_picks(top_n=3)
    assert p["engine_version"] == "model_engine_v1"
    assert p["universe"] >= 2
    assert len(p["top"]) >= 1
    assert set(me.FEATURES) == set(p["coefficients"].keys())
    # the honest, corrected track record + caveats travel with the output
    assert "NONE" in p["validation"]["tradeable_edge"]
    assert len(p["caveats"]) >= 4
    assert "MIRAGE" in p["caveats"][0]
    assert "not a buy list" in p["note"].lower()
    assert p["top"][0]["model_score"] is not None
