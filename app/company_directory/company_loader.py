from pathlib import Path
import pandas as pd

from app.company_directory.company_schema import (
    COMPANY_COLUMNS,
    SECTOR_COLUMNS,
    INDUSTRY_COLUMNS,
    LISTING_COLUMNS,
)


BASE_DIR = Path(__file__).resolve().parents[2]
DIRECTORY_DIR = BASE_DIR / "database" / "company_directory"

COMPANIES_PATH = DIRECTORY_DIR / "companies.csv"
SECTORS_PATH = DIRECTORY_DIR / "sectors.csv"
INDUSTRIES_PATH = DIRECTORY_DIR / "industries.csv"
LISTINGS_PATH = DIRECTORY_DIR / "listings.csv"


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
    DIRECTORY_DIR.mkdir(parents=True, exist_ok=True)

    result = df.copy()

    for col in columns:
        if col not in result.columns:
            result[col] = None

    result = result[columns]
    result.to_csv(path, index=False, encoding="utf-8")


def load_companies() -> pd.DataFrame:
    df = load_csv(COMPANIES_PATH, COMPANY_COLUMNS)

    if not df.empty:
        df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()
        df["sector"] = df["sector"].astype(str).str.upper().str.strip()
        df["industry"] = df["industry"].astype(str).str.upper().str.strip()
        df = df.drop_duplicates(subset=["symbol"], keep="last")

    return df


def save_companies(df: pd.DataFrame) -> None:
    save_csv(df, COMPANIES_PATH, COMPANY_COLUMNS)


def load_sectors() -> pd.DataFrame:
    return load_csv(SECTORS_PATH, SECTOR_COLUMNS)


def save_sectors(df: pd.DataFrame) -> None:
    save_csv(df, SECTORS_PATH, SECTOR_COLUMNS)


def load_industries() -> pd.DataFrame:
    return load_csv(INDUSTRIES_PATH, INDUSTRY_COLUMNS)


def save_industries(df: pd.DataFrame) -> None:
    save_csv(df, INDUSTRIES_PATH, INDUSTRY_COLUMNS)


def load_listings() -> pd.DataFrame:
    return load_csv(LISTINGS_PATH, LISTING_COLUMNS)


def save_listings(df: pd.DataFrame) -> None:
    save_csv(df, LISTINGS_PATH, LISTING_COLUMNS)


def directory_summary() -> dict:
    companies = load_companies()
    sectors = load_sectors()
    industries = load_industries()
    listings = load_listings()

    return {
        "companies": len(companies),
        "with_sector": int(companies["sector"].notna().sum()) if "sector" in companies.columns else 0,
        "sectors": len(sectors),
        "industries": len(industries),
        "listings": len(listings),
        "directory": str(DIRECTORY_DIR),
    }