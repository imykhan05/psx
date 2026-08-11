"""
Fundamental data loader with provenance tracking.

Every fundamentals row carries a `data_provenance` label so downstream engines
can refuse to emit a valuation, verdict, or confidence from data that is not
genuinely sourced. See ROADMAP.md F0.1.

Provenance values:
- REAL   : sourced from an actual financial statement / verified data feed.
- SEED   : hand-entered / illustrative placeholder. NOT tradeable. Must never
           produce an investment recommendation.
- ABSENT : no fundamentals exist for this symbol.

The loader treats anything that is not exactly REAL as non-tradeable. A file
with no `data_provenance` column is assumed SEED — we have no basis to call
un-labelled, hand-maintained numbers real.
"""

from pathlib import Path

import pandas as pd


FUNDAMENTALS_PATH = Path("database/fundamentals/fundamentals.csv")

PROVENANCE_COLUMN = "data_provenance"

PROVENANCE_REAL = "REAL"
PROVENANCE_SEED = "SEED"
PROVENANCE_ABSENT = "ABSENT"


def _normalize_provenance(value) -> str:
    """Map any raw provenance value onto a known label; default to SEED."""
    text = str(value).strip().upper()

    if text == PROVENANCE_REAL:
        return PROVENANCE_REAL

    if text == PROVENANCE_ABSENT:
        return PROVENANCE_ABSENT

    # Unknown, blank, NaN, or explicitly SEED -> treat as un-tradeable SEED.
    return PROVENANCE_SEED


def load_fundamentals(path: Path = FUNDAMENTALS_PATH) -> pd.DataFrame:
    """
    Load fundamentals if present, else return an empty frame.

    Never raises on a missing/empty file: the correct state for a system with
    no sourced fundamentals is "no fundamentals", not a crash. Every returned
    row carries a normalized `data_provenance` label.
    """
    path = Path(path)

    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=["symbol", PROVENANCE_COLUMN])

    df = pd.read_csv(path)

    if df.empty or "symbol" not in df.columns:
        return pd.DataFrame(columns=["symbol", PROVENANCE_COLUMN])

    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()

    if PROVENANCE_COLUMN not in df.columns:
        # No provenance recorded -> we cannot vouch for these numbers.
        df[PROVENANCE_COLUMN] = PROVENANCE_SEED

    df[PROVENANCE_COLUMN] = df[PROVENANCE_COLUMN].apply(_normalize_provenance)

    return df


def merge_fundamentals(price_df: pd.DataFrame) -> pd.DataFrame:
    """
    Left-merge fundamentals onto the price frame. Symbols with no fundamentals
    row are labelled ABSENT so the long-term engine can gate them out.
    """
    prices = price_df.copy()
    prices["symbol"] = prices["symbol"].astype(str).str.strip().str.upper()

    fundamentals = load_fundamentals()

    if fundamentals.empty:
        merged = prices.copy()
        merged[PROVENANCE_COLUMN] = PROVENANCE_ABSENT
        return merged

    merged = prices.merge(
        fundamentals,
        on="symbol",
        how="left",
    )

    merged[PROVENANCE_COLUMN] = (
        merged[PROVENANCE_COLUMN]
        .fillna(PROVENANCE_ABSENT)
        .apply(_normalize_provenance)
    )

    return merged


def fundamentals_summary() -> dict:
    """Provenance-aware summary; never raises on a missing file."""
    df = load_fundamentals()

    if df.empty:
        return {
            "fundamental_records": 0,
            "symbols": 0,
            "real_symbols": 0,
            "seed_symbols": 0,
            "tradeable": False,
            "file": str(FUNDAMENTALS_PATH),
            "note": (
                "No sourced fundamentals present. Long-term valuation is "
                "disabled until real data is ingested (ROADMAP.md F3.3)."
            ),
        }

    provenance = df[PROVENANCE_COLUMN]
    real_count = int((provenance == PROVENANCE_REAL).sum())
    seed_count = int((provenance == PROVENANCE_SEED).sum())

    return {
        "fundamental_records": int(len(df)),
        "symbols": int(df["symbol"].nunique()),
        "real_symbols": real_count,
        "seed_symbols": seed_count,
        "tradeable": real_count > 0,
        "file": str(FUNDAMENTALS_PATH),
        "note": (
            "Only REAL-provenance symbols may produce long-term verdicts."
            if real_count > 0
            else "No REAL-provenance fundamentals; long-term valuation disabled."
        ),
    }
