from __future__ import annotations

import math
import re
from typing import Iterable, List

import pandas as pd


ENGINE_VERSION = "institutional_v5_calibrator_1.2_balanced"

BLOCKED_SYMBOLS = {
    "JDMT",
}

BLOCKED_SYMBOL_PATTERNS = [
    r"ETF$",
    r".*ETF.*",
    r".*GIS.*",
    r"^P\d+GIS.*",
    r"^P\d+FRR.*",
    r"^P\d+TFC.*",
    r"^P\d+SUK.*",
]

BLOCKED_TEXT_KEYWORDS = [
    "ETF",
    "REIT",
    "FUND",
    "MUTUAL FUND",
    "TREASURY",
    "GOVT SECURITIES",
    "GOVERNMENT SECURITIES",
    "GIS",
    "SUKUK",
    "T-BILL",
    "T BILL",
    "BOND",
    "DEBT",
    "FIXED RATE",
    "FLOATING RATE",
]

# IMPORTANT:
# HIGH RISK removed from hard no-trade words.
# HIGH RISK should reduce score, not automatically kill trade.
NO_TRADE_WORDS = [
    "NO TRADE",
    "REJECTED",
    "AVOID",
    "CHASE RISK",
]


def _safe_num(series_or_value, default: float = 0.0):
    if isinstance(series_or_value, pd.Series):
        return pd.to_numeric(series_or_value, errors="coerce").fillna(default)

    try:
        if series_or_value is None:
            return default
        if isinstance(series_or_value, float) and math.isnan(series_or_value):
            return default
        return float(series_or_value)
    except Exception:
        return default


def _clip(series: pd.Series, low: float = 0.0, high: float = 100.0) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0).clip(lower=low, upper=high)


def _norm_0_100(series: pd.Series, neutral: float = 50.0) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")

    if s.notna().sum() == 0:
        return pd.Series(neutral, index=series.index, dtype="float64")

    s = s.fillna(s.median())
    lo = float(s.min())
    hi = float(s.max())

    if hi - lo < 1e-9:
        return pd.Series(neutral, index=series.index, dtype="float64")

    return ((s - lo) / (hi - lo) * 100.0).clip(0, 100)


def _percentile_score(series: pd.Series, neutral: float = 50.0) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")

    if s.notna().sum() <= 1:
        return pd.Series(neutral, index=series.index, dtype="float64")

    return (s.rank(pct=True, method="average") * 100.0).fillna(neutral).clip(0, 100)


def _text_contains_any(value: object, keywords: Iterable[str]) -> bool:
    text = str(value or "").upper().strip()
    return any(k in text for k in keywords)


def _matches_any_pattern(value: object, patterns: Iterable[str]) -> bool:
    text = str(value or "").upper().strip()
    return any(re.match(pattern, text) for pattern in patterns)


def _ensure_column(df: pd.DataFrame, column: str, default) -> pd.DataFrame:
    if column not in df.columns:
        df[column] = default
    return df


def _copy_raw_column(df: pd.DataFrame, column: str) -> None:
    raw_col = f"{column}_raw"
    if column in df.columns and raw_col not in df.columns:
        df[raw_col] = df[column]


def _security_firewall_flags(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in ["symbol", "company", "sector", "industry", "final_decision", "risk_permission", "risk_status"]:
        _ensure_column(df, col, "UNKNOWN")
        df[col] = df[col].astype(str).str.upper().str.strip()

    symbol_block = df["symbol"].isin(BLOCKED_SYMBOLS)
    pattern_block = df["symbol"].apply(lambda x: _matches_any_pattern(x, BLOCKED_SYMBOL_PATTERNS))

    text_block = pd.Series(False, index=df.index)
    for col in ["symbol", "company", "sector", "industry"]:
        text_block = text_block | df[col].apply(lambda x: _text_contains_any(x, BLOCKED_TEXT_KEYWORDS))

    df["institutional_v5_security_block"] = symbol_block | pattern_block | text_block

    block_reason: List[str] = []

    for _, row in df.iterrows():
        reasons = []
        symbol = str(row.get("symbol", "")).upper()

        if symbol in BLOCKED_SYMBOLS:
            reasons.append("hard blocked symbol")

        if _matches_any_pattern(symbol, BLOCKED_SYMBOL_PATTERNS):
            reasons.append("blocked symbol pattern")

        for col in ["company", "sector", "industry"]:
            if _text_contains_any(row.get(col, ""), BLOCKED_TEXT_KEYWORDS):
                reasons.append(f"blocked security type in {col}")

        block_reason.append(" | ".join(sorted(set(reasons))) if reasons else "")

    df["institutional_v5_security_block_reason"] = block_reason

    return df


def _build_component_scores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    numeric_defaults = {
        "final_score": 50.0,
        "ai_score": 50.0,
        "buy_probability": 50.0,
        "confidence_v3": 50.0,
        "smart_money_score": 50.0,
        "accumulation_score": 50.0,
        "trade_validation_score": 50.0,
        "entry_timing_score": 50.0,
        "risk_management_score": 40.0,
        "trend_score_v5": 50.0,
        "liquidity_score_raw": 50.0,
        "volume_ratio_20": 1.0,
        "value_traded": 0.0,
        "rsi": 50.0,
        "atr_percent": 5.0,
        "change_pct": 0.0,
        "risk_reward_t1": 1.0,
    }

    for col, default in numeric_defaults.items():
        _ensure_column(df, col, default)
        df[col] = _safe_num(df[col], default)

    for col in [
        "final_score",
        "ai_score",
        "buy_probability",
        "confidence",
        "confidence_v3",
        "final_decision",
        "verdict",
        "risk_level",
    ]:
        _copy_raw_column(df, col)

    raw_blend = (
        _clip(df["final_score"]) * 0.24
        + _clip(df["ai_score"]) * 0.14
        + _clip(df["buy_probability"]) * 0.19
        + _clip(df["smart_money_score"]) * 0.17
        + _clip(df["trade_validation_score"]) * 0.16
        + _clip(df["entry_timing_score"]) * 0.10
    )

    rank_component = _percentile_score(raw_blend)
    absolute_component = _clip(raw_blend)

    trend_component = (
        _clip(df["trend_score_v5"]) * 0.40
        + _clip(df["buy_probability"]) * 0.25
        + _clip(df["smart_money_score"]) * 0.35
    )

    liquidity_component = (
        _clip(df["liquidity_score_raw"]) * 0.45
        + _norm_0_100(df["value_traded"], neutral=50.0) * 0.40
        + _norm_0_100(df["volume_ratio_20"], neutral=50.0) * 0.15
    )

    rsi = _safe_num(df["rsi"], 50.0)

    rsi_component = pd.Series(70.0, index=df.index, dtype="float64")
    rsi_component = rsi_component.mask(rsi < 40, 40)
    rsi_component = rsi_component.mask((rsi >= 40) & (rsi < 55), 60)
    rsi_component = rsi_component.mask((rsi >= 55) & (rsi <= 72), 90)
    rsi_component = rsi_component.mask((rsi > 72) & (rsi <= 82), 70)
    rsi_component = rsi_component.mask((rsi > 82) & (rsi <= 88), 48)
    rsi_component = rsi_component.mask(rsi > 88, 35)

    volatility_penalty = pd.Series(0.0, index=df.index, dtype="float64")
    volatility_penalty += (_safe_num(df["atr_percent"], 5.0) > 7.5).astype(float) * 6
    volatility_penalty += (_safe_num(df["atr_percent"], 5.0) > 12.0).astype(float) * 10
    volatility_penalty += (_safe_num(df["change_pct"], 0.0) > 7.0).astype(float) * 6
    volatility_penalty += (_safe_num(df["change_pct"], 0.0) > 9.5).astype(float) * 10

    risk_component = _clip(df["risk_management_score"]) - volatility_penalty
    risk_component = risk_component.clip(0, 100)

    rr_component = (_safe_num(df["risk_reward_t1"], 1.0) * 58.0).clip(0, 100)

    df["institutional_v5_raw_blend"] = raw_blend.round(2)
    df["institutional_v5_rank_component"] = rank_component.round(2)
    df["institutional_v5_absolute_component"] = absolute_component.round(2)
    df["institutional_v5_trend_component"] = trend_component.round(2)
    df["institutional_v5_liquidity_component"] = liquidity_component.round(2)
    df["institutional_v5_rsi_component"] = rsi_component.round(2)
    df["institutional_v5_risk_component"] = risk_component.round(2)
    df["institutional_v5_rr_component"] = rr_component.round(2)

    return df


def _apply_unified_score(df: pd.DataFrame, market_summary: dict | None = None) -> pd.DataFrame:
    df = df.copy()
    market_summary = market_summary or {}

    market_score = _safe_num(market_summary.get("market_score", 50), 50)

    market_adjustment = 0.0
    if market_score >= 75:
        market_adjustment = 2.0
    elif market_score >= 65:
        market_adjustment = 1.5
    elif market_score < 45:
        market_adjustment = -4.0
    elif market_score < 55:
        market_adjustment = -2.0

    score = (
        df["institutional_v5_absolute_component"] * 0.30
        + df["institutional_v5_rank_component"] * 0.20
        + df["institutional_v5_trend_component"] * 0.14
        + df["institutional_v5_liquidity_component"] * 0.10
        + df["institutional_v5_rsi_component"] * 0.07
        + df["institutional_v5_risk_component"] * 0.12
        + df["institutional_v5_rr_component"] * 0.07
        + market_adjustment
    )

    risk_text = (
        df.get("risk_permission", "").astype(str).str.upper()
        + " "
        + df.get("risk_status", "").astype(str).str.upper()
        + " "
        + df.get("risk_action", "").astype(str).str.upper()
    )

    entry_action = df.get("entry_timing_action", "").astype(str).str.upper()
    trade_status = df.get("trade_validation_status", "").astype(str).str.upper()
    trade_action = df.get("trade_action", "").astype(str).str.upper()

    hard_no_trade_mask = risk_text.apply(lambda x: _text_contains_any(x, NO_TRADE_WORDS))
    high_risk_mask = risk_text.str.contains("HIGH RISK", regex=False, na=False)
    weak_trade_mask = trade_status.str.contains("REJECTED|WEAK", regex=True, na=False) | trade_action.str.contains("AVOID", na=False)
    wait_mask = entry_action.str.contains("WAIT|DIP|PULLBACK", regex=True, na=False)

    score = score - hard_no_trade_mask.astype(float) * 8
    score = score - high_risk_mask.astype(float) * 4
    score = score - weak_trade_mask.astype(float) * 8
    score = score - wait_mask.astype(float) * 2
    score = score - df["institutional_v5_security_block"].astype(float) * 35

    df["institutional_v5_hard_no_trade"] = hard_no_trade_mask
    df["institutional_v5_high_risk_flag"] = high_risk_mask
    df["institutional_v5_wait_flag"] = wait_mask

    df["institutional_v5_score"] = score.clip(0, 100).round(2)

    probability = (
        df["institutional_v5_score"] * 0.70
        + df["institutional_v5_rank_component"] * 0.18
        + df["institutional_v5_risk_component"] * 0.12
    )

    probability = probability - hard_no_trade_mask.astype(float) * 7
    probability = probability - high_risk_mask.astype(float) * 4
    probability = probability - df["institutional_v5_security_block"].astype(float) * 35

    df["institutional_v5_win_probability"] = probability.clip(1, 99).round(2)
    df["institutional_v5_loss_probability"] = (100 - df["institutional_v5_win_probability"]).round(2)

    confidence = (
        df["institutional_v5_score"] * 0.48
        + df["institutional_v5_liquidity_component"] * 0.18
        + df["institutional_v5_risk_component"] * 0.18
        + df["institutional_v5_rr_component"] * 0.16
    )

    df["institutional_v5_confidence"] = confidence.clip(1, 99).round(2)

    return df


def _score_to_verdict(score: float, blocked: bool, hard_no_trade: bool, wait: bool) -> str:
    if blocked:
        return "AVOID"

    if hard_no_trade and score < 78:
        return "NO TRADE"

    if score >= 88 and not wait:
        return "STRONG BUY"

    if score >= 80:
        return "BUY"

    if score >= 70:
        return "ACCUMULATE"

    if score >= 58:
        return "WATCH"

    return "AVOID"


def _public_decision(verdict: str) -> str:
    if verdict in {"ELITE BUY", "STRONG BUY", "BUY"}:
        return "BUY"

    if verdict == "ACCUMULATE":
        return "ACCUMULATE"

    if verdict == "WATCH":
        return "WATCH"

    if verdict == "NO TRADE":
        return "NO TRADE"

    return "AVOID"


def _confidence_label(conf: float) -> str:
    if conf >= 92:
        return "ELITE"
    if conf >= 86:
        return "VERY HIGH"
    if conf >= 78:
        return "HIGH"
    if conf >= 65:
        return "MEDIUM"
    return "LOW"


def _risk_grade(row: pd.Series) -> str:
    score = _safe_num(row.get("institutional_v5_risk_component"), 0)

    if row.get("institutional_v5_security_block", False):
        return "BLOCKED"

    risk_text = f"{row.get('risk_permission', '')} {row.get('risk_status', '')} {row.get('risk_action', '')}".upper()

    if _text_contains_any(risk_text, ["REJECTED", "AVOID", "CHASE RISK"]):
        return "AVOID"

    if _text_contains_any(risk_text, ["HIGH RISK", "NO TRADE"]):
        if score >= 45:
            return "HIGH RISK"
        return "AVOID"

    if score >= 80:
        return "A"

    if score >= 65:
        return "B"

    if score >= 50:
        return "C"

    return "HIGH RISK"


def _build_reason(row: pd.Series) -> str:
    reasons = []
    warnings = []

    if _safe_num(row.get("institutional_v5_score"), 0) >= 80:
        reasons.append("institutional score strong")

    if _safe_num(row.get("smart_money_score"), 0) >= 80:
        reasons.append("smart money strong")

    if _safe_num(row.get("accumulation_score"), 0) >= 80:
        reasons.append("accumulation strong")

    if _safe_num(row.get("trade_validation_score"), 0) >= 85:
        reasons.append("trade validation strong")

    if _safe_num(row.get("entry_timing_score"), 0) >= 85:
        reasons.append("entry timing supportive")

    if _safe_num(row.get("value_traded"), 0) >= 100_000_000:
        reasons.append("high traded value")

    if _safe_num(row.get("volume_ratio_20"), 0) >= 1.8:
        reasons.append("volume expansion")

    if row.get("institutional_v5_security_block", False):
        warnings.append(str(row.get("institutional_v5_security_block_reason", "blocked security")))

    if _safe_num(row.get("rsi"), 50) >= 82:
        warnings.append("RSI overheated")

    if _safe_num(row.get("change_pct"), 0) >= 7:
        warnings.append("large daily move; avoid chasing")

    if _safe_num(row.get("atr_percent"), 0) >= 7.5:
        warnings.append("high volatility")

    risk_text = f"{row.get('risk_permission', '')} {row.get('risk_status', '')}".upper()

    if _text_contains_any(risk_text, ["NO TRADE", "HIGH RISK", "CHASE RISK", "REJECTED"]):
        warnings.append("risk restriction; controlled position only")

    reason_text = " | ".join(reasons) if reasons else "balanced setup"
    warning_text = " | ".join([w for w in warnings if w])

    if warning_text:
        return f"{reason_text} || Warnings: {warning_text}"

    return reason_text


def _apply_unified_decision(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    hard_no_trade_mask = df.get("institutional_v5_hard_no_trade", False)
    wait_mask = df.get("institutional_v5_wait_flag", False)

    verdicts = []

    for idx, row in df.iterrows():
        hard_no_trade = bool(hard_no_trade_mask.loc[idx]) if isinstance(hard_no_trade_mask, pd.Series) else False
        wait = bool(wait_mask.loc[idx]) if isinstance(wait_mask, pd.Series) else False

        verdicts.append(
            _score_to_verdict(
                score=_safe_num(row.get("institutional_v5_score"), 0),
                blocked=bool(row.get("institutional_v5_security_block", False)),
                hard_no_trade=hard_no_trade,
                wait=wait,
            )
        )

    df["institutional_v5_verdict"] = verdicts
    df["institutional_v5_final_decision"] = df["institutional_v5_verdict"].apply(_public_decision)
    df["institutional_v5_confidence_label"] = df["institutional_v5_confidence"].apply(_confidence_label)
    df["institutional_v5_risk_grade"] = df.apply(_risk_grade, axis=1)
    df["institutional_v5_reason"] = df.apply(_build_reason, axis=1)

    df["final_score"] = df["institutional_v5_score"]
    df["ai_score"] = df["institutional_v5_score"]
    df["buy_probability"] = df["institutional_v5_win_probability"]
    df["sell_probability"] = df["institutional_v5_loss_probability"]
    df["confidence_v3"] = df["institutional_v5_confidence"]
    df["confidence"] = df["institutional_v5_confidence"]
    df["confidence_label"] = df["institutional_v5_confidence_label"]
    df["verdict"] = df["institutional_v5_verdict"]
    df["final_decision"] = df["institutional_v5_final_decision"]
    df["decision_reason"] = df["institutional_v5_reason"]
    df["model_version"] = "AI_V5.2_BALANCED_CALIBRATED"
    df["ai_engine_version"] = ENGINE_VERSION

    df["risk_level"] = df["institutional_v5_risk_grade"].replace({
        "A": "LOW",
        "B": "MEDIUM",
        "C": "MEDIUM",
        "HIGH RISK": "HIGH",
        "AVOID": "HIGH",
        "BLOCKED": "HIGH",
    })

    return df


def apply_institutional_v5_calibration(
    df: pd.DataFrame,
    market_summary: dict | None = None,
    remove_blocked_from_final: bool = False,
) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()

    if df.empty:
        out = df.copy()
        out["ai_engine_version"] = ENGINE_VERSION
        return out

    out = df.copy()
    out = out.loc[:, ~out.columns.duplicated()].copy()

    out = _security_firewall_flags(out)
    out = _build_component_scores(out)
    out = _apply_unified_score(out, market_summary=market_summary)
    out = _apply_unified_decision(out)

    if remove_blocked_from_final:
        out = out[~out["institutional_v5_security_block"]].copy()

    out = out.sort_values(
        by=["institutional_v5_score", "institutional_v5_win_probability", "value_traded"],
        ascending=[False, False, False],
    ).reset_index(drop=True)

    return out