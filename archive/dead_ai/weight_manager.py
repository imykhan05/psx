import json
from pathlib import Path
from datetime import datetime
from copy import deepcopy


BASE_DIR = Path(__file__).resolve().parents[2]
WEIGHTS_PATH = BASE_DIR / "config_files" / "adaptive_weights.json"
HISTORY_DIR = BASE_DIR / "database" / "ai_learning"


FEATURE_MAP = {
    "macd_bullish": "macd_bullish",
    "is_volume_spike": "volume_spike",
    "is_close_strong": "close_strong",
    "is_close_near_high": "close_near_high",
    "is_healthy_gain": "healthy_gain",
    "is_liquid": "liquid",
    "is_highly_liquid": "highly_liquid",
    "is_3d_momentum": "healthy_gain",
    "is_5d_momentum": "healthy_gain"
}


def load_weights() -> dict:
    if not WEIGHTS_PATH.exists():
        raise FileNotFoundError(f"Adaptive weights file not found: {WEIGHTS_PATH}")

    with open(WEIGHTS_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def save_weights(data: dict) -> None:
    WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(WEIGHTS_PATH, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def backup_weights(data: dict) -> Path:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = HISTORY_DIR / f"adaptive_weights_backup_{timestamp}.json"

    with open(backup_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)

    return backup_path


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


def parse_change(change) -> int:
    if change is None:
        return 0

    if isinstance(change, int):
        return change

    text = str(change).strip()

    if text in ["", "0"]:
        return 0

    try:
        return int(text.replace("+", ""))
    except ValueError:
        return 0


def apply_weight_changes(weight_changes: dict) -> dict:
    """
    Example input:
    {
        "is_close_near_high": "+4",
        "macd_bullish": "+2",
        "is_volume_spike": "0"
    }
    """

    current = load_weights()
    updated = deepcopy(current)

    backup_path = backup_weights(current)

    max_update = int(updated.get("maximum_single_update", 4))
    weights = updated.get("weights", {})

    applied_changes = {}

    for feature, raw_change in weight_changes.items():
        mapped_feature = FEATURE_MAP.get(feature, feature)

        if mapped_feature not in weights:
            applied_changes[feature] = {
                "mapped_to": mapped_feature,
                "status": "SKIPPED",
                "reason": "Feature not found in adaptive_weights.json"
            }
            continue

        change = parse_change(raw_change)

        if change > max_update:
            change = max_update

        if change < -max_update:
            change = -max_update

        item = weights[mapped_feature]

        old_weight = int(item.get("weight", 0))
        minimum = int(item.get("minimum", 0))
        maximum = int(item.get("maximum", 100))

        new_weight = clamp(
            old_weight + change,
            minimum,
            maximum
        )

        item["weight"] = new_weight

        applied_changes[feature] = {
            "mapped_to": mapped_feature,
            "status": "UPDATED",
            "old_weight": old_weight,
            "change": change,
            "new_weight": new_weight
        }

    updated["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    save_weights(updated)

    return {
        "weights_file": str(WEIGHTS_PATH),
        "backup_file": str(backup_path),
        "applied_changes": applied_changes
    }


def get_weight(feature_name: str, default: int = 0) -> int:
    data = load_weights()
    weights = data.get("weights", {})

    feature = FEATURE_MAP.get(feature_name, feature_name)

    if feature not in weights:
        return default

    return int(weights[feature].get("weight", default))


def get_all_weights() -> dict:
    data = load_weights()
    return {
        key: value.get("weight")
        for key, value in data.get("weights", {}).items()
    }