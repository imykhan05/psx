from datetime import datetime
import pandas as pd

from app.master_data.company_master import CompanyMaster
from app.master_data.master_schema import MASTER_COLUMNS


class MasterBuilder:
    def __init__(self):
        self.master_db = CompanyMaster()

    def build(self, final_df: pd.DataFrame, long_term_df: pd.DataFrame | None = None) -> pd.DataFrame:
        master = final_df.copy()
        master = self.remove_duplicate_columns(master)
        master = self.prepare_short_term(master)

        master = self.preserve_existing_sectors(master)

        if long_term_df is not None and not long_term_df.empty:
            master = self.merge_long_term(master, long_term_df)

        master = self.preserve_existing_sectors(master)
        master = self.remove_duplicate_columns(master)
        master = self.ensure_master_columns(master)

        return self.master_db.update(master)

    def preserve_existing_sectors(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        existing = self.master_db.load()

        if existing.empty or "symbol" not in result.columns or "symbol" not in existing.columns:
            return result

        result["symbol"] = result["symbol"].astype(str).str.upper().str.strip()
        existing["symbol"] = existing["symbol"].astype(str).str.upper().str.strip()

        keep_cols = ["symbol", "sector", "industry"]
        existing = existing[[c for c in keep_cols if c in existing.columns]].copy()

        merged = result.merge(existing, on="symbol", how="left", suffixes=("", "_old"))

        for col in ["sector", "industry"]:
            old_col = f"{col}_old"
            if old_col in merged.columns:
                merged[col] = merged[col].where(
                    merged[col].notna()
                    & (merged[col].astype(str).str.upper().str.strip() != "UNKNOWN")
                    & (merged[col].astype(str).str.upper().str.strip() != "NAN")
                    & (merged[col].astype(str).str.strip() != ""),
                    merged[old_col],
                )
                merged = merged.drop(columns=[old_col])

        return self.remove_duplicate_columns(merged)

    def prepare_short_term(self, df: pd.DataFrame) -> pd.DataFrame:
        result = self.remove_duplicate_columns(df.copy())

        if "close" in result.columns:
            result["last_price"] = result["close"]

        if "adaptive_verdict" in result.columns:
            result["short_term_verdict"] = result["adaptive_verdict"]
        elif "verdict" in result.columns:
            result["short_term_verdict"] = result["verdict"]

        result["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return self.remove_duplicate_columns(result)

    def merge_long_term(self, short_df: pd.DataFrame, long_df: pd.DataFrame) -> pd.DataFrame:
        result = self.remove_duplicate_columns(short_df.copy())
        long_term = self.remove_duplicate_columns(long_df.copy())

        if "symbol" not in result.columns or "symbol" not in long_term.columns:
            return result

        result["symbol"] = result["symbol"].astype(str).str.upper().str.strip()
        long_term["symbol"] = long_term["symbol"].astype(str).str.upper().str.strip()

        keep_cols = [c for c in MASTER_COLUMNS if c in long_term.columns and c != "symbol"]
        long_term = long_term[["symbol"] + keep_cols].copy()
        long_term = self.remove_duplicate_columns(long_term)

        merged = result.merge(long_term, on="symbol", how="left", suffixes=("", "_lt"))
        merged = self.remove_duplicate_columns(merged)

        for col in MASTER_COLUMNS:
            lt_col = f"{col}_lt"
            if lt_col in merged.columns:
                if col in merged.columns:
                    merged[col] = merged[col].combine_first(merged[lt_col])
                else:
                    merged[col] = merged[lt_col]
                merged = merged.drop(columns=[lt_col])

        return self.remove_duplicate_columns(merged)

    def ensure_master_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        result = self.remove_duplicate_columns(df.copy())

        for col in MASTER_COLUMNS:
            if col not in result.columns:
                result[col] = None

        result = result[MASTER_COLUMNS]
        return self.remove_duplicate_columns(result)

    @staticmethod
    def remove_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
        return df.loc[:, ~df.columns.duplicated()].copy()

    def summary(self) -> dict:
        return self.master_db.summary()


def build_company_master(final_df: pd.DataFrame, long_term_df: pd.DataFrame | None = None) -> pd.DataFrame:
    builder = MasterBuilder()
    return builder.build(final_df=final_df, long_term_df=long_term_df)