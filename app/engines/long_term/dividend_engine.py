import pandas as pd

from app.utils.long_term_loader import dividend_rules


class DividendEngine:
    def __init__(self):
        self.rules = dividend_rules()

    def score(self, row) -> dict:
        score = 0
        reasons = []
        risks = []

        dividend_yield = self.safe(row, "dividend_yield")
        dividend_years = self.safe(row, "dividend_years")
        payout_ratio = self.safe(row, "payout_ratio")

        if dividend_yield >= self.rules.get("excellent_dividend_yield", 10):
            score += 40
            reasons.append("Excellent dividend yield")
        elif dividend_yield >= self.rules.get("good_dividend_yield", 6):
            score += 30
            reasons.append("Good dividend yield")
        elif dividend_yield >= self.rules.get("minimum_dividend_yield", 3):
            score += 15
            reasons.append("Acceptable dividend yield")
        else:
            risks.append("Low or no dividend yield")

        if dividend_years >= self.rules.get("excellent_dividend_years", 10):
            score += 35
            reasons.append("Excellent dividend history")
        elif dividend_years >= self.rules.get("good_dividend_years", 5):
            score += 25
            reasons.append("Good dividend consistency")
        elif dividend_years >= self.rules.get("minimum_dividend_years", 3):
            score += 12
            reasons.append("Acceptable dividend history")
        else:
            risks.append("Weak dividend history")

        if 0 < payout_ratio <= self.rules.get("safe_payout_ratio", 60):
            score += 25
            reasons.append("Safe payout ratio")
        elif payout_ratio <= self.rules.get("high_payout_ratio", 85):
            score += 10
            reasons.append("High but acceptable payout ratio")
        else:
            risks.append("Unsafe or missing payout ratio")

        score = min(score, 100)

        return {
            "dividend_score": round(score, 2),
            "dividend_reasons": " | ".join(reasons) if reasons else "No strong dividend signal",
            "dividend_risks": " | ".join(risks) if risks else "Normal"
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