"""
Provenance gate tests (ROADMAP.md F0.1).

These lock in the guarantee that no fabricated or un-sourced fundamental
number can produce a long-term verdict, fair value, or confidence. If any of
these fail, the system is at risk of emitting fabricated investment
recommendations — the project's most severe class of defect.
"""

import pandas as pd
import pytest

from app.engines.long_term.fundamental_loader import (
    PROVENANCE_COLUMN,
    load_fundamentals,
    merge_fundamentals,
    fundamentals_summary,
)
from app.engines.long_term.long_term_engine import LongTermEngine


# A fully-populated, attractive-looking fundamentals row. The only thing that
# should decide whether it produces a verdict is its provenance label.
STRONG_LOOKING_FUNDAMENTALS = {
    "eps": 52.6,
    "book_value": 455.0,
    "roe": 21.4,
    "roa": 9.3,
    "debt_equity": 0.48,
    "current_ratio": 1.72,
    "net_margin": 17.3,
    "revenue_growth": 15.1,
    "profit_growth": 18.7,
    "eps_growth": 16.5,
    "dividend_yield": 4.2,
    "dividend_years": 8,
    "payout_ratio": 34,
    "pe": 9.5,
    "pb": 1.82,
    "fair_value": 980.0,
    "margin_of_safety": 53.0,
    "listing_years": 30,
    "is_sector_leader": 1,
    "stable_earnings": 1,
    "low_debt": 1,
    "consistent_dividend": 1,
}


def _row(provenance, close=459.0):
    data = {"symbol": "TEST", "close": close, "volume": 1_500_000}
    data.update(STRONG_LOOKING_FUNDAMENTALS)
    if provenance is not None:
        data[PROVENANCE_COLUMN] = provenance
    return pd.DataFrame([data])


@pytest.mark.parametrize("provenance", ["SEED", "ABSENT", "", "unknown", None])
def test_non_real_provenance_produces_no_verdict(provenance):
    """Anything that is not REAL must yield a non-actionable, zeroed result."""
    engine = LongTermEngine()
    result = engine.apply(_row(provenance))

    assert len(result) == 1
    row = result.iloc[0]

    assert row["long_term_verdict"] == "NO FUNDAMENTAL DATA"
    assert float(row["long_term_confidence"]) == 0.0
    assert float(row["fair_value"]) == 0.0
    assert float(row["investment_amount"]) == 0.0
    assert int(row["long_term_quantity"]) == 0
    # The fabricated fair value (980) must never surface as upside.
    assert float(row["upside_pct"]) == 0.0


def test_real_provenance_still_produces_a_verdict():
    """A REAL row with strong numbers must still be scored (gate is not a mute)."""
    engine = LongTermEngine()
    result = engine.apply(_row("REAL"))

    row = result.iloc[0]
    assert row["long_term_verdict"] != "NO FUNDAMENTAL DATA"
    # Strong undervalued fundamentals should produce a positive fair value.
    assert float(row["fair_value"]) > 0.0
    assert float(row["long_term_confidence"]) > 0.0


def test_seed_verdict_is_dropped_by_report_filter():
    """
    The reporting filter keeps only rows with confidence>0 OR fair_value>0.
    A gated SEED row must therefore not survive into the report.
    """
    from app.engines.reporting_engine_v3 import filter_meaningful_long_term_rows

    engine = LongTermEngine()
    gated = engine.apply(_row("SEED"))
    reportable = filter_meaningful_long_term_rows(gated)

    assert reportable.empty


def test_missing_fundamentals_file_does_not_raise(tmp_path, monkeypatch):
    """Loader must treat an absent file as 'no fundamentals', not an error."""
    import app.engines.long_term.fundamental_loader as loader

    missing = tmp_path / "does_not_exist.csv"
    monkeypatch.setattr(loader, "FUNDAMENTALS_PATH", missing)

    df = load_fundamentals(missing)
    assert df.empty

    summary = fundamentals_summary()
    assert summary["fundamental_records"] == 0
    assert summary["tradeable"] is False


def test_merge_labels_unmatched_symbols_absent():
    """Symbols with no fundamentals row must be labelled ABSENT after merge."""
    prices = pd.DataFrame(
        [
            {"symbol": "AAA", "close": 10.0},
            {"symbol": "BBB", "close": 20.0},
        ]
    )
    merged = merge_fundamentals(prices)

    assert PROVENANCE_COLUMN in merged.columns
    assert set(merged[PROVENANCE_COLUMN].unique()) <= {"ABSENT"}


def test_file_without_provenance_column_defaults_to_seed(tmp_path):
    """
    A fundamentals file with no data_provenance column must be treated as SEED
    (un-tradeable) — we cannot vouch for un-labelled hand-maintained numbers.
    """
    csv = tmp_path / "fundamentals.csv"
    csv.write_text("symbol,eps,fair_value\nHBL,26.5,385\n", encoding="utf-8")

    df = load_fundamentals(csv)
    assert (df[PROVENANCE_COLUMN] == "SEED").all()
