from __future__ import annotations

import json
import re
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from app.core.parser import read_psx_file
from app.core.sqlite_database import sqlite_summary, update_sqlite_database
from app.core.latest_trading_data_engine import (
    format_display_date,
    get_latest_trading_snapshot,
    parse_trading_date,
    remove_duplicate_columns,
)


ENGINE_VERSION = "daily_data_manager_v2_2_robust_file_detection"

DEFAULT_HISTORICAL_FOLDER = Path("database") / "historical_files"
DEFAULT_STATE_FILE = Path("database") / "daily_data_manager_state.json"
DEFAULT_LOG_FILE = Path("logs") / "daily_data_manager.log"

SUPPORTED_EXTENSIONS = (
    ".lis.z",
    ".lis",
    ".z",
    ".zip",
)

# NOTE (fixed):
# "summary" and "log" were removed from this list because real PSX daily
# files use names like "2026-01-12_mkt_summary.Z", which were being
# incorrectly filtered out as log/metadata files. Keep this list narrow
# and specific to avoid false positives against real daily market files.
IGNORED_NAME_KEYWORDS = (
    "download_log",
    "daily_download_log",
    "readme",
    "metadata",
    "state",
)

DATE_PATTERNS = (
    r"(?<!\d)(20\d{6})(?!\d)",                 # 20260709
    r"(?<!\d)(19\d{6})(?!\d)",                 # 19991231
    r"(?<!\d)(\d{2}[A-Z]{3}\d{4})(?![A-Z0-9])",  # 09JUL2026
    r"(?<!\d)(20\d{2})[-_](\d{2})[-_](\d{2})(?!\d)",  # 2026-07-09
    r"(?<!\d)(\d{2})[-_](\d{2})[-_](20\d{2})(?!\d)",  # 09-07-2026
)


@dataclass
class HistoricalFileRecord:
    path: str
    filename: str
    trading_date: str
    trading_date_iso: str
    modified_time: float
    modified_time_iso: str
    size_bytes: int
    extension: str


class DailyDataManagerV2:
    def __init__(
        self,
        historical_folder: str | Path = DEFAULT_HISTORICAL_FOLDER,
        state_file: str | Path = DEFAULT_STATE_FILE,
        log_file: str | Path = DEFAULT_LOG_FILE,
        supported_extensions: Iterable[str] = SUPPORTED_EXTENSIONS,
        date_column: str = "date",
    ):
        self.historical_folder = Path(historical_folder)
        self.state_file = Path(state_file)
        self.log_file = Path(log_file)
        self.supported_extensions = tuple(
            str(extension).lower().strip()
            for extension in supported_extensions
        )
        self.date_column = date_column

        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        import_to_sqlite: bool = True,
        force_import: bool = False,
    ) -> tuple[pd.DataFrame, dict]:
        started_at = datetime.now()

        try:
            files_df, scan_summary = self.scan_historical_files()

            if files_df.empty:
                summary = self.failed_summary(
                    reason=scan_summary.get(
                        "reason",
                        "No supported historical files found",
                    ),
                    started_at=started_at,
                )
                summary["file_scan"] = scan_summary
                self.write_log(summary)
                return pd.DataFrame(), summary

            latest_record = files_df.iloc[0].to_dict()
            latest_path = Path(latest_record["path"])

            snapshot, parse_summary = self.load_and_validate_file(latest_path)

            if snapshot.empty:
                summary = self.failed_summary(
                    reason=parse_summary.get(
                        "reason",
                        "Latest file could not be parsed",
                    ),
                    started_at=started_at,
                )
                summary["file_scan"] = scan_summary
                summary["latest_file"] = latest_record
                summary["parse_summary"] = parse_summary
                self.write_log(summary)
                return pd.DataFrame(), summary

            resolved_date = parse_summary.get("latest_trading_date")
            resolved_date_iso = parse_summary.get("latest_trading_date_iso")

            state_before = self.load_state()

            duplicate_guard = self.check_duplicate_state(
                state=state_before,
                latest_path=latest_path,
                trading_date_iso=resolved_date_iso,
                record_count=len(snapshot),
            )

            imported = False
            skipped_duplicate = False

            if import_to_sqlite:
                if duplicate_guard["is_duplicate"] and not force_import:
                    skipped_duplicate = True
                    sqlite_result_summary = sqlite_summary()
                else:
                    update_sqlite_database(snapshot)
                    sqlite_result_summary = sqlite_summary()
                    imported = True
            else:
                sqlite_result_summary = sqlite_summary()

            missing_dates = self.detect_missing_recent_dates(
                files_df=files_df,
                latest_date=resolved_date_iso,
                lookback_days=45,
            )

            state_after = {
                "engine_version": ENGINE_VERSION,
                "last_run_timestamp": datetime.now().isoformat(timespec="seconds"),
                "latest_file": str(latest_path.resolve()),
                "latest_filename": latest_path.name,
                "latest_trading_date": resolved_date,
                "latest_trading_date_iso": resolved_date_iso,
                "latest_snapshot_records": int(len(snapshot)),
                "latest_snapshot_symbols": int(
                    snapshot["symbol"].nunique()
                    if "symbol" in snapshot.columns
                    else len(snapshot)
                ),
                "last_import_performed": bool(imported),
                "last_import_skipped_duplicate": bool(skipped_duplicate),
                "latest_file_size_bytes": int(latest_path.stat().st_size),
                "latest_file_modified_time": datetime.fromtimestamp(
                    latest_path.stat().st_mtime
                ).isoformat(timespec="seconds"),
                "sqlite_summary": make_json_safe(sqlite_result_summary),
            }

            self.save_state(state_after)

            completed_at = datetime.now()

            summary = {
                "engine_version": ENGINE_VERSION,
                "status": "success",
                "started_at": started_at.isoformat(timespec="seconds"),
                "completed_at": completed_at.isoformat(timespec="seconds"),
                "duration_seconds": round(
                    (completed_at - started_at).total_seconds(),
                    3,
                ),
                "historical_folder": str(self.historical_folder.resolve()),
                "files_scanned": int(len(files_df)),
                "latest_file": str(latest_path.resolve()),
                "latest_filename": latest_path.name,
                "latest_trading_date": resolved_date,
                "latest_trading_date_iso": resolved_date_iso,
                "latest_snapshot_records": int(len(snapshot)),
                "latest_snapshot_symbols": int(
                    snapshot["symbol"].nunique()
                    if "symbol" in snapshot.columns
                    else len(snapshot)
                ),
                "import_to_sqlite": bool(import_to_sqlite),
                "force_import": bool(force_import),
                "import_performed": bool(imported),
                "duplicate_import_skipped": bool(skipped_duplicate),
                "duplicate_guard": duplicate_guard,
                "missing_recent_trading_dates": missing_dates,
                "missing_recent_trading_dates_count": len(missing_dates),
                "state_file": str(self.state_file.resolve()),
                "log_file": str(self.log_file.resolve()),
                "sqlite_summary": sqlite_result_summary,
                "file_scan": scan_summary,
                "parse_summary": parse_summary,
                "reason": (
                    "Latest daily file resolved successfully"
                    if not skipped_duplicate
                    else "Latest daily file already imported; duplicate import skipped"
                ),
            }

            self.write_log(summary)
            return snapshot, summary

        except Exception as exc:
            summary = self.failed_summary(
                reason=f"Daily Data Manager failed: {exc}",
                started_at=started_at,
            )
            summary["exception_type"] = type(exc).__name__
            summary["traceback"] = traceback.format_exc()
            self.write_log(summary)
            return pd.DataFrame(), summary

    def scan_historical_files(self) -> tuple[pd.DataFrame, dict]:
        if not self.historical_folder.exists():
            return pd.DataFrame(), {
                "status": "failed",
                "reason": f"Historical folder not found: {self.historical_folder}",
                "historical_folder": str(self.historical_folder),
                "files_scanned": 0,
            }

        if not self.historical_folder.is_dir():
            return pd.DataFrame(), {
                "status": "failed",
                "reason": f"Historical path is not a folder: {self.historical_folder}",
                "historical_folder": str(self.historical_folder),
                "files_scanned": 0,
            }

        records: list[HistoricalFileRecord] = []
        unsupported_count = 0
        ignored_name_count = 0
        undated_count = 0
        all_files_seen = 0

        for path in self.historical_folder.rglob("*"):
            if not path.is_file():
                continue

            all_files_seen += 1
            lower_name = path.name.lower()

            # Historical bundle/range archives often contain two dates,
            # for example: 2016-01-07_2026-07-07.zip.
            # They are not daily PSX snapshots and must never be selected.
            if count_date_tokens_in_filename(path.name) != 1:
                undated_count += 1
                continue

            if any(keyword in lower_name for keyword in IGNORED_NAME_KEYWORDS):
                ignored_name_count += 1
                continue

            if not self.is_supported_file(path):
                unsupported_count += 1
                continue

            extracted_date = extract_date_from_market_filename(path.name)

            if extracted_date is None or pd.isna(extracted_date):
                undated_count += 1
                continue

            stat = path.stat()
            trading_date = format_display_date(extracted_date)

            record = HistoricalFileRecord(
                path=str(path.resolve()),
                filename=path.name,
                trading_date=trading_date or extracted_date.strftime("%d%b%Y").upper(),
                trading_date_iso=extracted_date.strftime("%Y-%m-%d"),
                modified_time=float(stat.st_mtime),
                modified_time_iso=datetime.fromtimestamp(
                    stat.st_mtime
                ).isoformat(timespec="seconds"),
                size_bytes=int(stat.st_size),
                extension=detect_extension(path),
            )
            records.append(record)

        if not records:
            return pd.DataFrame(), {
                "status": "failed",
                "reason": (
                    "No dated PSX market files matched. "
                    f"Folder={self.historical_folder.resolve()}, "
                    f"all_files_seen={all_files_seen}, "
                    f"unsupported={unsupported_count}, "
                    f"ignored_names={ignored_name_count}, "
                    f"undated_supported={undated_count}"
                ),
                "historical_folder": str(self.historical_folder.resolve()),
                "all_files_seen": all_files_seen,
                "files_scanned": 0,
                "unsupported_files_skipped": unsupported_count,
                "ignored_name_files": ignored_name_count,
                "files_without_filename_date": undated_count,
                "supported_extensions": list(self.supported_extensions),
            }

        files_df = pd.DataFrame([asdict(record) for record in records])
        files_df["_sort_date"] = pd.to_datetime(
            files_df["trading_date_iso"],
            errors="coerce",
        )

        files_df = (
            files_df.sort_values(
                by=["_sort_date", "modified_time", "filename"],
                ascending=[False, False, False],
                na_position="last",
            )
            .drop(columns=["_sort_date"])
            .reset_index(drop=True)
        )

        summary = {
            "status": "success",
            "historical_folder": str(self.historical_folder.resolve()),
            "all_files_seen": int(all_files_seen),
            "files_scanned": int(len(files_df)),
            "dated_files": int(len(files_df)),
            "files_without_filename_date": int(undated_count),
            "unsupported_files_skipped": int(unsupported_count),
            "ignored_name_files": int(ignored_name_count),
            "oldest_filename_date": files_df["trading_date"].iloc[-1],
            "latest_filename_date": files_df["trading_date"].iloc[0],
            "latest_file": files_df["path"].iloc[0],
            "latest_filename": files_df["filename"].iloc[0],
            "supported_extensions": list(self.supported_extensions),
            "reason": "Historical PSX files scanned successfully",
        }

        return files_df, summary

    def load_and_validate_file(
        self,
        file_path: str | Path,
    ) -> tuple[pd.DataFrame, dict]:
        path = Path(file_path)

        if not path.exists():
            return pd.DataFrame(), {
                "status": "failed",
                "reason": f"File not found: {path}",
            }

        try:
            source_df = read_psx_file(str(path))
        except Exception as exc:
            return pd.DataFrame(), {
                "status": "failed",
                "source_file": str(path.resolve()),
                "reason": f"Parser failed: {exc}",
            }

        source_df = remove_duplicate_columns(source_df)

        if source_df is None or source_df.empty:
            return pd.DataFrame(), {
                "status": "failed",
                "source_file": str(path.resolve()),
                "source_records": 0,
                "reason": "Parser returned an empty DataFrame",
            }

        filename_date = extract_date_from_market_filename(path.name)

        if self.date_column not in source_df.columns:
            if filename_date is None or pd.isna(filename_date):
                return pd.DataFrame(), {
                    "status": "failed",
                    "source_file": str(path.resolve()),
                    "source_records": int(len(source_df)),
                    "reason": "Date column missing and filename has no valid date",
                }

            source_df[self.date_column] = format_display_date(filename_date)

        snapshot, snapshot_summary = get_latest_trading_snapshot(
            source_df,
            date_column=self.date_column,
        )
        snapshot = remove_duplicate_columns(snapshot)

        if snapshot.empty:
            snapshot_summary["source_file"] = str(path.resolve())
            snapshot_summary["source_records"] = int(len(source_df))
            return snapshot, snapshot_summary

        snapshot_date = parse_trading_date(snapshot[self.date_column].iloc[0])

        if filename_date is not None and not pd.isna(filename_date):
            filename_matches = filename_date == snapshot_date
            if not filename_matches:
                snapshot[self.date_column] = format_display_date(filename_date)
                snapshot_date = filename_date
        else:
            filename_matches = None

        snapshot_summary.update(
            {
                "status": "success",
                "source_file": str(path.resolve()),
                "source_filename": path.name,
                "source_records": int(len(source_df)),
                "filename_trading_date": (
                    format_display_date(filename_date)
                    if filename_date is not None and not pd.isna(filename_date)
                    else None
                ),
                "filename_trading_date_iso": (
                    filename_date.strftime("%Y-%m-%d")
                    if filename_date is not None and not pd.isna(filename_date)
                    else None
                ),
                "filename_date_matches_snapshot": filename_matches,
                "latest_trading_date": format_display_date(snapshot_date),
                "latest_trading_date_iso": (
                    snapshot_date.strftime("%Y-%m-%d")
                    if not pd.isna(snapshot_date)
                    else None
                ),
                "latest_snapshot_records": int(len(snapshot)),
                "latest_snapshot_symbols": int(
                    snapshot["symbol"].nunique()
                    if "symbol" in snapshot.columns
                    else len(snapshot)
                ),
                "reason": "Latest daily file parsed and validated",
            }
        )

        return snapshot.reset_index(drop=True), snapshot_summary

    def check_duplicate_state(
        self,
        state: dict,
        latest_path: Path,
        trading_date_iso: str | None,
        record_count: int,
    ) -> dict:
        previous_file = str(state.get("latest_file", "")).strip()
        previous_date = str(state.get("latest_trading_date_iso", "")).strip()
        previous_records = int(state.get("latest_snapshot_records", 0) or 0)
        current_file = str(latest_path.resolve())

        same_file = previous_file.lower() == current_file.lower()
        same_date = bool(trading_date_iso and previous_date == trading_date_iso)
        same_record_count = previous_records == int(record_count)
        is_duplicate = same_date and same_record_count

        return {
            "is_duplicate": bool(is_duplicate),
            "same_file": bool(same_file),
            "same_trading_date": bool(same_date),
            "same_record_count": bool(same_record_count),
            "previous_file": previous_file or None,
            "previous_trading_date_iso": previous_date or None,
            "previous_record_count": previous_records,
            "current_file": current_file,
            "current_trading_date_iso": trading_date_iso,
            "current_record_count": int(record_count),
        }

    def detect_missing_recent_dates(
        self,
        files_df: pd.DataFrame,
        latest_date: str | None,
        lookback_days: int = 45,
    ) -> list[str]:
        if files_df is None or files_df.empty:
            return []

        parsed_latest = parse_trading_date(latest_date)

        if pd.isna(parsed_latest):
            return []

        available_dates = set(
            pd.to_datetime(
                files_df["trading_date_iso"],
                errors="coerce",
            )
            .dropna()
            .dt.normalize()
            .tolist()
        )

        start_date = parsed_latest - timedelta(days=lookback_days)
        expected_weekdays = pd.date_range(
            start=start_date,
            end=parsed_latest,
            freq="B",
        )

        return [
            date.strftime("%Y-%m-%d")
            for date in expected_weekdays
            if date.normalize() not in available_dates
        ]

    def load_state(self) -> dict:
        if not self.state_file.exists():
            return {}

        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save_state(self, state: dict) -> None:
        self.state_file.write_text(
            json.dumps(
                make_json_safe(state),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def write_log(self, summary: dict) -> None:
        line = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "engine_version": ENGINE_VERSION,
            "status": summary.get("status"),
            "latest_filename": summary.get("latest_filename"),
            "latest_trading_date": summary.get("latest_trading_date"),
            "latest_snapshot_records": summary.get("latest_snapshot_records"),
            "import_performed": summary.get("import_performed"),
            "duplicate_import_skipped": summary.get("duplicate_import_skipped"),
            "reason": summary.get("reason"),
        }

        with self.log_file.open("a", encoding="utf-8") as file:
            file.write(
                json.dumps(
                    make_json_safe(line),
                    ensure_ascii=False,
                )
                + "\n"
            )

    def is_supported_file(self, path: Path) -> bool:
        lower_name = path.name.lower()
        return any(
            lower_name.endswith(extension)
            for extension in self.supported_extensions
        )

    def failed_summary(
        self,
        reason: str,
        started_at: datetime,
    ) -> dict:
        completed_at = datetime.now()

        return {
            "engine_version": ENGINE_VERSION,
            "status": "failed",
            "started_at": started_at.isoformat(timespec="seconds"),
            "completed_at": completed_at.isoformat(timespec="seconds"),
            "duration_seconds": round(
                (completed_at - started_at).total_seconds(),
                3,
            ),
            "historical_folder": str(self.historical_folder),
            "latest_file": None,
            "latest_filename": None,
            "latest_trading_date": None,
            "latest_trading_date_iso": None,
            "latest_snapshot_records": 0,
            "latest_snapshot_symbols": 0,
            "import_performed": False,
            "duplicate_import_skipped": False,
            "reason": reason,
        }


def run_daily_data_manager_v2(
    historical_folder: str | Path = DEFAULT_HISTORICAL_FOLDER,
    import_to_sqlite: bool = True,
    force_import: bool = False,
    state_file: str | Path = DEFAULT_STATE_FILE,
    log_file: str | Path = DEFAULT_LOG_FILE,
) -> tuple[pd.DataFrame, dict]:
    manager = DailyDataManagerV2(
        historical_folder=historical_folder,
        state_file=state_file,
        log_file=log_file,
    )
    return manager.run(
        import_to_sqlite=import_to_sqlite,
        force_import=force_import,
    )


def get_latest_daily_snapshot_v2(
    historical_folder: str | Path = DEFAULT_HISTORICAL_FOLDER,
) -> tuple[pd.DataFrame, dict]:
    manager = DailyDataManagerV2(historical_folder=historical_folder)
    return manager.run(
        import_to_sqlite=False,
        force_import=False,
    )


def scan_historical_files_v2(
    historical_folder: str | Path = DEFAULT_HISTORICAL_FOLDER,
) -> tuple[pd.DataFrame, dict]:
    manager = DailyDataManagerV2(historical_folder=historical_folder)
    return manager.scan_historical_files()



def count_date_tokens_in_filename(filename: str) -> int:
    text = str(filename).upper().strip()

    token_patterns = (
        r"(?<!\d)(?:19|20)\d{6}(?!\d)",
        r"(?<!\d)\d{2}[A-Z]{3}\d{4}(?![A-Z0-9])",
        r"(?<!\d)(?:19|20)\d{2}[-_]\d{2}[-_]\d{2}(?!\d)",
        r"(?<!\d)\d{2}[-_]\d{2}[-_](?:19|20)\d{2}(?!\d)",
    )

    matches: list[str] = []

    for pattern in token_patterns:
        matches.extend(re.findall(pattern, text))

    return len(matches)



def extract_date_from_market_filename(filename: str) -> pd.Timestamp | None:
    text = str(filename).upper().strip()

    # Accept only one unambiguous trading date in a daily filename.
    # Range archives containing a start and end date are intentionally rejected.
    if count_date_tokens_in_filename(filename) != 1:
        return None

    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text)
        if not match:
            continue

        groups = match.groups()

        try:
            if len(groups) == 1:
                value = groups[0]
                if re.fullmatch(r"\d{8}", value):
                    if value.startswith(("19", "20")):
                        return pd.Timestamp(datetime.strptime(value, "%Y%m%d"))
                return parse_trading_date(value)

            if len(groups) == 3:
                first, second, third = groups

                if len(first) == 4:
                    value = f"{first}-{second}-{third}"
                    return pd.Timestamp(datetime.strptime(value, "%Y-%m-%d"))

                value = f"{first}-{second}-{third}"
                return pd.Timestamp(datetime.strptime(value, "%d-%m-%Y"))

        except (ValueError, TypeError):
            continue

    return None


def detect_extension(path: Path) -> str:
    lower_name = path.name.lower()

    if lower_name.endswith(".lis.z"):
        return ".lis.z"
    if lower_name.endswith(".zip"):
        return ".zip"
    if lower_name.endswith(".z"):
        return ".z"
    if lower_name.endswith(".lis"):
        return ".lis"

    return path.suffix.lower()


def make_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(item) for item in value]

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")

    if isinstance(value, pd.Series):
        return value.to_dict()

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    return value