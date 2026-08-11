import pandas as pd


class AIScoreEngine:

    def __init__(self):
        pass

    def calculate_score(self, row):

        score = 0

        score += row.get("trend_score", 0) * 0.20

        score += row.get("momentum_score", 0) * 0.15

        score += row.get("volume_score", 0) * 0.10

        score += row.get("price_action_score", 0) * 0.15

        score += row.get("historical_score", 0) * 0.10

        score += row.get("market_strength_score", 50) * 0.05

        score += row.get("sector_strength_score", 50) * 0.05

        score += row.get("probability_confidence", 50) * 0.10

        score += row.get("confidence_v2", 50) * 0.10

        score -= row.get("risk_penalty", 0) * 0.10

        score = max(
            min(score, 100),
            0
        )

        return round(score, 2)

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
                "probability_confidence"
            ],

            ascending=False

        )

        return result

    def verdict(self, score):

        if score >= 90:
            return "STRONG BUY"

        if score >= 80:
            return "BUY"

        if score >= 65:
            return "WATCH"

        if score >= 50:
            return "SPECULATIVE"

        return "AVOID"

    def add_verdict(self, df):

        result = df.copy()

        result["adaptive_verdict"] = result[
            "adaptive_ai_score"
        ].apply(self.verdict)

        return result