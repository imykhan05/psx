from pathlib import Path
import pandas as pd

from app.psx_intelligence.psx_company_schema import (
    PSX_COMPANY_COLUMNS,
    SECTOR_DICTIONARY_COLUMNS,
)


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "database" / "psx_intelligence"

PSX_COMPANIES_PATH = DATA_DIR / "psx_companies.csv"
SECTOR_DICTIONARY_PATH = DATA_DIR / "sector_dictionary.csv"


def load_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=columns)

    try:
        df = pd.read_csv(path, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=columns)

    df.columns = df.columns.astype(str).str.strip().str.lower()

    for col in columns:
        if col not in df.columns:
            df[col] = None

    return df[columns].copy()


def save_csv(df: pd.DataFrame, path: Path, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    result = df.copy()

    for col in columns:
        if col not in result.columns:
            result[col] = None

    result = result[columns]
    result.to_csv(path, index=False, encoding="utf-8")


def normalize_companies(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    for col in PSX_COMPANY_COLUMNS:
        if col not in result.columns:
            result[col] = None

    result = result[PSX_COMPANY_COLUMNS]

    result["symbol"] = result["symbol"].astype(str).str.upper().str.strip()
    result["company"] = result["company"].astype(str).str.strip()
    result["sector"] = result["sector"].fillna("UNKNOWN").astype(str).str.upper().str.strip()
    result["industry"] = result["industry"].fillna("UNKNOWN").astype(str).str.upper().str.strip()
    result["market"] = result["market"].fillna("REGULAR").astype(str).str.upper().str.strip()
    result["status"] = result["status"].fillna("ACTIVE").astype(str).str.upper().str.strip()

    result.loc[result["sector"].isin(["", "NAN", "NONE"]), "sector"] = "UNKNOWN"
    result.loc[result["industry"].isin(["", "NAN", "NONE"]), "industry"] = "UNKNOWN"

    result = result.drop_duplicates(subset=["symbol"], keep="last")
    result = result.sort_values("symbol").reset_index(drop=True)

    return result


def load_psx_companies() -> pd.DataFrame:
    df = load_csv(PSX_COMPANIES_PATH, PSX_COMPANY_COLUMNS)
    return normalize_companies(df)


def save_psx_companies(df: pd.DataFrame) -> None:
    save_csv(normalize_companies(df), PSX_COMPANIES_PATH, PSX_COMPANY_COLUMNS)


def upsert_psx_companies(df: pd.DataFrame) -> pd.DataFrame:
    current = load_psx_companies()
    incoming = normalize_companies(df)

    combined = pd.concat([current, incoming], ignore_index=True)
    combined = normalize_companies(combined)

    save_psx_companies(combined)
    return combined


def load_sector_dictionary() -> pd.DataFrame:
    df = load_csv(SECTOR_DICTIONARY_PATH, SECTOR_DICTIONARY_COLUMNS)

    if not df.empty:
        df["sector"] = df["sector"].astype(str).str.upper().str.strip()
        df["sector_code"] = df["sector_code"].astype(str).str.upper().str.strip()

    return df


def save_sector_dictionary(df: pd.DataFrame) -> None:
    save_csv(df, SECTOR_DICTIONARY_PATH, SECTOR_DICTIONARY_COLUMNS)


def psx_company_summary() -> dict:
    companies = load_psx_companies()
    sectors = load_sector_dictionary()

    unknown_sector = (
        companies["sector"].astype(str).str.upper().str.strip().isin(["UNKNOWN", "", "NAN", "NONE"])
    ).sum() if not companies.empty else 0

    return {
        "companies": int(len(companies)),
        "known_sector": int(len(companies) - unknown_sector),
        "unknown_sector": int(unknown_sector),
        "sector_dictionary": int(len(sectors)),
        "file": str(PSX_COMPANIES_PATH),
    }