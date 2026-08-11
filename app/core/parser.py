from __future__ import annotations

import bz2
import gzip
import io
import lzma
import zipfile
from pathlib import Path

import pandas as pd

from config import FUTURE_MONTHS


COLUMN_NAMES = [
    "date",
    "symbol",
    "code",
    "company",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "prev_close",
    "x1",
    "x2",
    "x3",
]

REQUIRED_COLUMNS = [
    "date",
    "symbol",
    "code",
    "company",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "prev_close",
]


def read_psx_file(file_path: str) -> pd.DataFrame:
    """
    Read PSX daily market files safely.

    Supported formats:
    - ZIP archive
    - GZIP archive
    - BZ2 archive
    - XZ/LZMA archive
    - UNIX .Z compressed file, when unlzw3 is installed
    - Plain-text .lis file
    - Plain-text file incorrectly named .lis.Z
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"PSX file not found: {path}")

    if not path.is_file():
        raise ValueError(f"PSX path is not a file: {path}")

    raw_data = path.read_bytes()

    if not raw_data:
        raise ValueError(f"PSX file is empty: {path}")

    decompressed_data, detected_format = _decompress_file(
        raw_data=raw_data,
        file_path=path,
    )

    df = _read_pipe_separated_data(
        decompressed_data,
        source_name=path.name,
        detected_format=detected_format,
    )

    df = _clean_psx_dataframe(df)

    if df.empty:
        raise ValueError(
            f"PSX parser returned no valid market records from: {path}"
        )

    return df


def _decompress_file(
    raw_data: bytes,
    file_path: Path,
) -> tuple[bytes, str]:
    """
    Detect format using file signatures rather than extension only.
    """

    # ZIP signature:
    # PK\x03\x04, PK\x05\x06, PK\x07\x08
    if raw_data.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        return _read_zip_bytes(raw_data, file_path), "ZIP"

    # GZIP signature: 1F 8B
    if raw_data.startswith(b"\x1f\x8b"):
        try:
            return gzip.decompress(raw_data), "GZIP"
        except Exception as exc:
            raise ValueError(
                f"Failed to decompress GZIP file {file_path.name}: {exc}"
            ) from exc

    # UNIX compress .Z signature: 1F 9D
    if raw_data.startswith(b"\x1f\x9d"):
        return _read_unix_compress_z(raw_data, file_path), "UNIX_Z"

    # BZIP2 signature: BZh
    if raw_data.startswith(b"BZh"):
        try:
            return bz2.decompress(raw_data), "BZIP2"
        except Exception as exc:
            raise ValueError(
                f"Failed to decompress BZIP2 file {file_path.name}: {exc}"
            ) from exc

    # XZ signature: FD 37 7A 58 5A 00
    if raw_data.startswith(b"\xfd7zXZ\x00"):
        try:
            return lzma.decompress(raw_data), "XZ_LZMA"
        except Exception as exc:
            raise ValueError(
                f"Failed to decompress XZ/LZMA file {file_path.name}: {exc}"
            ) from exc

    # Some PSX files have .lis.Z extension but contain normal text.
    if _looks_like_text(raw_data):
        return raw_data, "PLAIN_TEXT"

    raise ValueError(
        f"Unsupported or corrupted PSX file format: {file_path}. "
        f"Header bytes: {raw_data[:8].hex(' ')}"
    )


def _read_zip_bytes(
    raw_data: bytes,
    file_path: Path,
) -> bytes:
    try:
        with zipfile.ZipFile(io.BytesIO(raw_data)) as archive:
            members = [
                member
                for member in archive.namelist()
                if not member.endswith("/")
            ]

            if not members:
                raise ValueError("ZIP archive contains no files")

            preferred_members = [
                member
                for member in members
                if member.lower().endswith(
                    (
                        ".lis",
                        ".txt",
                        ".csv",
                        ".dat",
                    )
                )
            ]

            selected_member = (
                preferred_members[0]
                if preferred_members
                else members[0]
            )

            return archive.read(selected_member)

    except zipfile.BadZipFile as exc:
        raise ValueError(
            f"Invalid ZIP archive: {file_path.name}"
        ) from exc


def _read_unix_compress_z(
    raw_data: bytes,
    file_path: Path,
) -> bytes:
    """
    Real UNIX .Z compressed files require LZW decompression.

    Install once with:
        pip install unlzw3
    """

    try:
        from unlzw3 import unlzw
    except ImportError as exc:
        raise ValueError(
            f"{file_path.name} is a genuine UNIX .Z compressed file. "
            f"Install its decoder once using: pip install unlzw3"
        ) from exc

    try:
        return unlzw(raw_data)
    except Exception as exc:
        raise ValueError(
            f"Failed to decompress UNIX .Z file {file_path.name}: {exc}"
        ) from exc


def _looks_like_text(raw_data: bytes) -> bool:
    sample = raw_data[:4096]

    if not sample:
        return False

    if b"\x00" in sample:
        return False

    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            decoded = sample.decode(encoding)

            if "|" in decoded:
                return True

            printable = sum(
                character.isprintable()
                or character in "\r\n\t"
                for character in decoded
            )

            if printable / max(len(decoded), 1) >= 0.90:
                return True

        except UnicodeDecodeError:
            continue

    return False


def _decode_text(raw_data: bytes) -> str:
    encodings = (
        "utf-8-sig",
        "utf-8",
        "cp1252",
        "latin-1",
    )

    for encoding in encodings:
        try:
            return raw_data.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise ValueError(
        "Could not decode PSX market file using supported text encodings."
    )


def _read_pipe_separated_data(
    raw_data: bytes,
    source_name: str,
    detected_format: str,
) -> pd.DataFrame:
    text = _decode_text(raw_data)

    text = text.replace("\x00", "").strip()

    if not text:
        raise ValueError(
            f"Decompressed PSX file is empty: {source_name}"
        )

    first_non_empty_line = next(
        (
            line
            for line in text.splitlines()
            if line.strip()
        ),
        "",
    )

    if "|" not in first_non_empty_line:
        raise ValueError(
            f"PSX file does not appear pipe-separated. "
            f"Source: {source_name}, format: {detected_format}"
        )

    try:
        df = pd.read_csv(
            io.StringIO(text),
            sep="|",
            header=None,
            names=COLUMN_NAMES,
            usecols=range(len(COLUMN_NAMES)),
            dtype=str,
            engine="python",
            on_bad_lines="skip",
        )
    except Exception as exc:
        raise ValueError(
            f"Failed to parse PSX pipe-separated data from "
            f"{source_name}: {exc}"
        ) from exc

    return df


def _clean_psx_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    result = df.copy()

    result = result[REQUIRED_COLUMNS]

    text_columns = [
        "date",
        "symbol",
        "code",
        "company",
    ]

    for column in text_columns:
        result[column] = (
            result[column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    result["symbol"] = result["symbol"].str.upper()

    # Remove accidental header rows.
    result = result[
        result["symbol"].ne("SYMBOL")
        & result["date"].str.upper().ne("DATE")
    ].copy()

    # Remove futures contracts using configured month codes.
    for month in FUTURE_MONTHS:
        month_text = str(month).upper().strip()

        if month_text:
            result = result[
                ~result["symbol"].str.contains(
                    month_text,
                    case=False,
                    na=False,
                    regex=False,
                )
            ]

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "prev_close",
    ]

    for column in numeric_columns:
        result[column] = pd.to_numeric(
            result[column]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.strip(),
            errors="coerce",
        )

    result["date_parsed"] = _parse_date_column(
        result["date"]
    )

    result = result.dropna(
        subset=[
            "date_parsed",
            "symbol",
            "close",
            "volume",
            "prev_close",
        ]
    )

    result = result[
        result["symbol"].ne("")
        & result["company"].ne("")
        & result["close"].gt(0)
        & result["prev_close"].gt(0)
        & result["volume"].gt(0)
    ].copy()

    # Normalize date format throughout the system.
    result["date"] = (
        result["date_parsed"]
        .dt.strftime("%d%b%Y")
        .str.upper()
    )

    result["change"] = (
        result["close"] - result["prev_close"]
    )

    result["change_pct"] = (
        result["change"]
        / result["prev_close"]
        * 100
    )

    price_range = (
        result["high"] - result["low"]
    ).abs()

    price_range = price_range.mask(
        price_range.eq(0),
        0.01,
    )

    result["close_position"] = (
        (
            result["close"] - result["low"]
        )
        / price_range
        * 100
    ).clip(
        lower=0,
        upper=100,
    )

    result = result.drop_duplicates(
        subset=[
            "date",
            "symbol",
        ],
        keep="last",
    )

    result = result.sort_values(
        by=[
            "date_parsed",
            "symbol",
        ],
        ascending=[
            True,
            True,
        ],
    ).reset_index(drop=True)

    return result


def _parse_date_column(
    date_series: pd.Series,
) -> pd.Series:
    cleaned = (
        date_series
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    parsed = pd.to_datetime(
        cleaned,
        format="%d%b%Y",
        errors="coerce",
    )

    missing_mask = parsed.isna()

    if missing_mask.any():
        fallback = pd.to_datetime(
            cleaned[missing_mask],
            errors="coerce",
            dayfirst=True,
        )

        parsed.loc[missing_mask] = fallback

    return parsed