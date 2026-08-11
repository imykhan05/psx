import pandas as pd


class PortfolioEngineV3:
    VERSION = "portfolio_engine_v3_1_relaxed"

    def __init__(
        self,
        capital: float = 50000,
        max_positions: int = 3,
        max_exposure_pct: float = 0.70,
        min_position_value: float = 3500,
    ):
        self.capital = float(capital)
        self.max_positions = int(max_positions)
        self.max_exposure_pct = float(max_exposure_pct)
        self.min_position_value = float(min_position_value)

    def build(self, df: pd.DataFrame) -> dict:
        if df is None or df.empty:
            return self.empty("No data received")

        data = remove_duplicate_columns(df.copy())
        data = self.ensure_columns(data)
        data = self.normalize_numeric(data)

        candidates = data.apply(self.score_candidate, axis=1, result_type="expand")
        data = remove_duplicate_columns(pd.concat([data, candidates], axis=1))

        eligible = data[data["portfolio_eligible"] == True].copy()

        if eligible.empty:
            return self.empty("No eligible portfolio candidates after V3.1 filters")

        eligible = eligible.sort_values(
            ["portfolio_rank_score", "final_score", "buy_probability", "smart_money_score", "volume"],
            ascending=[False, False, False, False, False],
        ).reset_index(drop=True)

        selected = eligible.head(self.max_positions).copy()
        trades = self.allocate_positions(selected)

        used_capital = float(trades["investment"].sum()) if not trades.empty else 0
        max_loss = float(trades["max_loss"].sum()) if not trades.empty else 0
        expected_profit_t1 = float(trades["expected_profit_t1"].sum()) if not trades.empty else 0
        expected_profit_t2 = float(trades["expected_profit_t2"].sum()) if not trades.empty else 0

        return {
            "engine_version": self.VERSION,
            "mode": "AI_V5_RISK_CONTROLLED_RELAXED",
            "capital": round(self.capital, 2),
            "max_positions": self.max_positions,
            "max_exposure_pct": round(self.max_exposure_pct * 100, 2),
            "eligible_candidates": int(len(eligible)),
            "selected_positions": int(len(trades)),
            "used_capital": round(used_capital, 2),
            "cash_reserve": round(self.capital - used_capital, 2),
            "total_expected_profit_t1": round(expected_profit_t1, 2),
            "total_expected_profit_t2": round(expected_profit_t2, 2),
            "total_max_loss_to_sl": round(max_loss, 2),
            "portfolio_risk_pct": round((max_loss / self.capital) * 100, 2) if self.capital else 0,
            "trades": trades,
            "reason": "Portfolio generated successfully",
        }

    def score_candidate(self, row) -> pd.Series:
        final_decision = text(row, "final_decision")
        trade_action = text(row, "trade_action")
        entry_action = text(row, "entry_timing_action")
        risk_permission = text(row, "risk_permission")
        risk_action = text(row, "risk_action")
        risk_status = text(row, "risk_status")

        final_score = num(row, "final_score")
        buy_probability = num(row, "buy_probability")
        smart_money_score = num(row, "smart_money_score")
        accumulation_score = num(row, "accumulation_score")
        trade_validation_score = num(row, "trade_validation_score")
        entry_timing_score = num(row, "entry_timing_score")
        sector_score = num(row, "sector_score", num(row, "sector_strength_score", 50))
        market_score = num(row, "market_score", 50)
        liquidity_score = num(row, "liquidity_score_v4", num(row, "liquidity_score_raw", 50))
        volume_score = num(row, "volume_score_v4", num(row, "volume_strength", 50))
        risk_reward = num(row, "risk_reward_t1", 1.15)
        change_pct = num(row, "change_pct")
        close = num(row, "close")
        volume = num(row, "volume")

        reasons = []
        warnings = []
        eligible = True

        if final_decision not in ["STRONG BUY", "BUY"]:
            eligible = False
            warnings.append("AI decision not BUY")

        if trade_action in ["AVOID", "REJECTED"]:
            eligible = False
            warnings.append("Trade validation rejected")

        # Relaxed: 70 instead of 75
        if trade_validation_score < 70:
            eligible = False
            warnings.append("Trade validation score below 70")

        if entry_action in ["NO TRADE", "WATCH ONLY"]:
            eligible = False
            warnings.append("Entry timing rejected")

        # Relaxed: do not reject every NO TRADE from risk engine if AI/entry/validation are strong.
        hard_risk_reject = (
            risk_permission == "NO TRADE"
            and risk_action == "AVOID"
            and risk_status in ["REJECTED", "CHASE RISK REJECTED"]
            and entry_timing_score < 90
        )

        if hard_risk_reject:
            eligible = False
            warnings.append("Risk engine hard rejected")

        if close <= 0:
            eligible = False
            warnings.append("Invalid close price")

        if volume <= 0:
            eligible = False
            warnings.append("Invalid volume")

        if risk_reward < 1.05:
            eligible = False
            warnings.append("Risk/reward below minimum")

        if risk_permission in ["WAIT", "TRADE ALLOWED SMALL", "NO TRADE"]:
            warnings.append("Controlled/small allocation only")

        if entry_action in ["WAIT PULLBACK", "BUY ON DIP", "BUY ABOVE BREAKOUT"]:
            warnings.append("Entry requires patience/confirmation")

        if risk_reward < 1.25:
            warnings.append("Risk/reward weak but acceptable for controlled allocation")

        if change_pct >= 9.8:
            warnings.append("Near upper cap; avoid chasing")

        rank_score = (
            final_score * 0.30
            + buy_probability * 0.20
            + smart_money_score * 0.14
            + trade_validation_score * 0.13
            + entry_timing_score * 0.10
            + sector_score * 0.05
            + market_score * 0.04
            + liquidity_score * 0.02
            + volume_score * 0.02
        )

        if risk_permission == "TRADE ALLOWED":
            rank_score += 5
            reasons.append("Risk allowed trade")
        elif risk_permission == "TRADE ALLOWED SMALL":
            rank_score += 2
            reasons.append("Risk allowed small trade")
        elif risk_permission == "WAIT":
            rank_score -= 3
            reasons.append("Risk suggests controlled entry")
        elif risk_permission == "NO TRADE":
            rank_score -= 6
            warnings.append("Risk says no trade; allowed only if setup is strong")

        if entry_action == "BUY NOW":
            rank_score += 6
            reasons.append("Entry timing BUY NOW")
        elif entry_action == "BUY ON DIP":
            rank_score += 3
            reasons.append("Buy on dip setup")
        elif entry_action == "WAIT PULLBACK":
            rank_score -= 1
            reasons.append("Wait pullback setup")
        elif entry_action == "BUY ABOVE BREAKOUT":
            rank_score += 1
            reasons.append("Breakout confirmation setup")

        if risk_reward >= 1.8:
            rank_score += 6
        elif risk_reward >= 1.4:
            rank_score += 2
        elif risk_reward < 1.25:
            rank_score -= 3

        if change_pct >= 9.8:
            rank_score -= 8
        elif change_pct >= 7:
            rank_score -= 3

        if smart_money_score >= 80:
            rank_score += 3
        if accumulation_score >= 80:
            rank_score += 2

        rank_score = round(max(min(rank_score, 100), 0), 2)

        return pd.Series({
            "portfolio_eligible": bool(eligible),
            "portfolio_rank_score": rank_score,
            "portfolio_reason": " | ".join(reasons),
            "portfolio_warning": " | ".join(warnings),
        })

    def allocate_positions(self, selected: pd.DataFrame) -> pd.DataFrame:
        if selected is None or selected.empty:
            return pd.DataFrame()

        total_exposure = self.capital * self.max_exposure_pct
        max_position_value = total_exposure / max(len(selected), 1)

        trades = []

        for _, row in selected.iterrows():
            close = num(row, "close")
            entry_low = num(row, "entry_low", close * 0.985)
            entry_high = num(row, "entry_high", close * 1.01)
            stop_loss = num(row, "stop_loss", close * 0.94)
            target_1 = num(row, "target_1", close * 1.08)
            target_2 = num(row, "target_2", close * 1.14)

            suggested_entry = num(row, "adjusted_entry_price", num(row, "suggested_entry_price", entry_high))
            if suggested_entry <= 0:
                suggested_entry = entry_high if entry_high > 0 else close

            risk_permission = text(row, "risk_permission")
            entry_action = text(row, "entry_timing_action")
            change_pct = num(row, "change_pct")
            risk_factor = num(row, "position_risk_factor", 1)

            allocation_factor = self.allocation_factor(row, risk_permission, entry_action, change_pct, risk_factor)
            allocation = min(max_position_value * allocation_factor, max_position_value)

            if allocation < self.min_position_value:
                allocation = self.min_position_value

            quantity = int(allocation // suggested_entry) if suggested_entry > 0 else 0
            investment = round(quantity * suggested_entry, 2)

            if quantity <= 0 or investment <= 0:
                continue

            risk_per_share = max(suggested_entry - stop_loss, 0)
            max_loss = round(quantity * risk_per_share, 2)
            expected_profit_t1 = round(quantity * max(target_1 - suggested_entry, 0), 2)
            expected_profit_t2 = round(quantity * max(target_2 - suggested_entry, 0), 2)

            trades.append({
                "rank": len(trades) + 1,
                "symbol": row.get("symbol", ""),
                "company": row.get("company", ""),
                "sector": row.get("sector", "UNKNOWN"),
                "industry": row.get("industry", "UNKNOWN"),
                "final_decision": row.get("final_decision", ""),
                "final_score": num(row, "final_score"),
                "buy_probability": num(row, "buy_probability"),
                "smart_money_score": num(row, "smart_money_score"),
                "accumulation_score": num(row, "accumulation_score"),
                "trade_validation_score": num(row, "trade_validation_score"),
                "entry_timing_score": num(row, "entry_timing_score"),
                "risk_management_score": num(row, "risk_management_score"),
                "risk_permission": row.get("risk_permission", ""),
                "risk_status": row.get("risk_status", ""),
                "entry_timing_action": row.get("entry_timing_action", ""),
                "portfolio_rank_score": num(row, "portfolio_rank_score"),
                "portfolio_reason": row.get("portfolio_reason", ""),
                "portfolio_warning": row.get("portfolio_warning", ""),
                "allocation_factor": round(allocation_factor, 2),
                "allocation": round(allocation, 2),
                "quantity": quantity,
                "final_quantity": quantity,
                "suggested_entry_price": round(suggested_entry, 2),
                "adjusted_entry_price": round(suggested_entry, 2),
                "investment": investment,
                "entry_low": round(entry_low, 2),
                "entry_high": round(entry_high, 2),
                "stop_loss": round(stop_loss, 2),
                "target_1": round(target_1, 2),
                "target_2": round(target_2, 2),
                "risk_per_share": round(risk_per_share, 2),
                "max_loss": max_loss,
                "expected_profit_t1": expected_profit_t1,
                "expected_profit_t2": expected_profit_t2,
                "risk_reward_t1": num(row, "risk_reward_t1"),
                "risk_pct_of_capital": round((max_loss / self.capital) * 100, 2) if self.capital else 0,
                "position_pct_of_capital": round((investment / self.capital) * 100, 2) if self.capital else 0,
                "holding_days": row.get("holding_days", "1-3 days"),
                "position_status": self.position_status(risk_permission, entry_action),
                "position_reason": self.position_reason(row),
            })

        trades_df = pd.DataFrame(trades)

        if not trades_df.empty:
            trades_df = trades_df.sort_values(
                ["portfolio_rank_score", "final_score", "buy_probability"],
                ascending=[False, False, False],
            ).reset_index(drop=True)
            trades_df["rank"] = range(1, len(trades_df) + 1)

        return trades_df

    def allocation_factor(self, row, risk_permission, entry_action, change_pct, risk_factor):
        factor = 1.0

        if risk_permission == "TRADE ALLOWED":
            factor *= 1.0
        elif risk_permission == "TRADE ALLOWED SMALL":
            factor *= 0.80
        elif risk_permission == "WAIT":
            factor *= 0.70
        elif risk_permission == "NO TRADE":
            factor *= 0.45

        if entry_action == "BUY NOW":
            factor *= 1.0
        elif entry_action == "BUY ON DIP":
            factor *= 0.85
        elif entry_action == "WAIT PULLBACK":
            factor *= 0.65
        elif entry_action == "BUY ABOVE BREAKOUT":
            factor *= 0.60

        if change_pct >= 9.8:
            factor *= 0.45
        elif change_pct >= 7:
            factor *= 0.70
        elif change_pct >= 4:
            factor *= 0.88

        factor *= max(min(risk_factor, 1.3), 0.35)
        return max(min(factor, 1.0), 0.25)

    def position_status(self, risk_permission, entry_action):
        if risk_permission == "WAIT":
            return "CONTROLLED / SMALL ENTRY"
        if entry_action in ["WAIT PULLBACK", "BUY ON DIP"]:
            return "WAIT ENTRY LEVEL"
        if entry_action == "BUY NOW":
            return "READY TO BUY"
        return "CONTROLLED"

    def position_reason(self, row):
        parts = []
        for col in ["portfolio_reason", "portfolio_warning", "risk_management_warnings", "entry_timing_warning"]:
            value = str(row.get(col, "")).strip()
            if value and value.lower() != "nan":
                parts.append(value)
        return " | ".join(parts)

    def ensure_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        defaults = {
            "symbol": "",
            "company": "",
            "sector": "UNKNOWN",
            "industry": "UNKNOWN",
            "close": 0,
            "change_pct": 0,
            "volume": 0,
            "final_decision": "",
            "final_score": 0,
            "buy_probability": 0,
            "sell_probability": 0,
            "smart_money_score": 50,
            "accumulation_score": 50,
            "trade_validation_score": 0,
            "trade_validation_status": "",
            "trade_action": "",
            "entry_timing_score": 0,
            "entry_timing_action": "",
            "entry_timing_status": "",
            "risk_management_score": 50,
            "risk_permission": "",
            "risk_status": "",
            "risk_action": "",
            "position_risk_factor": 1,
            "risk_reward_t1": 1.2,
            "sector_score": 50,
            "sector_strength_score": 50,
            "market_score": 50,
            "liquidity_score_v4": 50,
            "liquidity_score_raw": 50,
            "volume_score_v4": 50,
            "volume_strength": 50,
            "entry_low": 0,
            "entry_high": 0,
            "stop_loss": 0,
            "target_1": 0,
            "target_2": 0,
            "adjusted_entry_price": 0,
            "suggested_entry_price": 0,
            "holding_days": "1-3 days",
        }

        for col, default in defaults.items():
            if col not in df.columns:
                df[col] = default

        return df

    def normalize_numeric(self, df: pd.DataFrame) -> pd.DataFrame:
        numeric_cols = [
            "close", "change_pct", "volume", "final_score", "buy_probability",
            "sell_probability", "smart_money_score", "accumulation_score",
            "trade_validation_score", "entry_timing_score", "risk_management_score",
            "position_risk_factor", "risk_reward_t1", "sector_score",
            "sector_strength_score", "market_score", "liquidity_score_v4",
            "liquidity_score_raw", "volume_score_v4", "volume_strength",
            "entry_low", "entry_high", "stop_loss", "target_1", "target_2",
            "adjusted_entry_price", "suggested_entry_price",
        ]

        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        return df

    def empty(self, reason: str) -> dict:
        return {
            "engine_version": self.VERSION,
            "mode": "AI_V5_RISK_CONTROLLED_RELAXED",
            "capital": round(self.capital, 2),
            "max_positions": self.max_positions,
            "max_exposure_pct": round(self.max_exposure_pct * 100, 2),
            "eligible_candidates": 0,
            "selected_positions": 0,
            "used_capital": 0,
            "cash_reserve": round(self.capital, 2),
            "total_expected_profit_t1": 0,
            "total_expected_profit_t2": 0,
            "total_max_loss_to_sl": 0,
            "portfolio_risk_pct": 0,
            "trades": pd.DataFrame(),
            "reason": reason,
        }


def build_portfolio_plan_v3(
    final_df: pd.DataFrame,
    capital: float = 50000,
    max_positions: int = 3,
    max_exposure_pct: float = 0.70,
    min_position_value: float = 3500,
) -> dict:
    engine = PortfolioEngineV3(
        capital=capital,
        max_positions=max_positions,
        max_exposure_pct=max_exposure_pct,
        min_position_value=min_position_value,
    )
    return engine.build(final_df)


def remove_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    return df.loc[:, ~df.columns.duplicated()].copy()


def num(row, key: str, default: float = 0) -> float:
    value = row.get(key, default)
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    try:
        return float(value)
    except Exception:
        return default


def text(row, key: str, default: str = "") -> str:
    value = row.get(key, default)
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    return str(value).strip().upper()