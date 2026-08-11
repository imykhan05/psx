MASTER_COLUMNS = [
    # Basic Identity
    "symbol",
    "company",
    "sector",
    "industry",
    "exchange",
    "status",

    # Market Data
    "last_price",
    "market_cap",
    "shares_outstanding",
    "free_float",
    "avg_volume_30d",
    "avg_volume_90d",

    # Technical Metrics
    "change_pct",
    "volume",
    "ema20",
    "ema50",
    "ema100",
    "ema200",
    "rsi14",
    "macd",
    "macd_hist",
    "atr14",
    "close_position",
    "volatility_20d",
    "beta",

    # Short-Term AI
    "base_ai_score",
    "adaptive_ai_score",
    "confidence",
    "confidence_v2",
    "probability_confidence",
    "market_strength_score",
    "sector_strength_score",
    "sector_rank",
    "short_term_verdict",
    "final_decision",
    "risk_level",

    # Trade Plan
    "entry_low",
    "entry_high",
    "stop_loss",
    "target_1",
    "target_2",
    "holding_days",
    "reward_risk_ratio",

    # Fundamentals
    "eps",
    "book_value",
    "pe",
    "pb",
    "roe",
    "roa",
    "debt_equity",
    "current_ratio",
    "net_margin",
    "fair_value",
    "margin_of_safety",

    # Growth
    "revenue_growth",
    "profit_growth",
    "eps_growth",

    # Dividend
    "dividend_yield",
    "dividend_years",
    "payout_ratio",

    # Long-Term AI
    "fundamental_score",
    "growth_score",
    "valuation_score",
    "dividend_score",
    "quality_score",
    "long_term_score",
    "long_term_confidence",
    "long_term_verdict",
    "upside_pct",

    # Explainability
    "reasons",
    "risks",
    "decision_reason",
    "long_term_reason",
    "long_term_risk",

    # Meta
    "date",
    "date_parsed",
    "updated_at",
]


REQUIRED_COLUMNS = [
    "symbol",
    "company",
    "sector",
    "last_price",
    "volume",
    "base_ai_score",
    "adaptive_ai_score",
    "final_decision",
    "risk_level",
    "date",
]


def get_master_columns():
    return MASTER_COLUMNS


def get_required_columns():
    return REQUIRED_COLUMNS


def empty_master_row():
    return {col: None for col in MASTER_COLUMNS}