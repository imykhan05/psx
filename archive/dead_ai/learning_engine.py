import pandas as pd


class LearningEngine:
    def __init__(self, backtest_df: pd.DataFrame):
        self.df = backtest_df.copy()

    def analyze_feature(self, feature_column: str, return_column: str = "future_return_3d") -> dict:
        if feature_column not in self.df.columns:
            return self.empty_result(feature_column, "MISSING", "No data")

        data = self.df.dropna(subset=[return_column]).copy()

        if data.empty:
            return self.empty_result(feature_column, "NO_DATA", "Need more history")

        active = data[data[feature_column] == True].copy()

        if active.empty:
            return self.empty_result(feature_column, "NO_ACTIVE_SIGNALS", "No active signals")

        wins = (active[return_column] > 0).sum()
        total = len(active)

        win_rate = round((wins / total) * 100, 2)
        avg_return = round(active[return_column].mean(), 2)
        best_return = round(active[return_column].max(), 2)
        worst_return = round(active[return_column].min(), 2)

        suggestion = self.get_suggestion(win_rate, avg_return, total)

        strength_score = round(
            (win_rate * 0.60) + (avg_return * 8),
            2
        )

        return {
            "feature": feature_column,
            "status": "OK",
            "total_trades": int(total),
            "win_rate": win_rate,
            "avg_return": avg_return,
            "best_return": best_return,
            "worst_return": worst_return,
            "strength_score": strength_score,
            "suggestion": suggestion
        }

    def get_suggestion(self, win_rate: float, avg_return: float, total: int) -> str:
        if total < 20:
            return "NEED_MORE_TRADES"

        if win_rate >= 62 and avg_return >= 3:
            return "STRONG_INCREASE"

        if win_rate >= 58 and avg_return >= 2:
            return "INCREASE_WEIGHT"

        if win_rate <= 45 or avg_return < 0:
            return "DECREASE_WEIGHT"

        return "KEEP_WEIGHT"

    def empty_result(self, feature, status, suggestion):
        return {
            "feature": feature,
            "status": status,
            "total_trades": 0,
            "win_rate": 0,
            "avg_return": 0,
            "best_return": 0,
            "worst_return": 0,
            "strength_score": 0,
            "suggestion": suggestion
        }

    def run_learning(self) -> pd.DataFrame:
        features = [
            "macd_bullish",
            "is_3d_momentum",
            "is_5d_momentum",
            "is_volume_spike",
            "is_close_strong",
            "is_close_near_high",
            "is_healthy_gain",
            "is_highly_liquid",
            "is_liquid"
        ]

        rows = []

        for feature in features:
            rows.append(self.analyze_feature(feature))

        return pd.DataFrame(rows).sort_values(
            ["strength_score", "win_rate", "avg_return"],
            ascending=False
        )