from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class PerformanceDashboardConfigV1:
    reports_root: str = "reports"
    latest_folder: str = "reports/latest"
    backtest_folder: str = "reports/backtests"
    lifecycle_folder: str = "database/portfolio"
    output_folder: str = "reports/dashboard"
    dashboard_filename: str = "dashboard_v2.html"


class PerformanceDashboardV1:
    """
    Performance Analytics Dashboard V1

    Reads existing scanner outputs and generates:
    - Institutional HTML dashboard
    - performance_summary.json
    - performance_metrics.csv
    - equity_curve.csv
    - trade_journal.csv
    - sector_performance.csv
    - risk_dashboard.csv
    - portfolio_dashboard.csv

    This engine does not modify scanner logic.
    It only reads outputs produced by:
    - Reporting Engine V3
    - Trade Lifecycle Engine V1
    - Exit Intelligence Engine V1
    - Backtesting / Performance Analyzer V1
    """

    VERSION = "performance_dashboard_v2_0_institutional_terminal"

    def __init__(
        self,
        reports_root: str = "reports",
        latest_folder: str = "reports/latest",
        backtest_folder: str = "reports/backtests",
        lifecycle_folder: str = "database/portfolio",
        output_folder: str = "reports/dashboard",
        dashboard_filename: str = "dashboard_v2.html",
    ):
        self.config = PerformanceDashboardConfigV1(
            reports_root=reports_root,
            latest_folder=latest_folder,
            backtest_folder=backtest_folder,
            lifecycle_folder=lifecycle_folder,
            output_folder=output_folder,
            dashboard_filename=dashboard_filename,
        )

        self.latest_folder = Path(self.config.latest_folder)
        self.backtest_folder = Path(self.config.backtest_folder)
        self.lifecycle_folder = Path(self.config.lifecycle_folder)
        self.output_folder = Path(self.config.output_folder)

        self.output_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ---------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------

    def run(self) -> dict:
        data = self.load_all_sources()

        portfolio_df = data["portfolio"]
        top_buys_df = data["top_buys"]
        lifecycle_df = data["trade_lifecycle"]
        pending_df = data["pending_entries"]
        open_df = data["open_positions"]
        closed_df = data["closed_positions"]
        exit_df = data["exit_intelligence"]
        action_plan_df = data["daily_action_plan"]
        overall_df = data["overall_performance"]
        sector_perf_df = data["performance_by_sector"]
        metadata = data["metadata"]

        performance_metrics = self.calculate_performance_metrics(
            overall_df=overall_df,
            open_df=open_df,
            closed_df=closed_df,
            portfolio_df=portfolio_df,
            metadata=metadata,
        )

        equity_curve_df = self.build_equity_curve(
            closed_df=closed_df,
            lifecycle_df=lifecycle_df,
        )

        trade_journal_df = self.build_trade_journal(
            lifecycle_df=lifecycle_df,
            closed_df=closed_df,
            exit_df=exit_df,
            top_buys_df=top_buys_df,
        )

        risk_dashboard_df = self.build_risk_dashboard(
            portfolio_df=portfolio_df,
            open_df=open_df,
            metadata=metadata,
        )

        portfolio_dashboard_df = self.build_portfolio_dashboard(
            portfolio_df=portfolio_df,
            open_df=open_df,
            pending_df=pending_df,
        )

        sector_dashboard_df = self.build_sector_dashboard(
            sector_perf_df=sector_perf_df,
            top_buys_df=top_buys_df,
        )

        output_paths = self.save_outputs(
            performance_metrics=performance_metrics,
            equity_curve_df=equity_curve_df,
            trade_journal_df=trade_journal_df,
            sector_dashboard_df=sector_dashboard_df,
            risk_dashboard_df=risk_dashboard_df,
            portfolio_dashboard_df=portfolio_dashboard_df,
        )

        dashboard_path = self.generate_html_dashboard(
            performance_metrics=performance_metrics,
            portfolio_df=portfolio_df,
            top_buys_df=top_buys_df,
            open_df=open_df,
            closed_df=closed_df,
            pending_df=pending_df,
            exit_df=exit_df,
            action_plan_df=action_plan_df,
            equity_curve_df=equity_curve_df,
            sector_dashboard_df=sector_dashboard_df,
            risk_dashboard_df=risk_dashboard_df,
            portfolio_dashboard_df=portfolio_dashboard_df,
            metadata=metadata,
        )

        return {
            "status": "success",
            "engine_version": self.VERSION,
            "dashboard": str(dashboard_path),
            "latest_dashboard": str(Path(self.config.reports_root) / "latest_dashboard_v2.html"),
            "output_folder": str(self.output_folder),
            "performance_metrics": performance_metrics,
            "files": output_paths,
            "reason": "Performance Analytics Dashboard generated successfully",
        }

    # ---------------------------------------------------------
    # LOADERS
    # ---------------------------------------------------------

    def load_all_sources(self) -> dict:
        return {
            "portfolio": self.read_csv(
                self.latest_folder / "portfolio.csv"
            ),
            "top_buys": self.read_csv(
                self.latest_folder / "top_buys.csv"
            ),
            "trade_lifecycle": self.read_csv(
                self.latest_folder / "trade_lifecycle.csv"
            ),
            "pending_entries": self.read_csv(
                self.latest_folder / "pending_entries.csv"
            ),
            "open_positions": self.read_csv(
                self.lifecycle_folder / "open_positions.csv"
            ),
            "closed_positions": self.read_csv(
                self.lifecycle_folder / "closed_positions.csv"
            ),
            "exit_intelligence": self.read_csv(
                self.latest_folder / "exit_intelligence.csv"
            ),
            "daily_action_plan": self.read_csv(
                self.latest_folder / "daily_action_plan.csv"
            ),
            "overall_performance": self.read_csv(
                self.backtest_folder / "overall_performance.csv"
            ),
            "performance_by_sector": self.read_csv(
                self.backtest_folder / "performance_by_sector.csv"
            ),
            "metadata": self.read_json(
                self.latest_folder / "metadata.json"
            ),
        }

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

    def read_json(
        self,
        path: Path,
    ) -> dict:
        if (
            not path.exists()
            or path.stat().st_size == 0
        ):
            return {}

        try:
            return json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            return {}

    # ---------------------------------------------------------
    # ANALYTICS
    # ---------------------------------------------------------

    def calculate_performance_metrics(
        self,
        overall_df: pd.DataFrame,
        open_df: pd.DataFrame,
        closed_df: pd.DataFrame,
        portfolio_df: pd.DataFrame,
        metadata: dict,
    ) -> dict:
        overall = (
            overall_df.iloc[0].to_dict()
            if not overall_df.empty
            else {}
        )

        closed_count = int(
            safe_float(
                overall.get(
                    "closed_signals",
                    len(closed_df),
                )
            )
        )

        total_signals = int(
            safe_float(
                overall.get(
                    "total_signals",
                    0,
                )
            )
        )

        pending_signals = int(
            safe_float(
                overall.get(
                    "pending_signals",
                    max(
                        total_signals - closed_count,
                        0,
                    ),
                )
            )
        )

        wins = int(
            safe_float(
                overall.get(
                    "wins",
                    0,
                )
            )
        )

        losses = int(
            safe_float(
                overall.get(
                    "losses",
                    0,
                )
            )
        )

        win_rate = safe_float(
            overall.get(
                "win_rate_pct",
                0,
            )
        )

        avg_return = safe_float(
            overall.get(
                "average_return_pct",
                0,
            )
        )

        total_profit_loss = safe_float(
            overall.get(
                "total_profit_loss",
                0,
            )
        )

        average_win = safe_float(
            overall.get(
                "average_win",
                0,
            )
        )

        average_loss = safe_float(
            overall.get(
                "average_loss",
                0,
            )
        )

        expectancy = safe_float(
            overall.get(
                "expectancy_per_trade",
                0,
            )
        )

        profit_factor = normalize_profit_factor(
            overall.get(
                "profit_factor",
                0,
            )
        )

        average_holding_days = safe_float(
            overall.get(
                "average_holding_days",
                0,
            )
        )

        open_unrealized = numeric_sum(
            open_df,
            "unrealized_profit_loss",
        )

        open_realized = numeric_sum(
            open_df,
            "realized_profit_loss",
        )

        closed_realized = numeric_sum(
            closed_df,
            "realized_profit_loss",
        )

        portfolio_value = numeric_sum(
            portfolio_df,
            "investment",
        )

        if portfolio_value == 0:
            portfolio_value = numeric_sum(
                portfolio_df,
                "portfolio_investment",
            )

        max_drawdown = self.calculate_max_drawdown(
            closed_df
        )

        sharpe_ratio = self.calculate_sharpe_ratio(
            closed_df
        )

        recovery_factor = (
            total_profit_loss
            / abs(max_drawdown)
            if max_drawdown < 0
            else 0.0
        )

        market_summary = metadata.get(
            "market_summary",
            {},
        )

        portfolio_summary = metadata.get(
            "portfolio_summary",
            {},
        )

        lifecycle_summary = metadata.get(
            "lifecycle_summary",
            {},
        )

        return {
            "engine_version": self.VERSION,
            "generated_at": datetime.now().isoformat(
                timespec="seconds"
            ),
            "trading_date": metadata.get(
                "trading_date",
                "",
            ),
            "market_mood": market_summary.get(
                "market_mood",
                "UNKNOWN",
            ),
            "market_score": safe_float(
                market_summary.get(
                    "market_score",
                    0,
                )
            ),
            "capital": safe_float(
                portfolio_summary.get(
                    "capital",
                    0,
                )
            ),
            "used_capital": safe_float(
                portfolio_summary.get(
                    "used_capital",
                    portfolio_value,
                )
            ),
            "cash_reserve": safe_float(
                portfolio_summary.get(
                    "cash_reserve",
                    0,
                )
            ),
            "portfolio_health_score": safe_float(
                portfolio_summary.get(
                    "portfolio_health_score",
                    0,
                )
            ),
            "portfolio_risk_pct": safe_float(
                portfolio_summary.get(
                    "portfolio_risk_pct",
                    0,
                )
            ),
            "pending_entries": int(
                safe_float(
                    lifecycle_summary.get(
                        "pending_entries",
                        0,
                    )
                )
            ),
            "open_positions": int(
                safe_float(
                    lifecycle_summary.get(
                        "open_positions",
                        len(open_df),
                    )
                )
            ),
            "closed_positions": int(
                safe_float(
                    lifecycle_summary.get(
                        "closed_positions",
                        len(closed_df),
                    )
                )
            ),
            "total_signals": total_signals,
            "closed_signals": closed_count,
            "pending_signals": pending_signals,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(
                win_rate,
                2,
            ),
            "average_return_pct": round(
                avg_return,
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
            "profit_factor": round(
                profit_factor,
                4,
            ),
            "expectancy_per_trade": round(
                expectancy,
                2,
            ),
            "average_holding_days": round(
                average_holding_days,
                2,
            ),
            "realized_profit_loss": round(
                closed_realized
                + open_realized,
                2,
            ),
            "unrealized_profit_loss": round(
                open_unrealized,
                2,
            ),
            "total_profit_loss": round(
                total_profit_loss,
                2,
            ),
            "sharpe_ratio": round(
                sharpe_ratio,
                4,
            ),
            "max_drawdown_pct": round(
                max_drawdown,
                4,
            ),
            "recovery_factor": round(
                recovery_factor,
                4,
            ),
        }

    def calculate_max_drawdown(
        self,
        closed_df: pd.DataFrame,
    ) -> float:
        if closed_df.empty:
            return 0.0

        pnl = numeric_series(
            closed_df,
            "realized_profit_loss",
        )

        if pnl.empty:
            return 0.0

        equity = pnl.cumsum()
        running_max = equity.cummax()

        drawdown = (
            equity - running_max
        )

        base = running_max.abs().replace(
            0,
            1,
        )

        drawdown_pct = (
            drawdown
            / base
            * 100
        )

        return float(
            drawdown_pct.min()
        )

    def calculate_sharpe_ratio(
        self,
        closed_df: pd.DataFrame,
    ) -> float:
        if closed_df.empty:
            return 0.0

        returns = numeric_series(
            closed_df,
            "realized_profit_loss_pct",
        )

        if returns.empty:
            return 0.0

        std = float(
            returns.std(
                ddof=0
            )
        )

        if std == 0:
            return 0.0

        mean = float(
            returns.mean()
        )

        return (
            mean
            / std
            * math.sqrt(252)
        )

    def build_equity_curve(
        self,
        closed_df: pd.DataFrame,
        lifecycle_df: pd.DataFrame,
    ) -> pd.DataFrame:
        source = closed_df.copy()

        if source.empty:
            source = lifecycle_df[
                lifecycle_df.get(
                    "lifecycle_status",
                    pd.Series(
                        "",
                        index=lifecycle_df.index,
                    )
                )
                .fillna("")
                .astype(str)
                .str.upper()
                .isin(
                    [
                        "CLOSED",
                        "EXITED",
                        "FULL EXIT",
                    ]
                )
            ].copy() if not lifecycle_df.empty else pd.DataFrame()

        if source.empty:
            return pd.DataFrame(
                columns=[
                    "sequence",
                    "date",
                    "symbol",
                    "trade_profit_loss",
                    "cumulative_profit_loss",
                ]
            )

        date_column = first_existing_column(
            source,
            [
                "exit_date",
                "closed_at",
                "date",
            ],
        )

        pnl_column = first_existing_column(
            source,
            [
                "realized_profit_loss",
                "profit_loss",
            ],
        )

        if not date_column or not pnl_column:
            return pd.DataFrame(
                columns=[
                    "sequence",
                    "date",
                    "symbol",
                    "trade_profit_loss",
                    "cumulative_profit_loss",
                ]
            )

        result = pd.DataFrame({
            "date": source[
                date_column
            ].astype(str),
            "symbol": source.get(
                "symbol",
                pd.Series(
                    "",
                    index=source.index,
                )
            ).astype(str),
            "trade_profit_loss": pd.to_numeric(
                source[pnl_column],
                errors="coerce",
            ).fillna(0.0),
        })

        result["date_parsed"] = pd.to_datetime(
            result["date"],
            errors="coerce",
        )

        result = result.sort_values(
            [
                "date_parsed",
                "symbol",
            ],
            kind="stable",
        ).reset_index(
            drop=True
        )

        result["sequence"] = range(
            1,
            len(result) + 1,
        )

        result["cumulative_profit_loss"] = (
            result["trade_profit_loss"].cumsum()
        )

        return result[
            [
                "sequence",
                "date",
                "symbol",
                "trade_profit_loss",
                "cumulative_profit_loss",
            ]
        ]

    def build_trade_journal(
        self,
        lifecycle_df: pd.DataFrame,
        closed_df: pd.DataFrame,
        exit_df: pd.DataFrame,
        top_buys_df: pd.DataFrame,
    ) -> pd.DataFrame:
        frames = []

        if not lifecycle_df.empty:
            frames.append(
                lifecycle_df.copy()
            )

        if not closed_df.empty:
            frames.append(
                closed_df.copy()
            )

        if not frames:
            return pd.DataFrame(
                columns=[
                    "trade_id",
                    "symbol",
                    "company",
                    "sector",
                    "status",
                    "entry_date",
                    "entry_price",
                    "exit_date",
                    "exit_price",
                    "quantity",
                    "profit_loss",
                    "profit_loss_pct",
                    "buy_reason",
                    "exit_reason",
                    "lesson",
                ]
            )

        data = pd.concat(
            frames,
            ignore_index=True,
            sort=False,
        )

        exit_lookup = build_symbol_lookup(
            exit_df
        )

        top_lookup = build_symbol_lookup(
            top_buys_df
        )

        rows = []

        for _, row in data.iterrows():
            symbol = upper_text(
                row.get(
                    "symbol",
                    "",
                )
            )

            exit_row = exit_lookup.get(
                symbol,
                {},
            )

            top_row = top_lookup.get(
                symbol,
                {},
            )

            profit_loss = first_numeric(
                row,
                [
                    "realized_profit_loss",
                    "profit_loss",
                    "unrealized_profit_loss",
                ],
            )

            profit_loss_pct = first_numeric(
                row,
                [
                    "realized_profit_loss_pct",
                    "unrealized_profit_loss_pct",
                    "return_pct",
                ],
            )

            status = upper_text(
                first_valid(
                    row.get(
                        "position_status"
                    ),
                    row.get(
                        "lifecycle_status"
                    ),
                    "UNKNOWN",
                )
            )

            buy_reason = clean_text(
                first_valid(
                    top_row.get(
                        "decision_reason"
                    ),
                    top_row.get(
                        "position_reason"
                    ),
                    "",
                )
            )

            exit_reason = clean_text(
                first_valid(
                    row.get(
                        "close_reason"
                    ),
                    row.get(
                        "last_exit_reason"
                    ),
                    exit_row.get(
                        "exit_reason"
                    ),
                    "",
                )
            )

            lesson = self.build_trade_lesson(
                status=status,
                profit_loss=profit_loss,
                profit_loss_pct=profit_loss_pct,
                exit_reason=exit_reason,
            )

            rows.append({
                "trade_id": clean_text(
                    row.get(
                        "trade_id",
                        "",
                    )
                ),
                "symbol": symbol,
                "company": clean_text(
                    first_valid(
                        row.get(
                            "company"
                        ),
                        top_row.get(
                            "company"
                        ),
                        "",
                    )
                ),
                "sector": clean_text(
                    first_valid(
                        row.get(
                            "sector"
                        ),
                        top_row.get(
                            "sector"
                        ),
                        "",
                    )
                ),
                "status": status,
                "entry_date": clean_text(
                    first_valid(
                        row.get(
                            "entry_date"
                        ),
                        row.get(
                            "signal_date"
                        ),
                        "",
                    )
                ),
                "entry_price": first_numeric(
                    row,
                    [
                        "actual_entry_price",
                        "average_cost",
                    ],
                ),
                "exit_date": clean_text(
                    first_valid(
                        row.get(
                            "exit_date"
                        ),
                        row.get(
                            "closed_at"
                        ),
                        "",
                    )
                ),
                "exit_price": first_numeric(
                    row,
                    [
                        "final_exit_price",
                        "exit_price",
                        "current_price",
                    ],
                ),
                "quantity": int(
                    first_numeric(
                        row,
                        [
                            "original_quantity",
                            "actual_quantity",
                            "remaining_quantity",
                        ],
                    )
                ),
                "profit_loss": round(
                    profit_loss,
                    2,
                ),
                "profit_loss_pct": round(
                    profit_loss_pct,
                    2,
                ),
                "buy_reason": buy_reason,
                "exit_reason": exit_reason,
                "lesson": lesson,
            })

        result = pd.DataFrame(
            rows
        )

        if not result.empty:
            result = result.drop_duplicates(
                subset=[
                    "trade_id",
                    "symbol",
                    "status",
                ],
                keep="last",
            )

        return result

    def build_trade_lesson(
        self,
        status: str,
        profit_loss: float,
        profit_loss_pct: float,
        exit_reason: str,
    ) -> str:
        if status in {
            "OPEN",
            "PARTIAL EXIT",
        }:
            return "Trade still active; continue monitoring risk and trend."

        if profit_loss > 0:
            return (
                "Profitable trade. Review which entry, sector and "
                "momentum conditions contributed to success."
            )

        if profit_loss < 0:
            return (
                "Losing trade. Review entry timing, stop placement "
                "and whether risk filters were strict enough."
            )

        if exit_reason:
            return (
                "Review exit reason and compare it with initial trade thesis."
            )

        return "Insufficient closed-trade data for lesson generation."

    def build_risk_dashboard(
        self,
        portfolio_df: pd.DataFrame,
        open_df: pd.DataFrame,
        metadata: dict,
    ) -> pd.DataFrame:
        portfolio_summary = metadata.get(
            "portfolio_summary",
            {},
        )

        rows = [
            {
                "metric": "Portfolio Risk %",
                "value": safe_float(
                    portfolio_summary.get(
                        "portfolio_risk_pct",
                        0,
                    )
                ),
                "status": risk_label(
                    safe_float(
                        portfolio_summary.get(
                            "portfolio_risk_pct",
                            0,
                        )
                    ),
                    low=1.5,
                    medium=2.5,
                ),
            },
            {
                "metric": "Capital Utilization %",
                "value": safe_float(
                    portfolio_summary.get(
                        "capital_utilization_pct",
                        0,
                    )
                ),
                "status": exposure_label(
                    safe_float(
                        portfolio_summary.get(
                            "capital_utilization_pct",
                            0,
                        )
                    )
                ),
            },
            {
                "metric": "Open Position Count",
                "value": len(open_df),
                "status": (
                    "NORMAL"
                    if len(open_df) <= 5
                    else "HIGH"
                ),
            },
            {
                "metric": "Open Unrealized P/L",
                "value": round(
                    numeric_sum(
                        open_df,
                        "unrealized_profit_loss",
                    ),
                    2,
                ),
                "status": pnl_label(
                    numeric_sum(
                        open_df,
                        "unrealized_profit_loss",
                    )
                ),
            },
            {
                "metric": "Total Max Loss",
                "value": round(
                    numeric_sum(
                        portfolio_df,
                        "max_loss",
                    ),
                    2,
                ),
                "status": "CONTROLLED",
            },
        ]

        return pd.DataFrame(
            rows
        )

    def build_portfolio_dashboard(
        self,
        portfolio_df: pd.DataFrame,
        open_df: pd.DataFrame,
        pending_df: pd.DataFrame,
    ) -> pd.DataFrame:
        rows = []

        if not open_df.empty:
            for _, row in open_df.iterrows():
                rows.append({
                    "symbol": upper_text(
                        row.get(
                            "symbol",
                            "",
                        )
                    ),
                    "status": upper_text(
                        row.get(
                            "position_status",
                            "OPEN",
                        )
                    ),
                    "entry_price": first_numeric(
                        row,
                        [
                            "actual_entry_price",
                            "average_cost",
                        ],
                    ),
                    "current_price": first_numeric(
                        row,
                        [
                            "current_price",
                            "close",
                        ],
                    ),
                    "quantity": int(
                        first_numeric(
                            row,
                            [
                                "remaining_quantity",
                                "original_quantity",
                            ],
                        )
                    ),
                    "profit_loss": first_numeric(
                        row,
                        [
                            "unrealized_profit_loss",
                            "realized_profit_loss",
                        ],
                    ),
                    "profit_loss_pct": first_numeric(
                        row,
                        [
                            "unrealized_profit_loss_pct",
                            "realized_profit_loss_pct",
                        ],
                    ),
                    "stop_loss": first_numeric(
                        row,
                        [
                            "current_stop_loss",
                            "initial_stop_loss",
                        ],
                    ),
                    "target_1": first_numeric(
                        row,
                        [
                            "target_1",
                        ],
                    ),
                    "target_2": first_numeric(
                        row,
                        [
                            "target_2",
                        ],
                    ),
                })

        if not pending_df.empty:
            for _, row in pending_df.iterrows():
                rows.append({
                    "symbol": upper_text(
                        row.get(
                            "symbol",
                            "",
                        )
                    ),
                    "status": "READY TO BUY",
                    "entry_price": first_positive_numeric(
                        row,
                        [
                            "actual_entry_price",
                            "exit_entry_price",
                            "adjusted_entry_price",
                            "suggested_entry_price",
                            "entry_high",
                            "close",
                        ],
                    ),
                    "current_price": first_numeric(
                        row,
                        [
                            "close",
                        ],
                    ),
                    "quantity": int(
                        first_positive_numeric(
                            row,
                            [
                                "actual_quantity",
                                "open_quantity",
                                "remaining_quantity",
                                "portfolio_quantity",
                                "recommended_quantity",
                                "quantity",
                            ],
                        )
                    ),
                    "profit_loss": 0.0,
                    "profit_loss_pct": 0.0,
                    "stop_loss": first_positive_numeric(
                        row,
                        [
                            "current_stop_loss",
                            "exit_suggested_stop_loss",
                            "stop_loss",
                        ],
                    ),
                    "target_1": first_positive_numeric(
                        row,
                        [
                            "target_1",
                        ],
                    ),
                    "target_2": first_positive_numeric(
                        row,
                        [
                            "target_2",
                        ],
                    ),
                })

        return pd.DataFrame(
            rows
        )

    def build_sector_dashboard(
        self,
        sector_perf_df: pd.DataFrame,
        top_buys_df: pd.DataFrame,
    ) -> pd.DataFrame:
        if not sector_perf_df.empty:
            return sector_perf_df.copy()

        if (
            top_buys_df.empty
            or "sector" not in top_buys_df.columns
        ):
            return pd.DataFrame()

        working = top_buys_df.copy()

        working["sector"] = (
            working["sector"]
            .fillna("UNKNOWN")
            .astype(str)
            .str.upper()
            .str.strip()
        )

        working["final_score"] = numeric_series(
            working,
            "final_score",
        )

        working["buy_probability"] = numeric_series(
            working,
            "buy_probability",
        )

        rows = []

        for sector, group in working.groupby(
            "sector",
            dropna=False,
        ):
            rows.append({
                "sector": sector,
                "signals": len(group),
                "average_final_score": round(
                    group["final_score"].mean(),
                    2,
                ),
                "average_buy_probability": round(
                    group["buy_probability"].mean(),
                    2,
                ),
                "buy_signals": int(
                    group.get(
                        "final_decision",
                        pd.Series(
                            "",
                            index=group.index,
                        )
                    )
                    .astype(str)
                    .str.upper()
                    .isin(
                        [
                            "BUY",
                            "STRONG BUY",
                        ]
                    )
                    .sum()
                ),
            })

        return pd.DataFrame(
            rows
        ).sort_values(
            "average_final_score",
            ascending=False,
        )

    # ---------------------------------------------------------
    # OUTPUTS
    # ---------------------------------------------------------

    def save_outputs(
        self,
        performance_metrics: dict,
        equity_curve_df: pd.DataFrame,
        trade_journal_df: pd.DataFrame,
        sector_dashboard_df: pd.DataFrame,
        risk_dashboard_df: pd.DataFrame,
        portfolio_dashboard_df: pd.DataFrame,
    ) -> dict:
        paths = {
            "performance_summary_json": (
                self.output_folder
                / "performance_summary.json"
            ),
            "performance_metrics_csv": (
                self.output_folder
                / "performance_metrics.csv"
            ),
            "equity_curve_csv": (
                self.output_folder
                / "equity_curve.csv"
            ),
            "trade_journal_csv": (
                self.output_folder
                / "trade_journal.csv"
            ),
            "sector_dashboard_csv": (
                self.output_folder
                / "sector_dashboard.csv"
            ),
            "risk_dashboard_csv": (
                self.output_folder
                / "risk_dashboard.csv"
            ),
            "portfolio_dashboard_csv": (
                self.output_folder
                / "portfolio_dashboard.csv"
            ),
        }

        paths[
            "performance_summary_json"
        ].write_text(
            json.dumps(
                make_json_safe(
                    performance_metrics
                ),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        pd.DataFrame(
            [performance_metrics]
        ).to_csv(
            paths["performance_metrics_csv"],
            index=False,
        )

        equity_curve_df.to_csv(
            paths["equity_curve_csv"],
            index=False,
        )

        trade_journal_df.to_csv(
            paths["trade_journal_csv"],
            index=False,
        )

        sector_dashboard_df.to_csv(
            paths["sector_dashboard_csv"],
            index=False,
        )

        risk_dashboard_df.to_csv(
            paths["risk_dashboard_csv"],
            index=False,
        )

        portfolio_dashboard_df.to_csv(
            paths["portfolio_dashboard_csv"],
            index=False,
        )

        return {
            key: str(value)
            for key, value in paths.items()
        }

    def generate_html_dashboard(
        self,
        performance_metrics: dict,
        portfolio_df: pd.DataFrame,
        top_buys_df: pd.DataFrame,
        open_df: pd.DataFrame,
        closed_df: pd.DataFrame,
        pending_df: pd.DataFrame,
        exit_df: pd.DataFrame,
        action_plan_df: pd.DataFrame,
        equity_curve_df: pd.DataFrame,
        sector_dashboard_df: pd.DataFrame,
        risk_dashboard_df: pd.DataFrame,
        portfolio_dashboard_df: pd.DataFrame,
        metadata: dict,
    ) -> Path:
        output_path = (
            self.output_folder
            / self.config.dashboard_filename
        )

        equity_labels = equity_curve_df.get(
            "sequence",
            pd.Series(
                dtype=int
            )
        ).tolist()

        equity_values = equity_curve_df.get(
            "cumulative_profit_loss",
            pd.Series(
                dtype=float
            )
        ).round(
            2
        ).tolist()

        sector_labels = (
            sector_dashboard_df.get(
                "sector",
                pd.Series(
                    dtype=str
                )
            )
            .astype(str)
            .head(10)
            .tolist()
        )

        sector_values = (
            numeric_series(
                sector_dashboard_df.head(10),
                first_existing_column(
                    sector_dashboard_df,
                    [
                        "total_profit_loss",
                        "average_final_score",
                        "win_rate_pct",
                    ],
                )
                or "missing",
            )
            .round(2)
            .tolist()
        )

        allocation_source = portfolio_dashboard_df.copy()

        if not allocation_source.empty:
            allocation_source["allocation_value"] = (
                pd.to_numeric(
                    allocation_source.get("entry_price", 0),
                    errors="coerce",
                ).fillna(0)
                * pd.to_numeric(
                    allocation_source.get("quantity", 0),
                    errors="coerce",
                ).fillna(0)
            )

        allocation_labels = (
            allocation_source.get(
                "symbol",
                pd.Series(dtype=str),
            )
            .astype(str)
            .tolist()
        )

        allocation_values = (
            allocation_source.get(
                "allocation_value",
                pd.Series(dtype=float),
            )
            .round(2)
            .tolist()
        )

        action_counts = (
            action_plan_df.get(
                "recommended_action",
                pd.Series(dtype=str),
            )
            .fillna("")
            .astype(str)
            .value_counts()
        )

        action_labels = action_counts.index.tolist()
        action_values = action_counts.astype(int).tolist()

        engine_health_df = pd.DataFrame(
            [
                {"engine": "Reporting Engine V3", "status": "ONLINE"},
                {"engine": "Trade Lifecycle Engine V1", "status": "ONLINE"},
                {"engine": "Exit Intelligence Engine V1", "status": "ONLINE"},
                {"engine": "Backtest Engine V1", "status": "ONLINE"},
                {"engine": "Performance Dashboard V2", "status": "ONLINE"},
            ]
        )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PSX Institutional Trading Terminal</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
:root {{
    --bg: #07111f;
    --panel: #0d1b2a;
    --panel-2: #10243a;
    --border: #1f3a56;
    --text: #e7f0f8;
    --muted: #94a8bc;
    --green: #38d996;
    --red: #ff6b6b;
    --amber: #f7c948;
    --blue: #58a6ff;
}}
* {{
    box-sizing: border-box;
}}
body {{
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: Arial, Helvetica, sans-serif;
}}
.container {{
    width: min(1500px, 96%);
    margin: 20px auto 50px;
}}
.header {{
    display: flex;
    justify-content: space-between;
    gap: 20px;
    align-items: center;
    margin-bottom: 18px;
}}
.header h1 {{
    margin: 0;
    font-size: 28px;
}}
.header small {{
    color: var(--muted);
}}
.grid {{
    display: grid;
    grid-template-columns: repeat(12, 1fr);
    gap: 14px;
}}
.card {{
    background: linear-gradient(180deg, var(--panel), var(--panel-2));
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 16px;
    box-shadow: 0 10px 28px rgba(0,0,0,.18);
}}
.kpi {{
    grid-column: span 2;
}}
.kpi .label {{
    color: var(--muted);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: .7px;
}}
.kpi .value {{
    margin-top: 8px;
    font-size: 25px;
    font-weight: 700;
}}
.span-4 {{ grid-column: span 4; }}
.span-6 {{ grid-column: span 6; }}
.span-8 {{ grid-column: span 8; }}
.span-12 {{ grid-column: span 12; }}
h2 {{
    font-size: 18px;
    margin: 0 0 12px;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
}}
th, td {{
    text-align: left;
    padding: 9px 8px;
    border-bottom: 1px solid var(--border);
}}
th {{
    color: var(--muted);
    font-weight: 600;
}}
.positive {{ color: var(--green); }}
.negative {{ color: var(--red); }}
.warning {{ color: var(--amber); }}
.badge {{
    display: inline-block;
    padding: 4px 8px;
    border-radius: 999px;
    background: rgba(88,166,255,.14);
    color: var(--blue);
    font-size: 11px;
}}
.chart-box {{
    height: 300px;
}}
@media (max-width: 1100px) {{
    .kpi {{ grid-column: span 4; }}
    .span-4, .span-6, .span-8 {{ grid-column: span 12; }}
}}
@media (max-width: 650px) {{
    .kpi {{ grid-column: span 6; }}
    .header {{ flex-direction: column; align-items: flex-start; }}
    table {{ font-size: 10px; }}
}}
</style>
</head>
<body>
<div class="container">

<div class="header">
    <div>
        <h1>PSX Institutional Trading Terminal</h1>
        <small>
            Engine: {self.VERSION} |
            Trading Date: {escape_html(str(performance_metrics.get("trading_date", "")))} |
            Generated: {escape_html(str(performance_metrics.get("generated_at", "")))}
        </small>
    </div>
    <div>
        <span class="badge">
            Market: {escape_html(str(performance_metrics.get("market_mood", "UNKNOWN")))}
        </span>
    </div>
</div>

<div class="grid">
    {kpi_card("Capital", format_money(performance_metrics.get("capital", 0)))}
    {kpi_card("Used Capital", format_money(performance_metrics.get("used_capital", 0)))}
    {kpi_card("Cash Reserve", format_money(performance_metrics.get("cash_reserve", 0)))}
    {kpi_card("Portfolio Health", format_number(performance_metrics.get("portfolio_health_score", 0)))}
    {kpi_card("Portfolio Risk", format_percent(performance_metrics.get("portfolio_risk_pct", 0)))}
    {kpi_card("Open Positions", str(performance_metrics.get("open_positions", 0)))}

    {kpi_card("Win Rate", format_percent(performance_metrics.get("win_rate_pct", 0)))}
    {kpi_card("Profit Factor", format_number(performance_metrics.get("profit_factor", 0)))}
    {kpi_card("Expectancy", format_money(performance_metrics.get("expectancy_per_trade", 0)))}
    {kpi_card("Sharpe Ratio", format_number(performance_metrics.get("sharpe_ratio", 0)))}
    {kpi_card("Max Drawdown", format_percent(performance_metrics.get("max_drawdown_pct", 0)))}
    {kpi_card("Total P/L", format_money(performance_metrics.get("total_profit_loss", 0)), pnl_class(performance_metrics.get("total_profit_loss", 0)))}
    {kpi_card("Pending Entries", str(performance_metrics.get("pending_entries", 0)))}
    {kpi_card("Closed Positions", str(performance_metrics.get("closed_positions", 0)))}
    {kpi_card("Realized P/L", format_money(performance_metrics.get("realized_profit_loss", 0)), pnl_class(performance_metrics.get("realized_profit_loss", 0)))}
    {kpi_card("Unrealized P/L", format_money(performance_metrics.get("unrealized_profit_loss", 0)), pnl_class(performance_metrics.get("unrealized_profit_loss", 0)))}
    {kpi_card("Recovery Factor", format_number(performance_metrics.get("recovery_factor", 0)))}
    {kpi_card("Average Return", format_percent(performance_metrics.get("average_return_pct", 0)))}

    <div class="card span-8">
        <h2>Equity Curve</h2>
        <div class="chart-box"><canvas id="equityChart"></canvas></div>
    </div>

    <div class="card span-4">
        <h2>Sector Performance</h2>
        <div class="chart-box"><canvas id="sectorChart"></canvas></div>
    </div>

    <div class="card span-6">
        <h2>Portfolio Allocation</h2>
        <div class="chart-box"><canvas id="allocationChart"></canvas></div>
    </div>

    <div class="card span-6">
        <h2>Action Distribution</h2>
        <div class="chart-box"><canvas id="actionChart"></canvas></div>
    </div>

    <div class="card span-12">
        <h2>Portfolio Dashboard</h2>
        {dataframe_to_html(
            portfolio_dashboard_df,
            [
                "symbol", "status", "entry_price", "current_price",
                "quantity", "profit_loss", "profit_loss_pct",
                "stop_loss", "target_1", "target_2",
            ],
            rows=25,
        )}
    </div>

    <div class="card span-6">
        <h2>Today's Action Plan</h2>
        {dataframe_to_html(
            action_plan_df,
            [
                "priority", "symbol", "recommended_action",
                "current_price", "entry_price", "stop_loss",
                "target_1", "target_2", "confidence",
            ],
            rows=20,
        )}
    </div>

    <div class="card span-6">
        <h2>Exit Intelligence</h2>
        {dataframe_to_html(
            exit_df,
            [
                "symbol", "lifecycle_status", "exit_action",
                "exit_current_price", "exit_entry_price",
                "exit_profit_loss_pct", "exit_confidence",
            ],
            rows=20,
        )}
    </div>

    <div class="card span-6">
        <h2>Top Short-Term Picks</h2>
        {dataframe_to_html(
            top_buys_df,
            [
                "symbol", "company", "sector", "close",
                "final_decision", "buy_probability",
                "risk_permission", "lifecycle_status",
            ],
            rows=20,
        )}
    </div>

    <div class="card span-6">
        <h2>Risk Dashboard</h2>
        {dataframe_to_html(
            risk_dashboard_df,
            ["metric", "value", "status"],
            rows=20,
        )}
    </div>

    <div class="card span-12">
        <h2>Engine Health Monitor</h2>
        {dataframe_to_html(
            engine_health_df,
            ["engine", "status"],
            rows=20,
        )}
    </div>

    <div class="card span-12">
        <h2>Open Positions</h2>
        {dataframe_to_html(
            open_df,
            [
                "symbol", "company", "position_status",
                "actual_entry_price", "current_price",
                "remaining_quantity", "unrealized_profit_loss",
                "unrealized_profit_loss_pct", "current_stop_loss",
                "target_1", "target_2", "holding_days",
            ],
            rows=30,
        )}
    </div>

    <div class="card span-12">
        <h2>Closed Trades</h2>
        {dataframe_to_html(
            closed_df,
            [
                "trade_id", "symbol", "company",
                "entry_date", "exit_date",
                "actual_entry_price", "final_exit_price",
                "realized_profit_loss",
                "realized_profit_loss_pct",
                "holding_days", "close_reason",
            ],
            rows=30,
        )}
    </div>
</div>
</div>

<script>
const equityLabels = {json.dumps(equity_labels)};
const equityValues = {json.dumps(equity_values)};
const sectorLabels = {json.dumps(sector_labels)};
const sectorValues = {json.dumps(sector_values)};
const allocationLabels = {json.dumps(allocation_labels)};
const allocationValues = {json.dumps(allocation_values)};
const actionLabels = {json.dumps(action_labels)};
const actionValues = {json.dumps(action_values)};

new Chart(document.getElementById('equityChart'), {{
    type: 'line',
    data: {{
        labels: equityLabels,
        datasets: [{{
            label: 'Cumulative P/L',
            data: equityValues,
            tension: 0.3,
            fill: true
        }}]
    }},
    options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
            legend: {{ labels: {{ color: '#e7f0f8' }} }}
        }},
        scales: {{
            x: {{
                ticks: {{ color: '#94a8bc' }},
                grid: {{ color: 'rgba(255,255,255,.05)' }}
            }},
            y: {{
                ticks: {{ color: '#94a8bc' }},
                grid: {{ color: 'rgba(255,255,255,.05)' }}
            }}
        }}
    }}
}});

new Chart(document.getElementById('sectorChart'), {{
    type: 'bar',
    data: {{
        labels: sectorLabels,
        datasets: [{{
            label: 'Sector Metric',
            data: sectorValues
        }}]
    }},
    options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
            legend: {{ labels: {{ color: '#e7f0f8' }} }}
        }},
        scales: {{
            x: {{
                ticks: {{ color: '#94a8bc' }},
                grid: {{ color: 'rgba(255,255,255,.05)' }}
            }},
            y: {{
                ticks: {{ color: '#94a8bc' }},
                grid: {{ color: 'rgba(255,255,255,.05)' }}
            }}
        }}
    }}
}});

new Chart(document.getElementById('allocationChart'), {{
    type: 'doughnut',
    data: {{
        labels: allocationLabels,
        datasets: [{{
            label: 'Allocation',
            data: allocationValues
        }}]
    }},
    options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
            legend: {{ labels: {{ color: '#e7f0f8' }} }}
        }}
    }}
}});

new Chart(document.getElementById('actionChart'), {{
    type: 'bar',
    data: {{
        labels: actionLabels,
        datasets: [{{
            label: 'Actions',
            data: actionValues
        }}]
    }},
    options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
            legend: {{ labels: {{ color: '#e7f0f8' }} }}
        }},
        scales: {{
            x: {{
                ticks: {{ color: '#94a8bc' }},
                grid: {{ color: 'rgba(255,255,255,.05)' }}
            }},
            y: {{
                beginAtZero: true,
                ticks: {{ color: '#94a8bc' }},
                grid: {{ color: 'rgba(255,255,255,.05)' }}
            }}
        }}
    }}
}});
</script>
</body>
</html>
"""

        output_path.write_text(
            html,
            encoding="utf-8",
        )

        latest_dashboard = (
            Path(self.config.reports_root)
            / "latest_dashboard_v2.html"
        )

        latest_dashboard.write_text(
            html,
            encoding="utf-8",
        )

        return output_path


def run_performance_dashboard_v2(
    reports_root: str = "reports",
    latest_folder: str = "reports/latest",
    backtest_folder: str = "reports/backtests",
    lifecycle_folder: str = "database/portfolio",
    output_folder: str = "reports/dashboard",
    dashboard_filename: str = "dashboard.html",
) -> dict:
    engine = PerformanceDashboardV1(
        reports_root=reports_root,
        latest_folder=latest_folder,
        backtest_folder=backtest_folder,
        lifecycle_folder=lifecycle_folder,
        output_folder=output_folder,
        dashboard_filename=dashboard_filename,
    )

    return engine.run()


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

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


def first_existing_column(
    df: pd.DataFrame,
    columns: list[str],
) -> str:
    if (
        df is None
        or not hasattr(
            df,
            "columns",
        )
    ):
        return ""

    for column in columns:
        if column in df.columns:
            return column

    return ""


def first_numeric(
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

        if number is not None:
            return number

    return 0.0


def first_positive_numeric(
    row: Any,
    columns: list[str],
) -> float:
    for column in columns:
        try:
            value = row.get(column, None)
        except Exception:
            value = None

        number = safe_float(value, None)

        if number is not None and number > 0:
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


def normalize_profit_factor(
    value: Any,
) -> float:
    if str(value).strip().upper() == "INF":
        return 999.0

    return safe_float(
        value,
        0.0,
    ) or 0.0


def build_symbol_lookup(
    df: pd.DataFrame,
) -> dict[str, dict]:
    if (
        df is None
        or df.empty
        or "symbol" not in df.columns
    ):
        return {}

    lookup = {}

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
    return clean_text(value).upper()


def make_json_safe(
    value: Any,
) -> Any:
    if isinstance(value, dict):
        return {
            str(key): make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            make_json_safe(item)
            for item in value
        ]

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    return value


def escape_html(
    value: str,
) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


def dataframe_to_html(
    df: pd.DataFrame,
    columns: list[str],
    rows: int = 20,
) -> str:
    if (
        df is None
        or df.empty
    ):
        return "<p style='color:#94a8bc'>No records found.</p>"

    available = [
        column
        for column in columns
        if column in df.columns
    ]

    if not available:
        return "<p style='color:#94a8bc'>No matching columns found.</p>"

    view = df[
        available
    ].head(rows).copy()

    html = [
        "<div style='overflow:auto'>",
        "<table>",
        "<thead><tr>",
    ]

    for column in available:
        html.append(
            f"<th>{escape_html(column.replace('_', ' ').title())}</th>"
        )

    html.append("</tr></thead><tbody>")

    for _, row in view.iterrows():
        html.append("<tr>")

        for column in available:
            value = row.get(
                column,
                "",
            )

            if isinstance(
                value,
                float,
            ):
                value = round(
                    value,
                    2,
                )

            css_class = ""

            if column in {
                "profit_loss",
                "profit_loss_pct",
                "unrealized_profit_loss",
                "unrealized_profit_loss_pct",
                "realized_profit_loss",
                "realized_profit_loss_pct",
            }:
                number = safe_float(
                    value,
                    0.0,
                ) or 0.0

                css_class = (
                    "positive"
                    if number > 0
                    else (
                        "negative"
                        if number < 0
                        else ""
                    )
                )

            html.append(
                f"<td class='{css_class}'>{escape_html(str(value))}</td>"
            )

        html.append("</tr>")

    html.append("</tbody></table></div>")

    return "".join(html)


def kpi_card(
    label: str,
    value: str,
    css_class: str = "",
) -> str:
    return (
        "<div class='card kpi'>"
        f"<div class='label'>{escape_html(label)}</div>"
        f"<div class='value {css_class}'>{escape_html(value)}</div>"
        "</div>"
    )


def format_money(
    value: Any,
) -> str:
    number = safe_float(
        value,
        0.0,
    ) or 0.0

    return f"PKR {number:,.2f}"


def format_number(
    value: Any,
) -> str:
    number = safe_float(
        value,
        0.0,
    ) or 0.0

    return f"{number:,.2f}"


def format_percent(
    value: Any,
) -> str:
    number = safe_float(
        value,
        0.0,
    ) or 0.0

    return f"{number:,.2f}%"


def pnl_class(
    value: Any,
) -> str:
    number = safe_float(
        value,
        0.0,
    ) or 0.0

    if number > 0:
        return "positive"

    if number < 0:
        return "negative"

    return ""


def risk_label(
    value: float,
    low: float,
    medium: float,
) -> str:
    if value <= low:
        return "LOW"

    if value <= medium:
        return "MEDIUM"

    return "HIGH"


def exposure_label(
    value: float,
) -> str:
    if value < 35:
        return "LOW EXPOSURE"

    if value < 75:
        return "BALANCED"

    return "HIGH EXPOSURE"


def pnl_label(
    value: float,
) -> str:
    if value > 0:
        return "PROFIT"

    if value < 0:
        return "LOSS"

    return "FLAT"
