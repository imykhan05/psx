"""
Historical Signal Replay Engine V1 (ROADMAP.md F1.1).

Walks the full EOD history day by day, runs the existing rule-based scoring
chain on each day's as-of snapshot, records every verdict, then labels outcomes
against subsequent prices via the existing backtest engine. This converts the
~4 forward-recorded signals into a large, honestly-labelled dataset that can
finally validate the rule weights (F1.2) and later seed ML (F4.x).

LOOK-AHEAD SAFETY
-----------------
Features are computed ONCE over full history and sliced per date. This is only
valid because it is byte-identical to computing features over history truncated
at each date — proven by tests/test_lookahead_replay.py (the standing guard).
Every feature transform in feature_builder_v3 is a per-symbol backward-looking
rolling/ewm window; none look forward. The scoring engines used here are pure
functions of the as-of snapshot (verified: no disk/DB reads, no wall-clock).

STATE ISOLATION
---------------
This harness runs ONLY the scoring->verdict subset. It does not run portfolio
allocation, trade lifecycle, company-master sync, reporting, or the live signal
tracker, and it never writes to the live signal_history.csv, portfolio, or
report folders. Its only output is its own replay signals file.

OUTCOMES ARE LABELS, NOT FEATURES
---------------------------------
Outcome resolution uses future prices (D+1..D+N) via run_backtest_v1. Future
data as a label is correct; it never feeds a feature.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from app.engines.feature_builder_v3 import build_historical_features_v3
from app.engines.market_engine import MarketEngine
from app.engines.ai_engine_v5 import apply_ai_engine_v5
from app.engines.recommendation_engine import build_recommendations
from app.engines.decision_engine_v2 import apply_decision_engine_v2
from app.engines.trade_validation_engine import apply_trade_validation
from app.engines.entry_timing_engine import apply_entry_timing
from app.engines.risk_management_engine_v2 import apply_risk_management_v2
from app.engines.institutional_v5_calibrator import apply_institutional_v5_calibration
from app.engines.signal_consensus_engine import apply_signal_consensus
from app.engines.backtesting.signal_tracker_v1 import SIGNAL_HISTORY_COLUMNS
from app.engines.backtesting.backtest_engine_v1 import (
    run_backtest_v1,
    BacktestEngineV1,
    values_equal,
)

# Reused from main.py (import-safe: main() only runs under __main__).
from main import (
    clean_duplicate_columns,
    apply_consensus_master_decision,
)

DB_PATH = Path("database/psx_terminal.db")
HISTORY_PRICES_FILE = Path("database/psx_history_clean.csv")
DEFAULT_OUTPUT = Path("database/backtesting/replay_signals.csv")

REPLAY_ENGINE_VERSION = "replay_engine_v1"

# The replay file carries the standard signal schema plus a few replay-only
# columns needed for honest measurement (F1.2):
#   signal_close  - the close on the signal day (a market-on-close entry basis
#                   that always fills, isolating predictive power from the
#                   limit-entry fill question).
REPLAY_EXTRA_COLUMNS = ["signal_close"]
REPLAY_OUTPUT_COLUMNS = list(SIGNAL_HISTORY_COLUMNS) + REPLAY_EXTRA_COLUMNS


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_full_history(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Load the full daily_prices table as the replay history frame."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        history = pd.read_sql_query("SELECT * FROM daily_prices", conn)
    finally:
        conn.close()

    history["dp"] = pd.to_datetime(history["date_parsed"], errors="coerce")
    history = history.dropna(subset=["dp"]).reset_index(drop=True)
    return history


# ---------------------------------------------------------------------------
# Scoring subset (mirrors main.py's chain up to the consensus master decision)
# ---------------------------------------------------------------------------
def run_scoring_chain(
    snapshot: pd.DataFrame,
    capital: int,
    max_price: float,
) -> pd.DataFrame:
    """Run the rule-based scoring chain on one as-of day snapshot and return the
    finalized per-symbol decision frame. Pure function of the snapshot."""
    features = clean_duplicate_columns(snapshot.copy())

    # Engines expect these metadata columns; replay does not run company
    # enrichment (which mutates shared files), so default them if absent.
    for column, default in (("sector", "UNKNOWN"), ("industry", "UNKNOWN")):
        if column not in features.columns:
            features[column] = default

    market_summary = MarketEngine(features).summary()

    result = apply_ai_engine_v5(
        features,
        max_price=max_price,
        market_summary=market_summary,
    )
    result = clean_duplicate_columns(result)

    result = build_recommendations(result, capital=capital)
    result = clean_duplicate_columns(result)

    result = apply_decision_engine_v2(result, market_summary)
    result = clean_duplicate_columns(result)

    result = apply_trade_validation(result)
    result = clean_duplicate_columns(result)

    result = apply_entry_timing(result)
    result = clean_duplicate_columns(result)

    result = apply_risk_management_v2(result)
    result = clean_duplicate_columns(result)

    result = apply_institutional_v5_calibration(
        result,
        market_summary=market_summary,
        remove_blocked_from_final=False,
    )
    result = clean_duplicate_columns(result)

    result = apply_signal_consensus(result, market_summary=market_summary)
    result = clean_duplicate_columns(result)

    result = apply_consensus_master_decision(result)
    result = clean_duplicate_columns(result)

    result.attrs["market_summary"] = market_summary
    return result


# ---------------------------------------------------------------------------
# Signal record construction (SIGNAL_HISTORY_COLUMNS schema)
# ---------------------------------------------------------------------------
def _num(row, key, default=0.0):
    value = row.get(key, default)
    try:
        if pd.isna(value):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _text(row, key, default=""):
    value = row.get(key, default)
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _first_positive(row, keys):
    for key in keys:
        value = _num(row, key, 0.0)
        if value > 0:
            return value
    return 0.0


def label_outcomes_grouped(
    signal_file: Path,
    history_prices_file: Path,
    max_holding_days: int,
) -> dict:
    """
    Label replay outcomes fast, reusing BacktestEngineV1.evaluate_signal's exact
    outcome logic but eliminating its per-signal full-frame scan.

    The stock engine filters the whole ~900k-row price frame for every signal
    (O(signals x prices) -> hours at replay scale). Here we group prices by
    symbol once and hand evaluate_signal only that symbol's rows, so the
    internal filter is trivial. Outcome semantics are identical.
    """
    engine = BacktestEngineV1(
        signal_history_file=str(signal_file),
        historical_prices_file=str(history_prices_file),
        max_holding_days=max_holding_days,
        target_priority=False,
        close_open_signals_after_max_days=True,
    )

    signals = engine.tracker.load_history()
    if signals.empty:
        return {"status": "success", "evaluated": 0, "closed": 0, "reason": "no signals"}

    prices = engine.load_historical_prices()
    if prices.empty:
        return {"status": "failed", "reason": "no historical prices"}

    # Pre-group prices by symbol, each sorted by date (one pass).
    price_groups = {
        symbol: group.sort_values("date_parsed")
        for symbol, group in prices.groupby("symbol", sort=False)
    }
    empty_prices = prices.iloc[0:0]

    updated = signals.copy()
    evaluated = 0
    closed = 0

    for index, signal in signals.iterrows():
        symbol = str(signal.get("symbol", "")).strip().upper()
        group = price_groups.get(symbol, empty_prices)

        result = engine.evaluate_signal(signal=signal, prices=group)
        if result is None:
            continue

        evaluated += 1
        for column, value in result.items():
            if column not in updated.columns:
                if isinstance(value, bool):
                    updated[column] = False
                elif isinstance(value, (int, float)):
                    updated[column] = 0.0
                else:
                    updated[column] = ""
            if not values_equal(updated.at[index, column], value):
                updated.at[index, column] = value

        if str(result.get("tracking_status", "")).upper() == "CLOSED":
            closed += 1

    updated = engine.tracker.normalize_history(updated)
    engine.tracker.save_history(updated)

    return {
        "status": "success",
        "evaluated": evaluated,
        "closed": closed,
        "signal_file": str(signal_file),
    }


def build_replay_record(
    row: pd.Series,
    signal_date_text: str,
    signal_date_iso: str,
    market_summary: dict,
    source_file: str,
) -> dict:
    """Map one finalized decision row onto the signal-history schema."""
    symbol = _text(row, "symbol")

    entry_price = _first_positive(
        row, ["adjusted_entry_price", "suggested_entry_price", "entry_high", "close"]
    )

    record = {column: "" for column in REPLAY_OUTPUT_COLUMNS}
    record.update(
        {
            "signal_id": f"{signal_date_iso}_{symbol}",
            "signal_close": _num(row, "close"),
            "signal_date": signal_date_text,
            "signal_date_iso": signal_date_iso,
            "recorded_at": datetime.now().isoformat(timespec="seconds"),
            "symbol": symbol,
            "company": _text(row, "company"),
            "sector": _text(row, "sector", "UNKNOWN") or "UNKNOWN",
            "industry": _text(row, "industry", "UNKNOWN") or "UNKNOWN",
            "decision": _text(row, "final_decision"),
            "consensus_decision": _text(row, "consensus_decision"),
            "entry_action": _text(row, "entry_timing_action"),
            "risk_permission": _text(row, "risk_permission"),
            "risk_status": _text(row, "risk_status"),
            "market_mood": str(market_summary.get("market_mood", "")),
            "market_score": float(market_summary.get("market_score", 0) or 0),
            "portfolio_rank": 0,
            "portfolio_selected": False,
            "portfolio_fallback_candidate": False,
            "entry_price": entry_price,
            "entry_low": _num(row, "entry_low"),
            "entry_high": _num(row, "entry_high"),
            "stop_loss": _num(row, "stop_loss"),
            "target_1": _num(row, "target_1"),
            "target_2": _num(row, "target_2"),
            "quantity": 0,
            "investment": 0.0,
            "risk_per_share": _num(row, "risk_per_share"),
            "max_loss": _num(row, "max_loss"),
            "expected_profit_t1": _num(row, "expected_profit_t1"),
            "expected_profit_t2": _num(row, "expected_profit_t2"),
            "risk_reward_t1": _num(row, "risk_reward_t1"),
            "final_score": _num(row, "final_score"),
            "consensus_score": _num(row, "consensus_score"),
            "consensus_confidence": _num(row, "consensus_confidence"),
            "buy_probability": _num(row, "buy_probability"),
            "confidence_v3": _num(row, "confidence_v3"),
            "smart_money_score": _num(row, "smart_money_score"),
            "accumulation_score": _num(row, "accumulation_score"),
            "trade_validation_score": _num(row, "trade_validation_score"),
            "entry_timing_score": _num(row, "entry_timing_score"),
            "risk_management_score": _num(row, "risk_management_score"),
            "engine_version": REPLAY_ENGINE_VERSION,
            "portfolio_engine_version": "",
            "source_file": source_file,
            "tracking_status": "OPEN",
            "outcome_status": "PENDING",
        }
    )
    return record


# ---------------------------------------------------------------------------
# Replay driver
# ---------------------------------------------------------------------------
def run_historical_replay(
    capital: int = 50000,
    max_price: float = 500.0,
    max_holding_days: int = 5,
    start_date: str | None = None,
    end_date: str | None = None,
    max_dates: int | None = None,
    stride: int = 1,
    warmup_dates: int = 60,
    record_decisions: tuple[str, ...] | None = None,
    output_file: Path = DEFAULT_OUTPUT,
    history_prices_file: Path = HISTORY_PRICES_FILE,
    label_outcomes: bool = True,
    flush_every: int = 25,
    progress_every: int = 10,
    resume: bool = False,
) -> dict:
    """
    Replay the scoring chain across history and (optionally) label outcomes.

    record_decisions: if given, only record signals whose final_decision is in
        this set (e.g. ("STRONG BUY","BUY","WATCH","ACCUMULATE")). Default: all.
    warmup_dates: skip the earliest N trading dates (features are sparse there).
    max_holding_days: also used to skip the most recent N dates, which have no
        forward data to evaluate.
    """
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    started = datetime.now()
    print(f"[REPLAY] loading full history from {DB_PATH} ...")
    history = load_full_history()
    print(f"[REPLAY] history rows: {len(history):,}")

    print("[REPLAY] precomputing features over full history (once) ...")
    all_features = build_historical_features_v3(history)
    all_features["dp"] = pd.to_datetime(all_features["date_parsed"], errors="coerce")

    # Ordered unique trading dates.
    date_frame = (
        all_features[["date", "dp"]]
        .dropna()
        .drop_duplicates()
        .sort_values("dp")
        .reset_index(drop=True)
    )

    # Trim warm-up (start) and the un-evaluatable tail (end).
    if warmup_dates > 0:
        date_frame = date_frame.iloc[warmup_dates:]
    if max_holding_days > 0:
        date_frame = date_frame.iloc[:-max_holding_days] if len(date_frame) > max_holding_days else date_frame.iloc[0:0]

    if start_date:
        date_frame = date_frame[date_frame["dp"] >= pd.to_datetime(start_date)]
    if end_date:
        date_frame = date_frame[date_frame["dp"] <= pd.to_datetime(end_date)]

    replay_dates = date_frame["date"].tolist()

    # Optional even sampling across the full range (regime coverage) instead of
    # a contiguous block.
    if stride and stride > 1:
        replay_dates = replay_dates[::stride]

    already_done: set[str] = set()
    if resume and output_file.exists() and output_file.stat().st_size > 0:
        existing = pd.read_csv(output_file, usecols=["signal_date"])
        already_done = set(existing["signal_date"].astype(str).unique())
        replay_dates = [d for d in replay_dates if d not in already_done]
        print(f"[REPLAY] resume: {len(already_done)} dates already done, {len(replay_dates)} remaining")

    if max_dates:
        replay_dates = replay_dates[:max_dates]

    print(f"[REPLAY] dates to process: {len(replay_dates)}")

    decision_filter = (
        {d.upper() for d in record_decisions} if record_decisions else None
    )

    write_header = not (resume and output_file.exists() and already_done)
    if not resume:
        # Fresh run: start a clean file.
        if output_file.exists():
            output_file.unlink()
        write_header = True

    buffer: list[dict] = []
    total_records = 0
    processed_dates = 0

    def flush():
        nonlocal buffer, write_header, total_records
        if not buffer:
            return
        frame = pd.DataFrame(buffer, columns=REPLAY_OUTPUT_COLUMNS)
        frame.to_csv(
            output_file,
            mode="a" if not write_header else "w",
            header=write_header,
            index=False,
            encoding="utf-8-sig",
        )
        write_header = False
        total_records += len(buffer)
        buffer = []

    for i, date_text in enumerate(replay_dates, start=1):
        snapshot = all_features[all_features["date"] == date_text].copy()
        if snapshot.empty:
            continue

        signal_date_iso = str(snapshot["dp"].iloc[0].date())

        try:
            final = run_scoring_chain(snapshot, capital=capital, max_price=max_price)
        except Exception as exc:  # a single bad day must not abort the whole run
            print(f"[REPLAY][WARN] scoring failed for {date_text}: {exc}")
            continue

        market_summary = final.attrs.get("market_summary", {})

        for _, row in final.iterrows():
            decision = _text(row, "final_decision").upper()
            if decision_filter is not None and decision not in decision_filter:
                continue
            if _num(row, "close", 0) <= 0 and _num(row, "entry_price", 0) <= 0:
                continue
            buffer.append(
                build_replay_record(
                    row=row,
                    signal_date_text=date_text,
                    signal_date_iso=signal_date_iso,
                    market_summary=market_summary,
                    source_file=REPLAY_ENGINE_VERSION,
                )
            )

        processed_dates += 1
        if processed_dates % flush_every == 0:
            flush()
        if processed_dates % progress_every == 0:
            elapsed = (datetime.now() - started).total_seconds()
            rate = processed_dates / elapsed if elapsed else 0
            print(
                f"[REPLAY] {processed_dates}/{len(replay_dates)} dates "
                f"| {total_records + len(buffer):,} signals "
                f"| {rate:.2f} dates/s"
            )

    flush()

    summary = {
        "status": "success",
        "engine_version": REPLAY_ENGINE_VERSION,
        "dates_processed": processed_dates,
        "signals_recorded": total_records,
        "output_file": str(output_file),
        "elapsed_seconds": round((datetime.now() - started).total_seconds(), 1),
    }

    if label_outcomes and total_records > 0:
        print("[REPLAY] labelling outcomes (pre-grouped fast path) ...")
        label_started = datetime.now()
        backtest_summary = label_outcomes_grouped(
            signal_file=output_file,
            history_prices_file=history_prices_file,
            max_holding_days=max_holding_days,
        )
        backtest_summary["elapsed_seconds"] = round(
            (datetime.now() - label_started).total_seconds(), 1
        )
        summary["backtest"] = backtest_summary

        labelled = pd.read_csv(output_file)
        closed = labelled[
            labelled.get("tracking_status", "").astype(str).str.upper() == "CLOSED"
        ]
        summary["signals_labelled_closed"] = int(len(closed))

    print(f"[REPLAY] done: {summary}")
    return summary
