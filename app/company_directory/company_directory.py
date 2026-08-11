import pandas as pd

from app.company_directory.company_loader import (
    load_companies,
    save_companies,
    directory_summary,
)
from app.company_directory.company_schema import COMPANY_COLUMNS


class CompanyDirectory:
    def __init__(self):
        self.companies = load_companies()

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()

        for col in COMPANY_COLUMNS:
            if col not in result.columns:
                result[col] = None

        result = result[COMPANY_COLUMNS]

        result["symbol"] = result["symbol"].astype(str).str.upper().str.strip()
        result["company"] = result["company"].astype(str).str.strip()
        result["sector"] = result["sector"].astype(str).str.upper().str.strip()
        result["industry"] = result["industry"].astype(str).str.upper().str.strip()

        result = result.drop_duplicates(subset=["symbol"], keep="last")
        result = result.sort_values("symbol").reset_index(drop=True)

        return result

    def load(self) -> pd.DataFrame:
        self.companies = load_companies()
        return self.companies

    def save(self, df: pd.DataFrame) -> None:
        cleaned = self.normalize(df)
        save_companies(cleaned)
        self.companies = cleaned

    def update_from_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        current = self.load()
        incoming = self.normalize(df)

        combined = pd.concat([current, incoming], ignore_index=True)
        combined = self.normalize(combined)

        self.save(combined)
        return combined

    def get(self, symbol: str):
        symbol = symbol.upper().strip()
        df = self.load()

        row = df[df["symbol"] == symbol]

        if row.empty:
            return None

        return row.iloc[0].to_dict()

    def sector_for(self, symbol: str) -> str:
        item = self.get(symbol)

        if not item:
            return "UNKNOWN"

        sector = item.get("sector")

        if pd.isna(sector) or not str(sector).strip():
            return "UNKNOWN"

        return str(sector).upper().strip()

    def missing_sector_symbols(self) -> list[str]:
        df = self.load()

        if df.empty:
            return []

        missing = df[
            df["sector"].isna()
            | (df["sector"].astype(str).str.strip() == "")
            | (df["sector"].astype(str).str.upper().str.strip() == "UNKNOWN")
            | (df["sector"].astype(str).str.lower().str.strip() == "nan")
        ]

        return missing["symbol"].tolist()

    def summary(self) -> dict:
        return directory_summary()