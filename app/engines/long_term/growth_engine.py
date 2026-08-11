import pandas as pd

from app.utils.long_term_loader import growth_rules


class GrowthEngine:
    def __init__(self):
        self.rules = growth_rules()

    def score(self, row) -> dict:
        score = 0
        reasons = []
        risks = []

        eps_growth = self.safe(row, "eps_growth")
        revenue_growth = self.safe(row, "revenue_growth")
        profit_growth = self.safe(row, "profit_growth")

        if eps_growth >= self.rules.get("eps_growth_excellent", 20):
            score += 35
            reasons.append("Excellent EPS growth")
        elif eps_growth >= self.rules.get("eps_growth_good", 10):
            score += 25
            reasons.append("Good EPS growth")
        elif eps_growth >= self.rules.get("eps_growth_minimum", 5):
            score += 12
            reasons.append("Acceptable EPS growth")
        else:
            risks.append("Weak EPS growth")

        if revenue_growth >= self.rules.get("revenue_growth_excellent", 15):
            score += 30
            reasons.append("Excellent revenue growth")
        elif revenue_growth >= self.rules.get("revenue_growth_good", 8):
            score += 20
            reasons.append("Good revenue growth")
        elif revenue_growth >= self.rules.get("revenue_growth_minimum", 3):
            score += 10
            reasons.append("Acceptable revenue growth")
        else:
            risks.append("Weak revenue growth")

        if profit_growth >= self.rules.get("profit_growth_excellent", 20):
            score += 35
            reasons.append("Excellent profit growth")
        elif profit_growth >= self.rules.get("profit_growth_good", 10):
            score += 25
            reasons.append("Good profit growth")
        elif profit_growth >= self.rules.get("profit_growth_minimum", 5):
            score += 12
            reasons.append("Acceptable profit growth")
        else:
            risks.append("Weak profit growth")

        score = min(score, 100)

        return {
            "growth_score": round(score, 2),
            "growth_reasons": " | ".join(reasons) if reasons else "No strong growth signal",
            "growth_risks": " | ".join(risks) if risks else "Normal"
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