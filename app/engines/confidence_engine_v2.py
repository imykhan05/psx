import pandas as pd


def add_confidence_score_v2(df: pd.DataFrame) -> pd.DataFrame:
    """
    Confidence Engine V2

    Produces dynamic institutional confidence score.

    Output columns:
    - confidence_v3
    - confidence
    - confidence_label
    - confidence_reason
    """

    result = df.copy()

    if result.empty:
        return result

    confidence_data = result.apply(
        calculate_confidence_v2,
        axis=1,
        result_type="expand"
    )

    result = pd.concat([result, confidence_data], axis=1)

    result["confidence"] = result["confidence_v3"]

    return result


def calculate_confidence_v2(row) -> pd.Series:
    score = 45
    reasons = []

    data_quality = safe(row, "data_quality_score", 70)
    liquidity = safe(row, "liquidity_score_v4", safe(row, "liquidity_score_raw", 50))
    volume_score = safe(row, "volume_score_v4", 50)
    trend_score = safe(row, "trend_score_v4", safe(row, "trend_strength", 50))
    momentum_score = safe(row, "momentum_score_v4", 50)
    market_score = safe(row, "market_strength_score", safe(row, "market_score_v4", 50))
    sector_score = safe(row, "sector_strength_score", safe(row, "sector_score_v4", 50))
    risk_score = safe(row, "risk_score_v4", 50)
    history_days = safe(row, "history_days", 0)

    volume = safe(row, "volume", 0)
    close = safe(row, "close", 0)
    value_traded = safe(row, "value_traded", volume * close)

    if data_quality >= 90:
        score += 12
        reasons.append("Excellent data quality")
    elif data_quality >= 75:
        score += 8
        reasons.append("Good data quality")
    elif data_quality >= 55:
        score += 2
        reasons.append("Acceptable data quality")
    else:
        score -= 12
        reasons.append("Weak data quality")

    if history_days >= 50:
        score += 8
        reasons.append("Sufficient history")
    elif history_days >= 20:
        score += 4
        reasons.append("Medium history")
    else:
        score -= 8
        reasons.append("Short history")

    if liquidity >= 80:
        score += 12
        reasons.append("Strong liquidity")
    elif liquidity >= 60:
        score += 8
        reasons.append("Healthy liquidity")
    elif liquidity >= 40:
        score += 2
        reasons.append("Acceptable liquidity")
    else:
        score -= 12
        reasons.append("Weak liquidity")

    if value_traded >= 100000000:
        score += 8
        reasons.append("Institutional value traded")
    elif value_traded >= 20000000:
        score += 5
        reasons.append("Good value traded")
    elif value_traded < 1000000:
        score -= 8
        reasons.append("Very low value traded")

    if volume_score >= 75:
        score += 8
        reasons.append("Volume expansion")
    elif volume_score >= 60:
        score += 4
        reasons.append("Decent volume")
    elif volume_score < 40:
        score -= 6
        reasons.append("Weak volume")

    if trend_score >= 70:
        score += 10
        reasons.append("Strong trend")
    elif trend_score >= 58:
        score += 5
        reasons.append("Improving trend")
    elif trend_score < 45:
        score -= 8
        reasons.append("Weak trend")

    if momentum_score >= 70:
        score += 8
        reasons.append("Strong momentum")
    elif momentum_score >= 58:
        score += 4
        reasons.append("Positive momentum")
    elif momentum_score < 42:
        score -= 8
        reasons.append("Weak momentum")

    if market_score >= 75:
        score += 8
        reasons.append("Supportive market")
    elif market_score >= 60:
        score += 5
        reasons.append("Healthy market")
    elif market_score < 45:
        score -= 10
        reasons.append("Weak market")

    if sector_score >= 75:
        score += 7
        reasons.append("Strong sector")
    elif sector_score >= 60:
        score += 4
        reasons.append("Healthy sector")
    elif sector_score < 45:
        score -= 6
        reasons.append("Weak sector")

    if risk_score <= 40:
        score += 8
        reasons.append("Low risk")
    elif risk_score <= 55:
        score += 3
        reasons.append("Controlled risk")
    elif risk_score >= 75:
        score -= 14
        reasons.append("High risk")

    corporate_risk = bool(row.get("corporate_risk", False))
    if corporate_risk:
        score -= 25
        reasons.append("Corporate risk flag")

    if close <= 0:
        score -= 30
        reasons.append("Invalid price")

    if volume <= 0:
        score -= 20
        reasons.append("Invalid volume")

    score = round(max(min(score, 100), 0), 2)

    if score >= 85:
        label = "VERY HIGH"
    elif score >= 70:
        label = "HIGH"
    elif score >= 55:
        label = "MEDIUM"
    elif score >= 40:
        label = "LOW"
    else:
        label = "VERY LOW"

    return pd.Series({
        "confidence_v3": score,
        "confidence_label": label,
        "confidence_reason": " | ".join(reasons),
    })


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