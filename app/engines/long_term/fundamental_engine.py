import pandas as pd

from app.utils.long_term_loader import fundamental_rules


class FundamentalEngine:
    def __init__(self):
        self.rules = fundamental_rules()

    def score(self, row) -> dict:
        score = 0
        reasons = []
        risks = []

        roe = self.safe(row, "roe")
        roa = self.safe(row, "roa")
        debt_equity = self.safe(row, "debt_equity")
        current_ratio = self.safe(row, "current_ratio")
        net_margin = self.safe(row, "net_margin")
        eps = self.safe(row, "eps")

        # EPS
        if eps > 0:
            score += 10
            reasons.append("Positive EPS")
        else:
            risks.append("Negative or missing EPS")

        # ROE
        if roe >= self.rules.get("roe_excellent", 20):
            score += 25
            reasons.append("Excellent ROE")
        elif roe >= self.rules.get("roe_good", 15):
            score += 20
            reasons.append("Good ROE")
        elif roe >= self.rules.get("roe_minimum", 8):
            score += 10
            reasons.append("Acceptable ROE")
        else:
            risks.append("Weak ROE")

        # ROA
        if roa >= self.rules.get("roa_excellent", 10):
            score += 15
            reasons.append("Excellent ROA")
        elif roa >= self.rules.get("roa_good", 7):
            score += 10
            reasons.append("Good ROA")
        elif roa >= self.rules.get("roa_minimum", 4):
            score += 5
            reasons.append("Acceptable ROA")
        else:
            risks.append("Weak ROA")

        # Debt to Equity
        if debt_equity <= self.rules.get("debt_equity_safe", 0.5):
            score += 20
            reasons.append("Low debt")
        elif debt_equity <= self.rules.get("debt_equity_acceptable", 1.0):
            score += 10
            reasons.append("Acceptable debt")
        elif debt_equity > self.rules.get("debt_equity_high", 1.5):
            risks.append("High debt")

        # Current Ratio
        if current_ratio >= self.rules.get("current_ratio_good", 1.5):
            score += 10
            reasons.append("Strong current ratio")
        elif current_ratio >= self.rules.get("current_ratio_minimum", 1.0):
            score += 5
            reasons.append("Acceptable current ratio")
        else:
            risks.append("Weak liquidity ratio")

        # Net Margin
        if net_margin >= self.rules.get("net_margin_excellent", 20):
            score += 20
            reasons.append("Excellent net margin")
        elif net_margin >= self.rules.get("net_margin_good", 10):
            score += 10
            reasons.append("Good net margin")
        else:
            risks.append("Weak net margin")

        score = min(score, 100)

        return {
            "fundamental_score": round(score, 2),
            "fundamental_reasons": " | ".join(reasons) if reasons else "No strong fundamental signal",
            "fundamental_risks": " | ".join(risks) if risks else "Normal"
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