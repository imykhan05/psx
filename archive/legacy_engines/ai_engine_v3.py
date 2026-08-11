import pandas as pd

from app.engines.ai_engine import apply_ai_engine
from app.engines.confidence_engine import add_confidence_score
from app.engines.market_strength_engine import add_market_strength
from app.engines.sector_engine import SectorEngine
from app.engines.sector_strength_engine import SectorStrengthEngine
from app.engines.ai_score_engine import AIScoreEngine


class AIEngineV3:
    """
    AI Engine V3 - Phase 2

    Adds:
    - Base AI score
    - Confidence V2
    - Market Strength
    - Sector Strength
    - Adaptive AI Score
    - Adaptive Verdict
    """

    def __init__(self, max_price: float = 500, market_summary: dict | None = None):
        self.max_price = max_price
        self.market_summary = market_summary or {}

    def run(self, features: pd.DataFrame) -> pd.DataFrame:
        result = apply_ai_engine(
            features,
            max_price=self.max_price
        )

        result["ai_engine_version"] = "v3_phase_2"
        result["base_ai_score"] = result["ai_score"]

        # Market Strength
        result = add_market_strength(
            result,
            self.market_summary
        )

        # Temporary sector attach
        sector_engine = SectorEngine(result)
        result = sector_engine.attach_sectors()

        # Sector Strength
        sector_summary = SectorEngine(result).sector_summary()
        sector_strength = SectorStrengthEngine(sector_summary)
        result = sector_strength.attach_sector_strength(result)

        # Confidence V2
        result = add_confidence_score(result)

        # Probability placeholders for now
        if "probability_confidence" not in result.columns:
            result["probability_confidence"] = result["confidence_v2"]

        # Adaptive AI Score
        score_engine = AIScoreEngine()
        result = score_engine.apply(result)
        result = score_engine.add_verdict(result)

        # Make adaptive score primary score
        result["ai_score"] = result["adaptive_ai_score"]
        result["confidence"] = result["confidence_v2"]
        result["verdict"] = result["adaptive_verdict"]

        result = result.sort_values(
            [
                "adaptive_ai_score",
                "confidence_v2",
                "sector_strength_score",
                "market_strength_score",
                "volume"
            ],
            ascending=False
        )

        return result


def apply_ai_engine_v3(
    features: pd.DataFrame,
    max_price: float = 500,
    market_summary: dict | None = None
) -> pd.DataFrame:
    engine = AIEngineV3(
        max_price=max_price,
        market_summary=market_summary
    )

    return engine.run(features)