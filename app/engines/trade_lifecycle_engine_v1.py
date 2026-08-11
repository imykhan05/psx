from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class TradeLifecycleConfigV1:
    """
    Configuration for Trade Lifecycle Engine V1.0.
    """

    data_folder: str = "database/portfolio"
    open_positions_file: str = "open_positions.csv"
    closed_positions_file: str = "closed_positions.csv"
    trade_events_file: str = "trade_events.csv"
    pending_entries_file: str = "pending_entries.csv"
    default_max_holding_days: int = 5


class TradeLifecycleEngineV1:
    """
    Trade Lifecycle Engine V1.0

    Purpose:
    - Persist portfolio recommendations as pending entries.
    - Record actual manual buys.
    - Track open positions using current market data.
    - Record partial exits and full exits.
    - Maintain open positions, closed positions and event history.
    - Enrich scanner output with actual lifecycle status.

    Lifecycle states:
    - READY TO BUY
    - OPEN
    - PARTIAL EXIT
    - CLOSED
    - CANCELLED
    """

    VERSION = "trade_lifecycle_engine_v1_0"

    OPEN_STATES = {
        "OPEN",
        "PARTIAL EXIT",
    }

    CLOSED_STATES = {
        "CLOSED",
        "CANCELLED",
    }

    PENDING_STATES = {
        "READY TO BUY",
        "PENDING ENTRY",
    }

    OPEN_POSITION_COLUMNS = [
        "trade_id",
        "symbol",
        "company",
        "sector",
        "industry",
        "signal_date",
        "entry_date",
        "entry_time",
        "actual_entry_price",
        "original_quantity",
        "remaining_quantity",
        "average_cost",
        "initial_stop_loss",
        "current_stop_loss",
        "target_1",
        "target_2",
        "highest_price_since_entry",
        "lowest_price_since_entry",
        "current_price",
        "unrealized_profit_loss",
        "unrealized_profit_loss_pct",
        "realized_profit_loss",
        "partial_profit_booked",
        "holding_days",
        "position_status",
        "last_exit_action",
        "last_exit_reason",
        "last_updated_at",
        "engine_version",
    ]

    CLOSED_POSITION_COLUMNS = [
        "trade_id",
        "symbol",
        "company",
        "sector",
        "industry",
        "signal_date",
        "entry_date",
        "entry_time",
        "exit_date",
        "exit_time",
        "actual_entry_price",
        "average_cost",
        "original_quantity",
        "exit_quantity",
        "final_exit_price",
        "initial_stop_loss",
        "final_stop_loss",
        "target_1",
        "target_2",
        "highest_price_since_entry",
        "lowest_price_since_entry",
        "realized_profit_loss",
        "realized_profit_loss_pct",
        "holding_days",
        "close_reason",
        "position_status",
        "closed_at",
        "engine_version",
    ]

    EVENT_COLUMNS = [
        "event_id",
        "trade_id",
        "event_time",
        "event_type",
        "symbol",
        "quantity",
        "price",
        "profit_loss",
        "profit_loss_pct",
        "notes",
        "engine_version",
    ]

    PENDING_ENTRY_COLUMNS = [
        "symbol",
        "company",
        "sector",
        "industry",
        "signal_date",
        "suggested_entry_price",
        "entry_low",
        "entry_high",
        "stop_loss",
        "target_1",
        "target_2",
        "recommended_quantity",
        "recommended_investment",
        "risk_permission",
        "entry_timing_action",
        "position_status",
        "last_updated_at",
        "engine_version",
    ]

    def __init__(
        self,
        data_folder: str = "database/portfolio",
        open_positions_file: str = "open_positions.csv",
        closed_positions_file: str = "closed_positions.csv",
        trade_events_file: str = "trade_events.csv",
        pending_entries_file: str = "pending_entries.csv",
        default_max_holding_days: int = 5,
    ):
        self.config = TradeLifecycleConfigV1(
            data_folder=data_folder,
            open_positions_file=open_positions_file,
            closed_positions_file=closed_positions_file,
            trade_events_file=trade_events_file,
            pending_entries_file=pending_entries_file,
            default_max_holding_days=int(default_max_holding_days),
        )

        self.data_folder = Path(self.config.data_folder)
        self.open_positions_path = (
            self.data_folder / self.config.open_positions_file
        )
        self.closed_positions_path = (
            self.data_folder / self.config.closed_positions_file
        )
        self.trade_events_path = (
            self.data_folder / self.config.trade_events_file
        )
        self.pending_entries_path = (
            self.data_folder / self.config.pending_entries_file
        )

        self.data_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._ensure_storage()

    # ---------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------

    def sync_pending_entries(
        self,
        recommendations_df: pd.DataFrame,
    ) -> dict:
        """
        Persist current portfolio-selected READY TO BUY candidates.
        Existing pending symbols are updated instead of duplicated.
        """
        if (
            recommendations_df is None
            or not isinstance(recommendations_df, pd.DataFrame)
            or recommendations_df.empty
        ):
            return self._summary(
                status="success",
                reason="No recommendations available",
                pending_entries=0,
            )

        data = recommendations_df.copy()
        data = remove_duplicate_columns(data)

        if "portfolio_selected" not in data.columns:
            return self._summary(
                status="success",
                reason="No portfolio_selected column available",
                pending_entries=0,
            )

        selected = data[
            data["portfolio_selected"]
            .fillna(False)
            .apply(bool_value)
        ].copy()

        if selected.empty:
            self._save_dataframe(
                pd.DataFrame(
                    columns=self.PENDING_ENTRY_COLUMNS
                ),
                self.pending_entries_path,
                self.PENDING_ENTRY_COLUMNS,
            )

            return self._summary(
                status="success",
                reason="No current READY TO BUY candidates",
                pending_entries=0,
            )

        open_positions = self.load_open_positions()
        open_symbols = set(
            open_positions["symbol"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.strip()
            .tolist()
        )

        pending_rows = []

        for _, row in selected.iterrows():
            symbol = text_value(
                row.get("symbol", "")
            )

            if not symbol or symbol in open_symbols:
                continue

            pending_rows.append({
                "symbol": symbol,
                "company": clean_text(
                    row.get("company", "")
                ),
                "sector": clean_text(
                    row.get("sector", "")
                ),
                "industry": clean_text(
                    row.get("industry", "")
                ),
                "signal_date": clean_text(
                    row.get("date", "")
                ),
                "suggested_entry_price": positive_or_zero(
                    first_numeric(
                        row,
                        [
                            "adjusted_entry_price",
                            "suggested_entry_price",
                            "entry_price",
                            "entry_high",
                            "close",
                        ],
                    )
                ),
                "entry_low": positive_or_zero(
                    first_numeric(
                        row,
                        [
                            "entry_low",
                            "adjusted_entry_price",
                            "close",
                        ],
                    )
                ),
                "entry_high": positive_or_zero(
                    first_numeric(
                        row,
                        [
                            "entry_high",
                            "adjusted_entry_price",
                            "close",
                        ],
                    )
                ),
                "stop_loss": positive_or_zero(
                    first_numeric(
                        row,
                        [
                            "stop_loss",
                        ],
                    )
                ),
                "target_1": positive_or_zero(
                    first_numeric(
                        row,
                        [
                            "target_1",
                        ],
                    )
                ),
                "target_2": positive_or_zero(
                    first_numeric(
                        row,
                        [
                            "target_2",
                        ],
                    )
                ),
                "recommended_quantity": int(
                    max(
                        first_numeric(
                            row,
                            [
                                "portfolio_quantity",
                                "quantity",
                            ],
                        ),
                        0,
                    )
                ),
                "recommended_investment": positive_or_zero(
                    first_numeric(
                        row,
                        [
                            "portfolio_investment",
                            "investment",
                            "recommended_capital",
                        ],
                    )
                ),
                "risk_permission": text_value(
                    row.get("risk_permission", "")
                ),
                "entry_timing_action": text_value(
                    row.get("entry_timing_action", "")
                ),
                "position_status": "READY TO BUY",
                "last_updated_at": now_iso(),
                "engine_version": self.VERSION,
            })

        pending_df = pd.DataFrame(
            pending_rows,
            columns=self.PENDING_ENTRY_COLUMNS,
        )

        self._save_dataframe(
            pending_df,
            self.pending_entries_path,
            self.PENDING_ENTRY_COLUMNS,
        )

        return self._summary(
            status="success",
            reason="Pending entries synchronized",
            pending_entries=len(pending_df),
        )

    def open_position(
        self,
        symbol: str,
        actual_entry_price: float,
        quantity: int,
        entry_date: str | None = None,
        entry_time: str | None = None,
        stop_loss: float | None = None,
        target_1: float | None = None,
        target_2: float | None = None,
        notes: str = "",
    ) -> dict:
        """
        Convert a pending recommendation into an actual OPEN position.
        """
        symbol = text_value(symbol)
        actual_entry_price = positive_or_zero(
            actual_entry_price
        )
        quantity = int(
            max(
                quantity,
                0,
            )
        )

        if not symbol:
            raise ValueError(
                "Symbol is required"
            )

        if actual_entry_price <= 0:
            raise ValueError(
                "Actual entry price must be greater than zero"
            )

        if quantity <= 0:
            raise ValueError(
                "Quantity must be greater than zero"
            )

        open_positions = self.load_open_positions()

        if not open_positions.empty:
            duplicate = open_positions[
                open_positions["symbol"] == symbol
            ]

            if not duplicate.empty:
                raise ValueError(
                    f"Open position already exists for {symbol}"
                )

        pending = self.load_pending_entries()
        pending_row = None

        if not pending.empty:
            match = pending[
                pending["symbol"] == symbol
            ]

            if not match.empty:
                pending_row = match.iloc[0]

        entry_date = (
            entry_date
            or datetime.now().strftime("%Y-%m-%d")
        )
        entry_time = (
            entry_time
            or datetime.now().strftime("%H:%M:%S")
        )

        resolved_stop = positive_or_zero(
            stop_loss
            if stop_loss is not None
            else value_from_row(
                pending_row,
                "stop_loss",
                actual_entry_price * 0.94,
            )
        )

        resolved_target_1 = positive_or_zero(
            target_1
            if target_1 is not None
            else value_from_row(
                pending_row,
                "target_1",
                actual_entry_price * 1.07,
            )
        )

        resolved_target_2 = positive_or_zero(
            target_2
            if target_2 is not None
            else value_from_row(
                pending_row,
                "target_2",
                actual_entry_price * 1.14,
            )
        )

        trade_id = make_trade_id(
            symbol
        )

        row = {
            "trade_id": trade_id,
            "symbol": symbol,
            "company": clean_text(
                value_from_row(
                    pending_row,
                    "company",
                    "",
                )
            ),
            "sector": clean_text(
                value_from_row(
                    pending_row,
                    "sector",
                    "",
                )
            ),
            "industry": clean_text(
                value_from_row(
                    pending_row,
                    "industry",
                    "",
                )
            ),
            "signal_date": clean_text(
                value_from_row(
                    pending_row,
                    "signal_date",
                    "",
                )
            ),
            "entry_date": entry_date,
            "entry_time": entry_time,
            "actual_entry_price": actual_entry_price,
            "original_quantity": quantity,
            "remaining_quantity": quantity,
            "average_cost": actual_entry_price,
            "initial_stop_loss": resolved_stop,
            "current_stop_loss": resolved_stop,
            "target_1": resolved_target_1,
            "target_2": resolved_target_2,
            "highest_price_since_entry": actual_entry_price,
            "lowest_price_since_entry": actual_entry_price,
            "current_price": actual_entry_price,
            "unrealized_profit_loss": 0.0,
            "unrealized_profit_loss_pct": 0.0,
            "realized_profit_loss": 0.0,
            "partial_profit_booked": False,
            "holding_days": 0,
            "position_status": "OPEN",
            "last_exit_action": "",
            "last_exit_reason": "",
            "last_updated_at": now_iso(),
            "engine_version": self.VERSION,
        }

        open_positions = pd.concat(
            [
                open_positions,
                pd.DataFrame(
                    [row]
                ),
            ],
            ignore_index=True,
        )

        self._save_dataframe(
            open_positions,
            self.open_positions_path,
            self.OPEN_POSITION_COLUMNS,
        )

        if not pending.empty:
            pending = pending[
                pending["symbol"] != symbol
            ].copy()

            self._save_dataframe(
                pending,
                self.pending_entries_path,
                self.PENDING_ENTRY_COLUMNS,
            )

        self._append_event(
            trade_id=trade_id,
            event_type="OPEN",
            symbol=symbol,
            quantity=quantity,
            price=actual_entry_price,
            profit_loss=0.0,
            profit_loss_pct=0.0,
            notes=notes or "Position opened",
        )

        return {
            "status": "success",
            "engine_version": self.VERSION,
            "trade_id": trade_id,
            "symbol": symbol,
            "position_status": "OPEN",
            "actual_entry_price": actual_entry_price,
            "quantity": quantity,
            "stop_loss": resolved_stop,
            "target_1": resolved_target_1,
            "target_2": resolved_target_2,
            "reason": "Position opened successfully",
        }

    def update_positions(
        self,
        market_df: pd.DataFrame,
    ) -> dict:
        """
        Update all open positions using latest market data.
        """
        open_positions = self.load_open_positions()

        if open_positions.empty:
            return self._summary(
                status="success",
                reason="No open positions to update",
                open_positions=0,
            )

        if (
            market_df is None
            or not isinstance(market_df, pd.DataFrame)
            or market_df.empty
            or "symbol" not in market_df.columns
        ):
            return self._summary(
                status="failed",
                reason="Valid market dataframe is required",
                open_positions=len(open_positions),
            )

        market = market_df.copy()
        market["symbol"] = (
            market["symbol"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.strip()
        )

        market = market.drop_duplicates(
            subset=["symbol"],
            keep="last",
        )

        market_map = market.set_index(
            "symbol"
        )

        updated_count = 0

        for index, position in open_positions.iterrows():
            symbol = text_value(
                position.get("symbol", "")
            )

            if symbol not in market_map.index:
                continue

            market_row = market_map.loc[
                symbol
            ]

            if isinstance(
                market_row,
                pd.DataFrame,
            ):
                market_row = market_row.iloc[-1]

            current_price = positive_or_zero(
                first_numeric(
                    market_row,
                    [
                        "close",
                        "current_price",
                    ],
                )
            )

            if current_price <= 0:
                continue

            entry_price = positive_or_zero(
                position.get(
                    "average_cost",
                    position.get(
                        "actual_entry_price",
                        0,
                    ),
                )
            )

            remaining_quantity = int(
                max(
                    numeric_value(
                        position.get(
                            "remaining_quantity",
                            0,
                        )
                    ),
                    0,
                )
            )

            highest = max(
                positive_or_zero(
                    position.get(
                        "highest_price_since_entry",
                        entry_price,
                    )
                ),
                current_price,
            )

            previous_low = positive_or_zero(
                position.get(
                    "lowest_price_since_entry",
                    entry_price,
                )
            )

            lowest = (
                min(
                    previous_low,
                    current_price,
                )
                if previous_low > 0
                else current_price
            )

            unrealized = (
                current_price - entry_price
            ) * remaining_quantity

            unrealized_pct = (
                (
                    current_price - entry_price
                )
                / entry_price
                * 100
                if entry_price > 0
                else 0.0
            )

            holding_days = calculate_holding_days(
                position.get(
                    "entry_date",
                    "",
                ),
                market_row.get(
                    "date",
                    None,
                ),
            )

            open_positions.at[
                index,
                "current_price",
            ] = current_price

            open_positions.at[
                index,
                "highest_price_since_entry",
            ] = highest

            open_positions.at[
                index,
                "lowest_price_since_entry",
            ] = lowest

            open_positions.at[
                index,
                "unrealized_profit_loss",
            ] = round(
                unrealized,
                2,
            )

            open_positions.at[
                index,
                "unrealized_profit_loss_pct",
            ] = round(
                unrealized_pct,
                2,
            )

            open_positions.at[
                index,
                "holding_days",
            ] = holding_days

            open_positions.at[
                index,
                "last_updated_at",
            ] = now_iso()

            updated_count += 1

        self._save_dataframe(
            open_positions,
            self.open_positions_path,
            self.OPEN_POSITION_COLUMNS,
        )

        return self._summary(
            status="success",
            reason="Open positions updated",
            open_positions=len(open_positions),
            updated_positions=updated_count,
        )

    def record_partial_exit(
        self,
        symbol: str,
        exit_quantity: int,
        exit_price: float,
        exit_date: str | None = None,
        exit_time: str | None = None,
        reason: str = "PARTIAL PROFIT",
    ) -> dict:
        """
        Record a partial sale and keep the remaining position open.
        """
        symbol = text_value(symbol)
        exit_quantity = int(
            max(
                exit_quantity,
                0,
            )
        )
        exit_price = positive_or_zero(
            exit_price
        )

        open_positions = self.load_open_positions()
        match = open_positions[
            open_positions["symbol"] == symbol
        ]

        if match.empty:
            raise ValueError(
                f"No open position found for {symbol}"
            )

        index = match.index[0]
        position = open_positions.loc[index]

        remaining_quantity = int(
            max(
                numeric_value(
                    position.get(
                        "remaining_quantity",
                        0,
                    )
                ),
                0,
            )
        )

        if exit_quantity <= 0:
            raise ValueError(
                "Exit quantity must be greater than zero"
            )

        if exit_quantity >= remaining_quantity:
            raise ValueError(
                "Use close_position() when exiting the full remaining quantity"
            )

        if exit_price <= 0:
            raise ValueError(
                "Exit price must be greater than zero"
            )

        average_cost = positive_or_zero(
            position.get(
                "average_cost",
                position.get(
                    "actual_entry_price",
                    0,
                ),
            )
        )

        realized = (
            exit_price - average_cost
        ) * exit_quantity

        realized_pct = (
            (
                exit_price - average_cost
            )
            / average_cost
            * 100
            if average_cost > 0
            else 0.0
        )

        new_remaining = (
            remaining_quantity - exit_quantity
        )

        previous_realized = numeric_value(
            position.get(
                "realized_profit_loss",
                0,
            )
        )

        open_positions.at[
            index,
            "remaining_quantity",
        ] = new_remaining

        open_positions.at[
            index,
            "realized_profit_loss",
        ] = round(
            previous_realized + realized,
            2,
        )

        open_positions.at[
            index,
            "partial_profit_booked",
        ] = True

        open_positions.at[
            index,
            "position_status",
        ] = "PARTIAL EXIT"

        open_positions.at[
            index,
            "last_exit_action",
        ] = "PARTIAL PROFIT"

        open_positions.at[
            index,
            "last_exit_reason",
        ] = reason

        open_positions.at[
            index,
            "last_updated_at",
        ] = now_iso()

        self._save_dataframe(
            open_positions,
            self.open_positions_path,
            self.OPEN_POSITION_COLUMNS,
        )

        self._append_event(
            trade_id=clean_text(
                position.get(
                    "trade_id",
                    "",
                )
            ),
            event_type="PARTIAL EXIT",
            symbol=symbol,
            quantity=exit_quantity,
            price=exit_price,
            profit_loss=realized,
            profit_loss_pct=realized_pct,
            notes=reason,
            event_date=exit_date,
            event_time=exit_time,
        )

        return {
            "status": "success",
            "engine_version": self.VERSION,
            "symbol": symbol,
            "position_status": "PARTIAL EXIT",
            "exit_quantity": exit_quantity,
            "remaining_quantity": new_remaining,
            "exit_price": exit_price,
            "realized_profit_loss": round(
                realized,
                2,
            ),
            "realized_profit_loss_pct": round(
                realized_pct,
                2,
            ),
            "reason": "Partial exit recorded successfully",
        }

    def close_position(
        self,
        symbol: str,
        exit_price: float,
        exit_date: str | None = None,
        exit_time: str | None = None,
        reason: str = "FULL EXIT",
    ) -> dict:
        """
        Close the entire remaining position and move it to closed history.
        """
        symbol = text_value(symbol)
        exit_price = positive_or_zero(
            exit_price
        )

        if exit_price <= 0:
            raise ValueError(
                "Exit price must be greater than zero"
            )

        open_positions = self.load_open_positions()
        match = open_positions[
            open_positions["symbol"] == symbol
        ]

        if match.empty:
            raise ValueError(
                f"No open position found for {symbol}"
            )

        index = match.index[0]
        position = open_positions.loc[index]

        remaining_quantity = int(
            max(
                numeric_value(
                    position.get(
                        "remaining_quantity",
                        0,
                    )
                ),
                0,
            )
        )

        average_cost = positive_or_zero(
            position.get(
                "average_cost",
                position.get(
                    "actual_entry_price",
                    0,
                ),
            )
        )

        realized_on_exit = (
            exit_price - average_cost
        ) * remaining_quantity

        previous_realized = numeric_value(
            position.get(
                "realized_profit_loss",
                0,
            )
        )

        total_realized = (
            previous_realized
            + realized_on_exit
        )

        original_quantity = int(
            max(
                numeric_value(
                    position.get(
                        "original_quantity",
                        remaining_quantity,
                    )
                ),
                0,
            )
        )

        invested_value = (
            average_cost
            * original_quantity
        )

        total_realized_pct = (
            total_realized
            / invested_value
            * 100
            if invested_value > 0
            else 0.0
        )

        exit_date = (
            exit_date
            or datetime.now().strftime("%Y-%m-%d")
        )
        exit_time = (
            exit_time
            or datetime.now().strftime("%H:%M:%S")
        )

        closed_row = {
            "trade_id": clean_text(
                position.get(
                    "trade_id",
                    "",
                )
            ),
            "symbol": symbol,
            "company": clean_text(
                position.get(
                    "company",
                    "",
                )
            ),
            "sector": clean_text(
                position.get(
                    "sector",
                    "",
                )
            ),
            "industry": clean_text(
                position.get(
                    "industry",
                    "",
                )
            ),
            "signal_date": clean_text(
                position.get(
                    "signal_date",
                    "",
                )
            ),
            "entry_date": clean_text(
                position.get(
                    "entry_date",
                    "",
                )
            ),
            "entry_time": clean_text(
                position.get(
                    "entry_time",
                    "",
                )
            ),
            "exit_date": exit_date,
            "exit_time": exit_time,
            "actual_entry_price": average_cost,
            "average_cost": average_cost,
            "original_quantity": original_quantity,
            "exit_quantity": remaining_quantity,
            "final_exit_price": exit_price,
            "initial_stop_loss": positive_or_zero(
                position.get(
                    "initial_stop_loss",
                    0,
                )
            ),
            "final_stop_loss": positive_or_zero(
                position.get(
                    "current_stop_loss",
                    0,
                )
            ),
            "target_1": positive_or_zero(
                position.get(
                    "target_1",
                    0,
                )
            ),
            "target_2": positive_or_zero(
                position.get(
                    "target_2",
                    0,
                )
            ),
            "highest_price_since_entry": positive_or_zero(
                position.get(
                    "highest_price_since_entry",
                    0,
                )
            ),
            "lowest_price_since_entry": positive_or_zero(
                position.get(
                    "lowest_price_since_entry",
                    0,
                )
            ),
            "realized_profit_loss": round(
                total_realized,
                2,
            ),
            "realized_profit_loss_pct": round(
                total_realized_pct,
                2,
            ),
            "holding_days": int(
                max(
                    numeric_value(
                        position.get(
                            "holding_days",
                            0,
                        )
                    ),
                    0,
                )
            ),
            "close_reason": reason,
            "position_status": "CLOSED",
            "closed_at": now_iso(),
            "engine_version": self.VERSION,
        }

        closed_positions = self.load_closed_positions()
        closed_positions = pd.concat(
            [
                closed_positions,
                pd.DataFrame(
                    [closed_row]
                ),
            ],
            ignore_index=True,
        )

        self._save_dataframe(
            closed_positions,
            self.closed_positions_path,
            self.CLOSED_POSITION_COLUMNS,
        )

        open_positions = open_positions.drop(
            index=index
        ).reset_index(
            drop=True
        )

        self._save_dataframe(
            open_positions,
            self.open_positions_path,
            self.OPEN_POSITION_COLUMNS,
        )

        self._append_event(
            trade_id=closed_row["trade_id"],
            event_type="FULL EXIT",
            symbol=symbol,
            quantity=remaining_quantity,
            price=exit_price,
            profit_loss=realized_on_exit,
            profit_loss_pct=(
                (
                    exit_price - average_cost
                )
                / average_cost
                * 100
                if average_cost > 0
                else 0.0
            ),
            notes=reason,
            event_date=exit_date,
            event_time=exit_time,
        )

        return {
            "status": "success",
            "engine_version": self.VERSION,
            "symbol": symbol,
            "position_status": "CLOSED",
            "final_exit_price": exit_price,
            "realized_profit_loss": round(
                total_realized,
                2,
            ),
            "realized_profit_loss_pct": round(
                total_realized_pct,
                2,
            ),
            "reason": "Position closed successfully",
        }

    def cancel_pending_entry(
        self,
        symbol: str,
        reason: str = "ENTRY CANCELLED",
    ) -> dict:
        """
        Remove a READY TO BUY candidate without opening a position.
        """
        symbol = text_value(symbol)

        pending = self.load_pending_entries()

        if pending.empty:
            return {
                "status": "success",
                "engine_version": self.VERSION,
                "symbol": symbol,
                "reason": "No pending entry exists",
            }

        exists = (
            pending["symbol"] == symbol
        ).any()

        pending = pending[
            pending["symbol"] != symbol
        ].copy()

        self._save_dataframe(
            pending,
            self.pending_entries_path,
            self.PENDING_ENTRY_COLUMNS,
        )

        if exists:
            self._append_event(
                trade_id="",
                event_type="CANCELLED",
                symbol=symbol,
                quantity=0,
                price=0.0,
                profit_loss=0.0,
                profit_loss_pct=0.0,
                notes=reason,
            )

        return {
            "status": "success",
            "engine_version": self.VERSION,
            "symbol": symbol,
            "reason": (
                "Pending entry cancelled"
                if exists
                else "Pending entry not found"
            ),
        }

    def enrich_recommendations(
        self,
        recommendations_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Merge actual lifecycle information into scanner recommendations.
        """
        if (
            recommendations_df is None
            or not isinstance(recommendations_df, pd.DataFrame)
        ):
            return pd.DataFrame()

        result = remove_duplicate_columns(
            recommendations_df.copy()
        )

        if result.empty:
            return result

        if "symbol" not in result.columns:
            result["symbol"] = ""

        result["symbol"] = (
            result["symbol"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.strip()
        )

        open_positions = self.load_open_positions()
        pending_entries = self.load_pending_entries()

        lifecycle_columns = {
            "trade_id": "",
            "lifecycle_status": "",
            "actual_entry_price": 0.0,
            "actual_quantity": 0,
            "open_quantity": 0,
            "remaining_quantity": 0,
            "average_cost": 0.0,
            "current_stop_loss": 0.0,
            "highest_price_since_entry": 0.0,
            "lowest_price_since_entry": 0.0,
            "realized_profit_loss": 0.0,
            "unrealized_profit_loss": 0.0,
            "unrealized_profit_loss_pct": 0.0,
            "holding_days_numeric": 0,
            "partial_profit_booked": False,
        }

        for column, default in lifecycle_columns.items():
            if column not in result.columns:
                result[column] = default

        open_map = {}

        for _, row in open_positions.iterrows():
            open_map[
                text_value(
                    row.get(
                        "symbol",
                        "",
                    )
                )
            ] = row

        pending_symbols = set(
            pending_entries["symbol"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.strip()
            .tolist()
        )

        for index, row in result.iterrows():
            symbol = text_value(
                row.get(
                    "symbol",
                    "",
                )
            )

            if symbol in open_map:
                position = open_map[symbol]

                result.at[
                    index,
                    "trade_id",
                ] = clean_text(
                    position.get(
                        "trade_id",
                        "",
                    )
                )

                result.at[
                    index,
                    "lifecycle_status",
                ] = text_value(
                    position.get(
                        "position_status",
                        "OPEN",
                    )
                )

                result.at[
                    index,
                    "actual_entry_price",
                ] = positive_or_zero(
                    position.get(
                        "actual_entry_price",
                        0,
                    )
                )

                result.at[
                    index,
                    "actual_quantity",
                ] = int(
                    max(
                        numeric_value(
                            position.get(
                                "original_quantity",
                                0,
                            )
                        ),
                        0,
                    )
                )

                result.at[
                    index,
                    "open_quantity",
                ] = int(
                    max(
                        numeric_value(
                            position.get(
                                "remaining_quantity",
                                0,
                            )
                        ),
                        0,
                    )
                )

                result.at[
                    index,
                    "remaining_quantity",
                ] = int(
                    max(
                        numeric_value(
                            position.get(
                                "remaining_quantity",
                                0,
                            )
                        ),
                        0,
                    )
                )

                result.at[
                    index,
                    "average_cost",
                ] = positive_or_zero(
                    position.get(
                        "average_cost",
                        0,
                    )
                )

                result.at[
                    index,
                    "current_stop_loss",
                ] = positive_or_zero(
                    position.get(
                        "current_stop_loss",
                        0,
                    )
                )

                result.at[
                    index,
                    "highest_price_since_entry",
                ] = positive_or_zero(
                    position.get(
                        "highest_price_since_entry",
                        0,
                    )
                )

                result.at[
                    index,
                    "lowest_price_since_entry",
                ] = positive_or_zero(
                    position.get(
                        "lowest_price_since_entry",
                        0,
                    )
                )

                result.at[
                    index,
                    "realized_profit_loss",
                ] = numeric_value(
                    position.get(
                        "realized_profit_loss",
                        0,
                    )
                )

                result.at[
                    index,
                    "unrealized_profit_loss",
                ] = numeric_value(
                    position.get(
                        "unrealized_profit_loss",
                        0,
                    )
                )

                result.at[
                    index,
                    "unrealized_profit_loss_pct",
                ] = numeric_value(
                    position.get(
                        "unrealized_profit_loss_pct",
                        0,
                    )
                )

                result.at[
                    index,
                    "holding_days_numeric",
                ] = int(
                    max(
                        numeric_value(
                            position.get(
                                "holding_days",
                                0,
                            )
                        ),
                        0,
                    )
                )

                result.at[
                    index,
                    "partial_profit_booked",
                ] = bool_value(
                    position.get(
                        "partial_profit_booked",
                        False,
                    )
                )

            elif symbol in pending_symbols:
                result.at[
                    index,
                    "lifecycle_status",
                ] = "READY TO BUY"

            elif not clean_text(
                result.at[
                    index,
                    "lifecycle_status",
                ]
            ):
                result.at[
                    index,
                    "lifecycle_status",
                ] = "NO POSITION"

        return result

    def dashboard_summary(
        self,
    ) -> dict:
        open_positions = self.load_open_positions()
        closed_positions = self.load_closed_positions()
        pending_entries = self.load_pending_entries()
        events = self.load_trade_events()

        open_value = 0.0
        unrealized = 0.0
        realized_open = 0.0

        if not open_positions.empty:
            open_value = float(
                (
                    pd.to_numeric(
                        open_positions["current_price"],
                        errors="coerce",
                    ).fillna(0)
                    * pd.to_numeric(
                        open_positions["remaining_quantity"],
                        errors="coerce",
                    ).fillna(0)
                ).sum()
            )

            unrealized = float(
                pd.to_numeric(
                    open_positions["unrealized_profit_loss"],
                    errors="coerce",
                ).fillna(0).sum()
            )

            realized_open = float(
                pd.to_numeric(
                    open_positions["realized_profit_loss"],
                    errors="coerce",
                ).fillna(0).sum()
            )

        realized_closed = 0.0

        if not closed_positions.empty:
            realized_closed = float(
                pd.to_numeric(
                    closed_positions["realized_profit_loss"],
                    errors="coerce",
                ).fillna(0).sum()
            )

        return {
            "status": "success",
            "engine_version": self.VERSION,
            "pending_entries": len(
                pending_entries
            ),
            "open_positions": len(
                open_positions
            ),
            "closed_positions": len(
                closed_positions
            ),
            "trade_events": len(
                events
            ),
            "open_market_value": round(
                open_value,
                2,
            ),
            "unrealized_profit_loss": round(
                unrealized,
                2,
            ),
            "realized_profit_loss_open_positions": round(
                realized_open,
                2,
            ),
            "realized_profit_loss_closed_positions": round(
                realized_closed,
                2,
            ),
            "total_realized_profit_loss": round(
                realized_open
                + realized_closed,
                2,
            ),
            "open_positions_file": str(
                self.open_positions_path
            ),
            "closed_positions_file": str(
                self.closed_positions_path
            ),
            "pending_entries_file": str(
                self.pending_entries_path
            ),
            "trade_events_file": str(
                self.trade_events_path
            ),
        }

    # ---------------------------------------------------------
    # LOADERS
    # ---------------------------------------------------------

    def load_open_positions(
        self,
    ) -> pd.DataFrame:
        return self._load_dataframe(
            self.open_positions_path,
            self.OPEN_POSITION_COLUMNS,
        )

    def load_closed_positions(
        self,
    ) -> pd.DataFrame:
        return self._load_dataframe(
            self.closed_positions_path,
            self.CLOSED_POSITION_COLUMNS,
        )

    def load_trade_events(
        self,
    ) -> pd.DataFrame:
        return self._load_dataframe(
            self.trade_events_path,
            self.EVENT_COLUMNS,
        )

    def load_pending_entries(
        self,
    ) -> pd.DataFrame:
        return self._load_dataframe(
            self.pending_entries_path,
            self.PENDING_ENTRY_COLUMNS,
        )

    # ---------------------------------------------------------
    # INTERNAL HELPERS
    # ---------------------------------------------------------

    def _ensure_storage(
        self,
    ) -> None:
        self._save_dataframe(
            self.load_open_positions(),
            self.open_positions_path,
            self.OPEN_POSITION_COLUMNS,
        )

        self._save_dataframe(
            self.load_closed_positions(),
            self.closed_positions_path,
            self.CLOSED_POSITION_COLUMNS,
        )

        self._save_dataframe(
            self.load_trade_events(),
            self.trade_events_path,
            self.EVENT_COLUMNS,
        )

        self._save_dataframe(
            self.load_pending_entries(),
            self.pending_entries_path,
            self.PENDING_ENTRY_COLUMNS,
        )

    def _load_dataframe(
        self,
        path: Path,
        columns: list[str],
    ) -> pd.DataFrame:
        if (
            not path.exists()
            or path.stat().st_size == 0
        ):
            return pd.DataFrame(
                columns=columns
            )

        try:
            data = pd.read_csv(
                path
            )
        except (
            pd.errors.EmptyDataError,
            UnicodeDecodeError,
        ):
            return pd.DataFrame(
                columns=columns
            )

        for column in columns:
            if column not in data.columns:
                data[column] = default_for_column(
                    column
                )

        data = data[
            columns
        ].copy()

        if "symbol" in data.columns:
            data["symbol"] = (
                data["symbol"]
                .fillna("")
                .astype(str)
                .str.upper()
                .str.strip()
            )

        return data

    def _save_dataframe(
        self,
        df: pd.DataFrame,
        path: Path,
        columns: list[str],
    ) -> None:
        result = (
            df.copy()
            if isinstance(
                df,
                pd.DataFrame,
            )
            else pd.DataFrame()
        )

        for column in columns:
            if column not in result.columns:
                result[column] = default_for_column(
                    column
                )

        result = result[
            columns
        ]

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        result.to_csv(
            path,
            index=False,
        )

    def _append_event(
        self,
        trade_id: str,
        event_type: str,
        symbol: str,
        quantity: int,
        price: float,
        profit_loss: float,
        profit_loss_pct: float,
        notes: str,
        event_date: str | None = None,
        event_time: str | None = None,
    ) -> None:
        events = self.load_trade_events()

        if event_date or event_time:
            date_part = (
                event_date
                or datetime.now().strftime(
                    "%Y-%m-%d"
                )
            )
            time_part = (
                event_time
                or datetime.now().strftime(
                    "%H:%M:%S"
                )
            )
            event_timestamp = (
                f"{date_part}T{time_part}"
            )
        else:
            event_timestamp = now_iso()

        row = {
            "event_id": str(
                uuid.uuid4()
            ),
            "trade_id": clean_text(
                trade_id
            ),
            "event_time": event_timestamp,
            "event_type": text_value(
                event_type
            ),
            "symbol": text_value(
                symbol
            ),
            "quantity": int(
                max(
                    quantity,
                    0,
                )
            ),
            "price": round(
                positive_or_zero(
                    price
                ),
                4,
            ),
            "profit_loss": round(
                numeric_value(
                    profit_loss
                ),
                2,
            ),
            "profit_loss_pct": round(
                numeric_value(
                    profit_loss_pct
                ),
                2,
            ),
            "notes": clean_text(
                notes
            ),
            "engine_version": self.VERSION,
        }

        events = pd.concat(
            [
                events,
                pd.DataFrame(
                    [row]
                ),
            ],
            ignore_index=True,
        )

        self._save_dataframe(
            events,
            self.trade_events_path,
            self.EVENT_COLUMNS,
        )

    def _summary(
        self,
        status: str,
        reason: str,
        **kwargs: Any,
    ) -> dict:
        return {
            "status": status,
            "engine_version": self.VERSION,
            "reason": reason,
            **kwargs,
            "open_positions_file": str(
                self.open_positions_path
            ),
            "closed_positions_file": str(
                self.closed_positions_path
            ),
            "pending_entries_file": str(
                self.pending_entries_path
            ),
            "trade_events_file": str(
                self.trade_events_path
            ),
        }


def build_trade_lifecycle_engine_v1(
    data_folder: str = "database/portfolio",
) -> TradeLifecycleEngineV1:
    return TradeLifecycleEngineV1(
        data_folder=data_folder
    )


def apply_trade_lifecycle_engine_v1(
    recommendations_df: pd.DataFrame,
    market_df: pd.DataFrame | None = None,
    data_folder: str = "database/portfolio",
) -> tuple[pd.DataFrame, dict]:
    """
    Convenience integration function for main.py.

    Workflow:
    1. Synchronize READY TO BUY candidates.
    2. Update actual open positions using current market data.
    3. Enrich final recommendations with lifecycle state.
    4. Return enriched dataframe and summary.
    """
    engine = TradeLifecycleEngineV1(
        data_folder=data_folder
    )

    pending_summary = engine.sync_pending_entries(
        recommendations_df
    )

    update_summary = engine.update_positions(
        market_df
        if market_df is not None
        else recommendations_df
    )

    enriched = engine.enrich_recommendations(
        recommendations_df
    )

    dashboard = engine.dashboard_summary()

    summary = {
        "status": "success",
        "engine_version": engine.VERSION,
        "pending_sync": pending_summary,
        "position_update": update_summary,
        "dashboard": dashboard,
        "reason": "Trade Lifecycle Engine completed successfully",
    }

    return enriched, summary


def make_trade_id(
    symbol: str,
) -> str:
    timestamp = datetime.now().strftime(
        "%Y%m%d%H%M%S"
    )
    short_id = uuid.uuid4().hex[:8].upper()

    return (
        f"{text_value(symbol)}-"
        f"{timestamp}-"
        f"{short_id}"
    )


def calculate_holding_days(
    entry_date: Any,
    current_date: Any = None,
) -> int:
    entry = parse_date(
        entry_date
    )

    if entry is None:
        return 0

    current = parse_date(
        current_date
    )

    if current is None:
        current = pd.Timestamp(
            datetime.now().date()
        )

    days = (
        current.normalize()
        - entry.normalize()
    ).days

    return int(
        max(
            days,
            0,
        )
    )


def parse_date(
    value: Any,
) -> pd.Timestamp | None:
    if value is None:
        return None

    cleaned = str(
        value
    ).strip()

    if not cleaned:
        return None

    for fmt in (
        "%Y-%m-%d",
        "%d%b%Y",
        "%Y%m%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
    ):
        parsed = pd.to_datetime(
            cleaned,
            format=fmt,
            errors="coerce",
        )

        if pd.notna(parsed):
            return parsed

    parsed = pd.to_datetime(
        cleaned,
        errors="coerce",
    )

    if pd.isna(parsed):
        return None

    return parsed


def value_from_row(
    row: pd.Series | None,
    key: str,
    default: Any,
) -> Any:
    if row is None:
        return default

    try:
        value = row.get(
            key,
            default,
        )
    except Exception:
        return default

    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    return value


def first_numeric(
    row: Any,
    columns: list[str],
    default: float = 0.0,
) -> float:
    for column in columns:
        try:
            value = row.get(
                column,
                None,
            )
        except Exception:
            value = None

        number = numeric_value(
            value,
            None,
        )

        if number is not None:
            return number

    return float(
        default
    )


def numeric_value(
    value: Any,
    default: float | None = 0.0,
) -> float | None:
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    try:
        number = float(
            value
        )

        if math.isfinite(
            number
        ):
            return number

    except Exception:
        pass

    return default


def positive_or_zero(
    value: Any,
) -> float:
    number = numeric_value(
        value,
        0.0,
    )

    if number is None:
        return 0.0

    return float(
        number
        if number > 0
        else 0.0
    )


def clean_text(
    value: Any,
) -> str:
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    return str(
        value
    ).strip()


def text_value(
    value: Any,
) -> str:
    return clean_text(
        value
    ).upper()


def bool_value(
    value: Any,
) -> bool:
    if isinstance(
        value,
        bool,
    ):
        return value

    try:
        if pd.isna(value):
            return False
    except Exception:
        pass

    if isinstance(
        value,
        (
            int,
            float,
        ),
    ):
        return bool(
            value
        )

    return str(
        value
    ).strip().upper() in {
        "TRUE",
        "1",
        "YES",
        "Y",
        "SELECTED",
        "OPEN",
    }


def default_for_column(
    column: str,
) -> Any:
    boolean_columns = {
        "partial_profit_booked",
    }

    integer_columns = {
        "original_quantity",
        "remaining_quantity",
        "exit_quantity",
        "recommended_quantity",
        "holding_days",
        "quantity",
    }

    numeric_columns = {
        "actual_entry_price",
        "average_cost",
        "initial_stop_loss",
        "current_stop_loss",
        "final_stop_loss",
        "target_1",
        "target_2",
        "highest_price_since_entry",
        "lowest_price_since_entry",
        "current_price",
        "unrealized_profit_loss",
        "unrealized_profit_loss_pct",
        "realized_profit_loss",
        "realized_profit_loss_pct",
        "final_exit_price",
        "suggested_entry_price",
        "entry_low",
        "entry_high",
        "stop_loss",
        "recommended_investment",
        "price",
        "profit_loss",
        "profit_loss_pct",
    }

    if column in boolean_columns:
        return False

    if column in integer_columns:
        return 0

    if column in numeric_columns:
        return 0.0

    return ""


def remove_duplicate_columns(
    df: pd.DataFrame,
) -> pd.DataFrame:
    if (
        df is None
        or not hasattr(
            df,
            "columns",
        )
    ):
        return pd.DataFrame()

    return df.loc[
        :,
        ~df.columns.duplicated(),
    ].copy()


def now_iso() -> str:
    return datetime.now().isoformat(
        timespec="seconds"
    )