import pandas as pd


class EntryTimingEngine:
    """
    Smart Entry Timing Engine V1

    Purpose:
    Decide whether a BUY signal should be executed immediately or delayed.

    Outputs:
    - entry_timing_score
    - entry_timing_action
    - entry_timing_status
    - suggested_entry_type
    - suggested_entry_price
    - entry_timing_reason
    - entry_timing_warning
    """

    def __init__(self):
        self.version = "entry_timing_engine_v1"

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df

        result = df.copy()
        result = self.ensure_columns(result)

        timing = result.apply(
            self.calculate_entry_timing,
            axis=1,
            result_type="expand",
        )

        result = pd.concat([result, timing], axis=1)

        return result

    def calculate_entry_timing(self, row) -> pd.Series:
        score = 50
        reasons = []
        warnings = []

        symbol = text(row, "symbol")
        final_decision = text(row, "final_decision")
        trade_action = text(row, "trade_action")
        trade_status = text(row, "trade_validation_status")
        trend_label = text(row, "trend_label_v5")
        risk_level = text(row, "risk_level")

        close = num(row, "close")
        change_pct = num(row, "change_pct")
        rsi = num(row, "rsi", 50)
        adx = num(row, "adx", 20)
        atr_percent = num(row, "atr_percent", 0)
        close_position = num(row, "close_position", 50)
        position_52w = num(row, "position_52w", 50)

        final_score = num(row, "final_score")
        buy_probability = num(row, "buy_probability")
        sell_probability = num(row, "sell_probability")
        trade_validation_score = num(row, "trade_validation_score", 50)
        risk_reward = num(row, "risk_reward_t1", 1)

        trend_score = num(row, "trend_score_v5", num(row, "trend_score_v4", 50))
        momentum_score = num(row, "momentum_score_v4", num(row, "momentum_strength", 50))
        volume_score = num(row, "volume_score_v4", num(row, "volume_strength", 50))
        liquidity_score = num(row, "liquidity_score_v4", num(row, "liquidity_score_raw", 50))
        market_score = num(row, "market_score_v4", num(row, "market_score", 50))
        sector_score = num(row, "sector_score_v4", num(row, "sector_score", 50))

        volume_ratio_5 = num(row, "volume_ratio_5", 1)
        volume_ratio_20 = num(row, "volume_ratio_20", 1)

        entry_low = num(row, "entry_low", close * 0.985)
        entry_high = num(row, "entry_high", close * 1.01)
        stop_loss = num(row, "stop_loss", close * 0.94)
        target_1 = num(row, "target_1", close * 1.07)

        # Base eligibility
        if final_decision == "STRONG BUY":
            score += 15
            reasons.append("Final decision is STRONG BUY")
        elif final_decision == "BUY":
            score += 10
            reasons.append("Final decision is BUY")
        else:
            score -= 25
            warnings.append("Not a BUY decision")

        if trade_action == "BUY" or trade_status == "VALIDATED BUY":
            score += 12
            reasons.append("Trade validation confirms BUY")
        elif trade_action in ["WATCH", "WAIT"]:
            score -= 8
            warnings.append("Trade validation suggests waiting")
        elif trade_action == "AVOID":
            score -= 25
            warnings.append("Trade validation rejects trade")

        # Strength
        if final_score >= 90:
            score += 10
            reasons.append("Final score above 90")
        elif final_score >= 85:
            score += 7
            reasons.append("Final score above 85")
        elif final_score < 75:
            score -= 10
            warnings.append("Final score not strong enough")

        if buy_probability >= 85:
            score += 8
            reasons.append("Buy probability very strong")
        elif buy_probability >= 78:
            score += 5
            reasons.append("Buy probability strong")
        elif buy_probability < 70:
            score -= 8
            warnings.append("Buy probability weak")

        if sell_probability <= 20:
            score += 5
            reasons.append("Sell pressure low")
        elif sell_probability >= 30:
            score -= 8
            warnings.append("Sell pressure elevated")

        # Trend / momentum / volume
        if trend_score >= 90 or "STRONG UPTREND" in trend_label:
            score += 8
            reasons.append("Strong uptrend")
        elif trend_score < 60:
            score -= 10
            warnings.append("Weak trend")

        if momentum_score >= 85:
            score += 7
            reasons.append("Strong momentum")
        elif momentum_score >= 70:
            score += 4
            reasons.append("Momentum supportive")
        elif momentum_score < 50:
            score -= 8
            warnings.append("Momentum weak")

        if volume_score >= 75 or volume_ratio_20 >= 1.5:
            score += 8
            reasons.append("Volume breakout confirmed")
        elif volume_score >= 60 or volume_ratio_5 >= 1.2:
            score += 5
            reasons.append("Volume supportive")
        else:
            score -= 4
            warnings.append("Volume confirmation weak")

        if liquidity_score >= 80:
            score += 5
            reasons.append("High liquidity")
        elif liquidity_score < 55:
            score -= 8
            warnings.append("Liquidity risk")

        # Market and sector
        if market_score >= 70:
            score += 5
            reasons.append("Market supports entry")
        elif market_score < 50:
            score -= 10
            warnings.append("Market does not support aggressive entry")

        if sector_score >= 75:
            score += 5
            reasons.append("Sector supports entry")
        elif sector_score < 50:
            score -= 7
            warnings.append("Sector weak")

        # Chase / gap risk
        gap_risk = False

        if change_pct >= 9.5:
            score -= 18
            gap_risk = True
            warnings.append("Near upper cap / gap-up risk")
        elif change_pct >= 7:
            score -= 10
            gap_risk = True
            warnings.append("Large daily move; avoid chasing")
        elif change_pct >= 4:
            score -= 4
            warnings.append("Strong daily move; prefer controlled entry")
        elif -1 <= change_pct <= 3:
            score += 5
            reasons.append("Move not overextended")

        # RSI timing
        if rsi >= 82:
            score -= 12
            warnings.append("RSI overheated")
        elif rsi >= 75:
            score -= 7
            warnings.append("RSI high; wait for dip")
        elif 55 <= rsi <= 72:
            score += 7
            reasons.append("RSI healthy for bullish entry")
        elif rsi < 45:
            score -= 6
            warnings.append("RSI weak")

        # Close position
        if close_position >= 85:
            score += 5
            reasons.append("Strong close position")
        elif close_position <= 35:
            score -= 8
            warnings.append("Weak close position")

        # 52 week position
        if position_52w >= 95:
            score -= 8
            warnings.append("Very near 52-week high")
        elif position_52w >= 85:
            score -= 4
            warnings.append("Near 52-week high")
        elif 50 <= position_52w <= 80:
            score += 4
            reasons.append("Healthy 52-week position")

        # ATR volatility
        if atr_percent >= 10:
            score -= 12
            warnings.append("ATR volatility too high")
        elif atr_percent >= 7:
            score -= 6
            warnings.append("High volatility; smaller position")
        elif 2 <= atr_percent <= 6:
            score += 5
            reasons.append("ATR tradable")

        # ADX
        if adx >= 35:
            score += 5
            reasons.append("ADX confirms trend")
        elif adx < 18:
            score -= 5
            warnings.append("ADX weak")

        # Risk reward
        if risk_reward >= 2:
            score += 8
            reasons.append("Good risk/reward")
        elif risk_reward >= 1.5:
            score += 4
            reasons.append("Acceptable risk/reward")
        elif risk_reward > 0:
            score -= 6
            warnings.append("Risk/reward weak")

        # Risk level
        if risk_level == "LOW":
            score += 4
            reasons.append("Low risk stock")
        elif risk_level == "HIGH":
            score -= 8
            warnings.append("High risk stock")
        elif risk_level in ["VERY HIGH", "EXTREME"]:
            score -= 18
            warnings.append("Very high risk stock")

        score = round(max(min(score, 100), 0), 2)

        action, status, entry_type, suggested_price = self.decide_action(
            score=score,
            close=close,
            change_pct=change_pct,
            rsi=rsi,
            gap_risk=gap_risk,
            entry_low=entry_low,
            entry_high=entry_high,
            stop_loss=stop_loss,
            target_1=target_1,
            final_decision=final_decision,
            trade_action=trade_action,
        )

        return pd.Series({
            "entry_timing_score": score,
            "entry_timing_action": action,
            "entry_timing_status": status,
            "suggested_entry_type": entry_type,
            "suggested_entry_price": round(suggested_price, 2) if suggested_price > 0 else 0,
            "entry_timing_reason": " | ".join(reasons),
            "entry_timing_warning": " | ".join(warnings),
            "entry_timing_engine_version": self.version,
        })

    def decide_action(
        self,
        score: float,
        close: float,
        change_pct: float,
        rsi: float,
        gap_risk: bool,
        entry_low: float,
        entry_high: float,
        stop_loss: float,
        target_1: float,
        final_decision: str,
        trade_action: str,
    ):
        if final_decision not in ["STRONG BUY", "BUY"] or trade_action == "AVOID":
            return "NO TRADE", "REJECTED", "NONE", 0

        if score >= 85 and not gap_risk and rsi < 75:
            return "BUY NOW", "HIGH CONVICTION ENTRY", "MARKET / CONTROLLED", entry_high

        if score >= 78 and not gap_risk:
            return "BUY ON DIP", "GOOD SETUP - WAIT DIP", "DIP ENTRY", entry_low

        if score >= 72 and gap_risk:
            dip_price = min(entry_low, close * 0.985)
            return "WAIT PULLBACK", "AVOID CHASING", "PULLBACK ENTRY", dip_price

        if score >= 65:
            breakout_price = max(entry_high, close * 1.015)
            return "BUY ABOVE BREAKOUT", "CONFIRMATION REQUIRED", "BREAKOUT ENTRY", breakout_price

        if score >= 55:
            return "WATCH ONLY", "WAIT", "WATCHLIST", entry_low

        return "NO TRADE", "REJECTED", "NONE", 0

    def ensure_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        defaults = {
            "symbol": "",
            "company": "",
            "sector": "UNKNOWN",
            "close": 0,
            "change_pct": 0,
            "rsi": 50,
            "adx": 20,
            "atr_percent": 0,
            "close_position": 50,
            "position_52w": 50,
            "final_score": 0,
            "final_decision": "",
            "buy_probability": 0,
            "sell_probability": 100,
            "trade_validation_score": 50,
            "trade_validation_status": "",
            "trade_action": "",
            "risk_reward_t1": 1,
            "trend_score_v4": 50,
            "trend_score_v5": 50,
            "trend_label_v5": "",
            "momentum_score_v4": 50,
            "momentum_strength": 50,
            "volume_score_v4": 50,
            "volume_strength": 50,
            "liquidity_score_v4": 50,
            "liquidity_score_raw": 50,
            "market_score_v4": 50,
            "market_score": 50,
            "sector_score_v4": 50,
            "sector_score": 50,
            "volume_ratio_5": 1,
            "volume_ratio_20": 1,
            "entry_low": 0,
            "entry_high": 0,
            "stop_loss": 0,
            "target_1": 0,
            "risk_level": "MEDIUM",
        }

        for col, default in defaults.items():
            if col not in df.columns:
                df[col] = default

        return df


def apply_entry_timing(df: pd.DataFrame) -> pd.DataFrame:
    engine = EntryTimingEngine()
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