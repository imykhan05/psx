import pandas as pd

from app.engines.sector_engine import SectorEngine


def remove_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    return df.loc[:, ~df.columns.duplicated()].copy()


def apply_decision_engine_v2(final_df: pd.DataFrame, market_summary: dict) -> pd.DataFrame:
    df = final_df.copy()
    df = remove_duplicate_columns(df)

    if df.empty:
        return df

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

    df = remove_duplicate_columns(df)

    market_score = market_summary.get("market_score", 50)
    market_mood = market_summary.get("market_mood", "SIDEWAYS")

    decisions = df.apply(
        lambda row: make_final_decision_v2(row, market_score, market_mood),
        axis=1,
        result_type="expand"
    )

    result = pd.concat([df, decisions], axis=1)

    result = remove_duplicate_columns(result)

    sort_columns = [
        "decision_rank",
        "final_score",
        "buy_probability",
        "ai_score",
        "volume",
    ]

    for col in sort_columns:
        if col not in result.columns:
            result[col] = 0

    result = result.sort_values(
        sort_columns,
        ascending=[True, False, False, False, False]
    )

    result = remove_duplicate_columns(result)

    return result


def make_final_decision_v2(row, market_score: int, market_mood: str) -> pd.Series:
    ai_score = safe(row, "ai_score", safe(row, "ai_score_v4", 0))
    confidence = safe(row, "confidence", safe(row, "confidence_score_v4", 50))
    buy_probability = safe(row, "buy_probability", 50)
    sell_probability = safe(row, "sell_probability", 50)

    sector_score = safe(row, "sector_score", safe(row, "sector_score_v4", 50))
    trend_score = safe(row, "trend_score_v4", 50)
    momentum_score = safe(row, "momentum_score_v4", 50)
    volume_score = safe(row, "volume_score_v4", 50)
    liquidity_score = safe(row, "liquidity_score_v4", 50)
    risk_score = safe(row, "risk_score_v4", 50)

    risk_level = str(row.get("risk_level", "MEDIUM")).upper()
    reward_risk = safe(row, "reward_risk_ratio", safe(row, "risk_reward_t1", 1.5))

    final_score = (
        ai_score * 0.28
        + buy_probability * 0.22
        + trend_score * 0.12
        + momentum_score * 0.10
        + volume_score * 0.08
        + liquidity_score * 0.08
        + sector_score * 0.07
        + market_score * 0.05
    )

    if risk_level == "HIGH":
        final_score -= 10

    if risk_score >= 75:
        final_score -= 8
    elif risk_score <= 45:
        final_score += 3

    if sell_probability >= 60:
        final_score -= 6

    if market_score >= 70:
        final_score += 2
    elif market_score < 40:
        final_score -= 12

    final_score = round(max(min(final_score, 100), 0), 2)

    decision = "AVOID"
    decision_rank = 6
    decision_reason = []

    strong_buy_setup = (
        final_score >= 72
        and buy_probability >= 66
        and ai_score >= 68
        and liquidity_score >= 55
        and risk_level != "HIGH"
        and market_score >= 55
    )

    buy_setup = (
        final_score >= 64
        and buy_probability >= 58
        and ai_score >= 60
        and liquidity_score >= 45
        and risk_level != "HIGH"
        and market_score >= 50
    )

    watch_setup = (
        final_score >= 55
        and buy_probability >= 50
        and liquidity_score >= 35
        and market_score >= 45
    )

    sell_setup = (
        final_score < 42
        or sell_probability >= 68
        or risk_score >= 82
    )

    if market_score < 35:
        decision = "AVOID"
        decision_rank = 6
        decision_reason.append("Market too weak")

    elif strong_buy_setup:
        decision = "STRONG BUY"
        decision_rank = 1
        decision_reason.append("High probability institutional setup")

    elif buy_setup:
        decision = "BUY"
        decision_rank = 2
        decision_reason.append("AI probability and liquidity aligned")

    elif watch_setup:
        decision = "WATCH"
        decision_rank = 3
        decision_reason.append("Improving setup")

    elif sell_setup:
        decision = "SELL"
        decision_rank = 5
        decision_reason.append("Weak probability or high risk")

    else:
        decision = "AVOID"
        decision_rank = 6
        decision_reason.append("Setup not strong enough")

    if reward_risk < 1.1 and decision in ["STRONG BUY", "BUY"]:
        decision = "WAIT FOR BETTER ENTRY"
        decision_rank = 3
        decision_reason.append("Reward/risk needs better entry")

    if market_mood in ["STRONG BEARISH", "BEARISH"] and decision in ["STRONG BUY", "BUY"]:
        decision = "WAIT FOR CONFIRMATION"
        decision_rank = 3
        decision_reason.append("Market mood not fully supportive")

    if liquidity_score < 30 and decision in ["STRONG BUY", "BUY", "WATCH"]:
        decision = "AVOID"
        decision_rank = 6
        decision_reason.append("Liquidity too weak")

    return pd.Series({
        "market_score": market_score,
        "market_mood": market_mood,
        "final_score": final_score,
        "final_decision": decision,
        "decision_rank": decision_rank,
        "decision_reason": " | ".join(decision_reason),
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