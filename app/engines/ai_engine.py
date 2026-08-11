import json
from pathlib import Path
import pandas as pd

from app.engines.adaptive_weights import get_adaptive_weights

RULES_PATH = Path("rules/short_term_rules.json")


def load_rules(path: Path = RULES_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def safe(row, key, default=0):
    value = row.get(key, default)
    if pd.isna(value):
        return default
    return value


def score_stock(row, rules: dict) -> pd.Series:
    price = safe(row, "close")
    volume = safe(row, "volume")
    change_pct = safe(row, "change_pct")
    close_position = safe(row, "close_position")
    history_days = int(safe(row, "history_days", 0))
    company = str(row.get("company", "")).upper()

    weights = get_adaptive_weights(history_days)

    trend = 0
    momentum = 0
    volume_score = 0
    price_action = 0
    historical = 0
    risk_penalty = 0
    reasons = []
    risks = []

    # Trend
    if safe(row, "has_ema20") and safe(row, "above_ema20"):
        trend += 8
        reasons.append("Above EMA20")

    if safe(row, "has_ema50") and safe(row, "above_ema50"):
        trend += 7
        reasons.append("Above EMA50")

    if safe(row, "has_ema100") and safe(row, "above_ema100"):
        trend += 5
        reasons.append("Above EMA100")

    if safe(row, "has_ema200") and safe(row, "above_ema200"):
        trend += 5
        reasons.append("Above EMA200")

    trend = min(trend, weights["trend"])

    # Momentum
    rsi = row.get("rsi14")
    if pd.notna(rsi):
        if 50 <= rsi <= 70:
            momentum += 8
            reasons.append("Healthy RSI")
        elif 40 <= rsi < 50:
            momentum += 4
            reasons.append("RSI recovering")
        elif rsi > 75:
            risk_penalty += 4
            risks.append("RSI overbought")

    if safe(row, "macd_bullish"):
        momentum += 8
        reasons.append("MACD bullish")

    if safe(row, "is_3d_momentum"):
        momentum += 6
        reasons.append("3-day momentum")

    if safe(row, "is_5d_momentum"):
        momentum += 5
        reasons.append("5-day strength")

    momentum = min(momentum, weights["momentum"])

    # Volume
    if safe(row, "volume_ratio_5") >= 1:
        volume_score += 7
        reasons.append("Volume above 5-day average")

    if safe(row, "volume_ratio_20") >= 1:
        volume_score += 5
        reasons.append("Volume above 20-day average")

    if safe(row, "is_volume_spike"):
        volume_score += 8
        reasons.append("Relative volume spike")

    if safe(row, "is_highly_liquid"):
        volume_score += 8
        reasons.append("High liquidity")
    elif safe(row, "is_liquid"):
        volume_score += 5
        reasons.append("Medium liquidity")

    volume_score = min(volume_score, weights["volume"])

    # Price action
    if safe(row, "is_close_near_high"):
        price_action += 9
        reasons.append("Close near day high")
    elif safe(row, "is_close_strong"):
        price_action += 6
        reasons.append("Strong close")

    if safe(row, "is_healthy_gain"):
        price_action += 10
        reasons.append("Healthy daily gain")
    elif safe(row, "is_extended_today"):
        price_action += 5
        risk_penalty += 4
        risks.append("Daily move extended")

    price_action = min(price_action, weights["price_action"])

    # Historical
    if safe(row, "is_3d_momentum"):
        historical += 7

    if safe(row, "is_5d_momentum"):
        historical += 7

    if str(row.get("momentum_status", "")).upper() in ["MOMENTUM", "STRONG MOMENTUM"]:
        historical += 4
        reasons.append(str(row.get("momentum_status")))

    historical = min(historical, weights["historical"])

    # Risks
    if "WINDING" in company:
        risk_penalty += 25
        risks.append("WINDING-UP company")

    if "NON-COMPLIANT" in company:
        risk_penalty += 20
        risks.append("NON-COMPLIANT company")

    if price < 5:
        risk_penalty += 8
        risks.append("Price below 5")

    if volume < 50000:
        risk_penalty += 10
        risks.append("Low volume")

    if safe(row, "is_3d_extended"):
        risk_penalty += 4
        risks.append("3-day move extended")

    if safe(row, "is_5d_extended"):
        risk_penalty += 6
        risks.append("5-day move extended")

    raw_score = trend + momentum + volume_score + price_action + historical - risk_penalty
    ai_score = round(max(min(raw_score, 100), 0), 2)

    if risk_penalty >= 18:
        risk_level = "HIGH"
    elif risk_penalty >= 7:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    confidence = calculate_confidence(history_days, volume, safe(row, "volume_ratio_5"), risk_penalty)

    if ai_score >= 85 and risk_level != "HIGH":
        verdict = "STRONG BUY"
    elif ai_score >= 75 and risk_level != "HIGH":
        verdict = "BUY/WATCH"
    elif ai_score >= 60:
        verdict = "WATCH"
    else:
        verdict = "AVOID"

    return pd.Series({
        "ai_score": ai_score,
        "confidence": confidence,
        "trend_score": trend,
        "momentum_score": momentum,
        "volume_score": volume_score,
        "price_action_score": price_action,
        "historical_score": historical,
        "risk_penalty": risk_penalty,
        "risk_level": risk_level,
        "verdict": verdict,
        "entry_low": round(price * 0.985, 2),
        "entry_high": round(price * 1.010, 2),
        "stop_loss": round(price * 0.95, 2),
        "target_1": round(price * 1.08, 2),
        "target_2": round(price * 1.14, 2),
        "reasons": " | ".join(reasons[:10]) if reasons else "No strong signal",
        "risks": " | ".join(risks) if risks else "Normal"
    })


def calculate_confidence(history_days, volume, volume_ratio_5, risk_penalty):
    confidence = 35

    if history_days >= 200:
        confidence += 40
    elif history_days >= 50:
        confidence += 30
    elif history_days >= 20:
        confidence += 22
    elif history_days >= 14:
        confidence += 15
    elif history_days >= 5:
        confidence += 10

    if volume >= 1_000_000:
        confidence += 12
    elif volume >= 300_000:
        confidence += 7

    if volume_ratio_5 >= 1.5:
        confidence += 8
    elif volume_ratio_5 >= 1:
        confidence += 4

    if risk_penalty >= 18:
        confidence -= 20
    elif risk_penalty >= 7:
        confidence -= 10

    return int(max(min(confidence, 100), 0))


def apply_ai_engine(features: pd.DataFrame, max_price: float = 500) -> pd.DataFrame:
    rules = load_rules()

    df = features.copy()
    df = df[df["close"] <= max_price].copy()

    scores = df.apply(lambda row: score_stock(row, rules), axis=1, result_type="expand")
    result = pd.concat([df, scores], axis=1)

    result = result.sort_values(
        ["ai_score", "confidence", "volume"],
        ascending=False
    )

    return result