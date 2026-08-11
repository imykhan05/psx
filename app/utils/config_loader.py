import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = BASE_DIR / "config_files"


def load_json_config(filename: str) -> dict:
    path = CONFIG_DIR / filename

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def load_settings() -> dict:
    return load_json_config("settings.json")


def get_setting(path: str, default=None):
    settings = load_settings()

    keys = path.split(".")
    value = settings

    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value


def app_name() -> str:
    return get_setting("application.name", "PSX AI Terminal")


def app_version() -> str:
    return get_setting("application.version", "0.1.0")


def default_capital() -> int:
    return int(get_setting("application.default_capital", 50000))


def default_max_price() -> float:
    return float(get_setting("application.default_max_price", 300))


def scanner_max_price() -> float:
    return float(get_setting("scanner.maximum_price", 300))


def risk_stop_loss_percent() -> float:
    return float(get_setting("risk.default_stop_loss_percent", 5))


def risk_target1_percent() -> float:
    return float(get_setting("risk.default_target1_percent", 8))


def risk_target2_percent() -> float:
    return float(get_setting("risk.default_target2_percent", 15))


def minimum_reward_risk() -> float:
    return float(get_setting("risk.minimum_reward_risk", 1.5))