import math
import hashlib
from datetime import datetime

import pandas as pd


class AIScoreEngineV4:
    """
    Institutional AI Score Engine V4

    Backward-compatible with V3.
    """

    VERSION = "v4_institutional_1.0"

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()

        if result.empty:
            return result

        result["trend_score_v4"] = result.apply(self.trend_score, axis=1)
        result["momentum_score_v4"] = result.apply(self.momentum_score, axis=1)
        result["volume_score_v4"] = result.apply(self.volume_score, axis=1)
        result["liquidity_score_v4"] = result.apply(self.liquidity_score, axis=1)
        result["volatility_score_v4"] = result.apply(self.volatility_score, axis=1)
        result["market_score_v4"] = result.apply(self.market_score, axis=1)
        result["sector_score_v4"] = result.apply(self.sector_score, axis=1)
        result["confidence_score_v4"] = result.apply(self.confidence_score, axis=1)
        result["fundamental_score_v4"] = result.apply(self.fundamental_score, axis=1)
        result["risk_score_v4"] = result.apply(self.risk_score, axis=1)

        result["ai_score_v4"] = result.apply(self.final_score, axis=1)
        result["buy_probability"] = result.apply(self.buy_probability, axis=1)
        result["sell_probability"] = result.apply(self.sell_probability, axis=1)

        result["risk_level"] = result["risk_score_v4"].apply(self.risk_level)
        result["ai_signal_v4"] = result.apply(self.signal, axis=1)

        result["adaptive_ai_score"] = result["ai_score_v4"]
        result["adaptive_verdict"] = result["ai_signal_v4"]
        result["ai_score"] = result["ai_score_v4"]
        result["verdict"] = result["ai_signal_v4"]
        result["confidence"] = result["confidence_score_v4"]

        result["model_version"] = self.VERSION
        result["signal_date"] = datetime.now().strftime("%Y-%m-%d")
        result["signal_id"] = result.apply(self.signal_id, axis=1)

        result["expected_return_1d"] = result["buy_probability"].apply(
            lambda x: round((x - 50) / 10, 2)
        )
        result["expected_return_5d"] = result["buy_probability"].apply(
            lambda x: round((x - 50) / 4, 2)
        )
        result["expected_return_20d"] = result["buy_probability"].apply(
            lambda x: round((x - 50) / 2, 2)
        )

        result["future_return_1d"] = None
        result["future_return_5d"] = None
        result["future_return_20d"] = None
        result["signal_success"] = None
        result["learning_weight"] = 1.0

        sort_cols = [
            "ai_score_v4",
            "buy_probability",
            "confidence_score_v4",
            "sector_score_v4",
            "market_score_v4",
            "volume",
        ]

        available_sort_cols = [c for c in sort_cols if c in result.columns]

        if available_sort_cols:
            result = result.sort_values(
                available_sort_cols,
                ascending=False
            )

        return result

    def final_score(self, row) -> float:
        trend = self.safe(row, "trend_score_v4", 50)
        momentum = self.safe(row, "momentum_score_v4", 50)
        volume = self.safe(row, "volume_score_v4", 50)
        liquidity = self.safe(row, "liquidity_score_v4", 50)
        volatility = self.safe(row, "volatility_score_v4", 50)
        market = self.safe(row, "market_score_v4", 50)
        sector = self.safe(row, "sector_score_v4", 50)
        confidence = self.safe(row, "confidence_score_v4", 50)
        fundamentals = self.safe(row, "fundamental_score_v4", 50)
        risk = self.safe(row, "risk_score_v4", 50)

        score = (
            trend * 0.18
            + momentum * 0.15
            + volume * 0.10
            + liquidity * 0.10
            + volatility * 0.07
            + market * 0.10
            + sector * 0.10
            + confidence * 0.10
            + fundamentals * 0.10
            - max(risk - 50, 0) * 0.18
        )

        return round(self.clip(score), 2)

    def trend_score(self, row) -> float:
        close = self.safe(row, "close", self.safe(row, "price", 0))
        sma20 = self.safe(row, "sma_20", self.safe(row, "SMA_20", 0))
        sma50 = self.safe(row, "sma_50", self.safe(row, "SMA_50", 0))
        ema20 = self.safe(row, "ema_20", self.safe(row, "EMA_20", 0))

        score = 50

        if close and sma20:
            score += 14 if close > sma20 else -10

        if close and sma50:
            score += 18 if close > sma50 else -12

        if sma20 and sma50:
            score += 14 if sma20 > sma50 else -10

        if close and ema20:
            score += 10 if close > ema20 else -7

        return round(self.clip(score), 2)

    def momentum_score(self, row) -> float:
        rsi = self.safe(row, "rsi", self.safe(row, "RSI", 50))
        macd = self.safe(row, "macd", self.safe(row, "MACD", 0))
        macd_signal = self.safe(
            row,
            "macd_signal",
            self.safe(row, "MACD_signal", 0)
        )
        change_pct = self.safe(
            row,
            "change_percent",
            self.safe(row, "pct_change", 0)
        )

        score = 50

        if 55 <= rsi <= 68:
            score += 22
        elif 45 <= rsi < 55:
            score += 8
        elif 68 < rsi <= 78:
            score += 10
        elif rsi > 78:
            score -= 10
        elif rsi < 35:
            score -= 15

        if macd > macd_signal:
            score += 14
        elif macd < macd_signal:
            score -= 8

        if change_pct > 0:
            score += min(change_pct * 3, 14)
        elif change_pct < 0:
            score += max(change_pct * 3, -14)

        return round(self.clip(score), 2)

    def volume_score(self, row) -> float:
        volume = self.safe(row, "volume", 0)
        avg_volume = self.safe(
            row,
            "avg_volume",
            self.safe(
                row,
                "volume_avg",
                self.safe(row, "volume_sma_20", 0)
            )
        )

        score = 50

        if volume <= 0:
            return 25

        if avg_volume > 0:
            ratio = volume / avg_volume

            if ratio >= 2:
                score += 30
            elif ratio >= 1.5:
                score += 22
            elif ratio >= 1.1:
                score += 12
            elif ratio < 0.5:
                score -= 18
            elif ratio < 0.8:
                score -= 8
        else:
            if volume >= 1000000:
                score += 22
            elif volume >= 300000:
                score += 14
            elif volume >= 100000:
                score += 6
            else:
                score -= 12

        return round(self.clip(score), 2)

    def liquidity_score(self, row) -> float:
        volume = self.safe(row, "volume", 0)
        close = self.safe(row, "close", self.safe(row, "price", 0))
        value_traded = self.safe(row, "value_traded", volume * close)

        score = 50

        if value_traded >= 100000000:
            score += 35
        elif value_traded >= 50000000:
            score += 25
        elif value_traded >= 20000000:
            score += 15
        elif value_traded >= 5000000:
            score += 5
        elif value_traded < 1000000:
            score -= 25

        if close > 0 and close <= 3:
            score -= 15

        return round(self.clip(score), 2)

    def volatility_score(self, row) -> float:
        atr_pct = self.safe(
            row,
            "atr_percent",
            self.safe(row, "ATR_percent", None)
        )
        beta = self.safe(row, "beta", None)
        high = self.safe(row, "high", 0)
        low = self.safe(row, "low", 0)
        close = self.safe(row, "close", self.safe(row, "price", 0))

        score = 60

        if atr_pct is not None:
            if 1 <= atr_pct <= 5:
                score += 15
            elif 5 < atr_pct <= 8:
                score += 4
            elif atr_pct > 8:
                score -= 18
            elif atr_pct < 1:
                score -= 5
        elif high and low and close:
            intraday = ((high - low) / close) * 100

            if 1 <= intraday <= 5:
                score += 12
            elif intraday > 8:
                score -= 15

        if beta is not None:
            if beta <= 1.3:
                score += 5
            elif beta > 1.8:
                score -= 12

        return round(self.clip(score), 2)

    def market_score(self, row) -> float:
        return round(
            self.clip(self.safe(row, "market_strength_score", 50)),
            2
        )

    def sector_score(self, row) -> float:
        return round(
            self.clip(self.safe(row, "sector_strength_score", 50)),
            2
        )

    def confidence_score(self, row) -> float:
        confidence = self.safe(
            row,
            "confidence_v2",
            self.safe(row, "confidence", 50)
        )
        probability = self.safe(
            row,
            "probability_confidence",
            confidence
        )

        score = confidence * 0.70 + probability * 0.30

        return round(self.clip(score), 2)

    def fundamental_score(self, row) -> float:
        candidates = [
            "long_term_score",
            "fundamental_score",
            "fundamental_score_v2",
            "quality_score",
            "growth_score",
            "value_score",
        ]

        values = []

        for col in candidates:
            value = self.safe(row, col, None)

            if value is not None:
                values.append(value)

        if not values:
            return 50

        return round(self.clip(sum(values) / len(values)), 2)

    def risk_score(self, row) -> float:
        risk_penalty = self.safe(row, "risk_penalty", 0)
        volatility = self.safe(row, "volatility_score_v4", 50)
        liquidity = self.safe(row, "liquidity_score_v4", 50)
        rsi = self.safe(row, "rsi", self.safe(row, "RSI", 50))

        risk = 35

        risk += risk_penalty * 2.5

        if volatility < 40:
            risk += 20

        if liquidity < 35:
            risk += 18

        if rsi > 80:
            risk += 12

        if rsi < 25:
            risk += 10

        return round(self.clip(risk), 2)

    def buy_probability(self, row) -> float:
        score = self.safe(row, "ai_score_v4", 50)
        confidence = self.safe(row, "confidence_score_v4", 50)
        risk = self.safe(row, "risk_score_v4", 50)

        probability = (
            score * 0.70
            + confidence * 0.20
            + (100 - risk) * 0.10
        )

        return round(self.clip(probability), 2)

    def sell_probability(self, row) -> float:
        buy_prob = self.safe(row, "buy_probability", 50)
        risk = self.safe(row, "risk_score_v4", 50)
        trend = self.safe(row, "trend_score_v4", 50)

        probability = (
            (100 - buy_prob) * 0.55
            + risk * 0.30
            + (100 - trend) * 0.15
        )

        return round(self.clip(probability), 2)

    def signal(self, row) -> str:
        score = self.safe(row, "ai_score_v4", 0)
        buy_prob = self.safe(row, "buy_probability", 0)
        risk = self.safe(row, "risk_score_v4", 50)
        liquidity = self.safe(row, "liquidity_score_v4", 50)
        trend = self.safe(row, "trend_score_v4", 50)
        momentum = self.safe(row, "momentum_score_v4", 50)

        if (
            score >= 82
            and buy_prob >= 75
            and risk <= 65
            and liquidity >= 45
            and trend >= 58
        ):
            return "STRONG BUY"

        if (
            score >= 68
            and buy_prob >= 62
            and risk <= 72
            and liquidity >= 38
            and momentum >= 50
        ):
            return "BUY"

        if score >= 52 and buy_prob >= 48:
            return "WATCH"

        if score >= 40:
            return "HOLD"

        if score >= 28:
            return "SELL"

        return "AVOID"

    def risk_level(self, risk_score) -> str:
        if risk_score >= 75:
            return "HIGH"

        if risk_score >= 55:
            return "MEDIUM"

        return "LOW"

    def signal_id(self, row) -> str:
        symbol = str(row.get("symbol", row.get("Symbol", row.name)))
        date = datetime.now().strftime("%Y%m%d")
        raw = f"{symbol}_{date}_{self.VERSION}"

        return hashlib.md5(raw.encode()).hexdigest()[:16]

    @staticmethod
    def safe(row, key, default=0):
        try:
            value = row.get(key, default)
        except Exception:
            return default

        if value is None:
            return default

        try:
            if pd.isna(value):
                return default
        except Exception:
            pass

        try:
            return float(value)
        except Exception:
            return default

    @staticmethod
    def clip(value, low=0, high=100):
        if value is None:
            return 0

        if isinstance(value, float) and math.isnan(value):
            return 0

        return max(low, min(high, value))