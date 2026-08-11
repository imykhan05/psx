"""
Look-ahead bias tests for historical replay (ROADMAP.md F1.1).

These are the guarantee that underpins the whole replay: a feature value for
(symbol, date D) must depend ONLY on that symbol's rows dated <= D. If it also
depends on rows after D, every replay verdict is contaminated and every
downstream win-rate is meaningless.

The replay harness gains its speed by computing features once over the full
history and slicing per date ("Layer 2"). That is only legitimate if it is
byte-identical to computing features over history truncated at D ("Layer 1",
the safe definition). These tests assert exactly that equivalence, plus
determinism. If either fails, the harness must fall back to per-date truncation.
"""

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from app.engines.feature_builder_v3 import build_historical_features_v3

DB_PATH = Path("database/psx_terminal.db")

# Enough symbols to catch an accidental cross-symbol/global op, few enough to
# keep the test fast. Per-symbol independence means this is a complete test of
# the backward-looking property for these symbols.
SAMPLE_SYMBOLS = 40


@pytest.fixture(scope="module")
def sample_history() -> pd.DataFrame:
    """Load the longest-history symbols from the live DB as a replay-shaped frame."""
    if not DB_PATH.exists():
        pytest.skip("psx_terminal.db not present")

    conn = sqlite3.connect(str(DB_PATH))
    try:
        top = pd.read_sql_query(
            """
            SELECT symbol
            FROM daily_prices
            GROUP BY symbol
            ORDER BY COUNT(*) DESC
            LIMIT ?
            """,
            conn,
            params=(SAMPLE_SYMBOLS,),
        )["symbol"].tolist()

        placeholders = ",".join("?" for _ in top)
        history = pd.read_sql_query(
            f"SELECT * FROM daily_prices WHERE symbol IN ({placeholders})",
            conn,
            params=top,
        )
    finally:
        conn.close()

    history["dp"] = pd.to_datetime(history["date_parsed"], errors="coerce")
    history = history.dropna(subset=["dp"]).reset_index(drop=True)
    return history


def _test_dates(history: pd.DataFrame) -> list:
    """Pick a spread of dates with meaningful history before each."""
    dates = history[["date", "dp"]].drop_duplicates().sort_values("dp")
    dates = dates.iloc[60:]  # skip warm-up so features are populated
    if dates.empty:
        return []
    n = len(dates)
    picks = [dates.iloc[int(n * f)] for f in (0.15, 0.5, 0.85)]
    return [(row["date"], row["dp"]) for row in picks]


def _features_at(history: pd.DataFrame, date_text: str) -> pd.DataFrame:
    """Compute features over the given history and return the date_text slice,
    normalized (sorted by symbol, index reset, columns sorted) for comparison."""
    feats = build_historical_features_v3(history)
    slice_ = feats[feats["date"] == date_text].copy()
    slice_ = slice_.sort_values("symbol").reset_index(drop=True)
    return slice_.reindex(sorted(slice_.columns), axis=1)


def test_feature_asof_identity(sample_history):
    """
    Layer 1 == Layer 2: features at date D computed over FULL history must be
    byte-identical to features at D computed over history truncated at D.
    This is the core no-look-ahead guarantee.
    """
    dates = _test_dates(sample_history)
    assert dates, "no test dates available"

    for date_text, dp in dates:
        full_slice = _features_at(sample_history, date_text)

        truncated = sample_history[sample_history["dp"] <= dp].copy()
        trunc_slice = _features_at(truncated, date_text)

        assert not full_slice.empty, f"empty full slice for {date_text}"
        assert len(full_slice) == len(trunc_slice), (
            f"row-count mismatch at {date_text}: "
            f"full={len(full_slice)} truncated={len(trunc_slice)}"
        )

        pd.testing.assert_frame_equal(
            full_slice,
            trunc_slice,
            check_exact=True,
            check_like=True,
            obj=f"features at {date_text}",
        )


def test_replay_determinism(sample_history):
    """Same date replayed twice must yield identical features."""
    dates = _test_dates(sample_history)
    assert dates
    date_text = dates[len(dates) // 2][0]

    first = _features_at(sample_history, date_text)
    second = _features_at(sample_history, date_text)

    pd.testing.assert_frame_equal(first, second, check_exact=True)


def test_truncation_hides_future_rows(sample_history):
    """
    Sanity: truncating at D must actually remove rows after D (guards against a
    truncation that silently no-ops and makes the identity test vacuous).
    """
    dates = _test_dates(sample_history)
    assert dates
    _, dp = dates[0]  # earliest test date -> lots of future rows exist

    truncated = sample_history[sample_history["dp"] <= dp]
    assert len(truncated) < len(sample_history), "truncation removed nothing"
    assert truncated["dp"].max() <= dp
