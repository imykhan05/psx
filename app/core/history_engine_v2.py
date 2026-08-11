from pathlib import Path

import pandas as pd


HISTORY_EXPORT_FILE = Path("database/psx_history_clean.csv")


def prepare_history_v2(history: pd.DataFrame) -> pd.DataFrame:
    """
    Historical Data Engine V2

    Cleans and prepares PSX history for AI engines.
    """

    df = history.copy()

    if df.empty:
        return df

    df = normalize_history_columns(df)
    df = clean_numeric_columns(df)
    df = remove_duplicate_symbol_dates(df)
    df = add_history_quality_columns(df)
    df = sort_history(df)
    export_clean_history(df)

    return df


def parse_psx_dates(series) -> pd.Series:
    """
    Fast PSX date parser.

    Supported formats:
    - 30JUN2026
    - 2026-07-08
    - 08-JUL-2026
    - 08/07/2026
    """

    s = series.astype(str).str.strip().str.upper()

    parsed = pd.to_datetime(
        s,
        format="%d%b%Y",
        errors="coerce",
    )

    mask = parsed.isna()
    if mask.any():
        parsed.loc[mask] = pd.to_datetime(
            s.loc[mask],
            format="%Y-%m-%d",
            errors="coerce",
        )

    mask = parsed.isna()
    if mask.any():
        parsed.loc[mask] = pd.to_datetime(
            s.loc[mask],
            format="%d-%b-%Y",
            errors="coerce",
        )

    mask = parsed.isna()
    if mask.any():
        parsed.loc[mask] = pd.to_datetime(
            s.loc[mask],
            format="%d/%m/%Y",
            errors="coerce",
        )

    mask = parsed.isna()
    if mask.any():
        parsed.loc[mask] = pd.to_datetime(
            s.loc[mask],
            format="%m/%d/%Y",
            errors="coerce",
        )

    return parsed


def normalize_history_columns(df: pd.DataFrame) -> pd.DataFrame:
    if "symbol" not in df.columns:
        raise ValueError("History data missing required column: symbol")

    if "date" not in df.columns:
        raise ValueError("History data missing required column: date")

    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
    df["date"] = df["date"].astype(str).str.strip().str.upper()

    if "date_parsed" not in df.columns:
        df["date_parsed"] = parse_psx_dates(df["date"])
    else:
        df["date_parsed"] = parse_psx_dates(df["date_parsed"])

    if df["date_parsed"].isna().any():
        df["date_parsed"] = df["date_parsed"].fillna(
            parse_psx_dates(df["date"])
        )

    bad_dates = df["date_parsed"].isna().sum()

    if bad_dates > 0:
        print(f"Warning: {bad_dates} rows have invalid dates and will be removed.")
        df = df.dropna(subset=["date_parsed"]).copy()

    return df


def clean_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "change",
        "change_pct",
        "volume",
    ]

    for col in numeric_columns:
        if col not in df.columns:
            df[col] = 0

        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df


def remove_duplicate_symbol_dates(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)

    df = df.sort_values(["symbol", "date_parsed"])
    df = df.drop_duplicates(
        subset=["symbol", "date_parsed"],
        keep="last",
    )

    after = len(df)
    df.attrs["duplicates_removed"] = before - after

    return df


def add_history_quality_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["symbol", "date_parsed"]).copy()

    df["history_days_available"] = df.groupby("symbol")["date_parsed"].transform("count")
    df["history_row_number"] = df.groupby("symbol").cumcount() + 1

    df["history_quality"] = "POOR"
    df.loc[df["history_days_available"] >= 20, "history_quality"] = "SHORT"
    df.loc[df["history_days_available"] >= 50, "history_quality"] = "MEDIUM"
    df.loc[df["history_days_available"] >= 100, "history_quality"] = "GOOD"
    df.loc[df["history_days_available"] >= 250, "history_quality"] = "EXCELLENT"

    return df


def sort_history(df: pd.DataFrame) -> pd.DataFrame:
    return df.sort_values(["symbol", "date_parsed"]).reset_index(drop=True)


def export_clean_history(df: pd.DataFrame) -> None:
    HISTORY_EXPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(HISTORY_EXPORT_FILE, index=False)


def history_v2_summary(history: pd.DataFrame) -> dict:
    if history is None or history.empty:
        return {
            "status": "empty",
            "records": 0,
            "symbols": 0,
            "days": 0,
            "file": str(HISTORY_EXPORT_FILE),
        }

    symbols = history["symbol"].nunique() if "symbol" in history.columns else 0
    days = history["date_parsed"].nunique() if "date_parsed" in history.columns else 0

    avg_days_per_symbol = 0
    min_days_per_symbol = 0
    max_days_per_symbol = 0

    if "history_days_available" in history.columns and not history.empty:
        per_symbol = history.groupby("symbol")["date_parsed"].nunique()
        avg_days_per_symbol = round(per_symbol.mean(), 2)
        min_days_per_symbol = int(per_symbol.min())
        max_days_per_symbol = int(per_symbol.max())

    quality_counts = {}

    if "history_quality" in history.columns:
        quality_counts = history.drop_duplicates("symbol")["history_quality"].value_counts().to_dict()

    return {
        "status": "ready",
        "records": len(history),
        "symbols": symbols,
        "days": days,
        "avg_days_per_symbol": avg_days_per_symbol,
        "min_days_per_symbol": min_days_per_symbol,
        "max_days_per_symbol": max_days_per_symbol,
        "quality_counts": quality_counts,
        "duplicates_removed": history.attrs.get("duplicates_removed", 0),
        "file": str(HISTORY_EXPORT_FILE),
    }