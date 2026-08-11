import pandas as pd


def build_features(history: pd.DataFrame, latest_date: str) -> pd.DataFrame:
    all_features = build_historical_features(history)
    return all_features[all_features["date"] == latest_date].copy()


def build_historical_features(history: pd.DataFrame) -> pd.DataFrame:
    df = history.copy()

    df["date_parsed"] = pd.to_datetime(df["date_parsed"], errors="coerce")
    df = df.sort_values(["symbol", "date_parsed"])

    df["history_days"] = df.groupby("symbol").cumcount() + 1

    df["has_rsi14"] = df["history_days"] >= 14
    df["has_ema20"] = df["history_days"] >= 20
    df["has_ema50"] = df["history_days"] >= 50
    df["has_ema100"] = df["history_days"] >= 100
    df["has_ema200"] = df["history_days"] >= 200

    df["short_history_mode"] = df["history_days"] < 20
    df["medium_history_mode"] = (df["history_days"] >= 20) & (df["history_days"] < 50)
    df["long_history_mode"] = df["history_days"] >= 50

    df["is_liquid"] = df["volume"] >= 300000
    df["is_highly_liquid"] = df["volume"] >= 1000000

    df["is_volume_spike"] = df["volume_ratio_5"] >= 1.5
    df["is_close_strong"] = df["close_position"] >= 70
    df["is_close_near_high"] = df["close_position"] >= 85

    df["is_healthy_gain"] = (df["change_pct"] >= 2) & (df["change_pct"] <= 10)
    df["is_extended_today"] = df["change_pct"] > 10

    df["is_3d_momentum"] = (df["return_3d"] >= 3) & (df["return_3d"] <= 15)
    df["is_3d_extended"] = df["return_3d"] > 15

    df["is_5d_momentum"] = (df["return_5d"] >= 5) & (df["return_5d"] <= 25)
    df["is_5d_extended"] = df["return_5d"] > 25

    df["macd_bullish"] = df["macd_hist"] > 0

    df["corporate_risk"] = (
        df["company"].astype(str).str.upper().str.contains("WINDING", na=False)
        | df["company"].astype(str).str.upper().str.contains("NON-COMPLIANT", na=False)
    )

    return df