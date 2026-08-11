from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class EquityCurveConfigV1:
    starting_capital: float = 50000.0
    portfolio_folder: str = "database/portfolio"
    reports_folder: str = "reports/performance"
    equity_history_filename: str = "equity_history.csv"
    daily_equity_filename: str = "daily_equity_curve.csv"
    monthly_returns_filename: str = "monthly_returns.csv"
    drawdown_history_filename: str = "drawdown_history.csv"
    open_positions_filename: str = "open_positions.csv"
    closed_positions_filename: str = "closed_positions.csv"


class EquityCurveEngineV1:
    """
    Equity Curve Engine V1

    Reads actual portfolio records and maintains a daily equity history.

    Formula
    -------
    Total Equity =
        Starting Capital
        + Realized P/L
        + Unrealized P/L

    Outputs
    -------
    database/portfolio/equity_history.csv
    reports/performance/daily_equity_curve.csv
    reports/performance/monthly_returns.csv
    reports/performance/drawdown_history.csv
    """

    VERSION = "equity_curve_engine_v1_0_institutional"

    def __init__(
        self,
        starting_capital: float = 50000.0,
        portfolio_folder: str = "database/portfolio",
        reports_folder: str = "reports/performance",
        equity_history_filename: str = "equity_history.csv",
        daily_equity_filename: str = "daily_equity_curve.csv",
        monthly_returns_filename: str = "monthly_returns.csv",
        drawdown_history_filename: str = "drawdown_history.csv",
        open_positions_filename: str = "open_positions.csv",
        closed_positions_filename: str = "closed_positions.csv",
    ):
        self.config = EquityCurveConfigV1(
            starting_capital=starting_capital,
            portfolio_folder=portfolio_folder,
            reports_folder=reports_folder,
            equity_history_filename=equity_history_filename,
            daily_equity_filename=daily_equity_filename,
            monthly_returns_filename=monthly_returns_filename,
            drawdown_history_filename=drawdown_history_filename,
            open_positions_filename=open_positions_filename,
            closed_positions_filename=closed_positions_filename,
        )

        self.starting_capital = positive_float(
            self.config.starting_capital,
            "starting_capital",
        )

        self.portfolio_folder = Path(
            self.config.portfolio_folder
        )

        self.reports_folder = Path(
            self.config.reports_folder
        )

        self.portfolio_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.reports_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.equity_history_path = (
            self.portfolio_folder
            / self.config.equity_history_filename
        )

        self.daily_equity_path = (
            self.reports_folder
            / self.config.daily_equity_filename
        )

        self.monthly_returns_path = (
            self.reports_folder
            / self.config.monthly_returns_filename
        )

        self.drawdown_history_path = (
            self.reports_folder
            / self.config.drawdown_history_filename
        )

        self.open_positions_path = (
            self.portfolio_folder
            / self.config.open_positions_filename
        )

        self.closed_positions_path = (
            self.portfolio_folder
            / self.config.closed_positions_filename
        )

    # ---------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------

    def run(
        self,
        snapshot_date: str | None = None,
    ) -> dict:
        resolved_date = normalize_date(
            snapshot_date
            or datetime.now().strftime(
                "%Y-%m-%d"
            )
        )

        open_df = self.read_csv(
            self.open_positions_path
        )

        closed_df = self.read_csv(
            self.closed_positions_path
        )

        snapshot = self.build_snapshot(
            snapshot_date=resolved_date,
            open_df=open_df,
            closed_df=closed_df,
        )

        history_df = self.load_equity_history()

        history_df = self.upsert_snapshot(
            history_df=history_df,
            snapshot=snapshot,
        )

        history_df = self.calculate_equity_metrics(
            history_df
        )

        monthly_df = self.build_monthly_returns(
            history_df
        )

        drawdown_df = self.build_drawdown_history(
            history_df
        )

        self.save_dataframe(
            history_df,
            self.equity_history_path,
            self.equity_history_columns(),
        )

        self.save_dataframe(
            history_df,
            self.daily_equity_path,
            self.equity_history_columns(),
        )

        self.save_dataframe(
            monthly_df,
            self.monthly_returns_path,
            self.monthly_return_columns(),
        )

        self.save_dataframe(
            drawdown_df,
            self.drawdown_history_path,
            self.drawdown_columns(),
        )

        latest_row = (
            history_df.iloc[-1].to_dict()
            if not history_df.empty
            else snapshot
        )

        return {
            "status": "success",
            "engine_version": self.VERSION,
            "snapshot_date": resolved_date,
            "starting_capital": round(
                self.starting_capital,
                2,
            ),
            "cash_balance": round(
                safe_float(
                    latest_row.get(
                        "cash_balance",
                        0,
                    )
                ),
                2,
            ),
            "open_market_value": round(
                safe_float(
                    latest_row.get(
                        "open_market_value",
                        0,
                    )
                ),
                2,
            ),
            "realized_profit_loss": round(
                safe_float(
                    latest_row.get(
                        "realized_profit_loss",
                        0,
                    )
                ),
                2,
            ),
            "unrealized_profit_loss": round(
                safe_float(
                    latest_row.get(
                        "unrealized_profit_loss",
                        0,
                    )
                ),
                2,
            ),
            "total_equity": round(
                safe_float(
                    latest_row.get(
                        "total_equity",
                        self.starting_capital,
                    )
                ),
                2,
            ),
            "daily_return_pct": round(
                safe_float(
                    latest_row.get(
                        "daily_return_pct",
                        0,
                    )
                ),
                4,
            ),
            "cumulative_return_pct": round(
                safe_float(
                    latest_row.get(
                        "cumulative_return_pct",
                        0,
                    )
                ),
                4,
            ),
            "drawdown_pct": round(
                safe_float(
                    latest_row.get(
                        "drawdown_pct",
                        0,
                    )
                ),
                4,
            ),
            "max_drawdown_pct": round(
                safe_float(
                    history_df["drawdown_pct"].min()
                    if (
                        not history_df.empty
                        and "drawdown_pct" in history_df.columns
                    )
                    else 0,
                ),
                4,
            ),
            "equity_history_csv": str(
                self.equity_history_path
            ),
            "daily_equity_curve_csv": str(
                self.daily_equity_path
            ),
            "monthly_returns_csv": str(
                self.monthly_returns_path
            ),
            "drawdown_history_csv": str(
                self.drawdown_history_path
            ),
            "reason": (
                "Equity curve and performance history updated successfully"
            ),
        }

    # ---------------------------------------------------------
    # SNAPSHOT
    # ---------------------------------------------------------

    def build_snapshot(
        self,
        snapshot_date: str,
        open_df: pd.DataFrame,
        closed_df: pd.DataFrame,
    ) -> dict:
        open_df = remove_duplicate_columns(
            open_df
        )

        closed_df = remove_duplicate_columns(
            closed_df
        )

        open_market_value = self.calculate_open_market_value(
            open_df
        )

        open_cost_value = self.calculate_open_cost_value(
            open_df
        )

        unrealized_profit_loss = self.calculate_unrealized_profit_loss(
            open_df
        )

        realized_profit_loss = self.calculate_realized_profit_loss(
            open_df=open_df,
            closed_df=closed_df,
        )

        invested_capital = open_cost_value

        cash_balance = (
            self.starting_capital
            - invested_capital
            + realized_profit_loss
        )

        total_equity = (
            cash_balance
            + open_market_value
        )

        gross_profit_loss = (
            realized_profit_loss
            + unrealized_profit_loss
        )

        active_positions = int(
            len(open_df)
        )

        closed_positions = int(
            len(closed_df)
        )

        winning_open_positions = int(
            (
                numeric_series(
                    open_df,
                    "unrealized_profit_loss",
                )
                > 0
            ).sum()
        )

        losing_open_positions = int(
            (
                numeric_series(
                    open_df,
                    "unrealized_profit_loss",
                )
                < 0
            ).sum()
        )

        return {
            "engine_version": self.VERSION,
            "date": snapshot_date,
            "starting_capital": round(
                self.starting_capital,
                2,
            ),
            "cash_balance": round(
                cash_balance,
                2,
            ),
            "invested_capital": round(
                invested_capital,
                2,
            ),
            "open_market_value": round(
                open_market_value,
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
            "gross_profit_loss": round(
                gross_profit_loss,
                2,
            ),
            "total_equity": round(
                total_equity,
                2,
            ),
            "active_positions": active_positions,
            "closed_positions": closed_positions,
            "winning_open_positions": winning_open_positions,
            "losing_open_positions": losing_open_positions,
            "daily_return_pct": 0.0,
            "cumulative_return_pct": 0.0,
            "peak_equity": round(
                total_equity,
                2,
            ),
            "drawdown_amount": 0.0,
            "drawdown_pct": 0.0,
            "last_updated_at": datetime.now().isoformat(
                timespec="seconds"
            ),
        }

    def calculate_open_market_value(
        self,
        open_df: pd.DataFrame,
    ) -> float:
        if open_df.empty:
            return 0.0

        if (
            "market_value" in open_df.columns
            and numeric_series(
                open_df,
                "market_value",
            ).sum() > 0
        ):
            return float(
                numeric_series(
                    open_df,
                    "market_value",
                ).sum()
            )

        current_price = first_numeric_series(
            open_df,
            [
                "current_price",
                "close",
                "last_price",
                "actual_entry_price",
                "average_cost",
            ],
        )

        quantity = first_numeric_series(
            open_df,
            [
                "remaining_quantity",
                "open_quantity",
                "actual_quantity",
                "original_quantity",
            ],
        )

        return float(
            (
                current_price
                * quantity
            ).sum()
        )

    def calculate_open_cost_value(
        self,
        open_df: pd.DataFrame,
    ) -> float:
        if open_df.empty:
            return 0.0

        if (
            "cost_value" in open_df.columns
            and numeric_series(
                open_df,
                "cost_value",
            ).sum() > 0
        ):
            return float(
                numeric_series(
                    open_df,
                    "cost_value",
                ).sum()
            )

        entry_price = first_numeric_series(
            open_df,
            [
                "average_cost",
                "actual_entry_price",
            ],
        )

        quantity = first_numeric_series(
            open_df,
            [
                "remaining_quantity",
                "open_quantity",
                "actual_quantity",
                "original_quantity",
            ],
        )

        return float(
            (
                entry_price
                * quantity
            ).sum()
        )

    def calculate_unrealized_profit_loss(
        self,
        open_df: pd.DataFrame,
    ) -> float:
        if open_df.empty:
            return 0.0

        if "unrealized_profit_loss" in open_df.columns:
            return float(
                numeric_series(
                    open_df,
                    "unrealized_profit_loss",
                ).sum()
            )

        return (
            self.calculate_open_market_value(
                open_df
            )
            - self.calculate_open_cost_value(
                open_df
            )
        )

    def calculate_realized_profit_loss(
        self,
        open_df: pd.DataFrame,
        closed_df: pd.DataFrame,
    ) -> float:
        open_realized = numeric_sum(
            open_df,
            "realized_profit_loss",
        )

        closed_realized = numeric_sum(
            closed_df,
            "realized_profit_loss",
        )

        return float(
            open_realized
            + closed_realized
        )

    # ---------------------------------------------------------
    # HISTORY
    # ---------------------------------------------------------

    def load_equity_history(
        self,
    ) -> pd.DataFrame:
        history_df = self.read_csv(
            self.equity_history_path
        )

        if history_df.empty:
            return pd.DataFrame(
                columns=self.equity_history_columns()
            )

        return self.normalize_history(
            history_df
        )

    def upsert_snapshot(
        self,
        history_df: pd.DataFrame,
        snapshot: dict,
    ) -> pd.DataFrame:
        history_df = self.normalize_history(
            history_df
        )

        snapshot_df = pd.DataFrame(
            [snapshot]
        )

        if history_df.empty:
            combined = snapshot_df
        else:
            combined = pd.concat(
                [
                    history_df,
                    snapshot_df,
                ],
                ignore_index=True,
                sort=False,
            )

        combined["date"] = (
            combined["date"]
            .fillna("")
            .astype(str)
        )

        combined = combined.drop_duplicates(
            subset=["date"],
            keep="last",
        )

        combined["_parsed_date"] = pd.to_datetime(
            combined["date"],
            errors="coerce",
        )

        combined = combined.sort_values(
            "_parsed_date",
            kind="stable",
        ).drop(
            columns=["_parsed_date"]
        ).reset_index(
            drop=True
        )

        return self.normalize_history(
            combined
        )

    def normalize_history(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        df = remove_duplicate_columns(
            df.copy()
        )

        for column in self.equity_history_columns():
            if column not in df.columns:
                df[column] = default_for_column(
                    column
                )

        text_columns = {
            "engine_version",
            "date",
            "last_updated_at",
        }

        integer_columns = {
            "active_positions",
            "closed_positions",
            "winning_open_positions",
            "losing_open_positions",
        }

        for column in text_columns:
            df[column] = (
                df[column]
                .fillna("")
                .astype(str)
            )

        for column in integer_columns:
            df[column] = (
                pd.to_numeric(
                    df[column],
                    errors="coerce",
                )
                .fillna(0)
                .astype(int)
            )

        numeric_columns = [
            column
            for column in self.equity_history_columns()
            if (
                column not in text_columns
                and column not in integer_columns
            )
        ]

        for column in numeric_columns:
            df[column] = (
                pd.to_numeric(
                    df[column],
                    errors="coerce",
                )
                .fillna(0.0)
                .astype(float)
            )

        return df[
            self.equity_history_columns()
        ]

    def calculate_equity_metrics(
        self,
        history_df: pd.DataFrame,
    ) -> pd.DataFrame:
        history_df = self.normalize_history(
            history_df
        )

        if history_df.empty:
            return history_df

        equity = numeric_series(
            history_df,
            "total_equity",
        )

        previous_equity = equity.shift(1)

        daily_return = (
            (
                equity
                - previous_equity
            )
            / previous_equity.replace(
                0,
                pd.NA,
            )
            * 100
        ).fillna(0.0)

        cumulative_return = (
            (
                equity
                - self.starting_capital
            )
            / self.starting_capital
            * 100
        )

        peak_equity = equity.cummax()

        drawdown_amount = (
            equity
            - peak_equity
        )

        drawdown_pct = (
            drawdown_amount
            / peak_equity.replace(
                0,
                pd.NA,
            )
            * 100
        ).fillna(0.0)

        history_df["daily_return_pct"] = (
            daily_return.round(4)
        )

        history_df["cumulative_return_pct"] = (
            cumulative_return.round(4)
        )

        history_df["peak_equity"] = (
            peak_equity.round(2)
        )

        history_df["drawdown_amount"] = (
            drawdown_amount.round(2)
        )

        history_df["drawdown_pct"] = (
            drawdown_pct.round(4)
        )

        return history_df

    # ---------------------------------------------------------
    # MONTHLY RETURNS
    # ---------------------------------------------------------

    def build_monthly_returns(
        self,
        history_df: pd.DataFrame,
    ) -> pd.DataFrame:
        if history_df.empty:
            return pd.DataFrame(
                columns=self.monthly_return_columns()
            )

        working = history_df.copy()

        working["_date"] = pd.to_datetime(
            working["date"],
            errors="coerce",
        )

        working = working[
            working["_date"].notna()
        ].copy()

        if working.empty:
            return pd.DataFrame(
                columns=self.monthly_return_columns()
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
            group = group.sort_values(
                "_date"
            )

            start_equity = safe_float(
                group.iloc[0].get(
                    "total_equity",
                    self.starting_capital,
                )
            )

            end_equity = safe_float(
                group.iloc[-1].get(
                    "total_equity",
                    self.starting_capital,
                )
            )

            monthly_return_pct = (
                (
                    end_equity
                    - start_equity
                )
                / start_equity
                * 100
                if start_equity > 0
                else 0.0
            )

            rows.append({
                "month": month,
                "start_date": group.iloc[0]["date"],
                "end_date": group.iloc[-1]["date"],
                "start_equity": round(
                    start_equity,
                    2,
                ),
                "end_equity": round(
                    end_equity,
                    2,
                ),
                "monthly_profit_loss": round(
                    end_equity
                    - start_equity,
                    2,
                ),
                "monthly_return_pct": round(
                    monthly_return_pct,
                    4,
                ),
                "best_daily_return_pct": round(
                    numeric_series(
                        group,
                        "daily_return_pct",
                    ).max(),
                    4,
                ),
                "worst_daily_return_pct": round(
                    numeric_series(
                        group,
                        "daily_return_pct",
                    ).min(),
                    4,
                ),
                "month_end_drawdown_pct": round(
                    safe_float(
                        group.iloc[-1].get(
                            "drawdown_pct",
                            0,
                        )
                    ),
                    4,
                ),
                "maximum_month_drawdown_pct": round(
                    numeric_series(
                        group,
                        "drawdown_pct",
                    ).min(),
                    4,
                ),
                "active_positions_end": int(
                    safe_float(
                        group.iloc[-1].get(
                            "active_positions",
                            0,
                        )
                    )
                ),
                "closed_positions_end": int(
                    safe_float(
                        group.iloc[-1].get(
                            "closed_positions",
                            0,
                        )
                    )
                ),
            })

        return pd.DataFrame(
            rows,
            columns=self.monthly_return_columns(),
        )

    # ---------------------------------------------------------
    # DRAWDOWN
    # ---------------------------------------------------------

    def build_drawdown_history(
        self,
        history_df: pd.DataFrame,
    ) -> pd.DataFrame:
        if history_df.empty:
            return pd.DataFrame(
                columns=self.drawdown_columns()
            )

        result = history_df[
            [
                "date",
                "total_equity",
                "peak_equity",
                "drawdown_amount",
                "drawdown_pct",
                "daily_return_pct",
                "cumulative_return_pct",
            ]
        ].copy()

        result["drawdown_status"] = (
            result["drawdown_pct"]
            .apply(
                drawdown_status
            )
        )

        result["new_equity_high"] = (
            numeric_series(
                result,
                "total_equity",
            )
            .round(2)
            .eq(
                numeric_series(
                    result,
                    "peak_equity",
                ).round(2)
            )
        )

        return result[
            self.drawdown_columns()
        ]

    # ---------------------------------------------------------
    # FILES
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

    def equity_history_columns(
        self,
    ) -> list[str]:
        return [
            "engine_version",
            "date",
            "starting_capital",
            "cash_balance",
            "invested_capital",
            "open_market_value",
            "realized_profit_loss",
            "unrealized_profit_loss",
            "gross_profit_loss",
            "total_equity",
            "active_positions",
            "closed_positions",
            "winning_open_positions",
            "losing_open_positions",
            "daily_return_pct",
            "cumulative_return_pct",
            "peak_equity",
            "drawdown_amount",
            "drawdown_pct",
            "last_updated_at",
        ]

    def monthly_return_columns(
        self,
    ) -> list[str]:
        return [
            "month",
            "start_date",
            "end_date",
            "start_equity",
            "end_equity",
            "monthly_profit_loss",
            "monthly_return_pct",
            "best_daily_return_pct",
            "worst_daily_return_pct",
            "month_end_drawdown_pct",
            "maximum_month_drawdown_pct",
            "active_positions_end",
            "closed_positions_end",
        ]

    def drawdown_columns(
        self,
    ) -> list[str]:
        return [
            "date",
            "total_equity",
            "peak_equity",
            "drawdown_amount",
            "drawdown_pct",
            "daily_return_pct",
            "cumulative_return_pct",
            "drawdown_status",
            "new_equity_high",
        ]


def run_equity_curve_engine_v1(
    starting_capital: float = 50000.0,
    snapshot_date: str | None = None,
    portfolio_folder: str = "database/portfolio",
    reports_folder: str = "reports/performance",
) -> dict:
    engine = EquityCurveEngineV1(
        starting_capital=starting_capital,
        portfolio_folder=portfolio_folder,
        reports_folder=reports_folder,
    )

    return engine.run(
        snapshot_date=snapshot_date
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


def first_numeric_series(
    df: pd.DataFrame,
    columns: list[str],
) -> pd.Series:
    if (
        df is None
        or df.empty
    ):
        return pd.Series(
            dtype=float
        )

    result = pd.Series(
        0.0,
        index=df.index,
        dtype=float,
    )

    unresolved = pd.Series(
        True,
        index=df.index,
    )

    for column in columns:
        if column not in df.columns:
            continue

        values = pd.to_numeric(
            df[column],
            errors="coerce",
        ).fillna(0.0)

        usable = (
            unresolved
            & values.gt(0)
        )

        result.loc[
            usable
        ] = values.loc[
            usable
        ]

        unresolved.loc[
            usable
        ] = False

    return result


def drawdown_status(
    value: Any,
) -> str:
    drawdown = safe_float(
        value,
        0.0,
    )

    if drawdown >= 0:
        return "NEW HIGH / NO DRAWDOWN"

    if drawdown >= -2:
        return "LOW DRAWDOWN"

    if drawdown >= -5:
        return "CONTROLLED DRAWDOWN"

    if drawdown >= -10:
        return "HIGH DRAWDOWN"

    return "CRITICAL DRAWDOWN"


def default_for_column(
    column: str,
) -> Any:
    text_columns = {
        "engine_version",
        "date",
        "last_updated_at",
        "month",
        "start_date",
        "end_date",
        "drawdown_status",
    }

    boolean_columns = {
        "new_equity_high",
    }

    integer_columns = {
        "active_positions",
        "closed_positions",
        "winning_open_positions",
        "losing_open_positions",
        "active_positions_end",
        "closed_positions_end",
    }

    if column in text_columns:
        return ""

    if column in boolean_columns:
        return False

    if column in integer_columns:
        return 0

    return 0.0
