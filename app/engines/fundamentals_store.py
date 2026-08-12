"""
Read-only access to the REAL PSX fundamentals scraped by tools/fetch_fundamentals.py
(database/fundamentals/psx_fundamentals.json). Genuine sourced data — never
invented. Returns {} when a symbol has no fundamentals or the store is absent.
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STORE = PROJECT_ROOT / "database" / "fundamentals" / "psx_fundamentals.json"


def load_all() -> dict:
    if not STORE.exists() or STORE.stat().st_size == 0:
        return {}
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    data.pop("_meta", None)
    return data


def get_fundamentals(symbol: str) -> dict:
    return load_all().get(str(symbol).strip().upper(), {})
