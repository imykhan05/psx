import pandas as pd


class InstitutionalSmartMoneyEngine:
    """
    Institutional Smart Money Engine V1

    Purpose:
    Detect accumulation, distribution, hidden buying/selling,
    volume breakout, false breakout, Wyckoff phase, and smart money flow.

    This engine is safe and additive:
    It does not remove existing columns.
    It only adds new institutional columns.
    """

    def __init__(self):
        self.version = "institutional_smart_money_engine_v1"

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df

        result = df.copy()
        result = self.ensure_columns(result)

        institutional = result.apply(
            self.calculate_smart_money,
            axis=1,
            result_type="expand",
        )

        result = pd.concat([result, institutional], axis=1)

        return result

    def calculate_smart_money(self, row) -> pd.Series:
        close = num(row, "close")
        open_price = num(row, "open", close)
        high = num(row, "high", close)
        low = num(row, "low", close)

        change_pct = num(row, "change_pct")
        volume = num(row, "volume")
        value_traded = num(row, "value_traded")
        volume_ratio_5 = num(row, "volume_ratio_5", 1)
        volume_ratio_20 = num(row, "volume_ratio_20", 1)

        rsi = num(row, "rsi", 50)
        adx = num(row, "adx", 20)
        atr_percent = num(row, "atr_percent", 0)
        macd_hist = num(row, "macd_hist", 0)

        close_position = num(row, "close_position", 50)
        position_52w = num(row, "position_52w", 50)

        ema20 = num(row, "ema_20")
        ema50 = num(row, "ema_50")
        ema100 = num(row, "ema_100")
        ema200 = num(row, "ema_200")

        liquidity_score = num(row, "liquidity_score_v4", num(row, "liquidity_score_raw", 50))
        trend_score = num(row, "trend_score_v5", num(row, "trend_score_v4", num(row, "trend_strength", 50)))
        momentum_score = num(row, "momentum_score_v4", num(row, "momentum_strength", 50))
        volume_score = num(row, "volume_score_v4", num(row, "volume_strength", 50))

        body_pct = self.body_percent(open_price, close, high, low)
        upper_wick_pct = self.upper_wick_percent(open_price, close, high, low)
        lower_wick_pct = self.lower_wick_percent(open_price, close, high, low)

        accumulation_score = 40
        distribution_score = 25
        smart_money_score = 45

        reasons = []
        warnings = []

        # Volume participation
        if volume_ratio_20 >= 2.5 and change_pct > 0:
            accumulation_score += 18
            smart_money_score += 14
            reasons.append("Strong volume expansion with positive price action")
        elif volume_ratio_20 >= 1.5 and change_pct > 0:
            accumulation_score += 12
            smart_money_score += 9
            reasons.append("Volume accumulation detected")
        elif volume_ratio_20 >= 2.0 and change_pct < 0:
            distribution_score += 18
            smart_money_score -= 8
            warnings.append("High volume selling pressure")

        # Close strength
        if close_position >= 85:
            accumulation_score += 12
            smart_money_score += 8
            reasons.append("Strong close near high")
        elif close_position <= 25:
            distribution_score += 12
            smart_money_score -= 8
            warnings.append("Weak close near low")

        # Candle structure
        if lower_wick_pct >= 35 and close_position >= 65:
            accumulation_score += 10
            smart_money_score += 8
            reasons.append("Lower wick absorption / buying support")

        if upper_wick_pct >= 35 and close_position <= 60:
            distribution_score += 10
            smart_money_score -= 7
            warnings.append("Upper wick supply / selling pressure")

        # Trend alignment
        price_above_ema20 = close > ema20 if close > 0 and ema20 > 0 else False
        price_above_ema50 = close > ema50 if close > 0 and ema50 > 0 else False
        ema20_above_ema50 = ema20 > ema50 if ema20 > 0 and ema50 > 0 else False
        ema50_above_ema100 = ema50 > ema100 if ema50 > 0 and ema100 > 0 else False
        ema100_above_ema200 = ema100 > ema200 if ema100 > 0 and ema200 > 0 else False

        if price_above_ema20 and price_above_ema50 and ema20_above_ema50:
            accumulation_score += 10
            smart_money_score += 8
            reasons.append("Institutional trend alignment")

        if ema20_above_ema50 and ema50_above_ema100 and ema100_above_ema200:
            smart_money_score += 6
            reasons.append("Multi-EMA bullish structure")

        # Momentum confirmation
        if trend_score >= 85 and momentum_score >= 75:
            smart_money_score += 10
            accumulation_score += 8
            reasons.append("Trend and momentum confirm institutional flow")
        elif trend_score < 50 and momentum_score < 50:
            smart_money_score -= 10
            distribution_score += 8
            warnings.append("Trend and momentum weak")

        # MACD confirmation
        if macd_hist > 0 and change_pct > 0:
            smart_money_score += 5
            accumulation_score += 5
            reasons.append("MACD histogram supports buying")
        elif macd_hist < 0 and change_pct < 0:
            smart_money_score -= 5
            distribution_score += 5
            warnings.append("MACD histogram supports selling")

        # Breakout confirmation
        breakout_confirmation = False
        false_breakout = False

        if position_52w >= 80 and volume_ratio_20 >= 1.5 and close_position >= 75 and change_pct > 0:
            breakout_confirmation = True
            accumulation_score += 12
            smart_money_score += 10
            reasons.append("Breakout confirmation with volume")

        if position_52w >= 90 and upper_wick_pct >= 30 and close_position < 65:
            false_breakout = True
            distribution_score += 14
            smart_money_score -= 12
            warnings.append("Possible false breakout / upthrust")

        # Hidden buying / selling
        hidden_buying = False
        hidden_selling = False

        if change_pct <= 1.5 and volume_ratio_20 >= 1.4 and close_position >= 65 and lower_wick_pct >= 20:
            hidden_buying = True
            accumulation_score += 14
            smart_money_score += 12
            reasons.append("Hidden buying / absorption detected")

        if change_pct >= -1 and volume_ratio_20 >= 1.4 and close_position <= 45 and upper_wick_pct >= 25:
            hidden_selling = True
            distribution_score += 14
            smart_money_score -= 10
            warnings.append("Hidden selling / supply detected")

        # Exhaustion
        demand_exhaustion = False
        supply_exhaustion = False

        if rsi >= 80 and change_pct >= 7 and upper_wick_pct >= 20:
            demand_exhaustion = True
            distribution_score += 12
            smart_money_score -= 12
            warnings.append("Demand exhaustion risk")

        if rsi <= 35 and change_pct <= -5 and lower_wick_pct >= 25:
            supply_exhaustion = True
            accumulation_score += 10
            smart_money_score += 8
            reasons.append("Supply exhaustion / possible reversal")

        # Wyckoff style phase
        wyckoff_phase = self.detect_wyckoff_phase(
            accumulation_score=accumulation_score,
            distribution_score=distribution_score,
            trend_score=trend_score,
            volume_ratio_20=volume_ratio_20,
            close_position=close_position,
            change_pct=change_pct,
            rsi=rsi,
            breakout_confirmation=breakout_confirmation,
            false_breakout=false_breakout,
            hidden_buying=hidden_buying,
            hidden_selling=hidden_selling,
        )

        # Liquidity/value traded
        if liquidity_score >= 80 and value_traded > 0:
            smart_money_score += 6
            reasons.append("Liquid enough for institutional activity")
        elif liquidity_score < 55:
            smart_money_score -= 8
            warnings.append("Liquidity weak for institutional quality")

        # ATR stability
        if atr_percent >= 12:
            smart_money_score -= 10
            warnings.append("Very high volatility reduces institutional quality")
        elif 2 <= atr_percent <= 6:
            smart_money_score += 5
            reasons.append("Volatility is tradable")

        # Clamp scores
        accumulation_score = round(max(min(accumulation_score, 100), 0), 2)
        distribution_score = round(max(min(distribution_score, 100), 0), 2)
        smart_money_score = round(max(min(smart_money_score, 100), 0), 2)

        institutional_buy_probability = self.buy_probability(
            smart_money_score,
            accumulation_score,
            distribution_score,
            breakout_confirmation,
            hidden_buying,
        )

        institutional_sell_probability = self.sell_probability(
            smart_money_score,
            accumulation_score,
            distribution_score,
            false_breakout,
            hidden_selling,
            demand_exhaustion,
        )

        institutional_signal = self.signal(
            smart_money_score,
            accumulation_score,
            distribution_score,
            institutional_buy_probability,
            institutional_sell_probability,
            wyckoff_phase,
        )

        delivery_strength = self.delivery_strength(
            volume_ratio_20,
            value_traded,
            liquidity_score,
            close_position,
            change_pct,
        )

        volume_climax = volume_ratio_20 >= 2.5
        dry_volume = volume_ratio_20 <= 0.55 and volume_ratio_5 <= 0.65

        price_volume_divergence = self.price_volume_divergence(
            change_pct,
            volume_ratio_20,
            close_position,
        )

        spring_detection = (
            lower_wick_pct >= 35
            and close_position >= 65
            and rsi <= 55
            and volume_ratio_20 >= 1.2
        )

        upthrust_detection = (
            upper_wick_pct >= 35
            and close_position <= 60
            and position_52w >= 75
            and volume_ratio_20 >= 1.2
        )

        return pd.Series({
            "smart_money_score": smart_money_score,
            "accumulation_score": accumulation_score,
            "distribution_score": distribution_score,
            "delivery_strength": delivery_strength,
            "price_volume_divergence": price_volume_divergence,
            "volume_climax": volume_climax,
            "dry_volume": dry_volume,
            "breakout_confirmation": breakout_confirmation,
            "false_breakout_detection": false_breakout,
            "hidden_buying": hidden_buying,
            "hidden_selling": hidden_selling,
            "wyckoff_phase": wyckoff_phase,
            "spring_detection": spring_detection,
            "upthrust_detection": upthrust_detection,
            "demand_exhaustion": demand_exhaustion,
            "supply_exhaustion": supply_exhaustion,
            "institutional_signal": institutional_signal,
            "institutional_buy_probability": institutional_buy_probability,
            "institutional_sell_probability": institutional_sell_probability,
            "institutional_reasons": " | ".join(reasons),
            "institutional_warnings": " | ".join(warnings),
            "institutional_engine_version": self.version,
        })

    def body_percent(self, open_price, close, high, low) -> float:
        rng = high - low
        if rng <= 0:
            return 0
        return abs(close - open_price) / rng * 100

    def upper_wick_percent(self, open_price, close, high, low) -> float:
        rng = high - low
        if rng <= 0:
            return 0
        upper_body = max(open_price, close)
        return max(high - upper_body, 0) / rng * 100

    def lower_wick_percent(self, open_price, close, high, low) -> float:
        rng = high - low
        if rng <= 0:
            return 0
        lower_body = min(open_price, close)
        return max(lower_body - low, 0) / rng * 100

    def detect_wyckoff_phase(
        self,
        accumulation_score,
        distribution_score,
        trend_score,
        volume_ratio_20,
        close_position,
        change_pct,
        rsi,
        breakout_confirmation,
        false_breakout,
        hidden_buying,
        hidden_selling,
    ) -> str:
        if false_breakout or hidden_selling:
            return "DISTRIBUTION / UPTHRUST"

        if breakout_confirmation and trend_score >= 75:
            return "MARKUP / BREAKOUT"

        if hidden_buying or (accumulation_score >= 70 and close_position >= 60):
            return "ACCUMULATION"

        if distribution_score >= 65:
            return "DISTRIBUTION"

        if trend_score >= 75 and change_pct > 0:
            return "MARKUP"

        if trend_score < 45 and change_pct < 0:
            return "MARKDOWN"

        if volume_ratio_20 < 0.8 and 40 <= rsi <= 60:
            return "RANGE / BASE"

        return "NEUTRAL"

    def buy_probability(
        self,
        smart_money_score,
        accumulation_score,
        distribution_score,
        breakout_confirmation,
        hidden_buying,
    ) -> float:
        prob = (
            smart_money_score * 0.45
            + accumulation_score * 0.40
            - distribution_score * 0.20
            + 25
        )

        if breakout_confirmation:
            prob += 8

        if hidden_buying:
            prob += 7

        return round(max(min(prob, 100), 0), 2)

    def sell_probability(
        self,
        smart_money_score,
        accumulation_score,
        distribution_score,
        false_breakout,
        hidden_selling,
        demand_exhaustion,
    ) -> float:
        prob = (
            distribution_score * 0.55
            + (100 - smart_money_score) * 0.25
            - accumulation_score * 0.15
        )

        if false_breakout:
            prob += 10

        if hidden_selling:
            prob += 8

        if demand_exhaustion:
            prob += 8

        return round(max(min(prob, 100), 0), 2)

    def signal(
        self,
        smart_money_score,
        accumulation_score,
        distribution_score,
        buy_probability,
        sell_probability,
        wyckoff_phase,
    ) -> str:
        if sell_probability >= 70 or distribution_score >= 80:
            return "INSTITUTIONAL SELLING"

        if buy_probability >= 80 and accumulation_score >= 70:
            return "STRONG INSTITUTIONAL BUYING"

        if buy_probability >= 65 and smart_money_score >= 65:
            return "INSTITUTIONAL BUYING"

        if "ACCUMULATION" in wyckoff_phase:
            return "ACCUMULATION WATCH"

        if "DISTRIBUTION" in wyckoff_phase:
            return "DISTRIBUTION RISK"

        return "NEUTRAL"

    def delivery_strength(
        self,
        volume_ratio_20,
        value_traded,
        liquidity_score,
        close_position,
        change_pct,
    ) -> float:
        score = 40

        if volume_ratio_20 >= 2:
            score += 20
        elif volume_ratio_20 >= 1.3:
            score += 12
        elif volume_ratio_20 < 0.7:
            score -= 8

        if liquidity_score >= 80:
            score += 15
        elif liquidity_score >= 65:
            score += 8
        elif liquidity_score < 50:
            score -= 10

        if close_position >= 75 and change_pct > 0:
            score += 15
        elif close_position < 35:
            score -= 10

        if value_traded > 0:
            score += 5

        return round(max(min(score, 100), 0), 2)

    def price_volume_divergence(self, change_pct, volume_ratio_20, close_position) -> str:
        if change_pct > 2 and volume_ratio_20 < 0.8:
            return "PRICE UP / WEAK VOLUME"

        if change_pct < -2 and volume_ratio_20 >= 1.5:
            return "SELLING VOLUME DIVERGENCE"

        if abs(change_pct) < 1 and volume_ratio_20 >= 1.5 and close_position >= 60:
            return "ABSORPTION / HIDDEN BUYING"

        if abs(change_pct) < 1 and volume_ratio_20 >= 1.5 and close_position <= 40:
            return "SUPPLY / HIDDEN SELLING"

        return "NORMAL"

    def ensure_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        defaults = {
            "symbol": "",
            "company": "",
            "open": 0,
            "high": 0,
            "low": 0,
            "close": 0,
            "change_pct": 0,
            "volume": 0,
            "value_traded": 0,
            "volume_ratio_5": 1,
            "volume_ratio_20": 1,
            "rsi": 50,
            "adx": 20,
            "atr_percent": 0,
            "macd_hist": 0,
            "close_position": 50,
            "position_52w": 50,
            "ema_20": 0,
            "ema_50": 0,
            "ema_100": 0,
            "ema_200": 0,
            "liquidity_score_v4": 50,
            "liquidity_score_raw": 50,
            "trend_score_v4": 50,
            "trend_score_v5": 50,
            "trend_strength": 50,
            "momentum_score_v4": 50,
            "momentum_strength": 50,
            "volume_score_v4": 50,
            "volume_strength": 50,
        }

        for col, default in defaults.items():
            if col not in df.columns:
                df[col] = default

        return df


def apply_institutional_engine(df: pd.DataFrame) -> pd.DataFrame:
    engine = InstitutionalSmartMoneyEngine()
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