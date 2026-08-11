import pandas as pd


def calculate_expected_value(row) -> float:
    profit_probability = row.get("profit_probability", 0) / 100
    stop_loss_probability = row.get("stop_loss_probability", 0) / 100
    avg_win = row.get("avg_win", 0)
    avg_loss = row.get("avg_loss", 0)

    if pd.isna(avg_win):
        avg_win = 0

    if pd.isna(avg_loss):
        avg_loss = 0

    ev = (profit_probability * avg_win) + (stop_loss_probability * avg_loss)

    return round(ev, 2)


def add_expected_value(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["expected_value"] = result.apply(calculate_expected_value, axis=1)
    return result