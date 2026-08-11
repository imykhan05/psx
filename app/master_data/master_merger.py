from pathlib import Path
import pandas as pd


MASTER_PATH = Path("database/master/company_master.csv")


def is_bad(value) -> bool:
    if pd.isna(value):
        return True
    value = str(value).strip().upper()
    return value in ["", "UNKNOWN", "NAN", "NONE"]


def load_master_metadata() -> pd.DataFrame:
    if not MASTER_PATH.exists() or MASTER_PATH.stat().st_size == 0:
        return pd.DataFrame(columns=["symbol", "company", "sector", "industry"])

    master = pd.read_csv(MASTER_PATH)

    keep_cols = ["symbol", "company", "sector", "industry"]
    available = [c for c in keep_cols if c in master.columns]

    master = master[available].copy()

    for col in keep_cols:
        if col not in master.columns:
            master[col] = None

    master["symbol"] = master["symbol"].astype(str).str.upper().str.strip()

    master = master.drop_duplicates(subset=["symbol"], keep="last")

    return master[keep_cols]


def merge_master_metadata(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    master = load_master_metadata()

    if result.empty or master.empty or "symbol" not in result.columns:
        return result

    result["symbol"] = result["symbol"].astype(str).str.upper().str.strip()

    merged = result.merge(
        master,
        on="symbol",
        how="left",
        suffixes=("", "_master"),
    )

    for col in ["company", "sector", "industry"]:
        master_col = f"{col}_master"

        if master_col in merged.columns:
            if col in merged.columns:
                merged[col] = merged.apply(
                    lambda row: row[master_col]
                    if is_bad(row[col]) and not is_bad(row[master_col])
                    else row[col],
                    axis=1,
                )
            else:
                merged[col] = merged[master_col]

            merged = merged.drop(columns=[master_col])

    return merged