from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class SmartMoneyTrackerConfigV2:
    output_folder: str = "reports/smart_money"
    summary_filename: str = "smart_money_summary.csv"
    stocks_filename: str = "smart_money_stocks.csv"
    sectors_filename: str = "smart_money_by_sector.csv"
    accumulation_filename: str = "accumulation_candidates.csv"
    distribution_filename: str = "distribution_candidates.csv"
    traps_filename: str = "retail_trap_candidates.csv"
    json_filename: str = "smart_money_tracker.json"
    markdown_filename: str = "smart_money_tracker.md"
    html_filename: str = "smart_money_tracker.html"


class SmartMoneyTrackerV2:
    """
    Smart Money Tracker V2

    Detects institutional-style accumulation, distribution, breakout quality,
    hidden accumulation and retail-trap risk using only available market data.

    This is a heuristic decision-support engine. It does not claim access to
    investor-category or foreign-flow data unless those columns are present.
    """

    VERSION = "smart_money_tracker_v2_0_institutional_heuristic"

    def __init__(
        self,
        output_folder: str = "reports/smart_money",
    ):
        self.config = SmartMoneyTrackerConfigV2(
            output_folder=output_folder,
        )

        self.output_folder = Path(
            self.config.output_folder
        )
        self.output_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.summary_path = (
            self.output_folder
            / self.config.summary_filename
        )
        self.stocks_path = (
            self.output_folder
            / self.config.stocks_filename
        )
        self.sectors_path = (
            self.output_folder
            / self.config.sectors_filename
        )
        self.accumulation_path = (
            self.output_folder
            / self.config.accumulation_filename
        )
        self.distribution_path = (
            self.output_folder
            / self.config.distribution_filename
        )
        self.traps_path = (
            self.output_folder
            / self.config.traps_filename
        )
        self.json_path = (
            self.output_folder
            / self.config.json_filename
        )
        self.markdown_path = (
            self.output_folder
            / self.config.markdown_filename
        )
        self.html_path = (
            self.output_folder
            / self.config.html_filename
        )

    def run(
        self,
        market_df: pd.DataFrame,
        market_breadth_summary: dict | None = None,
        trading_date: str | None = None,
    ) -> dict:
        df = clean_df(
            market_df
        )
        market_breadth_summary = (
            market_breadth_summary
            or {}
        )

        resolved_date = normalize_date(
            trading_date
        )

        if df.empty:
            stocks_df = pd.DataFrame(
                columns=self.stock_columns()
            )
            sector_df = pd.DataFrame(
                columns=self.sector_columns()
            )
            summary = self.empty_summary(
                trading_date=resolved_date
            )
        else:
            df = self.normalize_market_df(
                df
            )

            stocks_df = self.build_stock_scores(
                df=df,
                market_breadth_summary=market_breadth_summary,
            )

            sector_df = self.build_sector_scores(
                stocks_df
            )

            summary = self.build_summary(
                stocks_df=stocks_df,
                sector_df=sector_df,
                market_breadth_summary=market_breadth_summary,
                trading_date=resolved_date,
            )

        accumulation_df = stocks_df[
            stocks_df.get(
                "smart_money_label",
                pd.Series(
                    dtype=str,
                ),
            )
            .astype(str)
            .str.upper()
            .isin(
                [
                    "INSTITUTIONAL BUYING",
                    "OPERATOR ACCUMULATION",
                    "HIDDEN ACCUMULATION",
                ]
            )
        ].copy() if not stocks_df.empty else pd.DataFrame(
            columns=self.stock_columns()
        )

        distribution_df = stocks_df[
            stocks_df.get(
                "smart_money_label",
                pd.Series(
                    dtype=str,
                ),
            )
            .astype(str)
            .str.upper()
            .isin(
                [
                    "DISTRIBUTION",
                    "INSTITUTIONAL SELLING",
                ]
            )
        ].copy() if not stocks_df.empty else pd.DataFrame(
            columns=self.stock_columns()
        )

        traps_df = stocks_df[
            stocks_df.get(
                "retail_trap_risk",
                pd.Series(
                    dtype=str,
                ),
            )
            .astype(str)
            .str.upper()
            .isin(
                [
                    "HIGH",
                    "CRITICAL",
                ]
            )
        ].copy() if not stocks_df.empty else pd.DataFrame(
            columns=self.stock_columns()
        )

        self.save_dataframe(
            stocks_df,
            self.stocks_path,
            self.stock_columns(),
        )

        self.save_dataframe(
            sector_df,
            self.sectors_path,
            self.sector_columns(),
        )

        self.save_dataframe(
            accumulation_df,
            self.accumulation_path,
            self.stock_columns(),
        )

        self.save_dataframe(
            distribution_df,
            self.distribution_path,
            self.stock_columns(),
        )

        self.save_dataframe(
            traps_df,
            self.traps_path,
            self.stock_columns(),
        )

        pd.DataFrame(
            [summary]
        ).to_csv(
            self.summary_path,
            index=False,
            encoding="utf-8-sig",
        )

        payload = {
            "engine_version": self.VERSION,
            "generated_at": datetime.now().isoformat(
                timespec="seconds"
            ),
            "summary": summary,
            "top_accumulation": accumulation_df.head(
                25
            ).to_dict(
                orient="records"
            ),
            "top_distribution": distribution_df.head(
                25
            ).to_dict(
                orient="records"
            ),
            "sector_scores": sector_df.head(
                25
            ).to_dict(
                orient="records"
            ),
        }

        self.json_path.write_text(
            json.dumps(
                payload,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        self.markdown_path.write_text(
            self.build_markdown(
                summary=summary,
                accumulation_df=accumulation_df,
                distribution_df=distribution_df,
                sector_df=sector_df,
            ),
            encoding="utf-8",
        )

        self.html_path.write_text(
            self.build_html(
                summary=summary,
                accumulation_df=accumulation_df,
                distribution_df=distribution_df,
                traps_df=traps_df,
                sector_df=sector_df,
            ),
            encoding="utf-8",
        )

        return {
            "status": "success",
            "engine_version": self.VERSION,
            "trading_date": resolved_date,
            "institutional_buying_count": summary[
                "institutional_buying_count"
            ],
            "operator_accumulation_count": summary[
                "operator_accumulation_count"
            ],
            "hidden_accumulation_count": summary[
                "hidden_accumulation_count"
            ],
            "distribution_count": summary[
                "distribution_count"
            ],
            "retail_trap_count": summary[
                "retail_trap_count"
            ],
            "market_smart_money_score": summary[
                "market_smart_money_score"
            ],
            "market_smart_money_label": summary[
                "market_smart_money_label"
            ],
            "summary_csv": str(
                self.summary_path
            ),
            "stocks_csv": str(
                self.stocks_path
            ),
            "sectors_csv": str(
                self.sectors_path
            ),
            "accumulation_csv": str(
                self.accumulation_path
            ),
            "distribution_csv": str(
                self.distribution_path
            ),
            "retail_traps_csv": str(
                self.traps_path
            ),
            "json": str(
                self.json_path
            ),
            "markdown": str(
                self.markdown_path
            ),
            "html": str(
                self.html_path
            ),
            "reason": (
                "Smart money tracking completed successfully"
            ),
        }

    # ---------------------------------------------------------
    # NORMALIZATION
    # ---------------------------------------------------------

    def normalize_market_df(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        result = df.copy()

        defaults = {
            "symbol": "",
            "company": "",
            "sector": "UNKNOWN",
        }

        for column, default in defaults.items():
            if column not in result.columns:
                result[column] = default

        for column in [
            "symbol",
            "company",
            "sector",
        ]:
            result[column] = (
                result[column]
                .fillna(defaults[column])
                .astype(str)
                .str.strip()
            )

        result["symbol"] = (
            result["symbol"]
            .str.upper()
        )
        result["sector"] = (
            result["sector"]
            .str.upper()
            .replace(
                {
                    "": "UNKNOWN",
                    "NAN": "UNKNOWN",
                }
            )
        )

        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
            "prev_close",
            "volume",
            "avg_volume_20",
            "volume_sma20",
            "volume_ratio",
            "change_pct",
            "rsi",
            "rsi_14",
            "ema20",
            "ema50",
            "macd",
            "macd_signal",
            "trend_score_v5",
            "trend_score_v4",
            "buy_probability",
            "smart_money_score",
            "trade_validation_score",
            "confidence",
            "confidence_v3",
            "institutional_v5_score",
            "institutional_score",
            "final_score",
            "high_52w",
            "low_52w",
            "delivery_pct",
            "foreign_buy_value",
            "foreign_sell_value",
            "foreign_net_value",
            "upper_cap",
            "lower_cap",
        ]

        for column in numeric_columns:
            if column in result.columns:
                result[column] = pd.to_numeric(
                    result[column],
                    errors="coerce",
                ).fillna(
                    0.0
                )

        if "change_pct" not in result.columns:
            close = number_series(
                result,
                "close",
            )
            prev_close = number_series(
                result,
                "prev_close",
            )

            result["change_pct"] = (
                (
                    close
                    - prev_close
                )
                / prev_close.replace(
                    0,
                    pd.NA,
                )
                * 100
            ).fillna(
                0.0
            )

        return result

    # ---------------------------------------------------------
    # STOCK SCORING
    # ---------------------------------------------------------

    def build_stock_scores(
        self,
        df: pd.DataFrame,
        market_breadth_summary: dict,
    ) -> pd.DataFrame:
        close = number_series(
            df,
            "close",
        )
        open_price = number_series(
            df,
            "open",
        )
        high = number_series(
            df,
            "high",
        )
        low = number_series(
            df,
            "low",
        )
        volume = number_series(
            df,
            "volume",
        )
        change_pct = number_series(
            df,
            "change_pct",
        )

        avg_volume = first_available_series(
            df,
            [
                "avg_volume_20",
                "volume_sma20",
                "average_volume_20",
            ],
        )

        # Force plain float64 before combining calculated ratios.
        # Pandas nullable integer/extension dtypes reject float assignment.
        volume_ratio = pd.to_numeric(
            first_available_series(
                df,
                [
                    "volume_ratio",
                ],
            ),
            errors="coerce",
        ).fillna(
            0.0
        ).astype(
            "float64"
        )

        calculated_ratio = pd.to_numeric(
            volume
            / avg_volume.replace(
                0,
                float("nan"),
            ),
            errors="coerce",
        ).fillna(
            0.0
        ).astype(
            "float64"
        )

        volume_ratio = volume_ratio.mask(
            volume_ratio.le(0),
            calculated_ratio,
        ).astype(
            "float64"
        )

        intraday_position = (
            (
                close
                - low
            )
            / (
                high
                - low
            ).replace(
                0,
                pd.NA,
            )
            * 100
        ).fillna(
            50.0
        )

        body_strength = (
            (
                close
                - open_price
            )
            / (
                high
                - low
            ).replace(
                0,
                pd.NA,
            )
            * 100
        ).fillna(
            0.0
        )

        ema20 = first_available_series(
            df,
            [
                "ema20",
                "ema_20",
            ],
        )
        ema50 = first_available_series(
            df,
            [
                "ema50",
                "ema_50",
            ],
        )
        rsi = first_available_series(
            df,
            [
                "rsi_14",
                "rsi",
            ],
        )
        macd = first_available_series(
            df,
            [
                "macd",
            ],
        )
        macd_signal = first_available_series(
            df,
            [
                "macd_signal",
                "signal_line",
            ],
        )
        trend_score = first_available_series(
            df,
            [
                "trend_score_v5",
                "trend_score_v4",
                "trend_score",
            ],
        )
        buy_probability = first_available_series(
            df,
            [
                "buy_probability",
            ],
        )
        existing_smart_money = first_available_series(
            df,
            [
                "smart_money_score",
            ],
        )
        institutional_score = first_available_series(
            df,
            [
                "institutional_v5_score",
                "institutional_score",
                "final_score",
            ],
        )

        delivery_pct = first_available_series(
            df,
            [
                "delivery_pct",
            ],
        )

        foreign_net = first_available_series(
            df,
            [
                "foreign_net_value",
            ],
        )

        if (
            "foreign_net_value"
            not in df.columns
            and "foreign_buy_value" in df.columns
            and "foreign_sell_value" in df.columns
        ):
            foreign_net = (
                number_series(
                    df,
                    "foreign_buy_value",
                )
                - number_series(
                    df,
                    "foreign_sell_value",
                )
            )

        liquidity_score = normalize_to_100(
            volume
        )

        volume_score = (
            volume_ratio.clip(
                lower=0,
                upper=5,
            )
            / 5
            * 100
        )

        price_strength_score = (
            intraday_position.clip(
                lower=0,
                upper=100,
            )
            * 0.55
            + normalize_signed_to_100(
                change_pct,
                lower=-10,
                upper=10,
            )
            * 0.45
        )

        trend_alignment_score = pd.Series(
            0.0,
            index=df.index,
            dtype=float,
        )

        trend_alignment_score += (
            close.gt(
                ema20
            )
            & ema20.gt(
                0
            )
        ).astype(
            float
        ) * 25

        trend_alignment_score += (
            ema20.gt(
                ema50
            )
            & ema50.gt(
                0
            )
        ).astype(
            float
        ) * 25

        trend_alignment_score += (
            macd.gt(
                macd_signal
            )
            & (
                macd.ne(0)
                | macd_signal.ne(0)
            )
        ).astype(
            float
        ) * 20

        trend_alignment_score += (
            rsi.between(
                50,
                72,
                inclusive="both",
            )
        ).astype(
            float
        ) * 15

        trend_alignment_score += (
            trend_score.clip(
                lower=0,
                upper=100,
            )
            * 0.15
        )

        delivery_score = (
            delivery_pct.clip(
                lower=0,
                upper=100,
            )
        )

        foreign_score = normalize_signed_to_100(
            foreign_net,
            lower=-1,
            upper=1,
            use_distribution=True,
        )

        ai_score = weighted_series(
            [
                (
                    buy_probability.clip(
                        lower=0,
                        upper=100,
                    ),
                    0.35,
                ),
                (
                    existing_smart_money.clip(
                        lower=0,
                        upper=100,
                    ),
                    0.25,
                ),
                (
                    institutional_score.clip(
                        lower=0,
                        upper=100,
                    ),
                    0.25,
                ),
                (
                    trend_score.clip(
                        lower=0,
                        upper=100,
                    ),
                    0.15,
                ),
            ]
        )

        accumulation_score = weighted_series(
            [
                (
                    volume_score,
                    0.22,
                ),
                (
                    price_strength_score,
                    0.20,
                ),
                (
                    trend_alignment_score,
                    0.18,
                ),
                (
                    ai_score,
                    0.18,
                ),
                (
                    liquidity_score,
                    0.08,
                ),
                (
                    delivery_score,
                    0.08,
                ),
                (
                    foreign_score,
                    0.06,
                ),
            ]
        )

        distribution_pressure = weighted_series(
            [
                (
                    normalize_signed_to_100(
                        -change_pct,
                        lower=-10,
                        upper=10,
                    ),
                    0.30,
                ),
                (
                    (
                        100
                        - intraday_position.clip(
                            0,
                            100,
                        )
                    ),
                    0.25,
                ),
                (
                    volume_score,
                    0.20,
                ),
                (
                    (
                        100
                        - trend_alignment_score.clip(
                            0,
                            100,
                        )
                    ),
                    0.15,
                ),
                (
                    (
                        100
                        - ai_score.clip(
                            0,
                            100,
                        )
                    ),
                    0.10,
                ),
            ]
        )

        hidden_accumulation_score = weighted_series(
            [
                (
                    volume_score,
                    0.35,
                ),
                (
                    (
                        100
                        - normalize_signed_to_100(
                            change_pct.abs(),
                            lower=0,
                            upper=5,
                        )
                    ),
                    0.25,
                ),
                (
                    intraday_position.clip(
                        0,
                        100,
                    ),
                    0.15,
                ),
                (
                    trend_alignment_score,
                    0.15,
                ),
                (
                    ai_score,
                    0.10,
                ),
            ]
        )

        breakout_quality_score = weighted_series(
            [
                (
                    intraday_position.clip(
                        0,
                        100,
                    ),
                    0.25,
                ),
                (
                    body_strength.clip(
                        lower=-100,
                        upper=100,
                    ).add(
                        100
                    ).div(
                        2
                    ),
                    0.15,
                ),
                (
                    volume_score,
                    0.25,
                ),
                (
                    trend_alignment_score,
                    0.20,
                ),
                (
                    ai_score,
                    0.15,
                ),
            ]
        )

        fake_breakout_risk = weighted_series(
            [
                (
                    (
                        100
                        - intraday_position.clip(
                            0,
                            100,
                        )
                    ),
                    0.30,
                ),
                (
                    (
                        100
                        - body_strength.clip(
                            lower=-100,
                            upper=100,
                        ).add(
                            100
                        ).div(
                            2
                        )
                    ),
                    0.20,
                ),
                (
                    volume_score,
                    0.20,
                ),
                (
                    (
                        100
                        - trend_alignment_score.clip(
                            0,
                            100,
                        )
                    ),
                    0.15,
                ),
                (
                    (
                        100
                        - ai_score.clip(
                            0,
                            100,
                        )
                    ),
                    0.15,
                ),
            ]
        )

        retail_trap_score = weighted_series(
            [
                (
                    fake_breakout_risk,
                    0.45,
                ),
                (
                    distribution_pressure,
                    0.35,
                ),
                (
                    normalize_signed_to_100(
                        change_pct,
                        lower=-10,
                        upper=10,
                    ),
                    0.20,
                ),
            ]
        )

        final_smart_money_score = weighted_series(
            [
                (
                    accumulation_score,
                    0.50,
                ),
                (
                    hidden_accumulation_score,
                    0.20,
                ),
                (
                    breakout_quality_score,
                    0.15,
                ),
                (
                    (
                        100
                        - distribution_pressure
                    ),
                    0.10,
                ),
                (
                    (
                        100
                        - retail_trap_score
                    ),
                    0.05,
                ),
            ]
        ).clip(
            lower=0,
            upper=100,
        )

        breadth_score = safe_float(
            market_breadth_summary.get(
                "breadth_score",
                50.0,
            )
        )

        breadth_multiplier = max(
            0.85,
            min(
                1.15,
                0.85
                + breadth_score
                / 100
                * 0.30,
            ),
        )

        final_smart_money_score = (
            final_smart_money_score
            * breadth_multiplier
        ).clip(
            lower=0,
            upper=100,
        )

        result = pd.DataFrame({
            "symbol": df["symbol"],
            "company": df["company"],
            "sector": df["sector"],
            "close": close,
            "change_pct": change_pct,
            "volume": volume,
            "volume_ratio": volume_ratio,
            "intraday_position_pct": intraday_position,
            "body_strength_pct": body_strength,
            "liquidity_score": liquidity_score,
            "volume_score": volume_score,
            "price_strength_score": price_strength_score,
            "trend_alignment_score": trend_alignment_score,
            "ai_confirmation_score": ai_score,
            "delivery_score": delivery_score,
            "foreign_flow_score": foreign_score,
            "accumulation_score": accumulation_score,
            "hidden_accumulation_score": hidden_accumulation_score,
            "distribution_pressure": distribution_pressure,
            "breakout_quality_score": breakout_quality_score,
            "fake_breakout_risk": fake_breakout_risk,
            "retail_trap_score": retail_trap_score,
            "smart_money_score_v2": final_smart_money_score,
        })

        result["smart_money_label"] = result.apply(
            classify_smart_money_row,
            axis=1,
        )

        result["retail_trap_risk"] = result[
            "retail_trap_score"
        ].apply(
            classify_risk
        )

        result["breakout_quality"] = result[
            "breakout_quality_score"
        ].apply(
            classify_quality
        )

        result["recommended_action"] = result.apply(
            build_action,
            axis=1,
        )

        result["smart_money_reason"] = result.apply(
            build_reason,
            axis=1,
        )

        result = result.sort_values(
            [
                "smart_money_score_v2",
                "volume",
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
            self.stock_columns()
        ]

    # ---------------------------------------------------------
    # SECTOR SCORES
    # ---------------------------------------------------------

    def build_sector_scores(
        self,
        stocks_df: pd.DataFrame,
    ) -> pd.DataFrame:
        if stocks_df.empty:
            return pd.DataFrame(
                columns=self.sector_columns()
            )

        rows = []

        for sector, group in stocks_df.groupby(
            "sector",
            dropna=False,
        ):
            labels = (
                group["smart_money_label"]
                .fillna("")
                .astype(str)
                .str.upper()
            )

            rows.append({
                "sector": upper(
                    sector
                )
                or "UNKNOWN",
                "stocks": int(
                    len(group)
                ),
                "average_smart_money_score": round(
                    number_series(
                        group,
                        "smart_money_score_v2",
                    ).mean(),
                    2,
                ),
                "average_accumulation_score": round(
                    number_series(
                        group,
                        "accumulation_score",
                    ).mean(),
                    2,
                ),
                "average_distribution_pressure": round(
                    number_series(
                        group,
                        "distribution_pressure",
                    ).mean(),
                    2,
                ),
                "institutional_buying_count": int(
                    labels.eq(
                        "INSTITUTIONAL BUYING"
                    ).sum()
                ),
                "operator_accumulation_count": int(
                    labels.eq(
                        "OPERATOR ACCUMULATION"
                    ).sum()
                ),
                "hidden_accumulation_count": int(
                    labels.eq(
                        "HIDDEN ACCUMULATION"
                    ).sum()
                ),
                "distribution_count": int(
                    labels.isin(
                        [
                            "DISTRIBUTION",
                            "INSTITUTIONAL SELLING",
                        ]
                    ).sum()
                ),
                "retail_trap_count": int(
                    group["retail_trap_risk"]
                    .fillna("")
                    .astype(str)
                    .str.upper()
                    .isin(
                        [
                            "HIGH",
                            "CRITICAL",
                        ]
                    )
                    .sum()
                ),
            })

        result = pd.DataFrame(
            rows
        )

        result["sector_smart_money_label"] = result.apply(
            classify_sector,
            axis=1,
        )

        return result.sort_values(
            [
                "average_smart_money_score",
                "stocks",
            ],
            ascending=[
                False,
                False,
            ],
        ).reset_index(
            drop=True
        )[
            self.sector_columns()
        ]

    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------

    def build_summary(
        self,
        stocks_df: pd.DataFrame,
        sector_df: pd.DataFrame,
        market_breadth_summary: dict,
        trading_date: str,
    ) -> dict:
        labels = (
            stocks_df["smart_money_label"]
            .fillna("")
            .astype(str)
            .str.upper()
        )

        institutional_buying_count = int(
            labels.eq(
                "INSTITUTIONAL BUYING"
            ).sum()
        )
        operator_accumulation_count = int(
            labels.eq(
                "OPERATOR ACCUMULATION"
            ).sum()
        )
        hidden_accumulation_count = int(
            labels.eq(
                "HIDDEN ACCUMULATION"
            ).sum()
        )
        distribution_count = int(
            labels.isin(
                [
                    "DISTRIBUTION",
                    "INSTITUTIONAL SELLING",
                ]
            ).sum()
        )
        retail_trap_count = int(
            stocks_df["retail_trap_risk"]
            .fillna("")
            .astype(str)
            .str.upper()
            .isin(
                [
                    "HIGH",
                    "CRITICAL",
                ]
            )
            .sum()
        )

        market_score = round(
            number_series(
                stocks_df,
                "smart_money_score_v2",
            ).mean(),
            2,
        )

        top_score = round(
            number_series(
                stocks_df,
                "smart_money_score_v2",
            ).head(
                20
            ).mean(),
            2,
        )

        accumulation_share = (
            (
                institutional_buying_count
                + operator_accumulation_count
                + hidden_accumulation_count
            )
            / len(
                stocks_df
            )
            * 100
            if len(
                stocks_df
            ) > 0
            else 0.0
        )

        distribution_share = (
            distribution_count
            / len(
                stocks_df
            )
            * 100
            if len(
                stocks_df
            ) > 0
            else 0.0
        )

        return {
            "engine_version": self.VERSION,
            "generated_at": datetime.now().isoformat(
                timespec="seconds"
            ),
            "trading_date": trading_date,
            "total_symbols": int(
                len(stocks_df)
            ),
            "institutional_buying_count": institutional_buying_count,
            "operator_accumulation_count": operator_accumulation_count,
            "hidden_accumulation_count": hidden_accumulation_count,
            "distribution_count": distribution_count,
            "retail_trap_count": retail_trap_count,
            "accumulation_share_pct": round(
                accumulation_share,
                4,
            ),
            "distribution_share_pct": round(
                distribution_share,
                4,
            ),
            "market_smart_money_score": market_score,
            "top_20_smart_money_score": top_score,
            "market_smart_money_label": classify_market_smart_money(
                market_score,
                accumulation_share,
                distribution_share,
            ),
            "breadth_score_used": round(
                safe_float(
                    market_breadth_summary.get(
                        "breadth_score",
                        0,
                    )
                ),
                2,
            ),
            "strongest_sector": (
                text(
                    sector_df.iloc[0].get(
                        "sector",
                        "",
                    )
                )
                if not sector_df.empty
                else ""
            ),
            "strongest_sector_score": (
                round(
                    safe_float(
                        sector_df.iloc[0].get(
                            "average_smart_money_score",
                            0,
                        )
                    ),
                    2,
                )
                if not sector_df.empty
                else 0.0
            ),
            "top_symbol": (
                text(
                    stocks_df.iloc[0].get(
                        "symbol",
                        "",
                    )
                )
                if not stocks_df.empty
                else ""
            ),
            "top_symbol_score": (
                round(
                    safe_float(
                        stocks_df.iloc[0].get(
                            "smart_money_score_v2",
                            0,
                        )
                    ),
                    2,
                )
                if not stocks_df.empty
                else 0.0
            ),
        }

    def empty_summary(
        self,
        trading_date: str,
    ) -> dict:
        return {
            "engine_version": self.VERSION,
            "generated_at": datetime.now().isoformat(
                timespec="seconds"
            ),
            "trading_date": trading_date,
            "total_symbols": 0,
            "institutional_buying_count": 0,
            "operator_accumulation_count": 0,
            "hidden_accumulation_count": 0,
            "distribution_count": 0,
            "retail_trap_count": 0,
            "accumulation_share_pct": 0.0,
            "distribution_share_pct": 0.0,
            "market_smart_money_score": 0.0,
            "top_20_smart_money_score": 0.0,
            "market_smart_money_label": "NO DATA",
            "breadth_score_used": 0.0,
            "strongest_sector": "",
            "strongest_sector_score": 0.0,
            "top_symbol": "",
            "top_symbol_score": 0.0,
        }

    # ---------------------------------------------------------
    # RENDERERS
    # ---------------------------------------------------------

    def build_markdown(
        self,
        summary: dict,
        accumulation_df: pd.DataFrame,
        distribution_df: pd.DataFrame,
        sector_df: pd.DataFrame,
    ) -> str:
        lines = [
            "# Smart Money Tracker V2",
            "",
            f"- Trading Date: **{summary['trading_date']}**",
            f"- Market Smart Money Score: **{summary['market_smart_money_score']:.2f}/100**",
            f"- Market Label: **{summary['market_smart_money_label']}**",
            f"- Institutional Buying: **{summary['institutional_buying_count']}**",
            f"- Operator Accumulation: **{summary['operator_accumulation_count']}**",
            f"- Hidden Accumulation: **{summary['hidden_accumulation_count']}**",
            f"- Distribution: **{summary['distribution_count']}**",
            f"- Retail Traps: **{summary['retail_trap_count']}**",
            "",
            "## Top Accumulation Candidates",
            "",
        ]

        if accumulation_df.empty:
            lines.append(
                "_No strong accumulation candidates found._"
            )
        else:
            for _, row in accumulation_df.head(
                15
            ).iterrows():
                lines.append(
                    (
                        f"- **{text(row.get('symbol'))}** — "
                        f"{safe_float(row.get('smart_money_score_v2')):.1f}/100 "
                        f"({text(row.get('smart_money_label'))})"
                    )
                )

        lines.extend(
            [
                "",
                "## Distribution Candidates",
                "",
            ]
        )

        if distribution_df.empty:
            lines.append(
                "_No major distribution candidates found._"
            )
        else:
            for _, row in distribution_df.head(
                10
            ).iterrows():
                lines.append(
                    (
                        f"- **{text(row.get('symbol'))}** — "
                        f"Distribution pressure "
                        f"{safe_float(row.get('distribution_pressure')):.1f}"
                    )
                )

        lines.extend(
            [
                "",
                "## Strongest Sectors",
                "",
            ]
        )

        for _, row in sector_df.head(
            10
        ).iterrows():
            lines.append(
                (
                    f"- **{text(row.get('sector'))}** — "
                    f"{safe_float(row.get('average_smart_money_score')):.1f}/100"
                )
            )

        return "\n".join(
            lines
        )

    def build_html(
        self,
        summary: dict,
        accumulation_df: pd.DataFrame,
        distribution_df: pd.DataFrame,
        traps_df: pd.DataFrame,
        sector_df: pd.DataFrame,
    ) -> str:
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Smart Money Tracker V2</title>
<style>
body{{margin:0;background:#06101c;color:#edf5fc;font-family:Arial,sans-serif}}
.container{{width:min(1450px,96%);margin:24px auto}}
.grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}}
.card{{background:#0d1c2d;border:1px solid #21405d;border-radius:14px;padding:16px}}
.label{{font-size:11px;color:#91a8bd;text-transform:uppercase}}
.value{{font-size:23px;font-weight:700;margin-top:7px}}
.full{{grid-column:span 5}}
.half{{grid-column:span 2}}
.wide{{grid-column:span 3}}
table{{width:100%;border-collapse:collapse;font-size:11px}}
th,td{{padding:8px;border-bottom:1px solid #21405d;text-align:left}}
th{{color:#91a8bd}}
@media(max-width:900px){{.grid{{grid-template-columns:1fr 1fr}}.full,.half,.wide{{grid-column:span 2}}}}
</style>
</head>
<body>
<div class="container">
<h1>PSX Smart Money Tracker V2</h1>
<p>Trading Date: {escape(summary['trading_date'])}</p>
<div class="grid">
{metric_card("Market Score", f"{summary['market_smart_money_score']:.1f}")}
{metric_card("Institutional Buying", summary['institutional_buying_count'])}
{metric_card("Operator Accumulation", summary['operator_accumulation_count'])}
{metric_card("Distribution", summary['distribution_count'])}
{metric_card("Retail Traps", summary['retail_trap_count'])}
<div class="card full">
<div class="label">Market Smart Money Label</div>
<div class="value">{escape(summary['market_smart_money_label'])}</div>
</div>
<div class="card wide">
<h2>Top Accumulation</h2>
{table_html(accumulation_df, ["rank","symbol","sector","smart_money_score_v2","smart_money_label","volume_ratio","change_pct","breakout_quality","recommended_action"], 25)}
</div>
<div class="card half">
<h2>Sector Strength</h2>
{table_html(sector_df, ["sector","stocks","average_smart_money_score","institutional_buying_count","distribution_count","sector_smart_money_label"], 20)}
</div>
<div class="card wide">
<h2>Distribution Candidates</h2>
{table_html(distribution_df, ["rank","symbol","sector","distribution_pressure","smart_money_label","recommended_action"], 20)}
</div>
<div class="card half">
<h2>Retail Trap Candidates</h2>
{table_html(traps_df, ["rank","symbol","retail_trap_score","retail_trap_risk","fake_breakout_risk","recommended_action"], 20)}
</div>
</div>
</div>
</body>
</html>"""

    # ---------------------------------------------------------
    # FILE HELPERS
    # ---------------------------------------------------------

    def save_dataframe(
        self,
        df: pd.DataFrame,
        path: Path,
        columns: list[str],
    ) -> None:
        df = clean_df(
            df
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
                df[column] = default_value(
                    column
                )

        df[columns].to_csv(
            path,
            index=False,
            encoding="utf-8-sig",
        )

    def stock_columns(
        self,
    ) -> list[str]:
        return [
            "rank",
            "symbol",
            "company",
            "sector",
            "close",
            "change_pct",
            "volume",
            "volume_ratio",
            "intraday_position_pct",
            "body_strength_pct",
            "liquidity_score",
            "volume_score",
            "price_strength_score",
            "trend_alignment_score",
            "ai_confirmation_score",
            "delivery_score",
            "foreign_flow_score",
            "accumulation_score",
            "hidden_accumulation_score",
            "distribution_pressure",
            "breakout_quality_score",
            "breakout_quality",
            "fake_breakout_risk",
            "retail_trap_score",
            "retail_trap_risk",
            "smart_money_score_v2",
            "smart_money_label",
            "recommended_action",
            "smart_money_reason",
        ]

    def sector_columns(
        self,
    ) -> list[str]:
        return [
            "sector",
            "stocks",
            "average_smart_money_score",
            "average_accumulation_score",
            "average_distribution_pressure",
            "institutional_buying_count",
            "operator_accumulation_count",
            "hidden_accumulation_count",
            "distribution_count",
            "retail_trap_count",
            "sector_smart_money_label",
        ]


def run_smart_money_tracker_v2(
    market_df: pd.DataFrame,
    market_breadth_summary: dict | None = None,
    trading_date: str | None = None,
    output_folder: str = "reports/smart_money",
) -> dict:
    engine = SmartMoneyTrackerV2(
        output_folder=output_folder
    )

    return engine.run(
        market_df=market_df,
        market_breadth_summary=market_breadth_summary,
        trading_date=trading_date,
    )


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def clean_df(
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


def number_series(
    df: pd.DataFrame,
    column: str,
) -> pd.Series:
    if (
        df.empty
        or column not in df.columns
    ):
        return pd.Series(
            0.0,
            index=df.index,
            dtype=float,
        )

    return pd.to_numeric(
        df[column],
        errors="coerce",
    ).fillna(
        0.0
    )


def first_available_series(
    df: pd.DataFrame,
    columns: list[str],
) -> pd.Series:
    for column in columns:
        if column in df.columns:
            return number_series(
                df,
                column,
            )

    return pd.Series(
        0.0,
        index=df.index,
        dtype=float,
    )


def normalize_to_100(
    series: pd.Series,
) -> pd.Series:
    series = pd.to_numeric(
        series,
        errors="coerce",
    ).fillna(
        0.0
    )

    if series.empty:
        return series

    low = float(
        series.quantile(
            0.05
        )
    )
    high = float(
        series.quantile(
            0.95
        )
    )

    if high <= low:
        return pd.Series(
            50.0,
            index=series.index,
            dtype=float,
        )

    return (
        (
            series
            - low
        )
        / (
            high
            - low
        )
        * 100
    ).clip(
        lower=0,
        upper=100,
    )


def normalize_signed_to_100(
    series: pd.Series,
    lower: float,
    upper: float,
    use_distribution: bool = False,
) -> pd.Series:
    series = pd.to_numeric(
        series,
        errors="coerce",
    ).fillna(
        0.0
    )

    if use_distribution:
        if series.abs().sum() == 0:
            return pd.Series(
                50.0,
                index=series.index,
                dtype=float,
            )

        lower = float(
            series.quantile(
                0.05
            )
        )
        upper = float(
            series.quantile(
                0.95
            )
        )

    if upper <= lower:
        return pd.Series(
            50.0,
            index=series.index,
            dtype=float,
        )

    return (
        (
            series
            - lower
        )
        / (
            upper
            - lower
        )
        * 100
    ).clip(
        lower=0,
        upper=100,
    )


def weighted_series(
    items: list[tuple[pd.Series, float]],
) -> pd.Series:
    if not items:
        return pd.Series(
            dtype=float
        )

    index = items[0][0].index
    result = pd.Series(
        0.0,
        index=index,
        dtype=float,
    )
    total_weight = 0.0

    for series, weight in items:
        weight = safe_float(
            weight
        )

        if weight <= 0:
            continue

        result = (
            result
            + pd.to_numeric(
                series,
                errors="coerce",
            ).fillna(
                0.0
            )
            * weight
        )
        total_weight += weight

    if total_weight <= 0:
        return result

    return result / total_weight


def classify_smart_money_row(
    row: pd.Series,
) -> str:
    score = safe_float(
        row.get(
            "smart_money_score_v2",
            0,
        )
    )
    accumulation = safe_float(
        row.get(
            "accumulation_score",
            0,
        )
    )
    hidden = safe_float(
        row.get(
            "hidden_accumulation_score",
            0,
        )
    )
    distribution = safe_float(
        row.get(
            "distribution_pressure",
            0,
        )
    )
    trap = safe_float(
        row.get(
            "retail_trap_score",
            0,
        )
    )

    if (
        distribution >= 75
        and score < 45
    ):
        return "INSTITUTIONAL SELLING"

    if distribution >= 65:
        return "DISTRIBUTION"

    if (
        score >= 78
        and accumulation >= 72
        and trap < 55
    ):
        return "INSTITUTIONAL BUYING"

    if (
        score >= 68
        and accumulation >= 65
    ):
        return "OPERATOR ACCUMULATION"

    if (
        hidden >= 70
        and distribution < 55
    ):
        return "HIDDEN ACCUMULATION"

    if trap >= 75:
        return "RETAIL TRAP"

    return "NEUTRAL"


def classify_risk(
    score: float,
) -> str:
    score = safe_float(
        score
    )

    if score >= 80:
        return "CRITICAL"

    if score >= 65:
        return "HIGH"

    if score >= 45:
        return "MEDIUM"

    return "LOW"


def classify_quality(
    score: float,
) -> str:
    score = safe_float(
        score
    )

    if score >= 80:
        return "EXCELLENT"

    if score >= 65:
        return "STRONG"

    if score >= 50:
        return "MODERATE"

    return "WEAK"


def build_action(
    row: pd.Series,
) -> str:
    label = text(
        row.get(
            "smart_money_label",
            ""
        )
    ).upper()

    if label == "INSTITUTIONAL BUYING":
        return "STRONG WATCH / BUY VALIDATION"

    if label in {
        "OPERATOR ACCUMULATION",
        "HIDDEN ACCUMULATION",
    }:
        return "WATCH FOR ENTRY"

    if label in {
        "DISTRIBUTION",
        "INSTITUTIONAL SELLING",
    }:
        return "AVOID / REDUCE"

    if label == "RETAIL TRAP":
        return "AVOID"

    return "MONITOR"


def build_reason(
    row: pd.Series,
) -> str:
    parts = [
        f"Volume score {safe_float(row.get('volume_score')):.1f}",
        f"Accumulation {safe_float(row.get('accumulation_score')):.1f}",
        f"Distribution {safe_float(row.get('distribution_pressure')):.1f}",
        f"Breakout quality {safe_float(row.get('breakout_quality_score')):.1f}",
        f"Trap risk {safe_float(row.get('retail_trap_score')):.1f}",
    ]

    return " | ".join(
        parts
    )


def classify_sector(
    row: pd.Series,
) -> str:
    score = safe_float(
        row.get(
            "average_smart_money_score",
            0,
        )
    )
    distribution = safe_float(
        row.get(
            "average_distribution_pressure",
            0,
        )
    )

    if (
        score >= 70
        and distribution < 50
    ):
        return "ACCUMULATION"

    if distribution >= 65:
        return "DISTRIBUTION"

    if score >= 55:
        return "POSITIVE"

    if score < 40:
        return "WEAK"

    return "NEUTRAL"


def classify_market_smart_money(
    market_score: float,
    accumulation_share: float,
    distribution_share: float,
) -> str:
    if (
        market_score >= 65
        and accumulation_share
        > distribution_share
    ):
        return "BROAD ACCUMULATION"

    if (
        market_score >= 55
        and accumulation_share
        >= distribution_share
    ):
        return "SELECTIVE ACCUMULATION"

    if distribution_share > accumulation_share:
        return "DISTRIBUTION RISK"

    return "NEUTRAL"


def metric_card(
    label: str,
    value: Any,
) -> str:
    return (
        "<div class='card'>"
        f"<div class='label'>{escape(label)}</div>"
        f"<div class='value'>{escape(value)}</div>"
        "</div>"
    )


def table_html(
    df: pd.DataFrame,
    columns: list[str],
    rows: int,
) -> str:
    if df.empty:
        return "<p>No records found.</p>"

    available = [
        column
        for column in columns
        if column in df.columns
    ]

    if not available:
        return "<p>No requested columns found.</p>"

    header = "".join(
        f"<th>{escape(column.replace('_', ' ').title())}</th>"
        for column in available
    )

    body = []

    for _, row in df[available].head(
        rows
    ).iterrows():
        cells = []

        for column in available:
            value = row.get(
                column,
                "",
            )

            number = safe_float(
                value,
                float(
                    "nan"
                ),
            )

            if math.isfinite(
                number
            ):
                display = (
                    f"{number:.2f}"
                    if not number.is_integer()
                    else str(
                        int(
                            number
                        )
                    )
                )
            else:
                display = text(
                    value
                )

            cells.append(
                f"<td>{escape(display)}</td>"
            )

        body.append(
            "<tr>"
            + "".join(
                cells
            )
            + "</tr>"
        )

    return (
        "<div style='overflow:auto'><table>"
        "<thead><tr>"
        + header
        + "</tr></thead><tbody>"
        + "".join(
            body
        )
        + "</tbody></table></div>"
    )


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        if pd.isna(
            value
        ):
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


def text(
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


def upper(
    value: Any,
) -> str:
    return text(
        value
    ).upper()


def normalize_date(
    value: Any,
) -> str:
    candidate = text(
        value
    )

    if not candidate:
        return datetime.now().strftime(
            "%Y-%m-%d"
        )

    parsed = pd.to_datetime(
        candidate,
        errors="coerce",
    )

    if pd.isna(
        parsed
    ):
        return candidate

    return parsed.strftime(
        "%Y-%m-%d"
    )


def escape(
    value: Any,
) -> str:
    import html

    return html.escape(
        text(
            value
        )
    )


def default_value(
    column: str,
) -> Any:
    text_columns = {
        "symbol",
        "company",
        "sector",
        "breakout_quality",
        "retail_trap_risk",
        "smart_money_label",
        "recommended_action",
        "smart_money_reason",
        "sector_smart_money_label",
    }

    integer_columns = {
        "rank",
        "stocks",
        "institutional_buying_count",
        "operator_accumulation_count",
        "hidden_accumulation_count",
        "distribution_count",
        "retail_trap_count",
    }

    if column in text_columns:
        return ""

    if column in integer_columns:
        return 0

    return 0.0
