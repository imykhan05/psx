from pathlib import Path

import pandas as pd

from app.core.parser import read_psx_file
from app.core.sqlite_database import update_sqlite_database


HISTORICAL_FOLDER = Path("database/historical_files")
DAILY_IMPORT_LOG_FILE = Path("database/daily_import_log.csv")


def import_latest_daily_file(folder: str | Path = HISTORICAL_FOLDER) -> dict:
    """
    Daily Import Engine V1.1

    Imports only the latest PSX daily file from historical_files.
    Does NOT re-process all old files.
    """

    folder = Path(folder)
    latest_file = find_latest_history_file(folder)

    if latest_file is None:
        return {
            "status": "no_file_found",
            "folder": str(folder),
            "file": None,
            "records": 0,
        }

    return import_daily_file(latest_file)


def import_daily_file(file_path: str | Path) -> dict:
    file_path = Path(file_path)

    try:
        df = read_daily_file(file_path)

        if df.empty:
            write_daily_import_log(file_path, "empty", 0, "No records found")
            return {
                "status": "empty",
                "file": str(file_path),
                "records": 0,
            }

        df = normalize_daily_frame(df, file_path)
        history = update_sqlite_database(df)

        write_daily_import_log(file_path, "imported", len(df), "")

        return {
            "status": "imported",
            "file": str(file_path),
            "records": len(df),
            "total_history_records": len(history),
        }

    except Exception as exc:
        write_daily_import_log(file_path, "failed", 0, str(exc))
        return {
            "status": "failed",
            "file": str(file_path),
            "records": 0,
            "error": str(exc),
        }


def find_latest_history_file(folder: Path) -> Path | None:
    supported = []

    for file_path in folder.rglob("*"):
        if not file_path.is_file():
            continue

        name = file_path.name.lower()

        if (
            name.endswith(".csv")
            or name.endswith(".lis")
            or name.endswith(".z")
            or name.endswith(".lis.z")
        ):
            supported.append(file_path)

    if not supported:
        return None

    supported = sorted(
        supported,
        key=get_file_sort_key,
        reverse=True,
    )

    return supported[0]


def get_file_sort_key(file_path: Path) -> float:
    extracted = extract_date_from_filename(file_path.name)

    if extracted is not None:
        parsed = pd.to_datetime(extracted, format="%d%b%Y", errors="coerce")

        if pd.notna(parsed):
            return parsed.timestamp()

    return file_path.stat().st_mtime


def extract_sort_date(file_path: Path):
    extracted = extract_date_from_filename(file_path.name)

    if extracted is None:
        return None

    parsed = pd.to_datetime(extracted, format="%d%b%Y", errors="coerce")

    if pd.isna(parsed):
        return None

    return parsed.to_pydatetime()


def read_daily_file(file_path: Path) -> pd.DataFrame:
    if file_path.suffix.lower() == ".csv":
        return pd.read_csv(file_path)

    return read_psx_file(str(file_path))


def normalize_daily_frame(df: pd.DataFrame, file_path: Path) -> pd.DataFrame:
    result = df.copy()

    if "symbol" not in result.columns:
        raise ValueError("Missing symbol column")

    if "date" not in result.columns:
        extracted_date = extract_date_from_filename(file_path.name)

        if extracted_date is None:
            raise ValueError("Missing date column and date could not be extracted from filename")

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
    name = filename.upper()

    # First try full filename patterns directly
    direct_patterns = [
        ("%Y-%m-%d", 10),
        ("%Y%m%d", 8),
        ("%d%b%Y", 9),
    ]

    clean_name = (
        name.replace("_MKT_SUMMARY", "")
        .replace("_NEW", "")
        .replace(".LIS.Z", "")
        .replace(".LIS", "")
        .replace(".CSV", "")
        .replace(".Z", "")
    )

    for fmt, length in direct_patterns:
        candidate = clean_name[:length]

        if len(candidate) == length:
            parsed = pd.to_datetime(candidate, format=fmt, errors="coerce")

            if pd.notna(parsed):
                return parsed.strftime("%d%b%Y").upper()

    # Then try tokens
    tokens = name.replace("-", "_").replace(".", "_").replace(" ", "_").split("_")

    for token in tokens:
        token = token.strip()

        if len(token) == 8 and token.isdigit():
            parsed = pd.to_datetime(token, format="%Y%m%d", errors="coerce")
            if pd.notna(parsed):
                return parsed.strftime("%d%b%Y").upper()

        if len(token) == 10:
            parsed = pd.to_datetime(token, format="%Y-%m-%d", errors="coerce")
            if pd.notna(parsed):
                return parsed.strftime("%d%b%Y").upper()

        if len(token) == 9:
            parsed = pd.to_datetime(token, format="%d%b%Y", errors="coerce")
            if pd.notna(parsed):
                return parsed.strftime("%d%b%Y").upper()

    return None


def write_daily_import_log(file_path: Path, status: str, records: int, error: str):
    DAILY_IMPORT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    row = {
        "file": str(file_path),
        "status": status,
        "records": records,
        "error": error,
    }

    if DAILY_IMPORT_LOG_FILE.exists():
        old = pd.read_csv(DAILY_IMPORT_LOG_FILE)
        new = pd.concat([old, pd.DataFrame([row])], ignore_index=True)
    else:
        new = pd.DataFrame([row])

    new.to_csv(DAILY_IMPORT_LOG_FILE, index=False)