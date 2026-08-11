import pandas as pd

from config import DATABASE_DIR, HISTORY_CSV


def update_database(today_df: pd.DataFrame) -> pd.DataFrame:
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    if HISTORY_CSV.exists():
        old = pd.read_csv(HISTORY_CSV)
        old["date_parsed"] = pd.to_datetime(old["date_parsed"], errors="coerce")
        combined = pd.concat([old, today_df], ignore_index=True)
    else:
        combined = today_df.copy()

    combined = combined.drop_duplicates(subset=["date", "symbol"], keep="last")
    combined = combined.sort_values(["symbol", "date_parsed"])

    combined.to_csv(HISTORY_CSV, index=False)

    return combined


def load_history() -> pd.DataFrame:
    if not HISTORY_CSV.exists():
        return pd.DataFrame()

    history = pd.read_csv(HISTORY_CSV)
    history["date_parsed"] = pd.to_datetime(history["date_parsed"], errors="coerce")
    return history