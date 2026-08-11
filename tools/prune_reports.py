"""
Prune old timestamped scanner run-folders under reports/.

Each scanner run writes a folder like:
    reports/TRADING_2026-07-13__RUN_2026-07-20_17-24-00/
    reports/2026-07-10_16-10-38/
    reports/30JUN2026/
These accumulate indefinitely. This script keeps only the newest N run-folders
(by modification time) and removes the rest.

SAFETY: it only ever touches folders that look like a dated run-folder. It never
deletes:
- reports/latest/                     (the live snapshot the terminal reads)
- the named category folders          (market_breadth/, smart_money/, alerts/,
                                        dashboard/, ai_assistant/, backtests/, …)
- any file directly under reports/

Usage:
    python tools/prune_reports.py            # dry-run: shows what would be deleted
    python tools/prune_reports.py --apply    # actually delete
    python tools/prune_reports.py --keep 20  # keep newest 20 instead of 10
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

DEFAULT_KEEP = 10

# A folder is a prunable run-folder only if its name matches one of these.
RUN_FOLDER_PATTERNS = (
    re.compile(r"^TRADING_.*__RUN_.*$"),          # TRADING_2026-07-13__RUN_2026-07-20_17-24-00
    re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$"),  # 2026-07-10_16-10-38
    re.compile(r"^\d{2}[A-Z]{3}\d{4}$"),          # 30JUN2026
)

# Never delete these, even if a pattern somehow matched.
PROTECTED_NAMES = {"latest"}


def is_run_folder(path: Path) -> bool:
    if not path.is_dir():
        return False
    if path.name in PROTECTED_NAMES:
        return False
    return any(pattern.match(path.name) for pattern in RUN_FOLDER_PATTERNS)


def find_run_folders(reports_dir: Path) -> list[Path]:
    if not reports_dir.exists():
        return []
    folders = [p for p in reports_dir.iterdir() if is_run_folder(p)]
    # Newest first by modification time.
    folders.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return folders


def prune(reports_dir: Path, keep: int, apply: bool) -> dict:
    folders = find_run_folders(reports_dir)
    keep_list = folders[:keep]
    delete_list = folders[keep:]

    print(f"Reports dir      : {reports_dir}")
    print(f"Run-folders found: {len(folders)}")
    print(f"Keeping newest   : {len(keep_list)}")
    print(f"To remove        : {len(delete_list)}")
    print()

    if not delete_list:
        print("Nothing to prune.")
        return {"found": len(folders), "kept": len(keep_list), "removed": 0}

    for folder in delete_list:
        if apply:
            shutil.rmtree(folder)
            print(f"  removed  {folder.name}")
        else:
            print(f"  [dry-run] would remove  {folder.name}")

    if not apply:
        print()
        print("Dry-run only. Re-run with --apply to delete.")

    return {
        "found": len(folders),
        "kept": len(keep_list),
        "removed": len(delete_list) if apply else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune old scanner run-folders.")
    parser.add_argument(
        "--keep",
        type=int,
        default=DEFAULT_KEEP,
        help=f"How many newest run-folders to keep (default {DEFAULT_KEEP}).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete. Without this flag the script only reports.",
    )
    parser.add_argument(
        "--reports-dir",
        default=str(REPORTS_DIR),
        help="Override the reports directory.",
    )
    args = parser.parse_args()

    prune(Path(args.reports_dir), keep=max(args.keep, 0), apply=args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
