from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from app.engines.backtesting.signal_tracker_v1 import (
    SIGNAL_HISTORY_COLUMNS,
    SIGNAL_HISTORY_FILE,
    SignalTrackerV1,
    parse_signal_date,
    remove_duplicate_columns,
)


DEFAULT_HISTORY_SOURCE = Path(
    "database/psx_history_clean.csv"
)


@dataclass
class BacktestConfigV1:
    signal_history_file: Path = SIGNAL_HISTORY_FILE
    historical_prices_file: Path = DEFAULT_HISTORY_SOURCE
    max_holding_days: int = 5
    target_priority: bool = False
    close_open_signals_after_max_days: bool = True


class BacktestEngineV1:
    """
    Backtest Engine V1

    Evaluates saved portfolio signals against historical daily OHLC data.

    Core behaviour:
    - Reads signals from database/backtesting/signal_history.csv
    - Reads historical prices from database/psx_history_clean.csv
    - Evaluates target 1, target 2 and stop-loss
    - Tracks 1D/2D/3D/5D returns
    - Calculates MFE and MAE
    - Updates outcome status and realized P/L
    - Preserves pending signals when future data is unavailable
    """

    VERSION = "backtest_engine_v1_1_auto_schema_migration"

    def __init__(
        self,
        signal_history_file: str | Path = SIGNAL_HISTORY_FILE,
        historical_prices_file: str | Path = DEFAULT_HISTORY_SOURCE,
        max_holding_days: int = 5,
        target_priority: bool = False,
        close_open_signals_after_max_days: bool = True,
    ):
        self.config = BacktestConfigV1(
            signal_history_file=Path(
                signal_history_file
            ),
            historical_prices_file=Path(
                historical_prices_file
            ),
            max_holding_days=int(
                max_holding_days
            ),
            target_priority=bool(
                target_priority
            ),
            close_open_signals_after_max_days=bool(
                close_open_signals_after_max_days
            ),
        )

        self.tracker = SignalTrackerV1(
            history_file=self.config.signal_history_file
        )

    def run(self) -> dict:
        signals = self.tracker.load_history()

        if signals.empty:
            return self.summary(
                status="success",
                reason="No signals available for backtesting",
                evaluated=0,
                updated=0,
                closed=0,
                pending=0,
                signals=signals,
            )

        prices = self.load_historical_prices()

        if prices.empty:
            return self.summary(
                status="failed",
                reason="Historical price data unavailable",
                evaluated=0,
                updated=0,
                closed=0,
                pending=len(signals),
                signals=signals,
            )

        updated_signals = signals.copy()

        evaluated_count = 0
        updated_count = 0
        closed_count = 0
        pending_count = 0

        for index, signal in signals.iterrows():
            result = self.evaluate_signal(
                signal=signal,
                prices=prices,
            )

            if result is None:
                pending_count += 1
                continue

            evaluated_count += 1

            changed = False

            # ---------------------------------------------------------
            # AUTO SCHEMA MIGRATION
            # Create any columns produced by the latest backtest engine
            # that do not yet exist in an older signal_history.csv file.
            # ---------------------------------------------------------
            for column, value in result.items():
                if column not in updated_signals.columns:
                    if isinstance(value, bool):
                        updated_signals[column] = False
                    elif isinstance(value, (int, float)):
                        updated_signals[column] = 0.0
                    else:
                        updated_signals[column] = ""

            for column, value in result.items():
                old_value = updated_signals.at[
                    index,
                    column,
                ]

                if not values_equal(
                    old_value,
                    value,
                ):
                    updated_signals.at[
                        index,
                        column,
                    ] = value
                    changed = True

            if changed:
                updated_count += 1

            if result.get(
                "tracking_status"
            ) == "CLOSED":
                closed_count += 1
            else:
                pending_count += 1

        updated_signals = self.tracker.normalize_history(
            updated_signals
        )

        self.tracker.save_history(
            updated_signals
        )

        return self.summary(
            status="success",
            reason="Backtesting completed successfully",
            evaluated=evaluated_count,
            updated=updated_count,
            closed=closed_count,
            pending=pending_count,
            signals=updated_signals,
        )

    def load_historical_prices(
        self,
    ) -> pd.DataFrame:
        path = self.config.historical_prices_file

        if not path.exists() or path.stat().st_size == 0:
            return pd.DataFrame()

        try:
            prices = pd.read_csv(path)
        except (
            pd.errors.EmptyDataError,
            pd.errors.ParserError,
            UnicodeDecodeError,
        ):
            return pd.DataFrame()

        prices = remove_duplicate_columns(
            prices
        )

        required = {
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
        }

        if not required.issubset(
            prices.columns
        ):
            return pd.DataFrame()

        prices["symbol"] = (
            prices["symbol"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.strip()
        )

        prices["date_parsed"] = pd.to_datetime(
            prices["date"],
            format="%d%b%Y",
            errors="coerce",
        )

        if prices["date_parsed"].isna().all():
            prices["date_parsed"] = pd.to_datetime(
                prices["date"],
                errors="coerce",
            )

        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]

        for column in numeric_columns:
            if column in prices.columns:
                prices[column] = pd.to_numeric(
                    prices[column],
                    errors="coerce",
                )

        prices = prices.dropna(
            subset=[
                "symbol",
                "date_parsed",
                "high",
                "low",
                "close",
            ]
        ).copy()

        prices = prices[
            prices["symbol"] != ""
        ].copy()

        prices = prices.sort_values(
            by=[
                "symbol",
                "date_parsed",
            ],
            kind="stable",
        ).reset_index(drop=True)

        return prices

    def evaluate_signal(
        self,
        signal: pd.Series,
        prices: pd.DataFrame,
    ) -> dict | None:
        symbol = str(
            signal.get("symbol", "")
        ).strip().upper()

        signal_date = parse_signal_date(
            signal.get(
                "signal_date_iso",
                signal.get(
                    "signal_date"
                ),
            )
        )

        if not symbol or signal_date is None:
            return None

        entry_price = safe_float(
            signal.get("entry_price")
        )
        stop_loss = safe_float(
            signal.get("stop_loss")
        )
        target_1 = safe_float(
            signal.get("target_1")
        )
        target_2 = safe_float(
            signal.get("target_2")
        )
        quantity = safe_int(
            signal.get("quantity")
        )

        if entry_price <= 0:
            return None

        future = prices[
            (prices["symbol"] == symbol)
            & (
                prices["date_parsed"]
                > signal_date
            )
        ].copy()

        if future.empty:
            return None

        future = future.sort_values(
            "date_parsed"
        ).head(
            self.config.max_holding_days
        )

        if future.empty:
            return None

        max_high = float(
            future["high"].max()
        )
        min_low = float(
            future["low"].min()
        )

        mfe_pct = (
            (max_high - entry_price)
            / entry_price
            * 100
        )

        mae_pct = (
            (min_low - entry_price)
            / entry_price
            * 100
        )

        outcome = self.resolve_outcome(
            future=future,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_1=target_1,
            target_2=target_2,
        )

        exit_price = outcome[
            "exit_price"
        ]
        exit_date = outcome[
            "exit_date"
        ]
        holding_days = outcome[
            "holding_days"
        ]
        tracking_status = outcome[
            "tracking_status"
        ]

        return_pct = (
            (exit_price - entry_price)
            / entry_price
            * 100
            if exit_price > 0
            else 0.0
        )

        profit_loss = (
            (exit_price - entry_price)
            * quantity
            if exit_price > 0
            else 0.0
        )

        day_returns = self.calculate_day_returns(
            future=future,
            entry_price=entry_price,
        )

        result = {
            "tracking_status": tracking_status,
            "outcome_status": outcome[
                "outcome_status"
            ],
            "target_1_hit": bool(
                outcome["target_1_hit"]
            ),
            "target_2_hit": bool(
                outcome["target_2_hit"]
            ),
            "stop_loss_hit": bool(
                outcome["stop_loss_hit"]
            ),
            "exit_price": round(
                exit_price,
                4,
            ),
            "exit_date": (
                exit_date.strftime(
                    "%Y-%m-%d"
                )
                if exit_date is not None
                else ""
            ),
            "holding_days": int(
                holding_days
            ),
            "return_pct": round(
                return_pct,
                4,
            ),
            "profit_loss": round(
                profit_loss,
                2,
            ),
            "max_favorable_excursion_pct": round(
                mfe_pct,
                4,
            ),
            "max_adverse_excursion_pct": round(
                mae_pct,
                4,
            ),
            "last_evaluated_date": future[
                "date_parsed"
            ].max().strftime(
                "%Y-%m-%d"
            ),
        }

        result.update(day_returns)

        return result

    def resolve_outcome(
        self,
        future: pd.DataFrame,
        entry_price: float,
        stop_loss: float,
        target_1: float,
        target_2: float,
    ) -> dict:
        target_1_hit = False
        target_2_hit = False
        stop_loss_hit = False

        for day_number, (
            _,
            row,
        ) in enumerate(
            future.iterrows(),
            start=1,
        ):
            high = safe_float(
                row.get("high")
            )
            low = safe_float(
                row.get("low")
            )
            close = safe_float(
                row.get("close")
            )
            date = row.get(
                "date_parsed"
            )

            hit_stop = (
                stop_loss > 0
                and low <= stop_loss
            )
            hit_t1 = (
                target_1 > 0
                and high >= target_1
            )
            hit_t2 = (
                target_2 > 0
                and high >= target_2
            )

            if hit_t2:
                target_2_hit = True
                target_1_hit = True

            elif hit_t1:
                target_1_hit = True

            if hit_stop:
                stop_loss_hit = True

            if hit_stop and (
                hit_t1 or hit_t2
            ):
                if self.config.target_priority:
                    if hit_t2:
                        return {
                            "tracking_status": "CLOSED",
                            "outcome_status": "TARGET_2 HIT",
                            "target_1_hit": True,
                            "target_2_hit": True,
                            "stop_loss_hit": True,
                            "exit_price": target_2,
                            "exit_date": date,
                            "holding_days": day_number,
                        }

                    return {
                        "tracking_status": "CLOSED",
                        "outcome_status": "TARGET_1 HIT",
                        "target_1_hit": True,
                        "target_2_hit": False,
                        "stop_loss_hit": True,
                        "exit_price": target_1,
                        "exit_date": date,
                        "holding_days": day_number,
                    }

                return {
                    "tracking_status": "CLOSED",
                    "outcome_status": "STOP LOSS HIT",
                    "target_1_hit": target_1_hit,
                    "target_2_hit": target_2_hit,
                    "stop_loss_hit": True,
                    "exit_price": stop_loss,
                    "exit_date": date,
                    "holding_days": day_number,
                }

            if hit_t2:
                return {
                    "tracking_status": "CLOSED",
                    "outcome_status": "TARGET_2 HIT",
                    "target_1_hit": True,
                    "target_2_hit": True,
                    "stop_loss_hit": stop_loss_hit,
                    "exit_price": target_2,
                    "exit_date": date,
                    "holding_days": day_number,
                }

            if hit_t1:
                return {
                    "tracking_status": "CLOSED",
                    "outcome_status": "TARGET_1 HIT",
                    "target_1_hit": True,
                    "target_2_hit": False,
                    "stop_loss_hit": stop_loss_hit,
                    "exit_price": target_1,
                    "exit_date": date,
                    "holding_days": day_number,
                }

            if hit_stop:
                return {
                    "tracking_status": "CLOSED",
                    "outcome_status": "STOP LOSS HIT",
                    "target_1_hit": False,
                    "target_2_hit": False,
                    "stop_loss_hit": True,
                    "exit_price": stop_loss,
                    "exit_date": date,
                    "holding_days": day_number,
                }

        last_row = future.iloc[-1]
        last_close = safe_float(
            last_row.get("close")
        )
        last_date = last_row.get(
            "date_parsed"
        )
        observed_days = len(future)

        if (
            observed_days
            >= self.config.max_holding_days
            and self.config.close_open_signals_after_max_days
        ):
            return {
                "tracking_status": "CLOSED",
                "outcome_status": "TIME EXIT",
                "target_1_hit": target_1_hit,
                "target_2_hit": target_2_hit,
                "stop_loss_hit": stop_loss_hit,
                "exit_price": last_close,
                "exit_date": last_date,
                "holding_days": observed_days,
            }

        return {
            "tracking_status": "OPEN",
            "outcome_status": "PENDING",
            "target_1_hit": target_1_hit,
            "target_2_hit": target_2_hit,
            "stop_loss_hit": stop_loss_hit,
            "exit_price": last_close,
            "exit_date": last_date,
            "holding_days": observed_days,
        }

    def calculate_day_returns(
        self,
        future: pd.DataFrame,
        entry_price: float,
    ) -> dict:
        output = {
            "return_1d": 0.0,
            "return_2d": 0.0,
            "return_3d": 0.0,
            "return_5d": 0.0,
        }

        mapping = {
            1: "return_1d",
            2: "return_2d",
            3: "return_3d",
            5: "return_5d",
        }

        for day_number, column in mapping.items():
            if len(future) < day_number:
                continue

            close = safe_float(
                future.iloc[
                    day_number - 1
                ].get("close")
            )

            if close <= 0:
                continue

            output[column] = round(
                (
                    (close - entry_price)
                    / entry_price
                    * 100
                ),
                4,
            )

        return output

    def summary(
        self,
        status: str,
        reason: str,
        evaluated: int,
        updated: int,
        closed: int,
        pending: int,
        signals: pd.DataFrame,
    ) -> dict:
        total = len(signals)

        win_count = 0
        loss_count = 0
        time_exit_count = 0
        avg_return = 0.0
        total_profit_loss = 0.0

        if not signals.empty:
            outcome = signals[
                "outcome_status"
            ].astype(str)

            win_count = int(
                outcome.isin([
                    "TARGET_1 HIT",
                    "TARGET_2 HIT",
                ]).sum()
            )

            loss_count = int(
                (
                    outcome
                    == "STOP LOSS HIT"
                ).sum()
            )

            time_exit_count = int(
                (
                    outcome
                    == "TIME EXIT"
                ).sum()
            )

            closed_mask = (
                signals[
                    "tracking_status"
                ].astype(str)
                == "CLOSED"
            )

            closed_signals = signals[
                closed_mask
            ]

            if not closed_signals.empty:
                avg_return = float(
                    pd.to_numeric(
                        closed_signals[
                            "return_pct"
                        ],
                        errors="coerce",
                    )
                    .fillna(0)
                    .mean()
                )

                total_profit_loss = float(
                    pd.to_numeric(
                        closed_signals[
                            "profit_loss"
                        ],
                        errors="coerce",
                    )
                    .fillna(0)
                    .sum()
                )

        decisive = win_count + loss_count

        win_rate = (
            win_count
            / decisive
            * 100
            if decisive > 0
            else 0.0
        )

        return {
            "status": status,
            "engine_version": self.VERSION,
            "reason": reason,
            "signal_history_file": str(
                self.config.signal_history_file
            ),
            "historical_prices_file": str(
                self.config.historical_prices_file
            ),
            "max_holding_days": int(
                self.config.max_holding_days
            ),
            "total_signals": int(total),
            "evaluated_signals": int(
                evaluated
            ),
            "updated_signals": int(
                updated
            ),
            "closed_signals": int(
                closed
            ),
            "pending_signals": int(
                pending
            ),
            "wins": int(win_count),
            "losses": int(loss_count),
            "time_exits": int(
                time_exit_count
            ),
            "win_rate_pct": round(
                win_rate,
                2,
            ),
            "average_return_pct": round(
                avg_return,
                4,
            ),
            "total_profit_loss": round(
                total_profit_loss,
                2,
            ),
        }


def run_backtest_v1(
    signal_history_file: str | Path = SIGNAL_HISTORY_FILE,
    historical_prices_file: str | Path = DEFAULT_HISTORY_SOURCE,
    max_holding_days: int = 5,
    target_priority: bool = False,
    close_open_signals_after_max_days: bool = True,
) -> dict:
    engine = BacktestEngineV1(
        signal_history_file=signal_history_file,
        historical_prices_file=historical_prices_file,
        max_holding_days=max_holding_days,
        target_priority=target_priority,
        close_open_signals_after_max_days=(
            close_open_signals_after_max_days
        ),
    )

    return engine.run()


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        if pd.isna(value):
            return float(default)
    except Exception:
        pass

    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return float(default)


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(
            float(value)
        )
    except (
        TypeError,
        ValueError,
    ):
        return int(default)


def values_equal(
    left: Any,
    right: Any,
) -> bool:
    try:
        if pd.isna(left) and pd.isna(right):
            return True
    except Exception:
        pass

    if isinstance(
        left,
        (int, float),
    ) or isinstance(
        right,
        (int, float),
    ):
        try:
            return abs(
                float(left)
                - float(right)
            ) < 1e-9
        except Exception:
            pass

    return str(left) == str(right)