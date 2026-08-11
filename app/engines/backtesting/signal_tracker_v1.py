from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


SIGNAL_HISTORY_FILE = Path(
    "database/backtesting/signal_history.csv"
)

SIGNAL_HISTORY_COLUMNS = [
    "signal_id",
    "signal_date",
    "signal_date_iso",
    "recorded_at",
    "symbol",
    "company",
    "sector",
    "industry",
    "decision",
    "consensus_decision",
    "entry_action",
    "risk_permission",
    "risk_status",
    "market_mood",
    "market_score",
    "portfolio_rank",
    "portfolio_selected",
    "portfolio_fallback_candidate",
    "entry_price",
    "entry_low",
    "entry_high",
    "stop_loss",
    "target_1",
    "target_2",
    "quantity",
    "investment",
    "risk_per_share",
    "max_loss",
    "expected_profit_t1",
    "expected_profit_t2",
    "risk_reward_t1",
    "final_score",
    "consensus_score",
    "consensus_confidence",
    "buy_probability",
    "confidence_v3",
    "portfolio_rank_score",
    "position_quality_index",
    "institutional_portfolio_score",
    "smart_money_score",
    "accumulation_score",
    "trade_validation_score",
    "entry_timing_score",
    "risk_management_score",
    "engine_version",
    "portfolio_engine_version",
    "source_file",
    "tracking_status",
    "outcome_status",
    "target_1_hit",
    "target_2_hit",
    "stop_loss_hit",
    "exit_price",
    "exit_date",
    "holding_days",
    "return_pct",
    "return_1d",
    "return_2d",
    "return_3d",
    "return_5d",
    "profit_loss",
    "max_favorable_excursion_pct",
    "max_adverse_excursion_pct",
    "last_evaluated_date",
]


@dataclass
class SignalTrackerConfig:
    history_file: Path = SIGNAL_HISTORY_FILE
    save_only_selected: bool = True
    allow_duplicate_signal_date: bool = False


class SignalTrackerV1:
    """
    Signal Tracker V1

    Responsibilities:
    - Save portfolio-selected signals after each scanner run.
    - Preserve a stable historical schema.
    - Avoid duplicate symbol/date records.
    - Keep future outcome columns ready for backtesting.
    - Update existing same-day signals safely.
    """

    VERSION = "signal_tracker_v1_1_backtest_returns_schema"

    def __init__(
        self,
        history_file: str | Path = SIGNAL_HISTORY_FILE,
        save_only_selected: bool = True,
        allow_duplicate_signal_date: bool = False,
    ):
        self.config = SignalTrackerConfig(
            history_file=Path(history_file),
            save_only_selected=bool(save_only_selected),
            allow_duplicate_signal_date=bool(
                allow_duplicate_signal_date
            ),
        )

    def load_history(self) -> pd.DataFrame:
        path = self.config.history_file

        if not path.exists() or path.stat().st_size == 0:
            return pd.DataFrame(
                columns=SIGNAL_HISTORY_COLUMNS
            )

        try:
            history = pd.read_csv(path)
        except (
            pd.errors.EmptyDataError,
            pd.errors.ParserError,
            UnicodeDecodeError,
        ):
            return pd.DataFrame(
                columns=SIGNAL_HISTORY_COLUMNS
            )

        return self.normalize_history(history)

    def save_history(
        self,
        history: pd.DataFrame,
    ) -> None:
        normalized = self.normalize_history(history)

        self.config.history_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        normalized.to_csv(
            self.config.history_file,
            index=False,
        )

    def record_portfolio_signals(
        self,
        portfolio: dict,
        signal_date: Any,
        source_file: str = "",
        final_df: pd.DataFrame | None = None,
    ) -> dict:
        """
        Record portfolio trades into signal history.

        Parameters:
        - portfolio: Portfolio Engine V5 result dictionary.
        - signal_date: Trading date such as 09JUL2026 or 2026-07-09.
        - source_file: Daily source file used by scanner.
        - final_df: Optional final recommendations dataframe for metadata fallback.
        """
        parsed_date = parse_signal_date(signal_date)

        if parsed_date is None:
            return {
                "status": "failed",
                "engine_version": self.VERSION,
                "reason": f"Invalid signal date: {signal_date}",
                "saved_records": 0,
                "updated_records": 0,
                "history_file": str(
                    self.config.history_file
                ),
            }

        trades = self.extract_trades(portfolio)

        if trades.empty:
            return {
                "status": "success",
                "engine_version": self.VERSION,
                "reason": "No portfolio trades to record",
                "saved_records": 0,
                "updated_records": 0,
                "total_history_records": len(
                    self.load_history()
                ),
                "history_file": str(
                    self.config.history_file
                ),
            }

        final_lookup = self.build_final_lookup(
            final_df
        )

        records = []

        for _, trade in trades.iterrows():
            record = self.build_signal_record(
                trade=trade,
                signal_date=parsed_date,
                source_file=source_file,
                final_lookup=final_lookup,
                portfolio=portfolio,
            )

            if (
                self.config.save_only_selected
                and not record["portfolio_selected"]
            ):
                continue

            records.append(record)

        if not records:
            return {
                "status": "success",
                "engine_version": self.VERSION,
                "reason": "No eligible selected signals to record",
                "saved_records": 0,
                "updated_records": 0,
                "total_history_records": len(
                    self.load_history()
                ),
                "history_file": str(
                    self.config.history_file
                ),
            }

        incoming = pd.DataFrame(
            records,
            columns=SIGNAL_HISTORY_COLUMNS,
        )

        history = self.load_history()

        combined, saved_count, updated_count = (
            self.merge_signals(
                history=history,
                incoming=incoming,
            )
        )

        self.save_history(combined)

        return {
            "status": "success",
            "engine_version": self.VERSION,
            "reason": "Portfolio signals recorded successfully",
            "saved_records": int(saved_count),
            "updated_records": int(updated_count),
            "current_run_records": int(len(incoming)),
            "total_history_records": int(
                len(combined)
            ),
            "signal_date": parsed_date.strftime(
                "%d%b%Y"
            ).upper(),
            "history_file": str(
                self.config.history_file
            ),
        }

    def extract_trades(
        self,
        portfolio: dict,
    ) -> pd.DataFrame:
        if not portfolio or not isinstance(
            portfolio,
            dict,
        ):
            return pd.DataFrame()

        trades = portfolio.get("trades")

        if trades is None:
            return pd.DataFrame()

        if isinstance(trades, pd.DataFrame):
            return remove_duplicate_columns(
                trades.copy()
            )

        try:
            return remove_duplicate_columns(
                pd.DataFrame(trades)
            )
        except Exception:
            return pd.DataFrame()

    def build_final_lookup(
        self,
        final_df: pd.DataFrame | None,
    ) -> dict[str, dict]:
        if (
            final_df is None
            or not isinstance(final_df, pd.DataFrame)
            or final_df.empty
            or "symbol" not in final_df.columns
        ):
            return {}

        data = remove_duplicate_columns(
            final_df.copy()
        )

        data["symbol"] = (
            data["symbol"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.strip()
        )

        lookup = {}

        for _, row in data.iterrows():
            symbol = str(
                row.get("symbol", "")
            ).strip().upper()

            if symbol:
                lookup[symbol] = row.to_dict()

        return lookup

    def build_signal_record(
        self,
        trade: pd.Series,
        signal_date: pd.Timestamp,
        source_file: str,
        final_lookup: dict[str, dict],
        portfolio: dict,
    ) -> dict:
        symbol = text_value(
            trade.get("symbol", "")
        )

        final_row = final_lookup.get(
            symbol,
            {},
        )

        recorded_at = datetime.now().isoformat(
            timespec="seconds"
        )

        signal_date_iso = signal_date.strftime(
            "%Y-%m-%d"
        )

        signal_id = (
            f"{signal_date_iso}_{symbol}"
        )

        portfolio_selected = bool_value(
            trade.get(
                "portfolio_selected",
                True,
            )
        )

        record = {
            "signal_id": signal_id,
            "signal_date": signal_date.strftime(
                "%d%b%Y"
            ).upper(),
            "signal_date_iso": signal_date_iso,
            "recorded_at": recorded_at,
            "symbol": symbol,
            "company": first_valid(
                trade.get("company"),
                final_row.get("company"),
                "",
            ),
            "sector": first_valid(
                trade.get("sector"),
                final_row.get("sector"),
                "UNKNOWN",
            ),
            "industry": first_valid(
                trade.get("industry"),
                final_row.get("industry"),
                "UNKNOWN",
            ),
            "decision": first_valid(
                trade.get("final_decision"),
                final_row.get("final_decision"),
                "",
            ),
            "consensus_decision": first_valid(
                trade.get("consensus_decision"),
                final_row.get(
                    "consensus_decision"
                ),
                "",
            ),
            "entry_action": first_valid(
                trade.get("entry_timing_action"),
                final_row.get(
                    "entry_timing_action"
                ),
                "",
            ),
            "risk_permission": first_valid(
                trade.get("risk_permission"),
                final_row.get("risk_permission"),
                "",
            ),
            "risk_status": first_valid(
                trade.get("risk_status"),
                final_row.get("risk_status"),
                "",
            ),
            "market_mood": first_valid(
                portfolio.get("market_mood"),
                final_row.get("market_mood"),
                "",
            ),
            "market_score": number_value(
                portfolio.get(
                    "market_score",
                    final_row.get(
                        "market_score",
                        0,
                    ),
                )
            ),
            "portfolio_rank": int_value(
                trade.get("rank", 0)
            ),
            "portfolio_selected": portfolio_selected,
            "portfolio_fallback_candidate": bool_value(
                trade.get(
                    "portfolio_fallback_candidate",
                    False,
                )
            ),
            "entry_price": number_value(
                first_valid(
                    trade.get(
                        "adjusted_entry_price"
                    ),
                    trade.get(
                        "suggested_entry_price"
                    ),
                    trade.get("entry_high"),
                    0,
                )
            ),
            "entry_low": number_value(
                trade.get("entry_low", 0)
            ),
            "entry_high": number_value(
                trade.get("entry_high", 0)
            ),
            "stop_loss": number_value(
                trade.get("stop_loss", 0)
            ),
            "target_1": number_value(
                trade.get("target_1", 0)
            ),
            "target_2": number_value(
                trade.get("target_2", 0)
            ),
            "quantity": int_value(
                first_valid(
                    trade.get("final_quantity"),
                    trade.get("quantity"),
                    0,
                )
            ),
            "investment": number_value(
                trade.get("investment", 0)
            ),
            "risk_per_share": number_value(
                trade.get("risk_per_share", 0)
            ),
            "max_loss": number_value(
                trade.get("max_loss", 0)
            ),
            "expected_profit_t1": number_value(
                trade.get(
                    "expected_profit_t1",
                    0,
                )
            ),
            "expected_profit_t2": number_value(
                trade.get(
                    "expected_profit_t2",
                    0,
                )
            ),
            "risk_reward_t1": number_value(
                trade.get("risk_reward_t1", 0)
            ),
            "final_score": number_value(
                first_valid(
                    trade.get("final_score"),
                    final_row.get("final_score"),
                    0,
                )
            ),
            "consensus_score": number_value(
                first_valid(
                    trade.get("consensus_score"),
                    final_row.get(
                        "consensus_score"
                    ),
                    0,
                )
            ),
            "consensus_confidence": number_value(
                first_valid(
                    trade.get(
                        "consensus_confidence"
                    ),
                    final_row.get(
                        "consensus_confidence"
                    ),
                    0,
                )
            ),
            "buy_probability": number_value(
                first_valid(
                    trade.get("buy_probability"),
                    final_row.get(
                        "buy_probability"
                    ),
                    0,
                )
            ),
            "confidence_v3": number_value(
                first_valid(
                    trade.get("confidence_v3"),
                    final_row.get(
                        "confidence_v3"
                    ),
                    0,
                )
            ),
            "portfolio_rank_score": number_value(
                trade.get(
                    "portfolio_rank_score",
                    0,
                )
            ),
            "position_quality_index": number_value(
                trade.get(
                    "position_quality_index",
                    0,
                )
            ),
            "institutional_portfolio_score": number_value(
                trade.get(
                    "institutional_portfolio_score",
                    0,
                )
            ),
            "smart_money_score": number_value(
                first_valid(
                    trade.get("smart_money_score"),
                    final_row.get(
                        "smart_money_score"
                    ),
                    0,
                )
            ),
            "accumulation_score": number_value(
                first_valid(
                    trade.get(
                        "accumulation_score"
                    ),
                    final_row.get(
                        "accumulation_score"
                    ),
                    0,
                )
            ),
            "trade_validation_score": number_value(
                first_valid(
                    trade.get(
                        "trade_validation_score"
                    ),
                    final_row.get(
                        "trade_validation_score"
                    ),
                    0,
                )
            ),
            "entry_timing_score": number_value(
                first_valid(
                    trade.get(
                        "entry_timing_score"
                    ),
                    final_row.get(
                        "entry_timing_score"
                    ),
                    0,
                )
            ),
            "risk_management_score": number_value(
                first_valid(
                    trade.get(
                        "risk_management_score"
                    ),
                    final_row.get(
                        "risk_management_score"
                    ),
                    0,
                )
            ),
            "engine_version": self.VERSION,
            "portfolio_engine_version": first_valid(
                portfolio.get(
                    "engine_version"
                ),
                "",
            ),
            "source_file": str(
                source_file or ""
            ),
            "tracking_status": "OPEN",
            "outcome_status": "PENDING",
            "target_1_hit": False,
            "target_2_hit": False,
            "stop_loss_hit": False,
            "exit_price": 0.0,
            "exit_date": "",
            "holding_days": 0,
            "return_pct": 0.0,
            "return_1d": 0.0,
            "return_2d": 0.0,
            "return_3d": 0.0,
            "return_5d": 0.0,
            "profit_loss": 0.0,
            "max_favorable_excursion_pct": 0.0,
            "max_adverse_excursion_pct": 0.0,
            "last_evaluated_date": "",
        }

        return record

    def merge_signals(
        self,
        history: pd.DataFrame,
        incoming: pd.DataFrame,
    ) -> tuple[pd.DataFrame, int, int]:
        history = self.normalize_history(
            history
        )

        incoming = self.normalize_history(
            incoming
        )

        if history.empty:
            return (
                incoming.reset_index(drop=True),
                len(incoming),
                0,
            )

        saved_count = 0
        updated_count = 0

        history = history.set_index(
            "signal_id",
            drop=False,
        )

        for _, new_row in incoming.iterrows():
            signal_id = str(
                new_row["signal_id"]
            )

            if (
                signal_id in history.index
                and not self.config.allow_duplicate_signal_date
            ):
                old_row = history.loc[
                    signal_id
                ]

                if isinstance(
                    old_row,
                    pd.DataFrame,
                ):
                    old_row = old_row.iloc[-1]

                merged = self.merge_record(
                    old_row.to_dict(),
                    new_row.to_dict(),
                )

                for column, value in merged.items():
                    history.at[
                        signal_id,
                        column,
                    ] = value

                updated_count += 1

            else:
                history = pd.concat(
                    [
                        history.reset_index(
                            drop=True
                        ),
                        pd.DataFrame(
                            [new_row.to_dict()]
                        ),
                    ],
                    ignore_index=True,
                ).set_index(
                    "signal_id",
                    drop=False,
                )

                saved_count += 1

        combined = history.reset_index(
            drop=True
        )

        combined = self.normalize_history(
            combined
        )

        combined = combined.sort_values(
            by=[
                "signal_date_iso",
                "portfolio_rank",
                "symbol",
            ],
            ascending=[
                False,
                True,
                True,
            ],
            kind="stable",
        ).reset_index(drop=True)

        return (
            combined,
            saved_count,
            updated_count,
        )

    def merge_record(
        self,
        old_record: dict,
        new_record: dict,
    ) -> dict:
        merged = old_record.copy()

        protected_outcome_columns = {
            "tracking_status",
            "outcome_status",
            "target_1_hit",
            "target_2_hit",
            "stop_loss_hit",
            "exit_price",
            "exit_date",
            "holding_days",
            "return_pct",
            "return_1d",
            "return_2d",
            "return_3d",
            "return_5d",
            "profit_loss",
            "max_favorable_excursion_pct",
            "max_adverse_excursion_pct",
            "last_evaluated_date",
        }

        for column in SIGNAL_HISTORY_COLUMNS:
            if column in protected_outcome_columns:
                continue

            new_value = new_record.get(
                column
            )

            if is_valid_value(new_value):
                merged[column] = new_value

        return merged

    def normalize_history(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        if df is None or not isinstance(
            df,
            pd.DataFrame,
        ):
            return pd.DataFrame(
                columns=SIGNAL_HISTORY_COLUMNS
            )

        result = remove_duplicate_columns(
            df.copy()
        )

        for column in SIGNAL_HISTORY_COLUMNS:
            if column not in result.columns:
                result[column] = default_for_column(
                    column
                )

        result = result[
            SIGNAL_HISTORY_COLUMNS
        ].copy()

        text_columns = {
            "signal_id",
            "signal_date",
            "signal_date_iso",
            "recorded_at",
            "symbol",
            "company",
            "sector",
            "industry",
            "decision",
            "consensus_decision",
            "entry_action",
            "risk_permission",
            "risk_status",
            "market_mood",
            "engine_version",
            "portfolio_engine_version",
            "source_file",
            "tracking_status",
            "outcome_status",
            "exit_date",
            "last_evaluated_date",
        }

        bool_columns = {
            "portfolio_selected",
            "portfolio_fallback_candidate",
            "target_1_hit",
            "target_2_hit",
            "stop_loss_hit",
        }

        int_columns = {
            "portfolio_rank",
            "quantity",
            "holding_days",
        }

        for column in text_columns:
            result[column] = (
                result[column]
                .fillna("")
                .astype(str)
                .str.strip()
            )

        if "symbol" in result.columns:
            result["symbol"] = (
                result["symbol"]
                .str.upper()
            )

        for column in bool_columns:
            result[column] = result[
                column
            ].apply(bool_value)

        for column in int_columns:
            result[column] = (
                pd.to_numeric(
                    result[column],
                    errors="coerce",
                )
                .fillna(0)
                .astype(int)
            )

        numeric_columns = [
            column
            for column in SIGNAL_HISTORY_COLUMNS
            if column not in text_columns
            and column not in bool_columns
            and column not in int_columns
        ]

        for column in numeric_columns:
            result[column] = (
                pd.to_numeric(
                    result[column],
                    errors="coerce",
                )
                .fillna(0.0)
                .astype(float)
            )

        if not result.empty:
            result = result[
                result["signal_id"] != ""
            ].copy()

            result = result.drop_duplicates(
                subset=["signal_id"],
                keep="last",
            )

        return result.reset_index(
            drop=True
        )


def record_signals_v1(
    portfolio: dict,
    signal_date: Any,
    source_file: str = "",
    final_df: pd.DataFrame | None = None,
    history_file: str | Path = SIGNAL_HISTORY_FILE,
    save_only_selected: bool = True,
) -> dict:
    tracker = SignalTrackerV1(
        history_file=history_file,
        save_only_selected=save_only_selected,
    )

    return tracker.record_portfolio_signals(
        portfolio=portfolio,
        signal_date=signal_date,
        source_file=source_file,
        final_df=final_df,
    )


def parse_signal_date(
    value: Any,
) -> pd.Timestamp | None:
    if value is None:
        return None

    if isinstance(value, pd.Timestamp):
        return value.normalize()

    formats = [
        "%d%b%Y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
    ]

    text = str(value).strip()

    for date_format in formats:
        parsed = pd.to_datetime(
            text,
            format=date_format,
            errors="coerce",
        )

        if pd.notna(parsed):
            return parsed.normalize()

    parsed = pd.to_datetime(
        text,
        errors="coerce",
    )

    if pd.isna(parsed):
        return None

    return parsed.normalize()


def default_for_column(
    column: str,
) -> Any:
    if column in {
        "portfolio_selected",
        "portfolio_fallback_candidate",
        "target_1_hit",
        "target_2_hit",
        "stop_loss_hit",
    }:
        return False

    if column in {
        "portfolio_rank",
        "quantity",
        "holding_days",
    }:
        return 0

    if column in {
        "signal_id",
        "signal_date",
        "signal_date_iso",
        "recorded_at",
        "symbol",
        "company",
        "sector",
        "industry",
        "decision",
        "consensus_decision",
        "entry_action",
        "risk_permission",
        "risk_status",
        "market_mood",
        "engine_version",
        "portfolio_engine_version",
        "source_file",
        "tracking_status",
        "outcome_status",
        "exit_date",
        "last_evaluated_date",
    }:
        return ""

    return 0.0


def first_valid(
    *values: Any,
) -> Any:
    for value in values:
        if is_valid_value(value):
            return value

    return ""


def is_valid_value(
    value: Any,
) -> bool:
    if value is None:
        return False

    try:
        if pd.isna(value):
            return False
    except Exception:
        pass

    text = str(value).strip()

    if text.upper() in {
        "",
        "NAN",
        "NONE",
        "NULL",
    }:
        return False

    return True


def number_value(
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


def int_value(
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


def bool_value(
    value: Any,
) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    return str(value).strip().lower() in {
        "true",
        "1",
        "yes",
        "y",
        "selected",
    }


def text_value(
    value: Any,
    default: str = "",
) -> str:
    if not is_valid_value(value):
        return str(default).strip().upper()

    return str(value).strip().upper()


def remove_duplicate_columns(
    df: pd.DataFrame,
) -> pd.DataFrame:
    if df is None or not hasattr(
        df,
        "columns",
    ):
        return pd.DataFrame()

    return df.loc[
        :,
        ~df.columns.duplicated(),
    ].copy()