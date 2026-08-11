import pandas as pd
import numpy as np


def build_features_v2(history: pd.DataFrame, latest_date: str) -> pd.DataFrame:
    all_features = build_historical_features_v2(history)
    return all_features[all_features["date"] == latest_date].copy()


def build_historical_features_v2(history: pd.DataFrame) -> pd.DataFrame:
    df = history.copy()

    df["date_parsed"] = pd.to_datetime(df["date_parsed"], errors="coerce")
    df = df.sort_values(["symbol", "date_parsed"])

    df = add_core_history_features(df)
    df = add_return_features(df)
    df = add_volume_features(df)
    df = add_trend_features(df)
    df = add_momentum_features(df)
    df = add_volatility_features(df)
    df = add_liquidity_features(df)
    df = add_breakout_features(df)
    df = add_quality_flags(df)

    return df


def add_core_history_features(df: pd.DataFrame) -> pd.DataFrame:
    df["history_days"] = df.groupby("symbol").cumcount() + 1

    df["has_rsi14"] = df["history_days"] >= 14
    df["has_ema20"] = df["history_days"] >= 20
    df["has_ema50"] = df["history_days"] >= 50
    df["has_ema100"] = df["history_days"] >= 100
    df["has_ema200"] = df["history_days"] >= 200

    df["short_history_mode"] = df["history_days"] < 20
    df["medium_history_mode"] = (df["history_days"] >= 20) & (df["history_days"] < 50)
    df["long_history_mode"] = df["history_days"] >= 50

    return df


def add_return_features(df: pd.DataFrame) -> pd.DataFrame:
    group = df.groupby("symbol")

    df["return_1d"] = group["close"].pct_change(1) * 100
    df["return_3d"] = group["close"].pct_change(3) * 100
    df["return_5d"] = group["close"].pct_change(5) * 100
    df["return_10d"] = group["close"].pct_change(10) * 100
    df["return_20d"] = group["close"].pct_change(20) * 100

    df["change_percent"] = df.get("change_pct", df["return_1d"])
    df["pct_change"] = df.get("change_pct", df["return_1d"])

    return df


def add_volume_features(df: pd.DataFrame) -> pd.DataFrame:
    group = df.groupby("symbol")

    df["avg_volume"] = group["volume"].transform(
        lambda x: x.rolling(20, min_periods=3).mean()
    )
    df["volume_avg"] = df["avg_volume"]
    df["volume_sma_20"] = df["avg_volume"]

    df["volume_ratio_5"] = df["volume"] / group["volume"].transform(
        lambda x: x.rolling(5, min_periods=2).mean()
    )

    df["volume_ratio_20"] = df["volume"] / df["avg_volume"]

    df["volume_ratio_5"] = df["volume_ratio_5"].replace([np.inf, -np.inf], np.nan).fillna(1)
    df["volume_ratio_20"] = df["volume_ratio_20"].replace([np.inf, -np.inf], np.nan).fillna(1)

    df["is_liquid"] = df["volume"] >= 300000
    df["is_highly_liquid"] = df["volume"] >= 1000000
    df["is_volume_spike"] = df["volume_ratio_5"] >= 1.5
    df["is_volume_expansion"] = df["volume_ratio_20"] >= 1.2

    return df


def add_trend_features(df: pd.DataFrame) -> pd.DataFrame:
    group = df.groupby("symbol")

    df["sma_20"] = group["close"].transform(
        lambda x: x.rolling(20, min_periods=3).mean()
    )
    df["sma_50"] = group["close"].transform(
        lambda x: x.rolling(50, min_periods=5).mean()
    )

    df["ema_20"] = group["close"].transform(
        lambda x: x.ewm(span=20, adjust=False, min_periods=3).mean()
    )
    df["ema_50"] = group["close"].transform(
        lambda x: x.ewm(span=50, adjust=False, min_periods=5).mean()
    )
    df["ema_100"] = group["close"].transform(
        lambda x: x.ewm(span=100, adjust=False, min_periods=10).mean()
    )
    df["ema_200"] = group["close"].transform(
        lambda x: x.ewm(span=200, adjust=False, min_periods=20).mean()
    )

    df["price_above_ema20"] = df["close"] > df["ema_20"]
    df["price_above_ema50"] = df["close"] > df["ema_50"]
    df["ema20_above_ema50"] = df["ema_20"] > df["ema_50"]

    df["trend_strength"] = 50
    df.loc[df["price_above_ema20"], "trend_strength"] += 15
    df.loc[df["price_above_ema50"], "trend_strength"] += 15
    df.loc[df["ema20_above_ema50"], "trend_strength"] += 15
    df["trend_strength"] = df["trend_strength"].clip(0, 100)

    return df


def add_momentum_features(df: pd.DataFrame) -> pd.DataFrame:
    group = df.groupby("symbol")

    delta = group["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.groupby(df["symbol"]).transform(
        lambda x: x.rolling(14, min_periods=3).mean()
    )
    avg_loss = loss.groupby(df["symbol"]).transform(
        lambda x: x.rolling(14, min_periods=3).mean()
    )

    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))
    df["rsi"] = df["rsi"].fillna(50).clip(0, 100)

    ema12 = group["close"].transform(
        lambda x: x.ewm(span=12, adjust=False, min_periods=3).mean()
    )
    ema26 = group["close"].transform(
        lambda x: x.ewm(span=26, adjust=False, min_periods=5).mean()
    )

    df["macd"] = ema12 - ema26
    df["macd_signal"] = df.groupby("symbol")["macd"].transform(
        lambda x: x.ewm(span=9, adjust=False, min_periods=3).mean()
    )
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    df["macd_bullish"] = df["macd_hist"] > 0

    df["is_3d_momentum"] = (df["return_3d"] >= 3) & (df["return_3d"] <= 15)
    df["is_3d_extended"] = df["return_3d"] > 15

    df["is_5d_momentum"] = (df["return_5d"] >= 5) & (df["return_5d"] <= 25)
    df["is_5d_extended"] = df["return_5d"] > 25

    df["is_healthy_gain"] = (df["change_pct"] >= 2) & (df["change_pct"] <= 10)
    df["is_extended_today"] = df["change_pct"] > 10

    return df


def add_volatility_features(df: pd.DataFrame) -> pd.DataFrame:
    group = df.groupby("symbol")

    prev_close = group["close"].shift(1)

    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - prev_close).abs()
    tr3 = (df["low"] - prev_close).abs()

    df["true_range"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    df["atr"] = df.groupby("symbol")["true_range"].transform(
        lambda x: x.rolling(14, min_periods=3).mean()
    )

    df["atr_percent"] = (df["atr"] / df["close"]) * 100
    df["atr_percent"] = df["atr_percent"].replace([np.inf, -np.inf], np.nan).fillna(0)

    df["intraday_range_pct"] = ((df["high"] - df["low"]) / df["close"]) * 100
    df["intraday_range_pct"] = df["intraday_range_pct"].replace([np.inf, -np.inf], np.nan).fillna(0)

    return df


def add_liquidity_features(df: pd.DataFrame) -> pd.DataFrame:
    df["value_traded"] = df["close"] * df["volume"]

    df["liquidity_score_raw"] = 50
    df.loc[df["value_traded"] >= 100000000, "liquidity_score_raw"] = 90
    df.loc[
        (df["value_traded"] >= 50000000) & (df["value_traded"] < 100000000),
        "liquidity_score_raw",
    ] = 80
    df.loc[
        (df["value_traded"] >= 20000000) & (df["value_traded"] < 50000000),
        "liquidity_score_raw",
    ] = 70
    df.loc[
        (df["value_traded"] >= 5000000) & (df["value_traded"] < 20000000),
        "liquidity_score_raw",
    ] = 60
    df.loc[df["value_traded"] < 1000000, "liquidity_score_raw"] = 30

    return df


def add_breakout_features(df: pd.DataFrame) -> pd.DataFrame:
    group = df.groupby("symbol")

    df["high_20"] = group["high"].transform(
        lambda x: x.rolling(20, min_periods=3).max()
    )
    df["low_20"] = group["low"].transform(
        lambda x: x.rolling(20, min_periods=3).min()
    )

    df["close_position"] = (
        (df["close"] - df["low_20"]) / (df["high_20"] - df["low_20"])
    ) * 100

    df["close_position"] = df["close_position"].replace(
        [np.inf, -np.inf],
        np.nan
    ).fillna(50).clip(0, 100)

    df["is_close_strong"] = df["close_position"] >= 70
    df["is_close_near_high"] = df["close_position"] >= 85

    df["breakout_20d"] = df["close"] >= df["high_20"]
    df["near_breakout_20d"] = df["close_position"] >= 85

    return df


def add_quality_flags(df: pd.DataFrame) -> pd.DataFrame:
    df["corporate_risk"] = (
        df["company"].astype(str).str.upper().str.contains("WINDING", na=False)
        | df["company"].astype(str).str.upper().str.contains("NON-COMPLIANT", na=False)
    )

    df["data_quality_score"] = 100
    df.loc[df["short_history_mode"], "data_quality_score"] -= 25
    df.loc[df["volume"] <= 0, "data_quality_score"] -= 30
    df.loc[df["close"] <= 0, "data_quality_score"] -= 40
    df.loc[df["corporate_risk"], "data_quality_score"] -= 40

    df["data_quality_score"] = df["data_quality_score"].clip(0, 100)

    return df