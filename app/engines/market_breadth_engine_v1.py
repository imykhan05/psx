from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class MarketBreadthConfigV1:
    output_folder: str = "reports/market_breadth"
    summary_filename: str = "market_breadth_summary.csv"
    sector_filename: str = "market_breadth_by_sector.csv"
    advance_decline_filename: str = "advance_decline.csv"
    volume_filename: str = "volume_breadth.csv"
    momentum_filename: str = "momentum_breadth.csv"
    health_filename: str = "market_health.csv"
    json_filename: str = "market_breadth.json"
    markdown_filename: str = "market_breadth.md"
    html_filename: str = "market_breadth.html"


class MarketBreadthEngineV1:
    """
    Market Breadth Engine V1

    Measures whole-market participation and strength using:
    - advance / decline breadth
    - up-volume / down-volume breadth
    - momentum breadth
    - sector participation
    - AI decision breadth
    - breakout / new-high / new-low breadth
    - upper-cap environment probability

    The engine is column-tolerant and does not modify trading signals.
    """

    VERSION = "market_breadth_engine_v1_0_institutional"

    def __init__(
        self,
        output_folder: str = "reports/market_breadth",
    ):
        self.config = MarketBreadthConfigV1(
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
        self.sector_path = (
            self.output_folder
            / self.config.sector_filename
        )
        self.advance_decline_path = (
            self.output_folder
            / self.config.advance_decline_filename
        )
        self.volume_path = (
            self.output_folder
            / self.config.volume_filename
        )
        self.momentum_path = (
            self.output_folder
            / self.config.momentum_filename
        )
        self.health_path = (
            self.output_folder
            / self.config.health_filename
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
        trading_date: str | None = None,
    ) -> dict:
        df = clean_df(
            market_df
        )

        resolved_date = normalize_date(
            trading_date
        )

        if df.empty:
            summary = self.empty_summary(
                resolved_date
            )
            sector_df = pd.DataFrame(
                columns=self.sector_columns()
            )
            advance_df = pd.DataFrame(
                [summary]
            )
            volume_df = pd.DataFrame(
                [summary]
            )
            momentum_df = pd.DataFrame(
                [summary]
            )
            health_df = pd.DataFrame(
                [summary]
            )
        else:
            df = self.normalize_market_df(
                df
            )

            advance_metrics = self.calculate_advance_decline(
                df
            )
            volume_metrics = self.calculate_volume_breadth(
                df
            )
            momentum_metrics = self.calculate_momentum_breadth(
                df
            )
            ai_metrics = self.calculate_ai_breadth(
                df
            )
            breakout_metrics = self.calculate_breakout_breadth(
                df
            )
            sector_df = self.calculate_sector_breadth(
                df
            )

            summary = self.build_summary(
                trading_date=resolved_date,
                total_symbols=int(len(df)),
                advance_metrics=advance_metrics,
                volume_metrics=volume_metrics,
                momentum_metrics=momentum_metrics,
                ai_metrics=ai_metrics,
                breakout_metrics=breakout_metrics,
                sector_df=sector_df,
            )

            advance_df = pd.DataFrame(
                [advance_metrics]
            )
            volume_df = pd.DataFrame(
                [volume_metrics]
            )
            momentum_df = pd.DataFrame(
                [momentum_metrics]
            )
            health_df = pd.DataFrame(
                [summary]
            )

        pd.DataFrame(
            [summary]
        ).to_csv(
            self.summary_path,
            index=False,
            encoding="utf-8-sig",
        )

        self.save_dataframe(
            sector_df,
            self.sector_path,
            self.sector_columns(),
        )

        advance_df.to_csv(
            self.advance_decline_path,
            index=False,
            encoding="utf-8-sig",
        )

        volume_df.to_csv(
            self.volume_path,
            index=False,
            encoding="utf-8-sig",
        )

        momentum_df.to_csv(
            self.momentum_path,
            index=False,
            encoding="utf-8-sig",
        )

        health_df.to_csv(
            self.health_path,
            index=False,
            encoding="utf-8-sig",
        )

        payload = {
            "engine_version": self.VERSION,
            "generated_at": datetime.now().isoformat(
                timespec="seconds"
            ),
            "summary": summary,
            "sector_breadth": sector_df.to_dict(
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
                sector_df=sector_df,
            ),
            encoding="utf-8",
        )

        self.html_path.write_text(
            self.build_html(
                summary=summary,
                sector_df=sector_df,
            ),
            encoding="utf-8",
        )

        return {
            "status": "success",
            "engine_version": self.VERSION,
            "trading_date": resolved_date,
            "breadth_score": summary[
                "breadth_score"
            ],
            "breadth_label": summary[
                "breadth_label"
            ],
            "market_health_score": summary[
                "market_health_score"
            ],
            "upper_cap_probability": summary[
                "upper_cap_probability"
            ],
            "advancing": summary[
                "advancing"
            ],
            "declining": summary[
                "declining"
            ],
            "up_volume_pct": summary[
                "up_volume_pct"
            ],
            "momentum_positive_pct": summary[
                "momentum_positive_pct"
            ],
            "summary_csv": str(
                self.summary_path
            ),
            "sector_csv": str(
                self.sector_path
            ),
            "advance_decline_csv": str(
                self.advance_decline_path
            ),
            "volume_breadth_csv": str(
                self.volume_path
            ),
            "momentum_breadth_csv": str(
                self.momentum_path
            ),
            "market_health_csv": str(
                self.health_path
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
                "Market breadth intelligence generated successfully"
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

        if "symbol" not in result.columns:
            result["symbol"] = ""

        if "sector" not in result.columns:
            result["sector"] = "UNKNOWN"

        result["symbol"] = (
            result["symbol"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.strip()
        )

        result["sector"] = (
            result["sector"]
            .fillna("UNKNOWN")
            .astype(str)
            .str.upper()
            .str.strip()
            .replace(
                {
                    "": "UNKNOWN",
                    "NAN": "UNKNOWN",
                }
            )
        )

        for column in [
            "close",
            "open",
            "high",
            "low",
            "prev_close",
            "change_pct",
            "volume",
            "rsi_14",
            "rsi",
            "ema20",
            "ema50",
            "macd",
            "macd_signal",
            "trend_score_v5",
            "trend_score_v4",
            "buy_probability",
            "smart_money_score",
            "trade_validation_score",
            "final_score",
            "high_52w",
            "low_52w",
            "upper_cap",
            "lower_cap",
        ]:
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
    # CORE METRICS
    # ---------------------------------------------------------

    def calculate_advance_decline(
        self,
        df: pd.DataFrame,
    ) -> dict:
        changes = number_series(
            df,
            "change_pct",
        )

        advancing = int(
            (
                changes > 0
            ).sum()
        )
        declining = int(
            (
                changes < 0
            ).sum()
        )
        unchanged = int(
            (
                changes == 0
            ).sum()
        )

        active = (
            advancing
            + declining
        )

        advance_pct = (
            advancing
            / active
            * 100
            if active > 0
            else 0.0
        )

        decline_pct = (
            declining
            / active
            * 100
            if active > 0
            else 0.0
        )

        advance_decline_ratio = (
            advancing
            / declining
            if declining > 0
            else float(
                advancing
            )
        )

        breadth_spread = (
            advance_pct
            - decline_pct
        )

        return {
            "advancing": advancing,
            "declining": declining,
            "unchanged": unchanged,
            "advance_pct": round(
                advance_pct,
                4,
            ),
            "decline_pct": round(
                decline_pct,
                4,
            ),
            "advance_decline_ratio": round(
                advance_decline_ratio,
                4,
            ),
            "breadth_spread": round(
                breadth_spread,
                4,
            ),
            "average_change_pct": round(
                float(
                    changes.mean()
                ),
                4,
            ),
            "median_change_pct": round(
                float(
                    changes.median()
                ),
                4,
            ),
        }

    def calculate_volume_breadth(
        self,
        df: pd.DataFrame,
    ) -> dict:
        volume = number_series(
            df,
            "volume",
        )
        changes = number_series(
            df,
            "change_pct",
        )

        up_volume = float(
            volume[
                changes > 0
            ].sum()
        )
        down_volume = float(
            volume[
                changes < 0
            ].sum()
        )
        flat_volume = float(
            volume[
                changes == 0
            ].sum()
        )

        directional_volume = (
            up_volume
            + down_volume
        )

        up_volume_pct = (
            up_volume
            / directional_volume
            * 100
            if directional_volume > 0
            else 0.0
        )

        down_volume_pct = (
            down_volume
            / directional_volume
            * 100
            if directional_volume > 0
            else 0.0
        )

        volume_ratio = (
            up_volume
            / down_volume
            if down_volume > 0
            else up_volume
        )

        return {
            "total_volume": round(
                up_volume
                + down_volume
                + flat_volume,
                2,
            ),
            "up_volume": round(
                up_volume,
                2,
            ),
            "down_volume": round(
                down_volume,
                2,
            ),
            "flat_volume": round(
                flat_volume,
                2,
            ),
            "up_volume_pct": round(
                up_volume_pct,
                4,
            ),
            "down_volume_pct": round(
                down_volume_pct,
                4,
            ),
            "up_down_volume_ratio": round(
                volume_ratio,
                4,
            ),
            "volume_breadth_spread": round(
                up_volume_pct
                - down_volume_pct,
                4,
            ),
        }

    def calculate_momentum_breadth(
        self,
        df: pd.DataFrame,
    ) -> dict:
        total = max(
            int(
                len(df)
            ),
            1,
        )

        close = number_series(
            df,
            "close",
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

        close_above_ema20 = percentage_true(
            close > ema20,
            ema20 > 0,
        )

        ema20_above_ema50 = percentage_true(
            ema20 > ema50,
            (
                ema20 > 0
            )
            & (
                ema50 > 0
            ),
        )

        rsi_above_60 = percentage_true(
            rsi >= 60,
            rsi > 0,
        )

        rsi_above_50 = percentage_true(
            rsi >= 50,
            rsi > 0,
        )

        macd_positive = percentage_true(
            macd > macd_signal,
            (
                macd != 0
            )
            | (
                macd_signal != 0
            ),
        )

        trend_positive = percentage_true(
            trend_score >= 60,
            trend_score > 0,
        )

        available_scores = [
            score
            for score in [
                close_above_ema20,
                ema20_above_ema50,
                rsi_above_60,
                macd_positive,
                trend_positive,
            ]
            if score >= 0
        ]

        momentum_positive_pct = (
            sum(
                available_scores
            )
            / len(
                available_scores
            )
            if available_scores
            else 0.0
        )

        return {
            "symbols_analyzed": total,
            "close_above_ema20_pct": round(
                close_above_ema20,
                4,
            ),
            "ema20_above_ema50_pct": round(
                ema20_above_ema50,
                4,
            ),
            "rsi_above_50_pct": round(
                rsi_above_50,
                4,
            ),
            "rsi_above_60_pct": round(
                rsi_above_60,
                4,
            ),
            "macd_positive_pct": round(
                macd_positive,
                4,
            ),
            "trend_positive_pct": round(
                trend_positive,
                4,
            ),
            "momentum_positive_pct": round(
                momentum_positive_pct,
                4,
            ),
        }

    def calculate_ai_breadth(
        self,
        df: pd.DataFrame,
    ) -> dict:
        decision = (
            df.get(
                "final_decision",
                pd.Series(
                    "",
                    index=df.index,
                ),
            )
            .fillna("")
            .astype(str)
            .str.upper()
            .str.strip()
        )

        buy_count = int(
            decision.eq(
                "BUY"
            ).sum()
        )
        hold_count = int(
            decision.eq(
                "HOLD"
            ).sum()
        )
        avoid_count = int(
            decision.isin(
                [
                    "AVOID",
                    "SELL",
                    "NO TRADE",
                ]
            ).sum()
        )

        classified = (
            buy_count
            + hold_count
            + avoid_count
        )

        buy_pct = (
            buy_count
            / classified
            * 100
            if classified > 0
            else 0.0
        )

        smart_money = first_available_series(
            df,
            [
                "smart_money_score",
            ],
        )

        institutional_strength_pct = percentage_true(
            smart_money >= 75,
            smart_money > 0,
        )

        high_probability = first_available_series(
            df,
            [
                "buy_probability",
            ],
        )

        high_probability_buy_pct = percentage_true(
            high_probability >= 70,
            high_probability > 0,
        )

        return {
            "ai_buy_count": buy_count,
            "ai_hold_count": hold_count,
            "ai_avoid_count": avoid_count,
            "ai_buy_pct": round(
                buy_pct,
                4,
            ),
            "institutional_strength_pct": round(
                institutional_strength_pct,
                4,
            ),
            "high_probability_buy_pct": round(
                high_probability_buy_pct,
                4,
            ),
        }

    def calculate_breakout_breadth(
        self,
        df: pd.DataFrame,
    ) -> dict:
        close = number_series(
            df,
            "close",
        )
        high = number_series(
            df,
            "high",
        )
        low = number_series(
            df,
            "low",
        )

        high_52w = first_available_series(
            df,
            [
                "high_52w",
                "week_52_high",
                "high52",
            ],
        )

        low_52w = first_available_series(
            df,
            [
                "low_52w",
                "week_52_low",
                "low52",
            ],
        )

        new_high_pct = percentage_true(
            close >= high_52w * 0.995,
            high_52w > 0,
        )

        new_low_pct = percentage_true(
            close <= low_52w * 1.005,
            low_52w > 0,
        )

        breakout_flag = (
            (
                df.get(
                    "entry_timing_action",
                    pd.Series(
                        "",
                        index=df.index,
                    ),
                )
                .fillna("")
                .astype(str)
                .str.upper()
                .str.contains(
                    "BREAKOUT",
                    na=False,
                )
            )
            | (
                df.get(
                    "institutional_signal",
                    pd.Series(
                        "",
                        index=df.index,
                    ),
                )
                .fillna("")
                .astype(str)
                .str.upper()
                .str.contains(
                    "BREAKOUT",
                    na=False,
                )
            )
        )

        breakout_pct = (
            float(
                breakout_flag.mean()
                * 100
            )
            if len(
                breakout_flag
            )
            else 0.0
        )

        upper_cap_count = self.detect_upper_caps(
            df
        )
        lower_cap_count = self.detect_lower_caps(
            df
        )

        return {
            "new_high_pct": round(
                new_high_pct,
                4,
            ),
            "new_low_pct": round(
                new_low_pct,
                4,
            ),
            "breakout_candidate_pct": round(
                breakout_pct,
                4,
            ),
            "upper_cap_count": int(
                upper_cap_count
            ),
            "lower_cap_count": int(
                lower_cap_count
            ),
            "intraday_strength_pct": round(
                percentage_true(
                    close >= (
                        low
                        + (
                            high
                            - low
                        )
                        * 0.70
                    ),
                    high > low,
                ),
                4,
            ),
        }

    def detect_upper_caps(
        self,
        df: pd.DataFrame,
    ) -> int:
        if "upper_cap" in df.columns:
            upper_cap = number_series(
                df,
                "upper_cap",
            )
            close = number_series(
                df,
                "close",
            )

            return int(
                (
                    (
                        upper_cap > 0
                    )
                    & (
                        close
                        >= upper_cap
                        * 0.999
                    )
                ).sum()
            )

        change = number_series(
            df,
            "change_pct",
        )

        return int(
            (
                change >= 9.5
            ).sum()
        )

    def detect_lower_caps(
        self,
        df: pd.DataFrame,
    ) -> int:
        if "lower_cap" in df.columns:
            lower_cap = number_series(
                df,
                "lower_cap",
            )
            close = number_series(
                df,
                "close",
            )

            return int(
                (
                    (
                        lower_cap > 0
                    )
                    & (
                        close
                        <= lower_cap
                        * 1.001
                    )
                ).sum()
            )

        change = number_series(
            df,
            "change_pct",
        )

        return int(
            (
                change <= -9.5
            ).sum()
        )

    def calculate_sector_breadth(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        rows = []

        for sector, group in df.groupby(
            "sector",
            dropna=False,
        ):
            changes = number_series(
                group,
                "change_pct",
            )
            volume = number_series(
                group,
                "volume",
            )

            advancing = int(
                (
                    changes > 0
                ).sum()
            )
            declining = int(
                (
                    changes < 0
                ).sum()
            )
            active = (
                advancing
                + declining
            )

            advance_pct = (
                advancing
                / active
                * 100
                if active > 0
                else 0.0
            )

            up_volume = float(
                volume[
                    changes > 0
                ].sum()
            )
            down_volume = float(
                volume[
                    changes < 0
                ].sum()
            )

            directional_volume = (
                up_volume
                + down_volume
            )

            up_volume_pct = (
                up_volume
                / directional_volume
                * 100
                if directional_volume > 0
                else 0.0
            )

            trend_score = first_available_series(
                group,
                [
                    "trend_score_v5",
                    "trend_score_v4",
                    "trend_score",
                ],
            )

            trend_positive_pct = percentage_true(
                trend_score >= 60,
                trend_score > 0,
            )

            buy_probability = first_available_series(
                group,
                [
                    "buy_probability",
                ],
            )

            ai_strength_pct = percentage_true(
                buy_probability >= 70,
                buy_probability > 0,
            )

            sector_score = weighted_average(
                [
                    (
                        advance_pct,
                        0.35,
                    ),
                    (
                        up_volume_pct,
                        0.30,
                    ),
                    (
                        trend_positive_pct,
                        0.20,
                    ),
                    (
                        ai_strength_pct,
                        0.15,
                    ),
                ]
            )

            rows.append({
                "sector": upper(
                    sector
                )
                or "UNKNOWN",
                "stocks": int(
                    len(group)
                ),
                "advancing": advancing,
                "declining": declining,
                "unchanged": int(
                    (
                        changes == 0
                    ).sum()
                ),
                "advance_pct": round(
                    advance_pct,
                    4,
                ),
                "average_change_pct": round(
                    float(
                        changes.mean()
                    ),
                    4,
                ),
                "total_volume": round(
                    float(
                        volume.sum()
                    ),
                    2,
                ),
                "up_volume_pct": round(
                    up_volume_pct,
                    4,
                ),
                "trend_positive_pct": round(
                    trend_positive_pct,
                    4,
                ),
                "ai_strength_pct": round(
                    ai_strength_pct,
                    4,
                ),
                "sector_breadth_score": round(
                    sector_score,
                    2,
                ),
                "sector_breadth_label": classify_breadth(
                    sector_score
                ),
            })

        result = pd.DataFrame(
            rows
        )

        if not result.empty:
            result = result.sort_values(
                [
                    "sector_breadth_score",
                    "total_volume",
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
    # SUMMARY
    # ---------------------------------------------------------

    def build_summary(
        self,
        trading_date: str,
        total_symbols: int,
        advance_metrics: dict,
        volume_metrics: dict,
        momentum_metrics: dict,
        ai_metrics: dict,
        breakout_metrics: dict,
        sector_df: pd.DataFrame,
    ) -> dict:
        breadth_score = weighted_average(
            [
                (
                    advance_metrics[
                        "advance_pct"
                    ],
                    0.28,
                ),
                (
                    volume_metrics[
                        "up_volume_pct"
                    ],
                    0.24,
                ),
                (
                    momentum_metrics[
                        "momentum_positive_pct"
                    ],
                    0.22,
                ),
                (
                    ai_metrics[
                        "ai_buy_pct"
                    ],
                    0.12,
                ),
                (
                    ai_metrics[
                        "institutional_strength_pct"
                    ],
                    0.08,
                ),
                (
                    breakout_metrics[
                        "intraday_strength_pct"
                    ],
                    0.06,
                ),
            ]
        )

        sector_participation = (
            float(
                (
                    number_series(
                        sector_df,
                        "sector_breadth_score",
                    )
                    >= 60
                ).mean()
                * 100
            )
            if not sector_df.empty
            else 0.0
        )

        market_health_score = weighted_average(
            [
                (
                    breadth_score,
                    0.70,
                ),
                (
                    sector_participation,
                    0.20,
                ),
                (
                    max(
                        0.0,
                        min(
                            100.0,
                            50
                            + advance_metrics[
                                "average_change_pct"
                            ]
                            * 10,
                        ),
                    ),
                    0.10,
                ),
            ]
        )

        upper_cap_score = weighted_average(
            [
                (
                    advance_metrics[
                        "advance_pct"
                    ],
                    0.25,
                ),
                (
                    volume_metrics[
                        "up_volume_pct"
                    ],
                    0.25,
                ),
                (
                    momentum_metrics[
                        "momentum_positive_pct"
                    ],
                    0.20,
                ),
                (
                    breakout_metrics[
                        "intraday_strength_pct"
                    ],
                    0.15,
                ),
                (
                    ai_metrics[
                        "institutional_strength_pct"
                    ],
                    0.15,
                ),
            ]
        )

        return {
            "engine_version": self.VERSION,
            "generated_at": datetime.now().isoformat(
                timespec="seconds"
            ),
            "trading_date": trading_date,
            "total_symbols": total_symbols,
            **advance_metrics,
            **volume_metrics,
            **momentum_metrics,
            **ai_metrics,
            **breakout_metrics,
            "bullish_sectors": int(
                (
                    number_series(
                        sector_df,
                        "sector_breadth_score",
                    )
                    >= 60
                ).sum()
            )
            if not sector_df.empty
            else 0,
            "weak_sectors": int(
                (
                    number_series(
                        sector_df,
                        "sector_breadth_score",
                    )
                    < 40
                ).sum()
            )
            if not sector_df.empty
            else 0,
            "sector_participation_pct": round(
                sector_participation,
                4,
            ),
            "breadth_score": round(
                breadth_score,
                2,
            ),
            "breadth_label": classify_breadth(
                breadth_score
            ),
            "market_health_score": round(
                market_health_score,
                2,
            ),
            "market_health_label": classify_market_health(
                market_health_score
            ),
            "upper_cap_environment_score": round(
                upper_cap_score,
                2,
            ),
            "upper_cap_probability": classify_upper_cap_probability(
                upper_cap_score
            ),
            "market_participation_status": classify_participation(
                advance_metrics[
                    "advance_pct"
                ],
                volume_metrics[
                    "up_volume_pct"
                ],
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
            "advancing": 0,
            "declining": 0,
            "unchanged": 0,
            "advance_pct": 0.0,
            "decline_pct": 0.0,
            "advance_decline_ratio": 0.0,
            "breadth_spread": 0.0,
            "average_change_pct": 0.0,
            "median_change_pct": 0.0,
            "total_volume": 0.0,
            "up_volume": 0.0,
            "down_volume": 0.0,
            "flat_volume": 0.0,
            "up_volume_pct": 0.0,
            "down_volume_pct": 0.0,
            "up_down_volume_ratio": 0.0,
            "volume_breadth_spread": 0.0,
            "symbols_analyzed": 0,
            "close_above_ema20_pct": 0.0,
            "ema20_above_ema50_pct": 0.0,
            "rsi_above_50_pct": 0.0,
            "rsi_above_60_pct": 0.0,
            "macd_positive_pct": 0.0,
            "trend_positive_pct": 0.0,
            "momentum_positive_pct": 0.0,
            "ai_buy_count": 0,
            "ai_hold_count": 0,
            "ai_avoid_count": 0,
            "ai_buy_pct": 0.0,
            "institutional_strength_pct": 0.0,
            "high_probability_buy_pct": 0.0,
            "new_high_pct": 0.0,
            "new_low_pct": 0.0,
            "breakout_candidate_pct": 0.0,
            "upper_cap_count": 0,
            "lower_cap_count": 0,
            "intraday_strength_pct": 0.0,
            "bullish_sectors": 0,
            "weak_sectors": 0,
            "sector_participation_pct": 0.0,
            "breadth_score": 0.0,
            "breadth_label": "NO DATA",
            "market_health_score": 0.0,
            "market_health_label": "NO DATA",
            "upper_cap_environment_score": 0.0,
            "upper_cap_probability": "NO DATA",
            "market_participation_status": "NO DATA",
        }

    # ---------------------------------------------------------
    # OUTPUT HELPERS
    # ---------------------------------------------------------

    def build_markdown(
        self,
        summary: dict,
        sector_df: pd.DataFrame,
    ) -> str:
        lines = [
            "# Market Breadth Intelligence",
            "",
            f"- Trading Date: **{summary['trading_date']}**",
            f"- Breadth Score: **{summary['breadth_score']:.2f}/100**",
            f"- Breadth Label: **{summary['breadth_label']}**",
            f"- Market Health: **{summary['market_health_score']:.2f}/100**",
            f"- Participation: **{summary['market_participation_status']}**",
            f"- Upper-Cap Probability: **{summary['upper_cap_probability']}**",
            "",
            "## Breadth",
            "",
            f"- Advancing: **{summary['advancing']}**",
            f"- Declining: **{summary['declining']}**",
            f"- Advance Ratio: **{summary['advance_decline_ratio']:.2f}**",
            f"- Up Volume: **{summary['up_volume_pct']:.2f}%**",
            f"- Momentum Positive: **{summary['momentum_positive_pct']:.2f}%**",
            f"- Bullish Sectors: **{summary['bullish_sectors']}**",
            "",
            "## Strongest Sectors",
            "",
        ]

        if sector_df.empty:
            lines.append(
                "_No sector data available._"
            )
        else:
            for _, row in sector_df.head(
                10
            ).iterrows():
                lines.append(
                    (
                        f"- **{text(row.get('sector'))}** — "
                        f"{safe_float(row.get('sector_breadth_score')):.1f}/100 "
                        f"({text(row.get('sector_breadth_label'))})"
                    )
                )

        return "\n".join(
            lines
        )

    def build_html(
        self,
        summary: dict,
        sector_df: pd.DataFrame,
    ) -> str:
        sector_rows = ""

        for _, row in sector_df.head(
            25
        ).iterrows():
            sector_rows += (
                "<tr>"
                f"<td>{escape(row.get('sector'))}</td>"
                f"<td>{safe_int(row.get('stocks'))}</td>"
                f"<td>{safe_float(row.get('advance_pct')):.1f}%</td>"
                f"<td>{safe_float(row.get('up_volume_pct')):.1f}%</td>"
                f"<td>{safe_float(row.get('trend_positive_pct')):.1f}%</td>"
                f"<td>{safe_float(row.get('sector_breadth_score')):.1f}</td>"
                f"<td>{escape(row.get('sector_breadth_label'))}</td>"
                "</tr>"
            )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Market Breadth Engine V1</title>
<style>
body{{margin:0;background:#06101c;color:#edf5fc;font-family:Arial,sans-serif}}
.container{{width:min(1300px,96%);margin:24px auto}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
.card{{background:#0d1c2d;border:1px solid #21405d;border-radius:14px;padding:16px}}
.label{{font-size:11px;color:#91a8bd;text-transform:uppercase}}
.value{{font-size:24px;font-weight:700;margin-top:7px}}
.full{{grid-column:span 4}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th,td{{padding:9px;border-bottom:1px solid #21405d;text-align:left}}
th{{color:#91a8bd}}
@media(max-width:800px){{.grid{{grid-template-columns:1fr 1fr}}.full{{grid-column:span 2}}}}
</style>
</head>
<body>
<div class="container">
<h1>PSX Market Breadth Intelligence</h1>
<p>Trading Date: {escape(summary['trading_date'])}</p>
<div class="grid">
<div class="card"><div class="label">Breadth Score</div><div class="value">{summary['breadth_score']:.1f}</div></div>
<div class="card"><div class="label">Market Health</div><div class="value">{summary['market_health_score']:.1f}</div></div>
<div class="card"><div class="label">Advance / Decline</div><div class="value">{summary['advancing']} / {summary['declining']}</div></div>
<div class="card"><div class="label">Upper-Cap Probability</div><div class="value">{escape(summary['upper_cap_probability'])}</div></div>
<div class="card"><div class="label">Up Volume</div><div class="value">{summary['up_volume_pct']:.1f}%</div></div>
<div class="card"><div class="label">Momentum Positive</div><div class="value">{summary['momentum_positive_pct']:.1f}%</div></div>
<div class="card"><div class="label">Institutional Strength</div><div class="value">{summary['institutional_strength_pct']:.1f}%</div></div>
<div class="card"><div class="label">Bullish Sectors</div><div class="value">{summary['bullish_sectors']}</div></div>
<div class="card full">
<h2>Sector Breadth</h2>
<div style="overflow:auto">
<table>
<thead><tr><th>Sector</th><th>Stocks</th><th>Advance %</th><th>Up Volume %</th><th>Trend + %</th><th>Score</th><th>Label</th></tr></thead>
<tbody>{sector_rows}</tbody>
</table>
</div>
</div>
</div>
</div>
</body>
</html>"""

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

    def sector_columns(
        self,
    ) -> list[str]:
        return [
            "sector",
            "stocks",
            "advancing",
            "declining",
            "unchanged",
            "advance_pct",
            "average_change_pct",
            "total_volume",
            "up_volume_pct",
            "trend_positive_pct",
            "ai_strength_pct",
            "sector_breadth_score",
            "sector_breadth_label",
        ]


def run_market_breadth_engine_v1(
    market_df: pd.DataFrame,
    trading_date: str | None = None,
    output_folder: str = "reports/market_breadth",
) -> dict:
    engine = MarketBreadthEngineV1(
        output_folder=output_folder
    )

    return engine.run(
        market_df=market_df,
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


def percentage_true(
    condition: pd.Series,
    valid_mask: pd.Series,
) -> float:
    valid_mask = valid_mask.fillna(
        False
    )
    valid_count = int(
        valid_mask.sum()
    )

    if valid_count == 0:
        return 0.0

    return float(
        (
            condition.fillna(False)
            & valid_mask
        ).sum()
        / valid_count
        * 100
    )


def weighted_average(
    items: list[tuple[float, float]],
) -> float:
    valid = [
        (
            safe_float(value),
            safe_float(weight),
        )
        for value, weight in items
        if safe_float(weight) > 0
    ]

    total_weight = sum(
        weight
        for _, weight in valid
    )

    if total_weight <= 0:
        return 0.0

    return sum(
        value
        * weight
        for value, weight in valid
    ) / total_weight


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

        if math.isfinite(number):
            return number
    except Exception:
        pass

    return default


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(
            float(
                value
            )
        )
    except Exception:
        return default


def text(
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

    if pd.isna(parsed):
        return candidate

    return parsed.strftime(
        "%Y-%m-%d"
    )


def classify_breadth(
    score: float,
) -> str:
    if score >= 75:
        return "VERY STRONG"

    if score >= 60:
        return "BULLISH"

    if score >= 45:
        return "NEUTRAL"

    if score >= 30:
        return "WEAK"

    return "BEARISH"


def classify_market_health(
    score: float,
) -> str:
    if score >= 80:
        return "EXCELLENT"

    if score >= 65:
        return "STRONG"

    if score >= 50:
        return "HEALTHY"

    if score >= 35:
        return "FRAGILE"

    return "WEAK"


def classify_upper_cap_probability(
    score: float,
) -> str:
    if score >= 75:
        return "VERY HIGH"

    if score >= 60:
        return "HIGH"

    if score >= 45:
        return "MODERATE"

    if score >= 30:
        return "LOW"

    return "VERY LOW"


def classify_participation(
    advance_pct: float,
    up_volume_pct: float,
) -> str:
    if (
        advance_pct >= 60
        and up_volume_pct >= 60
    ):
        return "BROAD PARTICIPATION"

    if (
        advance_pct >= 50
        and up_volume_pct >= 50
    ):
        return "HEALTHY PARTICIPATION"

    if (
        advance_pct < 40
        and up_volume_pct < 40
    ):
        return "WEAK PARTICIPATION"

    return "MIXED PARTICIPATION"


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
    if column in {
        "sector",
        "sector_breadth_label",
    }:
        return ""

    if column in {
        "stocks",
        "advancing",
        "declining",
        "unchanged",
    }:
        return 0

    return 0.0
