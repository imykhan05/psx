from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class ExitIntelligenceConfigV1:
    """
    Configuration for Exit Intelligence Engine V1.
    """

    partial_profit_pct: float = 40.0
    final_profit_pct: float = 100.0
    breakeven_trigger_pct: float = 3.0
    trail_trigger_pct: float = 5.0
    emergency_loss_pct: float = -8.0
    max_holding_days: int = 5
    minimum_confidence: float = 55.0
    add_more_min_confidence: float = 82.0
    add_more_max_profit_pct: float = 2.5
    add_more_max_rsi: float = 72.0
    weak_rsi_level: float = 45.0
    overbought_rsi_level: float = 82.0


class ExitIntelligenceEngineV1:
    """
    Exit Intelligence Engine V1

    Purpose:
    - Analyze every active BUY / portfolio position.
    - Convert market, risk, momentum, trend and profit information into
      a practical trade-management recommendation.
    - Preserve backward compatibility with existing project dataframes.

    Supported actions:
    - BUY NOW
    - HOLD
    - ADD MORE
    - PARTIAL PROFIT
    - BOOK FULL PROFIT
    - MOVE STOPLOSS
    - TRAIL STOP
    - EXIT TODAY
    - EMERGENCY EXIT
    - NO ACTION
    """

    VERSION = "exit_intelligence_engine_v1_1_position_state_aware"

    ACTIONS = {
        "BUY NOW",
        "HOLD",
        "ADD MORE",
        "PARTIAL PROFIT",
        "BOOK FULL PROFIT",
        "MOVE STOPLOSS",
        "TRAIL STOP",
        "EXIT TODAY",
        "EMERGENCY EXIT",
        "NO ACTION",
    }

    ACTIVE_BUY_DECISIONS = {
        "BUY",
        "STRONG BUY",
        "BUY SMALL",
        "ACCUMULATE",
    }

    HARD_EXIT_RISK_STATUSES = {
        "REJECTED",
        "HIGH RISK",
        "CHASE RISK REJECTED",
        "VOLATILITY REJECTED",
        "RISK/REWARD REJECTED",
    }

    def __init__(
        self,
        partial_profit_pct: float = 40.0,
        final_profit_pct: float = 100.0,
        breakeven_trigger_pct: float = 3.0,
        trail_trigger_pct: float = 5.0,
        emergency_loss_pct: float = -8.0,
        max_holding_days: int = 5,
        minimum_confidence: float = 55.0,
        add_more_min_confidence: float = 82.0,
        add_more_max_profit_pct: float = 2.5,
        add_more_max_rsi: float = 72.0,
        weak_rsi_level: float = 45.0,
        overbought_rsi_level: float = 82.0,
    ):
        self.config = ExitIntelligenceConfigV1(
            partial_profit_pct=float(partial_profit_pct),
            final_profit_pct=float(final_profit_pct),
            breakeven_trigger_pct=float(breakeven_trigger_pct),
            trail_trigger_pct=float(trail_trigger_pct),
            emergency_loss_pct=float(emergency_loss_pct),
            max_holding_days=int(max_holding_days),
            minimum_confidence=float(minimum_confidence),
            add_more_min_confidence=float(add_more_min_confidence),
            add_more_max_profit_pct=float(add_more_max_profit_pct),
            add_more_max_rsi=float(add_more_max_rsi),
            weak_rsi_level=float(weak_rsi_level),
            overbought_rsi_level=float(overbought_rsi_level),
        )

    def apply(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Apply exit intelligence row-by-row.

        The function never mutates the input dataframe.
        """
        if df is None or not isinstance(df, pd.DataFrame):
            return pd.DataFrame()

        if df.empty:
            result = df.copy()
            return self.ensure_output_columns(result)

        result = remove_duplicate_columns(df.copy())
        result = self.ensure_input_columns(result)
        result = self.normalize_columns(result)

        exit_rows = result.apply(
            lambda row: pd.Series(
                self.analyze_position(row)
            ),
            axis=1,
        )

        result = remove_duplicate_columns(
            pd.concat(
                [
                    result.reset_index(drop=True),
                    exit_rows.reset_index(drop=True),
                ],
                axis=1,
            )
        )

        return result

    def analyze_position(
        self,
        row: pd.Series,
    ) -> dict:
        """
        Analyze one active or potential position.
        """
        final_decision = text(
            row,
            "final_decision",
        )
        consensus_decision = text(
            row,
            "consensus_decision",
        )
        portfolio_selected = bool_value(
            row.get(
                "portfolio_selected",
                False,
            )
        )
        quantity = int(
            max(
                num(
                    row,
                    "portfolio_quantity",
                    num(
                        row,
                        "quantity",
                        num(
                            row,
                            "final_quantity",
                            0,
                        ),
                    ),
                ),
                0,
            )
        )

        position_status = text(
            row,
            "position_status",
            text(
                row,
                "portfolio_position_status",
                "",
            ),
        )

        lifecycle_status = text(
            row,
            "lifecycle_status",
            text(
                row,
                "trade_status",
                "",
            ),
        )

        actual_entry_price = num(
            row,
            "actual_entry_price",
            num(
                row,
                "executed_entry_price",
                0,
            ),
        )

        actual_quantity = int(
            max(
                num(
                    row,
                    "actual_quantity",
                    num(
                        row,
                        "open_quantity",
                        num(
                            row,
                            "remaining_quantity",
                            0,
                        ),
                    ),
                ),
                0,
            )
        )

        open_position_markers = {
            "OPEN",
            "OPEN POSITION",
            "ACTIVE",
            "ACTIVE POSITION",
            "HOLDING",
            "PARTIAL",
            "PARTIALLY OPEN",
        }

        closed_position_markers = {
            "CLOSED",
            "EXITED",
            "STOPPED OUT",
            "BOOKED",
            "FULL EXIT",
        }

        is_closed_position = (
            lifecycle_status in closed_position_markers
            or position_status in closed_position_markers
        )

        is_actual_open_position = (
            not is_closed_position
            and (
                actual_quantity > 0
                or actual_entry_price > 0
                or lifecycle_status in open_position_markers
                or position_status in open_position_markers
            )
        )

        is_entry_candidate = (
            not is_actual_open_position
            and not is_closed_position
            and portfolio_selected
            and (
                final_decision in self.ACTIVE_BUY_DECISIONS
                or consensus_decision in self.ACTIVE_BUY_DECISIONS
            )
        )

        is_unselected_buy_signal = (
            not portfolio_selected
            and not is_actual_open_position
            and (
                final_decision in self.ACTIVE_BUY_DECISIONS
                or consensus_decision in self.ACTIVE_BUY_DECISIONS
            )
        )

        if is_closed_position:
            return self.no_action_result(
                "Position already closed"
            )

        if is_unselected_buy_signal:
            return self.no_action_result(
                "BUY signal exists but position was not selected"
            )

        current_price = positive_or_default(
            num(
                row,
                "close",
                num(
                    row,
                    "current_price",
                    0,
                ),
            ),
            0,
        )

        entry_price = positive_or_default(
            actual_entry_price
            if is_actual_open_position
            else num(
                row,
                "adjusted_entry_price",
                num(
                    row,
                    "suggested_entry_price",
                    num(
                        row,
                        "entry_price",
                        num(
                            row,
                            "entry_high",
                            current_price,
                        ),
                    ),
                ),
            ),
            current_price,
        )

        original_stop = positive_or_default(
            num(
                row,
                "stop_loss",
                0,
            ),
            entry_price * 0.94
            if entry_price > 0
            else 0,
        )

        target_1 = positive_or_default(
            num(
                row,
                "target_1",
                0,
            ),
            entry_price * 1.07
            if entry_price > 0
            else 0,
        )

        target_2 = positive_or_default(
            num(
                row,
                "target_2",
                0,
            ),
            entry_price * 1.14
            if entry_price > 0
            else 0,
        )

        if current_price <= 0 or entry_price <= 0:
            return self.no_action_result(
                "Current price or entry price unavailable"
            )

        profit_pct = (
            (current_price - entry_price)
            / entry_price
            * 100
        )

        atr = max(
            num(
                row,
                "atr",
                0,
            ),
            0,
        )
        atr_percent = max(
            num(
                row,
                "atr_percent",
                0,
            ),
            0,
        )
        rsi = num(
            row,
            "rsi",
            50,
        )
        macd = num(
            row,
            "macd",
            0,
        )
        macd_signal = num(
            row,
            "macd_signal",
            0,
        )
        macd_hist = num(
            row,
            "macd_hist",
            macd - macd_signal,
        )
        trend_score = num(
            row,
            "trend_score_v5",
            num(
                row,
                "trend_score_v4",
                num(
                    row,
                    "trend_strength",
                    50,
                ),
            ),
        )
        buy_probability = num(
            row,
            "buy_probability",
            50,
        )
        confidence = num(
            row,
            "confidence_v3",
            num(
                row,
                "confidence",
                50,
            ),
        )
        risk_score = num(
            row,
            "risk_management_score",
            50,
        )
        smart_money_score = num(
            row,
            "smart_money_score",
            50,
        )
        accumulation_score = num(
            row,
            "accumulation_score",
            50,
        )
        distribution_score = num(
            row,
            "distribution_score",
            25,
        )
        sector_strength = num(
            row,
            "sector_strength_score",
            num(
                row,
                "sector_score",
                50,
            ),
        )
        market_score = num(
            row,
            "market_score",
            50,
        )
        volume_ratio = num(
            row,
            "volume_ratio_20",
            num(
                row,
                "volume_ratio_5",
                1,
            ),
        )
        change_pct = num(
            row,
            "change_pct",
            0,
        )
        risk_permission = text(
            row,
            "risk_permission",
        )
        risk_status = text(
            row,
            "risk_status",
        )
        risk_action = text(
            row,
            "risk_action",
        )
        entry_action = text(
            row,
            "entry_timing_action",
        )
        market_mood = text(
            row,
            "market_mood",
            "SIDEWAYS",
        )
        holding_days = int(
            max(
                num(
                    row,
                    "holding_days_numeric",
                    num(
                        row,
                        "holding_days",
                        num(
                            row,
                            "days_held",
                            0,
                        ),
                    ),
                ),
                0,
            )
        )

        target_1_hit = current_price >= target_1 > 0
        target_2_hit = current_price >= target_2 > 0
        stop_hit = current_price <= original_stop > 0

        bearish_macd = (
            macd < macd_signal
            and macd_hist < 0
        )
        bullish_macd = (
            macd > macd_signal
            and macd_hist > 0
        )

        weak_trend = trend_score < 45
        strong_trend = trend_score >= 75
        weak_smart_money = smart_money_score < 45
        strong_smart_money = smart_money_score >= 75
        heavy_distribution = distribution_score >= 65
        weak_sector = sector_strength < 45
        weak_market = (
            market_score < 40
            or market_mood in {
                "BEARISH",
                "STRONG BEARISH",
                "PANIC",
            }
        )

        hard_risk_exit = (
            risk_permission == "NO TRADE"
            or risk_action == "AVOID"
            or risk_status in self.HARD_EXIT_RISK_STATUSES
        )

        # ---------------------------------------------------------
        # ENTRY CANDIDATE LOGIC
        # Portfolio-selected stocks are recommendations, not holdings.
        # They must receive BUY NOW / NO ACTION, never HOLD or EXIT.
        # ---------------------------------------------------------
        if is_entry_candidate:
            if risk_permission == "WAIT":
                return self.build_result(
                    action="NO ACTION",
                    reasons=[
                        "Portfolio candidate is waiting for risk approval",
                        "No actual position has been opened",
                    ],
                    risk_level="MEDIUM",
                    current_price=current_price,
                    entry_price=entry_price,
                    original_stop=original_stop,
                    suggested_stop=original_stop,
                    trailing_stop=original_stop,
                    profit_lock_pct=0,
                    target_status="NOT ENTERED",
                    confidence=self.exit_confidence(
                        base=58,
                        confidence=confidence,
                        risk_score=risk_score,
                        trend_score=trend_score,
                    ),
                    profit_pct=0,
                )

            if (
                risk_permission in {
                    "TRADE ALLOWED",
                    "TRADE ALLOWED SMALL",
                }
                and entry_action == "BUY NOW"
            ):
                return self.build_result(
                    action="BUY NOW",
                    reasons=[
                        "Portfolio candidate selected",
                        "Entry timing approves immediate entry",
                        "Risk engine permits trade",
                        "No actual position has been opened yet",
                    ],
                    risk_level=(
                        "CONTROLLED"
                        if risk_permission == "TRADE ALLOWED SMALL"
                        else "LOW"
                    ),
                    current_price=current_price,
                    entry_price=entry_price,
                    original_stop=original_stop,
                    suggested_stop=original_stop,
                    trailing_stop=original_stop,
                    profit_lock_pct=0,
                    target_status="NOT ENTERED",
                    confidence=self.exit_confidence(
                        base=84,
                        confidence=confidence,
                        risk_score=risk_score,
                        trend_score=trend_score,
                    ),
                    profit_pct=0,
                )

            return self.build_result(
                action="NO ACTION",
                reasons=[
                    "Portfolio candidate selected but entry conditions are not approved",
                    "No actual position has been opened",
                ],
                risk_level="MEDIUM",
                current_price=current_price,
                entry_price=entry_price,
                original_stop=original_stop,
                suggested_stop=original_stop,
                trailing_stop=original_stop,
                profit_lock_pct=0,
                target_status="NOT ENTERED",
                confidence=self.exit_confidence(
                    base=55,
                    confidence=confidence,
                    risk_score=risk_score,
                    trend_score=trend_score,
                ),
                profit_pct=0,
            )

        if not is_actual_open_position:
            return self.no_action_result(
                "No actual open position"
            )

        emergency_reasons = []

        if stop_hit:
            emergency_reasons.append(
                "Stop loss breached"
            )

        if profit_pct <= self.config.emergency_loss_pct:
            emergency_reasons.append(
                "Loss exceeded emergency threshold"
            )

        if (
            hard_risk_exit
            and bearish_macd
            and weak_trend
        ):
            emergency_reasons.append(
                "Risk engine, MACD and trend all turned negative"
            )

        if (
            heavy_distribution
            and weak_smart_money
            and bearish_macd
        ):
            emergency_reasons.append(
                "Distribution and institutional selling pressure"
            )

        if emergency_reasons:
            return self.build_result(
                action="EMERGENCY EXIT",
                reasons=emergency_reasons,
                risk_level="CRITICAL",
                current_price=current_price,
                entry_price=entry_price,
                original_stop=original_stop,
                suggested_stop=current_price,
                trailing_stop=current_price,
                profit_lock_pct=max(profit_pct, 0),
                target_status=self.target_status(
                    target_1_hit,
                    target_2_hit,
                ),
                confidence=self.exit_confidence(
                    base=95,
                    confidence=confidence,
                    risk_score=risk_score,
                    trend_score=trend_score,
                ),
                profit_pct=profit_pct,
            )

        if target_2_hit:
            return self.build_result(
                action="BOOK FULL PROFIT",
                reasons=[
                    "Target 2 achieved",
                    "Full planned reward captured",
                ],
                risk_level="LOW",
                current_price=current_price,
                entry_price=entry_price,
                original_stop=original_stop,
                suggested_stop=max(
                    original_stop,
                    target_1,
                ),
                trailing_stop=max(
                    original_stop,
                    current_price - self.trailing_distance(
                        current_price,
                        atr,
                        atr_percent,
                    ),
                ),
                profit_lock_pct=self.config.final_profit_pct,
                target_status="TARGET 2 HIT",
                confidence=self.exit_confidence(
                    base=96,
                    confidence=confidence,
                    risk_score=risk_score,
                    trend_score=trend_score,
                ),
                profit_pct=profit_pct,
            )

        if target_1_hit:
            if (
                strong_trend
                and bullish_macd
                and strong_smart_money
                and not heavy_distribution
            ):
                action = "PARTIAL PROFIT"
                reasons = [
                    "Target 1 achieved",
                    "Trend remains strong",
                    "Book partial profit and trail remaining quantity",
                ]
            else:
                action = "BOOK FULL PROFIT"
                reasons = [
                    "Target 1 achieved",
                    "Momentum or trend no longer strong enough to hold",
                ]

            trailing_stop = max(
                entry_price,
                current_price - self.trailing_distance(
                    current_price,
                    atr,
                    atr_percent,
                ),
            )

            return self.build_result(
                action=action,
                reasons=reasons,
                risk_level=(
                    "LOW"
                    if action == "PARTIAL PROFIT"
                    else "MEDIUM"
                ),
                current_price=current_price,
                entry_price=entry_price,
                original_stop=original_stop,
                suggested_stop=max(
                    entry_price,
                    trailing_stop,
                ),
                trailing_stop=trailing_stop,
                profit_lock_pct=(
                    self.config.partial_profit_pct
                    if action == "PARTIAL PROFIT"
                    else self.config.final_profit_pct
                ),
                target_status="TARGET 1 HIT",
                confidence=self.exit_confidence(
                    base=90,
                    confidence=confidence,
                    risk_score=risk_score,
                    trend_score=trend_score,
                ),
                profit_pct=profit_pct,
            )

        exit_today_reasons = []

        if hard_risk_exit:
            exit_today_reasons.append(
                "Risk engine no longer permits trade"
            )

        if (
            weak_trend
            and bearish_macd
        ):
            exit_today_reasons.append(
                "Trend broken with bearish MACD confirmation"
            )

        if (
            rsi < self.config.weak_rsi_level
            and bearish_macd
        ):
            exit_today_reasons.append(
                "RSI and MACD both weakened"
            )

        if weak_market and weak_sector:
            exit_today_reasons.append(
                "Market and sector both weak"
            )

        if (
            holding_days >= self.config.max_holding_days
            and profit_pct <= 0
        ):
            exit_today_reasons.append(
                "Maximum holding period reached without profit"
            )

        if exit_today_reasons:
            return self.build_result(
                action="EXIT TODAY",
                reasons=exit_today_reasons,
                risk_level="HIGH",
                current_price=current_price,
                entry_price=entry_price,
                original_stop=original_stop,
                suggested_stop=max(
                    original_stop,
                    current_price - self.trailing_distance(
                        current_price,
                        atr,
                        atr_percent,
                    ),
                ),
                trailing_stop=max(
                    original_stop,
                    current_price - self.trailing_distance(
                        current_price,
                        atr,
                        atr_percent,
                    ),
                ),
                profit_lock_pct=max(profit_pct, 0),
                target_status=self.target_status(
                    target_1_hit,
                    target_2_hit,
                ),
                confidence=self.exit_confidence(
                    base=84,
                    confidence=confidence,
                    risk_score=risk_score,
                    trend_score=trend_score,
                ),
                profit_pct=profit_pct,
            )

        if profit_pct >= self.config.trail_trigger_pct:
            trail_stop = max(
                entry_price,
                current_price - self.trailing_distance(
                    current_price,
                    atr,
                    atr_percent,
                ),
            )

            return self.build_result(
                action="TRAIL STOP",
                reasons=[
                    "Profit exceeded trailing-stop trigger",
                    "Protect gains while trend remains valid",
                ],
                risk_level="LOW",
                current_price=current_price,
                entry_price=entry_price,
                original_stop=original_stop,
                suggested_stop=trail_stop,
                trailing_stop=trail_stop,
                profit_lock_pct=max(
                    min(
                        profit_pct * 0.60,
                        90,
                    ),
                    0,
                ),
                target_status=self.target_status(
                    target_1_hit,
                    target_2_hit,
                ),
                confidence=self.exit_confidence(
                    base=86,
                    confidence=confidence,
                    risk_score=risk_score,
                    trend_score=trend_score,
                ),
                profit_pct=profit_pct,
            )

        if profit_pct >= self.config.breakeven_trigger_pct:
            return self.build_result(
                action="MOVE STOPLOSS",
                reasons=[
                    "Trade moved sufficiently into profit",
                    "Move stop loss to breakeven",
                ],
                risk_level="LOW",
                current_price=current_price,
                entry_price=entry_price,
                original_stop=original_stop,
                suggested_stop=max(
                    original_stop,
                    entry_price,
                ),
                trailing_stop=max(
                    original_stop,
                    entry_price,
                ),
                profit_lock_pct=max(
                    min(
                        profit_pct * 0.35,
                        50,
                    ),
                    0,
                ),
                target_status=self.target_status(
                    target_1_hit,
                    target_2_hit,
                ),
                confidence=self.exit_confidence(
                    base=82,
                    confidence=confidence,
                    risk_score=risk_score,
                    trend_score=trend_score,
                ),
                profit_pct=profit_pct,
            )

        add_more_allowed = (
            profit_pct >= 0
            and profit_pct <= self.config.add_more_max_profit_pct
            and confidence >= self.config.add_more_min_confidence
            and buy_probability >= 80
            and strong_trend
            and bullish_macd
            and smart_money_score >= 80
            and accumulation_score >= 80
            and distribution_score < 50
            and rsi <= self.config.add_more_max_rsi
            and risk_permission in {
                "TRADE ALLOWED",
                "TRADE ALLOWED SMALL",
            }
            and risk_score >= 65
            and entry_action in {
                "BUY NOW",
                "BUY ON DIP",
            }
        )

        if add_more_allowed:
            return self.build_result(
                action="ADD MORE",
                reasons=[
                    "Position remains near entry",
                    "Trend, MACD and smart money remain strong",
                    "Risk engine still permits controlled exposure",
                ],
                risk_level="CONTROLLED",
                current_price=current_price,
                entry_price=entry_price,
                original_stop=original_stop,
                suggested_stop=original_stop,
                trailing_stop=original_stop,
                profit_lock_pct=0,
                target_status=self.target_status(
                    target_1_hit,
                    target_2_hit,
                ),
                confidence=self.exit_confidence(
                    base=80,
                    confidence=confidence,
                    risk_score=risk_score,
                    trend_score=trend_score,
                ),
                profit_pct=profit_pct,
            )

        if (
            profit_pct < 0
            and current_price > original_stop
            and not bearish_macd
            and not weak_trend
            and not hard_risk_exit
        ):
            return self.build_result(
                action="HOLD",
                reasons=[
                    "Price is below entry but stop loss remains intact",
                    "Trend has not broken",
                    "No confirmed exit signal",
                ],
                risk_level="MEDIUM",
                current_price=current_price,
                entry_price=entry_price,
                original_stop=original_stop,
                suggested_stop=original_stop,
                trailing_stop=original_stop,
                profit_lock_pct=0,
                target_status=self.target_status(
                    target_1_hit,
                    target_2_hit,
                ),
                confidence=self.exit_confidence(
                    base=72,
                    confidence=confidence,
                    risk_score=risk_score,
                    trend_score=trend_score,
                ),
                profit_pct=profit_pct,
            )

        if (
            profit_pct >= 0
            and strong_trend
            and confidence >= self.config.minimum_confidence
            and not bearish_macd
            and not hard_risk_exit
        ):
            return self.build_result(
                action="HOLD",
                reasons=[
                    "Trade remains profitable or near breakeven",
                    "Trend remains valid",
                    "No target or exit trigger reached",
                ],
                risk_level="LOW",
                current_price=current_price,
                entry_price=entry_price,
                original_stop=original_stop,
                suggested_stop=original_stop,
                trailing_stop=original_stop,
                profit_lock_pct=0,
                target_status=self.target_status(
                    target_1_hit,
                    target_2_hit,
                ),
                confidence=self.exit_confidence(
                    base=76,
                    confidence=confidence,
                    risk_score=risk_score,
                    trend_score=trend_score,
                ),
                profit_pct=profit_pct,
            )

        return self.build_result(
            action="NO ACTION",
            reasons=[
                "No exit, add-more or profit-booking trigger reached"
            ],
            risk_level="NORMAL",
            current_price=current_price,
            entry_price=entry_price,
            original_stop=original_stop,
            suggested_stop=original_stop,
            trailing_stop=original_stop,
            profit_lock_pct=0,
            target_status=self.target_status(
                target_1_hit,
                target_2_hit,
            ),
            confidence=self.exit_confidence(
                base=60,
                confidence=confidence,
                risk_score=risk_score,
                trend_score=trend_score,
            ),
            profit_pct=profit_pct,
        )

    def trailing_distance(
        self,
        current_price: float,
        atr: float,
        atr_percent: float,
    ) -> float:
        """
        Calculate practical trailing-stop distance.
        """
        atr_distance = atr * 1.5 if atr > 0 else 0
        percent_distance = (
            current_price
            * max(
                atr_percent,
                3.0,
            )
            / 100
        )

        distance = max(
            atr_distance,
            percent_distance,
        )

        maximum_distance = current_price * 0.10

        return clamp(
            distance,
            current_price * 0.02,
            maximum_distance,
        )

    def exit_confidence(
        self,
        base: float,
        confidence: float,
        risk_score: float,
        trend_score: float,
    ) -> float:
        score = (
            base * 0.55
            + confidence * 0.20
            + risk_score * 0.15
            + trend_score * 0.10
        )

        return round(
            clamp(
                score,
                0,
                100,
            ),
            2,
        )

    def target_status(
        self,
        target_1_hit: bool,
        target_2_hit: bool,
    ) -> str:
        if target_2_hit:
            return "TARGET 2 HIT"

        if target_1_hit:
            return "TARGET 1 HIT"

        return "TARGETS PENDING"

    def build_result(
        self,
        action: str,
        reasons: list[str],
        risk_level: str,
        current_price: float,
        entry_price: float,
        original_stop: float,
        suggested_stop: float,
        trailing_stop: float,
        profit_lock_pct: float,
        target_status: str,
        confidence: float,
        profit_pct: float,
    ) -> dict:
        action = (
            action
            if action in self.ACTIONS
            else "NO ACTION"
        )

        return {
            "exit_engine_version": self.VERSION,
            "exit_action": action,
            "exit_reason": " | ".join(
                unique_strings(
                    reasons
                )
            ),
            "exit_risk_level": str(
                risk_level
            ).upper(),
            "exit_suggested_action": action,
            "exit_current_price": round(
                current_price,
                2,
            ),
            "exit_entry_price": round(
                entry_price,
                2,
            ),
            "exit_original_stop_loss": round(
                original_stop,
                2,
            ),
            "exit_suggested_stop_loss": round(
                max(
                    suggested_stop,
                    0,
                ),
                2,
            ),
            "exit_trailing_stop": round(
                max(
                    trailing_stop,
                    0,
                ),
                2,
            ),
            "exit_profit_lock_pct": round(
                clamp(
                    profit_lock_pct,
                    0,
                    100,
                ),
                2,
            ),
            "exit_target_status": target_status,
            "exit_confidence": round(
                clamp(
                    confidence,
                    0,
                    100,
                ),
                2,
            ),
            "exit_profit_loss_pct": round(
                profit_pct,
                2,
            ),
        }

    def no_action_result(
        self,
        reason: str,
    ) -> dict:
        return {
            "exit_engine_version": self.VERSION,
            "exit_action": "NO ACTION",
            "exit_reason": reason,
            "exit_risk_level": "NORMAL",
            "exit_suggested_action": "NO ACTION",
            "exit_current_price": 0.0,
            "exit_entry_price": 0.0,
            "exit_original_stop_loss": 0.0,
            "exit_suggested_stop_loss": 0.0,
            "exit_trailing_stop": 0.0,
            "exit_profit_lock_pct": 0.0,
            "exit_target_status": "NOT APPLICABLE",
            "exit_confidence": 0.0,
            "exit_profit_loss_pct": 0.0,
        }

    def ensure_output_columns(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        defaults = self.no_action_result(
            "No data available"
        )

        for column, default in defaults.items():
            if column not in df.columns:
                df[column] = default

        return df

    def ensure_input_columns(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        defaults = {
            "symbol": "",
            "company": "",
            "date": "",
            "close": 0.0,
            "current_price": 0.0,
            "entry_price": 0.0,
            "adjusted_entry_price": 0.0,
            "suggested_entry_price": 0.0,
            "entry_high": 0.0,
            "stop_loss": 0.0,
            "target_1": 0.0,
            "target_2": 0.0,
            "final_decision": "",
            "consensus_decision": "",
            "portfolio_selected": False,
            "portfolio_quantity": 0,
            "quantity": 0,
            "final_quantity": 0,
            "actual_quantity": 0,
            "open_quantity": 0,
            "remaining_quantity": 0,
            "actual_entry_price": 0.0,
            "executed_entry_price": 0.0,
            "position_status": "",
            "portfolio_position_status": "",
            "lifecycle_status": "",
            "trade_status": "",
            "rsi": 50.0,
            "macd": 0.0,
            "macd_signal": 0.0,
            "macd_hist": 0.0,
            "atr": 0.0,
            "atr_percent": 0.0,
            "trend_score_v4": 50.0,
            "trend_score_v5": 50.0,
            "trend_strength": 50.0,
            "buy_probability": 50.0,
            "confidence": 50.0,
            "confidence_v3": 50.0,
            "risk_management_score": 50.0,
            "smart_money_score": 50.0,
            "accumulation_score": 50.0,
            "distribution_score": 25.0,
            "sector_score": 50.0,
            "sector_strength_score": 50.0,
            "market_score": 50.0,
            "volume_ratio_5": 1.0,
            "volume_ratio_20": 1.0,
            "change_pct": 0.0,
            "risk_permission": "",
            "risk_status": "",
            "risk_action": "",
            "entry_timing_action": "",
            "market_mood": "SIDEWAYS",
            "holding_days_numeric": 0,
            "holding_days": 0,
            "days_held": 0,
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
            "current_price",
            "entry_price",
            "adjusted_entry_price",
            "suggested_entry_price",
            "entry_high",
            "stop_loss",
            "target_1",
            "target_2",
            "portfolio_quantity",
            "quantity",
            "final_quantity",
            "actual_quantity",
            "open_quantity",
            "remaining_quantity",
            "actual_entry_price",
            "executed_entry_price",
            "rsi",
            "macd",
            "macd_signal",
            "macd_hist",
            "atr",
            "atr_percent",
            "trend_score_v4",
            "trend_score_v5",
            "trend_strength",
            "buy_probability",
            "confidence",
            "confidence_v3",
            "risk_management_score",
            "smart_money_score",
            "accumulation_score",
            "distribution_score",
            "sector_score",
            "sector_strength_score",
            "market_score",
            "volume_ratio_5",
            "volume_ratio_20",
            "change_pct",
            "holding_days_numeric",
            "holding_days",
            "days_held",
        ]

        for column in numeric_columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            ).fillna(0)

        text_columns = [
            "symbol",
            "company",
            "date",
            "final_decision",
            "consensus_decision",
            "risk_permission",
            "risk_status",
            "risk_action",
            "entry_timing_action",
            "market_mood",
            "position_status",
            "portfolio_position_status",
            "lifecycle_status",
            "trade_status",
        ]

        for column in text_columns:
            df[column] = (
                df[column]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.upper()
            )

        df["portfolio_selected"] = df[
            "portfolio_selected"
        ].apply(bool_value)

        return df


def apply_exit_intelligence_engine_v1(
    df: pd.DataFrame,
    partial_profit_pct: float = 40.0,
    final_profit_pct: float = 100.0,
    breakeven_trigger_pct: float = 3.0,
    trail_trigger_pct: float = 5.0,
    emergency_loss_pct: float = -8.0,
    max_holding_days: int = 5,
    minimum_confidence: float = 55.0,
    add_more_min_confidence: float = 82.0,
    add_more_max_profit_pct: float = 2.5,
    add_more_max_rsi: float = 72.0,
    weak_rsi_level: float = 45.0,
    overbought_rsi_level: float = 82.0,
) -> pd.DataFrame:
    engine = ExitIntelligenceEngineV1(
        partial_profit_pct=partial_profit_pct,
        final_profit_pct=final_profit_pct,
        breakeven_trigger_pct=breakeven_trigger_pct,
        trail_trigger_pct=trail_trigger_pct,
        emergency_loss_pct=emergency_loss_pct,
        max_holding_days=max_holding_days,
        minimum_confidence=minimum_confidence,
        add_more_min_confidence=add_more_min_confidence,
        add_more_max_profit_pct=add_more_max_profit_pct,
        add_more_max_rsi=add_more_max_rsi,
        weak_rsi_level=weak_rsi_level,
        overbought_rsi_level=overbought_rsi_level,
    )

    return engine.apply(
        df
    )


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
    default: float = 0.0,
) -> float:
    value = row.get(
        key,
        default,
    )

    try:
        if pd.isna(value):
            return float(
                default
            )
    except Exception:
        pass

    try:
        number = float(
            value
        )

        if math.isfinite(number):
            return number

        return float(
            default
        )

    except Exception:
        return float(
            default
        )


def text(
    row: pd.Series,
    key: str,
    default: str = "",
) -> str:
    value = row.get(
        key,
        default,
    )

    try:
        if pd.isna(value):
            return str(
                default
            ).upper()
    except Exception:
        pass

    cleaned = str(
        value
    ).strip()

    if not cleaned:
        return str(
            default
        ).upper()

    return cleaned.upper()


def positive_or_default(
    value: float,
    default: float,
) -> float:
    try:
        number = float(
            value
        )

        if number > 0 and math.isfinite(number):
            return number

    except Exception:
        pass

    return float(
        default
    )


def bool_value(
    value: Any,
) -> bool:
    if isinstance(
        value,
        bool,
    ):
        return value

    try:
        if pd.isna(value):
            return False
    except Exception:
        pass

    if isinstance(
        value,
        (
            int,
            float,
        ),
    ):
        return bool(
            value
        )

    return str(
        value
    ).strip().upper() in {
        "TRUE",
        "1",
        "YES",
        "Y",
        "SELECTED",
    }


def unique_strings(
    values: list[str],
) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned = str(
            value
        ).strip()

        key = cleaned.lower()

        if not cleaned or key in seen:
            continue

        seen.add(
            key
        )
        output.append(
            cleaned
        )

    return output


def clamp(
    value: float,
    low: float,
    high: float,
) -> float:
    try:
        number = float(
            value
        )
    except Exception:
        number = low

    return max(
        low,
        min(
            high,
            number,
        ),
    )