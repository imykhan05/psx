from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class TradeJournalConfigV1:
    portfolio_folder: str = "database/portfolio"
    reports_folder: str = "reports/trade_journal"
    latest_reports_folder: str = "reports/latest"
    execution_log_filename: str = "execution_log.csv"
    open_positions_filename: str = "open_positions.csv"
    closed_positions_filename: str = "closed_positions.csv"
    pending_entries_filename: str = "pending_entries.csv"
    journal_filename: str = "trade_journal.csv"
    monthly_summary_filename: str = "monthly_trade_journal.csv"
    review_filename: str = "trade_review_queue.csv"
    summary_filename: str = "trade_journal_summary.csv"


class TradeJournalProV1:
    """
    Trade Journal Pro V1

    Builds an institutional trading journal from actual execution records,
    open positions, closed positions and current recommendation context.

    The engine does not execute or modify trades.
    """

    VERSION = "trade_journal_pro_v1_0_institutional"

    def __init__(
        self,
        portfolio_folder: str = "database/portfolio",
        reports_folder: str = "reports/trade_journal",
        latest_reports_folder: str = "reports/latest",
    ):
        self.config = TradeJournalConfigV1(
            portfolio_folder=portfolio_folder,
            reports_folder=reports_folder,
            latest_reports_folder=latest_reports_folder,
        )

        self.portfolio_folder = Path(
            self.config.portfolio_folder
        )
        self.reports_folder = Path(
            self.config.reports_folder
        )
        self.latest_reports_folder = Path(
            self.config.latest_reports_folder
        )

        self.portfolio_folder.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.reports_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.execution_log_path = (
            self.portfolio_folder
            / self.config.execution_log_filename
        )
        self.open_positions_path = (
            self.portfolio_folder
            / self.config.open_positions_filename
        )
        self.closed_positions_path = (
            self.portfolio_folder
            / self.config.closed_positions_filename
        )
        self.pending_entries_path = (
            self.portfolio_folder
            / self.config.pending_entries_filename
        )

        self.journal_path = (
            self.reports_folder
            / self.config.journal_filename
        )
        self.monthly_summary_path = (
            self.reports_folder
            / self.config.monthly_summary_filename
        )
        self.review_path = (
            self.reports_folder
            / self.config.review_filename
        )
        self.summary_path = (
            self.reports_folder
            / self.config.summary_filename
        )

    # ---------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------

    def run(
        self,
        starting_capital: float = 50000.0,
        recommendation_df: pd.DataFrame | None = None,
    ) -> dict:
        starting_capital = positive_float(
            starting_capital,
            "starting_capital",
        )

        execution_df = self.read_csv(
            self.execution_log_path
        )
        open_df = self.read_csv(
            self.open_positions_path
        )
        closed_df = self.read_csv(
            self.closed_positions_path
        )
        pending_df = self.read_csv(
            self.pending_entries_path
        )

        recommendation_df = remove_duplicate_columns(
            recommendation_df
        )

        if recommendation_df.empty:
            recommendation_df = self.load_latest_recommendations()

        journal_df = self.build_trade_journal(
            execution_df=execution_df,
            open_df=open_df,
            closed_df=closed_df,
            pending_df=pending_df,
            recommendation_df=recommendation_df,
            starting_capital=starting_capital,
        )

        monthly_df = self.build_monthly_summary(
            journal_df
        )

        review_df = self.build_review_queue(
            journal_df
        )

        summary = self.build_summary(
            journal_df=journal_df,
            starting_capital=starting_capital,
        )

        self.save_dataframe(
            journal_df,
            self.journal_path,
            self.journal_columns(),
        )

        self.save_dataframe(
            monthly_df,
            self.monthly_summary_path,
            self.monthly_columns(),
        )

        self.save_dataframe(
            review_df,
            self.review_path,
            self.review_columns(),
        )

        pd.DataFrame(
            [summary]
        ).to_csv(
            self.summary_path,
            index=False,
            encoding="utf-8-sig",
        )

        return {
            "status": "success",
            "engine_version": self.VERSION,
            "total_trades": int(
                len(journal_df)
            ),
            "open_trades": int(
                (
                    journal_df.get(
                        "trade_status",
                        pd.Series(dtype=str),
                    )
                    .astype(str)
                    .str.upper()
                    .isin(
                        [
                            "OPEN",
                            "PARTIAL EXIT",
                            "HOLD",
                            "TRAIL STOP",
                        ]
                    )
                ).sum()
            )
            if not journal_df.empty
            else 0,
            "closed_trades": int(
                (
                    journal_df.get(
                        "trade_status",
                        pd.Series(dtype=str),
                    )
                    .astype(str)
                    .str.upper()
                    .isin(
                        [
                            "CLOSED",
                            "STOP LOSS HIT",
                            "FULL EXIT",
                        ]
                    )
                ).sum()
            )
            if not journal_df.empty
            else 0,
            "win_rate_pct": summary[
                "win_rate_pct"
            ],
            "realized_profit_loss": summary[
                "realized_profit_loss"
            ],
            "journal_csv": str(
                self.journal_path
            ),
            "monthly_summary_csv": str(
                self.monthly_summary_path
            ),
            "review_queue_csv": str(
                self.review_path
            ),
            "summary_csv": str(
                self.summary_path
            ),
            "reason": (
                "Institutional trade journal generated successfully"
            ),
        }

    # ---------------------------------------------------------
    # LOADERS
    # ---------------------------------------------------------

    def load_latest_recommendations(
        self,
    ) -> pd.DataFrame:
        candidates = [
            self.latest_reports_folder
            / "top_buys.csv",
            self.latest_reports_folder
            / "trade_lifecycle.csv",
            self.latest_reports_folder
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

        if "symbol" in combined.columns:
            combined["symbol"] = (
                combined["symbol"]
                .fillna("")
                .astype(str)
                .str.upper()
                .str.strip()
            )

            combined = combined.drop_duplicates(
                subset=["symbol"],
                keep="first",
            )

        return remove_duplicate_columns(
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
            return remove_duplicate_columns(
                pd.read_csv(path)
            )
        except (
            pd.errors.EmptyDataError,
            pd.errors.ParserError,
            UnicodeDecodeError,
        ):
            return pd.DataFrame()

    # ---------------------------------------------------------
    # JOURNAL BUILDER
    # ---------------------------------------------------------

    def build_trade_journal(
        self,
        execution_df: pd.DataFrame,
        open_df: pd.DataFrame,
        closed_df: pd.DataFrame,
        pending_df: pd.DataFrame,
        recommendation_df: pd.DataFrame,
        starting_capital: float,
    ) -> pd.DataFrame:
        trade_ids = set()

        for df in [
            execution_df,
            open_df,
            closed_df,
        ]:
            if (
                not df.empty
                and "trade_id" in df.columns
            ):
                trade_ids.update(
                    df["trade_id"]
                    .dropna()
                    .astype(str)
                    .str.strip()
                    .tolist()
                )

        trade_ids = {
            trade_id
            for trade_id in trade_ids
            if trade_id
        }

        if not trade_ids:
            return pd.DataFrame(
                columns=self.journal_columns()
            )

        execution_lookup = group_by_trade_id(
            execution_df
        )
        open_lookup = row_lookup(
            open_df,
            "trade_id",
        )
        closed_lookup = row_lookup(
            closed_df,
            "trade_id",
        )
        recommendation_lookup = row_lookup(
            recommendation_df,
            "symbol",
            uppercase=True,
        )
        pending_lookup = row_lookup(
            pending_df,
            "symbol",
            uppercase=True,
        )

        rows = []

        for trade_id in sorted(
            trade_ids
        ):
            executions = execution_lookup.get(
                trade_id,
                pd.DataFrame(),
            )

            open_row = open_lookup.get(
                trade_id,
                {},
            )

            closed_row = closed_lookup.get(
                trade_id,
                {},
            )

            base_row = (
                closed_row
                if closed_row
                else open_row
            )

            symbol = upper_text(
                first_valid(
                    base_row.get(
                        "symbol"
                    ),
                    first_non_empty_from_df(
                        executions,
                        "symbol",
                    ),
                    "",
                )
            )

            recommendation = recommendation_lookup.get(
                symbol,
                {},
            )

            pending = pending_lookup.get(
                symbol,
                {},
            )

            buy_executions = filter_actions(
                executions,
                ["BUY EXECUTED"],
            )

            sell_executions = filter_actions(
                executions,
                [
                    "PARTIAL SELL EXECUTED",
                    "FULL SELL EXECUTED",
                ],
            )

            entry_date = clean_text(
                first_valid(
                    base_row.get(
                        "entry_date"
                    ),
                    first_non_empty_from_df(
                        buy_executions,
                        "entry_date",
                    ),
                    "",
                )
            )

            exit_date = clean_text(
                first_valid(
                    base_row.get(
                        "exit_date"
                    ),
                    first_non_empty_from_df(
                        sell_executions,
                        "exit_date",
                        last=True,
                    ),
                    "",
                )
            )

            entry_price = first_positive_numeric_from_sources(
                [
                    base_row,
                    dataframe_last_row(
                        buy_executions
                    ),
                    pending,
                ],
                [
                    "actual_entry_price",
                    "entry_price",
                    "executed_entry_price",
                    "adjusted_entry_price",
                ],
            )

            exit_price = first_positive_numeric_from_sources(
                [
                    base_row,
                    dataframe_last_row(
                        sell_executions
                    ),
                ],
                [
                    "final_exit_price",
                    "last_exit_price",
                    "exit_price",
                ],
            )

            original_quantity = int(
                first_positive_numeric_from_sources(
                    [
                        base_row,
                        dataframe_last_row(
                            buy_executions
                        ),
                        pending,
                    ],
                    [
                        "original_quantity",
                        "actual_quantity",
                        "executed_quantity",
                        "portfolio_quantity",
                        "quantity",
                    ],
                )
            )

            remaining_quantity = int(
                first_positive_numeric_from_sources(
                    [
                        base_row,
                    ],
                    [
                        "remaining_quantity",
                        "open_quantity",
                    ],
                )
            )

            realized_profit_loss = safe_float(
                first_valid(
                    base_row.get(
                        "realized_profit_loss"
                    ),
                    numeric_sum(
                        sell_executions,
                        "profit_loss",
                    ),
                    0,
                )
            )

            unrealized_profit_loss = safe_float(
                base_row.get(
                    "unrealized_profit_loss",
                    0,
                )
            )

            total_profit_loss = (
                realized_profit_loss
                + unrealized_profit_loss
            )

            trade_status = clean_text(
                first_valid(
                    base_row.get(
                        "position_status"
                    ),
                    base_row.get(
                        "lifecycle_status"
                    ),
                    (
                        "CLOSED"
                        if exit_date
                        else "OPEN"
                    ),
                )
            ).upper()

            holding_days = int(
                safe_float(
                    first_valid(
                        base_row.get(
                            "holding_days"
                        ),
                        base_row.get(
                            "holding_days_numeric"
                        ),
                        calculate_holding_days(
                            entry_date,
                            exit_date,
                        ),
                    )
                )
            )

            invested_amount = (
                entry_price
                * original_quantity
            )

            return_pct = (
                total_profit_loss
                / invested_amount
                * 100
                if invested_amount > 0
                else 0.0
            )

            capital_return_pct = (
                total_profit_loss
                / starting_capital
                * 100
                if starting_capital > 0
                else 0.0
            )

            stop_loss = first_positive_numeric_from_sources(
                [
                    base_row,
                    recommendation,
                    pending,
                ],
                [
                    "current_stop_loss",
                    "initial_stop_loss",
                    "stop_loss",
                ],
            )

            target_1 = first_positive_numeric_from_sources(
                [
                    base_row,
                    recommendation,
                    pending,
                ],
                ["target_1"],
            )

            target_2 = first_positive_numeric_from_sources(
                [
                    base_row,
                    recommendation,
                    pending,
                ],
                ["target_2"],
            )

            close_reason = clean_text(
                first_valid(
                    base_row.get(
                        "close_reason"
                    ),
                    last_non_empty_from_df(
                        sell_executions,
                        "notes",
                    ),
                    "",
                )
            )

            why_bought = self.generate_buy_reason(
                recommendation=recommendation,
                pending=pending,
            )

            why_sold = self.generate_sell_reason(
                trade_status=trade_status,
                close_reason=close_reason,
                exit_price=exit_price,
                stop_loss=stop_loss,
                target_1=target_1,
                target_2=target_2,
            )

            trade_result = classify_trade_result(
                total_profit_loss=total_profit_loss,
                trade_status=trade_status,
            )

            mistake_flag, mistake_notes = detect_trade_mistake(
                entry_price=entry_price,
                planned_entry=first_positive_numeric_from_sources(
                    [
                        base_row,
                        pending,
                    ],
                    [
                        "planned_entry_price",
                        "adjusted_entry_price",
                        "suggested_entry_price",
                    ],
                ),
                exit_price=exit_price,
                stop_loss=stop_loss,
                target_1=target_1,
                target_2=target_2,
                trade_status=trade_status,
                total_profit_loss=total_profit_loss,
            )

            lesson = build_trade_lesson(
                trade_result=trade_result,
                mistake_flag=mistake_flag,
                mistake_notes=mistake_notes,
                why_sold=why_sold,
            )

            rows.append({
                "trade_id": trade_id,
                "symbol": symbol,
                "company": clean_text(
                    first_valid(
                        base_row.get(
                            "company"
                        ),
                        recommendation.get(
                            "company"
                        ),
                        pending.get(
                            "company"
                        ),
                        "",
                    )
                ),
                "sector": clean_text(
                    first_valid(
                        base_row.get(
                            "sector"
                        ),
                        recommendation.get(
                            "sector"
                        ),
                        pending.get(
                            "sector"
                        ),
                        "",
                    )
                ),
                "strategy": infer_strategy(
                    recommendation
                ),
                "entry_date": entry_date,
                "exit_date": exit_date,
                "entry_price": round(
                    entry_price,
                    4,
                ),
                "exit_price": round(
                    exit_price,
                    4,
                ),
                "original_quantity": original_quantity,
                "remaining_quantity": remaining_quantity,
                "invested_amount": round(
                    invested_amount,
                    2,
                ),
                "stop_loss": round(
                    stop_loss,
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
                "realized_profit_loss": round(
                    realized_profit_loss,
                    2,
                ),
                "unrealized_profit_loss": round(
                    unrealized_profit_loss,
                    2,
                ),
                "total_profit_loss": round(
                    total_profit_loss,
                    2,
                ),
                "return_pct": round(
                    return_pct,
                    4,
                ),
                "capital_return_pct": round(
                    capital_return_pct,
                    4,
                ),
                "holding_days": holding_days,
                "trade_status": trade_status,
                "trade_result": trade_result,
                "final_decision": clean_text(
                    recommendation.get(
                        "final_decision",
                        "",
                    )
                ),
                "buy_probability": round(
                    safe_float(
                        recommendation.get(
                            "buy_probability",
                            0,
                        )
                    ),
                    2,
                ),
                "consensus_score": round(
                    safe_float(
                        recommendation.get(
                            "consensus_score",
                            0,
                        )
                    ),
                    2,
                ),
                "confidence": round(
                    first_positive_numeric_from_sources(
                        [
                            recommendation,
                            pending,
                        ],
                        [
                            "confidence",
                            "confidence_v3",
                            "consensus_confidence",
                            "buy_probability",
                        ],
                    ),
                    2,
                ),
                "risk_permission": clean_text(
                    recommendation.get(
                        "risk_permission",
                        "",
                    )
                ),
                "entry_timing_action": clean_text(
                    recommendation.get(
                        "entry_timing_action",
                        "",
                    )
                ),
                "exit_action": clean_text(
                    recommendation.get(
                        "exit_action",
                        "",
                    )
                ),
                "why_bought": why_bought,
                "why_sold": why_sold,
                "mistake_flag": bool(
                    mistake_flag
                ),
                "mistake_notes": mistake_notes,
                "lesson_learned": lesson,
                "psychology_notes": clean_text(
                    first_non_empty_from_df(
                        executions,
                        "notes",
                    )
                ),
                "entry_screenshot": "",
                "exit_screenshot": "",
                "manual_review_status": (
                    "REVIEW REQUIRED"
                    if trade_status in {
                        "CLOSED",
                        "FULL EXIT",
                        "STOP LOSS HIT",
                    }
                    else "OPEN TRADE"
                ),
                "journal_updated_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
            })

        result = pd.DataFrame(
            rows
        )

        if not result.empty:
            result["_date"] = pd.to_datetime(
                result["entry_date"],
                errors="coerce",
            )

            result = result.sort_values(
                [
                    "_date",
                    "trade_id",
                ],
                ascending=[
                    False,
                    True,
                ],
            ).drop(
                columns=["_date"]
            ).reset_index(
                drop=True
            )

        return result

    # ---------------------------------------------------------
    # REASONS / REVIEW
    # ---------------------------------------------------------

    def generate_buy_reason(
        self,
        recommendation: dict,
        pending: dict,
    ) -> str:
        parts = []

        for value in [
            recommendation.get(
                "consensus_reason"
            ),
            recommendation.get(
                "decision_reason"
            ),
            recommendation.get(
                "institutional_v5_reason"
            ),
            pending.get(
                "position_reason"
            ),
        ]:
            text = clean_text(
                value
            )

            if text and text not in parts:
                parts.append(text)

        if not parts:
            parts.append(
                "Manual order executed from an approved pending recommendation."
            )

        return " | ".join(
            parts
        )

    def generate_sell_reason(
        self,
        trade_status: str,
        close_reason: str,
        exit_price: float,
        stop_loss: float,
        target_1: float,
        target_2: float,
    ) -> str:
        if close_reason:
            return close_reason

        if (
            exit_price > 0
            and target_2 > 0
            and exit_price >= target_2
        ):
            return "Full profit booked at or above Target 2."

        if (
            exit_price > 0
            and target_1 > 0
            and exit_price >= target_1
        ):
            return "Partial or full profit booked at or above Target 1."

        if (
            exit_price > 0
            and stop_loss > 0
            and exit_price <= stop_loss
        ):
            return "Position exited at or below stop loss."

        if trade_status in {
            "OPEN",
            "HOLD",
            "PARTIAL EXIT",
            "TRAIL STOP",
        }:
            return "Trade remains active."

        return "Manual exit recorded."

    # ---------------------------------------------------------
    # MONTHLY SUMMARY
    # ---------------------------------------------------------

    def build_monthly_summary(
        self,
        journal_df: pd.DataFrame,
    ) -> pd.DataFrame:
        if journal_df.empty:
            return pd.DataFrame(
                columns=self.monthly_columns()
            )

        working = journal_df.copy()

        working["_date"] = pd.to_datetime(
            working["exit_date"].where(
                working["exit_date"]
                .fillna("")
                .astype(str)
                .str.strip()
                .ne(""),
                working["entry_date"],
            ),
            errors="coerce",
        )

        working = working[
            working["_date"].notna()
        ].copy()

        if working.empty:
            return pd.DataFrame(
                columns=self.monthly_columns()
            )

        working["month"] = (
            working["_date"]
            .dt.to_period("M")
            .astype(str)
        )

        rows = []

        for month, group in working.groupby(
            "month",
            sort=True,
        ):
            closed_mask = (
                group["trade_status"]
                .astype(str)
                .str.upper()
                .isin(
                    [
                        "CLOSED",
                        "FULL EXIT",
                        "STOP LOSS HIT",
                    ]
                )
            )

            closed_group = group[
                closed_mask
            ].copy()

            wins = int(
                (
                    numeric_series(
                        closed_group,
                        "realized_profit_loss",
                    )
                    > 0
                ).sum()
            )

            losses = int(
                (
                    numeric_series(
                        closed_group,
                        "realized_profit_loss",
                    )
                    < 0
                ).sum()
            )

            closed_count = int(
                len(
                    closed_group
                )
            )

            rows.append({
                "month": month,
                "total_trades": int(
                    len(group)
                ),
                "closed_trades": closed_count,
                "open_trades": int(
                    len(group)
                    - closed_count
                ),
                "winning_trades": wins,
                "losing_trades": losses,
                "win_rate_pct": round(
                    (
                        wins
                        / closed_count
                        * 100
                    )
                    if closed_count > 0
                    else 0.0,
                    4,
                ),
                "realized_profit_loss": round(
                    numeric_sum(
                        closed_group,
                        "realized_profit_loss",
                    ),
                    2,
                ),
                "unrealized_profit_loss": round(
                    numeric_sum(
                        group,
                        "unrealized_profit_loss",
                    ),
                    2,
                ),
                "average_return_pct": round(
                    numeric_series(
                        closed_group,
                        "return_pct",
                    ).mean()
                    if not closed_group.empty
                    else 0.0,
                    4,
                ),
                "best_trade_profit_loss": round(
                    numeric_series(
                        group,
                        "total_profit_loss",
                    ).max(),
                    2,
                ),
                "worst_trade_profit_loss": round(
                    numeric_series(
                        group,
                        "total_profit_loss",
                    ).min(),
                    2,
                ),
                "mistakes_detected": int(
                    group["mistake_flag"]
                    .fillna(False)
                    .astype(bool)
                    .sum()
                ),
            })

        return pd.DataFrame(
            rows,
            columns=self.monthly_columns(),
        )

    # ---------------------------------------------------------
    # REVIEW QUEUE
    # ---------------------------------------------------------

    def build_review_queue(
        self,
        journal_df: pd.DataFrame,
    ) -> pd.DataFrame:
        if journal_df.empty:
            return pd.DataFrame(
                columns=self.review_columns()
            )

        review_mask = (
            journal_df["manual_review_status"]
            .astype(str)
            .str.upper()
            .eq("REVIEW REQUIRED")
            | journal_df["mistake_flag"]
            .fillna(False)
            .astype(bool)
        )

        review = journal_df[
            review_mask
        ][
            [
                "trade_id",
                "symbol",
                "company",
                "strategy",
                "trade_status",
                "trade_result",
                "realized_profit_loss",
                "return_pct",
                "why_bought",
                "why_sold",
                "mistake_flag",
                "mistake_notes",
                "lesson_learned",
                "manual_review_status",
            ]
        ].copy()

        review["review_priority"] = review.apply(
            lambda row: (
                1
                if bool(
                    row.get(
                        "mistake_flag",
                        False,
                    )
                )
                else 2
            ),
            axis=1,
        )

        review["review_action"] = review.apply(
            lambda row: (
                "Review mistake and update process rule"
                if bool(
                    row.get(
                        "mistake_flag",
                        False,
                    )
                )
                else "Complete post-trade review"
            ),
            axis=1,
        )

        return review[
            self.review_columns()
        ].sort_values(
            [
                "review_priority",
                "trade_id",
            ]
        ).reset_index(
            drop=True
        )

    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------

    def build_summary(
        self,
        journal_df: pd.DataFrame,
        starting_capital: float,
    ) -> dict:
        if journal_df.empty:
            return {
                "engine_version": self.VERSION,
                "generated_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
                "starting_capital": round(
                    starting_capital,
                    2,
                ),
                "total_trades": 0,
                "open_trades": 0,
                "closed_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate_pct": 0.0,
                "realized_profit_loss": 0.0,
                "unrealized_profit_loss": 0.0,
                "total_profit_loss": 0.0,
                "average_return_pct": 0.0,
                "mistakes_detected": 0,
                "journal_health": "NO DATA",
            }

        closed_mask = (
            journal_df["trade_status"]
            .astype(str)
            .str.upper()
            .isin(
                [
                    "CLOSED",
                    "FULL EXIT",
                    "STOP LOSS HIT",
                ]
            )
        )

        open_mask = ~closed_mask

        closed_df = journal_df[
            closed_mask
        ]

        wins = int(
            (
                numeric_series(
                    closed_df,
                    "realized_profit_loss",
                )
                > 0
            ).sum()
        )

        losses = int(
            (
                numeric_series(
                    closed_df,
                    "realized_profit_loss",
                )
                < 0
            ).sum()
        )

        closed_count = int(
            len(
                closed_df
            )
        )

        mistakes = int(
            journal_df["mistake_flag"]
            .fillna(False)
            .astype(bool)
            .sum()
        )

        completion_score = max(
            0.0,
            100
            - mistakes * 10
            - int(
                (
                    journal_df["manual_review_status"]
                    .astype(str)
                    .str.upper()
                    .eq("REVIEW REQUIRED")
                ).sum()
            ) * 5,
        )

        return {
            "engine_version": self.VERSION,
            "generated_at": datetime.now().isoformat(
                timespec="seconds"
            ),
            "starting_capital": round(
                starting_capital,
                2,
            ),
            "total_trades": int(
                len(
                    journal_df
                )
            ),
            "open_trades": int(
                open_mask.sum()
            ),
            "closed_trades": closed_count,
            "winning_trades": wins,
            "losing_trades": losses,
            "win_rate_pct": round(
                (
                    wins
                    / closed_count
                    * 100
                )
                if closed_count > 0
                else 0.0,
                4,
            ),
            "realized_profit_loss": round(
                numeric_sum(
                    journal_df,
                    "realized_profit_loss",
                ),
                2,
            ),
            "unrealized_profit_loss": round(
                numeric_sum(
                    journal_df,
                    "unrealized_profit_loss",
                ),
                2,
            ),
            "total_profit_loss": round(
                numeric_sum(
                    journal_df,
                    "total_profit_loss",
                ),
                2,
            ),
            "average_return_pct": round(
                numeric_series(
                    closed_df,
                    "return_pct",
                ).mean()
                if not closed_df.empty
                else 0.0,
                4,
            ),
            "mistakes_detected": mistakes,
            "journal_completion_score": round(
                completion_score,
                2,
            ),
            "journal_health": classify_journal_health(
                completion_score
            ),
        }

    # ---------------------------------------------------------
    # FILE SAVE
    # ---------------------------------------------------------

    def save_dataframe(
        self,
        df: pd.DataFrame,
        path: Path,
        columns: list[str],
    ) -> None:
        df = remove_duplicate_columns(
            df.copy()
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
    # SCHEMAS
    # ---------------------------------------------------------

    def journal_columns(
        self,
    ) -> list[str]:
        return [
            "trade_id",
            "symbol",
            "company",
            "sector",
            "strategy",
            "entry_date",
            "exit_date",
            "entry_price",
            "exit_price",
            "original_quantity",
            "remaining_quantity",
            "invested_amount",
            "stop_loss",
            "target_1",
            "target_2",
            "realized_profit_loss",
            "unrealized_profit_loss",
            "total_profit_loss",
            "return_pct",
            "capital_return_pct",
            "holding_days",
            "trade_status",
            "trade_result",
            "final_decision",
            "buy_probability",
            "consensus_score",
            "confidence",
            "risk_permission",
            "entry_timing_action",
            "exit_action",
            "why_bought",
            "why_sold",
            "mistake_flag",
            "mistake_notes",
            "lesson_learned",
            "psychology_notes",
            "entry_screenshot",
            "exit_screenshot",
            "manual_review_status",
            "journal_updated_at",
        ]

    def monthly_columns(
        self,
    ) -> list[str]:
        return [
            "month",
            "total_trades",
            "closed_trades",
            "open_trades",
            "winning_trades",
            "losing_trades",
            "win_rate_pct",
            "realized_profit_loss",
            "unrealized_profit_loss",
            "average_return_pct",
            "best_trade_profit_loss",
            "worst_trade_profit_loss",
            "mistakes_detected",
        ]

    def review_columns(
        self,
    ) -> list[str]:
        return [
            "review_priority",
            "trade_id",
            "symbol",
            "company",
            "strategy",
            "trade_status",
            "trade_result",
            "realized_profit_loss",
            "return_pct",
            "why_bought",
            "why_sold",
            "mistake_flag",
            "mistake_notes",
            "lesson_learned",
            "manual_review_status",
            "review_action",
        ]


def run_trade_journal_pro_v1(
    starting_capital: float = 50000.0,
    recommendation_df: pd.DataFrame | None = None,
    portfolio_folder: str = "database/portfolio",
    reports_folder: str = "reports/trade_journal",
    latest_reports_folder: str = "reports/latest",
) -> dict:
    engine = TradeJournalProV1(
        portfolio_folder=portfolio_folder,
        reports_folder=reports_folder,
        latest_reports_folder=latest_reports_folder,
    )

    return engine.run(
        starting_capital=starting_capital,
        recommendation_df=recommendation_df,
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


def row_lookup(
    df: pd.DataFrame,
    column: str,
    uppercase: bool = False,
) -> dict[str, dict]:
    if (
        df is None
        or df.empty
        or column not in df.columns
    ):
        return {}

    lookup = {}

    for _, row in df.iterrows():
        key = clean_text(
            row.get(
                column,
                "",
            )
        )

        if uppercase:
            key = key.upper()

        if key:
            lookup[key] = row.to_dict()

    return lookup


def group_by_trade_id(
    df: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    if (
        df is None
        or df.empty
        or "trade_id" not in df.columns
    ):
        return {}

    result = {}

    for trade_id, group in df.groupby(
        "trade_id",
        dropna=False,
    ):
        key = clean_text(
            trade_id
        )

        if key:
            result[key] = group.copy()

    return result


def filter_actions(
    df: pd.DataFrame,
    actions: list[str],
) -> pd.DataFrame:
    if (
        df is None
        or df.empty
        or "action" not in df.columns
    ):
        return pd.DataFrame()

    normalized = {
        action.upper()
        for action in actions
    }

    return df[
        df["action"]
        .fillna("")
        .astype(str)
        .str.upper()
        .isin(normalized)
    ].copy()


def dataframe_last_row(
    df: pd.DataFrame,
) -> dict:
    if (
        df is None
        or df.empty
    ):
        return {}

    return df.iloc[-1].to_dict()


def first_non_empty_from_df(
    df: pd.DataFrame,
    column: str,
    last: bool = False,
) -> str:
    if (
        df is None
        or df.empty
        or column not in df.columns
    ):
        return ""

    values = (
        df[column]
        .dropna()
        .astype(str)
        .str.strip()
    )

    values = values[
        values.ne("")
    ]

    if values.empty:
        return ""

    return (
        values.iloc[-1]
        if last
        else values.iloc[0]
    )


def last_non_empty_from_df(
    df: pd.DataFrame,
    column: str,
) -> str:
    return first_non_empty_from_df(
        df,
        column,
        last=True,
    )


def first_positive_numeric_from_sources(
    sources: list[dict],
    columns: list[str],
) -> float:
    for source in sources:
        if not source:
            continue

        for column in columns:
            number = safe_float(
                source.get(
                    column,
                    0,
                )
            )

            if number > 0:
                return number

    return 0.0


def first_valid(
    *values: Any,
) -> Any:
    for value in values:
        try:
            if pd.isna(value):
                continue
        except Exception:
            pass

        text = str(
            value
        ).strip()

        if text.upper() not in {
            "",
            "NAN",
            "NONE",
            "NULL",
        }:
            return value

    return ""


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
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


def positive_float(
    value: Any,
    field_name: str,
) -> float:
    number = safe_float(
        value,
        0.0,
    )

    if number <= 0:
        raise ValueError(
            f"{field_name} must be greater than zero."
        )

    return number


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


def calculate_holding_days(
    entry_date: str,
    exit_date: str,
) -> int:
    start = pd.to_datetime(
        entry_date,
        errors="coerce",
    )

    end = pd.to_datetime(
        exit_date,
        errors="coerce",
    )

    if pd.isna(
        start
    ):
        return 0

    if pd.isna(
        end
    ):
        end = pd.Timestamp.now()

    return max(
        int(
            (
                end.normalize()
                - start.normalize()
            ).days
        ),
        0,
    )


def infer_strategy(
    recommendation: dict,
) -> str:
    signal = clean_text(
        recommendation.get(
            "institutional_signal",
            "",
        )
    ).upper()

    entry_action = clean_text(
        recommendation.get(
            "entry_timing_action",
            "",
        )
    ).upper()

    smart_money = safe_float(
        recommendation.get(
            "smart_money_score",
            0,
        )
    )

    trend = safe_float(
        first_valid(
            recommendation.get(
                "trend_score_v5"
            ),
            recommendation.get(
                "trend_score_v4"
            ),
            0,
        )
    )

    if "BREAKOUT" in entry_action:
        return "BREAKOUT"

    if smart_money >= 80:
        return "SMART MONEY"

    if trend >= 70:
        return "TREND FOLLOWING"

    if signal:
        return signal

    return "MOMENTUM"


def classify_trade_result(
    total_profit_loss: float,
    trade_status: str,
) -> str:
    status = trade_status.upper()

    if status in {
        "OPEN",
        "HOLD",
        "PARTIAL EXIT",
        "TRAIL STOP",
    }:
        return "OPEN"

    if total_profit_loss > 0:
        return "WIN"

    if total_profit_loss < 0:
        return "LOSS"

    return "BREAKEVEN"


def detect_trade_mistake(
    entry_price: float,
    planned_entry: float,
    exit_price: float,
    stop_loss: float,
    target_1: float,
    target_2: float,
    trade_status: str,
    total_profit_loss: float,
) -> tuple[bool, str]:
    mistakes = []

    if (
        planned_entry > 0
        and entry_price
        > planned_entry * 1.03
    ):
        mistakes.append(
            "Entry price was more than 3% above planned entry."
        )

    if (
        trade_status.upper()
        in {
            "CLOSED",
            "FULL EXIT",
            "STOP LOSS HIT",
        }
        and exit_price > 0
        and stop_loss > 0
        and exit_price < stop_loss * 0.98
    ):
        mistakes.append(
            "Exit occurred materially below stop loss."
        )

    if (
        total_profit_loss < 0
        and exit_price > 0
        and target_1 > 0
        and exit_price >= target_1
    ):
        mistakes.append(
            "Trade reached Target 1 but finished as a loss."
        )

    if (
        total_profit_loss < 0
        and exit_price > 0
        and target_2 > 0
        and exit_price >= target_2
    ):
        mistakes.append(
            "Trade reached Target 2 but finished as a loss."
        )

    return (
        bool(
            mistakes
        ),
        " | ".join(
            mistakes
        ),
    )


def build_trade_lesson(
    trade_result: str,
    mistake_flag: bool,
    mistake_notes: str,
    why_sold: str,
) -> str:
    if mistake_flag:
        return (
            "Process improvement required: "
            + mistake_notes
        )

    if trade_result == "WIN":
        return (
            "Repeat the setup only when the same entry, risk and confirmation conditions exist."
        )

    if trade_result == "LOSS":
        return (
            "Loss remained part of the risk process; review entry timing and stop discipline."
        )

    if trade_result == "OPEN":
        return (
            "Trade is active; maintain stop discipline and avoid emotional changes."
        )

    return (
        why_sold
        or "Review the trade and document one repeatable lesson."
    )


def classify_journal_health(
    score: float,
) -> str:
    if score >= 90:
        return "EXCELLENT"

    if score >= 75:
        return "STRONG"

    if score >= 60:
        return "NEEDS REVIEW"

    return "WEAK"


def clean_text(
    value: Any,
) -> str:
    try:
        if pd.isna(
            value
        ):
            return ""
    except Exception:
        pass

    return str(
        value
    ).strip()


def upper_text(
    value: Any,
) -> str:
    return clean_text(
        value
    ).upper()


def default_for_column(
    column: str,
) -> Any:
    text_columns = {
        "trade_id",
        "symbol",
        "company",
        "sector",
        "strategy",
        "entry_date",
        "exit_date",
        "trade_status",
        "trade_result",
        "final_decision",
        "risk_permission",
        "entry_timing_action",
        "exit_action",
        "why_bought",
        "why_sold",
        "mistake_notes",
        "lesson_learned",
        "psychology_notes",
        "entry_screenshot",
        "exit_screenshot",
        "manual_review_status",
        "journal_updated_at",
        "month",
        "review_action",
    }

    integer_columns = {
        "original_quantity",
        "remaining_quantity",
        "holding_days",
        "total_trades",
        "closed_trades",
        "open_trades",
        "winning_trades",
        "losing_trades",
        "mistakes_detected",
        "review_priority",
    }

    boolean_columns = {
        "mistake_flag",
    }

    if column in text_columns:
        return ""

    if column in integer_columns:
        return 0

    if column in boolean_columns:
        return False

    return 0.0
