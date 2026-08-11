import numpy as np
import pandas as pd


def build_features_v3(history: pd.DataFrame, latest_date: str) -> pd.DataFrame:
    all_features = build_historical_features_v3(history)
    return all_features[all_features["date"] == latest_date].copy()


def build_historical_features_v3(history: pd.DataFrame) -> pd.DataFrame:
    df = history.copy()

    df["date_parsed"] = pd.to_datetime(df["date_parsed"], errors="coerce")
    df = df.sort_values(["symbol", "date_parsed"]).reset_index(drop=True)

    df = add_base_columns(df)
    df = add_history_flags(df)
    df = add_return_features(df)
    df = add_moving_averages(df)
    df = add_rsi(df)
    df = add_macd(df)
    df = add_atr(df)
    df = add_adx(df)
    df = add_volume_features(df)
    df = add_liquidity_features(df)
    df = add_breakout_features(df)
    df = add_bollinger_features(df)
    df = add_strength_scores(df)
    df = add_quality_flags(df)

    df = df.replace([np.inf, -np.inf], np.nan)

    return df


def add_base_columns(df: pd.DataFrame) -> pd.DataFrame:
    required = ["open", "high", "low", "close", "volume", "change_pct"]

    for col in required:
        if col not in df.columns:
            df[col] = 0

        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if "company" not in df.columns:
        df["company"] = ""

    return df


def add_history_flags(df: pd.DataFrame) -> pd.DataFrame:
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
    df["return_50d"] = group["close"].pct_change(50) * 100

    df["change_percent"] = df["change_pct"]
    df["pct_change"] = df["change_pct"]

    for col in [
        "return_1d",
        "return_3d",
        "return_5d",
        "return_10d",
        "return_20d",
        "return_50d",
    ]:
        df[col] = df[col].fillna(0)

    return df


def add_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    group = df.groupby("symbol")

    df["sma_5"] = group["close"].transform(lambda x: x.rolling(5, min_periods=2).mean())
    df["sma_10"] = group["close"].transform(lambda x: x.rolling(10, min_periods=3).mean())
    df["sma_20"] = group["close"].transform(lambda x: x.rolling(20, min_periods=3).mean())
    df["sma_50"] = group["close"].transform(lambda x: x.rolling(50, min_periods=5).mean())
    df["sma_100"] = group["close"].transform(lambda x: x.rolling(100, min_periods=10).mean())
    df["sma_200"] = group["close"].transform(lambda x: x.rolling(200, min_periods=20).mean())

    df["ema_5"] = group["close"].transform(lambda x: x.ewm(span=5, adjust=False, min_periods=2).mean())
    df["ema_10"] = group["close"].transform(lambda x: x.ewm(span=10, adjust=False, min_periods=3).mean())
    df["ema_20"] = group["close"].transform(lambda x: x.ewm(span=20, adjust=False, min_periods=3).mean())
    df["ema_50"] = group["close"].transform(lambda x: x.ewm(span=50, adjust=False, min_periods=5).mean())
    df["ema_100"] = group["close"].transform(lambda x: x.ewm(span=100, adjust=False, min_periods=10).mean())
    df["ema_200"] = group["close"].transform(lambda x: x.ewm(span=200, adjust=False, min_periods=20).mean())

    for col in [
        "sma_5", "sma_10", "sma_20", "sma_50", "sma_100", "sma_200",
        "ema_5", "ema_10", "ema_20", "ema_50", "ema_100", "ema_200",
    ]:
        df[col] = df[col].fillna(df["close"])

    df["price_above_ema20"] = df["close"] > df["ema_20"]
    df["price_above_ema50"] = df["close"] > df["ema_50"]
    df["price_above_ema100"] = df["close"] > df["ema_100"]
    df["price_above_ema200"] = df["close"] > df["ema_200"]

    df["ema20_above_ema50"] = df["ema_20"] > df["ema_50"]
    df["ema50_above_ema100"] = df["ema_50"] > df["ema_100"]
    df["ema100_above_ema200"] = df["ema_100"] > df["ema_200"]

    df["ema20_slope"] = group["ema_20"].diff(3).fillna(0)
    df["ema50_slope"] = group["ema_50"].diff(5).fillna(0)

    return df


def add_rsi(df: pd.DataFrame) -> pd.DataFrame:
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

    return df


def add_macd(df: pd.DataFrame) -> pd.DataFrame:
    group = df.groupby("symbol")

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
    df["macd_hist"] = (df["macd"] - df["macd_signal"]).fillna(0)
    df["macd_bullish"] = df["macd_hist"] > 0

    return df


def add_atr(df: pd.DataFrame) -> pd.DataFrame:
    group = df.groupby("symbol")
    prev_close = group["close"].shift(1)

    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - prev_close).abs()
    tr3 = (df["low"] - prev_close).abs()

    df["true_range"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    df["atr"] = df.groupby("symbol")["true_range"].transform(
        lambda x: x.rolling(14, min_periods=3).mean()
    )

    df["atr"] = df["atr"].fillna(df["true_range"]).fillna(0)
    df["atr_percent"] = ((df["atr"] / df["close"]) * 100).replace([np.inf, -np.inf], np.nan).fillna(0)

    df["intraday_range_pct"] = (((df["high"] - df["low"]) / df["close"]) * 100).replace(
        [np.inf, -np.inf],
        np.nan
    ).fillna(0)

    return df


def add_adx(df: pd.DataFrame) -> pd.DataFrame:
    group = df.groupby("symbol")

    high_diff = group["high"].diff()
    low_diff = -group["low"].diff()

    plus_dm = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
    minus_dm = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)

    df["plus_dm"] = plus_dm
    df["minus_dm"] = minus_dm

    atr = df["atr"].replace(0, np.nan)

    df["plus_di"] = 100 * df.groupby("symbol")["plus_dm"].transform(
        lambda x: x.rolling(14, min_periods=3).mean()
    ) / atr

    df["minus_di"] = 100 * df.groupby("symbol")["minus_dm"].transform(
        lambda x: x.rolling(14, min_periods=3).mean()
    ) / atr

    dx = (
        (df["plus_di"] - df["minus_di"]).abs()
        / (df["plus_di"] + df["minus_di"]).replace(0, np.nan)
    ) * 100

    df["adx"] = dx.groupby(df["symbol"]).transform(
        lambda x: x.rolling(14, min_periods=3).mean()
    )

    df["plus_di"] = df["plus_di"].fillna(0).clip(0, 100)
    df["minus_di"] = df["minus_di"].fillna(0).clip(0, 100)
    df["adx"] = df["adx"].fillna(20).clip(0, 100)

    return df


def add_volume_features(df: pd.DataFrame) -> pd.DataFrame:
    group = df.groupby("symbol")

    df["avg_volume_5"] = group["volume"].transform(lambda x: x.rolling(5, min_periods=2).mean())
    df["avg_volume"] = group["volume"].transform(lambda x: x.rolling(20, min_periods=3).mean())
    df["volume_avg"] = df["avg_volume"]
    df["volume_sma_20"] = df["avg_volume"]

    df["volume_ratio_5"] = (df["volume"] / df["avg_volume_5"]).replace([np.inf, -np.inf], np.nan).fillna(1)
    df["volume_ratio_20"] = (df["volume"] / df["avg_volume"]).replace([np.inf, -np.inf], np.nan).fillna(1)

    df["is_liquid"] = df["volume"] >= 300000
    df["is_highly_liquid"] = df["volume"] >= 1000000
    df["is_volume_spike"] = df["volume_ratio_5"] >= 1.5
    df["is_volume_expansion"] = df["volume_ratio_20"] >= 1.2

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

    df["high_20"] = group["high"].transform(lambda x: x.rolling(20, min_periods=3).max())
    df["low_20"] = group["low"].transform(lambda x: x.rolling(20, min_periods=3).min())

    df["high_52w"] = group["high"].transform(lambda x: x.rolling(252, min_periods=20).max())
    df["low_52w"] = group["low"].transform(lambda x: x.rolling(252, min_periods=20).min())

    df["close_position"] = (
        (df["close"] - df["low_20"]) / (df["high_20"] - df["low_20"])
    ) * 100

    df["close_position"] = df["close_position"].replace(
        [np.inf, -np.inf],
        np.nan
    ).fillna(50).clip(0, 100)

    df["position_52w"] = (
        (df["close"] - df["low_52w"]) / (df["high_52w"] - df["low_52w"])
    ) * 100

    df["position_52w"] = df["position_52w"].replace(
        [np.inf, -np.inf],
        np.nan
    ).fillna(df["close_position"]).clip(0, 100)

    df["is_close_strong"] = df["close_position"] >= 70
    df["is_close_near_high"] = df["close_position"] >= 85
    df["breakout_20d"] = df["close"] >= df["high_20"]
    df["near_breakout_20d"] = df["close_position"] >= 85

    return df


def add_bollinger_features(df: pd.DataFrame) -> pd.DataFrame:
    group = df.groupby("symbol")

    rolling_mean = group["close"].transform(lambda x: x.rolling(20, min_periods=3).mean())
    rolling_std = group["close"].transform(lambda x: x.rolling(20, min_periods=3).std())

    df["bb_middle"] = rolling_mean.fillna(df["close"])
    df["bb_upper"] = (rolling_mean + (2 * rolling_std)).fillna(df["close"])
    df["bb_lower"] = (rolling_mean - (2 * rolling_std)).fillna(df["close"])

    df["bb_position"] = (
        (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])
    ) * 100

    df["bb_position"] = df["bb_position"].replace(
        [np.inf, -np.inf],
        np.nan
    ).fillna(50).clip(0, 100)

    return df


def add_strength_scores(df: pd.DataFrame) -> pd.DataFrame:
    df["trend_strength"] = 50

    df.loc[df["price_above_ema20"], "trend_strength"] += 10
    df.loc[df["price_above_ema50"], "trend_strength"] += 12
    df.loc[df["ema20_above_ema50"], "trend_strength"] += 12
    df.loc[df["ema20_slope"] > 0, "trend_strength"] += 8
    df.loc[df["ema50_slope"] > 0, "trend_strength"] += 5
    df.loc[df["close_position"] >= 70, "trend_strength"] += 5
    df.loc[df["close_position"] <= 30, "trend_strength"] -= 10

    df["trend_strength"] = df["trend_strength"].clip(0, 100)

    df["momentum_strength"] = 50

    df.loc[(df["rsi"] >= 55) & (df["rsi"] <= 70), "momentum_strength"] += 15
    df.loc[(df["rsi"] > 70) & (df["rsi"] <= 80), "momentum_strength"] += 7
    df.loc[df["rsi"] > 80, "momentum_strength"] -= 8
    df.loc[df["rsi"] < 35, "momentum_strength"] -= 12
    df.loc[df["macd_bullish"], "momentum_strength"] += 10
    df.loc[df["return_3d"] > 0, "momentum_strength"] += 5
    df.loc[df["return_5d"] > 0, "momentum_strength"] += 5

    df["momentum_strength"] = df["momentum_strength"].clip(0, 100)

    df["volume_strength"] = 50

    df.loc[df["volume_ratio_20"] >= 2, "volume_strength"] += 30
    df.loc[
        (df["volume_ratio_20"] >= 1.5) & (df["volume_ratio_20"] < 2),
        "volume_strength",
    ] += 20
    df.loc[
        (df["volume_ratio_20"] >= 1.1) & (df["volume_ratio_20"] < 1.5),
        "volume_strength",
    ] += 10
    df.loc[df["volume_ratio_20"] < 0.7, "volume_strength"] -= 10

    df["volume_strength"] = df["volume_strength"].clip(0, 100)

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