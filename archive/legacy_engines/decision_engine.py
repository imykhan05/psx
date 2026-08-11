import pandas as pd

from app.engines.sector_engine import SectorEngine


def apply_decision_engine(final_df: pd.DataFrame, market_summary: dict) -> pd.DataFrame:
    df = final_df.copy()

    sector_engine = SectorEngine(df)
    sector_summary = sector_engine.sector_summary()

    sector_scores = dict(
        zip(
            sector_summary["sector"],
            sector_summary["sector_score"]
        )
    )

    df["sector"] = df["symbol"].apply(sector_engine.sector_for_stock)
    df["sector_score"] = df["sector"].map(sector_scores).fillna(50)

    market_score = market_summary.get("market_score", 50)
    market_mood = market_summary.get("market_mood", "SIDEWAYS")

    decisions = df.apply(
        lambda row: make_final_decision(row, market_score, market_mood),
        axis=1,
        result_type="expand"
    )

    result = pd.concat([df, decisions], axis=1)

    result = result.sort_values(
        ["decision_rank", "final_score", "ai_score", "confidence", "volume"],
        ascending=[True, False, False, False, False]
    )

    return result


def make_final_decision(row, market_score: int, market_mood: str) -> pd.Series:
    ai_score = row.get("ai_score", 0)
    confidence = row.get("confidence", 0)
    sector_score = row.get("sector_score", 50)
    risk_level = row.get("risk_level", "HIGH")
    reward_risk = row.get("reward_risk_ratio", 0)
    action = row.get("action", "AVOID")

    final_score = (
        ai_score * 0.50
        + confidence * 0.20
        + sector_score * 0.20
        + market_score * 0.10
    )

    final_score = round(final_score, 2)

    decision = "AVOID"
    decision_rank = 5
    decision_reason = []

    if market_score < 40:
        decision = "AVOID"
        decision_rank = 5
        decision_reason.append("Market weak")

    elif risk_level == "HIGH":
        decision = "AVOID"
        decision_rank = 5
        decision_reason.append("High risk")

    elif final_score >= 78 and confidence >= 65 and sector_score >= 65 and risk_level == "LOW":
        decision = "BUY"
        decision_rank = 1
        decision_reason.append("AI + sector + market aligned")

    elif final_score >= 70 and confidence >= 60 and risk_level != "HIGH":
        decision = "WAIT FOR CONFIRMATION"
        decision_rank = 2
        decision_reason.append("Good setup but needs morning confirmation")

    elif final_score >= 60:
        decision = "WATCH"
        decision_rank = 3
        decision_reason.append("Improving setup")

    else:
        decision = "AVOID"
        decision_rank = 5
        decision_reason.append("Score not strong enough")

    if reward_risk < 1.2 and decision in ["BUY", "WAIT FOR CONFIRMATION"]:
        decision = "WAIT FOR BETTER ENTRY"
        decision_rank = 3
        decision_reason.append("Reward/risk not attractive enough")

    if market_mood in ["STRONG BEARISH", "BEARISH"] and decision == "BUY":
        decision = "WAIT FOR CONFIRMATION"
        decision_rank = 2
        decision_reason.append("Market mood not fully supportive")

    return pd.Series({
        "market_score": market_score,
        "market_mood": market_mood,
        "final_score": final_score,
        "final_decision": decision,
        "decision_rank": decision_rank,
        "decision_reason": " | ".join(decision_reason)
    })