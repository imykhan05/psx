import pandas as pd


class PortfolioEngineV2:
    """
    Portfolio Engine V2

    Goal:
    Align portfolio allocation with AI Engine V4 / Decision Engine V2.

    Selection priority:
    1. STRONG BUY / BUY only
    2. Highest final_score
    3. Strong buy_probability
    4. High liquidity
    5. Low/medium risk
    6. Avoid poor quality / unknown risky securities
    """

    def __init__(
        self,
        capital: float = 50000,
        max_positions: int = 3,
        max_exposure_pct: float = 0.60,
    ):
        self.capital = float(capital)
        self.max_positions = int(max_positions)
        self.max_exposure_pct = float(max_exposure_pct)

    def build(self, df: pd.DataFrame) -> dict:
        if df is None or df.empty:
            return self.empty_plan("No data available")

        candidates = self.prepare_candidates(df)

        if candidates.empty:
            return self.empty_plan("No eligible BUY candidates found")

        trades = self.allocate(candidates)

        used_capital = round(trades["investment"].sum(), 2) if not trades.empty else 0
        cash_reserve = round(self.capital - used_capital, 2)

        total_expected_profit_t1 = (
            round(trades["expected_profit_t1"].sum(), 2)
            if "expected_profit_t1" in trades.columns and not trades.empty
            else 0
        )

        total_max_loss_to_sl = (
            round(trades["max_loss"].sum(), 2)
            if "max_loss" in trades.columns and not trades.empty
            else 0
        )

        return {
            "engine_version": "portfolio_engine_v2",
            "mode": "AI_ALIGNED",
            "capital": self.capital,
            "max_positions": self.max_positions,
            "max_exposure_pct": self.max_exposure_pct * 100,
            "eligible_candidates": len(candidates),
            "used_capital": used_capital,
            "cash_reserve": cash_reserve,
            "total_expected_profit_t1": total_expected_profit_t1,
            "total_max_loss_to_sl": total_max_loss_to_sl,
            "trades": trades,
        }

    def prepare_candidates(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()

        result = self.ensure_columns(result)

        result["final_score"] = pd.to_numeric(result["final_score"], errors="coerce").fillna(0)
        result["buy_probability"] = pd.to_numeric(result["buy_probability"], errors="coerce").fillna(0)
        result["sell_probability"] = pd.to_numeric(result["sell_probability"], errors="coerce").fillna(100)
        result["liquidity_score_v4"] = pd.to_numeric(result["liquidity_score_v4"], errors="coerce").fillna(0)
        result["volume"] = pd.to_numeric(result["volume"], errors="coerce").fillna(0)
        result["close"] = pd.to_numeric(result["close"], errors="coerce").fillna(0)
        result["risk_score_v4"] = pd.to_numeric(result["risk_score_v4"], errors="coerce").fillna(50)
        result["market_score_v4"] = pd.to_numeric(result["market_score_v4"], errors="coerce").fillna(50)
        result["sector_score_v4"] = pd.to_numeric(result["sector_score_v4"], errors="coerce").fillna(50)
        result["confidence_v3"] = pd.to_numeric(result["confidence_v3"], errors="coerce").fillna(50)
        result["atr_percent"] = pd.to_numeric(result["atr_percent"], errors="coerce").fillna(0)

        result["final_decision"] = result["final_decision"].astype(str).str.upper()
        result["verdict"] = result["verdict"].astype(str).str.upper()
        result["trend_label_v5"] = result["trend_label_v5"].astype(str).str.upper()
        result["risk_level"] = result["risk_level"].astype(str).str.upper()
        result["sector"] = result["sector"].astype(str).str.upper()

        buy_mask = result["final_decision"].isin(["STRONG BUY", "BUY"])
        score_mask = result["final_score"] >= 78
        probability_mask = result["buy_probability"] >= 75
        price_mask = result["close"] > 0
        liquidity_mask = result["liquidity_score_v4"] >= 55
        risk_mask = ~result["risk_level"].isin(["VERY HIGH", "EXTREME"])

        candidates = result[
            buy_mask
            & score_mask
            & probability_mask
            & price_mask
            & liquidity_mask
            & risk_mask
        ].copy()

        if candidates.empty:
            candidates = result[
                buy_mask
                & (result["final_score"] >= 70)
                & price_mask
                & liquidity_mask
            ].copy()

        if candidates.empty:
            return candidates

        candidates["portfolio_rank_score"] = self.calculate_rank_score(candidates)

        candidates = candidates.sort_values(
            by=[
                "portfolio_rank_score",
                "final_score",
                "buy_probability",
                "liquidity_score_v4",
                "volume",
            ],
            ascending=[False, False, False, False, False],
        ).reset_index(drop=True)

        return candidates

    def calculate_rank_score(self, df: pd.DataFrame) -> pd.Series:
        score = (
            (df["final_score"] * 0.35)
            + (df["buy_probability"] * 0.20)
            + (df["confidence_v3"] * 0.15)
            + (df["liquidity_score_v4"] * 0.10)
            + (df["market_score_v4"] * 0.08)
            + (df["sector_score_v4"] * 0.07)
        )

        score -= df["sell_probability"] * 0.05

        score += df["trend_label_v5"].apply(
            lambda x: 5 if "STRONG UPTREND" in x else 2 if "UPTREND" in x else 0
        )

        score += df["final_decision"].apply(
            lambda x: 4 if x == "STRONG BUY" else 2 if x == "BUY" else 0
        )

        score -= df["risk_level"].apply(
            lambda x: 8 if x == "HIGH" else 15 if x in ["VERY HIGH", "EXTREME"] else 0
        )

        score -= df["sector"].apply(
            lambda x: 3 if x in ["UNKNOWN", "", "NAN"] else 0
        )

        return score.round(2)

    def allocate(self, candidates: pd.DataFrame) -> pd.DataFrame:
        max_capital_to_use = self.capital * self.max_exposure_pct

        selected = candidates.head(self.max_positions).copy()

        if selected.empty:
            return selected

        weights = self.position_weights(len(selected))
        allocations = [round(max_capital_to_use * w, 2) for w in weights]

        rows = []

        for index, (_, row) in enumerate(selected.iterrows(), start=1):
            allocation = allocations[index - 1]
            close = float(row.get("close", 0))

            entry_low = safe_float(row.get("entry_low", close * 0.985))
            entry_high = safe_float(row.get("entry_high", close * 1.010))
            stop_loss = safe_float(row.get("stop_loss", close * 0.94))
            target_1 = safe_float(row.get("target_1", close * 1.07))
            target_2 = safe_float(row.get("target_2", close * 1.12))

            buy_price = entry_high if entry_high > 0 else close

            quantity = int(allocation // buy_price) if buy_price > 0 else 0
            investment = round(quantity * buy_price, 2)

            max_loss = round(max((buy_price - stop_loss) * quantity, 0), 2)
            expected_profit_t1 = round(max((target_1 - buy_price) * quantity, 0), 2)

            rows.append({
                "rank": index,
                "symbol": row.get("symbol", ""),
                "company": row.get("company", ""),
                "sector": row.get("sector", ""),
                "industry": row.get("industry", ""),
                "final_decision": row.get("final_decision", ""),
                "verdict": row.get("verdict", ""),
                "final_score": round(safe_float(row.get("final_score", 0)), 2),
                "portfolio_rank_score": round(safe_float(row.get("portfolio_rank_score", 0)), 2),
                "ai_score": round(safe_float(row.get("ai_score", 0)), 2),
                "buy_probability": round(safe_float(row.get("buy_probability", 0)), 2),
                "sell_probability": round(safe_float(row.get("sell_probability", 0)), 2),
                "confidence_v3": round(safe_float(row.get("confidence_v3", 0)), 2),
                "trend_score_v5": round(safe_float(row.get("trend_score_v5", 0)), 2),
                "trend_label_v5": row.get("trend_label_v5", ""),
                "liquidity_score_v4": round(safe_float(row.get("liquidity_score_v4", 0)), 2),
                "risk_level": row.get("risk_level", ""),
                "close": round(close, 2),
                "allocation": allocation,
                "quantity": quantity,
                "investment": investment,
                "max_loss": max_loss,
                "expected_profit_t1": expected_profit_t1,
                "entry_low": round(entry_low, 2),
                "entry_high": round(entry_high, 2),
                "stop_loss": round(stop_loss, 2),
                "target_1": round(target_1, 2),
                "target_2": round(target_2, 2),
                "holding_days": row.get("holding_days", "2-5 days"),
                "decision_reason": row.get("decision_reason", ""),
            })

        return pd.DataFrame(rows)

    def position_weights(self, count: int) -> list[float]:
        if count <= 1:
            return [1.0]

        if count == 2:
            return [0.60, 0.40]

        if count == 3:
            return [0.45, 0.35, 0.20]

        weight = round(1 / count, 4)
        return [weight] * count

    def ensure_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        defaults = {
            "symbol": "",
            "company": "",
            "sector": "UNKNOWN",
            "industry": "UNKNOWN",
            "close": 0,
            "volume": 0,
            "final_score": 0,
            "final_decision": "",
            "verdict": "",
            "buy_probability": 0,
            "sell_probability": 100,
            "confidence_v3": 50,
            "ai_score": 0,
            "trend_score_v5": 0,
            "trend_label_v5": "",
            "liquidity_score_v4": 0,
            "risk_score_v4": 50,
            "risk_level": "MEDIUM",
            "market_score_v4": 50,
            "sector_score_v4": 50,
            "entry_low": 0,
            "entry_high": 0,
            "stop_loss": 0,
            "target_1": 0,
            "target_2": 0,
            "holding_days": "2-5 days",
            "decision_reason": "",
            "atr_percent": 0,
        }

        for col, default in defaults.items():
            if col not in df.columns:
                df[col] = default

        return df

    def empty_plan(self, reason: str) -> dict:
        return {
            "engine_version": "portfolio_engine_v2",
            "mode": "AI_ALIGNED",
            "capital": self.capital,
            "max_positions": self.max_positions,
            "max_exposure_pct": self.max_exposure_pct * 100,
            "eligible_candidates": 0,
            "used_capital": 0,
            "cash_reserve": self.capital,
            "total_expected_profit_t1": 0,
            "total_max_loss_to_sl": 0,
            "reason": reason,
            "trades": pd.DataFrame(),
        }


def build_portfolio_plan_v2(
    df: pd.DataFrame,
    capital: float = 50000,
    max_positions: int = 3,
    max_exposure_pct: float = 0.60,
) -> dict:
    engine = PortfolioEngineV2(
        capital=capital,
        max_positions=max_positions,
        max_exposure_pct=max_exposure_pct,
    )

    return engine.build(df)


def safe_float(value, default: float = 0) -> float:
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    try:
        return float(value)
    except Exception:
        return default