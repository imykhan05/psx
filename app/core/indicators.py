import pandas as pd


def add_indicators(history: pd.DataFrame) -> pd.DataFrame:
    df = history.copy()
    df["date_parsed"] = pd.to_datetime(df["date_parsed"], errors="coerce")
    df = df.sort_values(["symbol", "date_parsed"])

    grouped = df.groupby("symbol", group_keys=False)

    # EMA
    for span in [5, 9, 20, 50, 100, 200]:
        df[f"ema{span}"] = grouped["close"].transform(
            lambda x: x.ewm(span=span, adjust=False).mean()
        )

    # SMA
    for window in [20, 50, 100, 200]:
        df[f"sma{window}"] = grouped["close"].transform(
            lambda x: x.rolling(window, min_periods=1).mean()
        )

    # Volume averages
    df["vol_avg5"] = grouped["volume"].transform(lambda x: x.rolling(5, min_periods=1).mean())
    df["vol_avg20"] = grouped["volume"].transform(lambda x: x.rolling(20, min_periods=1).mean())
    df["volume_ratio_5"] = df["volume"] / df["vol_avg5"].replace(0, pd.NA)
    df["volume_ratio_20"] = df["volume"] / df["vol_avg20"].replace(0, pd.NA)

    # Returns
    for days in [1, 3, 5, 10, 20, 50, 100]:
        df[f"return_{days}d"] = grouped["close"].pct_change(days) * 100

    # RSI 14
    delta = grouped["close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.groupby(df["symbol"]).transform(lambda x: x.rolling(14, min_periods=14).mean())
    avg_loss = loss.groupby(df["symbol"]).transform(lambda x: x.rolling(14, min_periods=14).mean())

    rs = avg_gain / avg_loss.replace(0, pd.NA)
    df["rsi14"] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = grouped["close"].transform(lambda x: x.ewm(span=12, adjust=False).mean())
    ema26 = grouped["close"].transform(lambda x: x.ewm(span=26, adjust=False).mean())
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df.groupby("symbol")["macd"].transform(
        lambda x: x.ewm(span=9, adjust=False).mean()
    )
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # ATR 14
    prev_close = grouped["close"].shift(1)
    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - prev_close).abs()
    tr3 = (df["low"] - prev_close).abs()
    df["true_range"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["atr14"] = df.groupby("symbol")["true_range"].transform(
        lambda x: x.rolling(14, min_periods=1).mean()
    )

    # Bollinger Bands
    df["bb_mid"] = grouped["close"].transform(lambda x: x.rolling(20, min_periods=1).mean())
    df["bb_std"] = grouped["close"].transform(lambda x: x.rolling(20, min_periods=1).std())
    df["bb_upper"] = df["bb_mid"] + (df["bb_std"] * 2)
    df["bb_lower"] = df["bb_mid"] - (df["bb_std"] * 2)
    df["bb_width"] = ((df["bb_upper"] - df["bb_lower"]) / df["bb_mid"].replace(0, pd.NA)) * 100

    # Trend flags
    df["above_ema20"] = df["close"] > df["ema20"]
    df["above_ema50"] = df["close"] > df["ema50"]
    df["above_ema100"] = df["close"] > df["ema100"]
    df["above_ema200"] = df["close"] > df["ema200"]

    def momentum_status(row):
        r3 = row.get("return_3d")
        r5 = row.get("return_5d")
        vr = row.get("volume_ratio_5")

        if pd.isna(r3):
            return "NEW DATA"
        if r3 >= 15 and pd.notna(vr) and vr >= 1.5:
            return "STRONG MOMENTUM"
        if r3 >= 8:
            return "MOMENTUM"
        if r3 >= 3:
            return "BUILDING"
        if r3 <= -8:
            return "WEAK"
        return "NEUTRAL"

    df["momentum_status"] = df.apply(momentum_status, axis=1)

    return df


def get_latest_day(history_with_indicators: pd.DataFrame, latest_date: str) -> pd.DataFrame:
    return history_with_indicators[history_with_indicators["date"] == latest_date].copy()