import sqlite3
from pathlib import Path

import pandas as pd

from config import DATABASE_DIR, HISTORY_CSV


SQLITE_DB_PATH = DATABASE_DIR / "psx_terminal.db"


def get_connection():
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(SQLITE_DB_PATH)


def initialize_database():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS daily_prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        symbol TEXT NOT NULL,
        code INTEGER,
        company TEXT,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume INTEGER,
        prev_close REAL,
        date_parsed TEXT,
        change REAL,
        change_pct REAL,
        close_position REAL,
        UNIQUE(date, symbol)
    )
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_daily_symbol_date
    ON daily_prices(symbol, date_parsed)
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_daily_date
    ON daily_prices(date)
    """)

    conn.commit()
    conn.close()


def save_daily_prices(df: pd.DataFrame):
    initialize_database()

    conn = get_connection()
    cur = conn.cursor()

    for _, row in df.iterrows():
        cur.execute("""
        INSERT OR REPLACE INTO daily_prices (
            date, symbol, code, company,
            open, high, low, close,
            volume, prev_close, date_parsed,
            change, change_pct, close_position
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(row.get("date")),
            str(row.get("symbol")),
            (
                int(row.get("code"))
                if pd.notna(row.get("code")) and str(row.get("code")).strip() != ""
                else None
            ),
            str(row.get("company")),
            float(row.get("open")),
            float(row.get("high")),
            float(row.get("low")),
            float(row.get("close")),
            int(row.get("volume")),
            float(row.get("prev_close")),
            str(row.get("date_parsed")),
            float(row.get("change")),
            float(row.get("change_pct")),
            float(row.get("close_position")),
        ))

    conn.commit()
    conn.close()


def import_csv_history_to_sqlite(csv_path: Path = HISTORY_CSV):
    if not csv_path.exists():
        raise FileNotFoundError(f"History CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    save_daily_prices(df)

    return len(df)


def load_history_from_sqlite() -> pd.DataFrame:
    initialize_database()

    conn = get_connection()

    df = pd.read_sql_query("""
        SELECT
            date, symbol, code, company,
            open, high, low, close,
            volume, prev_close, date_parsed,
            change, change_pct, close_position
        FROM daily_prices
        ORDER BY symbol, date_parsed
    """, conn)

    conn.close()

    if not df.empty:
        df["date_parsed"] = pd.to_datetime(df["date_parsed"], errors="coerce")

    return df


def update_sqlite_database(today_df: pd.DataFrame) -> pd.DataFrame:
    save_daily_prices(today_df)
    return load_history_from_sqlite()


def sqlite_summary():
    initialize_database()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM daily_prices")
    total_records = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT date) FROM daily_prices")
    total_days = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT symbol) FROM daily_prices")
    total_symbols = cur.fetchone()[0]

    conn.close()

    return {
        "database": str(SQLITE_DB_PATH),
        "total_records": total_records,
        "total_days": total_days,
        "total_symbols": total_symbols,
    }