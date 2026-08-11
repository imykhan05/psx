import pandas as pd

from app.engines.ai_engine import apply_ai_engine


class AIEngineV3:
    """
    AI Engine V3 - Phase 1

    Purpose:
    - Existing stable ai_engine.py ko reuse karta hai
    - Base AI score generate karta hai
    - Future phases mein confidence, probability, market strength,
      sector strength aur adaptive score integrate honge
    """

    def __init__(self, max_price: float = 500):
        self.max_price = max_price

    def run(self, features: pd.DataFrame) -> pd.DataFrame:
        result = apply_ai_engine(
            features,
            max_price=self.max_price
        )

        result["ai_engine_version"] = "v3_phase_1"
        result["base_ai_score"] = result["ai_score"]

        return result


def apply_ai_engine_v3(features: pd.DataFrame, max_price: float = 500) -> pd.DataFrame:
    engine = AIEngineV3(max_price=max_price)
    return engine.run(features)