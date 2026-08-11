import pandas as pd


class BacktestEngine:
    def __init__(self, history: pd.DataFrame):
        self.history = history.copy()
        self.history["date_parsed"] = pd.to_datetime(
            self.history["date_parsed"],
            errors="coerce"
        )
        self.history = self.history.sort_values(["symbol", "date_parsed"])

    def add_future_returns(self) -> pd.DataFrame:
        df = self.history.copy()

        for days in [1, 2, 3, 5, 10]:
            df[f"future_close_{days}d"] = df.groupby("symbol")["close"].shift(-days)

            df[f"future_return_{days}d"] = (
                (df[f"future_close_{days}d"] - df["close"])
                / df["close"]
                * 100
            ).round(2)

        return df

    def create_basic_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        signals = df[
            (df["change_pct"] >= 2)
            & (df["volume"] >= 100000)
        ].copy()

        return signals

    def simulate_signals(self, signal_df: pd.DataFrame) -> pd.DataFrame:
        df = signal_df.copy()

        for days in [1, 2, 3, 5, 10]:
            col = f"future_return_{days}d"
            if col in df.columns:
                df[f"bt_win_{days}d"] = df[col] > 0

        df["bt_result_1d"] = df["future_return_1d"].apply(self.result_label)
        df["bt_result_3d"] = df["future_return_3d"].apply(self.result_label)
        df["bt_result_5d"] = df["future_return_5d"].apply(self.result_label)

        return df

    def result_label(self, value):
        if pd.isna(value):
            return "NO DATA"
        if value >= 8:
            return "TARGET HIT"
        if value <= -5:
            return "STOP LOSS"
        if value > 0:
            return "PROFIT"
        return "LOSS"

    def summary_for_days(self, result_df: pd.DataFrame, days: int) -> dict:
        col = f"future_return_{days}d"

        df = result_df.dropna(subset=[col]).copy()

        if df.empty:
            return {
                "days": days,
                "total_trades": 0,
                "win_rate": 0,
                "avg_return": 0,
                "best_return": 0,
                "worst_return": 0
            }

        wins = (df[col] > 0).sum()
        total = len(df)

        return {
            "days": days,
            "total_trades": int(total),
            "win_rate": round((wins / total) * 100, 2),
            "avg_return": round(df[col].mean(), 2),
            "best_return": round(df[col].max(), 2),
            "worst_return": round(df[col].min(), 2)
        }

    def full_summary(self, result_df: pd.DataFrame) -> pd.DataFrame:
        rows = []

        for days in [1, 2, 3, 5, 10]:
            rows.append(self.summary_for_days(result_df, days))

        return pd.DataFrame(rows)

    def run_basic_backtest(self):
        df = self.add_future_returns()
        signals = self.create_basic_signals(df)
        result = self.simulate_signals(signals)
        summary = self.full_summary(result)

        return result, summary