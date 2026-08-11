import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = BASE_DIR / "config_files"
RISK_RULES_PATH = CONFIG_DIR / "risk_rules.json"


def load_risk_rules() -> dict:
    """
    Load complete risk_rules.json
    """
    if not RISK_RULES_PATH.exists():
        raise FileNotFoundError(f"Risk rules not found: {RISK_RULES_PATH}")

    with open(RISK_RULES_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def get_risk_value(path: str, default=None):
    """
    Example:
    get_risk_value("trade_risk.minimum_reward_risk")
    """
    rules = load_risk_rules()

    value = rules

    for key in path.split("."):
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value


# -------------------------------------------------------
# Global Risk
# -------------------------------------------------------

def max_portfolio_risk():
    return float(get_risk_value("global_risk.max_portfolio_risk_percent", 6))


def max_single_trade_risk():
    return float(get_risk_value("global_risk.max_single_trade_risk_percent", 2))


def max_daily_loss():
    return float(get_risk_value("global_risk.max_daily_loss_percent", 3))


def max_weekly_loss():
    return float(get_risk_value("global_risk.max_weekly_loss_percent", 7))


def max_monthly_loss():
    return float(get_risk_value("global_risk.max_monthly_loss_percent", 15))


# -------------------------------------------------------
# Trade Risk
# -------------------------------------------------------

def minimum_reward_risk():
    return float(get_risk_value("trade_risk.minimum_reward_risk", 1.5))


def ideal_reward_risk():
    return float(get_risk_value("trade_risk.ideal_reward_risk", 2.0))


def default_stop_loss():
    return float(get_risk_value("trade_risk.default_stop_loss_percent", 5))


def maximum_stop_loss():
    return float(get_risk_value("trade_risk.maximum_stop_loss_percent", 6))


# -------------------------------------------------------
# Liquidity
# -------------------------------------------------------

def minimum_volume():
    return int(get_risk_value("liquidity_risk.minimum_volume", 100000))


def preferred_volume():
    return int(get_risk_value("liquidity_risk.preferred_volume", 500000))


def high_liquidity_volume():
    return int(get_risk_value("liquidity_risk.high_liquidity_volume", 1000000))


# -------------------------------------------------------
# Price
# -------------------------------------------------------

def minimum_price():
    return float(get_risk_value("price_risk.minimum_price", 5))


def maximum_price():
    return float(get_risk_value("price_risk.maximum_price_short_term", 300))


# -------------------------------------------------------
# Market
# -------------------------------------------------------

def bullish_market():
    return int(get_risk_value("market_risk.bullish_min_score", 70))


def bearish_market():
    return int(get_risk_value("market_risk.bearish_below_score", 40))


# -------------------------------------------------------
# Sector
# -------------------------------------------------------

def minimum_sector_score():
    return int(get_risk_value("sector_risk.minimum_sector_score_for_buy", 65))


def maximum_sector_exposure():
    return int(get_risk_value("sector_risk.max_sector_exposure_percent", 35))


# -------------------------------------------------------
# Decision Blocks
# -------------------------------------------------------

def block_buy_market_score():
    return int(get_risk_value("decision_blocks.block_buy_if_market_score_below", 40))


def block_buy_sector_score():
    return int(get_risk_value("decision_blocks.block_buy_if_sector_score_below", 50))


def block_buy_confidence():
    return int(get_risk_value("decision_blocks.block_buy_if_confidence_below", 55))


def block_buy_reward_risk():
    return float(get_risk_value("decision_blocks.block_buy_if_reward_risk_below", 1.2))


def block_buy_volume():
    return int(get_risk_value("decision_blocks.block_buy_if_volume_below", 100000))


# -------------------------------------------------------
# Risk Labels
# -------------------------------------------------------

def low_risk_limit():
    return int(get_risk_value("risk_labels.low_risk_max_penalty", 5))


def medium_risk_limit():
    return int(get_risk_value("risk_labels.medium_risk_max_penalty", 15))


def high_risk_limit():
    return int(get_risk_value("risk_labels.high_risk_min_penalty", 16))