import pandas as pd


def calculate_confidence_score(row) -> int:
    confidence = 35

    history_days = safe(row, "history_days", 0)
    volume = safe(row, "volume", 0)
    volume_ratio_5 = safe(row, "volume_ratio_5", 0)
    risk_penalty = safe(row, "risk_penalty", 0)
    probability_confidence = safe(row, "probability_confidence", 0)

    if history_days >= 200:
        confidence += 35
    elif history_days >= 50:
        confidence += 25
    elif history_days >= 20:
        confidence += 18
    elif history_days >= 14:
        confidence += 12
    elif history_days >= 5:
        confidence += 8

    if volume >= 1_000_000:
        confidence += 12
    elif volume >= 300_000:
        confidence += 7
    elif volume >= 100_000:
        confidence += 4

    if volume_ratio_5 >= 2:
        confidence += 8
    elif volume_ratio_5 >= 1.5:
        confidence += 6
    elif volume_ratio_5 >= 1:
        confidence += 3

    if probability_confidence:
        confidence += int(probability_confidence * 0.15)

    if risk_penalty >= 18:
        confidence -= 20
    elif risk_penalty >= 7:
        confidence -= 10

    return int(max(min(confidence, 100), 0))


def add_confidence_score(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    result["confidence_v2"] = result.apply(
        calculate_confidence_score,
        axis=1
    )

    return result


def safe(row, key, default=0):
    value = row.get(key, default)

    if pd.isna(value):
        return default

    return value