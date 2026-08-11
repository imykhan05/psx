import pandas as pd

from app.utils.long_term_loader import quality_rules


class QualityEngine:
    def __init__(self):
        self.rules = quality_rules()

    def score(self, row) -> dict:
        score = 0
        reasons = []
        risks = []

        listing_years = self.safe(row, "listing_years")
        is_sector_leader = bool(self.safe(row, "is_sector_leader"))
        stable_earnings = bool(self.safe(row, "stable_earnings"))
        low_debt = bool(self.safe(row, "low_debt"))
        consistent_dividend = bool(self.safe(row, "consistent_dividend"))

        if listing_years >= self.rules.get("preferred_listing_years", 10):
            score += 30
            reasons.append("Long listing history")
        elif listing_years >= self.rules.get("minimum_listing_years", 5):
            score += 15
            reasons.append("Acceptable listing history")
        else:
            risks.append("Short listing history")

        if is_sector_leader:
            score += self.rules.get("sector_leader_bonus", 10)
            reasons.append("Sector leader")

        if stable_earnings:
            score += self.rules.get("stable_earnings_bonus", 10)
            reasons.append("Stable earnings")

        if low_debt:
            score += self.rules.get("low_debt_bonus", 10)
            reasons.append("Low debt quality")

        if consistent_dividend:
            score += self.rules.get("consistent_dividend_bonus", 10)
            reasons.append("Consistent dividend")

        score = min(score, 100)

        return {
            "quality_score": round(score, 2),
            "quality_reasons": " | ".join(reasons) if reasons else "No strong quality signal",
            "quality_risks": " | ".join(risks) if risks else "Normal"
        }

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()

        scores = result.apply(
            lambda row: pd.Series(self.score(row)),
            axis=1
        )

        return pd.concat([result, scores], axis=1)

    @staticmethod
    def safe(row, key, default=0):
        value = row.get(key, default)
        if pd.isna(value):
            return default
        return value