from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class LivePortfolioMonitorConfigV1:
    lifecycle_folder: str = "database/portfolio"
    reports_latest_folder: str = "reports/latest"
    output_folder: str = "reports/live_portfolio"
    open_positions_filename: str = "open_positions.csv"
    closed_positions_filename: str = "closed_positions.csv"
    live_positions_filename: str = "live_positions.csv"
    portfolio_summary_filename: str = "live_portfolio_summary.csv"


class LivePortfolioMonitorV1:
    """
    Live Portfolio Monitor V1

    Purpose
    -------
    Reads actual portfolio positions, matches them with latest PSX prices,
    calculates live P/L, detects stop-loss and target events, updates trailing
    stops, and exports a clean institutional live portfolio view.

    This engine does NOT automatically create a real position from a
    READY TO BUY signal. A position becomes live only when it exists in
    database/portfolio/open_positions.csv with an actual entry price and
    actual quantity.

    Supported lifecycle states
    --------------------------
    READY TO BUY
    OPEN
    HOLD
    TARGET 1 HIT
    PARTIAL EXIT
    TARGET 2 HIT
    TRAIL STOP
    STOP LOSS HIT
    FULL EXIT
    CLOSED
    """

    VERSION = "live_portfolio_monitor_v1_0_institutional"

    def __init__(
        self,
        lifecycle_folder: str = "database/portfolio",
        reports_latest_folder: str = "reports/latest",
        output_folder: str = "reports/live_portfolio",
        open_positions_filename: str = "open_positions.csv",
        closed_positions_filename: str = "closed_positions.csv",
        live_positions_filename: str = "live_positions.csv",
        portfolio_summary_filename: str = "live_portfolio_summary.csv",
    ):
        self.config = LivePortfolioMonitorConfigV1(
            lifecycle_folder=lifecycle_folder,
            reports_latest_folder=reports_latest_folder,
            output_folder=output_folder,
            open_positions_filename=open_positions_filename,
            closed_positions_filename=closed_positions_filename,
            live_positions_filename=live_positions_filename,
            portfolio_summary_filename=portfolio_summary_filename,
        )

        self.lifecycle_folder = Path(
            self.config.lifecycle_folder
        )
        self.reports_latest_folder = Path(
            self.config.reports_latest_folder
        )
        self.output_folder = Path(
            self.config.output_folder
        )

        self.lifecycle_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.output_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.open_positions_path = (
            self.lifecycle_folder
            / self.config.open_positions_filename
        )

        self.closed_positions_path = (
            self.lifecycle_folder
            / self.config.closed_positions_filename
        )

        self.live_positions_path = (
            self.output_folder
            / self.config.live_positions_filename
        )

        self.portfolio_summary_path = (
            self.output_folder
            / self.config.portfolio_summary_filename
        )

    # ---------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------

    def run(
        self,
        latest_market_df: pd.DataFrame | None = None,
    ) -> dict:
        open_positions_df = self.load_open_positions()
        closed_positions_df = self.load_closed_positions()

        market_df = (
            self.prepare_market_dataframe(
                latest_market_df
            )
            if latest_market_df is not None
            else self.load_latest_market_data()
        )

        monitored_df = self.monitor_positions(
            open_positions_df=open_positions_df,
            market_df=market_df,
        )

        active_df, newly_closed_df = self.split_active_and_closed(
            monitored_df
        )

        updated_closed_df = self.merge_closed_positions(
            existing_closed_df=closed_positions_df,
            newly_closed_df=newly_closed_df,
        )

        self.save_dataframe(
            active_df,
            self.open_positions_path,
            self.open_position_columns(),
        )

        self.save_dataframe(
            updated_closed_df,
            self.closed_positions_path,
            self.closed_position_columns(),
        )

        self.save_dataframe(
            monitored_df,
            self.live_positions_path,
            self.live_position_columns(),
        )

        summary = self.build_portfolio_summary(
            monitored_df=monitored_df,
            active_df=active_df,
            newly_closed_df=newly_closed_df,
        )

        pd.DataFrame(
            [summary]
        ).to_csv(
            self.portfolio_summary_path,
            index=False,
            encoding="utf-8-sig",
        )

        return {
            "status": "success",
            "engine_version": self.VERSION,
            "open_positions": int(
                len(active_df)
            ),
            "newly_closed_positions": int(
                len(newly_closed_df)
            ),
            "total_live_rows": int(
                len(monitored_df)
            ),
            "live_positions_csv": str(
                self.live_positions_path
            ),
            "open_positions_csv": str(
                self.open_positions_path
            ),
            "closed_positions_csv": str(
                self.closed_positions_path
            ),
            "portfolio_summary_csv": str(
                self.portfolio_summary_path
            ),
            "summary": summary,
            "reason": (
                "Live portfolio monitoring completed successfully"
            ),
        }

    # ---------------------------------------------------------
    # LOADERS
    # ---------------------------------------------------------

    def load_open_positions(
        self,
    ) -> pd.DataFrame:
        return self.read_csv(
            self.open_positions_path
        )

    def load_closed_positions(
        self,
    ) -> pd.DataFrame:
        return self.read_csv(
            self.closed_positions_path
        )

    def load_latest_market_data(
        self,
    ) -> pd.DataFrame:
        candidates = [
            self.reports_latest_folder
            / "top_buys.csv",
            self.reports_latest_folder
            / "trade_lifecycle.csv",
            self.reports_latest_folder
            / "exit_intelligence.csv",
        ]

        frames = []

        for path in candidates:
            df = self.read_csv(path)

            if not df.empty:
                frames.append(df)

        if not frames:
            return pd.DataFrame()

        combined = pd.concat(
            frames,
            ignore_index=True,
            sort=False,
        )

        return self.prepare_market_dataframe(
            combined
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

        return remove_duplicate_columns(df)

    # ---------------------------------------------------------
    # CORE MONITORING
    # ---------------------------------------------------------

    def prepare_market_dataframe(
        self,
        market_df: pd.DataFrame | None,
    ) -> pd.DataFrame:
        if (
            market_df is None
            or not isinstance(
                market_df,
                pd.DataFrame,
            )
            or market_df.empty
        ):
            return pd.DataFrame()

        data = remove_duplicate_columns(
            market_df.copy()
        )

        if "symbol" not in data.columns:
            return pd.DataFrame()

        data["symbol"] = (
            data["symbol"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.strip()
        )

        date_column = first_existing_column(
            data,
            [
                "date",
                "trading_date",
                "signal_date",
            ],
        )

        if date_column:
            data["_parsed_date"] = pd.to_datetime(
                data[date_column],
                format="%d%b%Y",
                errors="coerce",
            )

            fallback = pd.to_datetime(
                data[date_column],
                errors="coerce",
            )

            data["_parsed_date"] = (
                data["_parsed_date"]
                .fillna(fallback)
            )

            data = data.sort_values(
                [
                    "symbol",
                    "_parsed_date",
                ],
                ascending=[
                    True,
                    False,
                ],
            )
        else:
            data = data.sort_values(
                "symbol"
            )

        data = data.drop_duplicates(
            subset=["symbol"],
            keep="first",
        ).reset_index(
            drop=True
        )

        return data

    def monitor_positions(
        self,
        open_positions_df: pd.DataFrame,
        market_df: pd.DataFrame,
    ) -> pd.DataFrame:
        open_positions_df = self.normalize_open_positions(
            open_positions_df
        )

        if open_positions_df.empty:
            return pd.DataFrame(
                columns=self.live_position_columns()
            )

        market_lookup = build_symbol_lookup(
            market_df
        )

        rows = []

        for _, row in open_positions_df.iterrows():
            symbol = upper_text(
                row.get(
                    "symbol",
                    "",
                )
            )

            market_row = market_lookup.get(
                symbol,
                {},
            )

            monitored = self.monitor_single_position(
                position=row,
                market_row=market_row,
            )

            rows.append(monitored)

        result = pd.DataFrame(rows)

        if not result.empty:
            result = result.sort_values(
                [
                    "position_priority",
                    "unrealized_profit_loss_pct",
                ],
                ascending=[
                    True,
                    False,
                ],
            ).reset_index(
                drop=True
            )

        return result

    def monitor_single_position(
        self,
        position: pd.Series,
        market_row: dict,
    ) -> dict:
        now = datetime.now()

        actual_entry_price = first_positive_numeric(
            position,
            [
                "actual_entry_price",
                "average_cost",
                "entry_price",
            ],
        )

        original_quantity = int(
            first_positive_numeric(
                position,
                [
                    "original_quantity",
                    "actual_quantity",
                    "open_quantity",
                    "remaining_quantity",
                ],
            )
        )

        remaining_quantity = int(
            first_positive_numeric(
                position,
                [
                    "remaining_quantity",
                    "open_quantity",
                    "actual_quantity",
                    "original_quantity",
                ],
            )
        )

        if remaining_quantity <= 0:
            remaining_quantity = original_quantity

        current_price = first_positive_numeric_from_dict(
            market_row,
            [
                "close",
                "current_price",
                "exit_current_price",
            ],
        )

        if current_price <= 0:
            current_price = first_positive_numeric(
                position,
                [
                    "current_price",
                    "last_price",
                    "actual_entry_price",
                    "average_cost",
                ],
            )

        initial_stop_loss = first_positive_numeric(
            position,
            [
                "initial_stop_loss",
                "stop_loss",
                "current_stop_loss",
            ],
        )

        current_stop_loss = first_positive_numeric(
            position,
            [
                "current_stop_loss",
                "initial_stop_loss",
                "stop_loss",
            ],
        )

        target_1 = first_positive_numeric(
            position,
            [
                "target_1",
            ],
        )

        target_2 = first_positive_numeric(
            position,
            [
                "target_2",
            ],
        )

        highest_price = max(
            first_positive_numeric(
                position,
                [
                    "highest_price_since_entry",
                    "highest_price",
                ],
            ),
            current_price,
        )

        lowest_price = first_positive_numeric(
            position,
            [
                "lowest_price_since_entry",
                "lowest_price",
            ],
        )

        if lowest_price <= 0:
            lowest_price = current_price

        lowest_price = min(
            lowest_price,
            current_price,
        )

        market_high = first_positive_numeric_from_dict(
            market_row,
            [
                "high",
                "day_high",
            ],
        )

        market_low = first_positive_numeric_from_dict(
            market_row,
            [
                "low",
                "day_low",
            ],
        )

        if market_high > 0:
            highest_price = max(
                highest_price,
                market_high,
            )

        if market_low > 0:
            lowest_price = min(
                lowest_price,
                market_low,
            )

        realized_profit_loss = safe_float(
            position.get(
                "realized_profit_loss",
                0,
            )
        )

        unrealized_profit_loss = (
            (
                current_price
                - actual_entry_price
            )
            * remaining_quantity
            if (
                actual_entry_price > 0
                and remaining_quantity > 0
            )
            else 0.0
        )

        unrealized_profit_loss_pct = (
            (
                current_price
                - actual_entry_price
            )
            / actual_entry_price
            * 100
            if actual_entry_price > 0
            else 0.0
        )

        holding_days = calculate_holding_days(
            position.get(
                "entry_date",
                position.get(
                    "opened_at",
                    "",
                ),
            )
        )

        target_1_hit_before = bool_value(
            position.get(
                "target_1_hit",
                False,
            )
        )

        target_2_hit_before = bool_value(
            position.get(
                "target_2_hit",
                False,
            )
        )

        partial_profit_booked = bool_value(
            position.get(
                "partial_profit_booked",
                False,
            )
        )

        status_result = self.resolve_position_status(
            current_price=current_price,
            actual_entry_price=actual_entry_price,
            current_stop_loss=current_stop_loss,
            target_1=target_1,
            target_2=target_2,
            highest_price=highest_price,
            remaining_quantity=remaining_quantity,
            target_1_hit_before=target_1_hit_before,
            target_2_hit_before=target_2_hit_before,
            partial_profit_booked=partial_profit_booked,
        )

        status = status_result[
            "position_status"
        ]

        event = status_result[
            "position_event"
        ]

        recommended_action = status_result[
            "recommended_action"
        ]

        target_1_hit = status_result[
            "target_1_hit"
        ]

        target_2_hit = status_result[
            "target_2_hit"
        ]

        suggested_trailing_stop = self.calculate_trailing_stop(
            actual_entry_price=actual_entry_price,
            current_price=current_price,
            current_stop_loss=current_stop_loss,
            target_1=target_1,
            target_2=target_2,
            highest_price=highest_price,
            target_1_hit=target_1_hit,
            target_2_hit=target_2_hit,
        )

        effective_stop_loss = max(
            current_stop_loss,
            suggested_trailing_stop,
        )

        risk_amount = (
            max(
                actual_entry_price
                - effective_stop_loss,
                0,
            )
            * remaining_quantity
            if actual_entry_price > 0
            else 0.0
        )

        market_value = (
            current_price
            * remaining_quantity
        )

        cost_value = (
            actual_entry_price
            * remaining_quantity
        )

        stop_distance_pct = (
            (
                current_price
                - effective_stop_loss
            )
            / current_price
            * 100
            if current_price > 0
            else 0.0
        )

        profit_lock_pct = (
            (
                effective_stop_loss
                - actual_entry_price
            )
            / actual_entry_price
            * 100
            if (
                actual_entry_price > 0
                and effective_stop_loss
                > actual_entry_price
            )
            else 0.0
        )

        row = {
            "engine_version": self.VERSION,
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
            "company": clean_text(
                first_valid(
                    position.get(
                        "company"
                    ),
                    market_row.get(
                        "company"
                    ),
                    "",
                )
            ),
            "sector": clean_text(
                first_valid(
                    position.get(
                        "sector"
                    ),
                    market_row.get(
                        "sector"
                    ),
                    "",
                )
            ),
            "entry_date": clean_text(
                position.get(
                    "entry_date",
                    "",
                )
            ),
            "actual_entry_price": round(
                actual_entry_price,
                4,
            ),
            "average_cost": round(
                first_positive_numeric(
                    position,
                    [
                        "average_cost",
                        "actual_entry_price",
                    ],
                ),
                4,
            ),
            "original_quantity": int(
                original_quantity
            ),
            "remaining_quantity": int(
                remaining_quantity
            ),
            "current_price": round(
                current_price,
                4,
            ),
            "market_value": round(
                market_value,
                2,
            ),
            "cost_value": round(
                cost_value,
                2,
            ),
            "initial_stop_loss": round(
                initial_stop_loss,
                4,
            ),
            "current_stop_loss": round(
                effective_stop_loss,
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
            "target_1_hit": bool(
                target_1_hit
            ),
            "target_2_hit": bool(
                target_2_hit
            ),
            "partial_profit_booked": bool(
                partial_profit_booked
            ),
            "highest_price_since_entry": round(
                highest_price,
                4,
            ),
            "lowest_price_since_entry": round(
                lowest_price,
                4,
            ),
            "realized_profit_loss": round(
                realized_profit_loss,
                2,
            ),
            "unrealized_profit_loss": round(
                unrealized_profit_loss,
                2,
            ),
            "unrealized_profit_loss_pct": round(
                unrealized_profit_loss_pct,
                4,
            ),
            "total_profit_loss": round(
                realized_profit_loss
                + unrealized_profit_loss,
                2,
            ),
            "risk_amount_to_stop": round(
                risk_amount,
                2,
            ),
            "stop_distance_pct": round(
                stop_distance_pct,
                4,
            ),
            "profit_lock_pct": round(
                profit_lock_pct,
                4,
            ),
            "holding_days": int(
                holding_days
            ),
            "position_status": status,
            "lifecycle_status": status,
            "position_event": event,
            "recommended_action": recommended_action,
            "position_priority": status_priority(
                status
            ),
            "last_market_date": clean_text(
                first_valid(
                    market_row.get(
                        "date"
                    ),
                    market_row.get(
                        "trading_date"
                    ),
                    "",
                )
            ),
            "last_updated_at": now.isoformat(
                timespec="seconds"
            ),
            "close_reason": status_result[
                "close_reason"
            ],
            "final_exit_price": round(
                current_price,
                4,
            )
            if status in {
                "STOP LOSS HIT",
                "FULL EXIT",
                "CLOSED",
            }
            else 0.0,
            "exit_date": (
                now.strftime(
                    "%Y-%m-%d"
                )
                if status in {
                    "STOP LOSS HIT",
                    "FULL EXIT",
                    "CLOSED",
                }
                else ""
            ),
        }

        return row

    # ---------------------------------------------------------
    # STATUS / EVENT ENGINE
    # ---------------------------------------------------------

    def resolve_position_status(
        self,
        current_price: float,
        actual_entry_price: float,
        current_stop_loss: float,
        target_1: float,
        target_2: float,
        highest_price: float,
        remaining_quantity: int,
        target_1_hit_before: bool,
        target_2_hit_before: bool,
        partial_profit_booked: bool,
    ) -> dict:
        target_1_hit = bool(
            target_1_hit_before
            or (
                target_1 > 0
                and highest_price >= target_1
            )
        )

        target_2_hit = bool(
            target_2_hit_before
            or (
                target_2 > 0
                and highest_price >= target_2
            )
        )

        if remaining_quantity <= 0:
            return {
                "position_status": "CLOSED",
                "position_event": "NO REMAINING QUANTITY",
                "recommended_action": "CLOSED",
                "target_1_hit": target_1_hit,
                "target_2_hit": target_2_hit,
                "close_reason": "Position quantity reached zero",
            }

        if (
            current_stop_loss > 0
            and current_price <= current_stop_loss
        ):
            return {
                "position_status": "STOP LOSS HIT",
                "position_event": "STOP LOSS TRIGGERED",
                "recommended_action": "EXIT NOW",
                "target_1_hit": target_1_hit,
                "target_2_hit": target_2_hit,
                "close_reason": "Current price reached or crossed stop loss",
            }

        if (
            target_2 > 0
            and current_price >= target_2
        ):
            return {
                "position_status": "TARGET 2 HIT",
                "position_event": "TARGET 2 REACHED",
                "recommended_action": "BOOK FULL PROFIT",
                "target_1_hit": True,
                "target_2_hit": True,
                "close_reason": "",
            }

        if target_2_hit:
            return {
                "position_status": "TRAIL STOP",
                "position_event": "TARGET 2 WAS HIT",
                "recommended_action": "TRAIL REMAINING POSITION",
                "target_1_hit": True,
                "target_2_hit": True,
                "close_reason": "",
            }

        if (
            target_1 > 0
            and current_price >= target_1
        ):
            return {
                "position_status": "TARGET 1 HIT",
                "position_event": "TARGET 1 REACHED",
                "recommended_action": "BOOK PARTIAL PROFIT",
                "target_1_hit": True,
                "target_2_hit": target_2_hit,
                "close_reason": "",
            }

        if (
            target_1_hit
            or partial_profit_booked
        ):
            return {
                "position_status": "PARTIAL EXIT",
                "position_event": "PARTIAL PROFIT PHASE",
                "recommended_action": "HOLD WITH TRAILING STOP",
                "target_1_hit": True,
                "target_2_hit": target_2_hit,
                "close_reason": "",
            }

        if (
            actual_entry_price > 0
            and current_price
            >= actual_entry_price * 1.03
        ):
            return {
                "position_status": "HOLD",
                "position_event": "PROFITABLE OPEN POSITION",
                "recommended_action": "MOVE STOP TO BREAKEVEN",
                "target_1_hit": target_1_hit,
                "target_2_hit": target_2_hit,
                "close_reason": "",
            }

        return {
            "position_status": "OPEN",
            "position_event": "ACTIVE POSITION",
            "recommended_action": "HOLD",
            "target_1_hit": target_1_hit,
            "target_2_hit": target_2_hit,
            "close_reason": "",
        }

    def calculate_trailing_stop(
        self,
        actual_entry_price: float,
        current_price: float,
        current_stop_loss: float,
        target_1: float,
        target_2: float,
        highest_price: float,
        target_1_hit: bool,
        target_2_hit: bool,
    ) -> float:
        if actual_entry_price <= 0:
            return current_stop_loss

        trailing_stop = current_stop_loss

        gain_pct = (
            (
                current_price
                - actual_entry_price
            )
            / actual_entry_price
            * 100
        )

        if gain_pct >= 3:
            trailing_stop = max(
                trailing_stop,
                actual_entry_price,
            )

        if target_1_hit:
            trailing_stop = max(
                trailing_stop,
                actual_entry_price * 1.01,
            )

        if (
            target_1 > 0
            and highest_price >= target_1
        ):
            trailing_stop = max(
                trailing_stop,
                target_1 * 0.97,
            )

        if target_2_hit:
            trailing_stop = max(
                trailing_stop,
                highest_price * 0.96,
            )

        if (
            target_2 > 0
            and highest_price >= target_2
        ):
            trailing_stop = max(
                trailing_stop,
                target_2 * 0.98,
            )

        return round(
            trailing_stop,
            4,
        )

    # ---------------------------------------------------------
    # POSITION OUTPUT MANAGEMENT
    # ---------------------------------------------------------

    def split_active_and_closed(
        self,
        monitored_df: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        if monitored_df.empty:
            return (
                pd.DataFrame(
                    columns=self.open_position_columns()
                ),
                pd.DataFrame(
                    columns=self.closed_position_columns()
                ),
            )

        closed_statuses = {
            "STOP LOSS HIT",
            "FULL EXIT",
            "CLOSED",
        }

        closed_mask = (
            monitored_df["position_status"]
            .fillna("")
            .astype(str)
            .str.upper()
            .isin(closed_statuses)
        )

        active_df = monitored_df[
            ~closed_mask
        ].copy()

        closed_df = monitored_df[
            closed_mask
        ].copy()

        return (
            active_df.reset_index(
                drop=True
            ),
            closed_df.reset_index(
                drop=True
            ),
        )

    def merge_closed_positions(
        self,
        existing_closed_df: pd.DataFrame,
        newly_closed_df: pd.DataFrame,
    ) -> pd.DataFrame:
        existing_closed_df = remove_duplicate_columns(
            existing_closed_df
        )

        newly_closed_df = remove_duplicate_columns(
            newly_closed_df
        )

        if existing_closed_df.empty:
            combined = newly_closed_df.copy()
        elif newly_closed_df.empty:
            combined = existing_closed_df.copy()
        else:
            combined = pd.concat(
                [
                    existing_closed_df,
                    newly_closed_df,
                ],
                ignore_index=True,
                sort=False,
            )

        if combined.empty:
            return pd.DataFrame(
                columns=self.closed_position_columns()
            )

        subset = (
            ["trade_id"]
            if (
                "trade_id" in combined.columns
                and combined["trade_id"]
                .fillna("")
                .astype(str)
                .str.strip()
                .ne("")
                .any()
            )
            else [
                "symbol",
                "entry_date",
                "actual_entry_price",
            ]
        )

        existing_subset = [
            column
            for column in subset
            if column in combined.columns
        ]

        if existing_subset:
            combined = combined.drop_duplicates(
                subset=existing_subset,
                keep="last",
            )

        return combined.reset_index(
            drop=True
        )

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
            "trade_id": "",
            "symbol": "",
            "company": "",
            "sector": "",
            "entry_date": "",
            "actual_entry_price": 0.0,
            "average_cost": 0.0,
            "original_quantity": 0,
            "actual_quantity": 0,
            "open_quantity": 0,
            "remaining_quantity": 0,
            "initial_stop_loss": 0.0,
            "current_stop_loss": 0.0,
            "stop_loss": 0.0,
            "target_1": 0.0,
            "target_2": 0.0,
            "target_1_hit": False,
            "target_2_hit": False,
            "partial_profit_booked": False,
            "highest_price_since_entry": 0.0,
            "lowest_price_since_entry": 0.0,
            "realized_profit_loss": 0.0,
            "position_status": "OPEN",
        }

        for column, default in defaults.items():
            if column not in df.columns:
                df[column] = default

        df["symbol"] = (
            df["symbol"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.strip()
        )

        return df

    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------

    def build_portfolio_summary(
        self,
        monitored_df: pd.DataFrame,
        active_df: pd.DataFrame,
        newly_closed_df: pd.DataFrame,
    ) -> dict:
        total_market_value = numeric_sum(
            monitored_df,
            "market_value",
        )

        total_cost_value = numeric_sum(
            monitored_df,
            "cost_value",
        )

        unrealized_profit_loss = numeric_sum(
            active_df,
            "unrealized_profit_loss",
        )

        realized_profit_loss = numeric_sum(
            monitored_df,
            "realized_profit_loss",
        )

        total_profit_loss = (
            unrealized_profit_loss
            + realized_profit_loss
        )

        winners = int(
            (
                numeric_series(
                    active_df,
                    "unrealized_profit_loss",
                )
                > 0
            ).sum()
        )

        losers = int(
            (
                numeric_series(
                    active_df,
                    "unrealized_profit_loss",
                )
                < 0
            ).sum()
        )

        total_risk_to_stop = numeric_sum(
            active_df,
            "risk_amount_to_stop",
        )

        return {
            "engine_version": self.VERSION,
            "generated_at": datetime.now().isoformat(
                timespec="seconds"
            ),
            "total_monitored_positions": int(
                len(monitored_df)
            ),
            "active_positions": int(
                len(active_df)
            ),
            "newly_closed_positions": int(
                len(newly_closed_df)
            ),
            "winning_open_positions": winners,
            "losing_open_positions": losers,
            "total_cost_value": round(
                total_cost_value,
                2,
            ),
            "total_market_value": round(
                total_market_value,
                2,
            ),
            "unrealized_profit_loss": round(
                unrealized_profit_loss,
                2,
            ),
            "realized_profit_loss": round(
                realized_profit_loss,
                2,
            ),
            "total_profit_loss": round(
                total_profit_loss,
                2,
            ),
            "total_risk_to_stop": round(
                total_risk_to_stop,
                2,
            ),
            "portfolio_return_pct": round(
                (
                    total_profit_loss
                    / total_cost_value
                    * 100
                )
                if total_cost_value > 0
                else 0.0,
                4,
            ),
        }

    # ---------------------------------------------------------
    # COLUMN SCHEMAS
    # ---------------------------------------------------------

    def live_position_columns(
        self,
    ) -> list[str]:
        return [
            "engine_version",
            "trade_id",
            "symbol",
            "company",
            "sector",
            "entry_date",
            "actual_entry_price",
            "average_cost",
            "original_quantity",
            "remaining_quantity",
            "current_price",
            "market_value",
            "cost_value",
            "initial_stop_loss",
            "current_stop_loss",
            "target_1",
            "target_2",
            "target_1_hit",
            "target_2_hit",
            "partial_profit_booked",
            "highest_price_since_entry",
            "lowest_price_since_entry",
            "realized_profit_loss",
            "unrealized_profit_loss",
            "unrealized_profit_loss_pct",
            "total_profit_loss",
            "risk_amount_to_stop",
            "stop_distance_pct",
            "profit_lock_pct",
            "holding_days",
            "position_status",
            "lifecycle_status",
            "position_event",
            "recommended_action",
            "position_priority",
            "last_market_date",
            "last_updated_at",
            "close_reason",
            "final_exit_price",
            "exit_date",
        ]

    def open_position_columns(
        self,
    ) -> list[str]:
        return self.live_position_columns()

    def closed_position_columns(
        self,
    ) -> list[str]:
        return self.live_position_columns()

    # ---------------------------------------------------------
    # SAVE HELPERS
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


def run_live_portfolio_monitor_v1(
    latest_market_df: pd.DataFrame | None = None,
    lifecycle_folder: str = "database/portfolio",
    reports_latest_folder: str = "reports/latest",
    output_folder: str = "reports/live_portfolio",
) -> dict:
    engine = LivePortfolioMonitorV1(
        lifecycle_folder=lifecycle_folder,
        reports_latest_folder=reports_latest_folder,
        output_folder=output_folder,
    )

    return engine.run(
        latest_market_df=latest_market_df
    )


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


def build_symbol_lookup(
    df: pd.DataFrame,
) -> dict[str, dict]:
    if (
        df is None
        or df.empty
        or "symbol" not in df.columns
    ):
        return {}

    lookup: dict[str, dict] = {}

    for _, row in df.iterrows():
        symbol = upper_text(
            row.get(
                "symbol",
                "",
            )
        )

        if symbol:
            lookup[symbol] = row.to_dict()

    return lookup


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


def first_positive_numeric_from_dict(
    row: dict,
    columns: list[str],
) -> float:
    for column in columns:
        number = safe_float(
            row.get(
                column,
                None,
            ),
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


def numeric_series(
    df: pd.DataFrame,
    column: str,
) -> pd.Series:
    if (
        df is None
        or df.empty
        or column not in df.columns
    ):
        return pd.Series(
            0.0,
            index=(
                df.index
                if isinstance(
                    df,
                    pd.DataFrame,
                )
                else None
            ),
            dtype=float,
        )

    return pd.to_numeric(
        df[column],
        errors="coerce",
    ).fillna(
        0.0
    )


def numeric_sum(
    df: pd.DataFrame,
    column: str,
) -> float:
    return float(
        numeric_series(
            df,
            column,
        ).sum()
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
        return bool(value)

    return str(value).strip().upper() in {
        "TRUE",
        "1",
        "YES",
        "Y",
    }


def calculate_holding_days(
    entry_date: Any,
) -> int:
    parsed = pd.to_datetime(
        entry_date,
        errors="coerce",
    )

    if pd.isna(parsed):
        return 0

    today = pd.Timestamp.now().normalize()
    entry = parsed.normalize()

    return max(
        int(
            (
                today - entry
            ).days
        ),
        0,
    )


def status_priority(
    status: str,
) -> int:
    priorities = {
        "STOP LOSS HIT": 1,
        "TARGET 2 HIT": 2,
        "TARGET 1 HIT": 3,
        "TRAIL STOP": 4,
        "PARTIAL EXIT": 5,
        "HOLD": 6,
        "OPEN": 7,
        "CLOSED": 99,
    }

    return priorities.get(
        upper_text(status),
        50,
    )


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
        "remaining_quantity",
        "holding_days",
        "position_priority",
    }

    numeric_columns = {
        "actual_entry_price",
        "average_cost",
        "current_price",
        "market_value",
        "cost_value",
        "initial_stop_loss",
        "current_stop_loss",
        "target_1",
        "target_2",
        "highest_price_since_entry",
        "lowest_price_since_entry",
        "realized_profit_loss",
        "unrealized_profit_loss",
        "unrealized_profit_loss_pct",
        "total_profit_loss",
        "risk_amount_to_stop",
        "stop_distance_pct",
        "profit_lock_pct",
        "final_exit_price",
    }

    if column in boolean_columns:
        return False

    if column in integer_columns:
        return 0

    if column in numeric_columns:
        return 0.0

    return ""