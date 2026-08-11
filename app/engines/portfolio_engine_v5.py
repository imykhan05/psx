from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class PortfolioConfigV5:
    capital: float = 50000.0
    max_positions: int = 5
    min_positions_bullish: int = 2
    min_position_value: float = 3000.0
    max_position_pct: float = 0.28
    max_sector_positions: int = 2
    base_exposure_pct: float = 0.70
    max_portfolio_risk_pct: float = 2.50
    per_trade_risk_pct: float = 0.80


class PortfolioEngineV5:
    """
    Portfolio Engine V5 Institutional

    Key features:
    - Stock-only security firewall
    - Dynamic market exposure
    - Risk-parity position sizing
    - ATR and stop-distance controls
    - Sector diversification
    - Smart-money and consensus weighting
    - Controlled fallback candidates
    - Portfolio heat and capital controls
    - Cash reserve preservation
    """

    VERSION = "portfolio_engine_v5_1_clean_reasons_wait_firewall"

    HARD_BLOCKED_SYMBOLS = {
        "JDMT",
    }

    ALLOWED_UNKNOWN_INDUSTRY_SYMBOLS = {
        "PIBTL",
    }

    EXCLUDED_SECURITY_KEYWORDS = (
        "ETF",
        "REIT",
        "FUND",
        "MUTUAL",
        "TREASURY",
        "T-BILL",
        "TBILL",
        "GIS",
        "GHS",
        "GOVT",
        "GOVERNMENT SECURITIES",
        "GOVERNMENT SECURITY",
        "FIXED RATE",
        "FLOATING RATE",
        "SUKUK",
        "BOND",
        "DEBT",
        "MONEY MARKET",
    )

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
        "P01GHS",
        "P02GHS",
        "P03GHS",
        "P05GHS",
        "P10GHS",
        "P15GHS",
        "P20GHS",
    )

    def __init__(
        self,
        capital: float = 50000,
        max_positions: int = 5,
        min_positions_bullish: int = 2,
        min_position_value: float = 3000,
        max_position_pct: float = 0.28,
        max_sector_positions: int = 2,
        base_exposure_pct: float = 0.70,
        max_portfolio_risk_pct: float = 2.50,
        per_trade_risk_pct: float = 0.80,
    ):
        self.config = PortfolioConfigV5(
            capital=float(capital),
            max_positions=int(max_positions),
            min_positions_bullish=int(min_positions_bullish),
            min_position_value=float(min_position_value),
            max_position_pct=float(max_position_pct),
            max_sector_positions=int(max_sector_positions),
            base_exposure_pct=float(base_exposure_pct),
            max_portfolio_risk_pct=float(max_portfolio_risk_pct),
            per_trade_risk_pct=float(per_trade_risk_pct),
        )

    def build(self, df: pd.DataFrame) -> dict:
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return self.empty_plan("No data received")

        data = remove_duplicate_columns(df.copy())
        data = self.ensure_columns(data)
        data = self.normalize_columns(data)

        market_score = float(data["market_score"].max())
        market_mood = text_value(data["market_mood"].iloc[0], "SIDEWAYS")
        exposure_pct = self.dynamic_exposure_pct(market_score, market_mood)
        target_positions = self.dynamic_target_positions(market_score, market_mood)

        firewall_before = len(data)
        data = data[~data.apply(self.is_firewall_rejected, axis=1)].copy()
        firewall_removed = firewall_before - len(data)

        if data.empty:
            out = self.empty_plan("No candidates after institutional security firewall")
            out.update({
                "market_score": round(market_score, 2),
                "market_mood": market_mood,
                "firewall_removed": int(firewall_removed),
            })
            return out

        scored = data.apply(self.score_candidate, axis=1, result_type="expand")
        data = remove_duplicate_columns(pd.concat([data, scored], axis=1))

        primary = data[data["portfolio_eligible"]].copy()
        fallback = self.build_fallback_pool(
            data=data,
            primary=primary,
            market_score=market_score,
            market_mood=market_mood,
            target_positions=target_positions,
        )

        eligible = (
            pd.concat([primary, fallback], ignore_index=True)
            .drop_duplicates(subset=["symbol"], keep="first")
        )

        if eligible.empty:
            out = self.empty_plan("No eligible stock candidates after V5 filters")
            out.update({
                "market_score": round(market_score, 2),
                "market_mood": market_mood,
                "firewall_removed": int(firewall_removed),
            })
            return out

        eligible = eligible.sort_values(
            by=[
                "portfolio_rank_score",
                "position_quality_index",
                "institutional_portfolio_score",
                "consensus_score",
                "final_score",
                "buy_probability",
                "value_traded",
            ],
            ascending=[False, False, False, False, False, False, False],
        ).reset_index(drop=True)

        selected = self.select_diversified_positions(
            eligible=eligible,
            target_positions=target_positions,
        )

        trades = self.allocate_positions(
            selected=selected,
            exposure_pct=exposure_pct,
        )

        used_capital = float(trades["investment"].sum()) if not trades.empty else 0.0
        max_loss = float(trades["max_loss"].sum()) if not trades.empty else 0.0
        expected_profit_t1 = (
            float(trades["expected_profit_t1"].sum())
            if not trades.empty
            else 0.0
        )
        expected_profit_t2 = (
            float(trades["expected_profit_t2"].sum())
            if not trades.empty
            else 0.0
        )

        portfolio_risk_pct = (
            max_loss / self.config.capital * 100
            if self.config.capital > 0
            else 0.0
        )

        return {
            "engine_version": self.VERSION,
            "mode": "AI_V5_INSTITUTIONAL_RISK_PARITY",
            "capital": round(self.config.capital, 2),
            "market_score": round(market_score, 2),
            "market_mood": market_mood,
            "dynamic_exposure_pct": round(exposure_pct * 100, 2),
            "target_positions": int(target_positions),
            "max_positions": int(self.config.max_positions),
            "firewall_removed": int(firewall_removed),
            "eligible_candidates": int(len(eligible)),
            "selected_positions": int(len(trades)),
            "used_capital": round(used_capital, 2),
            "cash_reserve": round(self.config.capital - used_capital, 2),
            "capital_utilization_pct": round(
                used_capital / self.config.capital * 100
                if self.config.capital > 0
                else 0,
                2,
            ),
            "total_expected_profit_t1": round(expected_profit_t1, 2),
            "total_expected_profit_t2": round(expected_profit_t2, 2),
            "total_max_loss_to_sl": round(max_loss, 2),
            "portfolio_risk_pct": round(portfolio_risk_pct, 2),
            "portfolio_heat_status": self.portfolio_heat_status(
                portfolio_risk_pct
            ),
            "portfolio_health_score": self.portfolio_health_score(
                trades=trades,
                market_score=market_score,
            ),
            "trades": trades,
            "reason": "Portfolio Engine V5 institutional plan generated successfully",
        }

    def is_firewall_rejected(self, row: pd.Series) -> bool:
        symbol = text(row, "symbol")
        company = text(row, "company")
        sector = text(row, "sector", "UNKNOWN")
        industry = text(row, "industry", "UNKNOWN")
        final_decision = text(row, "final_decision")
        consensus_decision = text(row, "consensus_decision")
        risk_permission = text(row, "risk_permission")
        risk_status = text(row, "risk_status")
        risk_action = text(row, "risk_action")
        trade_action = text(row, "trade_action")
        entry_action = text(row, "entry_timing_action")

        combined = f"{symbol} {company} {sector} {industry}"

        if not symbol:
            return True

        if symbol in self.HARD_BLOCKED_SYMBOLS:
            return True

        if symbol.startswith(self.EXCLUDED_SYMBOL_PREFIXES):
            return True

        if any(keyword in combined for keyword in self.EXCLUDED_SECURITY_KEYWORDS):
            return True

        if final_decision not in ["BUY", "STRONG BUY"]:
            return True

        if consensus_decision in ["AVOID", "NO TRADE", "BLOCKED"]:
            return True

        if trade_action in ["AVOID", "REJECTED"]:
            return True

        if entry_action in ["NO TRADE", "WATCH ONLY", "NO ENTRY"]:
            return True

        if risk_permission in ["NO TRADE", "WAIT"]:
            return True

        if risk_action == "AVOID":
            return True

        if risk_status in [
            "REJECTED",
            "HIGH RISK",
            "CHASE RISK REJECTED",
            "VOLATILITY REJECTED",
            "RISK/REWARD REJECTED",
        ]:
            return True

        sector_unknown = sector in ["UNKNOWN", "", "NAN", "NONE"]
        industry_unknown = industry in ["UNKNOWN", "", "NAN", "NONE"]

        if (
            symbol not in self.ALLOWED_UNKNOWN_INDUSTRY_SYMBOLS
            and sector_unknown
            and industry_unknown
        ):
            return True

        return False

    def score_candidate(self, row: pd.Series) -> pd.Series:
        final_score = num(row, "final_score")
        ai_score = num(row, "ai_score", final_score)
        consensus_score = num(row, "consensus_score", final_score)
        consensus_confidence = num(
            row,
            "consensus_confidence",
            num(row, "confidence_v3", num(row, "confidence", 50)),
        )
        buy_probability = num(row, "buy_probability")
        confidence = num(
            row,
            "confidence_v3",
            num(row, "confidence", 50),
        )
        trend_score = num(
            row,
            "trend_score_v5",
            num(row, "trend_score_v4", 50),
        )
        smart_money_score = num(row, "smart_money_score", 50)
        accumulation_score = num(row, "accumulation_score", 50)
        distribution_score = num(row, "distribution_score", 25)
        validation_score = num(row, "trade_validation_score", 0)
        entry_score = num(row, "entry_timing_score", 0)
        risk_score = num(row, "risk_management_score", 0)
        institutional_score_v5 = num(
            row,
            "institutional_v5_score",
            smart_money_score,
        )
        sector_score = num(
            row,
            "sector_score",
            num(row, "sector_strength_score", 50),
        )
        market_score = num(row, "market_score", 50)
        liquidity_score = num(
            row,
            "liquidity_score_v4",
            num(row, "liquidity_score_raw", 50),
        )
        volume_score = num(
            row,
            "volume_score_v4",
            num(row, "volume_strength", 50),
        )
        value_traded = num(row, "value_traded", 0)
        risk_reward = num(row, "risk_reward_t1", 0)
        change_pct = num(row, "change_pct", 0)
        rsi = num(row, "rsi", 50)
        atr_percent = num(row, "atr_percent", 5)
        stop_distance_pct = num(
            row,
            "stop_distance_pct",
            self.calculate_stop_distance(row),
        )
        risk_permission = text(row, "risk_permission")
        entry_action = text(row, "entry_timing_action")
        consensus_decision = text(row, "consensus_decision")

        reasons: list[str] = []
        warnings: list[str] = []
        eligible = True

        if final_score < 78:
            eligible = False
            warnings.append("Final score below 78")

        if buy_probability < 78:
            eligible = False
            warnings.append("Buy probability below 78")

        if validation_score < 85:
            eligible = False
            warnings.append("Trade validation below 85")

        if entry_score < 80:
            eligible = False
            warnings.append("Entry timing below 80")

        if risk_score < 60:
            eligible = False
            warnings.append("Risk score below 60")

        if risk_reward < 1.10:
            eligible = False
            warnings.append("Risk/reward below 1.10")
        elif risk_reward < 1.30:
            warnings.append("Risk/reward is weak")

        if value_traded < 3_000_000:
            eligible = False
            warnings.append("Value traded below 3 million")

        if change_pct >= 9.5:
            eligible = False
            warnings.append("Near upper cap / chase risk")
        elif change_pct >= 7:
            warnings.append("Large daily move")

        if rsi >= 85:
            eligible = False
            warnings.append("RSI overheated")
        elif rsi >= 78:
            warnings.append("RSI elevated")

        if atr_percent >= 12:
            eligible = False
            warnings.append("ATR volatility extreme")
        elif atr_percent >= 8:
            warnings.append("ATR volatility high")

        if stop_distance_pct <= 0 or stop_distance_pct > 12:
            eligible = False
            warnings.append("Invalid or excessive stop distance")

        if risk_permission == "TRADE ALLOWED":
            reasons.append("Risk engine allowed trade")
        elif risk_permission == "TRADE ALLOWED SMALL":
            reasons.append("Risk engine allowed small position")
        elif risk_permission == "WAIT":
            reasons.append("Risk engine suggests controlled entry")

        if consensus_decision == "BUY":
            reasons.append("Consensus BUY")
        elif consensus_decision == "BUY SMALL":
            reasons.append("Consensus BUY SMALL")

        if entry_action == "BUY NOW":
            reasons.append("Entry timing BUY NOW")
        elif entry_action == "BUY ON DIP":
            reasons.append("Buy on dip")

        if smart_money_score >= 85:
            reasons.append("Smart money very strong")
        elif smart_money_score >= 80:
            reasons.append("Smart money strong")

        if accumulation_score >= 85:
            reasons.append("Accumulation strong")

        institutional_portfolio_score = (
            smart_money_score * 0.24
            + accumulation_score * 0.18
            + institutional_score_v5 * 0.20
            + buy_probability * 0.14
            + validation_score * 0.12
            + max(0, 100 - distribution_score) * 0.12
        )

        position_quality_index = (
            final_score * 0.14
            + consensus_score * 0.14
            + buy_probability * 0.11
            + confidence * 0.07
            + consensus_confidence * 0.07
            + trend_score * 0.07
            + smart_money_score * 0.11
            + accumulation_score * 0.08
            + validation_score * 0.10
            + entry_score * 0.06
            + risk_score * 0.05
        )

        risk_adjustment = 0.0

        if risk_permission == "TRADE ALLOWED":
            risk_adjustment += 5
        elif risk_permission == "TRADE ALLOWED SMALL":
            risk_adjustment += 2
        elif risk_permission == "WAIT":
            risk_adjustment -= 2

        if entry_action == "BUY NOW":
            risk_adjustment += 4
        elif entry_action == "BUY ON DIP":
            risk_adjustment += 2

        if risk_reward >= 1.8:
            risk_adjustment += 5
        elif risk_reward >= 1.4:
            risk_adjustment += 2
        elif risk_reward < 1.25:
            risk_adjustment -= 3

        if change_pct >= 7:
            risk_adjustment -= 3

        if rsi >= 78:
            risk_adjustment -= 2

        if atr_percent >= 8:
            risk_adjustment -= 2

        portfolio_rank_score = (
            ai_score * 0.10
            + final_score * 0.13
            + consensus_score * 0.14
            + buy_probability * 0.10
            + confidence * 0.05
            + trend_score * 0.06
            + institutional_portfolio_score * 0.16
            + validation_score * 0.08
            + entry_score * 0.07
            + risk_score * 0.06
            + sector_score * 0.03
            + market_score * 0.02
            + risk_adjustment
        )

        return pd.Series({
            "portfolio_eligible": bool(eligible),
            "portfolio_rank_score": round(
                clamp(portfolio_rank_score, 0, 100),
                2,
            ),
            "position_quality_index": round(
                clamp(position_quality_index, 0, 100),
                2,
            ),
            "institutional_portfolio_score": round(
                clamp(institutional_portfolio_score, 0, 100),
                2,
            ),
            "portfolio_reason": " | ".join(unique_strings(reasons)),
            "portfolio_warning": " | ".join(unique_strings(warnings)),
            "portfolio_fallback_candidate": False,
        })

    def build_fallback_pool(
        self,
        data: pd.DataFrame,
        primary: pd.DataFrame,
        market_score: float,
        market_mood: str,
        target_positions: int,
    ) -> pd.DataFrame:
        if len(primary) >= target_positions:
            return pd.DataFrame()

        mood = market_mood.upper()

        if mood in ["BEARISH", "PANIC", "STRONG BEARISH"]:
            return pd.DataFrame()

        needed = max(target_positions - len(primary), 0)

        fallback = data[
            (~data["portfolio_eligible"])
            & (data["final_decision"].isin(["BUY", "STRONG BUY"]))
            & (data["final_score"] >= 88)
            & (data["buy_probability"] >= 80)
            & (data["trade_validation_score"] >= 90)
            & (data["entry_timing_score"] >= 90)
            & (data["risk_management_score"] >= 65)
            & (data["risk_permission"].isin([
                "TRADE ALLOWED",
                "TRADE ALLOWED SMALL",
            ]))
            & (data["risk_status"].isin([
                "LOW RISK",
                "CONTROLLED RISK",
                "MEDIUM RISK",
                "",
            ]))
            & (data["value_traded"] >= 3_000_000)
            & (data["change_pct"] < 7)
            & (data["rsi"] < 82)
            & (data["atr_percent"] < 9)
            & (data["risk_reward_t1"] >= 1.10)
        ].copy()

        if fallback.empty:
            return fallback

        fallback["portfolio_fallback_candidate"] = True

        fallback = fallback.sort_values(
            by=[
                "portfolio_rank_score",
                "position_quality_index",
                "institutional_portfolio_score",
                "final_score",
            ],
            ascending=[False, False, False, False],
        ).head(needed)

        return fallback

    def select_diversified_positions(
        self,
        eligible: pd.DataFrame,
        target_positions: int,
    ) -> pd.DataFrame:
        if eligible is None or eligible.empty:
            return pd.DataFrame()

        selected_rows: list[pd.Series] = []
        selected_symbols: set[str] = set()
        sector_count: dict[str, int] = {}

        for _, row in eligible.iterrows():
            symbol = text(row, "symbol")
            sector = text(row, "sector", "UNKNOWN")

            if symbol in selected_symbols:
                continue

            if sector_count.get(sector, 0) >= self.config.max_sector_positions:
                continue

            selected_rows.append(row)
            selected_symbols.add(symbol)
            sector_count[sector] = sector_count.get(sector, 0) + 1

            if len(selected_rows) >= target_positions:
                break

        if len(selected_rows) < target_positions:
            for _, row in eligible.iterrows():
                symbol = text(row, "symbol")

                if symbol in selected_symbols:
                    continue

                selected_rows.append(row)
                selected_symbols.add(symbol)

                if len(selected_rows) >= target_positions:
                    break

        if not selected_rows:
            return pd.DataFrame()

        return pd.DataFrame(selected_rows).reset_index(drop=True)

    def allocate_positions(
        self,
        selected: pd.DataFrame,
        exposure_pct: float,
    ) -> pd.DataFrame:
        if selected is None or selected.empty:
            return pd.DataFrame()

        data = selected.copy()
        data["allocation_weight"] = data.apply(
            self.allocation_weight,
            axis=1,
        )

        total_weight = float(data["allocation_weight"].sum())

        if total_weight <= 0:
            data["allocation_weight"] = 1.0
            total_weight = float(data["allocation_weight"].sum())

        max_exposure_value = self.config.capital * exposure_pct
        max_portfolio_loss = (
            self.config.capital
            * self.config.max_portfolio_risk_pct
            / 100
        )
        max_trade_loss = (
            self.config.capital
            * self.config.per_trade_risk_pct
            / 100
        )

        trades: list[dict[str, Any]] = []
        used_capital = 0.0
        used_risk = 0.0

        for _, row in data.iterrows():
            close = num(row, "close")
            entry_low = positive_or_default(
                num(row, "entry_low"),
                close * 0.985,
            )
            entry_high = positive_or_default(
                num(row, "entry_high"),
                close * 1.01,
            )
            stop_loss = positive_or_default(
                num(row, "stop_loss"),
                close * 0.94,
            )
            target_1 = positive_or_default(
                num(row, "target_1"),
                close * 1.08,
            )
            target_2 = positive_or_default(
                num(row, "target_2"),
                close * 1.14,
            )
            suggested_entry = positive_or_default(
                num(
                    row,
                    "adjusted_entry_price",
                    num(row, "suggested_entry_price"),
                ),
                entry_high,
            )

            if suggested_entry <= 0 or stop_loss <= 0:
                continue

            risk_per_share = suggested_entry - stop_loss

            if risk_per_share <= 0:
                continue

            raw_weight = num(row, "allocation_weight") / total_weight
            allocation_factor = self.allocation_factor(row)

            weighted_allocation = (
                max_exposure_value
                * raw_weight
                * allocation_factor
            )

            max_position_value = (
                self.config.capital
                * self.config.max_position_pct
            )

            capital_based_allocation = min(
                weighted_allocation,
                max_position_value,
                max_exposure_value - used_capital,
            )

            risk_budget_remaining = max(
                max_portfolio_loss - used_risk,
                0,
            )

            allowed_trade_loss = min(
                max_trade_loss,
                risk_budget_remaining,
            )

            risk_based_quantity = int(
                allowed_trade_loss // risk_per_share
            )

            capital_based_quantity = int(
                capital_based_allocation // suggested_entry
            )

            quantity = min(
                risk_based_quantity,
                capital_based_quantity,
            )

            if quantity <= 0:
                continue

            investment = round(
                quantity * suggested_entry,
                2,
            )

            if (
                investment < self.config.min_position_value
                and suggested_entry <= self.config.min_position_value
            ):
                min_quantity = math.ceil(
                    self.config.min_position_value / suggested_entry
                )

                min_investment = min_quantity * suggested_entry
                min_risk = min_quantity * risk_per_share

                if (
                    min_investment <= max_position_value
                    and min_investment <= max_exposure_value - used_capital
                    and min_risk <= allowed_trade_loss
                ):
                    quantity = min_quantity
                    investment = round(min_investment, 2)

            if quantity <= 0 or investment <= 0:
                continue

            max_loss = round(
                quantity * risk_per_share,
                2,
            )

            if used_risk + max_loss > max_portfolio_loss:
                continue

            expected_profit_t1 = round(
                quantity
                * max(target_1 - suggested_entry, 0),
                2,
            )
            expected_profit_t2 = round(
                quantity
                * max(target_2 - suggested_entry, 0),
                2,
            )

            used_capital += investment
            used_risk += max_loss

            trades.append({
                "rank": len(trades) + 1,
                "symbol": row.get("symbol", ""),
                "company": row.get("company", ""),
                "sector": row.get("sector", "UNKNOWN"),
                "industry": row.get("industry", "UNKNOWN"),
                "final_decision": row.get("final_decision", ""),
                "consensus_decision": row.get(
                    "consensus_decision",
                    "",
                ),
                "final_score": round(
                    num(row, "final_score"),
                    2,
                ),
                "consensus_score": round(
                    num(row, "consensus_score"),
                    2,
                ),
                "buy_probability": round(
                    num(row, "buy_probability"),
                    2,
                ),
                "confidence_v3": round(
                    num(
                        row,
                        "confidence_v3",
                        num(row, "confidence", 50),
                    ),
                    2,
                ),
                "portfolio_rank_score": round(
                    num(row, "portfolio_rank_score"),
                    2,
                ),
                "position_quality_index": round(
                    num(row, "position_quality_index"),
                    2,
                ),
                "institutional_portfolio_score": round(
                    num(row, "institutional_portfolio_score"),
                    2,
                ),
                "smart_money_score": round(
                    num(row, "smart_money_score"),
                    2,
                ),
                "accumulation_score": round(
                    num(row, "accumulation_score"),
                    2,
                ),
                "trade_validation_score": round(
                    num(row, "trade_validation_score"),
                    2,
                ),
                "entry_timing_score": round(
                    num(row, "entry_timing_score"),
                    2,
                ),
                "entry_timing_action": row.get(
                    "entry_timing_action",
                    "",
                ),
                "risk_management_score": round(
                    num(row, "risk_management_score"),
                    2,
                ),
                "risk_permission": row.get(
                    "risk_permission",
                    "",
                ),
                "risk_status": row.get(
                    "risk_status",
                    "",
                ),
                "portfolio_fallback_candidate": bool(
                    row.get(
                        "portfolio_fallback_candidate",
                        False,
                    )
                ),
                "allocation_weight": round(
                    num(row, "allocation_weight"),
                    2,
                ),
                "allocation_factor": round(
                    allocation_factor,
                    2,
                ),
                "allocation": round(
                    capital_based_allocation,
                    2,
                ),
                "quantity": int(quantity),
                "final_quantity": int(quantity),
                "investment": investment,
                "suggested_entry_price": round(
                    suggested_entry,
                    2,
                ),
                "adjusted_entry_price": round(
                    suggested_entry,
                    2,
                ),
                "entry_low": round(entry_low, 2),
                "entry_high": round(entry_high, 2),
                "stop_loss": round(stop_loss, 2),
                "target_1": round(target_1, 2),
                "target_2": round(target_2, 2),
                "risk_per_share": round(
                    risk_per_share,
                    2,
                ),
                "max_loss": max_loss,
                "expected_profit_t1": expected_profit_t1,
                "expected_profit_t2": expected_profit_t2,
                "risk_reward_t1": round(
                    num(row, "risk_reward_t1"),
                    2,
                ),
                "risk_pct_of_capital": round(
                    max_loss / self.config.capital * 100
                    if self.config.capital > 0
                    else 0,
                    2,
                ),
                "position_pct_of_capital": round(
                    investment / self.config.capital * 100
                    if self.config.capital > 0
                    else 0,
                    2,
                ),
                "position_status": self.position_status(row),
                "exit_plan": self.exit_plan(row),
                "position_reason": self.position_reason(row),
            })

        trades_df = pd.DataFrame(trades)

        if not trades_df.empty:
            trades_df = trades_df.sort_values(
                by=[
                    "portfolio_rank_score",
                    "position_quality_index",
                    "buy_probability",
                ],
                ascending=[False, False, False],
            ).reset_index(drop=True)

            trades_df["rank"] = range(
                1,
                len(trades_df) + 1,
            )

        return trades_df

    def allocation_weight(self, row: pd.Series) -> float:
        quality = num(row, "position_quality_index", 50)
        institutional = num(
            row,
            "institutional_portfolio_score",
            50,
        )
        rank_score = num(row, "portfolio_rank_score", 50)
        risk_score = num(row, "risk_management_score", 50)
        validation = num(row, "trade_validation_score", 50)
        atr_percent = max(num(row, "atr_percent", 5), 0.5)
        stop_distance = max(
            num(
                row,
                "stop_distance_pct",
                self.calculate_stop_distance(row),
            ),
            1.0,
        )

        quality_weight = (
            rank_score * 0.30
            + quality * 0.25
            + institutional * 0.20
            + risk_score * 0.15
            + validation * 0.10
        )

        volatility_penalty = 1 / (
            1
            + atr_percent / 10
            + stop_distance / 20
        )

        return max(
            quality_weight * volatility_penalty,
            1.0,
        )

    def allocation_factor(self, row: pd.Series) -> float:
        risk_permission = text(row, "risk_permission")
        entry_action = text(row, "entry_timing_action")
        consensus_decision = text(row, "consensus_decision")
        change_pct = num(row, "change_pct")
        rsi = num(row, "rsi", 50)
        atr_percent = num(row, "atr_percent", 5)
        risk_reward = num(row, "risk_reward_t1", 1.15)
        risk_factor = num(row, "position_risk_factor", 1.0)
        fallback = bool(
            row.get("portfolio_fallback_candidate", False)
        )

        factor = 1.0

        if risk_permission == "TRADE ALLOWED":
            factor *= 1.0
        elif risk_permission == "TRADE ALLOWED SMALL":
            factor *= 0.82
        elif risk_permission == "WAIT":
            factor *= 0.68
        else:
            factor *= 0.55

        if consensus_decision == "BUY":
            factor *= 1.0
        elif consensus_decision == "BUY SMALL":
            factor *= 0.88

        if entry_action == "BUY NOW":
            factor *= 1.0
        elif entry_action == "BUY ON DIP":
            factor *= 0.85
        elif entry_action == "WAIT PULLBACK":
            factor *= 0.65
        elif entry_action == "BUY ABOVE BREAKOUT":
            factor *= 0.60

        if risk_reward >= 1.80:
            factor *= 1.08
        elif risk_reward >= 1.40:
            factor *= 1.03
        elif risk_reward < 1.25:
            factor *= 0.82

        if change_pct >= 7:
            factor *= 0.72
        elif change_pct >= 4:
            factor *= 0.88

        if rsi >= 78:
            factor *= 0.82

        if atr_percent >= 8:
            factor *= 0.75

        if fallback:
            factor *= 0.80

        factor *= clamp(risk_factor, 0.35, 1.25)

        return clamp(factor, 0.25, 1.10)

    def dynamic_exposure_pct(
        self,
        market_score: float,
        market_mood: str,
    ) -> float:
        mood = market_mood.upper()

        if mood in ["PANIC", "STRONG BEARISH"]:
            return 0.20

        if mood == "BEARISH" or market_score < 40:
            return 0.30

        if mood in ["SIDEWAYS", "MIXED"] or market_score < 50:
            return 0.50

        if mood == "BULLISH" and market_score < 60:
            return 0.65

        if mood == "BULLISH" and market_score < 75:
            return 0.75

        if mood in ["BULLISH", "STRONG BULLISH"] and market_score >= 75:
            return 0.85

        return clamp(
            self.config.base_exposure_pct,
            0.20,
            0.85,
        )

    def dynamic_target_positions(
        self,
        market_score: float,
        market_mood: str,
    ) -> int:
        mood = market_mood.upper()

        if mood in ["PANIC", "STRONG BEARISH"]:
            return 1

        if mood == "BEARISH" or market_score < 40:
            return min(2, self.config.max_positions)

        if mood in ["SIDEWAYS", "MIXED"] or market_score < 50:
            return min(3, self.config.max_positions)

        if mood == "BULLISH" and market_score < 65:
            return min(
                max(self.config.min_positions_bullish, 2),
                self.config.max_positions,
            )

        if market_score < 75:
            return min(4, self.config.max_positions)

        return self.config.max_positions

    def calculate_stop_distance(
        self,
        row: pd.Series,
    ) -> float:
        entry = num(
            row,
            "adjusted_entry_price",
            num(row, "entry_high", num(row, "close")),
        )
        stop = num(row, "stop_loss")

        if entry <= 0 or stop <= 0 or stop >= entry:
            return 0

        return (
            (entry - stop)
            / entry
            * 100
        )

    def position_status(self, row: pd.Series) -> str:
        risk_permission = text(row, "risk_permission")
        entry_action = text(row, "entry_timing_action")
        fallback = bool(
            row.get("portfolio_fallback_candidate", False)
        )

        if fallback:
            return "CONTROLLED FALLBACK POSITION"

        if risk_permission == "WAIT":
            return "CONTROLLED / SMALL ENTRY"

        if entry_action in ["BUY ON DIP", "WAIT PULLBACK"]:
            return "WAIT ENTRY LEVEL"

        if entry_action == "BUY NOW":
            return "READY TO BUY"

        return "CONTROLLED"

    def exit_plan(self, row: pd.Series) -> str:
        return (
            "Book 40% near Target 1 | Move stop to breakeven after 3-4% gain | "
            "Trail 40% toward Target 2 | Keep final 20% only while trend remains valid | "
            "Never average down below stop loss"
        )

    def position_reason(self, row: pd.Series) -> str:
        """
        Build a clean, non-contradictory and de-duplicated position reason.

        Resolved metadata warnings are removed when sector/industry values
        are already available. Repeated warnings from multiple engines are
        collapsed case-insensitively while preserving useful order.
        """
        sector = text(row, "sector", "UNKNOWN")
        industry = text(row, "industry", "UNKNOWN")

        sector_known = sector not in {
            "",
            "UNKNOWN",
            "NAN",
            "NONE",
        }
        industry_known = industry not in {
            "",
            "UNKNOWN",
            "NAN",
            "NONE",
        }

        raw_parts: list[str] = []

        for column in [
            "portfolio_reason",
            "portfolio_warning",
            "consensus_reason",
            "consensus_warnings",
            "risk_management_warnings",
            "entry_timing_warning",
            "validation_warnings",
        ]:
            value = clean_text(row.get(column, ""))

            if not value:
                continue

            raw_parts.extend(
                split_reason_fragments(value)
            )

        cleaned_parts: list[str] = []

        for part in raw_parts:
            normalized = normalize_reason_key(part)

            if not normalized:
                continue

            if (
                sector_known
                and normalized in {
                    "sector metadata missing",
                    "sector missing",
                    "unknown sector",
                }
            ):
                continue

            if (
                industry_known
                and normalized in {
                    "industry metadata missing",
                    "industry missing",
                    "unknown industry",
                }
            ):
                continue

            cleaned_parts.append(
                clean_reason_fragment(part)
            )

        return " | ".join(
            unique_strings_case_insensitive(
                cleaned_parts
            )
        )


    def portfolio_health_score(
        self,
        trades: pd.DataFrame,
        market_score: float,
    ) -> float:
        if trades is None or trades.empty:
            return 0.0

        avg_quality = float(
            trades["position_quality_index"].mean()
        )
        avg_institutional = float(
            trades["institutional_portfolio_score"].mean()
        )
        risk_pct = float(
            trades["risk_pct_of_capital"].sum()
        )

        concentration_penalty = 0.0

        if "sector" in trades.columns and len(trades) > 1:
            max_sector_count = int(
                trades["sector"].value_counts().max()
            )

            if max_sector_count > 1:
                concentration_penalty = (
                    max_sector_count - 1
                ) * 4

        score = (
            avg_quality * 0.45
            + avg_institutional * 0.25
            + market_score * 0.15
            + max(0, 100 - risk_pct * 12) * 0.15
            - concentration_penalty
        )

        return round(
            clamp(score, 0, 100),
            2,
        )

    def portfolio_heat_status(
        self,
        risk_pct: float,
    ) -> str:
        if risk_pct <= 1.25:
            return "LOW HEAT"

        if risk_pct <= 2.00:
            return "CONTROLLED HEAT"

        if risk_pct <= self.config.max_portfolio_risk_pct:
            return "MAX CONTROLLED HEAT"

        return "RISK LIMIT EXCEEDED"

    def ensure_columns(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        defaults = {
            "symbol": "",
            "company": "",
            "sector": "UNKNOWN",
            "industry": "UNKNOWN",
            "market_mood": "SIDEWAYS",
            "final_decision": "",
            "consensus_decision": "",
            "trade_action": "",
            "entry_timing_action": "",
            "risk_permission": "",
            "risk_status": "",
            "risk_action": "",
            "risk_management_warnings": "",
            "entry_timing_warning": "",
            "validation_warnings": "",
            "consensus_reason": "",
            "consensus_warnings": "",
            "close": 0,
            "change_pct": 0,
            "volume": 0,
            "value_traded": 0,
            "rsi": 50,
            "atr_percent": 5,
            "final_score": 0,
            "consensus_score": 0,
            "consensus_confidence": 50,
            "ai_score": 0,
            "buy_probability": 0,
            "confidence": 50,
            "confidence_v3": 50,
            "trend_score_v4": 50,
            "trend_score_v5": 50,
            "smart_money_score": 50,
            "accumulation_score": 50,
            "distribution_score": 25,
            "institutional_v5_score": 50,
            "trade_validation_score": 0,
            "entry_timing_score": 0,
            "risk_management_score": 50,
            "position_risk_factor": 1,
            "risk_reward_t1": 0,
            "stop_distance_pct": 0,
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
        }

        for column, default in defaults.items():
            if column not in df.columns:
                df[column] = default

        return df

    def normalize_columns(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        numeric_columns = [
            "close",
            "change_pct",
            "volume",
            "value_traded",
            "rsi",
            "atr_percent",
            "final_score",
            "consensus_score",
            "consensus_confidence",
            "ai_score",
            "buy_probability",
            "confidence",
            "confidence_v3",
            "trend_score_v4",
            "trend_score_v5",
            "smart_money_score",
            "accumulation_score",
            "distribution_score",
            "institutional_v5_score",
            "trade_validation_score",
            "entry_timing_score",
            "risk_management_score",
            "position_risk_factor",
            "risk_reward_t1",
            "stop_distance_pct",
            "sector_score",
            "sector_strength_score",
            "market_score",
            "liquidity_score_v4",
            "liquidity_score_raw",
            "volume_score_v4",
            "volume_strength",
            "entry_low",
            "entry_high",
            "stop_loss",
            "target_1",
            "target_2",
            "adjusted_entry_price",
            "suggested_entry_price",
        ]

        for column in numeric_columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            ).fillna(0)

        text_columns = [
            "symbol",
            "company",
            "sector",
            "industry",
            "market_mood",
            "final_decision",
            "consensus_decision",
            "trade_action",
            "entry_timing_action",
            "risk_permission",
            "risk_status",
            "risk_action",
        ]

        for column in text_columns:
            df[column] = (
                df[column]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.upper()
            )

        return df

    def empty_plan(
        self,
        reason: str,
    ) -> dict:
        return {
            "engine_version": self.VERSION,
            "mode": "AI_V5_INSTITUTIONAL_RISK_PARITY",
            "capital": round(self.config.capital, 2),
            "market_score": 0,
            "market_mood": "UNKNOWN",
            "dynamic_exposure_pct": 0,
            "target_positions": 0,
            "max_positions": int(self.config.max_positions),
            "firewall_removed": 0,
            "eligible_candidates": 0,
            "selected_positions": 0,
            "used_capital": 0,
            "cash_reserve": round(self.config.capital, 2),
            "capital_utilization_pct": 0,
            "total_expected_profit_t1": 0,
            "total_expected_profit_t2": 0,
            "total_max_loss_to_sl": 0,
            "portfolio_risk_pct": 0,
            "portfolio_heat_status": "NO HEAT",
            "portfolio_health_score": 0,
            "trades": pd.DataFrame(),
            "reason": reason,
        }


def build_portfolio_plan_v5(
    final_df: pd.DataFrame,
    capital: float = 50000,
    max_positions: int = 5,
    min_positions_bullish: int = 2,
    min_position_value: float = 3000,
    max_position_pct: float = 0.28,
    max_sector_positions: int = 2,
    base_exposure_pct: float = 0.70,
    max_portfolio_risk_pct: float = 2.50,
    per_trade_risk_pct: float = 0.80,
) -> dict:
    engine = PortfolioEngineV5(
        capital=capital,
        max_positions=max_positions,
        min_positions_bullish=min_positions_bullish,
        min_position_value=min_position_value,
        max_position_pct=max_position_pct,
        max_sector_positions=max_sector_positions,
        base_exposure_pct=base_exposure_pct,
        max_portfolio_risk_pct=max_portfolio_risk_pct,
        per_trade_risk_pct=per_trade_risk_pct,
    )

    return engine.build(final_df)


def remove_duplicate_columns(
    df: pd.DataFrame,
) -> pd.DataFrame:
    if df is None or not hasattr(df, "columns"):
        return pd.DataFrame()

    return df.loc[
        :,
        ~df.columns.duplicated(),
    ].copy()


def num(
    row: pd.Series,
    key: str,
    default: float = 0,
) -> float:
    value = row.get(key, default)

    try:
        if pd.isna(value):
            return float(default)
    except Exception:
        pass

    try:
        number = float(value)

        if math.isfinite(number):
            return number

        return float(default)

    except Exception:
        return float(default)


def text(
    row: pd.Series,
    key: str,
    default: str = "",
) -> str:
    return text_value(
        row.get(key, default),
        default,
    )


def text_value(
    value: Any,
    default: str = "",
) -> str:
    try:
        if pd.isna(value):
            return default.upper()
    except Exception:
        pass

    cleaned = str(value).strip()

    if not cleaned:
        return default.upper()

    return cleaned.upper()


def clean_text(
    value: Any,
) -> str:
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    cleaned = str(value).strip()

    if cleaned.lower() in {
        "",
        "nan",
        "none",
    }:
        return ""

    return cleaned


def unique_strings(
    values: list[str],
) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned = str(value).strip()

        if not cleaned or cleaned in seen:
            continue

        seen.add(cleaned)
        output.append(cleaned)

    return output


def split_reason_fragments(
    value: Any,
) -> list[str]:
    """
    Split multi-engine reason strings into individual fragments.
    """
    cleaned = clean_text(value)

    if not cleaned:
        return []

    fragments = []

    for part in cleaned.replace("\n", " | ").split("|"):
        item = part.strip()

        if item:
            fragments.append(item)

    return fragments


def normalize_reason_key(
    value: Any,
) -> str:
    """
    Normalize reason text for reliable de-duplication and filtering.
    """
    cleaned = clean_text(value).lower()

    cleaned = " ".join(
        cleaned.replace("warnings:", "")
        .replace("warning:", "")
        .replace(";", " ")
        .replace(",", " ")
        .split()
    )

    return cleaned


def clean_reason_fragment(
    value: Any,
) -> str:
    """
    Remove redundant prefixes while preserving readable reason text.
    """
    cleaned = clean_text(value)

    lowered = cleaned.lower()

    for prefix in (
        "warnings:",
        "warning:",
    ):
        if lowered.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            break

    return cleaned


def unique_strings_case_insensitive(
    values: list[str],
) -> list[str]:
    """
    Preserve first occurrence while removing repeated reason fragments
    regardless of capitalization or extra whitespace.
    """
    output: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned = clean_text(value)
        key = normalize_reason_key(cleaned)

        if not cleaned or not key or key in seen:
            continue

        seen.add(key)
        output.append(cleaned)

    return output



def positive_or_default(
    value: float,
    default: float,
) -> float:
    try:
        numeric = float(value)

        if numeric > 0 and math.isfinite(numeric):
            return numeric

    except Exception:
        pass

    return float(default)


def clamp(
    value: float,
    low: float,
    high: float,
) -> float:
    try:
        numeric = float(value)
    except Exception:
        numeric = low

    return max(
        low,
        min(high, numeric),
    )