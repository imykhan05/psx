import math
import pandas as pd


def build_portfolio_plan(final_df: pd.DataFrame, capital: int = 50000) -> dict:
    df = final_df.copy()

    # Only actionable candidates
    candidates = df[
        df["final_decision"].isin([
            "BUY",
            "WAIT FOR CONFIRMATION",
            "WAIT FOR BETTER ENTRY"
        ])
    ].copy()

    candidates = candidates.sort_values(
        ["final_score", "sector_score", "confidence", "volume"],
        ascending=False
    )

    market_score = int(df["market_score"].iloc[0]) if "market_score" in df.columns and not df.empty else 50

    if market_score >= 75:
        max_exposure_pct = 0.80
        mode = "AGGRESSIVE"
    elif market_score >= 55:
        max_exposure_pct = 0.60
        mode = "BALANCED"
    else:
        max_exposure_pct = 0.35
        mode = "DEFENSIVE"

    max_exposure = capital * max_exposure_pct

    selected = candidates.head(3).copy()

    allocation_weights = [0.45, 0.35, 0.20]

    rows = []
    used_capital = 0

    for i, (_, row) in enumerate(selected.iterrows()):
        allocation = max_exposure * allocation_weights[i]
        price = float(row["close"])

        quantity = math.floor(allocation / price) if price > 0 else 0
        investment = round(quantity * price, 2)

        entry_high = float(row.get("entry_high", price))
        stop_loss = float(row.get("stop_loss", price * 0.95))
        target_1 = float(row.get("target_1", price * 1.08))

        risk_per_share = max(entry_high - stop_loss, 0)
        profit_per_share = max(target_1 - entry_high, 0)

        max_loss = round(quantity * risk_per_share, 2)
        expected_profit = round(quantity * profit_per_share, 2)

        used_capital += investment

        rows.append({
            "rank": i + 1,
            "symbol": row["symbol"],
            "company": row["company"],
            "sector": row.get("sector", "UNKNOWN"),
            "final_decision": row["final_decision"],
            "final_score": row["final_score"],
            "confidence": row["confidence"],
            "sector_score": row["sector_score"],
            "entry_low": row["entry_low"],
            "entry_high": row["entry_high"],
            "stop_loss": row["stop_loss"],
            "target_1": row["target_1"],
            "target_2": row["target_2"],
            "allocation": round(allocation, 2),
            "quantity": quantity,
            "investment": investment,
            "max_loss": max_loss,
            "expected_profit_t1": expected_profit,
        })

    plan_df = pd.DataFrame(rows)

    cash_reserve = round(capital - used_capital, 2)
    total_expected_profit = round(plan_df["expected_profit_t1"].sum(), 2) if not plan_df.empty else 0
    total_max_loss = round(plan_df["max_loss"].sum(), 2) if not plan_df.empty else 0

    return {
        "mode": mode,
        "capital": capital,
        "market_score": market_score,
        "max_exposure_pct": round(max_exposure_pct * 100, 2),
        "used_capital": round(used_capital, 2),
        "cash_reserve": cash_reserve,
        "total_expected_profit_t1": total_expected_profit,
        "total_max_loss_to_sl": total_max_loss,
        "trades": plan_df,
    }