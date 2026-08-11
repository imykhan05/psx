from datetime import datetime
import pandas as pd

from app.master_data.company_master import CompanyMaster
from app.master_data.master_schema import MASTER_COLUMNS


class MasterBuilderV2:
    def __init__(self):
        self.master_db = CompanyMaster()

    def build(
        self,
        features_df: pd.DataFrame,
        final_df: pd.DataFrame | None = None,
        long_term_df: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        master = features_df.copy()
        master = self.clean_symbols(master)
        master = self.remove_duplicate_columns(master)
        master = self.prepare_base(master)

        master = self.merge_existing_master(master)

        if final_df is not None and not final_df.empty:
            master = self.merge_extra(master, final_df, suffix="_final")

        if long_term_df is not None and not long_term_df.empty:
            master = self.merge_extra(master, long_term_df, suffix="_lt")

        master = self.preserve_existing_metadata(master)
        master = self.remove_duplicate_columns(master)
        master = self.ensure_master_columns(master)

        return self.master_db.update(master)

    def prepare_base(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()

        if "close" in result.columns:
            result["last_price"] = result["close"]

        if "verdict" in result.columns:
            result["short_term_verdict"] = result["verdict"]

        if "adaptive_verdict" in result.columns:
            result["short_term_verdict"] = result["adaptive_verdict"]

        result["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return result

    def merge_existing_master(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        existing = self.master_db.load()

        if existing.empty or "symbol" not in existing.columns:
            return result

        existing = self.clean_symbols(existing)

        keep_cols = [
            c for c in MASTER_COLUMNS
            if c in existing.columns and c != "symbol"
        ]

        existing = existing[["symbol"] + keep_cols].copy()

        merged = result.merge(
            existing,
            on="symbol",
            how="left",
            suffixes=("", "_old"),
        )

        for col in keep_cols:
            old_col = f"{col}_old"

            if old_col in merged.columns:
                if col in merged.columns:
                    merged[col] = merged[col].where(
                        merged[col].notna()
                        & (merged[col].astype(str).str.upper().str.strip() != "UNKNOWN")
                        & (merged[col].astype(str).str.upper().str.strip() != "NAN")
                        & (merged[col].astype(str).str.strip() != ""),
                        merged[old_col],
                    )
                else:
                    merged[col] = merged[old_col]

                merged = merged.drop(columns=[old_col])

        return self.remove_duplicate_columns(merged)

    def merge_extra(self, base_df: pd.DataFrame, extra_df: pd.DataFrame, suffix: str) -> pd.DataFrame:
        base = self.clean_symbols(base_df.copy())
        extra = self.clean_symbols(extra_df.copy())

        if "symbol" not in base.columns or "symbol" not in extra.columns:
            return base

        keep_cols = [
            c for c in MASTER_COLUMNS
            if c in extra.columns and c != "symbol"
        ]

        if not keep_cols:
            return base

        extra = extra[["symbol"] + keep_cols].copy()
        extra = self.remove_duplicate_columns(extra)

        merged = base.merge(
            extra,
            on="symbol",
            how="left",
            suffixes=("", suffix),
        )

        for col in keep_cols:
            extra_col = f"{col}{suffix}"

            if extra_col in merged.columns:
                if col in merged.columns:
                    merged[col] = merged[col].where(
                        merged[col].notna()
                        & (merged[col].astype(str).str.upper().str.strip() != "UNKNOWN")
                        & (merged[col].astype(str).str.upper().str.strip() != "NAN")
                        & (merged[col].astype(str).str.strip() != ""),
                        merged[extra_col],
                    )
                else:
                    merged[col] = merged[extra_col]

                merged = merged.drop(columns=[extra_col])

        return self.remove_duplicate_columns(merged)

    def preserve_existing_metadata(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        existing = self.master_db.load()

        if existing.empty or "symbol" not in result.columns:
            return result

        existing = self.clean_symbols(existing)
        result = self.clean_symbols(result)

        keep_cols = ["symbol", "company", "sector", "industry"]

        existing = existing[
            [c for c in keep_cols if c in existing.columns]
        ].copy()

        merged = result.merge(
            existing,
            on="symbol",
            how="left",
            suffixes=("", "_meta"),
        )

        for col in ["company", "sector", "industry"]:
            meta_col = f"{col}_meta"

            if meta_col in merged.columns:
                if col in merged.columns:
                    merged[col] = merged[col].where(
                        merged[col].notna()
                        & (merged[col].astype(str).str.upper().str.strip() != "UNKNOWN")
                        & (merged[col].astype(str).str.upper().str.strip() != "NAN")
                        & (merged[col].astype(str).str.strip() != ""),
                        merged[meta_col],
                    )
                else:
                    merged[col] = merged[meta_col]

                merged = merged.drop(columns=[meta_col])

        return self.remove_duplicate_columns(merged)

    def ensure_master_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        result = self.remove_duplicate_columns(df.copy())

        for col in MASTER_COLUMNS:
            if col not in result.columns:
                result[col] = None

        result = result[MASTER_COLUMNS]
        return self.remove_duplicate_columns(result)

    @staticmethod
    def clean_symbols(df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()

        if "symbol" in result.columns:
            result["symbol"] = result["symbol"].astype(str).str.upper().str.strip()

        return result

    @staticmethod
    def remove_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
        return df.loc[:, ~df.columns.duplicated()].copy()


def build_company_master_v2(
    features_df: pd.DataFrame,
    final_df: pd.DataFrame | None = None,
    long_term_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    builder = MasterBuilderV2()
    return builder.build(
        features_df=features_df,
        final_df=final_df,
        long_term_df=long_term_df,
    )