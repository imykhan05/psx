from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class OrderExecutionConfigV1:
    portfolio_folder: str = "database/portfolio"
    reports_latest_folder: str = "reports/latest"
    pending_entries_filename: str = "pending_entries.csv"
    open_positions_filename: str = "open_positions.csv"
    closed_positions_filename: str = "closed_positions.csv"
    execution_log_filename: str = "execution_log.csv"


class OrderExecutionSimulatorV1:
    """
    Order Execution Simulator V1

    Converts a confirmed READY TO BUY recommendation into an actual OPEN
    portfolio position.

    Important safety behavior
    -------------------------
    - It never opens a trade automatically.
    - A symbol must exist in pending entries.
    - Actual entry price and quantity must be explicitly supplied.
    - Existing open positions are protected from duplicate execution.
    - Pending-entry plans remain separate from actual execution records.
    """

    VERSION = "order_execution_simulator_v1_1_pandas3_dtype_safe"

    def __init__(
        self,
        portfolio_folder: str = "database/portfolio",
        reports_latest_folder: str = "reports/latest",
        pending_entries_filename: str = "pending_entries.csv",
        open_positions_filename: str = "open_positions.csv",
        closed_positions_filename: str = "closed_positions.csv",
        execution_log_filename: str = "execution_log.csv",
    ):
        self.config = OrderExecutionConfigV1(
            portfolio_folder=portfolio_folder,
            reports_latest_folder=reports_latest_folder,
            pending_entries_filename=pending_entries_filename,
            open_positions_filename=open_positions_filename,
            closed_positions_filename=closed_positions_filename,
            execution_log_filename=execution_log_filename,
        )

        self.portfolio_folder = Path(
            self.config.portfolio_folder
        )
        self.reports_latest_folder = Path(
            self.config.reports_latest_folder
        )

        self.portfolio_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.pending_entries_path = (
            self.portfolio_folder
            / self.config.pending_entries_filename
        )

        self.latest_pending_entries_path = (
            self.reports_latest_folder
            / self.config.pending_entries_filename
        )

        self.open_positions_path = (
            self.portfolio_folder
            / self.config.open_positions_filename
        )

        self.closed_positions_path = (
            self.portfolio_folder
            / self.config.closed_positions_filename
        )

        self.execution_log_path = (
            self.portfolio_folder
            / self.config.execution_log_filename
        )

    # ---------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------

    def execute_buy(
        self,
        symbol: str,
        actual_entry_price: float,
        actual_quantity: int,
        entry_date: str | None = None,
        broker_reference: str = "",
        notes: str = "",
        commission: float = 0.0,
    ) -> dict:
        symbol = upper_text(symbol)

        if not symbol:
            raise ValueError(
                "Symbol is required."
            )

        actual_entry_price = positive_float(
            actual_entry_price,
            "actual_entry_price",
        )

        actual_quantity = positive_int(
            actual_quantity,
            "actual_quantity",
        )

        commission = non_negative_float(
            commission,
            "commission",
        )

        resolved_entry_date = normalize_date(
            entry_date
            or datetime.now().strftime(
                "%Y-%m-%d"
            )
        )

        pending_df = self.load_pending_entries()
        open_df = self.load_open_positions()
        closed_df = self.load_closed_positions()

        self.ensure_not_already_open(
            symbol=symbol,
            open_df=open_df,
        )

        pending_row = self.resolve_pending_entry(
            symbol=symbol,
            pending_df=pending_df,
        )

        trade_id = self.build_trade_id(
            symbol=symbol,
            entry_date=resolved_entry_date,
            open_df=open_df,
            closed_df=closed_df,
        )

        position = self.build_open_position(
            pending_row=pending_row,
            symbol=symbol,
            trade_id=trade_id,
            actual_entry_price=actual_entry_price,
            actual_quantity=actual_quantity,
            entry_date=resolved_entry_date,
            broker_reference=broker_reference,
            notes=notes,
            commission=commission,
        )

        updated_open_df = self.append_open_position(
            open_df=open_df,
            position=position,
        )

        updated_pending_df = self.mark_pending_as_executed(
            pending_df=pending_df,
            symbol=symbol,
            trade_id=trade_id,
            actual_entry_price=actual_entry_price,
            actual_quantity=actual_quantity,
            execution_date=resolved_entry_date,
        )

        self.save_dataframe(
            updated_open_df,
            self.open_positions_path,
            self.open_position_columns(),
        )

        self.save_dataframe(
            updated_pending_df,
            self.pending_entries_path,
            self.pending_entry_columns(
                updated_pending_df
            ),
        )

        self.append_execution_log(
            position=position,
            action="BUY EXECUTED",
        )

        investment = (
            actual_entry_price
            * actual_quantity
        )

        return {
            "status": "success",
            "engine_version": self.VERSION,
            "action": "BUY EXECUTED",
            "trade_id": trade_id,
            "symbol": symbol,
            "entry_date": resolved_entry_date,
            "actual_entry_price": round(
                actual_entry_price,
                4,
            ),
            "actual_quantity": int(
                actual_quantity
            ),
            "investment": round(
                investment,
                2,
            ),
            "commission": round(
                commission,
                2,
            ),
            "net_cost": round(
                investment + commission,
                2,
            ),
            "position_status": "OPEN",
            "open_positions_file": str(
                self.open_positions_path
            ),
            "pending_entries_file": str(
                self.pending_entries_path
            ),
            "execution_log_file": str(
                self.execution_log_path
            ),
            "reason": (
                "Pending recommendation converted into an actual open position"
            ),
        }

    def execute_sell(
        self,
        symbol: str,
        exit_price: float,
        exit_quantity: int | None = None,
        exit_date: str | None = None,
        broker_reference: str = "",
        notes: str = "",
        commission: float = 0.0,
    ) -> dict:
        symbol = upper_text(symbol)

        if not symbol:
            raise ValueError(
                "Symbol is required."
            )

        exit_price = positive_float(
            exit_price,
            "exit_price",
        )

        commission = non_negative_float(
            commission,
            "commission",
        )

        resolved_exit_date = normalize_date(
            exit_date
            or datetime.now().strftime(
                "%Y-%m-%d"
            )
        )

        open_df = self.load_open_positions()
        closed_df = self.load_closed_positions()

        open_df = self.prepare_execution_dtypes(
            open_df
        )

        closed_df = self.prepare_execution_dtypes(
            closed_df
        )

        if open_df.empty:
            raise ValueError(
                "No open positions are available."
            )

        matches = open_df[
            open_df["symbol"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.strip()
            .eq(symbol)
        ]

        if matches.empty:
            raise ValueError(
                f"No open position found for {symbol}."
            )

        index = matches.index[0]
        row = open_df.loc[index].copy()

        remaining_quantity = int(
            first_positive_numeric(
                row,
                [
                    "remaining_quantity",
                    "open_quantity",
                    "actual_quantity",
                    "original_quantity",
                ],
            )
        )

        if remaining_quantity <= 0:
            raise ValueError(
                f"{symbol} has no remaining quantity."
            )

        quantity_to_sell = (
            remaining_quantity
            if exit_quantity is None
            else positive_int(
                exit_quantity,
                "exit_quantity",
            )
        )

        if quantity_to_sell > remaining_quantity:
            raise ValueError(
                (
                    f"Exit quantity {quantity_to_sell} exceeds "
                    f"remaining quantity {remaining_quantity}."
                )
            )

        entry_price = first_positive_numeric(
            row,
            [
                "actual_entry_price",
                "average_cost",
            ],
        )

        gross_profit_loss = (
            exit_price
            - entry_price
        ) * quantity_to_sell

        net_profit_loss = (
            gross_profit_loss
            - commission
        )

        previous_realized = safe_float(
            row.get(
                "realized_profit_loss",
                0,
            )
        )

        total_realized = (
            previous_realized
            + net_profit_loss
        )

        new_remaining = (
            remaining_quantity
            - quantity_to_sell
        )

        full_exit = (
            new_remaining == 0
        )

        open_df.at[
            index,
            "remaining_quantity",
        ] = new_remaining

        open_df.at[
            index,
            "open_quantity",
        ] = new_remaining

        open_df.at[
            index,
            "realized_profit_loss",
        ] = round(
            total_realized,
            2,
        )

        open_df.at[
            index,
            "last_exit_price",
        ] = round(
            exit_price,
            4,
        )

        open_df.at[
            index,
            "last_exit_quantity",
        ] = int(
            quantity_to_sell
        )

        open_df.at[
            index,
            "last_exit_date",
        ] = resolved_exit_date

        open_df.at[
            index,
            "partial_profit_booked",
        ] = not full_exit

        open_df.at[
            index,
            "position_status",
        ] = (
            "FULL EXIT"
            if full_exit
            else "PARTIAL EXIT"
        )

        open_df.at[
            index,
            "lifecycle_status",
        ] = (
            "FULL EXIT"
            if full_exit
            else "PARTIAL EXIT"
        )

        open_df.at[
            index,
            "last_updated_at",
        ] = datetime.now().isoformat(
            timespec="seconds"
        )

        closed_record = None

        if full_exit:
            closed_record = open_df.loc[
                index
            ].to_dict()

            closed_record.update({
                "final_exit_price": round(
                    exit_price,
                    4,
                ),
                "exit_date": resolved_exit_date,
                "close_reason": (
                    clean_text(notes)
                    or "Manual full exit"
                ),
                "position_status": "CLOSED",
                "lifecycle_status": "CLOSED",
                "remaining_quantity": 0,
                "open_quantity": 0,
            })

            open_df = open_df.drop(
                index=index
            ).reset_index(
                drop=True
            )

            closed_df = self.append_closed_position(
                closed_df=closed_df,
                position=closed_record,
            )

        self.save_dataframe(
            open_df,
            self.open_positions_path,
            self.open_position_columns(),
        )

        self.save_dataframe(
            closed_df,
            self.closed_positions_path,
            self.closed_position_columns(),
        )

        log_record = (
            closed_record
            if closed_record is not None
            else open_df[
                open_df["symbol"]
                .fillna("")
                .astype(str)
                .str.upper()
                .str.strip()
                .eq(symbol)
            ].iloc[0].to_dict()
        )

        log_record.update({
            "last_exit_price": round(
                exit_price,
                4,
            ),
            "last_exit_quantity": int(
                quantity_to_sell
            ),
            "last_exit_date": resolved_exit_date,
            "broker_reference": clean_text(
                broker_reference
            ),
            "execution_notes": clean_text(
                notes
            ),
            "execution_commission": round(
                commission,
                2,
            ),
            "execution_profit_loss": round(
                net_profit_loss,
                2,
            ),
        })

        self.append_execution_log(
            position=log_record,
            action=(
                "FULL SELL EXECUTED"
                if full_exit
                else "PARTIAL SELL EXECUTED"
            ),
        )

        return {
            "status": "success",
            "engine_version": self.VERSION,
            "action": (
                "FULL SELL EXECUTED"
                if full_exit
                else "PARTIAL SELL EXECUTED"
            ),
            "trade_id": clean_text(
                row.get(
                    "trade_id",
                    "",
                )
            ),
            "symbol": symbol,
            "exit_date": resolved_exit_date,
            "exit_price": round(
                exit_price,
                4,
            ),
            "exit_quantity": int(
                quantity_to_sell
            ),
            "remaining_quantity": int(
                new_remaining
            ),
            "realized_profit_loss": round(
                net_profit_loss,
                2,
            ),
            "total_realized_profit_loss": round(
                total_realized,
                2,
            ),
            "position_status": (
                "CLOSED"
                if full_exit
                else "PARTIAL EXIT"
            ),
            "open_positions_file": str(
                self.open_positions_path
            ),
            "closed_positions_file": str(
                self.closed_positions_path
            ),
            "execution_log_file": str(
                self.execution_log_path
            ),
        }

    def list_pending_entries(
        self,
    ) -> pd.DataFrame:
        pending_df = self.load_pending_entries()

        if pending_df.empty:
            return pd.DataFrame()

        status_column = first_existing_column(
            pending_df,
            [
                "execution_status",
                "lifecycle_status",
            ],
        )

        if status_column:
            mask = (
                pending_df[status_column]
                .fillna("")
                .astype(str)
                .str.upper()
                .str.strip()
                .isin(
                    [
                        "",
                        "READY TO BUY",
                        "PENDING",
                    ]
                )
            )

            pending_df = pending_df[
                mask
            ].copy()

        return pending_df.reset_index(
            drop=True
        )

    # ---------------------------------------------------------
    # LOADERS
    # ---------------------------------------------------------

    def load_pending_entries(
        self,
    ) -> pd.DataFrame:
        local_df = self.read_csv(
            self.pending_entries_path
        )

        if not local_df.empty:
            return local_df

        latest_df = self.read_csv(
            self.latest_pending_entries_path
        )

        if not latest_df.empty:
            self.save_dataframe(
                latest_df,
                self.pending_entries_path,
                self.pending_entry_columns(
                    latest_df
                ),
            )

        return latest_df

    def load_open_positions(
        self,
    ) -> pd.DataFrame:
        df = self.read_csv(
            self.open_positions_path
        )

        return self.normalize_open_positions(
            df
        )

    def load_closed_positions(
        self,
    ) -> pd.DataFrame:
        return self.read_csv(
            self.closed_positions_path
        )

    def read_csv(
        self,
        path: Path,
    ) -> pd.DataFrame:
        if (
            not path.exists()
            or path.stat().st_size == 0
        ):
            return pd.DataFrame()

        try:
            df = pd.read_csv(path)
        except (
            pd.errors.EmptyDataError,
            pd.errors.ParserError,
            UnicodeDecodeError,
        ):
            return pd.DataFrame()

        return remove_duplicate_columns(
            df
        )

    # ---------------------------------------------------------
    # VALIDATION AND RECORD BUILDING
    # ---------------------------------------------------------

    def ensure_not_already_open(
        self,
        symbol: str,
        open_df: pd.DataFrame,
    ) -> None:
        if open_df.empty:
            return

        existing = open_df[
            open_df["symbol"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.strip()
            .eq(symbol)
        ]

        if not existing.empty:
            raise ValueError(
                (
                    f"{symbol} already has an open position. "
                    "Use the sell command or portfolio update workflow."
                )
            )

    def resolve_pending_entry(
        self,
        symbol: str,
        pending_df: pd.DataFrame,
    ) -> pd.Series:
        if pending_df.empty:
            raise ValueError(
                (
                    "No pending entries found. Run main.py first "
                    "to generate current portfolio recommendations."
                )
            )

        if "symbol" not in pending_df.columns:
            raise ValueError(
                "Pending entries file has no symbol column."
            )

        matches = pending_df[
            pending_df["symbol"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.strip()
            .eq(symbol)
        ]

        if matches.empty:
            available = (
                pending_df["symbol"]
                .dropna()
                .astype(str)
                .str.upper()
                .str.strip()
                .tolist()
            )

            raise ValueError(
                (
                    f"{symbol} is not a pending entry. "
                    f"Available pending symbols: {available}"
                )
            )

        row = matches.iloc[0].copy()

        execution_status = upper_text(
            row.get(
                "execution_status",
                "",
            )
        )

        if execution_status in {
            "BUY EXECUTED",
            "OPEN",
            "CLOSED",
            "CANCELLED",
        }:
            raise ValueError(
                (
                    f"{symbol} pending row is already marked "
                    f"{execution_status}."
                )
            )

        return row

    def build_trade_id(
        self,
        symbol: str,
        entry_date: str,
        open_df: pd.DataFrame,
        closed_df: pd.DataFrame,
    ) -> str:
        date_token = (
            pd.to_datetime(
                entry_date,
                errors="coerce",
            )
            .strftime("%Y%m%d")
        )

        prefix = (
            f"{symbol}-{date_token}"
        )

        existing_ids = []

        for df in [
            open_df,
            closed_df,
        ]:
            if (
                not df.empty
                and "trade_id" in df.columns
            ):
                existing_ids.extend(
                    df["trade_id"]
                    .fillna("")
                    .astype(str)
                    .tolist()
                )

        sequence = 1

        while (
            f"{prefix}-{sequence:03d}"
            in existing_ids
        ):
            sequence += 1

        return (
            f"{prefix}-{sequence:03d}"
        )

    def build_open_position(
        self,
        pending_row: pd.Series,
        symbol: str,
        trade_id: str,
        actual_entry_price: float,
        actual_quantity: int,
        entry_date: str,
        broker_reference: str,
        notes: str,
        commission: float,
    ) -> dict:
        now = datetime.now()

        planned_entry = first_positive_numeric(
            pending_row,
            [
                "adjusted_entry_price",
                "suggested_entry_price",
                "entry_high",
                "close",
            ],
        )

        initial_stop_loss = first_positive_numeric(
            pending_row,
            [
                "stop_loss",
                "current_stop_loss",
                "exit_suggested_stop_loss",
            ],
        )

        target_1 = first_positive_numeric(
            pending_row,
            [
                "target_1",
            ],
        )

        target_2 = first_positive_numeric(
            pending_row,
            [
                "target_2",
            ],
        )

        investment = (
            actual_entry_price
            * actual_quantity
        )

        entry_variance_pct = (
            (
                actual_entry_price
                - planned_entry
            )
            / planned_entry
            * 100
            if planned_entry > 0
            else 0.0
        )

        risk_per_share = max(
            actual_entry_price
            - initial_stop_loss,
            0,
        )

        max_loss = (
            risk_per_share
            * actual_quantity
        )

        return {
            "engine_version": self.VERSION,
            "trade_id": trade_id,
            "symbol": symbol,
            "company": clean_text(
                pending_row.get(
                    "company",
                    "",
                )
            ),
            "sector": clean_text(
                pending_row.get(
                    "sector",
                    "",
                )
            ),
            "industry": clean_text(
                pending_row.get(
                    "industry",
                    "",
                )
            ),
            "signal_date": clean_text(
                first_valid(
                    pending_row.get(
                        "date"
                    ),
                    pending_row.get(
                        "signal_date"
                    ),
                    "",
                )
            ),
            "entry_date": entry_date,
            "opened_at": now.isoformat(
                timespec="seconds"
            ),
            "planned_entry_price": round(
                planned_entry,
                4,
            ),
            "actual_entry_price": round(
                actual_entry_price,
                4,
            ),
            "average_cost": round(
                actual_entry_price,
                4,
            ),
            "entry_variance_pct": round(
                entry_variance_pct,
                4,
            ),
            "original_quantity": int(
                actual_quantity
            ),
            "actual_quantity": int(
                actual_quantity
            ),
            "open_quantity": int(
                actual_quantity
            ),
            "remaining_quantity": int(
                actual_quantity
            ),
            "investment": round(
                investment,
                2,
            ),
            "commission_paid": round(
                commission,
                2,
            ),
            "net_cost": round(
                investment + commission,
                2,
            ),
            "initial_stop_loss": round(
                initial_stop_loss,
                4,
            ),
            "current_stop_loss": round(
                initial_stop_loss,
                4,
            ),
            "stop_loss": round(
                initial_stop_loss,
                4,
            ),
            "target_1": round(
                target_1,
                4,
            ),
            "target_2": round(
                target_2,
                4,
            ),
            "target_1_hit": False,
            "target_2_hit": False,
            "partial_profit_booked": False,
            "highest_price_since_entry": round(
                actual_entry_price,
                4,
            ),
            "lowest_price_since_entry": round(
                actual_entry_price,
                4,
            ),
            "current_price": round(
                actual_entry_price,
                4,
            ),
            "market_value": round(
                investment,
                2,
            ),
            "cost_value": round(
                investment,
                2,
            ),
            "realized_profit_loss": 0.0,
            "unrealized_profit_loss": 0.0,
            "unrealized_profit_loss_pct": 0.0,
            "total_profit_loss": 0.0,
            "risk_per_share": round(
                risk_per_share,
                4,
            ),
            "risk_amount_to_stop": round(
                max_loss,
                2,
            ),
            "position_status": "OPEN",
            "lifecycle_status": "OPEN",
            "position_event": "BUY EXECUTED",
            "recommended_action": "HOLD",
            "holding_days": 0,
            "broker_reference": clean_text(
                broker_reference
            ),
            "execution_notes": clean_text(
                notes
            ),
            "last_updated_at": now.isoformat(
                timespec="seconds"
            ),
            "portfolio_rank": int(
                safe_float(
                    pending_row.get(
                        "portfolio_rank",
                        0,
                    )
                )
            ),
            "buy_probability": round(
                safe_float(
                    pending_row.get(
                        "buy_probability",
                        0,
                    )
                ),
                2,
            ),
            "confidence": round(
                first_positive_numeric(
                    pending_row,
                    [
                        "confidence",
                        "confidence_v3",
                        "exit_confidence",
                        "buy_probability",
                    ],
                ),
                2,
            ),
            "final_decision": clean_text(
                pending_row.get(
                    "final_decision",
                    "",
                )
            ),
            "risk_permission": clean_text(
                pending_row.get(
                    "risk_permission",
                    "",
                )
            ),
            "entry_timing_action": clean_text(
                pending_row.get(
                    "entry_timing_action",
                    "",
                )
            ),
        }

    # ---------------------------------------------------------
    # DATAFRAME UPDATES
    # ---------------------------------------------------------

    def append_open_position(
        self,
        open_df: pd.DataFrame,
        position: dict,
    ) -> pd.DataFrame:
        new_row = pd.DataFrame(
            [position]
        )

        if open_df.empty:
            combined = new_row
        else:
            combined = pd.concat(
                [
                    open_df,
                    new_row,
                ],
                ignore_index=True,
                sort=False,
            )

        combined = remove_duplicate_columns(
            combined
        )

        combined = combined.drop_duplicates(
            subset=[
                "trade_id",
            ],
            keep="last",
        )

        return combined.reset_index(
            drop=True
        )

    def append_closed_position(
        self,
        closed_df: pd.DataFrame,
        position: dict,
    ) -> pd.DataFrame:
        new_row = pd.DataFrame(
            [position]
        )

        if closed_df.empty:
            combined = new_row
        else:
            combined = pd.concat(
                [
                    closed_df,
                    new_row,
                ],
                ignore_index=True,
                sort=False,
            )

        if "trade_id" in combined.columns:
            combined = combined.drop_duplicates(
                subset=[
                    "trade_id",
                ],
                keep="last",
            )

        return combined.reset_index(
            drop=True
        )

    def mark_pending_as_executed(
        self,
        pending_df: pd.DataFrame,
        symbol: str,
        trade_id: str,
        actual_entry_price: float,
        actual_quantity: int,
        execution_date: str,
    ) -> pd.DataFrame:
        pending_df = remove_duplicate_columns(
            pending_df.copy()
        )

        required_defaults = {
            "execution_status": "",
            "executed_trade_id": "",
            "executed_entry_price": 0.0,
            "executed_quantity": 0,
            "execution_date": "",
            "execution_timestamp": "",
        }

        for column, default in required_defaults.items():
            if column not in pending_df.columns:
                pending_df[column] = default

        mask = (
            pending_df["symbol"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.strip()
            .eq(symbol)
        )

        pending_df.loc[
            mask,
            "execution_status",
        ] = "BUY EXECUTED"

        pending_df.loc[
            mask,
            "executed_trade_id",
        ] = trade_id

        pending_df.loc[
            mask,
            "executed_entry_price",
        ] = float(
            actual_entry_price
        )

        pending_df.loc[
            mask,
            "executed_quantity",
        ] = int(
            actual_quantity
        )

        pending_df.loc[
            mask,
            "execution_date",
        ] = execution_date

        pending_df.loc[
            mask,
            "execution_timestamp",
        ] = datetime.now().isoformat(
            timespec="seconds"
        )

        return pending_df

    def append_execution_log(
        self,
        position: dict,
        action: str,
    ) -> None:
        record = {
            "timestamp": datetime.now().isoformat(
                timespec="seconds"
            ),
            "engine_version": self.VERSION,
            "action": action,
            "trade_id": clean_text(
                position.get(
                    "trade_id",
                    "",
                )
            ),
            "symbol": upper_text(
                position.get(
                    "symbol",
                    "",
                )
            ),
            "entry_date": clean_text(
                position.get(
                    "entry_date",
                    "",
                )
            ),
            "actual_entry_price": safe_float(
                position.get(
                    "actual_entry_price",
                    0,
                )
            ),
            "actual_quantity": int(
                safe_float(
                    first_valid(
                        position.get(
                            "actual_quantity"
                        ),
                        position.get(
                            "original_quantity"
                        ),
                        0,
                    )
                )
            ),
            "exit_date": clean_text(
                first_valid(
                    position.get(
                        "last_exit_date"
                    ),
                    position.get(
                        "exit_date"
                    ),
                    "",
                )
            ),
            "exit_price": safe_float(
                first_valid(
                    position.get(
                        "last_exit_price"
                    ),
                    position.get(
                        "final_exit_price"
                    ),
                    0,
                )
            ),
            "exit_quantity": int(
                safe_float(
                    position.get(
                        "last_exit_quantity",
                        0,
                    )
                )
            ),
            "remaining_quantity": int(
                safe_float(
                    position.get(
                        "remaining_quantity",
                        0,
                    )
                )
            ),
            "commission": safe_float(
                first_valid(
                    position.get(
                        "execution_commission"
                    ),
                    position.get(
                        "commission_paid"
                    ),
                    0,
                )
            ),
            "profit_loss": safe_float(
                first_valid(
                    position.get(
                        "execution_profit_loss"
                    ),
                    position.get(
                        "realized_profit_loss"
                    ),
                    0,
                )
            ),
            "broker_reference": clean_text(
                position.get(
                    "broker_reference",
                    "",
                )
            ),
            "notes": clean_text(
                position.get(
                    "execution_notes",
                    "",
                )
            ),
            "position_status": clean_text(
                position.get(
                    "position_status",
                    "",
                )
            ),
        }

        log_df = self.read_csv(
            self.execution_log_path
        )

        log_df = pd.concat(
            [
                log_df,
                pd.DataFrame(
                    [record]
                ),
            ],
            ignore_index=True,
            sort=False,
        )

        self.save_dataframe(
            log_df,
            self.execution_log_path,
            list(record.keys()),
        )

    def prepare_execution_dtypes(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Force stable dtypes before row-level assignments.

        Pandas 3.x does not allow assigning date/status strings into columns
        inferred as float64 from empty CSV values.
        """
        df = remove_duplicate_columns(
            df.copy()
        )

        if df.empty:
            return df

        text_columns = {
            "engine_version",
            "trade_id",
            "symbol",
            "company",
            "sector",
            "industry",
            "signal_date",
            "entry_date",
            "opened_at",
            "position_status",
            "lifecycle_status",
            "position_event",
            "recommended_action",
            "broker_reference",
            "execution_notes",
            "last_updated_at",
            "final_decision",
            "risk_permission",
            "entry_timing_action",
            "last_exit_date",
            "exit_date",
            "close_reason",
        }

        boolean_columns = {
            "target_1_hit",
            "target_2_hit",
            "partial_profit_booked",
        }

        integer_columns = {
            "original_quantity",
            "actual_quantity",
            "open_quantity",
            "remaining_quantity",
            "holding_days",
            "portfolio_rank",
            "last_exit_quantity",
        }

        for column in text_columns:
            if column not in df.columns:
                df[column] = ""

            df[column] = (
                df[column]
                .fillna("")
                .astype(str)
            )

        for column in boolean_columns:
            if column not in df.columns:
                df[column] = False

            df[column] = (
                df[column]
                .fillna(False)
                .astype(bool)
            )

        for column in integer_columns:
            if column not in df.columns:
                df[column] = 0

            df[column] = (
                pd.to_numeric(
                    df[column],
                    errors="coerce",
                )
                .fillna(0)
                .astype(int)
            )

        numeric_columns = {
            "planned_entry_price",
            "actual_entry_price",
            "average_cost",
            "entry_variance_pct",
            "investment",
            "commission_paid",
            "net_cost",
            "initial_stop_loss",
            "current_stop_loss",
            "stop_loss",
            "target_1",
            "target_2",
            "highest_price_since_entry",
            "lowest_price_since_entry",
            "current_price",
            "market_value",
            "cost_value",
            "realized_profit_loss",
            "unrealized_profit_loss",
            "unrealized_profit_loss_pct",
            "total_profit_loss",
            "risk_per_share",
            "risk_amount_to_stop",
            "buy_probability",
            "confidence",
            "last_exit_price",
            "final_exit_price",
        }

        for column in numeric_columns:
            if column not in df.columns:
                df[column] = 0.0

            df[column] = (
                pd.to_numeric(
                    df[column],
                    errors="coerce",
                )
                .fillna(0.0)
                .astype(float)
            )

        return df

    # ---------------------------------------------------------
    # NORMALIZATION
    # ---------------------------------------------------------

    def normalize_open_positions(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        df = remove_duplicate_columns(
            df
        )

        if df.empty:
            return pd.DataFrame(
                columns=self.open_position_columns()
            )

        defaults = {
            column: default_for_column(
                column
            )
            for column in self.open_position_columns()
        }

        for column, default in defaults.items():
            if column not in df.columns:
                df[column] = default

        if "symbol" in df.columns:
            df["symbol"] = (
                df["symbol"]
                .fillna("")
                .astype(str)
                .str.upper()
                .str.strip()
            )

        df = self.prepare_execution_dtypes(
            df
        )

        return df

    # ---------------------------------------------------------
    # SCHEMAS
    # ---------------------------------------------------------

    def open_position_columns(
        self,
    ) -> list[str]:
        return [
            "engine_version",
            "trade_id",
            "symbol",
            "company",
            "sector",
            "industry",
            "signal_date",
            "entry_date",
            "opened_at",
            "planned_entry_price",
            "actual_entry_price",
            "average_cost",
            "entry_variance_pct",
            "original_quantity",
            "actual_quantity",
            "open_quantity",
            "remaining_quantity",
            "investment",
            "commission_paid",
            "net_cost",
            "initial_stop_loss",
            "current_stop_loss",
            "stop_loss",
            "target_1",
            "target_2",
            "target_1_hit",
            "target_2_hit",
            "partial_profit_booked",
            "highest_price_since_entry",
            "lowest_price_since_entry",
            "current_price",
            "market_value",
            "cost_value",
            "realized_profit_loss",
            "unrealized_profit_loss",
            "unrealized_profit_loss_pct",
            "total_profit_loss",
            "risk_per_share",
            "risk_amount_to_stop",
            "position_status",
            "lifecycle_status",
            "position_event",
            "recommended_action",
            "holding_days",
            "broker_reference",
            "execution_notes",
            "last_updated_at",
            "portfolio_rank",
            "buy_probability",
            "confidence",
            "final_decision",
            "risk_permission",
            "entry_timing_action",
            "last_exit_price",
            "last_exit_quantity",
            "last_exit_date",
        ]

    def closed_position_columns(
        self,
    ) -> list[str]:
        return self.open_position_columns() + [
            "final_exit_price",
            "exit_date",
            "close_reason",
        ]

    def pending_entry_columns(
        self,
        df: pd.DataFrame,
    ) -> list[str]:
        base = list(
            df.columns
        )

        for column in [
            "execution_status",
            "executed_trade_id",
            "executed_entry_price",
            "executed_quantity",
            "execution_date",
            "execution_timestamp",
        ]:
            if column not in base:
                base.append(
                    column
                )

        return base

    # ---------------------------------------------------------
    # SAVE
    # ---------------------------------------------------------

    def save_dataframe(
        self,
        df: pd.DataFrame,
        path: Path,
        columns: list[str],
    ) -> None:
        df = remove_duplicate_columns(
            df
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if df.empty:
            pd.DataFrame(
                columns=columns
            ).to_csv(
                path,
                index=False,
                encoding="utf-8-sig",
            )
            return

        for column in columns:
            if column not in df.columns:
                df[column] = default_for_column(
                    column
                )

        df[columns].to_csv(
            path,
            index=False,
            encoding="utf-8-sig",
        )


# ---------------------------------------------------------
# PUBLIC FUNCTIONS
# ---------------------------------------------------------

def execute_buy_order_v1(
    symbol: str,
    actual_entry_price: float,
    actual_quantity: int,
    entry_date: str | None = None,
    broker_reference: str = "",
    notes: str = "",
    commission: float = 0.0,
    portfolio_folder: str = "database/portfolio",
    reports_latest_folder: str = "reports/latest",
) -> dict:
    engine = OrderExecutionSimulatorV1(
        portfolio_folder=portfolio_folder,
        reports_latest_folder=reports_latest_folder,
    )

    return engine.execute_buy(
        symbol=symbol,
        actual_entry_price=actual_entry_price,
        actual_quantity=actual_quantity,
        entry_date=entry_date,
        broker_reference=broker_reference,
        notes=notes,
        commission=commission,
    )


def execute_sell_order_v1(
    symbol: str,
    exit_price: float,
    exit_quantity: int | None = None,
    exit_date: str | None = None,
    broker_reference: str = "",
    notes: str = "",
    commission: float = 0.0,
    portfolio_folder: str = "database/portfolio",
    reports_latest_folder: str = "reports/latest",
) -> dict:
    engine = OrderExecutionSimulatorV1(
        portfolio_folder=portfolio_folder,
        reports_latest_folder=reports_latest_folder,
    )

    return engine.execute_sell(
        symbol=symbol,
        exit_price=exit_price,
        exit_quantity=exit_quantity,
        exit_date=exit_date,
        broker_reference=broker_reference,
        notes=notes,
        commission=commission,
    )


def list_pending_orders_v1(
    portfolio_folder: str = "database/portfolio",
    reports_latest_folder: str = "reports/latest",
) -> pd.DataFrame:
    engine = OrderExecutionSimulatorV1(
        portfolio_folder=portfolio_folder,
        reports_latest_folder=reports_latest_folder,
    )

    return engine.list_pending_entries()


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def remove_duplicate_columns(
    df: pd.DataFrame | None,
) -> pd.DataFrame:
    if (
        df is None
        or not isinstance(
            df,
            pd.DataFrame,
        )
    ):
        return pd.DataFrame()

    return df.loc[
        :,
        ~df.columns.duplicated(),
    ].copy()


def first_existing_column(
    df: pd.DataFrame,
    columns: list[str],
) -> str:
    if (
        df is None
        or not isinstance(
            df,
            pd.DataFrame,
        )
    ):
        return ""

    for column in columns:
        if column in df.columns:
            return column

    return ""


def first_positive_numeric(
    row: Any,
    columns: list[str],
) -> float:
    for column in columns:
        try:
            value = row.get(
                column,
                None,
            )
        except Exception:
            value = None

        number = safe_float(
            value,
            None,
        )

        if (
            number is not None
            and number > 0
        ):
            return number

    return 0.0


def safe_float(
    value: Any,
    default: float | None = 0.0,
) -> float | None:
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    try:
        number = float(value)

        if math.isfinite(number):
            return number
    except Exception:
        pass

    return default


def positive_float(
    value: Any,
    field_name: str,
) -> float:
    number = safe_float(
        value,
        None,
    )

    if (
        number is None
        or number <= 0
    ):
        raise ValueError(
            f"{field_name} must be greater than zero."
        )

    return float(number)


def non_negative_float(
    value: Any,
    field_name: str,
) -> float:
    number = safe_float(
        value,
        None,
    )

    if (
        number is None
        or number < 0
    ):
        raise ValueError(
            f"{field_name} cannot be negative."
        )

    return float(number)


def positive_int(
    value: Any,
    field_name: str,
) -> int:
    number = safe_float(
        value,
        None,
    )

    if (
        number is None
        or number <= 0
        or not float(number).is_integer()
    ):
        raise ValueError(
            f"{field_name} must be a positive whole number."
        )

    return int(number)


def normalize_date(
    value: Any,
) -> str:
    parsed = pd.to_datetime(
        value,
        errors="coerce",
    )

    if pd.isna(parsed):
        raise ValueError(
            f"Invalid date: {value}"
        )

    return parsed.strftime(
        "%Y-%m-%d"
    )


def first_valid(
    *values: Any,
) -> Any:
    for value in values:
        try:
            if pd.isna(value):
                continue
        except Exception:
            pass

        text = str(value).strip()

        if text.upper() not in {
            "",
            "NAN",
            "NONE",
            "NULL",
        }:
            return value

    return ""


def clean_text(
    value: Any,
) -> str:
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    return str(value).strip()


def upper_text(
    value: Any,
) -> str:
    return clean_text(
        value
    ).upper()


def default_for_column(
    column: str,
) -> Any:
    boolean_columns = {
        "target_1_hit",
        "target_2_hit",
        "partial_profit_booked",
    }

    integer_columns = {
        "original_quantity",
        "actual_quantity",
        "open_quantity",
        "remaining_quantity",
        "holding_days",
        "portfolio_rank",
        "last_exit_quantity",
        "executed_quantity",
    }

    numeric_columns = {
        "planned_entry_price",
        "actual_entry_price",
        "average_cost",
        "entry_variance_pct",
        "investment",
        "commission_paid",
        "net_cost",
        "initial_stop_loss",
        "current_stop_loss",
        "stop_loss",
        "target_1",
        "target_2",
        "highest_price_since_entry",
        "lowest_price_since_entry",
        "current_price",
        "market_value",
        "cost_value",
        "realized_profit_loss",
        "unrealized_profit_loss",
        "unrealized_profit_loss_pct",
        "total_profit_loss",
        "risk_per_share",
        "risk_amount_to_stop",
        "buy_probability",
        "confidence",
        "last_exit_price",
        "final_exit_price",
        "executed_entry_price",
    }

    if column in boolean_columns:
        return False

    if column in integer_columns:
        return 0

    if column in numeric_columns:
        return 0.0

    return ""


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def print_dataframe(
    df: pd.DataFrame,
) -> None:
    if df is None or df.empty:
        print("No records found.")
        return

    preferred = [
        "symbol",
        "company",
        "portfolio_quantity",
        "adjusted_entry_price",
        "stop_loss",
        "target_1",
        "target_2",
        "execution_status",
    ]

    available = [
        column
        for column in preferred
        if column in df.columns
    ]

    if not available:
        available = list(
            df.columns
        )[:12]

    print(
        df[available].to_string(
            index=False
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "PSX Order Execution Simulator V1"
        )
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    list_parser = subparsers.add_parser(
        "list",
        help="List pending READY TO BUY orders.",
    )

    buy_parser = subparsers.add_parser(
        "buy",
        help="Confirm and execute a pending BUY order.",
    )

    buy_parser.add_argument(
        "--symbol",
        required=True,
    )

    buy_parser.add_argument(
        "--price",
        required=True,
        type=float,
    )

    buy_parser.add_argument(
        "--quantity",
        required=True,
        type=int,
    )

    buy_parser.add_argument(
        "--date",
        default=None,
    )

    buy_parser.add_argument(
        "--broker-reference",
        default="",
    )

    buy_parser.add_argument(
        "--notes",
        default="",
    )

    buy_parser.add_argument(
        "--commission",
        default=0.0,
        type=float,
    )

    sell_parser = subparsers.add_parser(
        "sell",
        help="Execute a partial or full SELL order.",
    )

    sell_parser.add_argument(
        "--symbol",
        required=True,
    )

    sell_parser.add_argument(
        "--price",
        required=True,
        type=float,
    )

    sell_parser.add_argument(
        "--quantity",
        default=None,
        type=int,
    )

    sell_parser.add_argument(
        "--date",
        default=None,
    )

    sell_parser.add_argument(
        "--broker-reference",
        default="",
    )

    sell_parser.add_argument(
        "--notes",
        default="",
    )

    sell_parser.add_argument(
        "--commission",
        default=0.0,
        type=float,
    )

    args = parser.parse_args()

    engine = OrderExecutionSimulatorV1()

    if args.command == "list":
        print_dataframe(
            engine.list_pending_entries()
        )
        return

    if args.command == "buy":
        result = engine.execute_buy(
            symbol=args.symbol,
            actual_entry_price=args.price,
            actual_quantity=args.quantity,
            entry_date=args.date,
            broker_reference=args.broker_reference,
            notes=args.notes,
            commission=args.commission,
        )

        for key, value in result.items():
            print(
                f"{key:25}: {value}"
            )

        return

    if args.command == "sell":
        result = engine.execute_sell(
            symbol=args.symbol,
            exit_price=args.price,
            exit_quantity=args.quantity,
            exit_date=args.date,
            broker_reference=args.broker_reference,
            notes=args.notes,
            commission=args.commission,
        )

        for key, value in result.items():
            print(
                f"{key:25}: {value}"
            )


if __name__ == "__main__":
    main()
