import pandas as pd

from app.utils.long_term_loader import valuation_rules


class ValuationEngine:
    def __init__(self):
        self.rules = valuation_rules()

    def score(self, row) -> dict:
        score = 0
        reasons = []
        risks = []

        pe = self.safe(row, "pe")
        pb = self.safe(row, "pb")
        margin_of_safety = self.safe(row, "margin_of_safety")

        if pe > 0:
            if pe <= self.rules.get("pe_undervalued", 8):
                score += 35
                reasons.append("Low P/E valuation")
            elif pe <= self.rules.get("pe_fair", 15):
                score += 25
                reasons.append("Fair P/E valuation")
            elif pe <= self.rules.get("pe_expensive", 25):
                score += 10
                reasons.append("Expensive but acceptable P/E")
            else:
                risks.append("Very high P/E")
        else:
            risks.append("Missing or invalid P/E")

        if pb > 0:
            if pb <= self.rules.get("pb_undervalued", 1.0):
                score += 30
                reasons.append("Low P/B valuation")
            elif pb <= self.rules.get("pb_fair", 2.0):
                score += 20
                reasons.append("Fair P/B valuation")
            elif pb <= self.rules.get("pb_expensive", 4.0):
                score += 8
                reasons.append("Expensive but acceptable P/B")
            else:
                risks.append("Very high P/B")
        else:
            risks.append("Missing or invalid P/B")

        if margin_of_safety >= self.rules.get("margin_of_safety_excellent", 30):
            score += 35
            reasons.append("Excellent margin of safety")
        elif margin_of_safety >= self.rules.get("margin_of_safety_good", 20):
            score += 25
            reasons.append("Good margin of safety")
        elif margin_of_safety >= self.rules.get("margin_of_safety_minimum", 10):
            score += 12
            reasons.append("Acceptable margin of safety")
        else:
            risks.append("Low margin of safety")

        score = min(score, 100)

        return {
            "valuation_score": round(score, 2),
            "valuation_reasons": " | ".join(reasons) if reasons else "No strong valuation signal",
            "valuation_risks": " | ".join(risks) if risks else "Normal"
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