import pandas as pd


class AIScoreEngineV5:
    """
    AI Score Engine V5
    ------------------
    Institutional weighted scoring engine.

    Final Output:
        adaptive_ai_score
        adaptive_verdict
        final_probability
        final_score
        model_version
    """

    VERSION = "AI_V5.0"

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:

        if df is None or df.empty:
            return df

        result = df.copy()

        self.ensure_columns(result)

        scores = result.apply(
            self.calculate_score,
            axis=1,
            result_type="expand",
        )

        result = pd.concat([result, scores], axis=1)

        return result

    def calculate_score(self, row):

        ai = self.safe(row, "ai_score", 50)

        trend = self.safe(row, "trend_score_v5", 50)

        confidence = self.safe(row, "confidence_v3", 50)

        smart = self.safe(row, "smart_money_score", 50)

        accumulation = self.safe(row, "accumulation_score", 50)

        distribution = self.safe(row, "distribution_score", 25)

        liquidity = self.safe(row, "liquidity_score_v4", 50)

        momentum = self.safe(row, "momentum_score_v4", 50)

        volume = self.safe(row, "volume_score_v4", 50)

        market = self.safe(row, "market_strength_score", 50)

        sector = self.safe(row, "sector_strength_score", 50)

        buy_prob = self.safe(
            row,
            "institutional_buy_probability",
            self.safe(row, "buy_probability", 50),
        )

        sell_prob = self.safe(
            row,
            "institutional_sell_probability",
            self.safe(row, "sell_probability", 25),
        )

        score = (

            ai * 0.18 +

            trend * 0.12 +

            confidence * 0.10 +

            smart * 0.15 +

            accumulation * 0.10 +

            liquidity * 0.07 +

            momentum * 0.07 +

            volume * 0.05 +

            market * 0.06 +

            sector * 0.05 +

            buy_prob * 0.08 -

            distribution * 0.05 -

            sell_prob * 0.02

        )

        score = max(min(score, 100), 0)

        probability = round(
            score * 0.75 + buy_prob * 0.25,
            2,
        )

        verdict = self.verdict(score)

        return pd.Series({

            "adaptive_ai_score": round(score, 2),

            "adaptive_verdict": verdict,

            "final_probability": probability,

            "final_score": round(score, 2),

            "model_version": self.VERSION,

        })

    @staticmethod
    def verdict(score):

        if score >= 90:
            return "STRONG BUY"

        if score >= 80:
            return "BUY"

        if score >= 70:
            return "ACCUMULATE"

        if score >= 60:
            return "WATCH"

        if score >= 45:
            return "HOLD"

        if score >= 30:
            return "REDUCE"

        return "SELL"

    @staticmethod
    def ensure_columns(df):

        defaults = {

            "ai_score": 50,

            "trend_score_v5": 50,

            "confidence_v3": 50,

            "smart_money_score": 50,

            "accumulation_score": 50,

            "distribution_score": 25,

            "liquidity_score_v4": 50,

            "momentum_score_v4": 50,

            "volume_score_v4": 50,

            "market_strength_score": 50,

            "sector_strength_score": 50,

            "institutional_buy_probability": 50,

            "institutional_sell_probability": 25,

            "buy_probability": 50,

            "sell_probability": 25,

        }

        for col, default in defaults.items():

            if col not in df.columns:
                df[col] = default

    @staticmethod
    def safe(row, key, default=0):

        value = row.get(key, default)

        try:

            if pd.isna(value):
                return default

        except Exception:
            pass

        try:
            return float(value)

        except Exception:
            return default


def apply_ai_score_engine_v5(df: pd.DataFrame):

    engine = AIScoreEngineV5()

    return engine.apply(df)