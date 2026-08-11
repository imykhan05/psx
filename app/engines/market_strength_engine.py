import pandas as pd


def calculate_market_strength_score(market_summary: dict) -> int:
    score = 50

    market_score = market_summary.get("market_score", 50)
    advance_ratio = market_summary.get("advance_decline_ratio", 1)
    avg_change = market_summary.get("average_change", 0)
    advancing = market_summary.get("advancing", 0)
    declining = market_summary.get("declining", 0)

    score += (market_score - 50) * 0.50

    if advance_ratio >= 2:
        score += 15
    elif advance_ratio >= 1.5:
        score += 10
    elif advance_ratio >= 1.2:
        score += 5
    elif advance_ratio < 0.7:
        score -= 15
    elif advance_ratio < 1:
        score -= 8

    if avg_change >= 2:
        score += 15
    elif avg_change >= 1:
        score += 8
    elif avg_change <= -2:
        score -= 15
    elif avg_change <= -1:
        score -= 8

    total = advancing + declining
    if total > 0:
        breadth_pct = (advancing / total) * 100

        if breadth_pct >= 70:
            score += 10
        elif breadth_pct >= 60:
            score += 5
        elif breadth_pct <= 40:
            score -= 8

    return int(max(min(score, 100), 0))


def add_market_strength(df: pd.DataFrame, market_summary: dict) -> pd.DataFrame:
    result = df.copy()

    market_strength = calculate_market_strength_score(market_summary)

    result["market_strength_score"] = market_strength

    return result


def market_strength_label(score: int) -> str:
    if score >= 85:
        return "STRONG BULLISH"
    if score >= 70:
        return "BULLISH"
    if score >= 50:
        return "NEUTRAL"
    if score >= 35:
        return "BEARISH"
    return "STRONG BEARISH"