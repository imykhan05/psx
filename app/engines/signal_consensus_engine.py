from __future__ import annotations

import math
from typing import Any

import pandas as pd


ENGINE_VERSION = "signal_consensus_engine_v1"


class SignalConsensusEngine:
    """
    Signal Consensus Engine V1

    Purpose:
    Combine multiple independent engines into one consistent signal.

    Inputs:
    - AI score / final score
    - Buy probability
    - Smart money score
    - Accumulation / distribution
    - Trade validation
    - Entry timing
    - Risk management
    - Trend
    - Liquidity
    - Market strength
    - Sector strength

    Outputs:
    - consensus_score
    - consensus_confidence
    - consensus_decision
    - consensus_entry_action
    - consensus_risk_level
    - consensus_position_factor
    - consensus_reason
    - consensus_warnings
    """

    def __init__(
        self,
        market_summary: dict | None = None,
    ):
        self.market_summary = market_summary or {}

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None:
            return pd.DataFrame()

        if not isinstance(df, pd.DataFrame):
            return pd.DataFrame()

        if df.empty:
            result = df.copy()
            result["consensus_engine_version"] = ENGINE_VERSION
            return result

        result = remove_duplicate_columns(df.copy())
        result = self.ensure_columns(result)
        result = self.normalize_numeric(result)

        consensus_output = result.apply(
            self.evaluate_row,
            axis=1,
            result_type="expand",
        )

        result = pd.concat(
            [result, consensus_output],
            axis=1,
        )

        result = remove_duplicate_columns(result)

        result = result.sort_values(
            by=[
                "consensus_rank",
                "consensus_score",
                "consensus_confidence",
                "buy_probability",
                "value_traded",
            ],
            ascending=[
                True,
                False,
                False,
                False,
                False,
            ],
        ).reset_index(drop=True)

        result["consensus_engine_version"] = ENGINE_VERSION

        return result

    def evaluate_row(self, row: pd.Series) -> pd.Series:
        ai_score = number(
            row,
            "institutional_v5_score",
            number(
                row,
                "final_score",
                number(row, "ai_score", 50),
            ),
        )

        buy_probability = number(
            row,
            "institutional_v5_win_probability",
            number(row, "buy_probability", 50),
        )

        confidence = number(
            row,
            "institutional_v5_confidence",
            number(
                row,
                "confidence_v3",
                number(row, "confidence", 50),
            ),
        )

        smart_money = number(row, "smart_money_score", 50)
        accumulation = number(row, "accumulation_score", 50)
        distribution = number(row, "distribution_score", 50)
        validation = number(row, "trade_validation_score", 50)
        entry_timing = number(row, "entry_timing_score", 50)
        risk_score = number(row, "risk_management_score", 50)
        trend_score = number(
            row,
            "trend_score_v5",
            number(row, "trend_score_v4", 50),
        )

        liquidity = number(
            row,
            "liquidity_score_v4",
            number(row, "liquidity_score_raw", 50),
        )

        sector_strength = number(
            row,
            "sector_strength_score",
            number(row, "sector_score", 50),
        )

        market_strength = number(
            row,
            "market_strength_score",
            number(
                row,
                "market_score",
                self.market_summary.get("market_score", 50),
            ),
        )

        risk_reward = number(row, "risk_reward_t1", 1.2)
        change_pct = number(row, "change_pct", 0)
        rsi = number(row, "rsi", 50)
        atr_percent = number(row, "atr_percent", 5)
        value_traded = number(row, "value_traded", 0)
        volume = number(row, "volume", 0)

        final_decision = text(row, "final_decision")
        institutional_decision = text(
            row,
            "institutional_v5_final_decision",
        )
        institutional_verdict = text(
            row,
            "institutional_v5_verdict",
        )

        trade_action = text(row, "trade_action")
        validation_status = text(row, "trade_validation_status")
        entry_action = text(row, "entry_timing_action")
        entry_status = text(row, "entry_timing_status")
        risk_permission = text(row, "risk_permission")
        risk_status = text(row, "risk_status")
        risk_action = text(row, "risk_action")
        institutional_signal = text(row, "institutional_signal")
        market_mood = text(
            row,
            "market_mood",
            str(self.market_summary.get("market_mood", "SIDEWAYS")),
        )

        security_block = boolean_value(
            row.get("institutional_v5_security_block", False)
        )

        reasons: list[str] = []
        warnings: list[str] = []

        hard_block = False

        if security_block:
            hard_block = True
            warnings.append("Blocked security type")

        if trade_action in {"REJECTED", "AVOID"}:
            if validation < 70:
                hard_block = True
            warnings.append("Trade validation rejected")

        if validation_status == "REJECTED" and validation < 65:
            hard_block = True
            warnings.append("Validation status rejected")

        if entry_action in {"NO TRADE", "WATCH ONLY"} and entry_timing < 65:
            hard_block = True
            warnings.append("Entry timing rejected")

        if risk_status in {"REJECTED"}:
            hard_block = True
            warnings.append("Risk engine rejected")

        if risk_status == "CHASE RISK REJECTED" and change_pct >= 7:
            hard_block = True
            warnings.append("Chase risk on extended move")

        if volume <= 0:
            hard_block = True
            warnings.append("Invalid volume")

        if value_traded <= 0:
            warnings.append("Value traded unavailable")

        ai_component = clip(ai_score)
        probability_component = clip(buy_probability)
        confidence_component = clip(confidence)

        institutional_component = (
            clip(smart_money) * 0.45
            + clip(accumulation) * 0.30
            + clip(100 - distribution) * 0.25
        )

        execution_component = (
            clip(validation) * 0.55
            + clip(entry_timing) * 0.45
        )

        market_component = (
            clip(market_strength) * 0.60
            + clip(sector_strength) * 0.40
        )

        quality_component = (
            clip(trend_score) * 0.55
            + clip(liquidity) * 0.45
        )

        base_score = (
            ai_component * 0.22
            + probability_component * 0.18
            + confidence_component * 0.10
            + institutional_component * 0.18
            + execution_component * 0.15
            + risk_score * 0.08
            + quality_component * 0.06
            + market_component * 0.03
        )

        score_adjustment = 0.0

        if final_decision in {"STRONG BUY", "BUY"}:
            score_adjustment += 4
            reasons.append("AI decision supportive")

        elif final_decision == "ACCUMULATE":
            score_adjustment += 2
            reasons.append("AI accumulate signal")

        elif final_decision in {"AVOID", "NO TRADE"}:
            score_adjustment -= 3
            warnings.append("AI final decision restrictive")

        if institutional_decision == "BUY":
            score_adjustment += 4
            reasons.append("Institutional calibration supportive")

        elif institutional_decision == "ACCUMULATE":
            score_adjustment += 2

        elif institutional_decision in {"NO TRADE", "AVOID"}:
            score_adjustment -= 3
            warnings.append("Institutional decision restrictive")

        if institutional_verdict == "STRONG BUY":
            score_adjustment += 2

        if institutional_signal in {
            "STRONG ACCUMULATION",
            "ACCUMULATION",
            "INSTITUTIONAL BUYING",
            "BUYING",
        }:
            score_adjustment += 3
            reasons.append("Institutional accumulation")

        if validation >= 90:
            score_adjustment += 3
            reasons.append("Trade validation very strong")

        elif validation >= 80:
            score_adjustment += 1

        elif validation < 60:
            score_adjustment -= 5
            warnings.append("Weak trade validation")

        if entry_action == "BUY NOW":
            score_adjustment += 4
            reasons.append("Entry timing buy now")

        elif entry_action == "BUY ON DIP":
            score_adjustment += 1
            reasons.append("Buy on dip setup")

        elif entry_action == "WAIT PULLBACK":
            score_adjustment -= 1
            warnings.append("Wait for pullback")

        elif entry_action == "BUY ABOVE BREAKOUT":
            score_adjustment -= 1
            warnings.append("Needs breakout confirmation")

        elif entry_action in {"NO TRADE", "WATCH ONLY"}:
            score_adjustment -= 5
            warnings.append("Entry engine restrictive")

        if risk_permission == "TRADE ALLOWED":
            score_adjustment += 3
            reasons.append("Risk engine allowed trade")

        elif risk_permission == "TRADE ALLOWED SMALL":
            score_adjustment += 1
            reasons.append("Risk engine allowed small position")

        elif risk_permission == "WAIT":
            score_adjustment -= 1
            warnings.append("Risk engine suggests wait")

        elif risk_permission == "NO TRADE":
            score_adjustment -= 4
            warnings.append("Risk engine says no trade")

        if risk_status == "CONTROLLED RISK":
            score_adjustment += 2
            reasons.append("Controlled risk")

        elif risk_status == "MEDIUM RISK":
            score_adjustment -= 1

        elif risk_status == "HIGH RISK":
            score_adjustment -= 4
            warnings.append("High risk")

        elif risk_status == "RISK/REWARD REJECTED":
            score_adjustment -= 6
            warnings.append("Poor risk/reward")

        elif risk_status == "CHASE RISK REJECTED":
            score_adjustment -= 6
            warnings.append("Chase risk")

        if risk_action == "AVOID":
            score_adjustment -= 4

        if risk_reward >= 2.0:
            score_adjustment += 4
            reasons.append("Excellent risk/reward")

        elif risk_reward >= 1.5:
            score_adjustment += 2
            reasons.append("Good risk/reward")

        elif risk_reward >= 1.2:
            score_adjustment += 0

        elif risk_reward >= 1.05:
            score_adjustment -= 2
            warnings.append("Weak risk/reward")

        else:
            score_adjustment -= 7
            warnings.append("Unacceptable risk/reward")

        if smart_money >= 85:
            score_adjustment += 3
            reasons.append("Strong smart money")

        elif smart_money >= 75:
            score_adjustment += 1

        elif smart_money < 45:
            score_adjustment -= 3
            warnings.append("Weak smart money")

        if accumulation >= 85:
            score_adjustment += 2
            reasons.append("Strong accumulation")

        if distribution >= 75:
            score_adjustment -= 4
            warnings.append("Distribution pressure")

        if trend_score >= 80:
            score_adjustment += 2
            reasons.append("Strong trend")

        elif trend_score < 40:
            score_adjustment -= 3
            warnings.append("Weak trend")

        if liquidity >= 75:
            score_adjustment += 1

        elif liquidity < 35:
            score_adjustment -= 4
            warnings.append("Weak liquidity")

        if market_strength >= 65:
            score_adjustment += 1
            reasons.append("Market supportive")

        elif market_strength < 45:
            score_adjustment -= 4
            warnings.append("Weak market")

        if "BULL" in market_mood:
            score_adjustment += 1

        elif "BEAR" in market_mood:
            score_adjustment -= 3

        if sector_strength >= 70:
            score_adjustment += 1
            reasons.append("Sector supportive")

        elif sector_strength < 40:
            score_adjustment -= 2
            warnings.append("Weak sector")

        if rsi >= 90:
            score_adjustment -= 7
            warnings.append("RSI extremely overheated")

        elif rsi >= 82:
            score_adjustment -= 4
            warnings.append("RSI overheated")

        elif 55 <= rsi <= 72:
            score_adjustment += 1

        if change_pct >= 9.5:
            score_adjustment -= 8
            warnings.append("Near upper cap / extended")

        elif change_pct >= 7:
            score_adjustment -= 4
            warnings.append("Large daily move")

        elif change_pct >= 4:
            score_adjustment -= 1

        if atr_percent >= 12:
            score_adjustment -= 5
            warnings.append("Very high volatility")

        elif atr_percent >= 8:
            score_adjustment -= 3
            warnings.append("High volatility")

        consensus_score = clip(base_score + score_adjustment)

        vote_result = self.calculate_votes(
            final_decision=final_decision,
            institutional_decision=institutional_decision,
            institutional_verdict=institutional_verdict,
            trade_action=trade_action,
            validation_status=validation_status,
            entry_action=entry_action,
            risk_permission=risk_permission,
            risk_status=risk_status,
            institutional_signal=institutional_signal,
        )

        bullish_votes = vote_result["bullish_votes"]
        neutral_votes = vote_result["neutral_votes"]
        bearish_votes = vote_result["bearish_votes"]
        total_votes = max(
            bullish_votes + neutral_votes + bearish_votes,
            1,
        )

        agreement_ratio = max(
            bullish_votes,
            neutral_votes,
            bearish_votes,
        ) / total_votes

        consensus_confidence = (
            consensus_score * 0.55
            + confidence_component * 0.20
            + agreement_ratio * 100 * 0.15
            + execution_component * 0.10
        )

        if hard_block:
            consensus_score = min(consensus_score, 45)
            consensus_confidence = min(consensus_confidence, 60)

        consensus_score = round(clip(consensus_score), 2)
        consensus_confidence = round(
            clip(consensus_confidence),
            2,
        )

        decision = self.make_decision(
            score=consensus_score,
            confidence=consensus_confidence,
            hard_block=hard_block,
            bullish_votes=bullish_votes,
            bearish_votes=bearish_votes,
            entry_action=entry_action,
            risk_permission=risk_permission,
            risk_status=risk_status,
            change_pct=change_pct,
            risk_reward=risk_reward,
        )

        entry_consensus = self.make_entry_action(
            decision=decision,
            original_entry_action=entry_action,
            risk_permission=risk_permission,
            change_pct=change_pct,
            rsi=rsi,
        )

        risk_level = self.make_risk_level(
            hard_block=hard_block,
            risk_status=risk_status,
            risk_score=risk_score,
            atr_percent=atr_percent,
            change_pct=change_pct,
            liquidity=liquidity,
        )

        position_factor = self.make_position_factor(
            decision=decision,
            risk_level=risk_level,
            risk_permission=risk_permission,
            confidence=consensus_confidence,
        )

        rank = self.decision_rank(decision)

        if not reasons:
            reasons.append("Balanced multi-engine consensus")

        return pd.Series(
            {
                "consensus_score": consensus_score,
                "consensus_confidence": consensus_confidence,
                "consensus_decision": decision,
                "consensus_entry_action": entry_consensus,
                "consensus_risk_level": risk_level,
                "consensus_position_factor": round(
                    position_factor,
                    2,
                ),
                "consensus_bullish_votes": int(bullish_votes),
                "consensus_neutral_votes": int(neutral_votes),
                "consensus_bearish_votes": int(bearish_votes),
                "consensus_agreement_pct": round(
                    agreement_ratio * 100,
                    2,
                ),
                "consensus_hard_block": bool(hard_block),
                "consensus_rank": int(rank),
                "consensus_reason": " | ".join(
                    unique_strings(reasons)
                ),
                "consensus_warnings": " | ".join(
                    unique_strings(warnings)
                ),
            }
        )

    def calculate_votes(
        self,
        final_decision: str,
        institutional_decision: str,
        institutional_verdict: str,
        trade_action: str,
        validation_status: str,
        entry_action: str,
        risk_permission: str,
        risk_status: str,
        institutional_signal: str,
    ) -> dict:
        bullish = 0
        neutral = 0
        bearish = 0

        bullish_words = {
            "STRONG BUY",
            "BUY",
            "ACCUMULATE",
            "APPROVED",
            "VALID",
            "BUY NOW",
            "BUY ON DIP",
            "TRADE ALLOWED",
            "TRADE ALLOWED SMALL",
            "CONTROLLED RISK",
            "STRONG ACCUMULATION",
            "ACCUMULATION",
            "INSTITUTIONAL BUYING",
        }

        neutral_words = {
            "WATCH",
            "WAIT",
            "WAIT PULLBACK",
            "BUY ABOVE BREAKOUT",
            "MEDIUM RISK",
            "SIDEWAYS",
            "",
            "UNKNOWN",
        }

        bearish_words = {
            "NO TRADE",
            "AVOID",
            "REJECTED",
            "SELL",
            "WATCH ONLY",
            "HIGH RISK",
            "CHASE RISK REJECTED",
            "RISK/REWARD REJECTED",
            "DISTRIBUTION",
        }

        signals = [
            final_decision,
            institutional_decision,
            institutional_verdict,
            trade_action,
            validation_status,
            entry_action,
            risk_permission,
            risk_status,
            institutional_signal,
        ]

        for signal in signals:
            normalized = str(signal or "").upper().strip()

            if normalized in bullish_words:
                bullish += 1

            elif normalized in bearish_words:
                bearish += 1

            elif normalized in neutral_words:
                neutral += 1

            else:
                neutral += 1

        return {
            "bullish_votes": bullish,
            "neutral_votes": neutral,
            "bearish_votes": bearish,
        }

    def make_decision(
        self,
        score: float,
        confidence: float,
        hard_block: bool,
        bullish_votes: int,
        bearish_votes: int,
        entry_action: str,
        risk_permission: str,
        risk_status: str,
        change_pct: float,
        risk_reward: float,
    ) -> str:
        if hard_block:
            return "AVOID"

        if risk_reward < 1.0:
            return "AVOID"

        if change_pct >= 9.5:
            return "WAIT FOR PULLBACK"

        if bearish_votes >= bullish_votes + 3:
            if score < 65:
                return "AVOID"

            return "WATCH"

        if score >= 88 and confidence >= 85:
            if risk_permission == "TRADE ALLOWED":
                return "STRONG BUY"

            return "BUY SMALL"

        if score >= 80 and confidence >= 75:
            if entry_action == "BUY NOW":
                if risk_permission in {
                    "TRADE ALLOWED",
                    "TRADE ALLOWED SMALL",
                    "WAIT",
                }:
                    return "BUY"

            if entry_action == "BUY ON DIP":
                return "BUY ON DIP"

            if entry_action == "WAIT PULLBACK":
                return "WAIT FOR PULLBACK"

            if entry_action == "BUY ABOVE BREAKOUT":
                return "BUY ABOVE BREAKOUT"

            return "BUY SMALL"

        if score >= 72:
            if entry_action == "BUY ON DIP":
                return "BUY ON DIP"

            if entry_action == "BUY ABOVE BREAKOUT":
                return "BUY ABOVE BREAKOUT"

            if risk_status in {
                "HIGH RISK",
                "CHASE RISK REJECTED",
            }:
                return "WATCH"

            return "ACCUMULATE"

        if score >= 62:
            return "WATCH"

        return "AVOID"

    def make_entry_action(
        self,
        decision: str,
        original_entry_action: str,
        risk_permission: str,
        change_pct: float,
        rsi: float,
    ) -> str:
        if decision in {"AVOID", "WATCH"}:
            return "NO ENTRY"

        if decision == "WAIT FOR PULLBACK":
            return "WAIT PULLBACK"

        if decision == "BUY ON DIP":
            return "BUY ON DIP"

        if decision == "BUY ABOVE BREAKOUT":
            return "BUY ABOVE BREAKOUT"

        if change_pct >= 7 or rsi >= 82:
            return "WAIT PULLBACK"

        if original_entry_action in {
            "BUY NOW",
            "BUY ON DIP",
            "WAIT PULLBACK",
            "BUY ABOVE BREAKOUT",
        }:
            return original_entry_action

        if risk_permission in {
            "WAIT",
            "TRADE ALLOWED SMALL",
        }:
            return "CONTROLLED ENTRY"

        return "BUY NOW"

    def make_risk_level(
        self,
        hard_block: bool,
        risk_status: str,
        risk_score: float,
        atr_percent: float,
        change_pct: float,
        liquidity: float,
    ) -> str:
        if hard_block:
            return "BLOCKED"

        points = 0

        if risk_status in {
            "HIGH RISK",
            "CHASE RISK REJECTED",
            "RISK/REWARD REJECTED",
        }:
            points += 3

        elif risk_status == "MEDIUM RISK":
            points += 1

        if risk_score < 35:
            points += 3

        elif risk_score < 50:
            points += 1

        if atr_percent >= 10:
            points += 2

        elif atr_percent >= 7:
            points += 1

        if change_pct >= 9.5:
            points += 2

        elif change_pct >= 7:
            points += 1

        if liquidity < 30:
            points += 2

        elif liquidity < 45:
            points += 1

        if points >= 6:
            return "VERY HIGH"

        if points >= 4:
            return "HIGH"

        if points >= 2:
            return "MEDIUM"

        return "LOW"

    def make_position_factor(
        self,
        decision: str,
        risk_level: str,
        risk_permission: str,
        confidence: float,
    ) -> float:
        factor = 1.0

        if decision == "STRONG BUY":
            factor *= 1.0

        elif decision == "BUY":
            factor *= 0.90

        elif decision == "BUY SMALL":
            factor *= 0.65

        elif decision == "ACCUMULATE":
            factor *= 0.60

        elif decision in {
            "BUY ON DIP",
            "BUY ABOVE BREAKOUT",
        }:
            factor *= 0.55

        elif decision == "WAIT FOR PULLBACK":
            factor *= 0.35

        elif decision == "WATCH":
            factor *= 0.20

        else:
            return 0.0

        if risk_permission == "TRADE ALLOWED":
            factor *= 1.0

        elif risk_permission == "TRADE ALLOWED SMALL":
            factor *= 0.80

        elif risk_permission == "WAIT":
            factor *= 0.65

        elif risk_permission == "NO TRADE":
            factor *= 0.40

        if risk_level == "LOW":
            factor *= 1.0

        elif risk_level == "MEDIUM":
            factor *= 0.80

        elif risk_level == "HIGH":
            factor *= 0.55

        elif risk_level == "VERY HIGH":
            factor *= 0.30

        elif risk_level == "BLOCKED":
            return 0.0

        confidence_factor = max(
            min(confidence / 85, 1.10),
            0.50,
        )

        factor *= confidence_factor

        return max(min(factor, 1.0), 0.0)

    def decision_rank(self, decision: str) -> int:
        ranking = {
            "STRONG BUY": 1,
            "BUY": 2,
            "BUY SMALL": 3,
            "ACCUMULATE": 4,
            "BUY ON DIP": 5,
            "BUY ABOVE BREAKOUT": 6,
            "WAIT FOR PULLBACK": 7,
            "WATCH": 8,
            "AVOID": 9,
        }

        return ranking.get(decision, 10)

    def ensure_columns(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        defaults = {
            "final_score": 50,
            "ai_score": 50,
            "buy_probability": 50,
            "confidence": 50,
            "confidence_v3": 50,
            "institutional_v5_score": 50,
            "institutional_v5_win_probability": 50,
            "institutional_v5_confidence": 50,
            "smart_money_score": 50,
            "accumulation_score": 50,
            "distribution_score": 50,
            "trade_validation_score": 50,
            "entry_timing_score": 50,
            "risk_management_score": 50,
            "trend_score_v4": 50,
            "trend_score_v5": 50,
            "liquidity_score_v4": 50,
            "liquidity_score_raw": 50,
            "sector_strength_score": 50,
            "sector_score": 50,
            "market_strength_score": 50,
            "market_score": self.market_summary.get(
                "market_score",
                50,
            ),
            "risk_reward_t1": 1.2,
            "change_pct": 0,
            "rsi": 50,
            "atr_percent": 5,
            "volume": 0,
            "value_traded": 0,
            "final_decision": "WATCH",
            "institutional_v5_final_decision": "WATCH",
            "institutional_v5_verdict": "WATCH",
            "trade_action": "WATCH",
            "trade_validation_status": "UNKNOWN",
            "entry_timing_action": "WATCH",
            "entry_timing_status": "UNKNOWN",
            "risk_permission": "WAIT",
            "risk_status": "MEDIUM RISK",
            "risk_action": "WAIT",
            "institutional_signal": "NEUTRAL",
            "market_mood": self.market_summary.get(
                "market_mood",
                "SIDEWAYS",
            ),
            "institutional_v5_security_block": False,
        }

        for column, default in defaults.items():
            if column not in df.columns:
                df[column] = default

        return df

    def normalize_numeric(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        numeric_columns = [
            "final_score",
            "ai_score",
            "buy_probability",
            "confidence",
            "confidence_v3",
            "institutional_v5_score",
            "institutional_v5_win_probability",
            "institutional_v5_confidence",
            "smart_money_score",
            "accumulation_score",
            "distribution_score",
            "trade_validation_score",
            "entry_timing_score",
            "risk_management_score",
            "trend_score_v4",
            "trend_score_v5",
            "liquidity_score_v4",
            "liquidity_score_raw",
            "sector_strength_score",
            "sector_score",
            "market_strength_score",
            "market_score",
            "risk_reward_t1",
            "change_pct",
            "rsi",
            "atr_percent",
            "volume",
            "value_traded",
        ]

        for column in numeric_columns:
            if column in df.columns:
                df[column] = pd.to_numeric(
                    df[column],
                    errors="coerce",
                ).fillna(0)

        return df


def apply_signal_consensus(
    df: pd.DataFrame,
    market_summary: dict | None = None,
) -> pd.DataFrame:
    engine = SignalConsensusEngine(
        market_summary=market_summary,
    )

    return engine.apply(df)


def number(
    row: pd.Series,
    key: str,
    default: float = 0,
) -> float:
    value = row.get(key, default)

    try:
        if pd.isna(value):
            return float(default)
    except Exception:
        pass

    try:
        return float(value)
    except Exception:
        return float(default)


def text(
    row: pd.Series,
    key: str,
    default: str = "",
) -> str:
    value = row.get(key, default)

    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    return str(value).upper().strip()


def clip(
    value: float,
    low: float = 0,
    high: float = 100,
) -> float:
    try:
        numeric_value = float(value)
    except Exception:
        numeric_value = low

    return max(
        min(numeric_value, high),
        low,
    )


def boolean_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if value is None:
        return False

    text_value = str(value).strip().upper()

    return text_value in {
        "TRUE",
        "1",
        "YES",
        "Y",
        "BLOCKED",
    }


def unique_strings(values: list[str]) -> list[str]:
    output = []
    seen = set()

    for value in values:
        clean = str(value).strip()

        if not clean:
            continue

        if clean in seen:
            continue

        seen.add(clean)
        output.append(clean)

    return output


def remove_duplicate_columns(
    df: pd.DataFrame,
) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()

    if not hasattr(df, "columns"):
        return pd.DataFrame()

    return df.loc[:, ~df.columns.duplicated()].copy()