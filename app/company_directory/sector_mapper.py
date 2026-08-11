import pandas as pd

from app.company_directory.company_directory import CompanyDirectory


class SectorMapper:
    def __init__(self):
        self.directory = CompanyDirectory()

    def attach_directory_data(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        companies = self.directory.load()

        if companies.empty:
            return self.ensure_sector_columns(result)

        result["symbol"] = result["symbol"].astype(str).str.upper().str.strip()
        companies["symbol"] = companies["symbol"].astype(str).str.upper().str.strip()

        keep_cols = [
            "symbol", "sector", "industry", "market", "status",
            "listing_date", "listing_year", "website", "remarks",
        ]

        available = [c for c in keep_cols if c in companies.columns]

        merged = result.merge(
            companies[available],
            on="symbol",
            how="left",
            suffixes=("", "_dir"),
        )

        for col in ["sector", "industry", "market", "status", "listing_date", "listing_year", "website", "remarks"]:
            dir_col = f"{col}_dir"

            if dir_col in merged.columns:
                if col in merged.columns:
                    merged[col] = merged[col].where(
                        merged[col].notna()
                        & (merged[col].astype(str).str.upper().str.strip() != "UNKNOWN")
                        & (merged[col].astype(str).str.strip() != ""),
                        merged[dir_col],
                    )
                else:
                    merged[col] = merged[dir_col]

                merged = merged.drop(columns=[dir_col])

        return self.ensure_sector_columns(merged)

    def ensure_sector_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()

        if "sector" not in result.columns:
            result["sector"] = "UNKNOWN"

        if "industry" not in result.columns:
            result["industry"] = "UNKNOWN"

        result["sector"] = result["sector"].fillna("UNKNOWN").astype(str).str.upper().str.strip()
        result["industry"] = result["industry"].fillna("UNKNOWN").astype(str).str.upper().str.strip()

        result.loc[result["sector"].isin(["", "NAN", "NONE"]), "sector"] = "UNKNOWN"
        result.loc[result["industry"].isin(["", "NAN", "NONE"]), "industry"] = "UNKNOWN"

        return result

    def build_directory_from_scan(self, df: pd.DataFrame) -> pd.DataFrame:
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

        directory_df = result[
            ["symbol", "company", "sector", "industry", "market", "status"]
        ].copy()

        directory_df["listing_date"] = None
        directory_df["listing_year"] = None
        directory_df["website"] = None
        directory_df["remarks"] = None

        existing = self.directory.load()

        if not existing.empty:
            existing["symbol"] = existing["symbol"].astype(str).str.upper().str.strip()
            directory_df["symbol"] = directory_df["symbol"].astype(str).str.upper().str.strip()

            directory_df = directory_df.merge(
                existing,
                on="symbol",
                how="left",
                suffixes=("", "_old"),
            )

            for col in [
                "sector", "industry", "market", "status",
                "listing_date", "listing_year", "website", "remarks",
            ]:
                old = f"{col}_old"

                if old in directory_df.columns:
                    directory_df[col] = directory_df[col].where(
                        directory_df[col].notna()
                        & (directory_df[col].astype(str).str.upper().str.strip() != "UNKNOWN")
                        & (directory_df[col].astype(str).str.upper().str.strip() != "NAN")
                        & (directory_df[col].astype(str).str.strip() != ""),
                        directory_df[old],
                    )
                    directory_df.drop(columns=[old], inplace=True)

        return self.directory.update_from_dataframe(directory_df)

    def missing_sector_report(self) -> pd.DataFrame:
        df = self.directory.load()

        if df.empty:
            return pd.DataFrame(columns=["symbol", "company", "sector", "industry"])

        missing = df[
            df["sector"].isna()
            | (df["sector"].astype(str).str.upper().str.strip().isin(["", "UNKNOWN", "NAN", "NONE"]))
        ].copy()

        return missing[["symbol", "company", "sector", "industry"]]

    def summary(self) -> dict:
        df = self.directory.load()

        if df.empty:
            return {
                "companies": 0,
                "unknown_sector": 0,
                "known_sector": 0,
            }

        unknown = (
            df["sector"].isna()
            | df["sector"].astype(str).str.upper().str.strip().isin(["", "UNKNOWN", "NAN", "NONE"])
        ).sum()

        return {
            "companies": int(len(df)),
            "unknown_sector": int(unknown),
            "known_sector": int(len(df) - unknown),
        }


def attach_directory_data(df: pd.DataFrame) -> pd.DataFrame:
    return SectorMapper().attach_directory_data(df)


def build_directory_from_scan(df: pd.DataFrame) -> pd.DataFrame:
    return SectorMapper().build_directory_from_scan(df)