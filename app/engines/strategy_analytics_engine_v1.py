from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class StrategyAnalyticsConfigV1:
    trade_journal_folder: str = "reports/trade_journal"
    reports_folder: str = "reports/strategy_analytics"
    journal_filename: str = "trade_journal.csv"
    analytics_filename: str = "strategy_analytics.csv"
    leaderboard_filename: str = "strategy_leaderboard.csv"
    monthly_filename: str = "strategy_monthly.csv"
    equity_filename: str = "strategy_equity.csv"
    summary_filename: str = "strategy_summary.csv"


class StrategyAnalyticsEngineV1:
    """
    Strategy Analytics Engine V1

    Reads Trade Journal Pro output and calculates institutional performance
    metrics separately for every detected strategy.

    Metrics include:
    - total/open/closed trades
    - wins/losses/breakeven
    - win rate
    - gross profit / gross loss
    - profit factor
    - expectancy
    - average return
    - average holding days
    - cumulative strategy P/L
    - Sharpe ratio
    - recovery factor
    - maximum drawdown
    - best/worst trade
    - monthly strategy performance
    - strategy leaderboard
    """

    VERSION = "strategy_analytics_engine_v1_0_institutional"

    def __init__(
        self,
        trade_journal_folder: str = "reports/trade_journal",
        reports_folder: str = "reports/strategy_analytics",
    ):
        self.config = StrategyAnalyticsConfigV1(
            trade_journal_folder=trade_journal_folder,
            reports_folder=reports_folder,
        )

        self.trade_journal_folder = Path(
            self.config.trade_journal_folder
        )
        self.reports_folder = Path(
            self.config.reports_folder
        )

        self.reports_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.journal_path = (
            self.trade_journal_folder
            / self.config.journal_filename
        )
        self.analytics_path = (
            self.reports_folder
            / self.config.analytics_filename
        )
        self.leaderboard_path = (
            self.reports_folder
            / self.config.leaderboard_filename
        )
        self.monthly_path = (
            self.reports_folder
            / self.config.monthly_filename
        )
        self.equity_path = (
            self.reports_folder
            / self.config.equity_filename
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
        journal_df: pd.DataFrame | None = None,
    ) -> dict:
        starting_capital = positive_float(
            starting_capital,
            "starting_capital",
        )

        if (
            journal_df is None
            or not isinstance(
                journal_df,
                pd.DataFrame,
            )
            or journal_df.empty
        ):
            journal_df = self.read_csv(
                self.journal_path
            )

        journal_df = self.normalize_journal(
            journal_df
        )

        analytics_df = self.build_strategy_analytics(
            journal_df=journal_df,
            starting_capital=starting_capital,
        )

        monthly_df = self.build_strategy_monthly(
            journal_df=journal_df,
        )

        equity_df = self.build_strategy_equity(
            journal_df=journal_df,
            starting_capital=starting_capital,
        )

        leaderboard_df = self.build_strategy_leaderboard(
            analytics_df=analytics_df,
        )

        summary = self.build_summary(
            analytics_df=analytics_df,
            leaderboard_df=leaderboard_df,
        )

        self.save_dataframe(
            analytics_df,
            self.analytics_path,
            self.analytics_columns(),
        )

        self.save_dataframe(
            leaderboard_df,
            self.leaderboard_path,
            self.leaderboard_columns(),
        )

        self.save_dataframe(
            monthly_df,
            self.monthly_path,
            self.monthly_columns(),
        )

        self.save_dataframe(
            equity_df,
            self.equity_path,
            self.equity_columns(),
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
            "strategies_analyzed": int(
                len(analytics_df)
            ),
            "best_strategy": summary[
                "best_strategy"
            ],
            "worst_strategy": summary[
                "worst_strategy"
            ],
            "best_strategy_score": summary[
                "best_strategy_score"
            ],
            "strategy_analytics_csv": str(
                self.analytics_path
            ),
            "leaderboard_csv": str(
                self.leaderboard_path
            ),
            "strategy_monthly_csv": str(
                self.monthly_path
            ),
            "strategy_equity_csv": str(
                self.equity_path
            ),
            "summary_csv": str(
                self.summary_path
            ),
            "reason": (
                "Strategy analytics generated successfully"
            ),
        }

    # ---------------------------------------------------------
    # NORMALIZATION
    # ---------------------------------------------------------

    def normalize_journal(
        self,
        journal_df: pd.DataFrame,
    ) -> pd.DataFrame:
        journal_df = remove_duplicate_columns(
            journal_df
        )

        if journal_df.empty:
            return pd.DataFrame(
                columns=[
                    "trade_id",
                    "symbol",
                    "strategy",
                    "entry_date",
                    "exit_date",
                    "realized_profit_loss",
                    "unrealized_profit_loss",
                    "total_profit_loss",
                    "return_pct",
                    "holding_days",
                    "trade_status",
                    "trade_result",
                ]
            )

        defaults = {
            "trade_id": "",
            "symbol": "",
            "strategy": "UNCLASSIFIED",
            "entry_date": "",
            "exit_date": "",
            "realized_profit_loss": 0.0,
            "unrealized_profit_loss": 0.0,
            "total_profit_loss": 0.0,
            "return_pct": 0.0,
            "holding_days": 0,
            "trade_status": "",
            "trade_result": "",
        }

        for column, default in defaults.items():
            if column not in journal_df.columns:
                journal_df[column] = default

        for column in [
            "trade_id",
            "symbol",
            "strategy",
            "entry_date",
            "exit_date",
            "trade_status",
            "trade_result",
        ]:
            journal_df[column] = (
                journal_df[column]
                .fillna("")
                .astype(str)
            )

        journal_df["strategy"] = (
            journal_df["strategy"]
            .str.upper()
            .str.strip()
            .replace(
                {
                    "": "UNCLASSIFIED",
                    "NAN": "UNCLASSIFIED",
                    "NONE": "UNCLASSIFIED",
                }
            )
        )

        for column in [
            "realized_profit_loss",
            "unrealized_profit_loss",
            "total_profit_loss",
            "return_pct",
            "holding_days",
        ]:
            journal_df[column] = pd.to_numeric(
                journal_df[column],
                errors="coerce",
            ).fillna(
                0.0
            )

        return journal_df

    # ---------------------------------------------------------
    # STRATEGY ANALYTICS
    # ---------------------------------------------------------

    def build_strategy_analytics(
        self,
        journal_df: pd.DataFrame,
        starting_capital: float,
    ) -> pd.DataFrame:
        if journal_df.empty:
            return pd.DataFrame(
                columns=self.analytics_columns()
            )

        rows = []

        for strategy, group in journal_df.groupby(
            "strategy",
            dropna=False,
        ):
            strategy = clean_text(
                strategy
            ).upper() or "UNCLASSIFIED"

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

            open_group = group[
                ~closed_mask
            ].copy()

            closed_count = int(
                len(closed_group)
            )

            winning_mask = (
                numeric_series(
                    closed_group,
                    "realized_profit_loss",
                )
                > 0
            )

            losing_mask = (
                numeric_series(
                    closed_group,
                    "realized_profit_loss",
                )
                < 0
            )

            breakeven_mask = (
                numeric_series(
                    closed_group,
                    "realized_profit_loss",
                )
                == 0
            )

            winning_trades = int(
                winning_mask.sum()
            )

            losing_trades = int(
                losing_mask.sum()
            )

            breakeven_trades = int(
                breakeven_mask.sum()
            )

            gross_profit = float(
                numeric_series(
                    closed_group,
                    "realized_profit_loss",
                )[
                    winning_mask
                ].sum()
            )

            gross_loss_abs = abs(
                float(
                    numeric_series(
                        closed_group,
                        "realized_profit_loss",
                    )[
                        losing_mask
                    ].sum()
                )
            )

            net_profit_loss = float(
                numeric_sum(
                    group,
                    "total_profit_loss",
                )
            )

            realized_profit_loss = float(
                numeric_sum(
                    closed_group,
                    "realized_profit_loss",
                )
            )

            unrealized_profit_loss = float(
                numeric_sum(
                    open_group,
                    "unrealized_profit_loss",
                )
            )

            win_rate_pct = (
                winning_trades
                / closed_count
                * 100
                if closed_count > 0
                else 0.0
            )

            average_win = (
                gross_profit
                / winning_trades
                if winning_trades > 0
                else 0.0
            )

            average_loss = (
                gross_loss_abs
                / losing_trades
                if losing_trades > 0
                else 0.0
            )

            loss_rate = (
                losing_trades
                / closed_count
                if closed_count > 0
                else 0.0
            )

            win_rate = (
                winning_trades
                / closed_count
                if closed_count > 0
                else 0.0
            )

            expectancy = (
                win_rate
                * average_win
                - loss_rate
                * average_loss
            )

            profit_factor = (
                gross_profit
                / gross_loss_abs
                if gross_loss_abs > 0
                else (
                    gross_profit
                    if gross_profit > 0
                    else 0.0
                )
            )

            average_return_pct = (
                numeric_series(
                    closed_group,
                    "return_pct",
                ).mean()
                if not closed_group.empty
                else 0.0
            )

            average_holding_days = (
                numeric_series(
                    group,
                    "holding_days",
                ).mean()
                if not group.empty
                else 0.0
            )

            sharpe_ratio = calculate_sharpe_ratio(
                numeric_series(
                    closed_group,
                    "return_pct",
                )
            )

            strategy_equity = build_equity_series(
                closed_group,
                starting_capital,
            )

            max_drawdown_pct = calculate_max_drawdown_pct(
                strategy_equity
            )

            recovery_factor = (
                realized_profit_loss
                / abs(
                    starting_capital
                    * max_drawdown_pct
                    / 100
                )
                if max_drawdown_pct < 0
                else (
                    realized_profit_loss
                    if realized_profit_loss > 0
                    else 0.0
                )
            )

            best_trade_row = best_trade_record(
                group
            )

            worst_trade_row = worst_trade_record(
                group
            )

            consistency_score = calculate_consistency_score(
                closed_group
            )

            profitability_score = calculate_profitability_score(
                realized_profit_loss=realized_profit_loss,
                starting_capital=starting_capital,
                profit_factor=profit_factor,
                expectancy=expectancy,
            )

            risk_score = calculate_risk_score(
                max_drawdown_pct=max_drawdown_pct,
                sharpe_ratio=sharpe_ratio,
            )

            sample_score = min(
                100.0,
                closed_count
                / 20
                * 100,
            )

            strategy_score = (
                profitability_score * 0.35
                + risk_score * 0.25
                + consistency_score * 0.20
                + sample_score * 0.20
            )

            rows.append({
                "strategy": strategy,
                "total_trades": int(
                    len(group)
                ),
                "open_trades": int(
                    len(open_group)
                ),
                "closed_trades": closed_count,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "breakeven_trades": breakeven_trades,
                "win_rate_pct": round(
                    win_rate_pct,
                    4,
                ),
                "gross_profit": round(
                    gross_profit,
                    2,
                ),
                "gross_loss": round(
                    gross_loss_abs,
                    2,
                ),
                "net_profit_loss": round(
                    net_profit_loss,
                    2,
                ),
                "realized_profit_loss": round(
                    realized_profit_loss,
                    2,
                ),
                "unrealized_profit_loss": round(
                    unrealized_profit_loss,
                    2,
                ),
                "profit_factor": round(
                    profit_factor,
                    4,
                ),
                "expectancy": round(
                    expectancy,
                    4,
                ),
                "average_win": round(
                    average_win,
                    2,
                ),
                "average_loss": round(
                    average_loss,
                    2,
                ),
                "average_return_pct": round(
                    average_return_pct,
                    4,
                ),
                "average_holding_days": round(
                    average_holding_days,
                    2,
                ),
                "sharpe_ratio": round(
                    sharpe_ratio,
                    4,
                ),
                "maximum_drawdown_pct": round(
                    max_drawdown_pct,
                    4,
                ),
                "recovery_factor": round(
                    recovery_factor,
                    4,
                ),
                "best_trade_symbol": best_trade_row[
                    "symbol"
                ],
                "best_trade_profit_loss": round(
                    best_trade_row[
                        "profit_loss"
                    ],
                    2,
                ),
                "worst_trade_symbol": worst_trade_row[
                    "symbol"
                ],
                "worst_trade_profit_loss": round(
                    worst_trade_row[
                        "profit_loss"
                    ],
                    2,
                ),
                "consistency_score": round(
                    consistency_score,
                    2,
                ),
                "profitability_score": round(
                    profitability_score,
                    2,
                ),
                "risk_score": round(
                    risk_score,
                    2,
                ),
                "sample_score": round(
                    sample_score,
                    2,
                ),
                "strategy_score": round(
                    strategy_score,
                    2,
                ),
                "status": classify_strategy_status(
                    strategy_score=strategy_score,
                    closed_trades=closed_count,
                    win_rate_pct=win_rate_pct,
                    net_profit_loss=net_profit_loss,
                ),
                "recommendation": build_strategy_recommendation(
                    closed_trades=closed_count,
                    win_rate_pct=win_rate_pct,
                    profit_factor=profit_factor,
                    expectancy=expectancy,
                    max_drawdown_pct=max_drawdown_pct,
                ),
            })

        result = pd.DataFrame(
            rows
        )

        if not result.empty:
            result = result.sort_values(
                [
                    "strategy_score",
                    "net_profit_loss",
                ],
                ascending=[
                    False,
                    False,
                ],
            ).reset_index(
                drop=True
            )

        return result

    # ---------------------------------------------------------
    # MONTHLY
    # ---------------------------------------------------------

    def build_strategy_monthly(
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

        for (
            strategy,
            month,
        ), group in working.groupby(
            [
                "strategy",
                "month",
            ],
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
            ]

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
                len(closed_group)
            )

            rows.append({
                "strategy": clean_text(
                    strategy
                ).upper(),
                "month": month,
                "total_trades": int(
                    len(group)
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
                "net_profit_loss": round(
                    numeric_sum(
                        group,
                        "total_profit_loss",
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
                "average_holding_days": round(
                    numeric_series(
                        group,
                        "holding_days",
                    ).mean(),
                    2,
                ),
            })

        return pd.DataFrame(
            rows,
            columns=self.monthly_columns(),
        )

    # ---------------------------------------------------------
    # EQUITY
    # ---------------------------------------------------------

    def build_strategy_equity(
        self,
        journal_df: pd.DataFrame,
        starting_capital: float,
    ) -> pd.DataFrame:
        if journal_df.empty:
            return pd.DataFrame(
                columns=self.equity_columns()
            )

        rows = []

        for strategy, group in journal_df.groupby(
            "strategy",
            dropna=False,
        ):
            strategy = clean_text(
                strategy
            ).upper() or "UNCLASSIFIED"

            closed_group = group[
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
            ].copy()

            if closed_group.empty:
                continue

            closed_group["_date"] = pd.to_datetime(
                closed_group["exit_date"],
                errors="coerce",
            )

            closed_group = closed_group.sort_values(
                [
                    "_date",
                    "trade_id",
                ],
                kind="stable",
            )

            equity = starting_capital
            peak = starting_capital

            for sequence, (_, row) in enumerate(
                closed_group.iterrows(),
                start=1,
            ):
                profit_loss = safe_float(
                    row.get(
                        "realized_profit_loss",
                        0,
                    )
                )

                equity += profit_loss
                peak = max(
                    peak,
                    equity,
                )

                drawdown_amount = (
                    equity
                    - peak
                )

                drawdown_pct = (
                    drawdown_amount
                    / peak
                    * 100
                    if peak > 0
                    else 0.0
                )

                rows.append({
                    "strategy": strategy,
                    "sequence": sequence,
                    "trade_id": clean_text(
                        row.get(
                            "trade_id",
                            "",
                        )
                    ),
                    "symbol": upper_text(
                        row.get(
                            "symbol",
                            "",
                        )
                    ),
                    "date": clean_text(
                        row.get(
                            "exit_date",
                            "",
                        )
                    ),
                    "trade_profit_loss": round(
                        profit_loss,
                        2,
                    ),
                    "strategy_equity": round(
                        equity,
                        2,
                    ),
                    "peak_equity": round(
                        peak,
                        2,
                    ),
                    "drawdown_amount": round(
                        drawdown_amount,
                        2,
                    ),
                    "drawdown_pct": round(
                        drawdown_pct,
                        4,
                    ),
                })

        return pd.DataFrame(
            rows,
            columns=self.equity_columns(),
        )

    # ---------------------------------------------------------
    # LEADERBOARD
    # ---------------------------------------------------------

    def build_strategy_leaderboard(
        self,
        analytics_df: pd.DataFrame,
    ) -> pd.DataFrame:
        if analytics_df.empty:
            return pd.DataFrame(
                columns=self.leaderboard_columns()
            )

        result = analytics_df[
            [
                "strategy",
                "strategy_score",
                "status",
                "closed_trades",
                "win_rate_pct",
                "profit_factor",
                "expectancy",
                "net_profit_loss",
                "sharpe_ratio",
                "maximum_drawdown_pct",
                "recovery_factor",
                "average_return_pct",
                "recommendation",
            ]
        ].copy()

        result = result.sort_values(
            [
                "strategy_score",
                "net_profit_loss",
            ],
            ascending=[
                False,
                False,
            ],
        ).reset_index(
            drop=True
        )

        result.insert(
            0,
            "rank",
            range(
                1,
                len(result) + 1,
            ),
        )

        return result[
            self.leaderboard_columns()
        ]

    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------

    def build_summary(
        self,
        analytics_df: pd.DataFrame,
        leaderboard_df: pd.DataFrame,
    ) -> dict:
        if analytics_df.empty:
            return {
                "engine_version": self.VERSION,
                "generated_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
                "strategies_analyzed": 0,
                "best_strategy": "",
                "worst_strategy": "",
                "best_strategy_score": 0.0,
                "worst_strategy_score": 0.0,
                "profitable_strategies": 0,
                "losing_strategies": 0,
                "strategies_with_enough_data": 0,
                "summary_status": "NO DATA",
            }

        best = analytics_df.iloc[0]
        worst = analytics_df.iloc[-1]

        profitable = int(
            (
                numeric_series(
                    analytics_df,
                    "net_profit_loss",
                )
                > 0
            ).sum()
        )

        losing = int(
            (
                numeric_series(
                    analytics_df,
                    "net_profit_loss",
                )
                < 0
            ).sum()
        )

        enough_data = int(
            (
                numeric_series(
                    analytics_df,
                    "closed_trades",
                )
                >= 10
            ).sum()
        )

        return {
            "engine_version": self.VERSION,
            "generated_at": datetime.now().isoformat(
                timespec="seconds"
            ),
            "strategies_analyzed": int(
                len(analytics_df)
            ),
            "best_strategy": clean_text(
                best.get(
                    "strategy",
                    "",
                )
            ),
            "worst_strategy": clean_text(
                worst.get(
                    "strategy",
                    "",
                )
            ),
            "best_strategy_score": round(
                safe_float(
                    best.get(
                        "strategy_score",
                        0,
                    )
                ),
                2,
            ),
            "worst_strategy_score": round(
                safe_float(
                    worst.get(
                        "strategy_score",
                        0,
                    )
                ),
                2,
            ),
            "profitable_strategies": profitable,
            "losing_strategies": losing,
            "strategies_with_enough_data": enough_data,
            "summary_status": (
                "LEARNING"
                if enough_data == 0
                else "ACTIVE"
            ),
        }

    # ---------------------------------------------------------
    # FILE HELPERS
    # ---------------------------------------------------------

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

    def analytics_columns(
        self,
    ) -> list[str]:
        return [
            "strategy",
            "total_trades",
            "open_trades",
            "closed_trades",
            "winning_trades",
            "losing_trades",
            "breakeven_trades",
            "win_rate_pct",
            "gross_profit",
            "gross_loss",
            "net_profit_loss",
            "realized_profit_loss",
            "unrealized_profit_loss",
            "profit_factor",
            "expectancy",
            "average_win",
            "average_loss",
            "average_return_pct",
            "average_holding_days",
            "sharpe_ratio",
            "maximum_drawdown_pct",
            "recovery_factor",
            "best_trade_symbol",
            "best_trade_profit_loss",
            "worst_trade_symbol",
            "worst_trade_profit_loss",
            "consistency_score",
            "profitability_score",
            "risk_score",
            "sample_score",
            "strategy_score",
            "status",
            "recommendation",
        ]

    def leaderboard_columns(
        self,
    ) -> list[str]:
        return [
            "rank",
            "strategy",
            "strategy_score",
            "status",
            "closed_trades",
            "win_rate_pct",
            "profit_factor",
            "expectancy",
            "net_profit_loss",
            "sharpe_ratio",
            "maximum_drawdown_pct",
            "recovery_factor",
            "average_return_pct",
            "recommendation",
        ]

    def monthly_columns(
        self,
    ) -> list[str]:
        return [
            "strategy",
            "month",
            "total_trades",
            "closed_trades",
            "winning_trades",
            "losing_trades",
            "win_rate_pct",
            "realized_profit_loss",
            "unrealized_profit_loss",
            "net_profit_loss",
            "average_return_pct",
            "best_trade_profit_loss",
            "worst_trade_profit_loss",
            "average_holding_days",
        ]

    def equity_columns(
        self,
    ) -> list[str]:
        return [
            "strategy",
            "sequence",
            "trade_id",
            "symbol",
            "date",
            "trade_profit_loss",
            "strategy_equity",
            "peak_equity",
            "drawdown_amount",
            "drawdown_pct",
        ]


def run_strategy_analytics_engine_v1(
    starting_capital: float = 50000.0,
    journal_df: pd.DataFrame | None = None,
    trade_journal_folder: str = "reports/trade_journal",
    reports_folder: str = "reports/strategy_analytics",
) -> dict:
    engine = StrategyAnalyticsEngineV1(
        trade_journal_folder=trade_journal_folder,
        reports_folder=reports_folder,
    )

    return engine.run(
        starting_capital=starting_capital,
        journal_df=journal_df,
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


def build_equity_series(
    closed_group: pd.DataFrame,
    starting_capital: float,
) -> pd.Series:
    if closed_group.empty:
        return pd.Series(
            [starting_capital],
            dtype=float,
        )

    group = closed_group.copy()

    group["_date"] = pd.to_datetime(
        group["exit_date"],
        errors="coerce",
    )

    group = group.sort_values(
        [
            "_date",
            "trade_id",
        ],
        kind="stable",
    )

    profits = numeric_series(
        group,
        "realized_profit_loss",
    )

    return (
        starting_capital
        + profits.cumsum()
    )


def calculate_max_drawdown_pct(
    equity: pd.Series,
) -> float:
    if equity is None or equity.empty:
        return 0.0

    equity = pd.to_numeric(
        equity,
        errors="coerce",
    ).dropna()

    if equity.empty:
        return 0.0

    peak = equity.cummax()

    drawdown = (
        equity
        - peak
    ) / peak.replace(
        0,
        pd.NA,
    ) * 100

    return float(
        drawdown.fillna(
            0.0
        ).min()
    )


def calculate_sharpe_ratio(
    returns: pd.Series,
) -> float:
    if returns is None or len(returns) < 2:
        return 0.0

    returns = pd.to_numeric(
        returns,
        errors="coerce",
    ).dropna()

    if len(returns) < 2:
        return 0.0

    std = float(
        returns.std(
            ddof=1
        )
    )

    if std <= 0:
        return 0.0

    return float(
        returns.mean()
        / std
        * math.sqrt(
            len(returns)
        )
    )


def best_trade_record(
    group: pd.DataFrame,
) -> dict:
    if group.empty:
        return {
            "symbol": "",
            "profit_loss": 0.0,
        }

    values = numeric_series(
        group,
        "total_profit_loss",
    )

    index = values.idxmax()

    return {
        "symbol": upper_text(
            group.loc[
                index
            ].get(
                "symbol",
                "",
            )
        ),
        "profit_loss": safe_float(
            values.loc[
                index
            ]
        ),
    }


def worst_trade_record(
    group: pd.DataFrame,
) -> dict:
    if group.empty:
        return {
            "symbol": "",
            "profit_loss": 0.0,
        }

    values = numeric_series(
        group,
        "total_profit_loss",
    )

    index = values.idxmin()

    return {
        "symbol": upper_text(
            group.loc[
                index
            ].get(
                "symbol",
                "",
            )
        ),
        "profit_loss": safe_float(
            values.loc[
                index
            ]
        ),
    }


def calculate_consistency_score(
    closed_group: pd.DataFrame,
) -> float:
    if closed_group.empty:
        return 0.0

    returns = numeric_series(
        closed_group,
        "return_pct",
    )

    if returns.empty:
        return 0.0

    positive_ratio = (
        (
            returns > 0
        ).sum()
        / len(returns)
        * 100
    )

    volatility_penalty = min(
        50.0,
        float(
            returns.std(
                ddof=0
            )
        ) * 5,
    )

    return max(
        0.0,
        min(
            100.0,
            positive_ratio
            - volatility_penalty
            + 25,
        ),
    )


def calculate_profitability_score(
    realized_profit_loss: float,
    starting_capital: float,
    profit_factor: float,
    expectancy: float,
) -> float:
    return_pct = (
        realized_profit_loss
        / starting_capital
        * 100
        if starting_capital > 0
        else 0.0
    )

    score = (
        50
        + return_pct * 8
        + min(
            profit_factor,
            5,
        ) * 6
        + max(
            min(
                expectancy / 100,
                10,
            ),
            -10,
        )
    )

    return max(
        0.0,
        min(
            100.0,
            score,
        ),
    )


def calculate_risk_score(
    max_drawdown_pct: float,
    sharpe_ratio: float,
) -> float:
    drawdown_penalty = min(
        80.0,
        abs(
            max_drawdown_pct
        ) * 8,
    )

    sharpe_bonus = max(
        -20.0,
        min(
            30.0,
            sharpe_ratio * 10,
        ),
    )

    return max(
        0.0,
        min(
            100.0,
            80
            - drawdown_penalty
            + sharpe_bonus,
        ),
    )


def classify_strategy_status(
    strategy_score: float,
    closed_trades: int,
    win_rate_pct: float,
    net_profit_loss: float,
) -> str:
    if closed_trades < 5:
        return "INSUFFICIENT DATA"

    if (
        strategy_score >= 80
        and win_rate_pct >= 60
        and net_profit_loss > 0
    ):
        return "ELITE"

    if (
        strategy_score >= 65
        and net_profit_loss > 0
    ):
        return "STRONG"

    if strategy_score >= 50:
        return "NEUTRAL"

    if net_profit_loss < 0:
        return "WEAK"

    return "WATCH"


def build_strategy_recommendation(
    closed_trades: int,
    win_rate_pct: float,
    profit_factor: float,
    expectancy: float,
    max_drawdown_pct: float,
) -> str:
    if closed_trades < 5:
        return (
            "Collect more closed trades before changing capital allocation."
        )

    if (
        win_rate_pct >= 60
        and profit_factor >= 1.5
        and expectancy > 0
        and max_drawdown_pct >= -10
    ):
        return (
            "Maintain or gradually increase allocation within portfolio risk limits."
        )

    if (
        expectancy < 0
        or profit_factor < 1
    ):
        return (
            "Reduce allocation and review entry, exit and risk rules."
        )

    if max_drawdown_pct < -10:
        return (
            "Keep strategy active only with smaller position size until drawdown improves."
        )

    return (
        "Maintain current allocation and continue collecting performance data."
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
        "strategy",
        "best_trade_symbol",
        "worst_trade_symbol",
        "status",
        "recommendation",
        "month",
        "trade_id",
        "symbol",
        "date",
    }

    integer_columns = {
        "total_trades",
        "open_trades",
        "closed_trades",
        "winning_trades",
        "losing_trades",
        "breakeven_trades",
        "rank",
        "sequence",
    }

    if column in text_columns:
        return ""

    if column in integer_columns:
        return 0

    return 0.0
