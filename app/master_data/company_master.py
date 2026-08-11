from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from app.master_data.master_schema import MASTER_COLUMNS


MASTER_DATABASE = Path("database/master/company_master.csv")

MISSING_TEXT_VALUES = {
    "",
    "NAN",
    "NONE",
    "NULL",
    "UNKNOWN",
    "N/A",
    "NA",
    "-",
}


class CompanyMaster:
    """
    Central Company Master Database.

    Important behaviour:
    - Existing valid data is never overwritten by blank/UNKNOWN values.
    - New valid data replaces old missing data.
    - Duplicate symbols are merged column by column.
    - Symbols, sectors and industries are normalized consistently.
    """

    def __init__(self):
        self.master_path = MASTER_DATABASE

    def load(self) -> pd.DataFrame:
        if (
            not self.master_path.exists()
            or self.master_path.stat().st_size == 0
        ):
            return pd.DataFrame(columns=MASTER_COLUMNS)

        try:
            df = pd.read_csv(self.master_path)
        except (
            pd.errors.EmptyDataError,
            pd.errors.ParserError,
            UnicodeDecodeError,
        ):
            return pd.DataFrame(columns=MASTER_COLUMNS)

        return self.normalize(df)

    def save(self, df: pd.DataFrame) -> None:
        normalized = self.normalize(df)

        self.master_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        normalized.to_csv(
            self.master_path,
            index=False,
        )

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or not isinstance(df, pd.DataFrame):
            return pd.DataFrame(columns=MASTER_COLUMNS)

        result = df.copy()

        result = result.loc[
            :,
            ~result.columns.duplicated(),
        ].copy()

        for column in MASTER_COLUMNS:
            if column not in result.columns:
                result[column] = pd.NA

        result = result[MASTER_COLUMNS].copy()

        if "symbol" in result.columns:
            result["symbol"] = (
                result["symbol"]
                .fillna("")
                .astype(str)
                .str.upper()
                .str.strip()
            )

            result = result[
                ~result["symbol"].isin(MISSING_TEXT_VALUES)
            ].copy()

        for column in [
            "company",
            "sector",
            "industry",
        ]:
            if column in result.columns:
                result[column] = result[column].apply(
                    self.normalize_text_value
                )

        result = self.merge_duplicate_symbols(result)

        if "symbol" in result.columns:
            result = result.sort_values(
                "symbol",
                kind="stable",
            ).reset_index(drop=True)

        return result

    def update(self, new_data: pd.DataFrame) -> pd.DataFrame:
        master = self.load()
        incoming = self.normalize(new_data)

        if incoming.empty:
            return master

        if master.empty:
            self.save(incoming)
            return incoming

        master = master.set_index(
            "symbol",
            drop=False,
        )

        incoming = incoming.set_index(
            "symbol",
            drop=False,
        )

        all_symbols = master.index.union(
            incoming.index
        )

        merged_rows = []

        for symbol in all_symbols:
            old_row = (
                master.loc[symbol]
                if symbol in master.index
                else None
            )

            new_row = (
                incoming.loc[symbol]
                if symbol in incoming.index
                else None
            )

            if isinstance(old_row, pd.DataFrame):
                old_row = self.merge_rows(
                    old_row.to_dict(orient="records")
                )

            if isinstance(new_row, pd.DataFrame):
                new_row = self.merge_rows(
                    new_row.to_dict(orient="records")
                )

            merged_row = {
                "symbol": symbol,
            }

            for column in MASTER_COLUMNS:
                if column == "symbol":
                    continue

                old_value = (
                    old_row.get(column)
                    if isinstance(old_row, (pd.Series, dict))
                    else pd.NA
                )

                new_value = (
                    new_row.get(column)
                    if isinstance(new_row, (pd.Series, dict))
                    else pd.NA
                )

                merged_row[column] = self.choose_best_value(
                    old_value=old_value,
                    new_value=new_value,
                    column=column,
                )

            merged_rows.append(merged_row)

        combined = pd.DataFrame(
            merged_rows,
            columns=MASTER_COLUMNS,
        )

        combined = self.normalize(combined)

        self.save(combined)

        return combined

    def get_company(self, symbol: str) -> dict | None:
        normalized_symbol = str(symbol).upper().strip()

        if not normalized_symbol:
            return None

        master = self.load()

        row = master[
            master["symbol"] == normalized_symbol
        ]

        if row.empty:
            return None

        return row.iloc[0].to_dict()

    def exists(self, symbol: str) -> bool:
        return self.get_company(symbol) is not None

    def total_companies(self) -> int:
        return len(self.load())

    def summary(self) -> dict:
        master = self.load()

        known_sector = 0
        unknown_sector = 0

        if "sector" in master.columns:
            sector_validity = master["sector"].apply(
                self.is_valid_value
            )

            known_sector = int(
                sector_validity.sum()
            )

            unknown_sector = int(
                (~sector_validity).sum()
            )

        with_fundamentals = 0

        if "eps" in master.columns:
            with_fundamentals = int(
                master["eps"].apply(
                    self.is_valid_numeric_or_text
                ).sum()
            )

        with_ai_score = 0

        if "adaptive_ai_score" in master.columns:
            with_ai_score = int(
                master["adaptive_ai_score"].apply(
                    self.is_valid_numeric_or_text
                ).sum()
            )

        return {
            "total_companies": int(len(master)),
            "with_sector": known_sector,
            "unknown_sector": unknown_sector,
            "with_fundamentals": with_fundamentals,
            "with_ai_score": with_ai_score,
            "file": str(self.master_path),
        }

    def merge_duplicate_symbols(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        if df.empty or "symbol" not in df.columns:
            return df

        merged_rows = []

        for symbol, group in df.groupby(
            "symbol",
            sort=False,
            dropna=False,
        ):
            rows = group.to_dict(
                orient="records"
            )

            merged = self.merge_rows(rows)
            merged["symbol"] = symbol

            merged_rows.append(merged)

        return pd.DataFrame(
            merged_rows,
            columns=MASTER_COLUMNS,
        )

    def merge_rows(
        self,
        rows: list[dict],
    ) -> dict:
        if not rows:
            return {
                column: pd.NA
                for column in MASTER_COLUMNS
            }

        merged = {
            column: pd.NA
            for column in MASTER_COLUMNS
        }

        for row in rows:
            for column in MASTER_COLUMNS:
                current_value = merged.get(
                    column,
                    pd.NA,
                )

                candidate_value = row.get(
                    column,
                    pd.NA,
                )

                merged[column] = self.choose_best_value(
                    old_value=current_value,
                    new_value=candidate_value,
                    column=column,
                )

        return merged

    def choose_best_value(
        self,
        old_value: Any,
        new_value: Any,
        column: str,
    ) -> Any:
        old_valid = self.is_valid_value(
            old_value
        )

        new_valid = self.is_valid_value(
            new_value
        )

        if column == "symbol":
            if new_valid:
                return str(
                    new_value
                ).upper().strip()

            if old_valid:
                return str(
                    old_value
                ).upper().strip()

            return pd.NA

        if column in {
            "sector",
            "industry",
            "company",
        }:
            if new_valid:
                return self.normalize_text_value(
                    new_value
                )

            if old_valid:
                return self.normalize_text_value(
                    old_value
                )

            return pd.NA

        if new_valid:
            return new_value

        if old_valid:
            return old_value

        return pd.NA

    @staticmethod
    def normalize_text_value(
        value: Any,
    ) -> Any:
        try:
            if pd.isna(value):
                return pd.NA
        except Exception:
            pass

        text = str(value).strip()

        if text.upper() in MISSING_TEXT_VALUES:
            return pd.NA

        return text.upper()

    @staticmethod
    def is_valid_value(
        value: Any,
    ) -> bool:
        try:
            if pd.isna(value):
                return False
        except Exception:
            pass

        text = str(value).strip()

        if text.upper() in MISSING_TEXT_VALUES:
            return False

        return True

    @staticmethod
    def is_valid_numeric_or_text(
        value: Any,
    ) -> bool:
        try:
            if pd.isna(value):
                return False
        except Exception:
            pass

        text = str(value).strip()

        if text.upper() in MISSING_TEXT_VALUES:
            return False

        try:
            numeric = float(value)

            return numeric != 0

        except (
            TypeError,
            ValueError,
        ):
            return bool(text)