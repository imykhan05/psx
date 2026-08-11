import pandas as pd


DEBUG_COLUMNS = [
    "symbol",
    "company",
    "date",
    "close",
    "change_pct",
    "volume",
    "history_days",
    "return_1d",
    "return_3d",
    "return_5d",
    "return_10d",
    "rsi",
    "macd",
    "macd_signal",
    "macd_hist",
    "atr",
    "atr_percent",
    "adx",
    "volume_ratio_5",
    "volume_ratio_20",
    "value_traded",
    "liquidity_score_raw",
    "close_position",
    "position_52w",
    "ema_20",
    "ema_50",
    "ema_100",
    "ema_200",
    "sma_20",
    "sma_50",
    "trend_strength",
    "momentum_strength",
    "volume_strength",
    "trend_score_v4",
    "trend_score_v5",
    "trend_label_v5",
    "confidence",
    "confidence_v3",
    "buy_probability",
    "sell_probability",
    "ai_score",
    "final_score",
    "final_decision",
]


def debug_feature_snapshot(df: pd.DataFrame, title: str = "FEATURE DEBUG SNAPSHOT", rows: int = 20):
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)

    if df is None or df.empty:
        print("No records found.")
        print("=" * 100)
        print()
        return

    available = [col for col in DEBUG_COLUMNS if col in df.columns]
    missing = [col for col in DEBUG_COLUMNS if col not in df.columns]

    print("Available debug columns:", len(available))
    print("Missing debug columns:", len(missing))

    if missing:
        print("Missing:")
        print(", ".join(missing))

    print("-" * 100)

    view = df[available].head(rows).copy()

    with pd.option_context(
        "display.max_columns",
        None,
        "display.width",
        240,
        "display.max_colwidth",
        40,
    ):
        print(view.to_string(index=False))

    print("=" * 100)
    print()


def debug_feature_quality(df: pd.DataFrame, title: str = "FEATURE QUALITY SUMMARY"):
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)

    if df is None or df.empty:
        print("No records found.")
        print("=" * 100)
        print()
        return

    checks = [
        "history_days",
        "return_1d",
        "return_3d",
        "return_5d",
        "return_10d",
        "rsi",
        "macd",
        "macd_signal",
        "macd_hist",
        "atr",
        "atr_percent",
        "adx",
        "volume_ratio_5",
        "volume_ratio_20",
        "value_traded",
        "liquidity_score_raw",
        "close_position",
        "position_52w",
        "ema_20",
        "ema_50",
        "ema_100",
        "ema_200",
        "sma_20",
        "sma_50",
        "trend_strength",
        "momentum_strength",
        "volume_strength",
        "trend_score_v4",
        "trend_score_v5",
        "confidence_v3",
        "buy_probability",
        "ai_score",
        "final_score",
    ]

    rows = []

    for col in checks:
        if col not in df.columns:
            rows.append({
                "feature": col,
                "status": "MISSING",
                "non_null_pct": 0,
                "zero_pct": 0,
                "min": None,
                "mean": None,
                "max": None,
                "unique": 0,
            })
            continue

        s = pd.to_numeric(df[col], errors="coerce")

        non_null_pct = round((s.notna().sum() / len(df)) * 100, 2)
        zero_pct = round(((s == 0).sum() / len(df)) * 100, 2)

        rows.append({
            "feature": col,
            "status": "OK" if non_null_pct > 0 else "EMPTY",
            "non_null_pct": non_null_pct,
            "zero_pct": zero_pct,
            "min": round(s.min(), 4) if s.notna().any() else None,
            "mean": round(s.mean(), 4) if s.notna().any() else None,
            "max": round(s.max(), 4) if s.notna().any() else None,
            "unique": s.nunique(dropna=True),
        })

    summary = pd.DataFrame(rows)

    with pd.option_context(
        "display.max_rows",
        None,
        "display.max_columns",
        None,
        "display.width",
        240,
    ):
        print(summary.to_string(index=False))

    print("=" * 100)
    print()


def debug_top_symbols(df: pd.DataFrame, symbols=None, title: str = "SYMBOL DEBUG"):
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)

    if df is None or df.empty:
        print("No records found.")
        print("=" * 100)
        print()
        return

    if symbols is None:
        symbols = ["TPLP", "PIBTL", "TPLRF1", "SGPL", "DFSM"]

    if "symbol" not in df.columns:
        print("symbol column missing.")
        print("=" * 100)
        print()
        return

    subset = df[df["symbol"].astype(str).isin(symbols)].copy()

    if subset.empty:
        print("No selected symbols found:", symbols)
        print("=" * 100)
        print()
        return

    available = [col for col in DEBUG_COLUMNS if col in subset.columns]

    with pd.option_context(
        "display.max_columns",
        None,
        "display.width",
        240,
        "display.max_colwidth",
        50,
    ):
        print(subset[available].to_string(index=False))

    print("=" * 100)
    print()