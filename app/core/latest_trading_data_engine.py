from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


ENGINE_VERSION = "latest_trading_data_engine_v2_historical_files"

DEFAULT_HISTORY_FOLDER = Path("database") / "historical_files"

SUPPORTED_FILE_EXTENSIONS = (
    ".lis.z",
    ".lis",
    ".csv",
    ".txt",
    ".zip",
)

SUPPORTED_DATE_FORMATS = (
    "%d%b%Y",
    "%d-%b-%Y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y%m%d",
    "%d %b %Y",
)

DATE_PATTERNS = (
    r"(?<!\d)(20\d{6})(?!\d)",
    r"(?<!\d)(19\d{6})(?!\d)",
    r"(?<!\d)(\d{2}[A-Z]{3}\d{4})(?![A-Z0-9])",
)


class LatestTradingDataEngine:
    """
    Latest Trading Data Engine V2

    Responsibilities
    ----------------
    1. Recursively scan database/historical_files.
    2. Detect trading dates from filenames.
    3. Select the latest valid daily market file.
    4. Parse that file through the existing PSX parser.
    5. Validate and normalize the snapshot date.
    6. Fall back to DataFrame maximum-date detection when needed.
    7. Return detailed diagnostics for main.py and reports.

    This engine does not delete, move, or modify historical source files.
    """

    def __init__(
        self,
        history_folder: str | Path = DEFAULT_HISTORY_FOLDER,
        date_column: str = "date",
        supported_extensions: Iterable[str] = SUPPORTED_FILE_EXTENSIONS,
    ):
        self.history_folder = Path(history_folder)
        self.date_column = date_column

        self.supported_extensions = tuple(
            str(extension).lower()
            for extension in supported_extensions
        )

    # =========================================================
    # PUBLIC: FIND LATEST FILE
    # =========================================================
    def find_latest_file(self) -> tuple[Path | None, dict]:
        if not self.history_folder.exists():
            return None, self.empty_file_summary(
                f"Historical files folder not found: {self.history_folder}"
            )

        if not self.history_folder.is_dir():
            return None, self.empty_file_summary(
                f"Historical files path is not a folder: {self.history_folder}"
            )

        supported_files = []

        for path in self.history_folder.rglob("*"):
            if not path.is_file():
                continue

            if not self.is_supported_file(path):
                continue

            filename_date = extract_date_from_filename(path.name)

            supported_files.append(
                {
                    "path": path,
                    "filename_date": filename_date,
                    "modified_time": path.stat().st_mtime,
                    "size_bytes": path.stat().st_size,
                }
            )

        if not supported_files:
            return None, self.empty_file_summary(
                f"No supported daily market files found under "
                f"{self.history_folder}"
            )

        dated_files = [
            item
            for item in supported_files
            if item["filename_date"] is not None
        ]

        if dated_files:
            dated_files.sort(
                key=lambda item: (
                    item["filename_date"],
                    item["modified_time"],
                ),
                reverse=True,
            )

            selected = dated_files[0]
            selection_method = "filename_trading_date"

        else:
            supported_files.sort(
                key=lambda item: item["modified_time"],
                reverse=True,
            )

            selected = supported_files[0]
            selection_method = "modified_time_fallback"

        selected_path = selected["path"]
        selected_date = selected["filename_date"]

        summary = {
            "engine_version": ENGINE_VERSION,
            "status": "success",
            "history_folder": str(self.history_folder.resolve()),
            "files_scanned": int(len(supported_files)),
            "files_with_valid_filename_date": int(len(dated_files)),
            "latest_file": str(selected_path.resolve()),
            "latest_filename": selected_path.name,
            "latest_file_size_bytes": int(selected["size_bytes"]),
            "latest_file_modified_time": datetime.fromtimestamp(
                selected["modified_time"]
            ).isoformat(timespec="seconds"),
            "filename_trading_date": (
                format_display_date(selected_date)
                if selected_date is not None
                else None
            ),
            "filename_trading_date_iso": (
                selected_date.strftime("%Y-%m-%d")
                if selected_date is not None
                else None
            ),
            "selection_method": selection_method,
            "reason": "Latest historical daily file resolved successfully",
        }

        return selected_path, summary

    # =========================================================
    # PUBLIC: LOAD LATEST FILE
    # =========================================================
    def load_latest_file(self) -> tuple[pd.DataFrame, dict]:
        latest_file, file_summary = self.find_latest_file()

        if latest_file is None:
            return pd.DataFrame(), file_summary

        try:
            source_df = self.read_market_file(latest_file)

        except Exception as exc:
            summary = dict(file_summary)
            summary.update(
                {
                    "status": "failed",
                    "source_records": 0,
                    "latest_snapshot_records": 0,
                    "latest_snapshot_symbols": 0,
                    "reason": (
                        f"Failed to parse latest daily file "
                        f"{latest_file.name}: {exc}"
                    ),
                }
            )

            return pd.DataFrame(), summary

        source_df = remove_duplicate_columns(source_df)

        if source_df.empty:
            summary = dict(file_summary)
            summary.update(
                {
                    "status": "failed",
                    "source_records": 0,
                    "latest_snapshot_records": 0,
                    "latest_snapshot_symbols": 0,
                    "reason": "Latest daily file parsed but returned no records",
                }
            )

            return pd.DataFrame(), summary

        filename_date = extract_date_from_filename(latest_file.name)

        snapshot, date_summary = self.resolve(
            source_df,
            preferred_date=filename_date,
        )

        summary = dict(file_summary)
        summary.update(date_summary)

        summary["source_file"] = str(latest_file.resolve())
        summary["source_records"] = int(len(source_df))

        if snapshot.empty:
            summary["status"] = "failed"
            summary["reason"] = (
                date_summary.get("reason")
                or "Could not resolve latest snapshot from daily file"
            )

            return snapshot, summary

        summary["status"] = "success"
        summary["reason"] = (
            "Latest historical daily file parsed and trading "
            "snapshot resolved successfully"
        )

        return snapshot, summary

    # =========================================================
    # PUBLIC: RESOLVE DATAFRAME LATEST DATE
    # =========================================================
    def resolve(
        self,
        df: pd.DataFrame,
        preferred_date: pd.Timestamp | datetime | str | None = None,
    ) -> tuple[pd.DataFrame, dict]:
        if df is None:
            return pd.DataFrame(), self.empty_dataframe_summary(
                "Input DataFrame is None"
            )

        if not isinstance(df, pd.DataFrame):
            return pd.DataFrame(), self.empty_dataframe_summary(
                "Input is not a pandas DataFrame"
            )

        if df.empty:
            return df.copy(), self.empty_dataframe_summary(
                "Input DataFrame is empty"
            )

        data = remove_duplicate_columns(df.copy())
        original_records = len(data)

        if self.date_column not in data.columns:
            parsed_preferred = parse_trading_date(preferred_date)

            if pd.isna(parsed_preferred):
                return pd.DataFrame(), self.empty_dataframe_summary(
                    f"Date column '{self.date_column}' is missing and "
                    f"no valid filename date is available",
                    total_input_records=original_records,
                )

            data[self.date_column] = format_display_date(
                parsed_preferred
            )

        data["_parsed_trading_date"] = data[
            self.date_column
        ].apply(parse_trading_date)

        parsed_preferred = parse_trading_date(preferred_date)

        missing_date_mask = data["_parsed_trading_date"].isna()

        if (
            missing_date_mask.any()
            and not pd.isna(parsed_preferred)
        ):
            data.loc[
                missing_date_mask,
                "_parsed_trading_date",
            ] = parsed_preferred

            data.loc[
                missing_date_mask,
                self.date_column,
            ] = format_display_date(parsed_preferred)

        valid_data = data[
            data["_parsed_trading_date"].notna()
        ].copy()

        invalid_date_records = original_records - len(valid_data)

        if valid_data.empty:
            return pd.DataFrame(), self.empty_dataframe_summary(
                "No valid trading dates found in parsed file",
                total_input_records=original_records,
                invalid_date_records=invalid_date_records,
            )

        if not pd.isna(parsed_preferred):
            preferred_rows = valid_data[
                valid_data["_parsed_trading_date"]
                == parsed_preferred
            ].copy()

            if not preferred_rows.empty:
                latest_date = parsed_preferred
                latest_snapshot = preferred_rows
                date_selection_method = "filename_date_confirmed"

            else:
                latest_date = valid_data[
                    "_parsed_trading_date"
                ].max()

                latest_snapshot = valid_data[
                    valid_data["_parsed_trading_date"]
                    == latest_date
                ].copy()

                date_selection_method = (
                    "dataframe_max_date_filename_mismatch"
                )

        else:
            latest_date = valid_data[
                "_parsed_trading_date"
            ].max()

            latest_snapshot = valid_data[
                valid_data["_parsed_trading_date"]
                == latest_date
            ].copy()

            date_selection_method = "dataframe_max_date"

        available_dates = (
            valid_data["_parsed_trading_date"]
            .dropna()
            .drop_duplicates()
            .sort_values()
        )

        latest_snapshot = latest_snapshot.drop(
            columns=["_parsed_trading_date"],
            errors="ignore",
        )

        latest_snapshot[self.date_column] = (
            format_display_date(latest_date)
        )

        latest_snapshot = latest_snapshot.reset_index(drop=True)

        summary = {
            "engine_version": ENGINE_VERSION,
            "status": "success",
            "date_column": self.date_column,
            "total_input_records": int(original_records),
            "valid_date_records": int(len(valid_data)),
            "invalid_date_records": int(invalid_date_records),
            "total_trading_dates_in_source": int(
                len(available_dates)
            ),
            "oldest_trading_date_in_source": (
                format_display_date(available_dates.iloc[0])
                if len(available_dates)
                else None
            ),
            "latest_trading_date": format_display_date(
                latest_date
            ),
            "latest_trading_date_iso": latest_date.strftime(
                "%Y-%m-%d"
            ),
            "latest_snapshot_records": int(
                len(latest_snapshot)
            ),
            "latest_snapshot_symbols": int(
                latest_snapshot["symbol"].nunique()
                if "symbol" in latest_snapshot.columns
                else len(latest_snapshot)
            ),
            "preferred_filename_date": (
                format_display_date(parsed_preferred)
                if not pd.isna(parsed_preferred)
                else None
            ),
            "date_selection_method": date_selection_method,
            "source_first_row_date": str(
                data[self.date_column].iloc[0]
            ),
            "source_last_row_date": str(
                data[self.date_column].iloc[-1]
            ),
            "reason": (
                "Latest trading-day snapshot resolved successfully"
            ),
        }

        return latest_snapshot, summary

    # =========================================================
    # PUBLIC: SPECIFIC DATE
    # =========================================================
    def resolve_requested_date(
        self,
        df: pd.DataFrame,
        requested_date: str,
    ) -> tuple[pd.DataFrame, dict]:
        if df is None or not isinstance(df, pd.DataFrame):
            return pd.DataFrame(), self.empty_dataframe_summary(
                "No valid DataFrame supplied"
            )

        if df.empty:
            return pd.DataFrame(), self.empty_dataframe_summary(
                "Input DataFrame is empty"
            )

        data = remove_duplicate_columns(df.copy())

        if self.date_column not in data.columns:
            return pd.DataFrame(), self.empty_dataframe_summary(
                f"Date column '{self.date_column}' is missing"
            )

        requested = parse_trading_date(requested_date)

        if pd.isna(requested):
            return pd.DataFrame(), self.empty_dataframe_summary(
                f"Invalid requested trading date: {requested_date}"
            )

        data["_parsed_trading_date"] = data[
            self.date_column
        ].apply(parse_trading_date)

        snapshot = data[
            data["_parsed_trading_date"] == requested
        ].copy()

        snapshot = snapshot.drop(
            columns=["_parsed_trading_date"],
            errors="ignore",
        ).reset_index(drop=True)

        if snapshot.empty:
            return snapshot, self.empty_dataframe_summary(
                f"No records found for {requested_date}"
            )

        snapshot[self.date_column] = format_display_date(
            requested
        )

        summary = {
            "engine_version": ENGINE_VERSION,
            "status": "success",
            "requested_trading_date": format_display_date(
                requested
            ),
            "requested_trading_date_iso": requested.strftime(
                "%Y-%m-%d"
            ),
            "latest_snapshot_records": int(len(snapshot)),
            "latest_snapshot_symbols": int(
                snapshot["symbol"].nunique()
                if "symbol" in snapshot.columns
                else len(snapshot)
            ),
            "reason": (
                "Requested trading-day snapshot resolved successfully"
            ),
        }

        return snapshot, summary

    # =========================================================
    # FILE PARSER
    # =========================================================
    def read_market_file(
        self,
        file_path: str | Path,
    ) -> pd.DataFrame:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Market file does not exist: {path}"
            )

        lower_name = path.name.lower()

        if lower_name.endswith(".csv"):
            return pd.read_csv(path)

        from app.core.parser import read_psx_file

        return read_psx_file(str(path))

    def is_supported_file(
        self,
        path: Path,
    ) -> bool:
        lower_name = path.name.lower()

        return any(
            lower_name.endswith(extension)
            for extension in self.supported_extensions
        )

    # =========================================================
    # EMPTY SUMMARIES
    # =========================================================
    def empty_file_summary(
        self,
        reason: str,
    ) -> dict:
        return {
            "engine_version": ENGINE_VERSION,
            "status": "failed",
            "history_folder": str(
                self.history_folder.resolve()
                if self.history_folder.exists()
                else self.history_folder
            ),
            "files_scanned": 0,
            "files_with_valid_filename_date": 0,
            "latest_file": None,
            "latest_filename": None,
            "filename_trading_date": None,
            "filename_trading_date_iso": None,
            "selection_method": None,
            "latest_snapshot_records": 0,
            "latest_snapshot_symbols": 0,
            "reason": reason,
        }

    def empty_dataframe_summary(
        self,
        reason: str,
        total_input_records: int = 0,
        invalid_date_records: int = 0,
    ) -> dict:
        return {
            "engine_version": ENGINE_VERSION,
            "status": "failed",
            "date_column": self.date_column,
            "total_input_records": int(total_input_records),
            "valid_date_records": 0,
            "invalid_date_records": int(
                invalid_date_records
            ),
            "total_trading_dates_in_source": 0,
            "oldest_trading_date_in_source": None,
            "latest_trading_date": None,
            "latest_trading_date_iso": None,
            "latest_snapshot_records": 0,
            "latest_snapshot_symbols": 0,
            "reason": reason,
        }


# =============================================================
# MAIN FUNCTIONS FOR MAIN.PY
# =============================================================
def get_latest_historical_file(
    history_folder: str | Path = DEFAULT_HISTORY_FOLDER,
) -> tuple[Path | None, dict]:
    engine = LatestTradingDataEngine(
        history_folder=history_folder
    )

    return engine.find_latest_file()


def load_latest_historical_snapshot(
    history_folder: str | Path = DEFAULT_HISTORY_FOLDER,
    date_column: str = "date",
) -> tuple[pd.DataFrame, dict]:
    engine = LatestTradingDataEngine(
        history_folder=history_folder,
        date_column=date_column,
    )

    return engine.load_latest_file()


def get_latest_trading_snapshot(
    df: pd.DataFrame,
    date_column: str = "date",
) -> tuple[pd.DataFrame, dict]:
    """
    Backward-compatible DataFrame resolver.

    Existing main.py versions can continue importing this function.
    """

    engine = LatestTradingDataEngine(
        date_column=date_column
    )

    return engine.resolve(df)


def get_latest_trading_snapshot_from_csv(
    file_path: str | Path,
    date_column: str = "date",
    **read_csv_kwargs: Any,
) -> tuple[pd.DataFrame, dict]:
    path = Path(file_path)

    if not path.exists():
        engine = LatestTradingDataEngine(
            date_column=date_column
        )

        return pd.DataFrame(), engine.empty_dataframe_summary(
            f"CSV file not found: {path}"
        )

    try:
        data = pd.read_csv(
            path,
            **read_csv_kwargs,
        )

    except Exception as exc:
        engine = LatestTradingDataEngine(
            date_column=date_column
        )

        return pd.DataFrame(), engine.empty_dataframe_summary(
            f"Failed to read CSV: {exc}"
        )

    engine = LatestTradingDataEngine(
        date_column=date_column
    )

    return engine.resolve(data)


def get_snapshot_for_date(
    df: pd.DataFrame,
    requested_date: str,
    date_column: str = "date",
) -> tuple[pd.DataFrame, dict]:
    engine = LatestTradingDataEngine(
        date_column=date_column
    )

    return engine.resolve_requested_date(
        df=df,
        requested_date=requested_date,
    )


# =============================================================
# DATE HELPERS
# =============================================================
def extract_date_from_filename(
    filename: str,
) -> pd.Timestamp | None:
    text = str(filename).upper().strip()

    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text)

        if not match:
            continue

        parsed = parse_trading_date(match.group(1))

        if not pd.isna(parsed):
            return parsed

    return None


def parse_trading_date(
    value: Any,
) -> pd.Timestamp:
    if value is None:
        return pd.NaT

    try:
        if pd.isna(value):
            return pd.NaT
    except Exception:
        pass

    if isinstance(value, pd.Timestamp):
        return value.normalize()

    if isinstance(value, datetime):
        return pd.Timestamp(value).normalize()

    text = str(value).strip().upper()

    if text in {
        "",
        "NAN",
        "NAT",
        "NONE",
        "NULL",
    }:
        return pd.NaT

    text = (
        text.replace("_", "-")
        .replace("\\", "-")
        .replace(".", "-")
        .strip()
    )

    compact_digits = re.sub(
        r"[^0-9]",
        "",
        text,
    )

    if len(compact_digits) == 8:
        if compact_digits.startswith(("19", "20")):
            try:
                return pd.Timestamp(
                    datetime.strptime(
                        compact_digits,
                        "%Y%m%d",
                    )
                ).normalize()
            except ValueError:
                pass

    for date_format in SUPPORTED_DATE_FORMATS:
        try:
            return pd.Timestamp(
                datetime.strptime(
                    text,
                    date_format,
                )
            ).normalize()

        except ValueError:
            continue

    try:
        parsed = pd.to_datetime(
            text,
            errors="coerce",
            dayfirst=True,
        )

        if pd.isna(parsed):
            return pd.NaT

        return pd.Timestamp(parsed).normalize()

    except Exception:
        return pd.NaT


def format_display_date(
    value: Any,
) -> str | None:
    parsed = parse_trading_date(value)

    if pd.isna(parsed):
        return None

    return parsed.strftime("%d%b%Y").upper()


def remove_duplicate_columns(
    df: pd.DataFrame,
) -> pd.DataFrame:
    if df is None or not hasattr(df, "columns"):
        return pd.DataFrame()

    return df.loc[
        :,
        ~df.columns.duplicated(),
    ].copy()