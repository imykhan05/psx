from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from app.engines.backtesting.signal_tracker_v1 import (
    SIGNAL_HISTORY_FILE,
    SignalTrackerV1,
)


DEFAULT_LEARNING_FOLDER = Path(
    "database/backtesting/learning"
)

DEFAULT_REPORT_FOLDER = Path(
    "reports/backtests"
)


@dataclass
class LearningConfigV1:
    signal_history_file: Path = SIGNAL_HISTORY_FILE
    learning_folder: Path = DEFAULT_LEARNING_FOLDER
    report_folder: Path = DEFAULT_REPORT_FOLDER
    minimum_closed_signals: int = 10
    minimum_group_signals: int = 3
    maximum_adjustment: float = 10.0


class LearningEngineV1:
    """
    Learning Engine V1

    Uses closed backtest outcomes to learn which patterns perform better.

    Important safety design:
    - Does NOT directly overwrite live engine code or thresholds.
    - Produces adaptive recommendations and score adjustments.
    - Requires minimum sample sizes before trusting patterns.
    - Caps every suggested adjustment.
    - Stores explainable learning outputs in CSV/JSON-like tables.
    """

    VERSION = "learning_engine_v1"

    def __init__(
        self,
        signal_history_file: str | Path = SIGNAL_HISTORY_FILE,
        learning_folder: str | Path = DEFAULT_LEARNING_FOLDER,
        report_folder: str | Path = DEFAULT_REPORT_FOLDER,
        minimum_closed_signals: int = 10,
        minimum_group_signals: int = 3,
        maximum_adjustment: float = 10.0,
    ):
        self.config = LearningConfigV1(
            signal_history_file=Path(
                signal_history_file
            ),
            learning_folder=Path(
                learning_folder
            ),
            report_folder=Path(
                report_folder
            ),
            minimum_closed_signals=int(
                minimum_closed_signals
            ),
            minimum_group_signals=int(
                minimum_group_signals
            ),
            maximum_adjustment=float(
                maximum_adjustment
            ),
        )

        self.tracker = SignalTrackerV1(
            history_file=self.config.signal_history_file
        )

    def run(self) -> dict:
        history = self.tracker.load_history()

        if history.empty:
            return self.empty_result(
                "No signal history available"
            )

        data = self.prepare_history(
            history
        )

        closed = data[
            data["tracking_status"]
            == "CLOSED"
        ].copy()

        if len(closed) < self.config.minimum_closed_signals:
            return {
                "status": "success",
                "engine_version": self.VERSION,
                "reason": (
                    "Insufficient closed signals for learning"
                ),
                "closed_signals": int(
                    len(closed)
                ),
                "required_closed_signals": int(
                    self.config.minimum_closed_signals
                ),
                "learning_ready": False,
                "learning_folder": str(
                    self.config.learning_folder
                ),
            }

        baseline = self.calculate_baseline(
            closed
        )

        sector_learning = self.learn_group(
            closed,
            "sector",
            baseline,
        )

        market_learning = self.learn_group(
            closed,
            "market_mood",
            baseline,
        )

        decision_learning = self.learn_group(
            closed,
            "consensus_decision",
            baseline,
        )

        risk_learning = self.learn_group(
            closed,
            "risk_permission",
            baseline,
        )

        entry_learning = self.learn_group(
            closed,
            "entry_action",
            baseline,
        )

        score_bands = self.learn_score_bands(
            closed,
            baseline,
        )

        adjustments = self.build_adjustment_table(
            sector_learning=sector_learning,
            market_learning=market_learning,
            decision_learning=decision_learning,
            risk_learning=risk_learning,
            entry_learning=entry_learning,
            score_bands=score_bands,
        )

        paths = self.save_learning_outputs(
            baseline=baseline,
            sector_learning=sector_learning,
            market_learning=market_learning,
            decision_learning=decision_learning,
            risk_learning=risk_learning,
            entry_learning=entry_learning,
            score_bands=score_bands,
            adjustments=adjustments,
        )

        return {
            "status": "success",
            "engine_version": self.VERSION,
            "reason": "Learning analysis completed successfully",
            "learning_ready": True,
            "closed_signals": int(
                len(closed)
            ),
            "baseline": baseline,
            "recommended_adjustments": int(
                len(adjustments)
            ),
            "outputs": paths,
        }

    def prepare_history(
        self,
        history: pd.DataFrame,
    ) -> pd.DataFrame:
        data = history.copy()

        text_columns = [
            "tracking_status",
            "outcome_status",
            "sector",
            "market_mood",
            "decision",
            "consensus_decision",
            "risk_permission",
            "entry_action",
            "symbol",
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

        numeric_columns = [
            "return_pct",
            "profit_loss",
            "max_favorable_excursion_pct",
            "max_adverse_excursion_pct",
            "final_score",
            "consensus_score",
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
            "investment",
            "max_loss",
            "holding_days",
        ]

        for column in numeric_columns:
            if column not in data.columns:
                data[column] = 0.0

            data[column] = pd.to_numeric(
                data[column],
                errors="coerce",
            ).fillna(0.0)

        data["is_win"] = (
            data["profit_loss"] > 0
        )

        data["is_loss"] = (
            data["profit_loss"] < 0
        )

        data["is_target_win"] = data[
            "outcome_status"
        ].isin(
            [
                "TARGET_1 HIT",
                "TARGET_2 HIT",
            ]
        )

        data["is_stop_loss"] = (
            data["outcome_status"]
            == "STOP LOSS HIT"
        )

        return data

    def calculate_baseline(
        self,
        closed: pd.DataFrame,
    ) -> dict:
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
                3.0
                if gross_profit > 0
                else 0.0
            )
        )

        profitable_rate = (
            closed["is_win"].mean()
            * 100
            if not closed.empty
            else 0.0
        )

        target_rate = (
            closed["is_target_win"].mean()
            * 100
            if not closed.empty
            else 0.0
        )

        stop_rate = (
            closed["is_stop_loss"].mean()
            * 100
            if not closed.empty
            else 0.0
        )

        return {
            "closed_signals": int(
                len(closed)
            ),
            "profitable_rate_pct": round(
                profitable_rate,
                2,
            ),
            "target_hit_rate_pct": round(
                target_rate,
                2,
            ),
            "stop_loss_rate_pct": round(
                stop_rate,
                2,
            ),
            "average_return_pct": round(
                safe_mean(
                    closed["return_pct"]
                ),
                4,
            ),
            "average_profit_loss": round(
                safe_mean(
                    closed["profit_loss"]
                ),
                2,
            ),
            "profit_factor": round(
                profit_factor,
                4,
            ),
            "average_mfe_pct": round(
                safe_mean(
                    closed[
                        "max_favorable_excursion_pct"
                    ]
                ),
                4,
            ),
            "average_mae_pct": round(
                safe_mean(
                    closed[
                        "max_adverse_excursion_pct"
                    ]
                ),
                4,
            ),
        }

    def learn_group(
        self,
        closed: pd.DataFrame,
        group_column: str,
        baseline: dict,
    ) -> pd.DataFrame:
        if group_column not in closed.columns:
            return pd.DataFrame()

        rows = []

        for value, group in closed.groupby(
            group_column,
            dropna=False,
        ):
            count = len(group)

            if count < self.config.minimum_group_signals:
                continue

            gross_profit = safe_sum(
                group.loc[
                    group["profit_loss"] > 0,
                    "profit_loss",
                ]
            )

            gross_loss = abs(
                safe_sum(
                    group.loc[
                        group["profit_loss"] < 0,
                        "profit_loss",
                    ]
                )
            )

            profit_factor = (
                gross_profit / gross_loss
                if gross_loss > 0
                else (
                    3.0
                    if gross_profit > 0
                    else 0.0
                )
            )

            profitable_rate = (
                group["is_win"].mean()
                * 100
            )

            avg_return = safe_mean(
                group["return_pct"]
            )

            avg_profit = safe_mean(
                group["profit_loss"]
            )

            avg_mae = safe_mean(
                group[
                    "max_adverse_excursion_pct"
                ]
            )

            adjustment = self.calculate_adjustment(
                profitable_rate=profitable_rate,
                avg_return=avg_return,
                profit_factor=profit_factor,
                baseline=baseline,
                sample_size=count,
            )

            rows.append({
                group_column: (
                    str(value).strip()
                    if str(value).strip()
                    else "UNKNOWN"
                ),
                "signals": int(count),
                "profitable_rate_pct": round(
                    profitable_rate,
                    2,
                ),
                "average_return_pct": round(
                    avg_return,
                    4,
                ),
                "average_profit_loss": round(
                    avg_profit,
                    2,
                ),
                "profit_factor": round(
                    profit_factor,
                    4,
                ),
                "average_mae_pct": round(
                    avg_mae,
                    4,
                ),
                "recommended_score_adjustment": round(
                    adjustment,
                    2,
                ),
                "learning_label": self.learning_label(
                    adjustment
                ),
            })

        result = pd.DataFrame(
            rows
        )

        if not result.empty:
            result = result.sort_values(
                by=[
                    "recommended_score_adjustment",
                    "signals",
                ],
                ascending=[
                    False,
                    False,
                ],
                kind="stable",
            ).reset_index(
                drop=True
            )

        return result

    def learn_score_bands(
        self,
        closed: pd.DataFrame,
        baseline: dict,
    ) -> pd.DataFrame:
        data = closed.copy()

        data["final_score_band"] = pd.cut(
            data["final_score"],
            bins=[
                -1,
                60,
                70,
                80,
                90,
                1000,
            ],
            labels=[
                "0-60",
                "60-70",
                "70-80",
                "80-90",
                "90+",
            ],
        )

        data["buy_probability_band"] = pd.cut(
            data["buy_probability"],
            bins=[
                -1,
                50,
                60,
                70,
                80,
                90,
                1000,
            ],
            labels=[
                "0-50",
                "50-60",
                "60-70",
                "70-80",
                "80-90",
                "90+",
            ],
        )

        rows = []

        for band_type in [
            "final_score_band",
            "buy_probability_band",
        ]:
            for value, group in data.groupby(
                band_type,
                observed=True,
                dropna=False,
            ):
                count = len(group)

                if count < self.config.minimum_group_signals:
                    continue

                profitable_rate = (
                    group["is_win"].mean()
                    * 100
                )

                avg_return = safe_mean(
                    group["return_pct"]
                )

                gross_profit = safe_sum(
                    group.loc[
                        group["profit_loss"] > 0,
                        "profit_loss",
                    ]
                )

                gross_loss = abs(
                    safe_sum(
                        group.loc[
                            group["profit_loss"] < 0,
                            "profit_loss",
                        ]
                    )
                )

                profit_factor = (
                    gross_profit / gross_loss
                    if gross_loss > 0
                    else (
                        3.0
                        if gross_profit > 0
                        else 0.0
                    )
                )

                adjustment = self.calculate_adjustment(
                    profitable_rate=profitable_rate,
                    avg_return=avg_return,
                    profit_factor=profit_factor,
                    baseline=baseline,
                    sample_size=count,
                )

                rows.append({
                    "band_type": band_type,
                    "band_value": str(
                        value
                    ),
                    "signals": int(
                        count
                    ),
                    "profitable_rate_pct": round(
                        profitable_rate,
                        2,
                    ),
                    "average_return_pct": round(
                        avg_return,
                        4,
                    ),
                    "profit_factor": round(
                        profit_factor,
                        4,
                    ),
                    "recommended_score_adjustment": round(
                        adjustment,
                        2,
                    ),
                    "learning_label": self.learning_label(
                        adjustment
                    ),
                })

        return pd.DataFrame(
            rows
        )

    def calculate_adjustment(
        self,
        profitable_rate: float,
        avg_return: float,
        profit_factor: float,
        baseline: dict,
        sample_size: int,
    ) -> float:
        baseline_win = safe_float(
            baseline.get(
                "profitable_rate_pct",
                0,
            )
        )

        baseline_return = safe_float(
            baseline.get(
                "average_return_pct",
                0,
            )
        )

        baseline_pf = safe_float(
            baseline.get(
                "profit_factor",
                0,
            )
        )

        win_edge = (
            profitable_rate
            - baseline_win
        ) / 10

        return_edge = (
            avg_return
            - baseline_return
        ) * 1.5

        pf_edge = (
            profit_factor
            - baseline_pf
        ) * 2.0

        sample_confidence = min(
            sample_size / 20,
            1.0,
        )

        raw_adjustment = (
            win_edge
            + return_edge
            + pf_edge
        ) * sample_confidence

        return clamp(
            raw_adjustment,
            -self.config.maximum_adjustment,
            self.config.maximum_adjustment,
        )

    def learning_label(
        self,
        adjustment: float,
    ) -> str:
        if adjustment >= 6:
            return "STRONG POSITIVE EDGE"

        if adjustment >= 2:
            return "POSITIVE EDGE"

        if adjustment <= -6:
            return "STRONG NEGATIVE EDGE"

        if adjustment <= -2:
            return "NEGATIVE EDGE"

        return "NEUTRAL"

    def build_adjustment_table(
        self,
        sector_learning: pd.DataFrame,
        market_learning: pd.DataFrame,
        decision_learning: pd.DataFrame,
        risk_learning: pd.DataFrame,
        entry_learning: pd.DataFrame,
        score_bands: pd.DataFrame,
    ) -> pd.DataFrame:
        rows = []

        mapping = [
            (
                "sector",
                sector_learning,
                "sector",
            ),
            (
                "market_mood",
                market_learning,
                "market_mood",
            ),
            (
                "consensus_decision",
                decision_learning,
                "consensus_decision",
            ),
            (
                "risk_permission",
                risk_learning,
                "risk_permission",
            ),
            (
                "entry_action",
                entry_learning,
                "entry_action",
            ),
        ]

        for feature_type, frame, value_column in mapping:
            if frame is None or frame.empty:
                continue

            for _, row in frame.iterrows():
                rows.append({
                    "feature_type": feature_type,
                    "feature_value": row.get(
                        value_column,
                        "",
                    ),
                    "signals": int(
                        row.get(
                            "signals",
                            0,
                        )
                    ),
                    "recommended_score_adjustment": safe_float(
                        row.get(
                            "recommended_score_adjustment",
                            0,
                        )
                    ),
                    "learning_label": row.get(
                        "learning_label",
                        "",
                    ),
                    "source_engine": self.VERSION,
                })

        if score_bands is not None and not score_bands.empty:
            for _, row in score_bands.iterrows():
                rows.append({
                    "feature_type": row.get(
                        "band_type",
                        "",
                    ),
                    "feature_value": row.get(
                        "band_value",
                        "",
                    ),
                    "signals": int(
                        row.get(
                            "signals",
                            0,
                        )
                    ),
                    "recommended_score_adjustment": safe_float(
                        row.get(
                            "recommended_score_adjustment",
                            0,
                        )
                    ),
                    "learning_label": row.get(
                        "learning_label",
                        "",
                    ),
                    "source_engine": self.VERSION,
                })

        result = pd.DataFrame(
            rows
        )

        if not result.empty:
            result = result.sort_values(
                by=[
                    "recommended_score_adjustment",
                    "signals",
                ],
                ascending=[
                    False,
                    False,
                ],
                kind="stable",
            ).reset_index(
                drop=True
            )

        return result

    def save_learning_outputs(
        self,
        baseline: dict,
        sector_learning: pd.DataFrame,
        market_learning: pd.DataFrame,
        decision_learning: pd.DataFrame,
        risk_learning: pd.DataFrame,
        entry_learning: pd.DataFrame,
        score_bands: pd.DataFrame,
        adjustments: pd.DataFrame,
    ) -> dict:
        learning_folder = self.config.learning_folder
        report_folder = self.config.report_folder

        learning_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        report_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        paths = {
            "baseline_csv": learning_folder
            / "learning_baseline.csv",
            "sector_csv": learning_folder
            / "learning_by_sector.csv",
            "market_mood_csv": learning_folder
            / "learning_by_market_mood.csv",
            "decision_csv": learning_folder
            / "learning_by_consensus_decision.csv",
            "risk_permission_csv": learning_folder
            / "learning_by_risk_permission.csv",
            "entry_action_csv": learning_folder
            / "learning_by_entry_action.csv",
            "score_bands_csv": learning_folder
            / "learning_by_score_band.csv",
            "adjustments_csv": learning_folder
            / "recommended_adjustments.csv",
            "summary_md": report_folder
            / "learning_engine_summary.md",
        }

        pd.DataFrame(
            [baseline]
        ).to_csv(
            paths["baseline_csv"],
            index=False,
        )

        sector_learning.to_csv(
            paths["sector_csv"],
            index=False,
        )

        market_learning.to_csv(
            paths["market_mood_csv"],
            index=False,
        )

        decision_learning.to_csv(
            paths["decision_csv"],
            index=False,
        )

        risk_learning.to_csv(
            paths["risk_permission_csv"],
            index=False,
        )

        entry_learning.to_csv(
            paths["entry_action_csv"],
            index=False,
        )

        score_bands.to_csv(
            paths["score_bands_csv"],
            index=False,
        )

        adjustments.to_csv(
            paths["adjustments_csv"],
            index=False,
        )

        markdown = self.build_markdown_summary(
            baseline=baseline,
            adjustments=adjustments,
            sector_learning=sector_learning,
            market_learning=market_learning,
        )

        paths["summary_md"].write_text(
            markdown,
            encoding="utf-8",
        )

        return {
            key: str(value)
            for key, value in paths.items()
        }

    def build_markdown_summary(
        self,
        baseline: dict,
        adjustments: pd.DataFrame,
        sector_learning: pd.DataFrame,
        market_learning: pd.DataFrame,
    ) -> str:
        lines = [
            "# PSX Learning Engine Summary",
            "",
            f"- Engine: `{self.VERSION}`",
            f"- Learning Ready: **Yes**",
            "",
            "## Baseline Performance",
            "",
        ]

        for key, value in baseline.items():
            lines.append(
                f"- **{key.replace('_', ' ').title()}**: {value}"
            )

        lines.extend(
            [
                "",
                "## Strongest Positive Adjustments",
                "",
                dataframe_to_markdown(
                    adjustments.head(10)
                ),
                "",
                "## Weakest Adjustments",
                "",
                dataframe_to_markdown(
                    adjustments.tail(10).sort_values(
                        "recommended_score_adjustment"
                    )
                    if not adjustments.empty
                    else adjustments
                ),
                "",
                "## Sector Learning",
                "",
                dataframe_to_markdown(
                    sector_learning.head(15)
                ),
                "",
                "## Market Mood Learning",
                "",
                dataframe_to_markdown(
                    market_learning.head(10)
                ),
                "",
                "## Safety Note",
                "",
                (
                    "These adjustments are recommendations only. "
                    "They should be reviewed and validated before "
                    "being applied to live scoring thresholds."
                ),
                "",
            ]
        )

        return "\n".join(
            lines
        )

    def empty_result(
        self,
        reason: str,
    ) -> dict:
        return {
            "status": "success",
            "engine_version": self.VERSION,
            "reason": reason,
            "learning_ready": False,
            "closed_signals": 0,
            "required_closed_signals": int(
                self.config.minimum_closed_signals
            ),
            "learning_folder": str(
                self.config.learning_folder
            ),
        }


def run_learning_engine_v1(
    signal_history_file: str | Path = SIGNAL_HISTORY_FILE,
    learning_folder: str | Path = DEFAULT_LEARNING_FOLDER,
    report_folder: str | Path = DEFAULT_REPORT_FOLDER,
    minimum_closed_signals: int = 10,
    minimum_group_signals: int = 3,
    maximum_adjustment: float = 10.0,
) -> dict:
    engine = LearningEngineV1(
        signal_history_file=signal_history_file,
        learning_folder=learning_folder,
        report_folder=report_folder,
        minimum_closed_signals=minimum_closed_signals,
        minimum_group_signals=minimum_group_signals,
        maximum_adjustment=maximum_adjustment,
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

    lines = [
        "| "
        + " | ".join(
            columns
        )
        + " |",
        "| "
        + " | ".join(
            ["---"] * len(columns)
        )
        + " |",
    ]

    for _, row in df.iterrows():
        values = []

        for column in columns:
            value = str(
                row.get(
                    column,
                    "",
                )
            ).replace(
                "|",
                "/",
            )

            values.append(
                value
            )

        lines.append(
            "| "
            + " | ".join(
                values
            )
            + " |"
        )

    return "\n".join(
        lines
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