from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from app.engines.backtesting.signal_tracker_v1 import (
    SIGNAL_HISTORY_FILE,
    SignalTrackerV1,
)


DEFAULT_REPORT_FOLDER = Path(
    "reports/backtests"
)


@dataclass
class PerformanceAnalyzerConfigV1:
    signal_history_file: Path = SIGNAL_HISTORY_FILE
    report_folder: Path = DEFAULT_REPORT_FOLDER
    min_closed_signals_for_rating: int = 10


class PerformanceAnalyzerV1:
    """
    Performance Analyzer V1

    Reads completed backtest signals and produces:
    - Overall trading performance
    - Win/loss statistics
    - Profit factor and expectancy
    - Average return and drawdown
    - Sector performance
    - Market mood performance
    - Decision and risk-permission performance
    - Symbol performance
    - Engine quality rating
    - CSV and Markdown reports
    """

    VERSION = "performance_analyzer_v1"

    def __init__(
        self,
        signal_history_file: str | Path = SIGNAL_HISTORY_FILE,
        report_folder: str | Path = DEFAULT_REPORT_FOLDER,
        min_closed_signals_for_rating: int = 10,
    ):
        self.config = PerformanceAnalyzerConfigV1(
            signal_history_file=Path(
                signal_history_file
            ),
            report_folder=Path(
                report_folder
            ),
            min_closed_signals_for_rating=int(
                min_closed_signals_for_rating
            ),
        )

        self.tracker = SignalTrackerV1(
            history_file=self.config.signal_history_file
        )

    def run(self) -> dict:
        history = self.tracker.load_history()

        if history.empty:
            return {
                "status": "success",
                "engine_version": self.VERSION,
                "reason": "No signal history available",
                "total_signals": 0,
                "closed_signals": 0,
                "report_folder": str(
                    self.config.report_folder
                ),
            }

        prepared = self.prepare_history(
            history
        )

        overall = self.calculate_overall_metrics(
            prepared
        )

        by_sector = self.group_performance(
            prepared,
            "sector",
        )
        by_market_mood = self.group_performance(
            prepared,
            "market_mood",
        )
        by_decision = self.group_performance(
            prepared,
            "decision",
        )
        by_consensus = self.group_performance(
            prepared,
            "consensus_decision",
        )
        by_risk_permission = self.group_performance(
            prepared,
            "risk_permission",
        )
        by_symbol = self.group_performance(
            prepared,
            "symbol",
        )
        by_entry_action = self.group_performance(
            prepared,
            "entry_action",
        )

        rating = self.engine_rating(
            overall
        )

        report_paths = self.write_reports(
            overall=overall,
            rating=rating,
            by_sector=by_sector,
            by_market_mood=by_market_mood,
            by_decision=by_decision,
            by_consensus=by_consensus,
            by_risk_permission=by_risk_permission,
            by_symbol=by_symbol,
            by_entry_action=by_entry_action,
        )

        return {
            "status": "success",
            "engine_version": self.VERSION,
            "reason": "Performance analysis completed successfully",
            "signal_history_file": str(
                self.config.signal_history_file
            ),
            "report_folder": str(
                self.config.report_folder
            ),
            "overall": overall,
            "engine_rating": rating,
            "reports": report_paths,
        }

    def prepare_history(
        self,
        history: pd.DataFrame,
    ) -> pd.DataFrame:
        data = history.copy()

        numeric_columns = [
            "return_pct",
            "profit_loss",
            "max_favorable_excursion_pct",
            "max_adverse_excursion_pct",
            "final_score",
            "consensus_score",
            "buy_probability",
            "portfolio_rank_score",
            "position_quality_index",
            "institutional_portfolio_score",
            "smart_money_score",
            "accumulation_score",
            "trade_validation_score",
            "entry_timing_score",
            "risk_management_score",
            "investment",
            "max_loss",
            "expected_profit_t1",
            "expected_profit_t2",
            "holding_days",
        ]

        for column in numeric_columns:
            if column not in data.columns:
                data[column] = 0.0

            data[column] = pd.to_numeric(
                data[column],
                errors="coerce",
            ).fillna(0.0)

        text_columns = [
            "tracking_status",
            "outcome_status",
            "sector",
            "market_mood",
            "decision",
            "consensus_decision",
            "risk_permission",
            "symbol",
            "entry_action",
        ]

        for column in text_columns:
            if column not in data.columns:
                data[column] = ""

            data[column] = (
                data[column]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.upper()
            )

        data["is_closed"] = (
            data["tracking_status"]
            == "CLOSED"
        )

        data["is_win"] = data[
            "outcome_status"
        ].isin(
            [
                "TARGET_1 HIT",
                "TARGET_2 HIT",
            ]
        )

        data["is_loss"] = (
            data["outcome_status"]
            == "STOP LOSS HIT"
        )

        data["is_time_exit"] = (
            data["outcome_status"]
            == "TIME EXIT"
        )

        data["is_profitable"] = (
            data["profit_loss"] > 0
        )

        data["is_losing"] = (
            data["profit_loss"] < 0
        )

        return data

    def calculate_overall_metrics(
        self,
        data: pd.DataFrame,
    ) -> dict:
        total_signals = len(data)

        closed = data[
            data["is_closed"]
        ].copy()

        pending = total_signals - len(
            closed
        )

        wins = int(
            closed["is_win"].sum()
        )
        losses = int(
            closed["is_loss"].sum()
        )
        time_exits = int(
            closed["is_time_exit"].sum()
        )

        profitable_trades = int(
            closed["is_profitable"].sum()
        )
        losing_trades = int(
            closed["is_losing"].sum()
        )

        decisive = wins + losses

        win_rate = (
            wins / decisive * 100
            if decisive > 0
            else 0.0
        )

        profitable_rate = (
            profitable_trades
            / len(closed)
            * 100
            if len(closed) > 0
            else 0.0
        )

        avg_return = safe_mean(
            closed["return_pct"]
        )

        median_return = safe_median(
            closed["return_pct"]
        )

        avg_profit_loss = safe_mean(
            closed["profit_loss"]
        )

        total_profit_loss = safe_sum(
            closed["profit_loss"]
        )

        gross_profit = safe_sum(
            closed.loc[
                closed["profit_loss"] > 0,
                "profit_loss",
            ]
        )

        gross_loss = abs(
            safe_sum(
                closed.loc[
                    closed["profit_loss"] < 0,
                    "profit_loss",
                ]
            )
        )

        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else (
                float("inf")
                if gross_profit > 0
                else 0.0
            )
        )

        average_win = safe_mean(
            closed.loc[
                closed["profit_loss"] > 0,
                "profit_loss",
            ]
        )

        average_loss = safe_mean(
            closed.loc[
                closed["profit_loss"] < 0,
                "profit_loss",
            ]
        )

        expectancy = self.calculate_expectancy(
            closed
        )

        avg_mfe = safe_mean(
            closed[
                "max_favorable_excursion_pct"
            ]
        )

        avg_mae = safe_mean(
            closed[
                "max_adverse_excursion_pct"
            ]
        )

        avg_holding_days = safe_mean(
            closed["holding_days"]
        )

        best_trade = (
            closed.loc[
                closed["profit_loss"].idxmax()
            ].to_dict()
            if not closed.empty
            else {}
        )

        worst_trade = (
            closed.loc[
                closed["profit_loss"].idxmin()
            ].to_dict()
            if not closed.empty
            else {}
        )

        return {
            "total_signals": int(
                total_signals
            ),
            "closed_signals": int(
                len(closed)
            ),
            "pending_signals": int(
                pending
            ),
            "wins": wins,
            "losses": losses,
            "time_exits": time_exits,
            "profitable_trades": profitable_trades,
            "losing_trades": losing_trades,
            "win_rate_pct": round(
                win_rate,
                2,
            ),
            "profitable_trade_rate_pct": round(
                profitable_rate,
                2,
            ),
            "average_return_pct": round(
                avg_return,
                4,
            ),
            "median_return_pct": round(
                median_return,
                4,
            ),
            "average_profit_loss": round(
                avg_profit_loss,
                2,
            ),
            "total_profit_loss": round(
                total_profit_loss,
                2,
            ),
            "gross_profit": round(
                gross_profit,
                2,
            ),
            "gross_loss": round(
                gross_loss,
                2,
            ),
            "profit_factor": (
                "INF"
                if profit_factor
                == float("inf")
                else round(
                    profit_factor,
                    4,
                )
            ),
            "average_win": round(
                average_win,
                2,
            ),
            "average_loss": round(
                average_loss,
                2,
            ),
            "expectancy_per_trade": round(
                expectancy,
                2,
            ),
            "average_mfe_pct": round(
                avg_mfe,
                4,
            ),
            "average_mae_pct": round(
                avg_mae,
                4,
            ),
            "average_holding_days": round(
                avg_holding_days,
                2,
            ),
            "best_trade_symbol": str(
                best_trade.get(
                    "symbol",
                    "",
                )
            ),
            "best_trade_profit_loss": round(
                safe_float(
                    best_trade.get(
                        "profit_loss",
                        0,
                    )
                ),
                2,
            ),
            "worst_trade_symbol": str(
                worst_trade.get(
                    "symbol",
                    "",
                )
            ),
            "worst_trade_profit_loss": round(
                safe_float(
                    worst_trade.get(
                        "profit_loss",
                        0,
                    )
                ),
                2,
            ),
        }

    def calculate_expectancy(
        self,
        closed: pd.DataFrame,
    ) -> float:
        if closed.empty:
            return 0.0

        wins = closed[
            closed["profit_loss"] > 0
        ]

        losses = closed[
            closed["profit_loss"] < 0
        ]

        win_probability = (
            len(wins)
            / len(closed)
        )

        loss_probability = (
            len(losses)
            / len(closed)
        )

        average_win = safe_mean(
            wins["profit_loss"]
        )

        average_loss = abs(
            safe_mean(
                losses["profit_loss"]
            )
        )

        return (
            win_probability
            * average_win
            - loss_probability
            * average_loss
        )

    def group_performance(
        self,
        data: pd.DataFrame,
        group_column: str,
    ) -> pd.DataFrame:
        if (
            group_column
            not in data.columns
        ):
            return pd.DataFrame()

        closed = data[
            data["is_closed"]
        ].copy()

        if closed.empty:
            return pd.DataFrame(
                columns=[
                    group_column,
                    "signals",
                    "wins",
                    "losses",
                    "time_exits",
                    "win_rate_pct",
                    "profitable_rate_pct",
                    "average_return_pct",
                    "total_profit_loss",
                    "profit_factor",
                    "average_mfe_pct",
                    "average_mae_pct",
                    "average_holding_days",
                ]
            )

        rows = []

        for group_value, group in closed.groupby(
            group_column,
            dropna=False,
        ):
            wins = int(
                group["is_win"].sum()
            )

            losses = int(
                group["is_loss"].sum()
            )

            time_exits = int(
                group[
                    "is_time_exit"
                ].sum()
            )

            decisive = wins + losses

            win_rate = (
                wins / decisive * 100
                if decisive > 0
                else 0.0
            )

            profitable_rate = (
                (
                    group[
                        "profit_loss"
                    ]
                    > 0
                ).sum()
                / len(group)
                * 100
                if len(group) > 0
                else 0.0
            )

            gross_profit = safe_sum(
                group.loc[
                    group[
                        "profit_loss"
                    ]
                    > 0,
                    "profit_loss",
                ]
            )

            gross_loss = abs(
                safe_sum(
                    group.loc[
                        group[
                            "profit_loss"
                        ]
                        < 0,
                        "profit_loss",
                    ]
                )
            )

            if gross_loss > 0:
                profit_factor = (
                    gross_profit
                    / gross_loss
                )
            elif gross_profit > 0:
                profit_factor = 999.0
            else:
                profit_factor = 0.0

            rows.append({
                group_column: (
                    str(group_value)
                    if str(
                        group_value
                    ).strip()
                    else "UNKNOWN"
                ),
                "signals": int(
                    len(group)
                ),
                "wins": wins,
                "losses": losses,
                "time_exits": time_exits,
                "win_rate_pct": round(
                    win_rate,
                    2,
                ),
                "profitable_rate_pct": round(
                    profitable_rate,
                    2,
                ),
                "average_return_pct": round(
                    safe_mean(
                        group[
                            "return_pct"
                        ]
                    ),
                    4,
                ),
                "total_profit_loss": round(
                    safe_sum(
                        group[
                            "profit_loss"
                        ]
                    ),
                    2,
                ),
                "profit_factor": round(
                    profit_factor,
                    4,
                ),
                "average_mfe_pct": round(
                    safe_mean(
                        group[
                            "max_favorable_excursion_pct"
                        ]
                    ),
                    4,
                ),
                "average_mae_pct": round(
                    safe_mean(
                        group[
                            "max_adverse_excursion_pct"
                        ]
                    ),
                    4,
                ),
                "average_holding_days": round(
                    safe_mean(
                        group[
                            "holding_days"
                        ]
                    ),
                    2,
                ),
            })

        result = pd.DataFrame(
            rows
        )

        if not result.empty:
            result = result.sort_values(
                by=[
                    "total_profit_loss",
                    "win_rate_pct",
                    "signals",
                ],
                ascending=[
                    False,
                    False,
                    False,
                ],
                kind="stable",
            ).reset_index(
                drop=True
            )

        return result

    def engine_rating(
        self,
        overall: dict,
    ) -> dict:
        closed = int(
            overall.get(
                "closed_signals",
                0,
            )
        )

        if (
            closed
            < self.config.min_closed_signals_for_rating
        ):
            return {
                "rating": "INSUFFICIENT DATA",
                "score": 0,
                "reason": (
                    f"At least "
                    f"{self.config.min_closed_signals_for_rating} "
                    f"closed signals required"
                ),
            }

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

        expectancy = safe_float(
            overall.get(
                "expectancy_per_trade",
                0,
            )
        )

        profit_factor_value = overall.get(
            "profit_factor",
            0,
        )

        if profit_factor_value == "INF":
            profit_factor = 3.0
        else:
            profit_factor = safe_float(
                profit_factor_value
            )

        avg_mae = abs(
            safe_float(
                overall.get(
                    "average_mae_pct",
                    0,
                )
            )
        )

        score = 0.0

        score += clamp(
            win_rate,
            0,
            70,
        ) * 0.40

        score += clamp(
            avg_return * 10,
            -20,
            30,
        )

        score += clamp(
            profit_factor * 10,
            0,
            25,
        )

        score += clamp(
            expectancy / 10,
            -10,
            15,
        )

        score += clamp(
            15 - avg_mae,
            0,
            15,
        )

        score = clamp(
            score,
            0,
            100,
        )

        if score >= 85:
            rating = "EXCELLENT"
        elif score >= 70:
            rating = "VERY GOOD"
        elif score >= 55:
            rating = "GOOD"
        elif score >= 40:
            rating = "WEAK"
        else:
            rating = "POOR"

        return {
            "rating": rating,
            "score": round(
                score,
                2,
            ),
            "reason": (
                "Rating based on win rate, average return, "
                "profit factor, expectancy and drawdown"
            ),
        }

    def write_reports(
        self,
        overall: dict,
        rating: dict,
        by_sector: pd.DataFrame,
        by_market_mood: pd.DataFrame,
        by_decision: pd.DataFrame,
        by_consensus: pd.DataFrame,
        by_risk_permission: pd.DataFrame,
        by_symbol: pd.DataFrame,
        by_entry_action: pd.DataFrame,
    ) -> dict:
        folder = self.config.report_folder

        folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        files = {
            "overall_csv": folder
            / "overall_performance.csv",
            "sector_csv": folder
            / "performance_by_sector.csv",
            "market_mood_csv": folder
            / "performance_by_market_mood.csv",
            "decision_csv": folder
            / "performance_by_decision.csv",
            "consensus_csv": folder
            / "performance_by_consensus.csv",
            "risk_permission_csv": folder
            / "performance_by_risk_permission.csv",
            "symbol_csv": folder
            / "performance_by_symbol.csv",
            "entry_action_csv": folder
            / "performance_by_entry_action.csv",
            "summary_md": folder
            / "backtest_performance_summary.md",
        }

        pd.DataFrame(
            [
                {
                    **overall,
                    "engine_rating": rating.get(
                        "rating",
                        "",
                    ),
                    "engine_rating_score": rating.get(
                        "score",
                        0,
                    ),
                }
            ]
        ).to_csv(
            files["overall_csv"],
            index=False,
        )

        by_sector.to_csv(
            files["sector_csv"],
            index=False,
        )
        by_market_mood.to_csv(
            files["market_mood_csv"],
            index=False,
        )
        by_decision.to_csv(
            files["decision_csv"],
            index=False,
        )
        by_consensus.to_csv(
            files["consensus_csv"],
            index=False,
        )
        by_risk_permission.to_csv(
            files[
                "risk_permission_csv"
            ],
            index=False,
        )
        by_symbol.to_csv(
            files["symbol_csv"],
            index=False,
        )
        by_entry_action.to_csv(
            files[
                "entry_action_csv"
            ],
            index=False,
        )

        markdown = self.build_markdown_summary(
            overall=overall,
            rating=rating,
            by_sector=by_sector,
            by_market_mood=by_market_mood,
            by_decision=by_decision,
            by_symbol=by_symbol,
        )

        files["summary_md"].write_text(
            markdown,
            encoding="utf-8",
        )

        return {
            key: str(path)
            for key, path in files.items()
        }

    def build_markdown_summary(
        self,
        overall: dict,
        rating: dict,
        by_sector: pd.DataFrame,
        by_market_mood: pd.DataFrame,
        by_decision: pd.DataFrame,
        by_symbol: pd.DataFrame,
    ) -> str:
        lines = [
            "# PSX Backtesting Performance Summary",
            "",
            f"- Engine: `{self.VERSION}`",
            f"- Rating: **{rating.get('rating', '')}**",
            f"- Rating Score: **{rating.get('score', 0)}**",
            "",
            "## Overall Performance",
            "",
        ]

        for key, value in overall.items():
            lines.append(
                f"- **{key.replace('_', ' ').title()}**: {value}"
            )

        lines.extend(
            [
                "",
                "## Best Sectors",
                "",
                dataframe_to_markdown(
                    by_sector.head(10)
                ),
                "",
                "## Market Mood Performance",
                "",
                dataframe_to_markdown(
                    by_market_mood.head(10)
                ),
                "",
                "## Decision Performance",
                "",
                dataframe_to_markdown(
                    by_decision.head(10)
                ),
                "",
                "## Best Symbols",
                "",
                dataframe_to_markdown(
                    by_symbol.head(10)
                ),
                "",
            ]
        )

        return "\n".join(
            lines
        )


def run_performance_analyzer_v1(
    signal_history_file: str | Path = SIGNAL_HISTORY_FILE,
    report_folder: str | Path = DEFAULT_REPORT_FOLDER,
    min_closed_signals_for_rating: int = 10,
) -> dict:
    engine = PerformanceAnalyzerV1(
        signal_history_file=signal_history_file,
        report_folder=report_folder,
        min_closed_signals_for_rating=min_closed_signals_for_rating,
    )

    return engine.run()


def dataframe_to_markdown(
    df: pd.DataFrame,
) -> str:
    if df is None or df.empty:
        return "_No data available._"

    columns = list(
        df.columns
    )

    header = (
        "| "
        + " | ".join(
            columns
        )
        + " |"
    )

    separator = (
        "| "
        + " | ".join(
            ["---"]
            * len(columns)
        )
        + " |"
    )

    rows = [
        header,
        separator,
    ]

    for _, row in df.iterrows():
        values = []

        for column in columns:
            value = row.get(
                column,
                "",
            )

            text = str(
                value
            ).replace(
                "|",
                "/",
            )

            values.append(
                text
            )

        rows.append(
            "| "
            + " | ".join(
                values
            )
            + " |"
        )

    return "\n".join(
        rows
    )


def safe_mean(
    series: pd.Series,
) -> float:
    if series is None or len(series) == 0:
        return 0.0

    values = pd.to_numeric(
        series,
        errors="coerce",
    ).dropna()

    if values.empty:
        return 0.0

    return float(
        values.mean()
    )


def safe_median(
    series: pd.Series,
) -> float:
    if series is None or len(series) == 0:
        return 0.0

    values = pd.to_numeric(
        series,
        errors="coerce",
    ).dropna()

    if values.empty:
        return 0.0

    return float(
        values.median()
    )


def safe_sum(
    series: pd.Series,
) -> float:
    if series is None or len(series) == 0:
        return 0.0

    values = pd.to_numeric(
        series,
        errors="coerce",
    ).fillna(0)

    return float(
        values.sum()
    )


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        if pd.isna(value):
            return float(
                default
            )
    except Exception:
        pass

    try:
        return float(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return float(
            default
        )


def clamp(
    value: float,
    low: float,
    high: float,
) -> float:
    try:
        numeric = float(
            value
        )
    except Exception:
        numeric = low

    return max(
        low,
        min(
            high,
            numeric,
        ),
    )