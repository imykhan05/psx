from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class PortfolioAnalyticsConfigV1:
    portfolio_folder: str = "database/portfolio"
    reports_folder: str = "reports/portfolio_analytics"
    latest_reports_folder: str = "reports/latest"
    open_positions_filename: str = "open_positions.csv"
    closed_positions_filename: str = "closed_positions.csv"
    equity_history_filename: str = "equity_history.csv"
    portfolio_analytics_filename: str = "portfolio_analytics.csv"
    sector_exposure_filename: str = "sector_exposure.csv"
    position_risk_filename: str = "position_risk_contribution.csv"
    rebalancing_filename: str = "rebalancing_suggestions.csv"
    summary_filename: str = "portfolio_analytics_summary.csv"


class PortfolioAnalyticsProV1:
    """
    Portfolio Analytics Pro V1

    Reads actual portfolio data and generates institutional analytics for:
    - Portfolio exposure
    - Cash utilization
    - Position concentration
    - Sector exposure
    - Risk contribution
    - Diversification score
    - Portfolio health
    - Rebalancing suggestions

    This module does not execute trades.
    """

    VERSION = "portfolio_analytics_pro_v1_0_institutional"

    def __init__(
        self,
        portfolio_folder: str = "database/portfolio",
        reports_folder: str = "reports/portfolio_analytics",
        latest_reports_folder: str = "reports/latest",
    ):
        self.config = PortfolioAnalyticsConfigV1(
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

        self.open_positions_path = (
            self.portfolio_folder
            / self.config.open_positions_filename
        )

        self.closed_positions_path = (
            self.portfolio_folder
            / self.config.closed_positions_filename
        )

        self.equity_history_path = (
            self.portfolio_folder
            / self.config.equity_history_filename
        )

        self.analytics_path = (
            self.reports_folder
            / self.config.portfolio_analytics_filename
        )

        self.sector_exposure_path = (
            self.reports_folder
            / self.config.sector_exposure_filename
        )

        self.position_risk_path = (
            self.reports_folder
            / self.config.position_risk_filename
        )

        self.rebalancing_path = (
            self.reports_folder
            / self.config.rebalancing_filename
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
    ) -> dict:
        starting_capital = positive_float(
            starting_capital,
            "starting_capital",
        )

        open_df = self.read_csv(
            self.open_positions_path
        )

        closed_df = self.read_csv(
            self.closed_positions_path
        )

        equity_df = self.read_csv(
            self.equity_history_path
        )

        positions_df = self.build_position_analytics(
            open_df=open_df,
            starting_capital=starting_capital,
        )

        sector_df = self.build_sector_exposure(
            positions_df=positions_df,
            starting_capital=starting_capital,
        )

        risk_df = self.build_position_risk_contribution(
            positions_df=positions_df,
        )

        summary = self.build_summary(
            positions_df=positions_df,
            sector_df=sector_df,
            risk_df=risk_df,
            closed_df=closed_df,
            equity_df=equity_df,
            starting_capital=starting_capital,
        )

        rebalancing_df = self.build_rebalancing_suggestions(
            positions_df=positions_df,
            sector_df=sector_df,
            summary=summary,
        )

        self.save_dataframe(
            positions_df,
            self.analytics_path,
            self.position_columns(),
        )

        self.save_dataframe(
            sector_df,
            self.sector_exposure_path,
            self.sector_columns(),
        )

        self.save_dataframe(
            risk_df,
            self.position_risk_path,
            self.risk_columns(),
        )

        self.save_dataframe(
            rebalancing_df,
            self.rebalancing_path,
            self.rebalancing_columns(),
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
            "open_positions": int(
                len(positions_df)
            ),
            "portfolio_exposure_pct": summary[
                "portfolio_exposure_pct"
            ],
            "cash_utilization_pct": summary[
                "cash_utilization_pct"
            ],
            "diversification_score": summary[
                "diversification_score"
            ],
            "portfolio_health_score": summary[
                "portfolio_health_score"
            ],
            "largest_position_pct": summary[
                "largest_position_pct"
            ],
            "largest_sector_pct": summary[
                "largest_sector_pct"
            ],
            "portfolio_analytics_csv": str(
                self.analytics_path
            ),
            "sector_exposure_csv": str(
                self.sector_exposure_path
            ),
            "position_risk_csv": str(
                self.position_risk_path
            ),
            "rebalancing_suggestions_csv": str(
                self.rebalancing_path
            ),
            "summary_csv": str(
                self.summary_path
            ),
            "reason": (
                "Portfolio analytics generated successfully"
            ),
        }

    # ---------------------------------------------------------
    # POSITION ANALYTICS
    # ---------------------------------------------------------

    def build_position_analytics(
        self,
        open_df: pd.DataFrame,
        starting_capital: float,
    ) -> pd.DataFrame:
        open_df = remove_duplicate_columns(
            open_df
        )

        if open_df.empty:
            return pd.DataFrame(
                columns=self.position_columns()
            )

        rows = []

        for _, row in open_df.iterrows():
            symbol = upper_text(
                row.get(
                    "symbol",
                    "",
                )
            )

            quantity = int(
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

            entry_price = first_positive_numeric(
                row,
                [
                    "average_cost",
                    "actual_entry_price",
                ],
            )

            current_price = first_positive_numeric(
                row,
                [
                    "current_price",
                    "close",
                    "last_price",
                    "actual_entry_price",
                ],
            )

            market_value = first_positive_numeric(
                row,
                [
                    "market_value",
                ],
            )

            if market_value <= 0:
                market_value = (
                    current_price
                    * quantity
                )

            cost_value = first_positive_numeric(
                row,
                [
                    "cost_value",
                    "investment",
                ],
            )

            if cost_value <= 0:
                cost_value = (
                    entry_price
                    * quantity
                )

            stop_loss = first_positive_numeric(
                row,
                [
                    "current_stop_loss",
                    "initial_stop_loss",
                    "stop_loss",
                ],
            )

            target_1 = first_positive_numeric(
                row,
                [
                    "target_1",
                ],
            )

            target_2 = first_positive_numeric(
                row,
                [
                    "target_2",
                ],
            )

            unrealized_profit_loss = safe_float(
                row.get(
                    "unrealized_profit_loss",
                    (
                        current_price
                        - entry_price
                    )
                    * quantity,
                )
            )

            unrealized_profit_loss_pct = (
                (
                    current_price
                    - entry_price
                )
                / entry_price
                * 100
                if entry_price > 0
                else 0.0
            )

            position_weight_pct = (
                market_value
                / starting_capital
                * 100
                if starting_capital > 0
                else 0.0
            )

            risk_per_share = max(
                entry_price
                - stop_loss,
                0,
            )

            risk_amount = (
                risk_per_share
                * quantity
            )

            risk_pct_of_capital = (
                risk_amount
                / starting_capital
                * 100
                if starting_capital > 0
                else 0.0
            )

            reward_to_target_1 = max(
                target_1
                - current_price,
                0,
            ) * quantity

            reward_to_target_2 = max(
                target_2
                - current_price,
                0,
            ) * quantity

            risk_reward_t1 = (
                reward_to_target_1
                / risk_amount
                if risk_amount > 0
                else 0.0
            )

            risk_reward_t2 = (
                reward_to_target_2
                / risk_amount
                if risk_amount > 0
                else 0.0
            )

            concentration_status = classify_concentration(
                position_weight_pct
            )

            risk_status = classify_position_risk(
                risk_pct_of_capital
            )

            rows.append({
                "symbol": symbol,
                "company": clean_text(
                    row.get(
                        "company",
                        "",
                    )
                ),
                "sector": clean_text(
                    row.get(
                        "sector",
                        "UNKNOWN",
                    )
                ).upper(),
                "position_status": clean_text(
                    row.get(
                        "position_status",
                        "",
                    )
                ),
                "entry_date": clean_text(
                    row.get(
                        "entry_date",
                        "",
                    )
                ),
                "quantity": quantity,
                "entry_price": round(
                    entry_price,
                    4,
                ),
                "current_price": round(
                    current_price,
                    4,
                ),
                "cost_value": round(
                    cost_value,
                    2,
                ),
                "market_value": round(
                    market_value,
                    2,
                ),
                "position_weight_pct": round(
                    position_weight_pct,
                    4,
                ),
                "unrealized_profit_loss": round(
                    unrealized_profit_loss,
                    2,
                ),
                "unrealized_profit_loss_pct": round(
                    unrealized_profit_loss_pct,
                    4,
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
                "risk_per_share": round(
                    risk_per_share,
                    4,
                ),
                "risk_amount": round(
                    risk_amount,
                    2,
                ),
                "risk_pct_of_capital": round(
                    risk_pct_of_capital,
                    4,
                ),
                "reward_to_target_1": round(
                    reward_to_target_1,
                    2,
                ),
                "reward_to_target_2": round(
                    reward_to_target_2,
                    2,
                ),
                "risk_reward_t1": round(
                    risk_reward_t1,
                    4,
                ),
                "risk_reward_t2": round(
                    risk_reward_t2,
                    4,
                ),
                "concentration_status": concentration_status,
                "risk_status": risk_status,
                "holding_days": int(
                    safe_float(
                        row.get(
                            "holding_days",
                            0,
                        )
                    )
                ),
            })

        result = pd.DataFrame(
            rows
        )

        if not result.empty:
            result = result.sort_values(
                "market_value",
                ascending=False,
            ).reset_index(
                drop=True
            )

        return result

    # ---------------------------------------------------------
    # SECTOR EXPOSURE
    # ---------------------------------------------------------

    def build_sector_exposure(
        self,
        positions_df: pd.DataFrame,
        starting_capital: float,
    ) -> pd.DataFrame:
        if positions_df.empty:
            return pd.DataFrame(
                columns=self.sector_columns()
            )

        rows = []

        for sector, group in positions_df.groupby(
            "sector",
            dropna=False,
        ):
            market_value = numeric_sum(
                group,
                "market_value",
            )

            cost_value = numeric_sum(
                group,
                "cost_value",
            )

            profit_loss = numeric_sum(
                group,
                "unrealized_profit_loss",
            )

            risk_amount = numeric_sum(
                group,
                "risk_amount",
            )

            exposure_pct = (
                market_value
                / starting_capital
                * 100
                if starting_capital > 0
                else 0.0
            )

            rows.append({
                "sector": clean_text(
                    sector
                ).upper(),
                "positions": int(
                    len(group)
                ),
                "cost_value": round(
                    cost_value,
                    2,
                ),
                "market_value": round(
                    market_value,
                    2,
                ),
                "sector_exposure_pct": round(
                    exposure_pct,
                    4,
                ),
                "unrealized_profit_loss": round(
                    profit_loss,
                    2,
                ),
                "risk_amount": round(
                    risk_amount,
                    2,
                ),
                "average_position_weight_pct": round(
                    numeric_series(
                        group,
                        "position_weight_pct",
                    ).mean(),
                    4,
                ),
                "sector_concentration_status": classify_sector_concentration(
                    exposure_pct
                ),
            })

        return pd.DataFrame(
            rows
        ).sort_values(
            "market_value",
            ascending=False,
        ).reset_index(
            drop=True
        )

    # ---------------------------------------------------------
    # RISK CONTRIBUTION
    # ---------------------------------------------------------

    def build_position_risk_contribution(
        self,
        positions_df: pd.DataFrame,
    ) -> pd.DataFrame:
        if positions_df.empty:
            return pd.DataFrame(
                columns=self.risk_columns()
            )

        total_risk = numeric_sum(
            positions_df,
            "risk_amount",
        )

        result = positions_df[
            [
                "symbol",
                "company",
                "sector",
                "market_value",
                "position_weight_pct",
                "risk_amount",
                "risk_pct_of_capital",
                "risk_reward_t1",
                "risk_reward_t2",
                "risk_status",
            ]
        ].copy()

        result["portfolio_risk_contribution_pct"] = (
            result["risk_amount"]
            / total_risk
            * 100
            if total_risk > 0
            else 0.0
        )

        result[
            "portfolio_risk_contribution_pct"
        ] = pd.to_numeric(
            result[
                "portfolio_risk_contribution_pct"
            ],
            errors="coerce",
        ).fillna(
            0.0
        ).round(
            4
        )

        result["risk_contribution_status"] = (
            result[
                "portfolio_risk_contribution_pct"
            ]
            .apply(
                classify_risk_contribution
            )
        )

        return result.sort_values(
            "risk_amount",
            ascending=False,
        ).reset_index(
            drop=True
        )

    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------

    def build_summary(
        self,
        positions_df: pd.DataFrame,
        sector_df: pd.DataFrame,
        risk_df: pd.DataFrame,
        closed_df: pd.DataFrame,
        equity_df: pd.DataFrame,
        starting_capital: float,
    ) -> dict:
        total_market_value = numeric_sum(
            positions_df,
            "market_value",
        )

        total_cost_value = numeric_sum(
            positions_df,
            "cost_value",
        )

        total_risk = numeric_sum(
            positions_df,
            "risk_amount",
        )

        unrealized_profit_loss = numeric_sum(
            positions_df,
            "unrealized_profit_loss",
        )

        realized_profit_loss = numeric_sum(
            closed_df,
            "realized_profit_loss",
        )

        cash_balance = (
            starting_capital
            - total_cost_value
            + realized_profit_loss
        )

        total_equity = (
            cash_balance
            + total_market_value
        )

        portfolio_exposure_pct = (
            total_market_value
            / starting_capital
            * 100
            if starting_capital > 0
            else 0.0
        )

        cash_utilization_pct = (
            total_cost_value
            / starting_capital
            * 100
            if starting_capital > 0
            else 0.0
        )

        largest_position_pct = (
            numeric_series(
                positions_df,
                "position_weight_pct",
            ).max()
            if not positions_df.empty
            else 0.0
        )

        largest_sector_pct = (
            numeric_series(
                sector_df,
                "sector_exposure_pct",
            ).max()
            if not sector_df.empty
            else 0.0
        )

        diversification_score = calculate_diversification_score(
            positions_df=positions_df,
            sector_df=sector_df,
        )

        concentration_score = max(
            0.0,
            100
            - largest_position_pct * 2.0
            - largest_sector_pct * 0.7,
        )

        risk_score = max(
            0.0,
            100
            - (
                total_risk
                / starting_capital
                * 100
            )
            * 20,
        ) if starting_capital > 0 else 0.0

        profitability_score = min(
            100.0,
            max(
                0.0,
                50
                + (
                    (
                        realized_profit_loss
                        + unrealized_profit_loss
                    )
                    / starting_capital
                    * 100
                )
                * 10,
            ),
        ) if starting_capital > 0 else 50.0

        portfolio_health_score = (
            diversification_score * 0.35
            + concentration_score * 0.25
            + risk_score * 0.25
            + profitability_score * 0.15
        )

        max_drawdown_pct = (
            numeric_series(
                equity_df,
                "drawdown_pct",
            ).min()
            if not equity_df.empty
            else 0.0
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
            "cash_balance": round(
                cash_balance,
                2,
            ),
            "total_cost_value": round(
                total_cost_value,
                2,
            ),
            "total_market_value": round(
                total_market_value,
                2,
            ),
            "total_equity": round(
                total_equity,
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
            "open_positions": int(
                len(positions_df)
            ),
            "closed_positions": int(
                len(closed_df)
            ),
            "portfolio_exposure_pct": round(
                portfolio_exposure_pct,
                4,
            ),
            "cash_utilization_pct": round(
                cash_utilization_pct,
                4,
            ),
            "cash_reserve_pct": round(
                max(
                    0.0,
                    100 - cash_utilization_pct,
                ),
                4,
            ),
            "largest_position_pct": round(
                largest_position_pct,
                4,
            ),
            "largest_sector_pct": round(
                largest_sector_pct,
                4,
            ),
            "total_risk_amount": round(
                total_risk,
                2,
            ),
            "portfolio_risk_pct": round(
                (
                    total_risk
                    / starting_capital
                    * 100
                )
                if starting_capital > 0
                else 0.0,
                4,
            ),
            "diversification_score": round(
                diversification_score,
                2,
            ),
            "concentration_score": round(
                concentration_score,
                2,
            ),
            "risk_score": round(
                risk_score,
                2,
            ),
            "profitability_score": round(
                profitability_score,
                2,
            ),
            "portfolio_health_score": round(
                portfolio_health_score,
                2,
            ),
            "maximum_drawdown_pct": round(
                max_drawdown_pct,
                4,
            ),
            "portfolio_status": classify_portfolio_health(
                portfolio_health_score
            ),
        }

    # ---------------------------------------------------------
    # REBALANCING
    # ---------------------------------------------------------

    def build_rebalancing_suggestions(
        self,
        positions_df: pd.DataFrame,
        sector_df: pd.DataFrame,
        summary: dict,
    ) -> pd.DataFrame:
        suggestions = []

        if positions_df.empty:
            suggestions.append({
                "priority": 1,
                "category": "PORTFOLIO",
                "symbol_or_sector": "PORTFOLIO",
                "issue": "No open positions",
                "suggested_action": (
                    "No rebalancing required until actual positions are open."
                ),
                "severity": "INFO",
            })

            return pd.DataFrame(
                suggestions
            )

        for _, row in positions_df.iterrows():
            symbol = upper_text(
                row.get(
                    "symbol",
                    "",
                )
            )

            weight = safe_float(
                row.get(
                    "position_weight_pct",
                    0,
                )
            )

            risk_pct = safe_float(
                row.get(
                    "risk_pct_of_capital",
                    0,
                )
            )

            risk_reward = safe_float(
                row.get(
                    "risk_reward_t1",
                    0,
                )
            )

            if weight > 25:
                suggestions.append({
                    "priority": 1,
                    "category": "POSITION CONCENTRATION",
                    "symbol_or_sector": symbol,
                    "issue": (
                        f"Position weight is {weight:.2f}%"
                    ),
                    "suggested_action": (
                        "Reduce position size or avoid adding more capital."
                    ),
                    "severity": "HIGH",
                })

            elif weight > 18:
                suggestions.append({
                    "priority": 2,
                    "category": "POSITION CONCENTRATION",
                    "symbol_or_sector": symbol,
                    "issue": (
                        f"Position weight is {weight:.2f}%"
                    ),
                    "suggested_action": (
                        "Monitor concentration and avoid further accumulation."
                    ),
                    "severity": "MEDIUM",
                })

            if risk_pct > 1.0:
                suggestions.append({
                    "priority": 1,
                    "category": "POSITION RISK",
                    "symbol_or_sector": symbol,
                    "issue": (
                        f"Risk is {risk_pct:.2f}% of capital"
                    ),
                    "suggested_action": (
                        "Reduce quantity or tighten stop loss."
                    ),
                    "severity": "HIGH",
                })

            if (
                risk_reward > 0
                and risk_reward < 1.5
            ):
                suggestions.append({
                    "priority": 2,
                    "category": "RISK REWARD",
                    "symbol_or_sector": symbol,
                    "issue": (
                        f"Risk/reward to Target 1 is {risk_reward:.2f}"
                    ),
                    "suggested_action": (
                        "Avoid adding more capital unless reward improves."
                    ),
                    "severity": "MEDIUM",
                })

        for _, row in sector_df.iterrows():
            sector = clean_text(
                row.get(
                    "sector",
                    "UNKNOWN",
                )
            )

            exposure = safe_float(
                row.get(
                    "sector_exposure_pct",
                    0,
                )
            )

            if exposure > 35:
                suggestions.append({
                    "priority": 1,
                    "category": "SECTOR CONCENTRATION",
                    "symbol_or_sector": sector,
                    "issue": (
                        f"Sector exposure is {exposure:.2f}%"
                    ),
                    "suggested_action": (
                        "Reduce sector concentration or diversify into another sector."
                    ),
                    "severity": "HIGH",
                })

            elif exposure > 25:
                suggestions.append({
                    "priority": 2,
                    "category": "SECTOR CONCENTRATION",
                    "symbol_or_sector": sector,
                    "issue": (
                        f"Sector exposure is {exposure:.2f}%"
                    ),
                    "suggested_action": (
                        "Avoid adding another position from this sector."
                    ),
                    "severity": "MEDIUM",
                })

        if safe_float(
            summary.get(
                "cash_reserve_pct",
                0,
            )
        ) > 70:
            suggestions.append({
                "priority": 3,
                "category": "CASH UTILIZATION",
                "symbol_or_sector": "PORTFOLIO",
                "issue": (
                    "Cash reserve is above 70%"
                ),
                "suggested_action": (
                    "Capital deployment is conservative; deploy only when high-quality signals appear."
                ),
                "severity": "INFO",
            })

        if not suggestions:
            suggestions.append({
                "priority": 5,
                "category": "PORTFOLIO",
                "symbol_or_sector": "PORTFOLIO",
                "issue": "No major portfolio imbalance detected",
                "suggested_action": (
                    "Maintain current allocation and continue monitoring."
                ),
                "severity": "LOW",
            })

        return pd.DataFrame(
            suggestions
        ).sort_values(
            [
                "priority",
                "severity",
            ],
            ascending=[
                True,
                True,
            ],
        ).reset_index(
            drop=True
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

    def position_columns(
        self,
    ) -> list[str]:
        return [
            "symbol",
            "company",
            "sector",
            "position_status",
            "entry_date",
            "quantity",
            "entry_price",
            "current_price",
            "cost_value",
            "market_value",
            "position_weight_pct",
            "unrealized_profit_loss",
            "unrealized_profit_loss_pct",
            "stop_loss",
            "target_1",
            "target_2",
            "risk_per_share",
            "risk_amount",
            "risk_pct_of_capital",
            "reward_to_target_1",
            "reward_to_target_2",
            "risk_reward_t1",
            "risk_reward_t2",
            "concentration_status",
            "risk_status",
            "holding_days",
        ]

    def sector_columns(
        self,
    ) -> list[str]:
        return [
            "sector",
            "positions",
            "cost_value",
            "market_value",
            "sector_exposure_pct",
            "unrealized_profit_loss",
            "risk_amount",
            "average_position_weight_pct",
            "sector_concentration_status",
        ]

    def risk_columns(
        self,
    ) -> list[str]:
        return [
            "symbol",
            "company",
            "sector",
            "market_value",
            "position_weight_pct",
            "risk_amount",
            "risk_pct_of_capital",
            "risk_reward_t1",
            "risk_reward_t2",
            "risk_status",
            "portfolio_risk_contribution_pct",
            "risk_contribution_status",
        ]

    def rebalancing_columns(
        self,
    ) -> list[str]:
        return [
            "priority",
            "category",
            "symbol_or_sector",
            "issue",
            "suggested_action",
            "severity",
        ]


def run_portfolio_analytics_pro_v1(
    starting_capital: float = 50000.0,
    portfolio_folder: str = "database/portfolio",
    reports_folder: str = "reports/portfolio_analytics",
    latest_reports_folder: str = "reports/latest",
) -> dict:
    engine = PortfolioAnalyticsProV1(
        portfolio_folder=portfolio_folder,
        reports_folder=reports_folder,
        latest_reports_folder=latest_reports_folder,
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
            0.0,
        )

        if number > 0:
            return number

    return 0.0


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


def classify_concentration(
    value: float,
) -> str:
    if value <= 10:
        return "LOW"

    if value <= 18:
        return "BALANCED"

    if value <= 25:
        return "HIGH"

    return "CRITICAL"


def classify_sector_concentration(
    value: float,
) -> str:
    if value <= 15:
        return "LOW"

    if value <= 25:
        return "BALANCED"

    if value <= 35:
        return "HIGH"

    return "CRITICAL"


def classify_position_risk(
    value: float,
) -> str:
    if value <= 0.5:
        return "LOW"

    if value <= 0.8:
        return "CONTROLLED"

    if value <= 1.2:
        return "HIGH"

    return "CRITICAL"


def classify_risk_contribution(
    value: float,
) -> str:
    if value <= 20:
        return "LOW"

    if value <= 35:
        return "BALANCED"

    if value <= 50:
        return "HIGH"

    return "DOMINANT"


def calculate_diversification_score(
    positions_df: pd.DataFrame,
    sector_df: pd.DataFrame,
) -> float:
    if positions_df.empty:
        return 0.0

    position_count = len(
        positions_df
    )

    sector_count = (
        positions_df["sector"]
        .fillna("UNKNOWN")
        .astype(str)
        .nunique()
        if "sector" in positions_df.columns
        else 0
    )

    weights = numeric_series(
        positions_df,
        "position_weight_pct",
    ) / 100

    concentration_index = float(
        (
            weights ** 2
        ).sum()
    )

    position_score = min(
        100.0,
        position_count
        / 5
        * 100,
    )

    sector_score = min(
        100.0,
        sector_count
        / 4
        * 100,
    )

    concentration_score = max(
        0.0,
        100
        - concentration_index
        * 100,
    )

    return (
        position_score * 0.35
        + sector_score * 0.35
        + concentration_score * 0.30
    )


def classify_portfolio_health(
    score: float,
) -> str:
    if score >= 85:
        return "EXCELLENT"

    if score >= 70:
        return "STRONG"

    if score >= 55:
        return "BALANCED"

    if score >= 40:
        return "WEAK"

    return "HIGH RISK"


def default_for_column(
    column: str,
) -> Any:
    text_columns = {
        "symbol",
        "company",
        "sector",
        "position_status",
        "entry_date",
        "concentration_status",
        "risk_status",
        "sector_concentration_status",
        "risk_contribution_status",
        "category",
        "symbol_or_sector",
        "issue",
        "suggested_action",
        "severity",
    }

    integer_columns = {
        "quantity",
        "holding_days",
        "positions",
        "priority",
    }

    if column in text_columns:
        return ""

    if column in integer_columns:
        return 0

    return 0.0
