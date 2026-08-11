import pandas as pd

from app.engines.ai_engine import apply_ai_engine
from app.engines.trend_engine_v2 import add_trend_engine_v2
from app.engines.confidence_engine_v2 import add_confidence_score_v2
from app.engines.market_strength_engine import add_market_strength
from app.engines.sector_engine import SectorEngine
from app.engines.sector_strength_engine import SectorStrengthEngine
from app.engines.institutional_engine import apply_institutional_engine
from app.engines.ai_score_engine_v5 import apply_ai_score_engine_v5


class AIEngineV5:
    """
    AI Engine V5 - Unified Institutional Intelligence Layer

    Purpose:
    Create one clean institutional AI pipeline.

    Pipeline:
    - Base AI Engine
    - Market Strength
    - Sector Attachment
    - Sector Strength
    - Trend Engine V2
    - Confidence Engine V2
    - Institutional Smart Money Engine
    - AI Score Engine V5

    Safe:
    - Does not modify old V4 files
    - Adds fallback columns
    - Produces final_score, adaptive_ai_score, adaptive_verdict
    """

    VERSION = "v5_unified_institutional_1.0"

    def __init__(self, max_price: float = 500, market_summary: dict | None = None):
        self.max_price = max_price
        self.market_summary = market_summary or {}

    def run(self, features: pd.DataFrame) -> pd.DataFrame:
        if features is None or features.empty:
            return features

        result = features.copy()
        result = self.prepare_feature_aliases(result)

        result = apply_ai_engine(
            result,
            max_price=self.max_price,
        )

        result["base_ai_score"] = result.get("ai_score", 50)
        result["ai_engine_version"] = self.VERSION

        result = add_market_strength(
            result,
            self.market_summary,
        )

        sector_engine = SectorEngine(result)
        result = sector_engine.attach_sectors()

        sector_summary = SectorEngine(result).sector_summary()
        sector_strength = SectorStrengthEngine(sector_summary)
        result = sector_strength.attach_sector_strength(result)

        result = add_trend_engine_v2(result)
        result = add_confidence_score_v2(result)

        result = self.ensure_pre_institutional_columns(result)

        result = apply_institutional_engine(result)

        result = self.ensure_probability_columns(result)

        result = apply_ai_score_engine_v5(result)

        result = self.finalize(result)

        return result

    def prepare_feature_aliases(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Fix old AI engine column-name mismatch safely.

        Old ai_engine.py expects:
        - above_ema20
        - above_ema50
        - above_ema100
        - above_ema200
        - rsi14
        - is_3d_momentum
        - is_5d_momentum
        - is_healthy_gain
        - is_extended_today
        """

        result = df.copy()

        alias_map = {
            "above_ema20": "price_above_ema20",
            "above_ema50": "price_above_ema50",
            "above_ema100": "price_above_ema100",
            "above_ema200": "price_above_ema200",
            "rsi14": "rsi",
        }

        for new_col, old_col in alias_map.items():
            if new_col not in result.columns and old_col in result.columns:
                result[new_col] = result[old_col]

        if "is_3d_momentum" not in result.columns:
            result["is_3d_momentum"] = result.get("return_3d", 0) > 0

        if "is_5d_momentum" not in result.columns:
            result["is_5d_momentum"] = result.get("return_5d", 0) > 0

        if "is_3d_extended" not in result.columns:
            result["is_3d_extended"] = result.get("return_3d", 0) >= 12

        if "is_5d_extended" not in result.columns:
            result["is_5d_extended"] = result.get("return_5d", 0) >= 18

        if "is_healthy_gain" not in result.columns:
            change = pd.to_numeric(
                result.get("change_pct", 0),
                errors="coerce",
            ).fillna(0)
            result["is_healthy_gain"] = (change >= 1) & (change <= 6)

        if "is_extended_today" not in result.columns:
            change = pd.to_numeric(
                result.get("change_pct", 0),
                errors="coerce",
            ).fillna(0)
            result["is_extended_today"] = change >= 7

        if "momentum_status" not in result.columns:
            result["momentum_status"] = "NEUTRAL"
            result.loc[result["is_3d_momentum"], "momentum_status"] = "MOMENTUM"
            result.loc[
                result["is_3d_momentum"] & result["is_5d_momentum"],
                "momentum_status",
            ] = "STRONG MOMENTUM"

        return result

    def ensure_pre_institutional_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()

        defaults = {
            "ai_score": 50,
            "confidence": 50,
            "confidence_v3": 50,
            "trend_score_v4": 50,
            "trend_score_v5": 50,
            "trend_label_v5": "NEUTRAL",
            "momentum_score_v4": 50,
            "volume_score_v4": 50,
            "liquidity_score_v4": 50,
            "risk_score_v4": 50,
            "market_score_v4": 50,
            "sector_score_v4": 50,
            "buy_probability": 50,
            "sell_probability": 25,
            "probability_confidence": 50,
        }

        for col, default in defaults.items():
            if col not in result.columns:
                result[col] = default

        if "probability_confidence" not in result.columns:
            result["probability_confidence"] = result["confidence_v3"]

        return result

    def ensure_probability_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()

        if "institutional_buy_probability" not in result.columns:
            result["institutional_buy_probability"] = result.get("buy_probability", 50)

        if "institutional_sell_probability" not in result.columns:
            result["institutional_sell_probability"] = result.get("sell_probability", 25)

        if "smart_money_score" not in result.columns:
            result["smart_money_score"] = 50

        if "accumulation_score" not in result.columns:
            result["accumulation_score"] = 50

        if "distribution_score" not in result.columns:
            result["distribution_score"] = 25

        if "institutional_signal" not in result.columns:
            result["institutional_signal"] = "NEUTRAL"

        return result

    def finalize(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()

        result["ai_engine_version"] = self.VERSION

        if "final_score" not in result.columns:
            result["final_score"] = result.get("adaptive_ai_score", result.get("ai_score", 50))

        if "final_decision" not in result.columns:
            result["final_decision"] = result.get("adaptive_verdict", result.get("verdict", "WATCH"))

        result["ai_score"] = pd.to_numeric(
            result.get("adaptive_ai_score", result.get("ai_score", 50)),
            errors="coerce",
        ).fillna(50).round(2)

        result["final_score"] = pd.to_numeric(
            result["final_score"],
            errors="coerce",
        ).fillna(result["ai_score"]).round(2)

        result["buy_probability"] = pd.to_numeric(
            result.get("final_probability", result.get("buy_probability", 50)),
            errors="coerce",
        ).fillna(50).round(2)

        result["sell_probability"] = pd.to_numeric(
            result.get("sell_probability", 25),
            errors="coerce",
        ).fillna(25).round(2)

        result["confidence"] = pd.to_numeric(
            result.get("confidence_v3", result.get("confidence", 50)),
            errors="coerce",
        ).fillna(50).round(2)

        result["verdict"] = result["final_decision"]

        sort_cols = [
            "final_score",
            "buy_probability",
            "smart_money_score",
            "confidence",
            "volume",
        ]

        available = [c for c in sort_cols if c in result.columns]

        if available:
            result = result.sort_values(
                available,
                ascending=False,
            ).reset_index(drop=True)

        return result


def apply_ai_engine_v5(
    features: pd.DataFrame,
    max_price: float = 500,
    market_summary: dict | None = None,
) -> pd.DataFrame:
    engine = AIEngineV5(
        max_price=max_price,
        market_summary=market_summary,
    )

    return engine.run(features)