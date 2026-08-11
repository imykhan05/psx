"""
PSX end-of-day market-summary downloader.

Downloads the official closing-summary `.Z` (a ZIP containing `closing11.lis`)
from the PSX Data Portal into
    database/historical_files/<year>/<YYYY-MM-DD>_mkt_summary.Z
— the exact path and filename the pipeline already reads.

It uses a plain HTTPS GET with a browser-like Referer/User-Agent (verified to
work — no headless browser needed), which makes it safe to run head-less from a
6 PM scheduler. Rules:
  - Weekends are skipped.
  - Files already present (and non-trivial in size) are skipped.
  - PSX holidays / not-yet-published days return HTTP 404 -> recorded as
    "missing" (NOT an error).
  - Only a real ZIP payload (magic bytes `PK`) is written to disk, so an error
    page can never masquerade as data.

Usage:
    python tools/download_eod.py                  # catch up: last file -> today
    python tools/download_eod.py --date 2026-07-24
    python tools/download_eod.py --from 2026-07-24 --to 2026-08-11
"""

from __future__ import annotations

import argparse
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HIST_DIR = PROJECT_ROOT / "database" / "historical_files"
LOG_FILE = PROJECT_ROOT / "logs" / "eod_download.log"

URL_TEMPLATE = "https://dps.psx.com.pk/download/mkt_summary/{date}.Z"
REFERER = "https://dps.psx.com.pk/downloads"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().isoformat(timespec="seconds")
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"{stamp}  {msg}\n")
    print(f"[eod] {msg}")


def save_path(d: date) -> Path:
    return HIST_DIR / str(d.year) / f"{d.isoformat()}_mkt_summary.Z"


def latest_existing_date() -> date | None:
    """Newest date already downloaded (across all year folders)."""
    latest: date | None = None
    for p in HIST_DIR.glob("*/*_mkt_summary.Z"):
        stem = p.name.split("_")[0]
        try:
            d = datetime.strptime(stem, "%Y-%m-%d").date()
        except ValueError:
            continue
        if latest is None or d > latest:
            latest = d
    return latest


def download_one(d: date) -> str:
    """Return: ok | skip | missing | empty | http_<code> | error."""
    sp = save_path(d)
    if sp.exists() and sp.stat().st_size > 100:
        return "skip"

    req = urllib.request.Request(
        URL_TEMPLATE.format(date=d.isoformat()),
        headers={"Referer": REFERER, "User-Agent": USER_AGENT, "Accept": "*/*"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        return "missing" if exc.code == 404 else f"http_{exc.code}"
    except Exception as exc:  # network error, timeout, etc.
        return f"error:{type(exc).__name__}"

    # Guard: only save a genuine ZIP payload, never an HTML error page.
    if len(data) < 100 or data[:2] != b"PK":
        return "empty"

    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_bytes(data)
    return "ok"


def trading_days(start: date, end: date):
    d = start
    while d <= end:
        if d.weekday() < 5:  # Mon-Fri
            yield d
        d += timedelta(days=1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download PSX EOD market-summary files.")
    parser.add_argument("--date", help="Single date YYYY-MM-DD.")
    parser.add_argument("--from", dest="from_date", help="Start date YYYY-MM-DD.")
    parser.add_argument("--to", dest="to_date", help="End date YYYY-MM-DD.")
    parser.add_argument("--delay", type=float, default=0.6, help="Seconds between requests.")
    args = parser.parse_args()

    if args.date:
        start = end = datetime.strptime(args.date, "%Y-%m-%d").date()
    elif args.from_date and args.to_date:
        start = datetime.strptime(args.from_date, "%Y-%m-%d").date()
        end = datetime.strptime(args.to_date, "%Y-%m-%d").date()
    else:
        # Default: catch up from the day after the newest file we have, to today.
        last = latest_existing_date()
        end = date.today()
        if last is None:
            _log("no existing files found; specify --from/--to for a first bulk fetch.")
            return 1
        start = last + timedelta(days=1)
        if start > end:
            _log(f"already up to date (latest file: {last.isoformat()}).")
            return 0

    _log(f"downloading {start.isoformat()} -> {end.isoformat()}")
    tally = {"ok": 0, "skip": 0, "missing": 0, "empty": 0, "error": 0}
    for d in trading_days(start, end):
        result = download_one(d)
        key = "error" if result.startswith(("error", "http_")) else result
        tally[key] = tally.get(key, 0) + 1
        if result == "ok":
            _log(f"{d.isoformat()}  OK ({save_path(d).stat().st_size} bytes)")
        elif result == "missing":
            _log(f"{d.isoformat()}  missing (holiday / not published)")
        elif result != "skip":
            _log(f"{d.isoformat()}  {result}")
        time.sleep(args.delay)

    _log(
        "summary: "
        + ", ".join(f"{k}={v}" for k, v in tally.items())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
