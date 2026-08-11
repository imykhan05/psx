import pandas as pd


class PositionSizingEngine:
    """
    Position Sizing Engine V1

    Purpose:
    Convert portfolio trades into risk-based institutional position sizes.

    It uses:
    - total capital
    - maximum portfolio exposure
    - risk per trade
    - stop loss distance
    - entry price
    - validation score
    - risk/reward
    - liquidity
    """

    def __init__(
        self,
        capital: float = 50000,
        max_exposure_pct: float = 0.60,
        risk_per_trade_pct: float = 0.015,
        max_position_pct: float = 0.30,
    ):
        self.capital = float(capital)
        self.max_exposure_pct = float(max_exposure_pct)
        self.risk_per_trade_pct = float(risk_per_trade_pct)
        self.max_position_pct = float(max_position_pct)

    def apply(self, portfolio: dict) -> dict:
        if not portfolio or "trades" not in portfolio:
            return portfolio

        trades = portfolio.get("trades")

        if trades is None or trades.empty:
            return portfolio

        sized_trades = self.size_trades(trades)

        used_capital = round(sized_trades["investment"].sum(), 2)
        cash_reserve = round(self.capital - used_capital, 2)

        total_expected_profit_t1 = round(sized_trades["expected_profit_t1"].sum(), 2)
        total_max_loss_to_sl = round(sized_trades["max_loss"].sum(), 2)

        portfolio["position_sizing_engine"] = "position_sizing_engine_v1"
        portfolio["risk_per_trade_pct"] = self.risk_per_trade_pct * 100
        portfolio["max_position_pct"] = self.max_position_pct * 100
        portfolio["used_capital"] = used_capital
        portfolio["cash_reserve"] = cash_reserve
        portfolio["total_expected_profit_t1"] = total_expected_profit_t1
        portfolio["total_max_loss_to_sl"] = total_max_loss_to_sl
        portfolio["portfolio_risk_pct"] = round(
            (total_max_loss_to_sl / self.capital) * 100,
            2,
        ) if self.capital > 0 else 0
        portfolio["trades"] = sized_trades

        return portfolio

    def size_trades(self, trades: pd.DataFrame) -> pd.DataFrame:
        result = trades.copy()

        result = self.ensure_columns(result)

        available_exposure = self.capital * self.max_exposure_pct
        max_position_value = self.capital * self.max_position_pct
        max_risk_per_trade = self.capital * self.risk_per_trade_pct

        rows = []
        used_exposure = 0

        for _, row in result.iterrows():
            entry_price = safe_float(row.get("entry_high", row.get("close", 0)))
            stop_loss = safe_float(row.get("stop_loss", 0))
            target_1 = safe_float(row.get("target_1", 0))
            target_2 = safe_float(row.get("target_2", 0))

            if entry_price <= 0 or stop_loss <= 0 or stop_loss >= entry_price:
                sized = self.zero_trade(row, "Invalid entry/stop loss")
                rows.append(sized)
                continue

            risk_per_share = entry_price - stop_loss

            validation_score = safe_float(row.get("trade_validation_score", row.get("final_score", 75)))
            risk_reward = safe_float(row.get("risk_reward_t1", 1.2))
            liquidity_score = safe_float(row.get("liquidity_score_v4", 70))
            final_score = safe_float(row.get("final_score", 0))
            buy_probability = safe_float(row.get("buy_probability", 0))

            risk_multiplier = self.risk_multiplier(
                validation_score=validation_score,
                risk_reward=risk_reward,
                liquidity_score=liquidity_score,
                final_score=final_score,
                buy_probability=buy_probability,
            )

            allowed_trade_risk = max_risk_per_trade * risk_multiplier

            qty_by_risk = int(allowed_trade_risk // risk_per_share)
            qty_by_position_cap = int(max_position_value // entry_price)

            remaining_exposure = max(available_exposure - used_exposure, 0)
            qty_by_remaining_exposure = int(remaining_exposure // entry_price)

            final_qty = min(qty_by_risk, qty_by_position_cap, qty_by_remaining_exposure)

            if final_qty <= 0:
                sized = self.zero_trade(row, "Position rejected by risk/exposure limits")
                rows.append(sized)
                continue

            investment = round(final_qty * entry_price, 2)
            max_loss = round(final_qty * risk_per_share, 2)
            expected_profit_t1 = round(max((target_1 - entry_price) * final_qty, 0), 2)
            expected_profit_t2 = round(max((target_2 - entry_price) * final_qty, 0), 2)

            used_exposure += investment

            risk_pct_of_capital = round((max_loss / self.capital) * 100, 2) if self.capital > 0 else 0
            position_pct_of_capital = round((investment / self.capital) * 100, 2) if self.capital > 0 else 0

            sized = row.to_dict()
            sized.update({
                "position_engine_version": "position_sizing_engine_v1",
                "sizing_method": "RISK_BASED",
                "risk_multiplier": round(risk_multiplier, 2),
                "risk_per_share": round(risk_per_share, 2),
                "allowed_trade_risk": round(allowed_trade_risk, 2),
                "risk_based_quantity": qty_by_risk,
                "max_position_quantity": qty_by_position_cap,
                "final_quantity": final_qty,
                "quantity": final_qty,
                "investment": investment,
                "max_loss": max_loss,
                "expected_profit_t1": expected_profit_t1,
                "expected_profit_t2": expected_profit_t2,
                "risk_pct_of_capital": risk_pct_of_capital,
                "position_pct_of_capital": position_pct_of_capital,
                "position_status": "APPROVED",
                "position_reason": "Risk-based position approved",
            })

            rows.append(sized)

        if not rows:
            return pd.DataFrame()

        return pd.DataFrame(rows)

    def risk_multiplier(
        self,
        validation_score: float,
        risk_reward: float,
        liquidity_score: float,
        final_score: float,
        buy_probability: float,
    ) -> float:
        multiplier = 1.0

        if validation_score >= 90:
            multiplier += 0.25
        elif validation_score >= 80:
            multiplier += 0.10
        elif validation_score < 70:
            multiplier -= 0.25

        if final_score >= 90:
            multiplier += 0.15
        elif final_score >= 85:
            multiplier += 0.08
        elif final_score < 75:
            multiplier -= 0.20

        if buy_probability >= 85:
            multiplier += 0.10
        elif buy_probability < 70:
            multiplier -= 0.15

        if liquidity_score >= 85:
            multiplier += 0.10
        elif liquidity_score < 60:
            multiplier -= 0.20

        if risk_reward >= 2.0:
            multiplier += 0.20
        elif risk_reward >= 1.5:
            multiplier += 0.10
        elif risk_reward < 1.2:
            multiplier -= 0.15

        return max(min(multiplier, 1.5), 0.4)

    def zero_trade(self, row, reason: str) -> dict:
        sized = row.to_dict()
        sized.update({
            "position_engine_version": "position_sizing_engine_v1",
            "sizing_method": "RISK_BASED",
            "risk_multiplier": 0,
            "risk_per_share": 0,
            "allowed_trade_risk": 0,
            "risk_based_quantity": 0,
            "max_position_quantity": 0,
            "final_quantity": 0,
            "quantity": 0,
            "investment": 0,
            "max_loss": 0,
            "expected_profit_t1": 0,
            "expected_profit_t2": 0,
            "risk_pct_of_capital": 0,
            "position_pct_of_capital": 0,
            "position_status": "REJECTED",
            "position_reason": reason,
        })

        return sized

    def ensure_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        defaults = {
            "symbol": "",
            "company": "",
            "sector": "UNKNOWN",
            "close": 0,
            "entry_high": 0,
            "stop_loss": 0,
            "target_1": 0,
            "target_2": 0,
            "final_score": 0,
            "buy_probability": 0,
            "trade_validation_score": 75,
            "risk_reward_t1": 1.2,
            "liquidity_score_v4": 70,
        }

        for col, default in defaults.items():
            if col not in df.columns:
                df[col] = default

        return df


def apply_position_sizing(
    portfolio: dict,
    capital: float = 50000,
    max_exposure_pct: float = 0.60,
    risk_per_trade_pct: float = 0.015,
    max_position_pct: float = 0.30,
) -> dict:
    engine = PositionSizingEngine(
        capital=capital,
        max_exposure_pct=max_exposure_pct,
        risk_per_trade_pct=risk_per_trade_pct,
        max_position_pct=max_position_pct,
    )

    return engine.apply(portfolio)


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