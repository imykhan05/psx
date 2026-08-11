import pandas as pd


class PortfolioEngineV4:
    """
    Portfolio Engine V4.4 - Data Quality Firewall + Stock Only Risk Optimizer

    Drop-in replacement for:
        app/engines/portfolio_engine_v4.py

    main.py does NOT need to change if it already imports build_portfolio_plan_v4.

    Goals:
    - Exclude ETF / REIT / GIS / Treasury / Govt securities / bonds / sukuk
    - Block hard-risk symbols like JDMT by default
    - Block NO TRADE + HIGH RISK / CHASE RISK / REJECTED candidates
    - Block UNKNOWN sector + UNKNOWN industry unless symbol is explicitly allowed
    - Keep 50,000 capital safe by selecting only 1-3 stock-only controlled trades
    """

    VERSION = "portfolio_engine_v4_4_balanced_bullish_allocation"

    HARD_BLOCKED_SYMBOLS = {
        "JDMT",  # Janana De Malucha Textile - blocked due to NO TRADE + HIGH RISK behavior
    }

    # Symbols allowed even if industry metadata is still UNKNOWN.
    # PIBTL has TRANSPORT sector but UNKNOWN industry in your current master data.
    QUALITY_ALLOWLIST = {
        "PIBTL",
    }

    EXCLUDED_SECURITY_KEYWORDS = [
        "ETF",
        "REIT",
        "FUND",
        "MUTUAL",
        "TREASURY",
        "T-BILL",
        "TBILL",
        "GIS",
        "GOVT",
        "GOVERNMENT SECURITIES",
        "GOVERNMENT SECURITY",
        "FIXED RATE",
        "FLOATING RATE",
        "SUKUK",
        "BOND",
        "DEBT",
        "MONEY MARKET",
    ]

    EXCLUDED_SYMBOL_PREFIXES = (
        "P01GIS",
        "P02GIS",
        "P03GIS",
        "P05GIS",
        "P10GIS",
        "P15GIS",
        "P20GIS",
        "P01FRR",
        "P02FRR",
        "P03FRR",
        "P05FRR",
        "P10FRR",
        "P15FRR",
        "P20FRR",
    )

    def __init__(
        self,
        capital: float = 50000,
        max_positions: int = 3,
        base_max_exposure_pct: float = 0.85,
        min_position_value: float = 3500,
        max_sector_positions: int = 2,
    ):
        self.capital = float(capital)
        self.max_positions = int(max_positions)
        self.base_max_exposure_pct = float(base_max_exposure_pct)
        self.min_position_value = float(min_position_value)
        self.max_sector_positions = int(max_sector_positions)

    def build(self, df: pd.DataFrame) -> dict:
        if df is None or df.empty:
            return self.empty("No data received")

        data = remove_duplicate_columns(df.copy())
        data = self.ensure_columns(data)
        data = self.normalize_numeric(data)

        before_count = len(data)
        data = self.apply_data_quality_firewall(data)
        firewall_removed = before_count - len(data)

        if data.empty:
            out = self.empty("No candidates after V4.4 data quality firewall")
            out["firewall_removed"] = int(firewall_removed)
            return out

        market_score = float(data["market_score"].max()) if "market_score" in data.columns else 50.0
        market_mood = str(data["market_mood"].iloc[0]) if "market_mood" in data.columns and not data.empty else "SIDEWAYS"
        max_exposure_pct = self.dynamic_exposure_pct(market_score, market_mood)

        scored = data.apply(self.score_candidate, axis=1, result_type="expand")
        data = remove_duplicate_columns(pd.concat([data, scored], axis=1))

        eligible = data[data["portfolio_eligible"] == True].copy()

        # Controlled fallback pool:
        # When primary filters leave fewer than two candidates in a bullish
        # or non-bearish market, allow exceptional BUY/BUY SMALL setups that
        # narrowly missed one conservative threshold. Hard firewall and risk
        # rejection rules still remain enforced.
        if len(eligible) < 2 and market_mood.upper() not in ["BEARISH", "PANIC"]:
            backup = data[
                (data["portfolio_eligible"] == False)
                & (data["final_decision"].isin(["BUY", "STRONG BUY"]))
                & (data["final_score"] >= 82)
                & (data["buy_probability"] >= 78)
                & (data["trade_validation_score"] >= 90)
                & (data["entry_timing_score"] >= 90)
                & (data["risk_management_score"] >= 60)
                & (data["risk_status"].isin(["CONTROLLED RISK", "MEDIUM RISK", "LOW RISK", ""]))
                & (~data["risk_permission"].isin(["NO TRADE"]))
                & (data["change_pct"] < 7)
                & (data["rsi"] < 82)
                & (data["atr_percent"] < 8)
                & (data["value_traded"] >= 3_000_000)
            ].copy()

            if not backup.empty:
                backup["portfolio_fallback_candidate"] = True
                eligible["portfolio_fallback_candidate"] = False

                eligible = (
                    pd.concat([eligible, backup], ignore_index=True)
                    .drop_duplicates(subset=["symbol"], keep="first")
                )

        if eligible.empty:
            out = self.empty("No eligible stock candidates after V4.4 risk filters")
            out["firewall_removed"] = int(firewall_removed)
            out["market_score"] = round(market_score, 2)
            out["market_mood"] = market_mood
            return out

        if "portfolio_fallback_candidate" not in eligible.columns:
            eligible["portfolio_fallback_candidate"] = False

        eligible = eligible.sort_values(
            [
                "portfolio_rank_score",
                "position_quality_index",
                "institutional_portfolio_score",
                "final_score",
                "buy_probability",
                "smart_money_score",
                "value_traded",
            ],
            ascending=[False, False, False, False, False, False, False],
        ).reset_index(drop=True)

        selected = self.select_diversified_positions(eligible)
        trades = self.allocate_positions(selected=selected, max_exposure_pct=max_exposure_pct)

        used_capital = float(trades["investment"].sum()) if not trades.empty else 0.0
        max_loss = float(trades["max_loss"].sum()) if not trades.empty else 0.0
        expected_profit_t1 = float(trades["expected_profit_t1"].sum()) if not trades.empty else 0.0
        expected_profit_t2 = float(trades["expected_profit_t2"].sum()) if not trades.empty else 0.0
        portfolio_risk_pct = round((max_loss / self.capital) * 100, 2) if self.capital else 0.0

        return {
            "engine_version": self.VERSION,
            "mode": "AI_V5_BALANCED_BULLISH_DATA_QUALITY_FIREWALL",
            "capital": round(self.capital, 2),
            "max_positions": self.max_positions,
            "base_max_exposure_pct": round(self.base_max_exposure_pct * 100, 2),
            "dynamic_max_exposure_pct": round(max_exposure_pct * 100, 2),
            "market_score": round(market_score, 2),
            "market_mood": market_mood,
            "firewall_removed": int(firewall_removed),
            "eligible_candidates": int(len(eligible)),
            "selected_positions": int(len(trades)),
            "used_capital": round(used_capital, 2),
            "cash_reserve": round(self.capital - used_capital, 2),
            "total_expected_profit_t1": round(expected_profit_t1, 2),
            "total_expected_profit_t2": round(expected_profit_t2, 2),
            "total_max_loss_to_sl": round(max_loss, 2),
            "portfolio_risk_pct": portfolio_risk_pct,
            "portfolio_health_score": self.portfolio_health_score(trades, market_score),
            "trades": trades,
            "reason": "V4.4 balanced bullish firewall portfolio generated successfully",
        }

    def apply_data_quality_firewall(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        data = df.copy()
        keep_mask = []

        for _, row in data.iterrows():
            keep_mask.append(not self.is_firewall_rejected(row))

        return data[keep_mask].copy().reset_index(drop=True)

    def is_firewall_rejected(self, row) -> bool:
        symbol = text(row, "symbol")
        company = text(row, "company")
        sector = text(row, "sector", "UNKNOWN")
        industry = text(row, "industry", "UNKNOWN")
        final_decision = text(row, "final_decision")
        risk_permission = text(row, "risk_permission")
        risk_status = text(row, "risk_status")
        risk_action = text(row, "risk_action")
        entry_action = text(row, "entry_timing_action")
        trade_action = text(row, "trade_action")

        combined = f"{symbol} {company} {sector} {industry}".upper()

        if symbol in self.HARD_BLOCKED_SYMBOLS:
            return True

        if symbol.startswith(self.EXCLUDED_SYMBOL_PREFIXES):
            return True

        for keyword in self.EXCLUDED_SECURITY_KEYWORDS:
            if keyword in combined:
                return True

        if final_decision not in ["BUY", "STRONG BUY"]:
            return True

        if trade_action in ["AVOID", "REJECTED"]:
            return True

        if entry_action in ["NO TRADE", "WATCH ONLY"]:
            return True

        # Reject only when BOTH sector and industry are unknown.
        # If a valid sector exists but industry metadata is missing,
        # keep the stock eligible for scoring.
        if symbol not in self.QUALITY_ALLOWLIST:
            sector_unknown = sector in ["UNKNOWN", "", "NAN", "NONE"]
            industry_unknown = industry in ["UNKNOWN", "", "NAN", "NONE"]

            if sector_unknown and industry_unknown:
                return True

        # Hard block if risk engine says avoid/rejected/high risk/chase risk.
        if risk_permission == "NO TRADE" and risk_action == "AVOID":
            return True

        if risk_status in ["REJECTED", "HIGH RISK", "CHASE RISK REJECTED"]:
            return True

        return False

    def score_candidate(self, row) -> pd.Series:
        symbol = text(row, "symbol")
        final_score = num(row, "final_score")
        ai_score = num(row, "ai_score", final_score)
        buy_probability = num(row, "buy_probability")
        confidence = num(row, "confidence_v3", num(row, "confidence", 50))
        trend_score = num(row, "trend_score_v5", num(row, "trend_score_v4", 50))
        smart_money_score = num(row, "smart_money_score")
        accumulation_score = num(row, "accumulation_score")
        distribution_score = num(row, "distribution_score", 25)
        trade_validation_score = num(row, "trade_validation_score")
        entry_timing_score = num(row, "entry_timing_score")
        risk_management_score = num(row, "risk_management_score", 50)
        sector_score = num(row, "sector_score", num(row, "sector_strength_score", 50))
        market_score = num(row, "market_score", 50)
        liquidity_score = num(row, "liquidity_score_v4", num(row, "liquidity_score_raw", 50))
        volume_score = num(row, "volume_score_v4", num(row, "volume_strength", 50))
        risk_reward = num(row, "risk_reward_t1", 1.15)
        change_pct = num(row, "change_pct")
        rsi = num(row, "rsi", 50)
        atr_percent = num(row, "atr_percent", 5)
        volume = num(row, "volume")
        value_traded = num(row, "value_traded")
        risk_permission = text(row, "risk_permission")
        entry_action = text(row, "entry_timing_action")

        reasons = []
        warnings = []
        eligible = True

        if final_score < 78:
            eligible = False
            warnings.append("Final score below 78")

        if buy_probability < 80:
            eligible = False
            warnings.append("Buy probability below 80")

        if trade_validation_score < 85:
            eligible = False
            warnings.append("Trade validation below 85")

        if entry_timing_score < 80:
            eligible = False
            warnings.append("Entry timing below 80")

        if risk_management_score < 50:
            eligible = False
            warnings.append("Risk management score below 50")

        if volume <= 0:
            eligible = False
            warnings.append("Invalid volume")

        if value_traded < 5_000_000 and symbol not in self.QUALITY_ALLOWLIST:
            eligible = False
            warnings.append("Value traded below minimum")

        if risk_reward < 1.10:
            eligible = False
            warnings.append("Risk reward below 1.10")
        elif risk_reward < 1.25:
            warnings.append("Risk/reward weak")

        if change_pct >= 9.8:
            eligible = False
            warnings.append("Near upper cap / chase risk")
        elif change_pct >= 7:
            warnings.append("Large daily move; controlled entry only")

        if rsi >= 88:
            eligible = False
            warnings.append("RSI extremely overheated")
        elif rsi >= 82:
            warnings.append("RSI overbought")

        if atr_percent >= 10:
            eligible = False
            warnings.append("ATR volatility extreme")
        elif atr_percent >= 7:
            warnings.append("ATR volatility high")

        if risk_permission == "WAIT":
            reasons.append("Risk suggests controlled entry")
        elif risk_permission == "TRADE ALLOWED SMALL":
            reasons.append("Risk allowed small trade")
        elif risk_permission == "TRADE ALLOWED":
            reasons.append("Risk allowed trade")

        if entry_action == "BUY NOW":
            reasons.append("Entry timing BUY NOW")
        elif entry_action == "BUY ON DIP":
            reasons.append("Buy on dip setup")
        elif entry_action == "WAIT PULLBACK":
            warnings.append("Wait pullback setup")
        elif entry_action == "BUY ABOVE BREAKOUT":
            warnings.append("Breakout confirmation required")

        if smart_money_score >= 85:
            reasons.append("Smart money very strong")
        elif smart_money_score >= 80:
            reasons.append("Smart money strong")

        if accumulation_score >= 85:
            reasons.append("Accumulation strong")

        position_quality_index = (
            final_score * 0.16
            + buy_probability * 0.12
            + confidence * 0.08
            + trend_score * 0.08
            + smart_money_score * 0.15
            + accumulation_score * 0.10
            + trade_validation_score * 0.13
            + entry_timing_score * 0.10
            + risk_management_score * 0.05
            + liquidity_score * 0.03
        )

        institutional_score = (
            smart_money_score * 0.38
            + accumulation_score * 0.24
            + buy_probability * 0.18
            + max(0, 100 - distribution_score) * 0.12
            + trade_validation_score * 0.08
        )

        risk_adjustment = 0.0
        if risk_permission == "TRADE ALLOWED":
            risk_adjustment += 5
        elif risk_permission == "TRADE ALLOWED SMALL":
            risk_adjustment += 2
        elif risk_permission == "WAIT":
            risk_adjustment -= 2

        if entry_action == "BUY NOW":
            risk_adjustment += 5
        elif entry_action == "BUY ON DIP":
            risk_adjustment += 2
        elif entry_action == "WAIT PULLBACK":
            risk_adjustment -= 2

        if risk_reward >= 1.8:
            risk_adjustment += 5
        elif risk_reward >= 1.4:
            risk_adjustment += 2
        elif risk_reward < 1.25:
            risk_adjustment -= 3

        if change_pct >= 7:
            risk_adjustment -= 3
        if rsi >= 82:
            risk_adjustment -= 2
        if atr_percent >= 7:
            risk_adjustment -= 2

        portfolio_rank_score = (
            ai_score * 0.14
            + final_score * 0.16
            + buy_probability * 0.12
            + confidence * 0.08
            + trend_score * 0.08
            + institutional_score * 0.16
            + trade_validation_score * 0.10
            + entry_timing_score * 0.08
            + risk_management_score * 0.05
            + sector_score * 0.02
            + market_score * 0.01
            + risk_adjustment
        )

        return pd.Series({
            "portfolio_eligible": bool(eligible),
            "portfolio_rank_score": round(clamp(portfolio_rank_score, 0, 100), 2),
            "position_quality_index": round(clamp(position_quality_index, 0, 100), 2),
            "institutional_portfolio_score": round(clamp(institutional_score, 0, 100), 2),
            "portfolio_reason": " | ".join(reasons),
            "portfolio_warning": " | ".join(warnings),
        })

    def select_diversified_positions(self, eligible: pd.DataFrame) -> pd.DataFrame:
        if eligible is None or eligible.empty:
            return pd.DataFrame()

        selected_rows = []
        sector_count = {}

        for _, row in eligible.iterrows():
            sector = text(row, "sector", "UNKNOWN")
            count = sector_count.get(sector, 0)
            if count >= self.max_sector_positions and len(selected_rows) < self.max_positions:
                continue

            selected_rows.append(row)
            sector_count[sector] = count + 1
            if len(selected_rows) >= self.max_positions:
                break

        if len(selected_rows) < self.max_positions:
            existing = {text(row, "symbol") for row in selected_rows}
            for _, row in eligible.iterrows():
                symbol = text(row, "symbol")
                if symbol in existing:
                    continue
                selected_rows.append(row)
                existing.add(symbol)
                if len(selected_rows) >= self.max_positions:
                    break

        return pd.DataFrame(selected_rows).reset_index(drop=True) if selected_rows else pd.DataFrame()

    def allocate_positions(self, selected: pd.DataFrame, max_exposure_pct: float) -> pd.DataFrame:
        if selected is None or selected.empty:
            return pd.DataFrame()

        selected = selected.copy()
        selected["allocation_weight"] = selected.apply(self.allocation_weight, axis=1)
        total_weight = float(selected["allocation_weight"].sum())
        if total_weight <= 0:
            selected["allocation_weight"] = 1.0
            total_weight = float(selected["allocation_weight"].sum())

        total_exposure = self.capital * max_exposure_pct
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
            if suggested_entry <= 0:
                continue

            factor = self.allocation_factor(row)
            base_allocation = total_exposure * (num(row, "allocation_weight") / total_weight)
            allocation = base_allocation * factor
            allocation = min(allocation, self.capital * 0.30)
            allocation = max(allocation, self.min_position_value)

            quantity = int(allocation // suggested_entry)
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
                "ai_score": num(row, "ai_score"),
                "portfolio_rank_score": num(row, "portfolio_rank_score"),
                "position_quality_index": num(row, "position_quality_index"),
                "institutional_portfolio_score": num(row, "institutional_portfolio_score"),
                "buy_probability": num(row, "buy_probability"),
                "confidence_v3": num(row, "confidence_v3", num(row, "confidence", 50)),
                "trend_score_v5": num(row, "trend_score_v5", num(row, "trend_score_v4", 50)),
                "smart_money_score": num(row, "smart_money_score"),
                "accumulation_score": num(row, "accumulation_score"),
                "trade_validation_score": num(row, "trade_validation_score"),
                "entry_timing_score": num(row, "entry_timing_score"),
                "entry_timing_action": row.get("entry_timing_action", ""),
                "risk_management_score": num(row, "risk_management_score"),
                "risk_permission": row.get("risk_permission", ""),
                "risk_status": row.get("risk_status", ""),
                "portfolio_fallback_candidate": bool(
                    row.get("portfolio_fallback_candidate", False)
                ),
                "allocation_weight": round(num(row, "allocation_weight"), 2),
                "allocation_factor": round(factor, 2),
                "allocation": round(allocation, 2),
                "quantity": quantity,
                "final_quantity": quantity,
                "investment": investment,
                "suggested_entry_price": round(suggested_entry, 2),
                "adjusted_entry_price": round(suggested_entry, 2),
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
                "position_status": self.position_status(row),
                "exit_plan": self.exit_plan(row),
                "position_reason": self.position_reason(row),
            })

        trades_df = pd.DataFrame(trades)
        if not trades_df.empty:
            trades_df = trades_df.sort_values(
                ["portfolio_rank_score", "position_quality_index", "buy_probability"],
                ascending=[False, False, False],
            ).reset_index(drop=True)
            trades_df["rank"] = range(1, len(trades_df) + 1)

        return trades_df

    def allocation_weight(self, row) -> float:
        score = (
            num(row, "portfolio_rank_score") * 0.32
            + num(row, "position_quality_index") * 0.24
            + num(row, "institutional_portfolio_score") * 0.20
            + num(row, "risk_management_score", 50) * 0.14
            + num(row, "trade_validation_score", 50) * 0.10
        )
        return max(score, 1.0)

    def allocation_factor(self, row) -> float:
        risk_permission = text(row, "risk_permission")
        entry_action = text(row, "entry_timing_action")
        change_pct = num(row, "change_pct")
        risk_factor = num(row, "position_risk_factor", 1)
        risk_management_score = num(row, "risk_management_score", 50)
        atr_percent = num(row, "atr_percent", 5)
        risk_reward = num(row, "risk_reward_t1", 1.15)

        factor = 1.0

        if risk_permission == "TRADE ALLOWED":
            factor *= 1.0
        elif risk_permission == "TRADE ALLOWED SMALL":
            factor *= 0.82
        elif risk_permission == "WAIT":
            factor *= 0.70
        else:
            factor *= 0.60

        if entry_action == "BUY NOW":
            factor *= 1.0
        elif entry_action == "BUY ON DIP":
            factor *= 0.86
        elif entry_action == "WAIT PULLBACK":
            factor *= 0.65
        elif entry_action == "BUY ABOVE BREAKOUT":
            factor *= 0.60

        if change_pct >= 7:
            factor *= 0.72
        elif change_pct >= 4:
            factor *= 0.88

        if risk_management_score < 60:
            factor *= 0.78
        if atr_percent >= 7:
            factor *= 0.75
        if risk_reward < 1.25:
            factor *= 0.82

        factor *= max(min(risk_factor, 1.25), 0.35)
        return clamp(factor, 0.25, 1.0)

    def dynamic_exposure_pct(self, market_score: float, market_mood: str) -> float:
        mood = str(market_mood).upper()
        exposure = self.base_max_exposure_pct

        if market_score >= 75 and mood in ["BULLISH", "STRONG BULLISH"]:
            exposure = min(0.78, exposure + 0.08)
        elif market_score >= 65 and mood == "BULLISH":
            exposure = min(0.75, exposure + 0.05)
        elif market_score < 45 or mood in ["BEARISH", "PANIC"]:
            exposure = min(exposure, 0.35)
        elif market_score < 55 or mood in ["SIDEWAYS", "MIXED"]:
            exposure = min(exposure, 0.65)

        return clamp(exposure, 0.20, 0.80)

    def position_status(self, row) -> str:
        risk_permission = text(row, "risk_permission")
        entry_action = text(row, "entry_timing_action")
        if risk_permission == "WAIT":
            return "CONTROLLED / SMALL ENTRY"
        if entry_action in ["BUY ON DIP", "WAIT PULLBACK"]:
            return "WAIT ENTRY LEVEL"
        if entry_action == "BUY NOW":
            return "READY TO BUY"
        return "CONTROLLED"

    def exit_plan(self, row) -> str:
        return (
            "Book 50% near Target 1 | Trail remaining position toward Target 2 | "
            "Use strict stop loss; no averaging down | Move SL to breakeven after 3-4% gain"
        )

    def position_reason(self, row) -> str:
        parts = []
        for col in [
            "portfolio_reason",
            "portfolio_warning",
            "risk_management_warnings",
            "entry_timing_warning",
            "validation_warnings",
        ]:
            value = str(row.get(col, "")).strip()
            if value and value.lower() != "nan":
                parts.append(value)
        return " | ".join(parts)

    def portfolio_health_score(self, trades: pd.DataFrame, market_score: float) -> float:
        if trades is None or trades.empty:
            return 0.0
        avg_quality = float(trades["position_quality_index"].mean()) if "position_quality_index" in trades.columns else 50.0
        risk_pct = float(trades["risk_pct_of_capital"].sum()) if "risk_pct_of_capital" in trades.columns else 0.0
        concentration_penalty = 0.0
        if "sector" in trades.columns and len(trades) > 1:
            max_sector = trades["sector"].value_counts().max()
            if max_sector > 1:
                concentration_penalty = (max_sector - 1) * 5
        score = avg_quality * 0.70 + market_score * 0.20 + max(0, 100 - risk_pct * 10) * 0.10 - concentration_penalty
        return round(clamp(score, 0, 100), 2)

    def ensure_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        defaults = {
            "symbol": "",
            "company": "",
            "sector": "UNKNOWN",
            "industry": "UNKNOWN",
            "market_mood": "SIDEWAYS",
            "final_decision": "",
            "trade_action": "",
            "entry_timing_action": "",
            "risk_permission": "",
            "risk_status": "",
            "risk_action": "",
            "risk_management_warnings": "",
            "entry_timing_warning": "",
            "validation_warnings": "",
            "close": 0,
            "change_pct": 0,
            "volume": 0,
            "value_traded": 0,
            "rsi": 50,
            "atr_percent": 5,
            "final_score": 0,
            "ai_score": 0,
            "buy_probability": 0,
            "confidence": 50,
            "confidence_v3": 50,
            "trend_score_v4": 50,
            "trend_score_v5": 50,
            "smart_money_score": 50,
            "accumulation_score": 50,
            "distribution_score": 25,
            "trade_validation_score": 0,
            "entry_timing_score": 0,
            "risk_management_score": 50,
            "position_risk_factor": 1,
            "risk_reward_t1": 1.15,
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
            "portfolio_fallback_candidate": False,
        }
        for col, default in defaults.items():
            if col not in df.columns:
                df[col] = default
        return df

    def normalize_numeric(self, df: pd.DataFrame) -> pd.DataFrame:
        numeric_cols = [
            "close", "change_pct", "volume", "value_traded", "rsi", "atr_percent",
            "final_score", "ai_score", "buy_probability", "confidence", "confidence_v3",
            "trend_score_v4", "trend_score_v5", "smart_money_score", "accumulation_score",
            "distribution_score", "trade_validation_score", "entry_timing_score",
            "risk_management_score", "position_risk_factor", "risk_reward_t1",
            "sector_score", "sector_strength_score", "market_score", "liquidity_score_v4",
            "liquidity_score_raw", "volume_score_v4", "volume_strength", "entry_low",
            "entry_high", "stop_loss", "target_1", "target_2", "adjusted_entry_price",
            "suggested_entry_price",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        return df

    def empty(self, reason: str) -> dict:
        return {
            "engine_version": self.VERSION,
            "mode": "AI_V5_BALANCED_BULLISH_DATA_QUALITY_FIREWALL",
            "capital": round(self.capital, 2),
            "max_positions": self.max_positions,
            "base_max_exposure_pct": round(self.base_max_exposure_pct * 100, 2),
            "dynamic_max_exposure_pct": 0,
            "market_score": 0,
            "market_mood": "UNKNOWN",
            "firewall_removed": 0,
            "eligible_candidates": 0,
            "selected_positions": 0,
            "used_capital": 0,
            "cash_reserve": round(self.capital, 2),
            "total_expected_profit_t1": 0,
            "total_expected_profit_t2": 0,
            "total_max_loss_to_sl": 0,
            "portfolio_risk_pct": 0,
            "portfolio_health_score": 0,
            "trades": pd.DataFrame(),
            "reason": reason,
        }


def build_portfolio_plan_v4(
    final_df: pd.DataFrame,
    capital: float = 50000,
    max_positions: int = 3,
    base_max_exposure_pct: float = 0.85,
    min_position_value: float = 3500,
    max_sector_positions: int = 2,
) -> dict:
    engine = PortfolioEngineV4(
        capital=capital,
        max_positions=max_positions,
        base_max_exposure_pct=base_max_exposure_pct,
        min_position_value=min_position_value,
        max_sector_positions=max_sector_positions,
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


def clamp(value: float, low: float, high: float) -> float:
    try:
        value = float(value)
    except Exception:
        value = low
    return max(low, min(high, value))