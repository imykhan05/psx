import pandas as pd


def simulate_trade(row) -> dict:
    entry = row.get("close", 0)
    stop_loss = entry * 0.95
    target_1 = entry * 1.08

    future_return = row.get("future_return_5d", 0)

    if pd.isna(future_return):
        outcome = "NO DATA"
    elif future_return >= 8:
        outcome = "TARGET HIT"
    elif future_return <= -5:
        outcome = "STOP LOSS"
    elif future_return > 0:
        outcome = "PROFIT"
    else:
        outcome = "LOSS"

    return {
        "entry": round(entry, 2),
        "stop_loss": round(stop_loss, 2),
        "target_1": round(target_1, 2),
        "future_return_5d": future_return,
        "outcome": outcome
    }