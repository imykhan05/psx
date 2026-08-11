import pandas as pd


class TradeValidationEngine:
    """
    Trade Validation Engine V1

    Purpose:
    Validate AI BUY signals before they enter Portfolio Engine.

    It checks:
    - final_score quality
    - buy probability
    - sell probability risk
    - trend strength
    - liquidity
    - volume confirmation
    - RSI overheating
    - ATR / volatility risk
    - risk reward
    - sector and market strength
    """

    def __init__(self):
        self.version = "trade_validation_engine_v1"

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df

        result = df.copy()
        result = self.ensure_columns(result)

        validation = result.apply(
            self.validate_row,
            axis=1,
            result_type="expand",
        )

        result = pd.concat([result, validation], axis=1)

        return result

    def validate_row(self, row) -> pd.Series:
        score = 50
        reasons = []
        warnings = []

        final_decision = text(row, "final_decision")
        verdict = text(row, "verdict")
        trend_label = text(row, "trend_label_v5")
        risk_level = text(row, "risk_level")
        sector = text(row, "sector")

        final_score = num(row, "final_score")
        buy_probability = num(row, "buy_probability")
        sell_probability = num(row, "sell_probability")
        ai_score = num(row, "ai_score")
        confidence = num(row, "confidence_v3", num(row, "confidence", 50))

        trend_score = num(row, "trend_score_v5", num(row, "trend_score_v4"))
        momentum_score = num(row, "momentum_score_v4", num(row, "momentum_strength", 50))
        volume_score = num(row, "volume_score_v4", num(row, "volume_strength", 50))
        liquidity_score = num(row, "liquidity_score_v4", num(row, "liquidity_score_raw", 50))
        market_score = num(row, "market_score_v4", num(row, "market_score", 50))
        sector_score = num(row, "sector_score_v4", num(row, "sector_score", 50))

        rsi = num(row, "rsi", 50)
        adx = num(row, "adx", 20)
        atr_percent = num(row, "atr_percent", 0)
        close_position = num(row, "close_position", 50)
        position_52w = num(row, "position_52w", 50)

        volume_ratio_5 = num(row, "volume_ratio_5", 1)
        volume_ratio_20 = num(row, "volume_ratio_20", 1)

        close = num(row, "close")
        entry_high = num(row, "entry_high", close)
        stop_loss = num(row, "stop_loss", close * 0.94)
        target_1 = num(row, "target_1", close * 1.07)

        # Base decision check
        if final_decision == "STRONG BUY":
            score += 18
            reasons.append("AI final decision is STRONG BUY")
        elif final_decision == "BUY":
            score += 12
            reasons.append("AI final decision is BUY")
        elif "BUY" in verdict:
            score += 8
            reasons.append("AI verdict supports BUY")
        else:
            score -= 25
            warnings.append("AI decision is not BUY")

        # Final score quality
        if final_score >= 90:
            score += 14
            reasons.append("Final score above 90")
        elif final_score >= 85:
            score += 10
            reasons.append("Final score above 85")
        elif final_score >= 80:
            score += 6
            reasons.append("Final score above 80")
        elif final_score < 70:
            score -= 18
            warnings.append("Final score below trade threshold")

        # Probability
        if buy_probability >= 85:
            score += 12
            reasons.append("Buy probability very strong")
        elif buy_probability >= 78:
            score += 8
            reasons.append("Buy probability strong")
        elif buy_probability < 65:
            score -= 12
            warnings.append("Buy probability weak")

        if sell_probability <= 20:
            score += 8
            reasons.append("Sell probability low")
        elif sell_probability >= 35:
            score -= 10
            warnings.append("Sell probability elevated")

        # Trend
        if trend_score >= 90 or "STRONG UPTREND" in trend_label:
            score += 12
            reasons.append("Strong uptrend confirmed")
        elif trend_score >= 75:
            score += 7
            reasons.append("Uptrend confirmed")
        elif trend_score < 55:
            score -= 15
            warnings.append("Trend not strong enough")

        # Momentum
        if momentum_score >= 85:
            score += 8
            reasons.append("Momentum very strong")
        elif momentum_score >= 70:
            score += 5
            reasons.append("Momentum supportive")
        elif momentum_score < 50:
            score -= 8
            warnings.append("Momentum weak")

        # Volume
        if volume_score >= 75 or volume_ratio_20 >= 1.5:
            score += 8
            reasons.append("Volume confirms move")
        elif volume_score >= 60 or volume_ratio_5 >= 1.2:
            score += 5
            reasons.append("Volume supportive")
        elif volume_score < 45 and volume_ratio_20 < 0.8:
            score -= 8
            warnings.append("Weak volume confirmation")

        # Liquidity
        if liquidity_score >= 80:
            score += 8
            reasons.append("High liquidity")
        elif liquidity_score >= 65:
            score += 5
            reasons.append("Good liquidity")
        elif liquidity_score < 55:
            score -= 12
            warnings.append("Low liquidity risk")

        # Market / sector
        if market_score >= 75:
            score += 6
            reasons.append("Market condition supportive")
        elif market_score < 45:
            score -= 12
            warnings.append("Market condition weak")

        if sector_score >= 75:
            score += 6
            reasons.append("Sector strength supportive")
        elif sector_score < 45:
            score -= 8
            warnings.append("Sector strength weak")

        # RSI overheating
        if rsi >= 85:
            score -= 10
            warnings.append("RSI overheated")
        elif rsi >= 75:
            score -= 4
            warnings.append("RSI high, avoid chasing")
        elif 55 <= rsi <= 72:
            score += 5
            reasons.append("RSI in healthy bullish zone")

        # ADX
        if adx >= 35:
            score += 6
            reasons.append("ADX confirms strong trend")
        elif adx < 18:
            score -= 5
            warnings.append("ADX trend strength weak")

        # ATR / volatility
        if atr_percent > 12:
            score -= 12
            warnings.append("Very high volatility risk")
        elif atr_percent > 8:
            score -= 6
            warnings.append("High volatility; use smaller position")
        elif 2 <= atr_percent <= 6:
            score += 5
            reasons.append("ATR volatility is tradable")

        # Close position / 52W position
        if close_position >= 80:
            score += 5
            reasons.append("Strong close near day/range high")
        elif close_position < 35:
            score -= 6
            warnings.append("Weak close position")

        if position_52w >= 90:
            score -= 4
            warnings.append("Near 52-week high, chase risk")
        elif 55 <= position_52w <= 85:
            score += 4
            reasons.append("Healthy 52-week positioning")

        # Risk level
        if risk_level == "LOW":
            score += 6
            reasons.append("Low risk level")
        elif risk_level == "MEDIUM":
            score += 2
        elif risk_level == "HIGH":
            score -= 8
            warnings.append("High risk level")
        elif risk_level in ["VERY HIGH", "EXTREME"]:
            score -= 18
            warnings.append("Very high risk level")

        # Unknown sector
        if sector in ["UNKNOWN", "", "NAN"]:
            score -= 4
            warnings.append("Sector metadata missing")

        # Risk reward
        rr = self.risk_reward(entry_high, stop_loss, target_1)

        if rr >= 2.0:
            score += 8
            reasons.append("Risk/reward above 2.0")
        elif rr >= 1.5:
            score += 5
            reasons.append("Risk/reward acceptable")
        elif rr > 0:
            score -= 8
            warnings.append("Risk/reward weak")

        # Confidence
        if confidence >= 90:
            score += 6
            reasons.append("Very high confidence")
        elif confidence < 60:
            score -= 8
            warnings.append("Confidence weak")

        # Cap score
        score = round(max(min(score, 100), 0), 2)

        if score >= 85:
            status = "VALIDATED BUY"
            action = "BUY"
        elif score >= 75:
            status = "BUY ON PULLBACK"
            action = "WAIT / BUY DIP"
        elif score >= 65:
            status = "WATCHLIST"
            action = "WATCH"
        elif score >= 50:
            status = "WEAK SETUP"
            action = "WAIT"
        else:
            status = "REJECTED"
            action = "AVOID"

        return pd.Series({
            "trade_validation_score": score,
            "trade_validation_status": status,
            "trade_action": action,
            "risk_reward_t1": round(rr, 2),
            "validation_reasons": " | ".join(reasons),
            "validation_warnings": " | ".join(warnings),
            "validation_engine_version": self.version,
        })

    def risk_reward(self, entry_high: float, stop_loss: float, target_1: float) -> float:
        try:
            risk = entry_high - stop_loss
            reward = target_1 - entry_high

            if risk <= 0:
                return 0

            return reward / risk
        except Exception:
            return 0

    def ensure_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        defaults = {
            "symbol": "",
            "company": "",
            "sector": "UNKNOWN",
            "final_decision": "",
            "verdict": "",
            "final_score": 0,
            "buy_probability": 0,
            "sell_probability": 100,
            "ai_score": 0,
            "confidence": 50,
            "confidence_v3": 50,
            "trend_score_v4": 0,
            "trend_score_v5": 0,
            "trend_label_v5": "",
            "momentum_score_v4": 50,
            "volume_score_v4": 50,
            "liquidity_score_v4": 50,
            "market_score_v4": 50,
            "sector_score_v4": 50,
            "risk_level": "MEDIUM",
            "rsi": 50,
            "adx": 20,
            "atr_percent": 0,
            "close_position": 50,
            "position_52w": 50,
            "volume_ratio_5": 1,
            "volume_ratio_20": 1,
            "close": 0,
            "entry_high": 0,
            "stop_loss": 0,
            "target_1": 0,
        }

        for col, default in defaults.items():
            if col not in df.columns:
                df[col] = default

        return df


def apply_trade_validation(df: pd.DataFrame) -> pd.DataFrame:
    engine = TradeValidationEngine()
    return engine.apply(df)


def num(row, key: str, default: float = 0) -> float:
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


def text(row, key: str, default: str = "") -> str:
    value = row.get(key, default)

    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    return str(value).strip().upper()