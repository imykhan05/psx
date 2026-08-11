import pandas as pd

from app.engines.ai_engine import apply_ai_engine
from app.engines.trend_engine_v2 import add_trend_engine_v2
from app.engines.confidence_engine_v2 import add_confidence_score_v2
from app.engines.market_strength_engine import add_market_strength
from app.engines.sector_engine import SectorEngine
from app.engines.sector_strength_engine import SectorStrengthEngine
from app.engines.institutional_engine import apply_institutional_engine
from app.engines.ai_score_engine_v4 import AIScoreEngineV4


class AIEngineV4:
    """
    AI Engine V4 - Institutional Scoring Layer

    Keeps existing architecture safe.
    Adds:
    - Market strength
    - Sector strength
    - Trend Engine V2
    - Confidence Engine V2
    - Institutional Smart Money Engine
    - AI Score Engine V4
    """

    def __init__(self, max_price: float = 500, market_summary: dict | None = None):
        self.max_price = max_price
        self.market_summary = market_summary or {}

    def run(self, features: pd.DataFrame) -> pd.DataFrame:
        result = apply_ai_engine(
            features,
            max_price=self.max_price
        )

        result["ai_engine_version"] = "v4_institutional_1.2"
        result["base_ai_score"] = result["ai_score"]

        result = add_market_strength(
            result,
            self.market_summary
        )

        sector_engine = SectorEngine(result)
        result = sector_engine.attach_sectors()

        sector_summary = SectorEngine(result).sector_summary()
        sector_strength = SectorStrengthEngine(sector_summary)
        result = sector_strength.attach_sector_strength(result)

        result = add_trend_engine_v2(result)
        result = add_confidence_score_v2(result)

        if "probability_confidence" not in result.columns:
            result["probability_confidence"] = result["confidence_v3"]

        result = apply_institutional_engine(result)

        score_engine = AIScoreEngineV4()
        result = score_engine.apply(result)

        result = self.apply_institutional_adjustment(result)

        result["ai_engine_version"] = "v4_institutional_1.2"

        return result

    def apply_institutional_adjustment(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Adjust final AI score using smart money signals.
        Safe additive layer after AIScoreEngineV4.
        """

        result = df.copy()

        result = self.ensure_institutional_columns(result)

        result["smart_money_score"] = pd.to_numeric(
            result["smart_money_score"],
            errors="coerce",
        ).fillna(50)

        result["accumulation_score"] = pd.to_numeric(
            result["accumulation_score"],
            errors="coerce",
        ).fillna(50)

        result["distribution_score"] = pd.to_numeric(
            result["distribution_score"],
            errors="coerce",
        ).fillna(25)

        result["institutional_buy_probability"] = pd.to_numeric(
            result["institutional_buy_probability"],
            errors="coerce",
        ).fillna(50)

        result["institutional_sell_probability"] = pd.to_numeric(
            result["institutional_sell_probability"],
            errors="coerce",
        ).fillna(30)

        result["ai_score"] = pd.to_numeric(
            result["ai_score"],
            errors="coerce",
        ).fillna(0)

        institutional_boost = (
            (result["smart_money_score"] - 50) * 0.08
            + (result["accumulation_score"] - 50) * 0.06
            - (result["distribution_score"] - 25) * 0.05
            + (result["institutional_buy_probability"] - 50) * 0.04
            - (result["institutional_sell_probability"] - 30) * 0.04
        )

        result["institutional_score_boost"] = institutional_boost.round(2)

        result["ai_score"] = (
            result["ai_score"] + result["institutional_score_boost"]
        ).clip(lower=0, upper=100).round(2)

        result["institutional_adjusted_ai_score"] = result["ai_score"]

        return result

    def ensure_institutional_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        defaults = {
            "smart_money_score": 50,
            "accumulation_score": 50,
            "distribution_score": 25,
            "institutional_buy_probability": 50,
            "institutional_sell_probability": 30,
            "institutional_signal": "NEUTRAL",
            "wyckoff_phase": "NEUTRAL",
        }

        for col, default in defaults.items():
            if col not in df.columns:
                df[col] = default

        return df


def apply_ai_engine_v4(
    features: pd.DataFrame,
    max_price: float = 500,
    market_summary: dict | None = None
) -> pd.DataFrame:
    engine = AIEngineV4(
        max_price=max_price,
        market_summary=market_summary
    )

    return engine.run(features)