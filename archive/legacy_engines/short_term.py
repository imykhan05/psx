import pandas as pd


def calculate_short_term_scores(latest: pd.DataFrame, max_price: float = 500) -> pd.DataFrame:
    df = latest.copy()
    df = df[df["close"] <= max_price].copy()

    scores = df.apply(score_stock, axis=1, result_type="expand")
    result = pd.concat([df, scores], axis=1)
    result = result.sort_values(["ai_score", "volume"], ascending=False)

    return result


def safe_value(row, key, default=0):
    value = row.get(key, default)
    if pd.isna(value):
        return default
    return value


def score_stock(row):
    price = safe_value(row, "close")
    volume = safe_value(row, "volume")
    change_pct = safe_value(row, "change_pct")
    close_position = safe_value(row, "close_position")
    company = str(row.get("company", "")).upper()

    trend_score = 0
    momentum_score = 0
    volume_score = 0
    price_action_score = 0
    historical_score = 0
    risk_penalty = 0
    reasons = []
    risks = []

    if safe_value(row, "above_ema20"):
        trend_score += 5
        reasons.append("Above EMA20")
    if safe_value(row, "above_ema50"):
        trend_score += 5
        reasons.append("Above EMA50")
    if safe_value(row, "above_ema100"):
        trend_score += 5
        reasons.append("Above EMA100")
    if safe_value(row, "above_ema200"):
        trend_score += 5
        reasons.append("Above EMA200")
    if safe_value(row, "ema20") > safe_value(row, "ema50"):
        trend_score += 5
        reasons.append("EMA20 above EMA50")

    rsi = safe_value(row, "rsi14", None)
    if rsi is not None:
        if 50 <= rsi <= 70:
            momentum_score += 8
            reasons.append("Healthy RSI")
        elif 40 <= rsi < 50:
            momentum_score += 4
            reasons.append("RSI recovering")
        elif rsi > 75:
            risk_penalty += 4
            risks.append("RSI overbought")

    if safe_value(row, "macd_hist") > 0:
        momentum_score += 6
        reasons.append("MACD bullish")

    r3 = safe_value(row, "return_3d")
    r5 = safe_value(row, "return_5d")

    if 3 <= r3 <= 15:
        momentum_score += 3
        historical_score += 4
        reasons.append("3-day momentum")
    elif r3 > 15:
        momentum_score += 2
        risk_penalty += 3
        risks.append("3-day move extended")

    if 5 <= r5 <= 25:
        momentum_score += 3
        historical_score += 4
        reasons.append("5-day strength")
    elif r5 > 25:
        risk_penalty += 5
        risks.append("5-day move extended")

    vr5 = safe_value(row, "volume_ratio_5")
    vr20 = safe_value(row, "volume_ratio_20")

    if vr5 >= 1:
        volume_score += 5
        reasons.append("Volume above 5-day avg")
    if vr20 >= 1:
        volume_score += 5
        reasons.append("Volume above 20-day avg")
    if vr5 >= 1.5 or vr20 >= 1.5:
        volume_score += 5
        reasons.append("Relative volume spike")

    if volume >= 1_000_000:
        volume_score += 5
        reasons.append("High liquidity")
    elif volume >= 300_000:
        volume_score += 3
        reasons.append("Medium liquidity")

    if close_position >= 85:
        price_action_score += 5
        reasons.append("Close near day high")
    elif close_position >= 70:
        price_action_score += 3
        reasons.append("Strong close")

    if 2 <= change_pct <= 10:
        price_action_score += 5
        reasons.append("Strong daily gain")
    elif change_pct > 10:
        price_action_score += 3
        risk_penalty += 4
        risks.append("Upper-side extended")

    if safe_value(row, "momentum_status") in ["MOMENTUM", "STRONG MOMENTUM"]:
        historical_score += 2
        reasons.append(str(row.get("momentum_status")))

    if "WINDING" in company:
        risk_penalty += 25
        risks.append("WINDING-UP risk")
    if "NON-COMPLIANT" in company:
        risk_penalty += 20
        risks.append("NON-COMPLIANT risk")
    if price < 5:
        risk_penalty += 8
        risks.append("Very low price")
    if volume < 50_000:
        risk_penalty += 10
        risks.append("Low liquidity")

    trend_score = min(trend_score, 25)
    momentum_score = min(momentum_score, 20)
    volume_score = min(volume_score, 20)
    price_action_score = min(price_action_score, 15)
    historical_score = min(historical_score, 10)

    ai_score = trend_score + momentum_score + volume_score + price_action_score + historical_score - risk_penalty
    ai_score = round(max(min(ai_score, 100), 0), 2)

    if ai_score >= 85:
        verdict = "STRONG BUY"
    elif ai_score >= 75:
        verdict = "BUY/WATCH"
    elif ai_score >= 60:
        verdict = "WATCH"
    else:
        verdict = "AVOID"

    risk_level = "LOW"
    if risk_penalty >= 15:
        risk_level = "HIGH"
    elif risk_penalty >= 6:
        risk_level = "MEDIUM"

    return pd.Series({
        "ai_score": ai_score,
        "trend_score": trend_score,
        "momentum_score": momentum_score,
        "volume_score": volume_score,
        "price_action_score": price_action_score,
        "historical_score": historical_score,
        "risk_penalty": risk_penalty,
        "verdict": verdict,
        "risk_level": risk_level,
        "entry_low": round(price * 0.985, 2),
        "entry_high": round(price * 1.01, 2),
        "stop_loss": round(price * 0.95, 2),
        "target_1": round(price * 1.08, 2),
        "target_2": round(price * 1.14, 2),
        "reasons": " | ".join(reasons[:8]) if reasons else "No strong signal",
        "risks": " | ".join(risks) if risks else "Normal"
    })