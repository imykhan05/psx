"""
Multi-horizon win-rate analyzer for replay signals (ROADMAP.md F1.2).

Measures how well each verdict tier predicts forward price direction at several
holding horizons, and separately reports the limit-entry fill rate — the two
caveats that made the first F1.1 result inconclusive.

PREDICTIVE-POWER METRIC (primary)
  For each signal, forward return is measured close-to-close from the SIGNAL-DAY
  close (signal_close) to the close H trading days later:
        ret_H = (close[D+H] - signal_close) / signal_close * 100
  Entry at the signal-day close always "fills", so this isolates the verdict's
  predictive value from the separate question of whether a limit entry filled.
  win_H = ret_H > 0.

ENTRY-FILL REALISM (caveat #2)
  entry_filled = did the low over the next 10 trading days reach the signal's
  limit entry_price. Reported per tier so we can see how often the rules'
  intended entries would actually have been reachable.

This module MEASURES ONLY. It does not touch the scoring rules.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DB_PATH = Path("database/psx_terminal.db")
HORIZONS = (3, 5, 10)
FILL_WINDOW = 10


def _load_prices() -> pd.DataFrame:
    import sqlite3

    conn = sqlite3.connect(str(DB_PATH))
    try:
        prices = pd.read_sql_query(
            "SELECT symbol, date, close, low FROM daily_prices", conn
        )
    finally:
        conn.close()

    prices["symbol"] = prices["symbol"].astype(str).str.upper().str.strip()
    prices["dp"] = pd.to_datetime(prices["date"], format="%d%b%Y", errors="coerce")
    prices = prices.dropna(subset=["dp"]).sort_values(["symbol", "dp"]).reset_index(drop=True)
    return prices


def _add_forward_columns(prices: pd.DataFrame) -> pd.DataFrame:
    """Vectorized per-symbol forward closes and forward min-low (for fill)."""
    g = prices.groupby("symbol", sort=False)

    for h in HORIZONS:
        prices[f"fwd_close_{h}"] = g["close"].shift(-h)

    def fwd_min_low(low: pd.Series) -> pd.Series:
        # min of low over the next FILL_WINDOW rows (excluding the current row).
        rev = low.iloc[::-1]
        m = rev.shift(1).rolling(FILL_WINDOW, min_periods=1).min()
        return m.iloc[::-1]

    prices["fwd_min_low_10"] = g["low"].transform(fwd_min_low)
    prices["key"] = prices["dp"].dt.strftime("%Y-%m-%d")
    return prices


def _wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    z = 1.96
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round((centre - half) * 100, 1), round((centre + half) * 100, 1))


def analyze(replay_file: str | Path) -> pd.DataFrame:
    replay_file = Path(replay_file)
    signals = pd.read_csv(replay_file)
    signals["symbol"] = signals["symbol"].astype(str).str.upper().str.strip()
    signals["decision"] = signals["decision"].astype(str).str.upper().str.strip()
    signals["signal_close"] = pd.to_numeric(signals["signal_close"], errors="coerce")
    signals["entry_price"] = pd.to_numeric(signals.get("entry_price", 0), errors="coerce")
    signals["key"] = signals["signal_date_iso"].astype(str)

    prices = _add_forward_columns(_load_prices())

    merged = signals.merge(
        prices[["symbol", "key", "fwd_close_3", "fwd_close_5", "fwd_close_10", "fwd_min_low_10"]],
        on=["symbol", "key"],
        how="left",
    )

    merged = merged[merged["signal_close"] > 0].copy()

    for h in HORIZONS:
        merged[f"ret_{h}"] = (
            (merged[f"fwd_close_{h}"] - merged["signal_close"]) / merged["signal_close"] * 100
        )

    merged["entry_filled"] = (
        merged["fwd_min_low_10"].notna()
        & (merged["entry_price"] > 0)
        & (merged["fwd_min_low_10"] <= merged["entry_price"])
    )

    tiers = ["STRONG BUY", "BUY", "ACCUMULATE", "WATCH", "AVOID"]
    rows = []
    for tier in tiers:
        t = merged[merged["decision"] == tier]
        if len(t) == 0:
            continue
        row = {"tier": tier, "signals": len(t)}
        for h in HORIZONS:
            r = t[f"ret_{h}"].dropna()
            n = len(r)
            k = int((r > 0).sum())
            wr = round(k / n * 100, 1) if n else float("nan")
            lo, hi = _wilson(k, n)
            row[f"win_{h}d_%"] = wr
            row[f"win_{h}d_CI"] = f"[{lo},{hi}]"
            row[f"avg_{h}d_%"] = round(r.mean(), 2) if n else float("nan")
            row[f"n_{h}d"] = n
        row["fill_rate_%"] = round(t["entry_filled"].mean() * 100, 1)
        rows.append(row)

    return pd.DataFrame(rows)


def print_report(replay_file: str | Path) -> pd.DataFrame:
    table = analyze(replay_file)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 40)

    print("=" * 100)
    print(f"F1.2 MULTI-HORIZON WIN-RATE REPORT  |  source: {replay_file}")
    print("=" * 100)

    win_cols = ["tier", "signals"]
    for h in HORIZONS:
        win_cols += [f"n_{h}d", f"win_{h}d_%", f"win_{h}d_CI", f"avg_{h}d_%"]
    win_cols += ["fill_rate_%"]
    print(table[win_cols].to_string(index=False))
    print()
    print("win = close-to-close forward return from signal-day close > 0 (market-on-close entry).")
    print("fill_rate = share of signals whose limit entry_price was reached within 10 trading days.")
    return table


if __name__ == "__main__":
    import sys

    src = sys.argv[1] if len(sys.argv) > 1 else "database/backtesting/replay_signals_dense.csv"
    print_report(src)
