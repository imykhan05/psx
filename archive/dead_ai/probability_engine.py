import pandas as pd


class ProbabilityEngine:
    def __init__(self, backtest_df: pd.DataFrame):
        self.df = backtest_df.copy()

    def calculate_probability_for_feature(
        self,
        feature_column: str,
        return_column: str = "future_return_3d"
    ) -> dict:
        if feature_column not in self.df.columns:
            return self.empty_result(feature_column, "MISSING")

        data = self.df.dropna(subset=[return_column]).copy()

        if data.empty:
            return self.empty_result(feature_column, "NO_DATA")

        active = data[data[feature_column] == True].copy()

        if active.empty:
            return self.empty_result(feature_column, "NO_ACTIVE_SIGNALS")

        total = len(active)

        target_hit = (active[return_column] >= 5).sum()
        profit = (active[return_column] > 0).sum()
        stop_loss = (active[return_column] <= -3).sum()

        target_probability = round((target_hit / total) * 100, 2)
        profit_probability = round((profit / total) * 100, 2)
        stop_loss_probability = round((stop_loss / total) * 100, 2)

        avg_return = round(active[return_column].mean(), 2)
        avg_win = round(active[active[return_column] > 0][return_column].mean(), 2)
        avg_loss = round(active[active[return_column] <= 0][return_column].mean(), 2)

        expected_value = round(
            (profit_probability / 100 * avg_win)
            + (stop_loss_probability / 100 * avg_loss),
            2
        )

        confidence = self.calculate_confidence(total, profit_probability, avg_return)

        return {
            "feature": feature_column,
            "status": "OK",
            "total_trades": int(total),
            "profit_probability": profit_probability,
            "target_probability": target_probability,
            "stop_loss_probability": stop_loss_probability,
            "avg_return": avg_return,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "expected_value": expected_value,
            "probability_confidence": confidence
        }

    def calculate_confidence(self, total: int, probability: float, avg_return: float) -> int:
        confidence = 40

        if total >= 30:
            confidence += 20
        elif total >= 15:
            confidence += 10

        if probability >= 60:
            confidence += 20
        elif probability >= 55:
            confidence += 10

        if avg_return >= 3:
            confidence += 15
        elif avg_return >= 1.5:
            confidence += 8

        return int(max(min(confidence, 100), 0))

    def run_probability_analysis(self) -> pd.DataFrame:
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
            rows.append(self.calculate_probability_for_feature(feature))

        return pd.DataFrame(rows).sort_values(
            ["expected_value", "profit_probability", "target_probability"],
            ascending=False
        )

    def empty_result(self, feature: str, status: str) -> dict:
        return {
            "feature": feature,
            "status": status,
            "total_trades": 0,
            "profit_probability": 0,
            "target_probability": 0,
            "stop_loss_probability": 0,
            "avg_return": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "expected_value": 0,
            "probability_confidence": 0
        }