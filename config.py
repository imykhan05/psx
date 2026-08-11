from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DATABASE_DIR = BASE_DIR / "database"

# All project data lives under database/. DATA_DIR is kept as an alias of
# DATABASE_DIR for backward compatibility: the former separate root data/ tree
# was consolidated into database/ (ROADMAP.md F0.4).
DATA_DIR = DATABASE_DIR
RAW_DATA_DIR = DATABASE_DIR / "raw"
REPORTS_DIR = BASE_DIR / "reports"
LOGS_DIR = BASE_DIR / "logs"

# Full cleaned history kept in sync with psx_terminal.db (2016-08-01 onward).
# The old 5-day psx_history.csv was stale; psx_history_clean.csv is the real one.
HISTORY_CSV = DATABASE_DIR / "psx_history_clean.csv"

MAX_PRICE_DEFAULT = 500
CAPITAL_DEFAULT = 50000

FUTURE_MONTHS = [
    "-JAN", "-FEB", "-MAR", "-APR", "-MAY", "-JUN",
    "-JUL", "-AUG", "-SEP", "-OCT", "-NOV", "-DEC"
]