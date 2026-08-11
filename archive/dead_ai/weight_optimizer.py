def suggest_weight_changes(rule_analysis: dict) -> dict:
    changes = {}

    for feature in rule_analysis.get("strong_features", []):
        changes[feature] = "+4"

    for feature in rule_analysis.get("increase_features", []):
        changes[feature] = "+2"

    for feature in rule_analysis.get("weak_features", []):
        changes[feature] = "-3"

    for feature in rule_analysis.get("neutral_features", []):
        changes[feature] = "0"

    return changes