import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = BASE_DIR / "config_files"
STRATEGY_RULES_PATH = CONFIG_DIR / "strategy_rules.json"


def load_strategy_rules() -> dict:
    if not STRATEGY_RULES_PATH.exists():
        raise FileNotFoundError(f"Strategy rules not found: {STRATEGY_RULES_PATH}")

    with open(STRATEGY_RULES_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def get_strategy_value(path: str, default=None):
    rules = load_strategy_rules()
    keys = path.split(".")
    value = rules

    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value


def short_term_rules() -> dict:
    return load_strategy_rules().get("short_term", {})


def long_term_rules() -> dict:
    return load_strategy_rules().get("long_term", {})


def decision_rules() -> dict:
    return load_strategy_rules().get("decision", {})


def portfolio_rules() -> dict:
    return load_strategy_rules().get("portfolio", {})


def market_weights() -> dict:
    return load_strategy_rules().get("market", {})


def adaptive_ai_rules() -> dict:
    return load_strategy_rules().get("adaptive_ai", {})


def short_term_minimum_ai_score() -> int:
    return int(get_strategy_value("short_term.minimum_ai_score", 60))


def buy_score() -> int:
    return int(get_strategy_value("short_term.buy_score", 80))


def strong_buy_score() -> int:
    return int(get_strategy_value("short_term.strong_buy_score", 90))


def watch_score() -> int:
    return int(get_strategy_value("short_term.watch_score", 65))


def avoid_score() -> int:
    return int(get_strategy_value("short_term.avoid_score", 45))


def minimum_confidence() -> int:
    return int(get_strategy_value("short_term.minimum_confidence", 60))


def minimum_reward_risk() -> float:
    return float(get_strategy_value("short_term.minimum_reward_risk", 1.5))


def max_positions() -> int:
    return int(get_strategy_value("portfolio.maximum_positions", 3))


def portfolio_allocation() -> list:
    return get_strategy_value("portfolio.allocation", [45, 35, 20])