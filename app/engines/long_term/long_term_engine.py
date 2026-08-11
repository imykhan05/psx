from __future__ import annotations

import math

import pandas as pd

from app.engines.long_term.fundamental_engine import FundamentalEngine
from app.engines.long_term.growth_engine import GrowthEngine
from app.engines.long_term.dividend_engine import DividendEngine
from app.engines.long_term.valuation_engine import ValuationEngine
from app.engines.long_term.quality_engine import QualityEngine
from app.utils.long_term_loader import (
    score_weights,
    verdict_rules,
    allocation_rules,
    holding_period,
)


ENGINE_VERSION = "long_term_engine_v2_valuation_aligned"


class LongTermEngine:
    """
    Long-Term Engine V2

    Main improvements:
    - Long-term verdict is aligned with fair value and upside.
    - Negative upside can never produce BUY or STRONG BUY.
    - Missing or unreliable valuation produces WATCH/AVOID.
    - Margin of safety is calculated.
    - Allocation depends on final valuation-aware verdict.
    - Confidence is reduced when valuation data is incomplete.
    """

    def __init__(self):
        self.weights = score_weights()
        self.verdicts = verdict_rules()
        self.allocations = allocation_rules()
        self.holding = holding_period()

        self.fundamental_engine = FundamentalEngine()
        self.growth_engine = GrowthEngine()
        self.dividend_engine = DividendEngine()
        self.valuation_engine = ValuationEngine()
        self.quality_engine = QualityEngine()

    def apply(
        self,
        df: pd.DataFrame,
        capital: int = 50000,
    ) -> pd.DataFrame:
        if df is None:
            return pd.DataFrame()

        if not isinstance(df, pd.DataFrame):
            return pd.DataFrame()

        if df.empty:
            result = df.copy()
            result["long_term_engine_version"] = ENGINE_VERSION
            return result

        result = self.remove_duplicate_columns(df.copy())

        result = self.fundamental_engine.apply(result)
        result = self.remove_duplicate_columns(result)

        result = self.growth_engine.apply(result)
        result = self.remove_duplicate_columns(result)

        result = self.dividend_engine.apply(result)
        result = self.remove_duplicate_columns(result)

        result = self.valuation_engine.apply(result)
        result = self.remove_duplicate_columns(result)

        result = self.quality_engine.apply(result)
        result = self.remove_duplicate_columns(result)

        scores = result.apply(
            lambda row: pd.Series(
                self.calculate_long_term_score(
                    row=row,
                    capital=capital,
                )
            ),
            axis=1,
        )

        result = pd.concat(
            [result, scores],
            axis=1,
        )

        result = self.remove_duplicate_columns(result)

        # Authoritative provenance gate: overwrite EVERY long-term output
        # column for non-REAL rows. This is required because input-origin
        # columns (e.g. a fabricated `fair_value`) survive the concat/dedup
        # above and would otherwise leak the fabricated number. (ROADMAP.md F0.1)
        result = self.enforce_provenance_gate(result)

        result = result.sort_values(
            by=[
                "long_term_rank",
                "long_term_score",
                "upside_pct",
                "long_term_confidence",
                "investment_amount",
            ],
            ascending=[
                True,
                False,
                False,
                False,
                False,
            ],
        ).reset_index(drop=True)

        result["long_term_engine_version"] = ENGINE_VERSION

        return result

    def calculate_long_term_score(
        self,
        row: pd.Series,
        capital: int,
    ) -> dict:
        # ---------------------------------------------------------------
        # PROVENANCE GATE (ROADMAP.md F0.1)
        # A long-term verdict, fair value, or confidence must never be
        # derived from data that is not a genuinely sourced financial
        # statement. Anything not explicitly REAL is refused here, before
        # any number is computed, so fabricated fundamentals can never
        # reach a report.
        # ---------------------------------------------------------------
        provenance = str(row.get("data_provenance", "ABSENT")).strip().upper()

        if provenance != "REAL":
            return self.no_fundamental_data_result(
                provenance=provenance,
                price=self.safe_number(row, "close", 0),
            )

        fundamental = self.safe_number(
            row,
            "fundamental_score",
            0,
        )

        growth = self.safe_number(
            row,
            "growth_score",
            0,
        )

        valuation = self.safe_number(
            row,
            "valuation_score",
            0,
        )

        dividend = self.safe_number(
            row,
            "dividend_score",
            0,
        )

        quality = self.safe_number(
            row,
            "quality_score",
            0,
        )

        price = self.safe_number(
            row,
            "close",
            0,
        )

        fair_value = self.safe_number(
            row,
            "fair_value",
            0,
        )

        total_weight = sum(self.weights.values()) or 100

        raw_score = (
            fundamental * self.weights.get("fundamental", 30)
            + growth * self.weights.get("growth", 25)
            + valuation * self.weights.get("valuation", 20)
            + dividend * self.weights.get("dividend", 15)
            + quality * self.weights.get("quality", 10)
        ) / total_weight

        raw_score = self.clip(
            raw_score,
            0,
            100,
        )

        upside_pct = self.calculate_upside(
            price=price,
            fair_value=fair_value,
        )

        margin_of_safety_pct = self.calculate_margin_of_safety(
            price=price,
            fair_value=fair_value,
        )

        valuation_status = self.get_valuation_status(
            price=price,
            fair_value=fair_value,
            upside_pct=upside_pct,
        )

        valuation_adjustment = self.calculate_valuation_adjustment(
            upside_pct=upside_pct,
            fair_value=fair_value,
            price=price,
        )

        adjusted_score = self.clip(
            raw_score + valuation_adjustment,
            0,
            100,
        )

        confidence = self.calculate_confidence(
            row=row,
            price=price,
            fair_value=fair_value,
            valuation_status=valuation_status,
        )

        verdict = self.get_verdict(
            score=adjusted_score,
            confidence=confidence,
            upside_pct=upside_pct,
            valuation_status=valuation_status,
            fundamental_score=fundamental,
            quality_score=quality,
        )

        allocation_pct = self.get_allocation_pct(
            verdict=verdict,
            confidence=confidence,
            upside_pct=upside_pct,
        )

        investment_amount = round(
            max(capital, 0) * allocation_pct,
            2,
        )

        quantity = (
            int(investment_amount // price)
            if price > 0
            else 0
        )

        expected_value = self.calculate_expected_value(
            price=price,
            fair_value=fair_value,
            confidence=confidence,
        )

        expected_return_pct = self.calculate_upside(
            price=price,
            fair_value=expected_value,
        )

        return {
            "long_term_score_raw": round(raw_score, 2),
            "long_term_score": round(adjusted_score, 2),
            "long_term_confidence": int(confidence),
            "long_term_verdict": verdict,
            "long_term_rank": self.get_verdict_rank(verdict),
            "investment_amount": investment_amount,
            "long_term_quantity": quantity,
            "fair_value": round(fair_value, 2),
            "current_price": round(price, 2),
            "upside_pct": round(upside_pct, 2),
            "margin_of_safety_pct": round(
                margin_of_safety_pct,
                2,
            ),
            "valuation_status": valuation_status,
            "valuation_adjustment": round(
                valuation_adjustment,
                2,
            ),
            "expected_value": round(
                expected_value,
                2,
            ),
            "expected_return_pct": round(
                expected_return_pct,
                2,
            ),
            "holding_years": self.get_holding_years(
                verdict=verdict,
                upside_pct=upside_pct,
            ),
            "long_term_reason": self.build_reason(
                row=row,
                score=adjusted_score,
                raw_score=raw_score,
                confidence=confidence,
                verdict=verdict,
                upside_pct=upside_pct,
                valuation_status=valuation_status,
                margin_of_safety_pct=margin_of_safety_pct,
            ),
            "long_term_risk": self.build_risk(
                row=row,
                upside_pct=upside_pct,
                valuation_status=valuation_status,
                confidence=confidence,
            ),
        }

    def enforce_provenance_gate(
        self,
        result: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Force the no-fundamental-data output for every non-REAL row, overwriting
        any input-origin columns (notably a fabricated `fair_value`). This is the
        single authoritative guarantee that no fabricated valuation reaches a
        report; the per-row early return in calculate_long_term_score() is a
        cheaper first line of defense that produces identical values.
        """
        if result is None or result.empty:
            return result

        if "data_provenance" not in result.columns:
            # No provenance information at all -> nothing is REAL, gate everything.
            result["data_provenance"] = "ABSENT"

        provenance = (
            result["data_provenance"].astype(str).str.strip().str.upper()
        )
        non_real = provenance != "REAL"

        if not non_real.any():
            return result

        for index in result.index[non_real]:
            gated = self.no_fundamental_data_result(
                provenance=str(
                    result.at[index, "data_provenance"]
                ).strip().upper(),
                price=self.safe_number(result.loc[index], "close", 0),
            )
            for column, value in gated.items():
                result.at[index, column] = value

        return result

    def no_fundamental_data_result(
        self,
        provenance: str,
        price: float = 0.0,
    ) -> dict:
        """
        Non-actionable result for a symbol without REAL fundamentals.

        confidence and fair_value are 0 so reporting's
        filter_meaningful_long_term_rows() drops the row entirely — no
        fabricated verdict, fair value, or confidence reaches any report.
        Same key set as the normal path so column shape stays stable.
        """
        if provenance == "SEED":
            reason = (
                "NO VERDICT: fundamentals for this symbol are placeholder "
                "(SEED) data, not sourced financials. Long-term valuation is "
                "disabled until real data is ingested (ROADMAP.md F3.3)."
            )
        else:
            reason = (
                "NO VERDICT: no sourced fundamentals available for this "
                "symbol. Long-term valuation requires real financial "
                "statements (ROADMAP.md F3.3)."
            )

        return {
            "long_term_score_raw": 0.0,
            "long_term_score": 0.0,
            "long_term_confidence": 0,
            "long_term_verdict": "NO FUNDAMENTAL DATA",
            "long_term_rank": self.get_verdict_rank("NO FUNDAMENTAL DATA"),
            "investment_amount": 0.0,
            "long_term_quantity": 0,
            "fair_value": 0.0,
            "current_price": round(self.safe_number(pd.Series({"close": price}), "close", 0), 2),
            "upside_pct": 0.0,
            "margin_of_safety_pct": 0.0,
            "valuation_status": "NO DATA",
            "valuation_adjustment": 0.0,
            "expected_value": 0.0,
            "expected_return_pct": 0.0,
            "holding_years": 0,
            "long_term_reason": reason,
            "long_term_risk": "Fundamentals unavailable",
            "data_provenance": provenance,
        }

    def calculate_confidence(
        self,
        row: pd.Series,
        price: float,
        fair_value: float,
        valuation_status: str,
    ) -> int:
        required_fields = [
            "eps",
            "roe",
            "roa",
            "debt_equity",
            "current_ratio",
            "net_margin",
            "eps_growth",
            "revenue_growth",
            "profit_growth",
            "dividend_yield",
            "pe",
            "pb",
            "fair_value",
        ]

        available = 0

        for field in required_fields:
            value = row.get(field, None)

            if self.has_valid_value(value):
                available += 1

        completeness_ratio = (
            available / len(required_fields)
            if required_fields
            else 0
        )

        confidence = 35
        confidence += int(completeness_ratio * 50)

        volume = self.safe_number(
            row,
            "volume",
            0,
        )

        if volume >= 500_000:
            confidence += 5

        if volume >= 1_000_000:
            confidence += 5

        if price <= 0:
            confidence -= 25

        if fair_value <= 0:
            confidence -= 25

        if valuation_status == "INVALID VALUATION":
            confidence -= 20

        elif valuation_status == "DEEPLY OVERVALUED":
            confidence -= 10

        elif valuation_status == "OVERVALUED":
            confidence -= 5

        if available < 6:
            confidence = min(confidence, 55)

        return int(
            self.clip(
                confidence,
                0,
                100,
            )
        )

    def get_verdict(
        self,
        score: float,
        confidence: int,
        upside_pct: float,
        valuation_status: str,
        fundamental_score: float,
        quality_score: float,
    ) -> str:
        if confidence < 45:
            return "AVOID"

        if valuation_status == "INVALID VALUATION":
            if score >= 75 and confidence >= 65:
                return "WATCH"

            return "AVOID"

        if upside_pct < -10:
            return "AVOID"

        if -10 <= upside_pct < 0:
            if score >= 80 and confidence >= 75:
                return "WATCH"

            return "AVOID"

        if 0 <= upside_pct < 5:
            if score >= 82 and confidence >= 80:
                return "WATCH"

            return "AVOID"

        if 5 <= upside_pct < 10:
            if (
                score >= 75
                and confidence >= 65
                and fundamental_score >= 65
            ):
                return "ACCUMULATE"

            return "WATCH"

        if 10 <= upside_pct < 20:
            if (
                score >= 80
                and confidence >= 70
                and fundamental_score >= 70
                and quality_score >= 60
            ):
                return "BUY"

            if score >= 68:
                return "ACCUMULATE"

            return "WATCH"

        if 20 <= upside_pct < 35:
            if (
                score >= 84
                and confidence >= 75
                and fundamental_score >= 75
                and quality_score >= 65
            ):
                return "STRONG BUY"

            if score >= 74 and confidence >= 65:
                return "BUY"

            return "ACCUMULATE"

        if upside_pct >= 35:
            if (
                score >= 82
                and confidence >= 75
                and fundamental_score >= 70
                and quality_score >= 60
            ):
                return "STRONG BUY"

            if score >= 72 and confidence >= 65:
                return "BUY"

            if score >= 62:
                return "ACCUMULATE"

            return "WATCH"

        return "AVOID"

    def get_allocation_pct(
        self,
        verdict: str,
        confidence: int,
        upside_pct: float,
    ) -> float:
        configured_key = verdict.lower().replace(" ", "_")

        configured_allocation = self.allocations.get(
            configured_key,
            None,
        )

        fallback_allocations = {
            "STRONG BUY": 0.25,
            "BUY": 0.15,
            "ACCUMULATE": 0.10,
            "WATCH": 0.05,
            "AVOID": 0.0,
        }

        allocation = (
            configured_allocation
            if configured_allocation is not None
            else fallback_allocations.get(verdict, 0.0)
        )

        if verdict == "WATCH":
            allocation = min(allocation, 0.05)

        if confidence < 60:
            allocation *= 0.50

        elif confidence < 75:
            allocation *= 0.75

        if upside_pct < 5:
            allocation = 0.0

        elif upside_pct < 10:
            allocation = min(allocation, 0.10)

        elif upside_pct < 20:
            allocation = min(allocation, 0.15)

        return round(
            max(min(allocation, 0.30), 0),
            4,
        )

    def calculate_valuation_adjustment(
        self,
        upside_pct: float,
        fair_value: float,
        price: float,
    ) -> float:
        if price <= 0 or fair_value <= 0:
            return -20

        if upside_pct >= 50:
            return 10

        if upside_pct >= 35:
            return 8

        if upside_pct >= 25:
            return 6

        if upside_pct >= 15:
            return 4

        if upside_pct >= 10:
            return 2

        if upside_pct >= 5:
            return 0

        if upside_pct >= 0:
            return -5

        if upside_pct >= -10:
            return -12

        if upside_pct >= -25:
            return -20

        return -30

    def get_valuation_status(
        self,
        price: float,
        fair_value: float,
        upside_pct: float,
    ) -> str:
        if price <= 0 or fair_value <= 0:
            return "INVALID VALUATION"

        if upside_pct >= 40:
            return "DEEPLY UNDERVALUED"

        if upside_pct >= 20:
            return "UNDERVALUED"

        if upside_pct >= 10:
            return "ATTRACTIVE"

        if upside_pct >= 5:
            return "SLIGHTLY UNDERVALUED"

        if upside_pct >= 0:
            return "FAIRLY VALUED"

        if upside_pct >= -10:
            return "SLIGHTLY OVERVALUED"

        if upside_pct >= -25:
            return "OVERVALUED"

        return "DEEPLY OVERVALUED"

    def calculate_expected_value(
        self,
        price: float,
        fair_value: float,
        confidence: int,
    ) -> float:
        if price <= 0:
            return 0

        if fair_value <= 0:
            return price

        confidence_weight = self.clip(
            confidence / 100,
            0.25,
            1.0,
        )

        expected_value = (
            fair_value * confidence_weight
            + price * (1 - confidence_weight)
        )

        return max(expected_value, 0)

    def calculate_upside(
        self,
        price: float,
        fair_value: float,
    ) -> float:
        if price <= 0 or fair_value <= 0:
            return 0

        return (
            (fair_value - price)
            / price
            * 100
        )

    def calculate_margin_of_safety(
        self,
        price: float,
        fair_value: float,
    ) -> float:
        if price <= 0 or fair_value <= 0:
            return 0

        return (
            (fair_value - price)
            / fair_value
            * 100
        )

    def get_holding_years(
        self,
        verdict: str,
        upside_pct: float,
    ) -> int:
        configured_years = int(
            self.holding.get(
                "ideal_years",
                5,
            )
        )

        if verdict == "STRONG BUY":
            return max(configured_years, 5)

        if verdict == "BUY":
            return max(min(configured_years, 5), 3)

        if verdict == "ACCUMULATE":
            return 3

        if verdict == "WATCH":
            return 1

        return 0

    def build_reason(
        self,
        row: pd.Series,
        score: float,
        raw_score: float,
        confidence: int,
        verdict: str,
        upside_pct: float,
        valuation_status: str,
        margin_of_safety_pct: float,
    ) -> str:
        reasons = [
            self.clean_text(
                row.get(
                    "fundamental_reasons",
                    "",
                )
            ),
            self.clean_text(
                row.get(
                    "growth_reasons",
                    "",
                )
            ),
            self.clean_text(
                row.get(
                    "valuation_reasons",
                    "",
                )
            ),
            self.clean_text(
                row.get(
                    "dividend_reasons",
                    "",
                )
            ),
            self.clean_text(
                row.get(
                    "quality_reasons",
                    "",
                )
            ),
        ]

        clean_reasons = [
            reason
            for reason in reasons
            if reason
        ]

        summary = (
            f"{verdict}: Adjusted score {score:.2f}/100 "
            f"(raw {raw_score:.2f}), confidence {confidence}%, "
            f"upside {upside_pct:.2f}%, "
            f"margin of safety {margin_of_safety_pct:.2f}%, "
            f"valuation {valuation_status}."
        )

        if clean_reasons:
            summary += " " + " | ".join(
                clean_reasons[:8]
            )

        return summary

    def build_risk(
        self,
        row: pd.Series,
        upside_pct: float,
        valuation_status: str,
        confidence: int,
    ) -> str:
        risks = [
            self.clean_text(
                row.get(
                    "fundamental_risks",
                    "",
                )
            ),
            self.clean_text(
                row.get(
                    "growth_risks",
                    "",
                )
            ),
            self.clean_text(
                row.get(
                    "valuation_risks",
                    "",
                )
            ),
            self.clean_text(
                row.get(
                    "dividend_risks",
                    "",
                )
            ),
            self.clean_text(
                row.get(
                    "quality_risks",
                    "",
                )
            ),
        ]

        clean_risks = [
            risk
            for risk in risks
            if risk
            and risk.upper() not in {
                "NORMAL",
                "NAN",
                "NONE",
            }
        ]

        if valuation_status == "INVALID VALUATION":
            clean_risks.append(
                "Fair value unavailable or invalid"
            )

        if upside_pct < 0:
            clean_risks.append(
                f"Current price is {abs(upside_pct):.2f}% above fair value"
            )

        if confidence < 60:
            clean_risks.append(
                "Low data confidence"
            )

        if not clean_risks:
            return "Normal"

        return " | ".join(
            self.unique_strings(clean_risks)
        )

    def get_verdict_rank(
        self,
        verdict: str,
    ) -> int:
        ranking = {
            "STRONG BUY": 1,
            "BUY": 2,
            "ACCUMULATE": 3,
            "WATCH": 4,
            "AVOID": 5,
            "NO FUNDAMENTAL DATA": 9,
        }

        return ranking.get(
            verdict,
            6,
        )

    @staticmethod
    def safe_number(
        row: pd.Series,
        key: str,
        default: float = 0,
    ) -> float:
        value = row.get(
            key,
            default,
        )

        try:
            if pd.isna(value):
                return float(default)
        except Exception:
            pass

        try:
            number = float(value)

            if math.isfinite(number):
                return number

            return float(default)

        except Exception:
            return float(default)

    @staticmethod
    def has_valid_value(
        value,
    ) -> bool:
        try:
            if pd.isna(value):
                return False
        except Exception:
            pass

        if value in [
            "",
            None,
            "nan",
            "NaN",
        ]:
            return False

        try:
            numeric = float(value)

            if not math.isfinite(numeric):
                return False

            return numeric != 0

        except Exception:
            return bool(
                str(value).strip()
            )

    @staticmethod
    def clean_text(
        value,
    ) -> str:
        try:
            if pd.isna(value):
                return ""
        except Exception:
            pass

        text = str(value).strip()

        if text.lower() in {
            "",
            "nan",
            "none",
            "normal",
        }:
            return ""

        return text

    @staticmethod
    def clip(
        value: float,
        low: float = 0,
        high: float = 100,
    ) -> float:
        try:
            numeric = float(value)
        except Exception:
            numeric = low

        return max(
            min(numeric, high),
            low,
        )

    @staticmethod
    def remove_duplicate_columns(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        if df is None:
            return pd.DataFrame()

        if not hasattr(df, "columns"):
            return pd.DataFrame()

        return df.loc[
            :,
            ~df.columns.duplicated(),
        ].copy()

    @staticmethod
    def unique_strings(
        values: list[str],
    ) -> list[str]:
        output = []
        seen = set()

        for value in values:
            cleaned = str(value).strip()

            if not cleaned:
                continue

            if cleaned in seen:
                continue

            seen.add(cleaned)
            output.append(cleaned)

        return output