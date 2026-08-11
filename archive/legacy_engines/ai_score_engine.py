import pandas as pd


class AIScoreEngine:
    """
    Calibrated AI Score Engine

    Formula:
    adaptive_ai_score =
        base_ai_score
        + confidence_bonus
        + market_bonus
        + sector_bonus
        + probability_bonus
        - risk_penalty_adjustment
    """

    def __init__(self):
        pass

    def calculate_score(self, row):
        base_score = self.safe(row, "base_ai_score", self.safe(row, "ai_score", 0))
        confidence = self.safe(row, "confidence_v2", self.safe(row, "confidence", 50))
        market_strength = self.safe(row, "market_strength_score", 50)
        sector_strength = self.safe(row, "sector_strength_score", 50)
        probability_confidence = self.safe(row, "probability_confidence", 50)
        risk_penalty = self.safe(row, "risk_penalty", 0)

        confidence_bonus = (confidence - 50) * 0.12
        market_bonus = (market_strength - 50) * 0.08
        sector_bonus = (sector_strength - 50) * 0.10
        probability_bonus = (probability_confidence - 50) * 0.08

        risk_adjustment = risk_penalty * 0.30

        score = (
            base_score
            + confidence_bonus
            + market_bonus
            + sector_bonus
            + probability_bonus
            - risk_adjustment
        )

        return round(max(min(score, 100), 0), 2)

    def apply(self, df: pd.DataFrame):
        result = df.copy()

        result["adaptive_ai_score"] = result.apply(
            self.calculate_score,
            axis=1
        )

        result = result.sort_values(
            [
                "adaptive_ai_score",
                "confidence_v2",
                "sector_strength_score",
                "market_strength_score",
                "volume",
            ],
            ascending=False
        )

        return result

    def verdict(self, score):
        if score >= 88:
            return "STRONG BUY"

        if score >= 76:
            return "BUY"

        if score >= 62:
            return "WATCH"

        if score >= 50:
            return "SPECULATIVE"

        return "AVOID"

    def add_verdict(self, df):
        result = df.copy()

        result["adaptive_verdict"] = result["adaptive_ai_score"].apply(
            self.verdict
        )

        return result

    @staticmethod
    def safe(row, key, default=0):
        value = row.get(key, default)

        if pd.isna(value):
            return default

        return value