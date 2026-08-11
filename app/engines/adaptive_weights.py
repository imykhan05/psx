def get_adaptive_weights(history_days: int) -> dict:
    if history_days < 14:
        return {
            "trend": 5,
            "momentum": 25,
            "volume": 30,
            "price_action": 25,
            "historical": 15,
        }

    if history_days < 20:
        return {
            "trend": 10,
            "momentum": 25,
            "volume": 25,
            "price_action": 25,
            "historical": 15,
        }

    if history_days < 50:
        return {
            "trend": 18,
            "momentum": 22,
            "volume": 25,
            "price_action": 20,
            "historical": 15,
        }

    return {
        "trend": 25,
        "momentum": 20,
        "volume": 20,
        "price_action": 15,
        "historical": 10,
    }