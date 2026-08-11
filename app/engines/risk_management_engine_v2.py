import pandas as pd


class RiskManagementEngineV2:
    """
    Risk Management Engine V2

    Purpose:
    Convert AI/Validation/Entry signals into final risk-controlled trade permission.

    It controls:
    - weak risk/reward
    - gap-up / upper cap chase risk
    - RSI overheat risk
    - ATR volatility risk
    - low liquidity risk
    - market / sector risk
    - stop loss distance
    - final trade permission
    """

    def __init__(self):
        self.version = "risk_management_engine_v2"

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df

        result = df.copy()
        result = self.ensure_columns(result)

        risk = result.apply(
            self.evaluate_risk,
            axis=1,
            result_type="expand",
        )

        result = pd.concat([result, risk], axis=1)

        return result

    def evaluate_risk(self, row) -> pd.Series:
        score = 100
        reasons = []
        warnings = []

        final_decision = text(row, "final_decision")
        trade_action = text(row, "trade_action")
        entry_action = text(row, "entry_timing_action")
        entry_status = text(row, "entry_timing_status")
        risk_level = text(row, "risk_level")
        sector = text(row, "sector")

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
        entry_timing_score = num(row, "entry_timing_score", 50)
        risk_reward = num(row, "risk_reward_t1", 0)

        liquidity_score = num(row, "liquidity_score_v4", num(row, "liquidity_score_raw", 50))
        market_score = num(row, "market_score_v4", num(row, "market_score", 50))
        sector_score = num(row, "sector_score_v4", num(row, "sector_score", 50))
        volume_score = num(row, "volume_score_v4", num(row, "volume_strength", 50))
        momentum_score = num(row, "momentum_score_v4", num(row, "momentum_strength", 50))

        entry_high = num(row, "entry_high", close)
        entry_low = num(row, "entry_low", close)
        stop_loss = num(row, "stop_loss", close * 0.94)
        target_1 = num(row, "target_1", close * 1.07)
        target_2 = num(row, "target_2", close * 1.12)

        hard_reject = False

        # Basic AI permission
        if final_decision not in ["STRONG BUY", "BUY"]:
            score -= 35
            warnings.append("AI final decision is not BUY")
            hard_reject = True
        else:
            reasons.append("AI decision supports trade")

        if trade_action == "AVOID":
            score -= 35
            warnings.append("Trade validation says AVOID")
            hard_reject = True
        elif trade_action in ["WAIT", "WATCH"]:
            score -= 15
            warnings.append("Trade validation is not immediate BUY")
        else:
            reasons.append("Trade validation supports entry")

        # Risk reward
        if risk_reward >= 2.0:
            score += 5
            reasons.append("Risk/reward strong")
        elif risk_reward >= 1.5:
            score -= 5
            warnings.append("Risk/reward acceptable but not ideal")
        elif risk_reward > 0:
            score -= 22
            warnings.append("Risk/reward weak")
        else:
            score -= 30
            warnings.append("Risk/reward invalid")
            hard_reject = True

        # Gap / upper cap risk
        if change_pct >= 9.5:
            score -= 28
            warnings.append("Near upper cap / gap-up chase risk")
        elif change_pct >= 7:
            score -= 18
            warnings.append("Large move; wait pullback")
        elif change_pct >= 4:
            score -= 8
            warnings.append("Strong move; controlled entry only")
        elif change_pct < -3:
            score -= 10
            warnings.append("Weak daily price action")

        # RSI
        if rsi >= 85:
            score -= 18
            warnings.append("RSI extremely overheated")
        elif rsi >= 75:
            score -= 12
            warnings.append("RSI overbought")
        elif 55 <= rsi <= 72:
            score += 4
            reasons.append("RSI healthy")
        elif rsi < 45:
            score -= 8
            warnings.append("RSI weak")

        # ATR / volatility
        if atr_percent >= 12:
            score -= 25
            warnings.append("ATR volatility extreme")
            hard_reject = True
        elif atr_percent >= 9:
            score -= 18
            warnings.append("ATR volatility very high")
        elif atr_percent >= 7:
            score -= 10
            warnings.append("ATR volatility high")
        elif 2 <= atr_percent <= 6:
            score += 3
            reasons.append("ATR tradable")

        # Stop loss distance
        stop_distance_pct = self.stop_distance_pct(entry_high, stop_loss)

        if stop_distance_pct <= 0:
            score -= 25
            warnings.append("Invalid stop loss")
            hard_reject = True
        elif stop_distance_pct > 12:
            score -= 18
            warnings.append("Stop loss too wide")
        elif stop_distance_pct > 8:
            score -= 10
            warnings.append("Stop loss wide")
        elif 3 <= stop_distance_pct <= 7:
            score += 4
            reasons.append("Stop distance healthy")

        # Liquidity
        if liquidity_score >= 80:
            score += 4
            reasons.append("Liquidity strong")
        elif liquidity_score < 55:
            score -= 16
            warnings.append("Liquidity weak")
        elif liquidity_score < 65:
            score -= 7
            warnings.append("Liquidity moderate")

        # Market and sector
        if market_score >= 75:
            score += 4
            reasons.append("Market supports risk")
        elif market_score < 50:
            score -= 15
            warnings.append("Market risk weak")

        if sector_score >= 75:
            score += 4
            reasons.append("Sector supports risk")
        elif sector_score < 50:
            score -= 12
            warnings.append("Sector risk weak")

        # Momentum/volume
        if momentum_score >= 80:
            score += 3
            reasons.append("Momentum strong")
        elif momentum_score < 55:
            score -= 8
            warnings.append("Momentum weak")

        if volume_score >= 75:
            score += 3
            reasons.append("Volume strong")
        elif volume_score < 50:
            score -= 8
            warnings.append("Volume weak")

        # 52-week / close position
        if position_52w >= 95:
            score -= 12
            warnings.append("Very near 52-week high")
        elif position_52w >= 88:
            score -= 7
            warnings.append("Near 52-week high")
        elif 50 <= position_52w <= 80:
            score += 3
            reasons.append("52-week position healthy")

        if close_position < 35:
            score -= 8
            warnings.append("Weak close position")
        elif close_position >= 80:
            score += 3
            reasons.append("Strong close position")

        # Entry timing
        if entry_action == "BUY NOW":
            score += 4
            reasons.append("Entry timing says BUY NOW")
        elif entry_action in ["WAIT PULLBACK", "BUY ON DIP"]:
            score -= 6
            warnings.append("Entry timing suggests waiting")
        elif entry_action in ["NO TRADE", "WATCH ONLY"]:
            score -= 18
            warnings.append("Entry timing does not approve immediate trade")

        if entry_timing_score < 65:
            score -= 12
            warnings.append("Entry timing score weak")

        # Final score / probability sanity
        if final_score < 78:
            score -= 12
            warnings.append("Final score below risk threshold")

        if buy_probability < 75:
            score -= 12
            warnings.append("Buy probability below risk threshold")

        if sell_probability > 35:
            score -= 12
            warnings.append("Sell probability too high")

        if trade_validation_score < 70:
            score -= 15
            warnings.append("Trade validation score weak")

        # Sector metadata
        if sector in ["UNKNOWN", "", "NAN"]:
            score -= 3
            warnings.append("Sector metadata missing")

        # Cap score
        score = round(max(min(score, 100), 0), 2)

        permission, risk_status, risk_action = self.decide_permission(
            score=score,
            hard_reject=hard_reject,
            risk_reward=risk_reward,
            change_pct=change_pct,
            rsi=rsi,
            atr_percent=atr_percent,
            entry_action=entry_action,
            final_decision=final_decision,
        )

        position_risk_factor = self.position_risk_factor(score, atr_percent, risk_reward, change_pct, rsi)

        adjusted_entry_price = self.adjusted_entry_price(
            entry_action=entry_action,
            entry_low=entry_low,
            entry_high=entry_high,
            close=close,
            change_pct=change_pct,
            rsi=rsi,
        )

        return pd.Series({
            "risk_management_score": score,
            "risk_permission": permission,
            "risk_status": risk_status,
            "risk_action": risk_action,
            "position_risk_factor": round(position_risk_factor, 2),
            "adjusted_entry_price": round(adjusted_entry_price, 2),
            "stop_distance_pct": round(stop_distance_pct, 2),
            "risk_management_reasons": " | ".join(reasons),
            "risk_management_warnings": " | ".join(warnings),
            "risk_engine_version": self.version,
        })

    def decide_permission(
        self,
        score: float,
        hard_reject: bool,
        risk_reward: float,
        change_pct: float,
        rsi: float,
        atr_percent: float,
        entry_action: str,
        final_decision: str,
    ):
        if hard_reject:
            return "NO TRADE", "REJECTED", "AVOID"

        if final_decision not in ["STRONG BUY", "BUY"]:
            return "NO TRADE", "REJECTED", "AVOID"

        if atr_percent >= 12:
            return "NO TRADE", "VOLATILITY REJECTED", "AVOID"

        if risk_reward > 0 and risk_reward < 1.15:
            if score >= 75 and entry_action in ["WAIT PULLBACK", "BUY ON DIP"]:
                return "WAIT", "RISK/REWARD WEAK", "WAIT FOR BETTER ENTRY"
            return "NO TRADE", "RISK/REWARD REJECTED", "AVOID"

        if change_pct >= 9.5 or rsi >= 82:
            if score >= 70:
                return "WAIT", "CHASE RISK", "WAIT PULLBACK"
            return "NO TRADE", "CHASE RISK REJECTED", "AVOID"

        if entry_action in ["WAIT PULLBACK", "BUY ON DIP"]:
            if score >= 70:
                return "WAIT", "ENTRY WAIT", "WAIT PULLBACK"

        if score >= 82:
            return "TRADE ALLOWED", "LOW RISK", "BUY"

        if score >= 72:
            return "TRADE ALLOWED SMALL", "CONTROLLED RISK", "BUY SMALL"

        if score >= 60:
            return "WAIT", "MEDIUM RISK", "WATCH / WAIT"

        return "NO TRADE", "HIGH RISK", "AVOID"

    def position_risk_factor(
        self,
        score: float,
        atr_percent: float,
        risk_reward: float,
        change_pct: float,
        rsi: float,
    ) -> float:
        factor = 1.0

        if score >= 90:
            factor += 0.20
        elif score >= 82:
            factor += 0.10
        elif score < 72:
            factor -= 0.25

        if risk_reward >= 2:
            factor += 0.20
        elif risk_reward < 1.2:
            factor -= 0.20

        if atr_percent >= 8:
            factor -= 0.20
        elif 2 <= atr_percent <= 5:
            factor += 0.05

        if change_pct >= 7:
            factor -= 0.20

        if rsi >= 75:
            factor -= 0.15

        return max(min(factor, 1.4), 0.30)

    def adjusted_entry_price(
        self,
        entry_action: str,
        entry_low: float,
        entry_high: float,
        close: float,
        change_pct: float,
        rsi: float,
    ) -> float:
        if entry_action in ["WAIT PULLBACK", "BUY ON DIP"]:
            return entry_low

        if change_pct >= 7 or rsi >= 75:
            return entry_low

        if entry_high > 0:
            return entry_high

        return close

    def stop_distance_pct(self, entry_high: float, stop_loss: float) -> float:
        try:
            if entry_high <= 0:
                return 0

            return ((entry_high - stop_loss) / entry_high) * 100
        except Exception:
            return 0

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
            "entry_timing_score": 50,
            "entry_timing_action": "",
            "entry_timing_status": "",
            "risk_reward_t1": 0,
            "liquidity_score_v4": 50,
            "liquidity_score_raw": 50,
            "market_score_v4": 50,
            "market_score": 50,
            "sector_score_v4": 50,
            "sector_score": 50,
            "volume_score_v4": 50,
            "volume_strength": 50,
            "momentum_score_v4": 50,
            "momentum_strength": 50,
            "risk_level": "MEDIUM",
            "entry_low": 0,
            "entry_high": 0,
            "stop_loss": 0,
            "target_1": 0,
            "target_2": 0,
        }

        for col, default in defaults.items():
            if col not in df.columns:
                df[col] = default

        return df


def apply_risk_management_v2(df: pd.DataFrame) -> pd.DataFrame:
    engine = RiskManagementEngineV2()
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