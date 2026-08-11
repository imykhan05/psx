import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = BASE_DIR / "config_files"
LONG_TERM_RULES_PATH = CONFIG_DIR / "long_term_rules.json"


def load_long_term_rules() -> dict:
    """
    Load complete long_term_rules.json
    """
    if not LONG_TERM_RULES_PATH.exists():
        raise FileNotFoundError(
            f"Long-Term rules file not found: {LONG_TERM_RULES_PATH}"
        )

    with open(LONG_TERM_RULES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_long_term_value(path: str, default=None):
    """
    Example:

    get_long_term_value(
        "fundamental_rules.roe_good"
    )
    """

    rules = load_long_term_rules()

    value = rules

    for key in path.split("."):

        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value


# --------------------------------------------------------
# Score Weights
# --------------------------------------------------------

def score_weights():
    return load_long_term_rules().get("score_weights", {})


# --------------------------------------------------------
# Minimum Requirements
# --------------------------------------------------------

def minimum_long_term_score():
    return int(
        get_long_term_value(
            "minimum_requirements.minimum_long_term_score",
            70
        )
    )


def minimum_confidence():
    return int(
        get_long_term_value(
            "minimum_requirements.minimum_confidence",
            60
        )
    )


def minimum_average_volume():
    return int(
        get_long_term_value(
            "minimum_requirements.minimum_average_volume",
            100000
        )
    )


# --------------------------------------------------------
# Fundamental
# --------------------------------------------------------

def fundamental_rules():
    return load_long_term_rules().get(
        "fundamental_rules",
        {}
    )


# --------------------------------------------------------
# Growth
# --------------------------------------------------------

def growth_rules():
    return load_long_term_rules().get(
        "growth_rules",
        {}
    )


# --------------------------------------------------------
# Dividend
# --------------------------------------------------------

def dividend_rules():
    return load_long_term_rules().get(
        "dividend_rules",
        {}
    )


# --------------------------------------------------------
# Valuation
# --------------------------------------------------------

def valuation_rules():
    return load_long_term_rules().get(
        "valuation_rules",
        {}
    )


# --------------------------------------------------------
# Quality
# --------------------------------------------------------

def quality_rules():
    return load_long_term_rules().get(
        "quality_rules",
        {}
    )


# --------------------------------------------------------
# Verdict
# --------------------------------------------------------

def verdict_rules():
    return load_long_term_rules().get(
        "verdicts",
        {}
    )


# --------------------------------------------------------
# Allocation
# --------------------------------------------------------

def allocation_rules():
    return load_long_term_rules().get(
        "allocation",
        {}
    )


# --------------------------------------------------------
# Holding Period
# --------------------------------------------------------

def holding_period():
    return load_long_term_rules().get(
        "holding_period",
        {}
    )


# --------------------------------------------------------
# Risk Filters
# --------------------------------------------------------

def risk_filters():
    return load_long_term_rules().get(
        "risk_filters",
        {}
    )