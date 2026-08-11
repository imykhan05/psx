from pathlib import Path

import pandas as pd

from app.core.parser import read_psx_file
from app.core.sqlite_database import update_sqlite_database


HISTORICAL_FOLDER = Path("database/historical_files")
BACKFILL_LOG_FILE = Path("database/historical_backfill_log.csv")


def run_historical_backfill(folder: str | Path = HISTORICAL_FOLDER) -> dict:
    """
    Historical Backfill Engine V2

    Supports year-wise / nested folders:
    database/historical_files/2024/
    database/historical_files/2025/
    database/historical_files/2026/

    Supported:
    - .csv
    - .lis
    - .Z
    - .z
    - .lis.Z
    """

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    files = collect_history_files(folder)

    if not files:
        return {
            "status": "no_files_found",
            "folder": str(folder),
            "files_found": 0,
            "files_processed": 0,
            "files_failed": 0,
            "records_loaded": 0,
            "message": "Put old PSX daily files inside database/historical_files and run again.",
        }

    logs = []
    total_records = 0
    processed = 0
    failed = 0
    empty = 0

    for index, file_path in enumerate(files, start=1):
        print(f"[BACKFILL] {index}/{len(files)} Processing: {file_path}")

        try:
            df = read_history_file(file_path)

            if df.empty:
                empty += 1
                logs.append(log_row(file_path, "empty", 0, "No records found"))
                continue

            df = normalize_backfill_frame(df, file_path)

            update_sqlite_database(df)

            processed += 1
            total_records += len(df)

            logs.append(log_row(file_path, "processed", len(df), ""))

        except Exception as exc:
            failed += 1
            logs.append(log_row(file_path, "failed", 0, str(exc)))
            print(f"[BACKFILL ERROR] {file_path}: {exc}")

    write_backfill_log(logs)

    return {
        "status": "completed",
        "folder": str(folder),
        "files_found": len(files),
        "files_processed": processed,
        "files_empty": empty,
        "files_failed": failed,
        "records_loaded": total_records,
        "log_file": str(BACKFILL_LOG_FILE),
    }


def collect_history_files(folder: Path) -> list[Path]:
    supported_suffixes = [".csv", ".lis", ".z"]

    files = []

    for file_path in folder.rglob("*"):
        if not file_path.is_file():
            continue

        name = file_path.name.lower()

        if file_path.suffix.lower() in supported_suffixes:
            files.append(file_path)
            continue

        if name.endswith(".lis.z"):
            files.append(file_path)
            continue

    return sorted(files)


def read_history_file(file_path: Path) -> pd.DataFrame:
    suffix = file_path.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(file_path)

    return read_psx_file(str(file_path))


def normalize_backfill_frame(df: pd.DataFrame, file_path: Path) -> pd.DataFrame:
    result = df.copy()

    if "symbol" not in result.columns:
        raise ValueError("Missing symbol column")

    if "date" not in result.columns:
        extracted_date = extract_date_from_filename(file_path.name)

        if extracted_date is None:
            extracted_date = extract_date_from_path(file_path)

        if extracted_date is None:
            raise ValueError("Missing date column and date could not be extracted from filename/path")

        result["date"] = extracted_date

    result["symbol"] = result["symbol"].astype(str).str.strip().str.upper()
    result["date"] = result["date"].astype(str).str.strip().str.upper()

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "change",
        "change_pct",
        "volume",
    ]

    for col in numeric_columns:
        if col not in result.columns:
            result[col] = 0

        result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0)

    if "company" not in result.columns:
        result["company"] = ""

    return result


def extract_date_from_filename(filename: str) -> str | None:
    """
    Supports:
    20260707_new.lis.Z
    20260707.lis
    07JUL2026.lis
    30JUN2026
    """

    name = filename.upper()
    tokens = name.replace("-", "_").replace(".", "_").replace(" ", "_").split("_")

    for token in tokens:
        token = token.strip()

        if len(token) == 8 and token.isdigit():
            parsed = pd.to_datetime(token, format="%Y%m%d", errors="coerce")
            if pd.notna(parsed):
                return parsed.strftime("%d%b%Y").upper()

        if len(token) == 9:
            parsed = pd.to_datetime(token, format="%d%b%Y", errors="coerce")
            if pd.notna(parsed):
                return parsed.strftime("%d%b%Y").upper()

    return None


def extract_date_from_path(file_path: Path) -> str | None:
    """
    Extra fallback for folder structures.
    Example:
    database/historical_files/2026/20260707_new.lis.Z
    """

    for part in reversed(file_path.parts):
        extracted = extract_date_from_filename(part)
        if extracted:
            return extracted

    return None


def log_row(file_path: Path, status: str, records: int, error: str) -> dict:
    return {
        "file": str(file_path),
        "status": status,
        "records": records,
        "error": error,
    }


def write_backfill_log(logs: list[dict]) -> None:
    BACKFILL_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(logs).to_csv(BACKFILL_LOG_FILE, index=False)