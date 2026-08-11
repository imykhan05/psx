import pandas as pd


def analyze_rules(learning_df: pd.DataFrame) -> dict:
    if learning_df.empty:
        return {
            "strong_features": [],
            "increase_features": [],
            "weak_features": [],
            "neutral_features": []
        }

    strong = learning_df[
        learning_df["suggestion"] == "STRONG_INCREASE"
    ]["feature"].tolist()

    increase = learning_df[
        learning_df["suggestion"] == "INCREASE_WEIGHT"
    ]["feature"].tolist()

    weak = learning_df[
        learning_df["suggestion"] == "DECREASE_WEIGHT"
    ]["feature"].tolist()

    neutral = learning_df[
        learning_df["suggestion"].isin(["KEEP_WEIGHT", "NEED_MORE_TRADES"])
    ]["feature"].tolist()

    return {
        "strong_features": strong,
        "increase_features": increase,
        "weak_features": weak,
        "neutral_features": neutral
    }