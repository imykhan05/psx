import pandas as pd


def add_trend_engine_v2(df: pd.DataFrame) -> pd.DataFrame:
    """
    Trend Engine V2.1

    Short-history aware trend engine.

    If history is less than 20 days, it avoids long EMA penalties and uses:
    - 1D / 3D / 5D returns
    - close position
    - RSI
    - MACD histogram
    - volume expansion
    - liquidity

    Output:
    - trend_score_v5
    - trend_label_v5
    - trend_reason_v5
    - trend_score_v4
    """

    result = df.copy()

    if result.empty:
        return result

    trend_data = result.apply(
        calculate_trend_v2,
        axis=1,
        result_type="expand",
    )

    result = pd.concat([result, trend_data], axis=1)

    result["trend_score_v4"] = result["trend_score_v5"]

    return result


def calculate_trend_v2(row) -> pd.Series:
    history_days = safe(row, "history_days", 0)

    if history_days < 20:
        return calculate_short_history_trend(row)

    return calculate_normal_trend(row)


def calculate_short_history_trend(row) -> pd.Series:
    close = safe(row, "close", safe(row, "price", 0))

    return_1d = safe(row, "return_1d", safe(row, "change_pct", 0))
    return_3d = safe(row, "return_3d", 0)
    return_5d = safe(row, "return_5d", 0)

    close_position = safe(row, "close_position", 50)
    position_52w = safe(row, "position_52w", close_position)

    rsi = safe(row, "rsi", 50)
    macd_hist = safe(row, "macd_hist", 0)

    volume_ratio_5 = safe(row, "volume_ratio_5", 1)
    volume_ratio_20 = safe(row, "volume_ratio_20", 1)

    liquidity_raw = safe(row, "liquidity_score_raw", 50)
    value_traded = safe(row, "value_traded", 0)

    score = 50
    reasons = []

    if return_1d > 0:
        score += min(return_1d * 1.5, 10)
        reasons.append("Positive 1D move")
    elif return_1d < 0:
        score += max(return_1d * 1.5, -10)
        reasons.append("Negative 1D move")

    if return_3d > 0:
        score += min(return_3d * 1.2, 12)
        reasons.append("Positive 3D momentum")
    elif return_3d < 0:
        score += max(return_3d * 1.2, -12)
        reasons.append("Negative 3D momentum")

    if return_5d > 0:
        score += min(return_5d * 0.8, 10)
        reasons.append("Positive 5D momentum")
    elif return_5d < 0:
        score += max(return_5d * 0.8, -10)
        reasons.append("Negative 5D momentum")

    if close_position >= 85:
        score += 12
        reasons.append("Close near short-range high")
    elif close_position >= 70:
        score += 7
        reasons.append("Strong close position")
    elif close_position <= 25:
        score -= 10
        reasons.append("Weak close position")

    if position_52w >= 75:
        score += 5
        reasons.append("Strong range position")
    elif position_52w <= 30:
        score -= 5
        reasons.append("Weak range position")

    if 55 <= rsi <= 70:
        score += 8
        reasons.append("Healthy RSI")
    elif 70 < rsi <= 80:
        score += 4
        reasons.append("Strong but extended RSI")
    elif rsi > 80:
        score -= 6
        reasons.append("Overextended RSI")
    elif rsi < 35:
        score -= 8
        reasons.append("Weak RSI")

    if macd_hist > 0:
        score += 6
        reasons.append("MACD improving")
    elif macd_hist < 0:
        score -= 4
        reasons.append("MACD weak")

    if volume_ratio_5 >= 1.5 or volume_ratio_20 >= 1.5:
        score += 8
        reasons.append("Volume expansion")
    elif volume_ratio_5 >= 1.1 or volume_ratio_20 >= 1.1:
        score += 4
        reasons.append("Volume support")
    elif volume_ratio_5 < 0.7 and volume_ratio_20 < 0.7:
        score -= 5
        reasons.append("Weak volume")

    if liquidity_raw >= 80 or value_traded >= 50000000:
        score += 5
        reasons.append("Strong liquidity")
    elif liquidity_raw < 40:
        score -= 6
        reasons.append("Weak liquidity")

    score = round(max(min(score, 100), 0), 2)
    label = trend_label(score)

    if not reasons:
        reasons.append("Short-history neutral trend")

    return pd.Series({
        "trend_score_v5": score,
        "trend_label_v5": label,
        "trend_reason_v5": " | ".join(reasons),
        "price_above_ema20_v2": False,
        "price_above_ema50_v2": False,
        "price_above_ema100_v2": False,
        "price_above_ema200_v2": False,
        "ema20_above_ema50_v2": False,
        "ema50_above_ema100_v2": False,
        "ema100_above_ema200_v2": False,
        "trend_history_mode": "SHORT",
    })


def calculate_normal_trend(row) -> pd.Series:
    close = safe(row, "close", safe(row, "price", 0))

    ema20 = safe(row, "ema_20", safe(row, "EMA_20", 0))
    ema50 = safe(row, "ema_50", safe(row, "EMA_50", 0))
    ema100 = safe(row, "ema_100", safe(row, "EMA_100", 0))
    ema200 = safe(row, "ema_200", safe(row, "EMA_200", 0))

    sma20 = safe(row, "sma_20", safe(row, "SMA_20", 0))
    sma50 = safe(row, "sma_50", safe(row, "SMA_50", 0))

    return_3d = safe(row, "return_3d", 0)
    return_5d = safe(row, "return_5d", 0)
    return_10d = safe(row, "return_10d", 0)

    close_position = safe(row, "close_position", 50)

    score = 50
    reasons = []

    price_above_ema20 = close > ema20 if close > 0 and ema20 > 0 else False
    price_above_ema50 = close > ema50 if close > 0 and ema50 > 0 else False
    price_above_ema100 = close > ema100 if close > 0 and ema100 > 0 else False
    price_above_ema200 = close > ema200 if close > 0 and ema200 > 0 else False

    ema20_above_ema50 = ema20 > ema50 if ema20 > 0 and ema50 > 0 else False
    ema50_above_ema100 = ema50 > ema100 if ema50 > 0 and ema100 > 0 else False
    ema100_above_ema200 = ema100 > ema200 if ema100 > 0 and ema200 > 0 else False

    price_above_sma20 = close > sma20 if close > 0 and sma20 > 0 else False
    price_above_sma50 = close > sma50 if close > 0 and sma50 > 0 else False

    if price_above_ema20:
        score += 10
        reasons.append("Price above EMA20")
    else:
        score -= 5
        reasons.append("Price below EMA20")

    if price_above_ema50:
        score += 12
        reasons.append("Price above EMA50")
    else:
        score -= 6
        reasons.append("Price below EMA50")

    if price_above_ema100:
        score += 6
        reasons.append("Price above EMA100")

    if price_above_ema200:
        score += 6
        reasons.append("Price above EMA200")

    if ema20_above_ema50:
        score += 12
        reasons.append("EMA20 above EMA50")
    else:
        score -= 5
        reasons.append("EMA20 below EMA50")

    if ema50_above_ema100:
        score += 5
        reasons.append("EMA50 above EMA100")

    if ema100_above_ema200:
        score += 5
        reasons.append("EMA100 above EMA200")

    if price_above_sma20:
        score += 5
        reasons.append("Price above SMA20")

    if price_above_sma50:
        score += 5
        reasons.append("Price above SMA50")

    if return_3d > 0:
        score += min(return_3d * 1.2, 8)
        reasons.append("Positive 3D trend")
    elif return_3d < 0:
        score += max(return_3d * 1.2, -8)
        reasons.append("Negative 3D trend")

    if return_5d > 0:
        score += min(return_5d * 0.8, 8)
        reasons.append("Positive 5D trend")
    elif return_5d < 0:
        score += max(return_5d * 0.8, -8)
        reasons.append("Negative 5D trend")

    if return_10d > 0:
        score += min(return_10d * 0.5, 6)
        reasons.append("Positive 10D trend")
    elif return_10d < 0:
        score += max(return_10d * 0.5, -6)
        reasons.append("Negative 10D trend")

    if close_position >= 85:
        score += 8
        reasons.append("Close near range high")
    elif close_position >= 70:
        score += 4
        reasons.append("Strong close position")
    elif close_position <= 25:
        score -= 8
        reasons.append("Weak close position")

    score = round(max(min(score, 100), 0), 2)
    label = trend_label(score)

    return pd.Series({
        "trend_score_v5": score,
        "trend_label_v5": label,
        "trend_reason_v5": " | ".join(reasons),
        "price_above_ema20_v2": price_above_ema20,
        "price_above_ema50_v2": price_above_ema50,
        "price_above_ema100_v2": price_above_ema100,
        "price_above_ema200_v2": price_above_ema200,
        "ema20_above_ema50_v2": ema20_above_ema50,
        "ema50_above_ema100_v2": ema50_above_ema100,
        "ema100_above_ema200_v2": ema100_above_ema200,
        "trend_history_mode": "NORMAL",
    })


def trend_label(score: float) -> str:
    if score >= 80:
        return "STRONG UPTREND"

    if score >= 65:
        return "UPTREND"

    if score >= 50:
        return "NEUTRAL / IMPROVING"

    if score >= 35:
        return "WEAK TREND"

    return "DOWNTREND"


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