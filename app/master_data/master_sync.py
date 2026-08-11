from pathlib import Path
import pandas as pd


MASTER_PATH = Path("database/master/company_master.csv")
DIRECTORY_PATH = Path("database/company_directory/companies.csv")
PSX_INTELLIGENCE_PATH = Path("database/psx_intelligence/psx_companies.csv")


def clean(value, default="UNKNOWN"):
    if pd.isna(value):
        return default
    value = str(value).strip()
    if value.upper() in ["", "NAN", "NONE"]:
        return default
    return value.upper()


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path)


def save_csv(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def prepare_master() -> pd.DataFrame:
    master = load_csv(MASTER_PATH)
    master = master[["symbol", "company", "sector", "industry"]].copy()

    master["symbol"] = master["symbol"].astype(str).str.upper().str.strip()
    master["company"] = master["company"].astype(str).str.strip()
    master["sector"] = master["sector"].apply(clean)
    master["industry"] = master["industry"].apply(clean)

    master = master.drop_duplicates(subset=["symbol"], keep="last")
    return master


def overwrite_metadata(target_path: Path, extra_cols: dict) -> dict:
    master = prepare_master()
    current = load_csv(target_path)

    if current.empty:
        current = master.copy()
    else:
        current["symbol"] = current["symbol"].astype(str).str.upper().str.strip()

        current = current.drop(
            columns=[c for c in ["company", "sector", "industry"] if c in current.columns],
            errors="ignore",
        )

        current = current.merge(master, on="symbol", how="left")

        for col in ["company", "sector", "industry"]:
            current[col] = current[col].fillna("UNKNOWN")

    for col, default in extra_cols.items():
        if col not in current.columns:
            current[col] = default
        else:
            current[col] = current[col].fillna(default)

    current["sector"] = current["sector"].apply(clean)
    current["industry"] = current["industry"].apply(clean)

    current = current.drop_duplicates(subset=["symbol"], keep="last")
    current = current.sort_values("symbol").reset_index(drop=True)

    save_csv(current, target_path)

    unknown = (current["sector"].astype(str).str.upper() == "UNKNOWN").sum()

    return {
        "status": "synced_v2",
        "file": str(target_path),
        "records": int(len(current)),
        "unknown_sector": int(unknown),
    }


def sync_master_to_company_directory() -> dict:
    return overwrite_metadata(
        DIRECTORY_PATH,
        {
            "market": "REGULAR",
            "status": "ACTIVE",
            "listing_date": None,
            "listing_year": None,
            "website": None,
            "remarks": None,
        },
    )


def sync_master_to_psx_intelligence() -> dict:
    return overwrite_metadata(
        PSX_INTELLIGENCE_PATH,
        {
            "market": "REGULAR",
            "status": "ACTIVE",
            "listing_date": None,
            "listing_year": None,
            "website": None,
            "source": "MASTER_SYNC_V2",
            "remarks": None,
        },
    )


def sync_master_everywhere() -> dict:
    return {
        "company_directory": sync_master_to_company_directory(),
        "psx_intelligence": sync_master_to_psx_intelligence(),
    }