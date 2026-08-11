import pandas as pd

from app.psx_intelligence.psx_company_loader import (
    load_psx_companies,
    upsert_psx_companies,
    psx_company_summary,
)


class PSXCompanyEnricher:
    def __init__(self):
        self.companies = load_psx_companies()

    def enrich_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        companies = load_psx_companies()

        if "symbol" not in result.columns:
            raise ValueError("symbol column missing")

        result["symbol"] = result["symbol"].astype(str).str.upper().str.strip()

        if companies.empty:
            return self.ensure_columns(result)

        companies["symbol"] = companies["symbol"].astype(str).str.upper().str.strip()

        keep_cols = [
            "symbol", "sector", "industry", "market", "status",
            "listing_date", "listing_year", "website", "source", "remarks",
        ]

        available = [c for c in keep_cols if c in companies.columns]

        merged = result.merge(
            companies[available],
            on="symbol",
            how="left",
            suffixes=("", "_psx"),
        )

        for col in [
            "sector", "industry", "market", "status",
            "listing_date", "listing_year", "website", "source", "remarks",
        ]:
            psx_col = f"{col}_psx"

            if psx_col in merged.columns:
                if col in merged.columns:
                    merged[col] = merged[col].where(
                        merged[col].notna()
                        & (merged[col].astype(str).str.upper().str.strip() != "UNKNOWN")
                        & (merged[col].astype(str).str.upper().str.strip() != "NAN")
                        & (merged[col].astype(str).str.strip() != ""),
                        merged[psx_col],
                    )
                else:
                    merged[col] = merged[psx_col]

                merged = merged.drop(columns=[psx_col])

        return self.ensure_columns(merged)

    def build_from_scan(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()

        if "symbol" not in result.columns:
            raise ValueError("symbol column missing")

        if "company" not in result.columns:
            result["company"] = None

        if "sector" not in result.columns:
            result["sector"] = "UNKNOWN"

        if "industry" not in result.columns:
            result["industry"] = "UNKNOWN"

        if "market" not in result.columns:
            result["market"] = "REGULAR"

        if "status" not in result.columns:
            result["status"] = "ACTIVE"

        company_df = result[
            ["symbol", "company", "sector", "industry", "market", "status"]
        ].copy()

        company_df["listing_date"] = None
        company_df["listing_year"] = None
        company_df["website"] = None
        company_df["source"] = "SCAN"
        company_df["remarks"] = None

        existing = load_psx_companies()

        if not existing.empty:
            existing["symbol"] = existing["symbol"].astype(str).str.upper().str.strip()
            company_df["symbol"] = company_df["symbol"].astype(str).str.upper().str.strip()

            company_df = company_df.merge(
                existing,
                on="symbol",
                how="left",
                suffixes=("", "_old"),
            )

            for col in [
                "sector", "industry", "market", "status",
                "listing_date", "listing_year", "website", "source", "remarks",
            ]:
                old = f"{col}_old"

                if old in company_df.columns:
                    company_df[col] = company_df[col].where(
                        company_df[col].notna()
                        & (company_df[col].astype(str).str.upper().str.strip() != "UNKNOWN")
                        & (company_df[col].astype(str).str.upper().str.strip() != "NAN")
                        & (company_df[col].astype(str).str.strip() != ""),
                        company_df[old],
                    )
                    company_df.drop(columns=[old], inplace=True)

        return upsert_psx_companies(company_df)

    def missing_sector_report(self) -> pd.DataFrame:
        companies = load_psx_companies()

        if companies.empty:
            return pd.DataFrame(columns=["symbol", "company", "sector", "industry"])

        missing = companies[
            companies["sector"]
            .astype(str)
            .str.upper()
            .str.strip()
            .isin(["UNKNOWN", "", "NAN", "NONE"])
        ].copy()

        return missing[["symbol", "company", "sector", "industry"]]

    def summary(self) -> dict:
        return psx_company_summary()

    @staticmethod
    def ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()

        if "sector" not in result.columns:
            result["sector"] = "UNKNOWN"

        if "industry" not in result.columns:
            result["industry"] = "UNKNOWN"

        if "market" not in result.columns:
            result["market"] = "REGULAR"

        if "status" not in result.columns:
            result["status"] = "ACTIVE"

        result["sector"] = result["sector"].fillna("UNKNOWN").astype(str).str.upper().str.strip()
        result["industry"] = result["industry"].fillna("UNKNOWN").astype(str).str.upper().str.strip()
        result["market"] = result["market"].fillna("REGULAR").astype(str).str.upper().str.strip()
        result["status"] = result["status"].fillna("ACTIVE").astype(str).str.upper().str.strip()

        result.loc[result["sector"].isin(["", "NAN", "NONE"]), "sector"] = "UNKNOWN"
        result.loc[result["industry"].isin(["", "NAN", "NONE"]), "industry"] = "UNKNOWN"

        return result


def enrich_with_psx_company_data(df: pd.DataFrame) -> pd.DataFrame:
    return PSXCompanyEnricher().enrich_dataframe(df)


def build_psx_company_database_from_scan(df: pd.DataFrame) -> pd.DataFrame:
    return PSXCompanyEnricher().build_from_scan(df)