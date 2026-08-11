import math
import pandas as pd


def build_recommendations(result: pd.DataFrame, capital: int = 50000) -> pd.DataFrame:
    df = result.copy()

    recommendations = df.apply(
        lambda row: recommend_stock(row, capital),
        axis=1,
        result_type="expand"
    )

    final = pd.concat([df, recommendations], axis=1)

    final = final.sort_values(
        ["recommendation_rank", "ai_score", "confidence", "volume"],
        ascending=[True, False, False, False]
    )

    return final


def recommend_stock(row, capital: int) -> pd.Series:
    ai_score = row.get("ai_score", 0)
    confidence = row.get("confidence", 0)
    risk_level = row.get("risk_level", "HIGH")
    verdict = row.get("verdict", "AVOID")
    price = row.get("close", 0)

    action = "AVOID"
    allocation_pct = 0.0
    holding_days = "No trade"
    rank = 4

    if verdict == "STRONG BUY" and risk_level != "HIGH" and confidence >= 65:
        action = "BUY"
        allocation_pct = 0.45
        holding_days = "2-5 days"
        rank = 1

    elif verdict in ["BUY/WATCH", "WATCH"] and risk_level == "LOW" and ai_score >= 65 and confidence >= 55:
        action = "WAIT FOR CONFIRMATION"
        allocation_pct = 0.30
        holding_days = "1-4 days"
        rank = 2

    elif verdict == "WATCH" and ai_score >= 60:
        action = "WATCH ONLY"
        allocation_pct = 0.15
        holding_days = "1-3 days"
        rank = 3

    risk_amount = capital * 0.02
    suggested_capital = round(capital * allocation_pct)

    quantity = 0
    if price > 0 and suggested_capital > 0:
        quantity = math.floor(suggested_capital / price)

    actual_investment = round(quantity * price, 2)

    entry_low = row.get("entry_low", price * 0.985)
    entry_high = row.get("entry_high", price * 1.01)
    stop_loss = row.get("stop_loss", price * 0.95)
    target_1 = row.get("target_1", price * 1.08)
    target_2 = row.get("target_2", price * 1.14)

    risk_per_share = max(entry_high - stop_loss, 0.01)
    reward_per_share = max(target_1 - entry_high, 0.01)
    rr_ratio = round(reward_per_share / risk_per_share, 2)

    max_loss = round(quantity * risk_per_share, 2)
    expected_t1_profit = round(quantity * reward_per_share, 2)

    final_reason = build_reason(row, action, rr_ratio)

    return pd.Series({
        "action": action,
        "recommended_capital": suggested_capital,
        "quantity": quantity,
        "actual_investment": actual_investment,
        "risk_amount_limit": round(risk_amount, 2),
        "max_loss_to_sl": max_loss,
        "expected_profit_t1": expected_t1_profit,
        "reward_risk_ratio": rr_ratio,
        "holding_days": holding_days,
        "recommendation_rank": rank,
        "final_reason": final_reason
    })


def build_reason(row, action: str, rr_ratio: float) -> str:
    reasons = str(row.get("reasons", ""))
    risks = str(row.get("risks", "Normal"))
    ai_score = row.get("ai_score", 0)
    confidence = row.get("confidence", 0)

    if action == "BUY":
        return (
            f"BUY setup: AI Score {ai_score}/100, Confidence {confidence}%, "
            f"RR {rr_ratio}. Reasons: {reasons}. Risks: {risks}."
        )

    if action == "WAIT FOR CONFIRMATION":
        return (
            f"Wait for live confirmation: AI Score {ai_score}/100, Confidence {confidence}%, "
            f"RR {rr_ratio}. Reasons: {reasons}. Risks: {risks}."
        )

    if action == "WATCH ONLY":
        return (
            f"Watch only: setup is improving but not strong enough for direct buy. "
            f"AI Score {ai_score}/100, Confidence {confidence}%. Reasons: {reasons}. Risks: {risks}."
        )

    return (
        f"Avoid for now: score/confidence/risk not strong enough. "
        f"AI Score {ai_score}/100, Confidence {confidence}%. Risks: {risks}."
    )