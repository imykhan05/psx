from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class StrategyOptimizerConfigV2:
    strategy_folder: str = "reports/strategy_analytics"
    journal_folder: str = "reports/trade_journal"
    output_folder: str = "database/strategy_learning"
    report_folder: str = "reports/strategy_optimizer"

    strategy_analytics_filename: str = "strategy_analytics.csv"
    strategy_monthly_filename: str = "strategy_monthly.csv"
    strategy_equity_filename: str = "strategy_equity.csv"
    trade_journal_filename: str = "trade_journal.csv"

    optimizer_output_filename: str = "strategy_optimizer_output.csv"
    strategy_weights_filename: str = "strategy_weights_v2.csv"
    strategy_actions_filename: str = "strategy_actions_v2.csv"
    learning_summary_filename: str = "strategy_learning_summary.csv"
    latest_weights_filename: str = "latest_strategy_weights.json"


class StrategyOptimizerSelfLearningV2:
    """
    Strategy Optimizer & Self-Learning Engine V2

    Reads Strategy Analytics V1 and Trade Journal Pro outputs, then generates
    safe, sample-aware strategy weights and operational recommendations.

    Important safeguards
    --------------------
    - No strategy is disabled on tiny samples.
    - Minimum closed-trade thresholds control confidence.
    - Weight changes are capped.
    - Output is advisory by default; it does not silently rewrite AI engines.
    - Strategies with insufficient data remain in LEARNING mode.
    """

    VERSION = "strategy_optimizer_self_learning_v2_0_sample_safe"

    def __init__(
        self,
        strategy_folder: str = "reports/strategy_analytics",
        journal_folder: str = "reports/trade_journal",
        output_folder: str = "database/strategy_learning",
        report_folder: str = "reports/strategy_optimizer",
        minimum_closed_trades: int = 10,
        strong_sample_trades: int = 25,
        disable_sample_trades: int = 30,
        maximum_weight_change: float = 0.15,
        minimum_weight: float = 0.50,
        maximum_weight: float = 1.50,
    ):
        self.config = StrategyOptimizerConfigV2(
            strategy_folder=strategy_folder,
            journal_folder=journal_folder,
            output_folder=output_folder,
            report_folder=report_folder,
        )

        self.strategy_folder = Path(
            self.config.strategy_folder
        )
        self.journal_folder = Path(
            self.config.journal_folder
        )
        self.output_folder = Path(
            self.config.output_folder
        )
        self.report_folder = Path(
            self.config.report_folder
        )

        self.output_folder.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.report_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.minimum_closed_trades = max(
            int(minimum_closed_trades),
            1,
        )
        self.strong_sample_trades = max(
            int(strong_sample_trades),
            self.minimum_closed_trades,
        )
        self.disable_sample_trades = max(
            int(disable_sample_trades),
            self.strong_sample_trades,
        )

        self.maximum_weight_change = max(
            0.0,
            float(maximum_weight_change),
        )
        self.minimum_weight = max(
            0.0,
            float(minimum_weight),
        )
        self.maximum_weight = max(
            self.minimum_weight,
            float(maximum_weight),
        )

        self.analytics_path = (
            self.strategy_folder
            / self.config.strategy_analytics_filename
        )
        self.monthly_path = (
            self.strategy_folder
            / self.config.strategy_monthly_filename
        )
        self.equity_path = (
            self.strategy_folder
            / self.config.strategy_equity_filename
        )
        self.journal_path = (
            self.journal_folder
            / self.config.trade_journal_filename
        )

        self.optimizer_output_path = (
            self.report_folder
            / self.config.optimizer_output_filename
        )
        self.strategy_weights_path = (
            self.output_folder
            / self.config.strategy_weights_filename
        )
        self.strategy_actions_path = (
            self.report_folder
            / self.config.strategy_actions_filename
        )
        self.learning_summary_path = (
            self.report_folder
            / self.config.learning_summary_filename
        )
        self.latest_weights_path = (
            self.output_folder
            / self.config.latest_weights_filename
        )

    # ---------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------

    def run(
        self,
        starting_capital: float = 50000.0,
    ) -> dict:
        starting_capital = positive_float(
            starting_capital,
            "starting_capital",
        )

        analytics_df = self.read_csv(
            self.analytics_path
        )
        monthly_df = self.read_csv(
            self.monthly_path
        )
        equity_df = self.read_csv(
            self.equity_path
        )
        journal_df = self.read_csv(
            self.journal_path
        )

        analytics_df = self.normalize_analytics(
            analytics_df
        )

        optimizer_df = self.build_optimizer_output(
            analytics_df=analytics_df,
            monthly_df=monthly_df,
            equity_df=equity_df,
            journal_df=journal_df,
            starting_capital=starting_capital,
        )

        weights_df = self.build_weights(
            optimizer_df
        )

        actions_df = self.build_actions(
            optimizer_df
        )

        summary = self.build_summary(
            optimizer_df=optimizer_df,
            weights_df=weights_df,
        )

        self.save_dataframe(
            optimizer_df,
            self.optimizer_output_path,
            self.optimizer_columns(),
        )

        self.save_dataframe(
            weights_df,
            self.strategy_weights_path,
            self.weight_columns(),
        )

        self.save_dataframe(
            actions_df,
            self.strategy_actions_path,
            self.action_columns(),
        )

        pd.DataFrame(
            [summary]
        ).to_csv(
            self.learning_summary_path,
            index=False,
            encoding="utf-8-sig",
        )

        self.write_latest_weights_json(
            weights_df=weights_df,
            summary=summary,
        )

        return {
            "status": "success",
            "engine_version": self.VERSION,
            "strategies_processed": int(
                len(optimizer_df)
            ),
            "strategies_active": int(
                (
                    optimizer_df.get(
                        "operating_status",
                        pd.Series(dtype=str),
                    )
                    .astype(str)
                    .str.upper()
                    .eq("ACTIVE")
                ).sum()
            )
            if not optimizer_df.empty
            else 0,
            "strategies_learning": int(
                (
                    optimizer_df.get(
                        "operating_status",
                        pd.Series(dtype=str),
                    )
                    .astype(str)
                    .str.upper()
                    .eq("LEARNING")
                ).sum()
            )
            if not optimizer_df.empty
            else 0,
            "strategies_reduced": int(
                (
                    optimizer_df.get(
                        "recommended_action",
                        pd.Series(dtype=str),
                    )
                    .astype(str)
                    .str.upper()
                    .eq("REDUCE")
                ).sum()
            )
            if not optimizer_df.empty
            else 0,
            "optimizer_output_csv": str(
                self.optimizer_output_path
            ),
            "strategy_weights_csv": str(
                self.strategy_weights_path
            ),
            "strategy_actions_csv": str(
                self.strategy_actions_path
            ),
            "learning_summary_csv": str(
                self.learning_summary_path
            ),
            "latest_weights_json": str(
                self.latest_weights_path
            ),
            "reason": (
                "Sample-safe strategy optimization completed successfully"
            ),
        }

    # ---------------------------------------------------------
    # NORMALIZATION
    # ---------------------------------------------------------

    def normalize_analytics(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        df = remove_duplicate_columns(
            df
        )

        if df.empty:
            return pd.DataFrame(
                columns=[
                    "strategy",
                    "closed_trades",
                    "win_rate_pct",
                    "profit_factor",
                    "expectancy",
                    "average_return_pct",
                    "sharpe_ratio",
                    "maximum_drawdown_pct",
                    "recovery_factor",
                    "strategy_score",
                    "net_profit_loss",
                ]
            )

        defaults = {
            "strategy": "UNCLASSIFIED",
            "closed_trades": 0,
            "win_rate_pct": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "average_return_pct": 0.0,
            "sharpe_ratio": 0.0,
            "maximum_drawdown_pct": 0.0,
            "recovery_factor": 0.0,
            "strategy_score": 0.0,
            "net_profit_loss": 0.0,
            "status": "",
        }

        for column, default in defaults.items():
            if column not in df.columns:
                df[column] = default

        df["strategy"] = (
            df["strategy"]
            .fillna("UNCLASSIFIED")
            .astype(str)
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
            "closed_trades",
            "win_rate_pct",
            "profit_factor",
            "expectancy",
            "average_return_pct",
            "sharpe_ratio",
            "maximum_drawdown_pct",
            "recovery_factor",
            "strategy_score",
            "net_profit_loss",
        ]:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            ).fillna(
                0.0
            )

        return df

    # ---------------------------------------------------------
    # OPTIMIZER
    # ---------------------------------------------------------

    def build_optimizer_output(
        self,
        analytics_df: pd.DataFrame,
        monthly_df: pd.DataFrame,
        equity_df: pd.DataFrame,
        journal_df: pd.DataFrame,
        starting_capital: float,
    ) -> pd.DataFrame:
        if analytics_df.empty:
            return pd.DataFrame(
                columns=self.optimizer_columns()
            )

        rows = []

        for _, row in analytics_df.iterrows():
            strategy = clean_text(
                row.get(
                    "strategy",
                    "UNCLASSIFIED",
                )
            ).upper()

            closed_trades = int(
                safe_float(
                    row.get(
                        "closed_trades",
                        0,
                    )
                )
            )

            sample_confidence = min(
                100.0,
                closed_trades
                / self.strong_sample_trades
                * 100,
            )

            operating_status = (
                "LEARNING"
                if closed_trades
                < self.minimum_closed_trades
                else "ACTIVE"
            )

            recent_30 = self.calculate_recent_window(
                journal_df=journal_df,
                strategy=strategy,
                days=30,
            )
            recent_60 = self.calculate_recent_window(
                journal_df=journal_df,
                strategy=strategy,
                days=60,
            )
            recent_90 = self.calculate_recent_window(
                journal_df=journal_df,
                strategy=strategy,
                days=90,
            )

            base_score = safe_float(
                row.get(
                    "strategy_score",
                    0,
                )
            )

            quality_score = self.calculate_quality_score(
                row=row,
                sample_confidence=sample_confidence,
                recent_30=recent_30,
                recent_60=recent_60,
                recent_90=recent_90,
            )

            suggested_weight = self.calculate_suggested_weight(
                row=row,
                quality_score=quality_score,
                closed_trades=closed_trades,
            )

            action = self.resolve_action(
                row=row,
                quality_score=quality_score,
                closed_trades=closed_trades,
            )

            disable_allowed = (
                closed_trades
                >= self.disable_sample_trades
            )

            if (
                action == "DISABLE"
                and not disable_allowed
            ):
                action = "REDUCE"

            reason = self.build_reason(
                row=row,
                quality_score=quality_score,
                sample_confidence=sample_confidence,
                recent_30=recent_30,
                action=action,
            )

            rows.append({
                "strategy": strategy,
                "closed_trades": closed_trades,
                "sample_confidence_pct": round(
                    sample_confidence,
                    2,
                ),
                "operating_status": operating_status,
                "base_strategy_score": round(
                    base_score,
                    2,
                ),
                "optimizer_quality_score": round(
                    quality_score,
                    2,
                ),
                "win_rate_pct": round(
                    safe_float(
                        row.get(
                            "win_rate_pct",
                            0,
                        )
                    ),
                    4,
                ),
                "profit_factor": round(
                    safe_float(
                        row.get(
                            "profit_factor",
                            0,
                        )
                    ),
                    4,
                ),
                "expectancy": round(
                    safe_float(
                        row.get(
                            "expectancy",
                            0,
                        )
                    ),
                    4,
                ),
                "sharpe_ratio": round(
                    safe_float(
                        row.get(
                            "sharpe_ratio",
                            0,
                        )
                    ),
                    4,
                ),
                "maximum_drawdown_pct": round(
                    safe_float(
                        row.get(
                            "maximum_drawdown_pct",
                            0,
                        )
                    ),
                    4,
                ),
                "recovery_factor": round(
                    safe_float(
                        row.get(
                            "recovery_factor",
                            0,
                        )
                    ),
                    4,
                ),
                "net_profit_loss": round(
                    safe_float(
                        row.get(
                            "net_profit_loss",
                            0,
                        )
                    ),
                    2,
                ),
                "return_on_capital_pct": round(
                    (
                        safe_float(
                            row.get(
                                "net_profit_loss",
                                0,
                            )
                        )
                        / starting_capital
                        * 100
                    )
                    if starting_capital > 0
                    else 0.0,
                    4,
                ),
                "recent_30d_trades": recent_30[
                    "trades"
                ],
                "recent_30d_win_rate_pct": recent_30[
                    "win_rate_pct"
                ],
                "recent_30d_profit_loss": recent_30[
                    "profit_loss"
                ],
                "recent_60d_trades": recent_60[
                    "trades"
                ],
                "recent_60d_win_rate_pct": recent_60[
                    "win_rate_pct"
                ],
                "recent_60d_profit_loss": recent_60[
                    "profit_loss"
                ],
                "recent_90d_trades": recent_90[
                    "trades"
                ],
                "recent_90d_win_rate_pct": recent_90[
                    "win_rate_pct"
                ],
                "recent_90d_profit_loss": recent_90[
                    "profit_loss"
                ],
                "current_weight": 1.0,
                "suggested_weight": round(
                    suggested_weight,
                    4,
                ),
                "weight_change_pct": round(
                    (
                        suggested_weight
                        - 1.0
                    )
                    * 100,
                    2,
                ),
                "recommended_action": action,
                "automatic_disable_allowed": bool(
                    disable_allowed
                ),
                "optimizer_reason": reason,
                "generated_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
            })

        return pd.DataFrame(
            rows
        ).sort_values(
            [
                "optimizer_quality_score",
                "strategy",
            ],
            ascending=[
                False,
                True,
            ],
        ).reset_index(
            drop=True
        )

    def calculate_recent_window(
        self,
        journal_df: pd.DataFrame,
        strategy: str,
        days: int,
    ) -> dict:
        if (
            journal_df is None
            or journal_df.empty
            or "strategy" not in journal_df.columns
        ):
            return {
                "trades": 0,
                "win_rate_pct": 0.0,
                "profit_loss": 0.0,
            }

        working = journal_df.copy()

        working["strategy"] = (
            working["strategy"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.strip()
        )

        working = working[
            working["strategy"].eq(
                strategy
            )
        ].copy()

        if working.empty:
            return {
                "trades": 0,
                "win_rate_pct": 0.0,
                "profit_loss": 0.0,
            }

        date_series = pd.to_datetime(
            working.get(
                "exit_date",
                working.get(
                    "entry_date",
                    pd.Series(
                        index=working.index,
                        dtype=str,
                    ),
                ),
            ),
            errors="coerce",
        )

        cutoff = (
            pd.Timestamp.now().normalize()
            - pd.Timedelta(
                days=days
            )
        )

        working = working[
            date_series.ge(
                cutoff
            )
        ].copy()

        if working.empty:
            return {
                "trades": 0,
                "win_rate_pct": 0.0,
                "profit_loss": 0.0,
            }

        closed_mask = (
            working.get(
                "trade_status",
                pd.Series(
                    "",
                    index=working.index,
                ),
            )
            .fillna("")
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

        closed = working[
            closed_mask
        ]

        wins = int(
            (
                numeric_series(
                    closed,
                    "realized_profit_loss",
                )
                > 0
            ).sum()
        )

        closed_count = int(
            len(closed)
        )

        return {
            "trades": closed_count,
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
            "profit_loss": round(
                numeric_sum(
                    closed,
                    "realized_profit_loss",
                ),
                2,
            ),
        }

    def calculate_quality_score(
        self,
        row: pd.Series,
        sample_confidence: float,
        recent_30: dict,
        recent_60: dict,
        recent_90: dict,
    ) -> float:
        base_score = safe_float(
            row.get(
                "strategy_score",
                0,
            )
        )

        win_rate = safe_float(
            row.get(
                "win_rate_pct",
                0,
            )
        )

        profit_factor = safe_float(
            row.get(
                "profit_factor",
                0,
            )
        )

        expectancy = safe_float(
            row.get(
                "expectancy",
                0,
            )
        )

        drawdown = abs(
            safe_float(
                row.get(
                    "maximum_drawdown_pct",
                    0,
                )
            )
        )

        recent_score = (
            recent_30[
                "win_rate_pct"
            ] * 0.50
            + recent_60[
                "win_rate_pct"
            ] * 0.30
            + recent_90[
                "win_rate_pct"
            ] * 0.20
        )

        if (
            recent_30["trades"]
            + recent_60["trades"]
            + recent_90["trades"]
            == 0
        ):
            recent_score = win_rate

        score = (
            base_score * 0.30
            + win_rate * 0.20
            + min(
                profit_factor,
                3.0,
            )
            / 3.0
            * 100
            * 0.15
            + recent_score * 0.15
            + max(
                0.0,
                min(
                    100.0,
                    50
                    + expectancy / 20,
                ),
            ) * 0.10
            + max(
                0.0,
                100
                - drawdown * 8,
            ) * 0.10
        )

        confidence_multiplier = (
            0.50
            + sample_confidence
            / 100
            * 0.50
        )

        return max(
            0.0,
            min(
                100.0,
                score
                * confidence_multiplier,
            ),
        )

    def calculate_suggested_weight(
        self,
        row: pd.Series,
        quality_score: float,
        closed_trades: int,
    ) -> float:
        if closed_trades < self.minimum_closed_trades:
            return 1.0

        if quality_score >= 80:
            target = 1.15
        elif quality_score >= 65:
            target = 1.08
        elif quality_score >= 50:
            target = 1.00
        elif quality_score >= 35:
            target = 0.90
        else:
            target = 0.80

        target = max(
            1.0 - self.maximum_weight_change,
            min(
                1.0 + self.maximum_weight_change,
                target,
            ),
        )

        return max(
            self.minimum_weight,
            min(
                self.maximum_weight,
                target,
            ),
        )

    def resolve_action(
        self,
        row: pd.Series,
        quality_score: float,
        closed_trades: int,
    ) -> str:
        if closed_trades < self.minimum_closed_trades:
            return "LEARN"

        profit_factor = safe_float(
            row.get(
                "profit_factor",
                0,
            )
        )

        expectancy = safe_float(
            row.get(
                "expectancy",
                0,
            )
        )

        win_rate = safe_float(
            row.get(
                "win_rate_pct",
                0,
            )
        )

        drawdown = safe_float(
            row.get(
                "maximum_drawdown_pct",
                0,
            )
        )

        if (
            closed_trades
            >= self.disable_sample_trades
            and profit_factor < 0.75
            and expectancy < 0
            and win_rate < 35
        ):
            return "DISABLE"

        if (
            quality_score >= 75
            and profit_factor >= 1.40
            and expectancy > 0
            and drawdown >= -10
        ):
            return "INCREASE"

        if (
            quality_score < 45
            or profit_factor < 1.0
            or expectancy < 0
        ):
            return "REDUCE"

        return "MAINTAIN"

    def build_reason(
        self,
        row: pd.Series,
        quality_score: float,
        sample_confidence: float,
        recent_30: dict,
        action: str,
    ) -> str:
        parts = [
            (
                f"Sample confidence {sample_confidence:.1f}%"
            ),
            (
                f"Optimizer quality {quality_score:.1f}"
            ),
            (
                f"Win rate {safe_float(row.get('win_rate_pct', 0)):.1f}%"
            ),
            (
                f"Profit factor {safe_float(row.get('profit_factor', 0)):.2f}"
            ),
            (
                f"Expectancy {safe_float(row.get('expectancy', 0)):.2f}"
            ),
            (
                f"30-day closed trades {recent_30['trades']}"
            ),
            (
                f"Action {action}"
            ),
        ]

        return " | ".join(
            parts
        )

    # ---------------------------------------------------------
    # OUTPUTS
    # ---------------------------------------------------------

    def build_weights(
        self,
        optimizer_df: pd.DataFrame,
    ) -> pd.DataFrame:
        if optimizer_df.empty:
            return pd.DataFrame(
                columns=self.weight_columns()
            )

        result = optimizer_df[
            [
                "strategy",
                "operating_status",
                "closed_trades",
                "sample_confidence_pct",
                "optimizer_quality_score",
                "current_weight",
                "suggested_weight",
                "weight_change_pct",
                "recommended_action",
                "automatic_disable_allowed",
            ]
        ].copy()

        result["effective_weight"] = result.apply(
            lambda row: (
                0.0
                if (
                    str(
                        row.get(
                            "recommended_action",
                            "",
                        )
                    ).upper()
                    == "DISABLE"
                    and bool(
                        row.get(
                            "automatic_disable_allowed",
                            False,
                        )
                    )
                )
                else safe_float(
                    row.get(
                        "suggested_weight",
                        1.0,
                    ),
                    1.0,
                )
            ),
            axis=1,
        )

        result["apply_automatically"] = (
            result["operating_status"]
            .astype(str)
            .str.upper()
            .eq("ACTIVE")
            & result["recommended_action"]
            .astype(str)
            .str.upper()
            .isin(
                [
                    "INCREASE",
                    "MAINTAIN",
                    "REDUCE",
                    "DISABLE",
                ]
            )
        )

        return result[
            self.weight_columns()
        ]

    def build_actions(
        self,
        optimizer_df: pd.DataFrame,
    ) -> pd.DataFrame:
        if optimizer_df.empty:
            return pd.DataFrame(
                columns=self.action_columns()
            )

        result = optimizer_df[
            [
                "strategy",
                "operating_status",
                "closed_trades",
                "optimizer_quality_score",
                "recommended_action",
                "suggested_weight",
                "automatic_disable_allowed",
                "optimizer_reason",
            ]
        ].copy()

        result["priority"] = result[
            "recommended_action"
        ].map(
            {
                "DISABLE": 1,
                "REDUCE": 2,
                "INCREASE": 3,
                "MAINTAIN": 4,
                "LEARN": 5,
            }
        ).fillna(
            9
        ).astype(
            int
        )

        result["operational_instruction"] = result.apply(
            build_operational_instruction,
            axis=1,
        )

        return result[
            self.action_columns()
        ].sort_values(
            [
                "priority",
                "strategy",
            ]
        ).reset_index(
            drop=True
        )

    def build_summary(
        self,
        optimizer_df: pd.DataFrame,
        weights_df: pd.DataFrame,
    ) -> dict:
        if optimizer_df.empty:
            return {
                "engine_version": self.VERSION,
                "generated_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
                "strategies_processed": 0,
                "active_strategies": 0,
                "learning_strategies": 0,
                "increase_recommendations": 0,
                "reduce_recommendations": 0,
                "disable_recommendations": 0,
                "summary_status": "NO DATA",
            }

        actions = (
            optimizer_df["recommended_action"]
            .fillna("")
            .astype(str)
            .str.upper()
        )

        statuses = (
            optimizer_df["operating_status"]
            .fillna("")
            .astype(str)
            .str.upper()
        )

        return {
            "engine_version": self.VERSION,
            "generated_at": datetime.now().isoformat(
                timespec="seconds"
            ),
            "strategies_processed": int(
                len(optimizer_df)
            ),
            "active_strategies": int(
                statuses.eq(
                    "ACTIVE"
                ).sum()
            ),
            "learning_strategies": int(
                statuses.eq(
                    "LEARNING"
                ).sum()
            ),
            "increase_recommendations": int(
                actions.eq(
                    "INCREASE"
                ).sum()
            ),
            "maintain_recommendations": int(
                actions.eq(
                    "MAINTAIN"
                ).sum()
            ),
            "reduce_recommendations": int(
                actions.eq(
                    "REDUCE"
                ).sum()
            ),
            "disable_recommendations": int(
                actions.eq(
                    "DISABLE"
                ).sum()
            ),
            "automatic_weight_updates": int(
                weights_df.get(
                    "apply_automatically",
                    pd.Series(
                        dtype=bool,
                    ),
                )
                .fillna(False)
                .astype(bool)
                .sum()
            )
            if not weights_df.empty
            else 0,
            "summary_status": (
                "LEARNING"
                if statuses.eq(
                    "ACTIVE"
                ).sum()
                == 0
                else "ACTIVE"
            ),
        }

    def write_latest_weights_json(
        self,
        weights_df: pd.DataFrame,
        summary: dict,
    ) -> None:
        import json

        payload = {
            "engine_version": self.VERSION,
            "generated_at": datetime.now().isoformat(
                timespec="seconds"
            ),
            "summary": summary,
            "weights": {},
        }

        if not weights_df.empty:
            for _, row in weights_df.iterrows():
                strategy = clean_text(
                    row.get(
                        "strategy",
                        "",
                    )
                )

                if not strategy:
                    continue

                payload["weights"][
                    strategy
                ] = {
                    "effective_weight": round(
                        safe_float(
                            row.get(
                                "effective_weight",
                                1.0,
                            ),
                            1.0,
                        ),
                        4,
                    ),
                    "recommended_action": clean_text(
                        row.get(
                            "recommended_action",
                            "",
                        )
                    ),
                    "operating_status": clean_text(
                        row.get(
                            "operating_status",
                            "",
                        )
                    ),
                    "apply_automatically": bool(
                        row.get(
                            "apply_automatically",
                            False,
                        )
                    ),
                }

        self.latest_weights_path.write_text(
            json.dumps(
                payload,
                indent=2,
            ),
            encoding="utf-8",
        )

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

    def optimizer_columns(
        self,
    ) -> list[str]:
        return [
            "strategy",
            "closed_trades",
            "sample_confidence_pct",
            "operating_status",
            "base_strategy_score",
            "optimizer_quality_score",
            "win_rate_pct",
            "profit_factor",
            "expectancy",
            "sharpe_ratio",
            "maximum_drawdown_pct",
            "recovery_factor",
            "net_profit_loss",
            "return_on_capital_pct",
            "recent_30d_trades",
            "recent_30d_win_rate_pct",
            "recent_30d_profit_loss",
            "recent_60d_trades",
            "recent_60d_win_rate_pct",
            "recent_60d_profit_loss",
            "recent_90d_trades",
            "recent_90d_win_rate_pct",
            "recent_90d_profit_loss",
            "current_weight",
            "suggested_weight",
            "weight_change_pct",
            "recommended_action",
            "automatic_disable_allowed",
            "optimizer_reason",
            "generated_at",
        ]

    def weight_columns(
        self,
    ) -> list[str]:
        return [
            "strategy",
            "operating_status",
            "closed_trades",
            "sample_confidence_pct",
            "optimizer_quality_score",
            "current_weight",
            "suggested_weight",
            "effective_weight",
            "weight_change_pct",
            "recommended_action",
            "automatic_disable_allowed",
            "apply_automatically",
        ]

    def action_columns(
        self,
    ) -> list[str]:
        return [
            "priority",
            "strategy",
            "operating_status",
            "closed_trades",
            "optimizer_quality_score",
            "recommended_action",
            "suggested_weight",
            "automatic_disable_allowed",
            "operational_instruction",
            "optimizer_reason",
        ]


def run_strategy_optimizer_self_learning_v2(
    starting_capital: float = 50000.0,
    strategy_folder: str = "reports/strategy_analytics",
    journal_folder: str = "reports/trade_journal",
    output_folder: str = "database/strategy_learning",
    report_folder: str = "reports/strategy_optimizer",
    minimum_closed_trades: int = 10,
    strong_sample_trades: int = 25,
    disable_sample_trades: int = 30,
    maximum_weight_change: float = 0.15,
) -> dict:
    engine = StrategyOptimizerSelfLearningV2(
        strategy_folder=strategy_folder,
        journal_folder=journal_folder,
        output_folder=output_folder,
        report_folder=report_folder,
        minimum_closed_trades=minimum_closed_trades,
        strong_sample_trades=strong_sample_trades,
        disable_sample_trades=disable_sample_trades,
        maximum_weight_change=maximum_weight_change,
    )

    return engine.run(
        starting_capital=starting_capital
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


def build_operational_instruction(
    row: pd.Series,
) -> str:
    action = clean_text(
        row.get(
            "recommended_action",
            "",
        )
    ).upper()

    weight = safe_float(
        row.get(
            "suggested_weight",
            1.0,
        ),
        1.0,
    )

    if action == "INCREASE":
        return (
            f"Increase strategy allocation gradually to weight {weight:.2f}."
        )

    if action == "REDUCE":
        return (
            f"Reduce strategy allocation to weight {weight:.2f} and review rules."
        )

    if action == "DISABLE":
        return (
            "Disable new entries for this strategy until manual review."
        )

    if action == "LEARN":
        return (
            "Keep default weight 1.00 and collect more closed trades."
        )

    return (
        "Maintain current strategy allocation."
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


def default_for_column(
    column: str,
) -> Any:
    text_columns = {
        "strategy",
        "operating_status",
        "recommended_action",
        "optimizer_reason",
        "generated_at",
        "operational_instruction",
    }

    integer_columns = {
        "closed_trades",
        "recent_30d_trades",
        "recent_60d_trades",
        "recent_90d_trades",
        "priority",
    }

    boolean_columns = {
        "automatic_disable_allowed",
        "apply_automatically",
    }

    if column in text_columns:
        return ""

    if column in integer_columns:
        return 0

    if column in boolean_columns:
        return False

    return 0.0
