"""
Standalone news-sentiment refresher (Priority 1, item 1).

Runs the news sentiment engine on its own schedule (e.g. twice a day via cron /
Windows Task Scheduler) and writes database/ai_learning/sentiment_cache.json.
This keeps the heavy transformer model OFF the API and normal-scan paths — the
API and the daily-signal engine only ever *read* the cache this produces.

Behaviour designed for unattended scheduled runs:
- A lock file prevents an overlapping run from stampeding the ~500MB model load.
- Every run appends a timestamped line to logs/sentiment_refresh.log.
- Exit 0 on success OR graceful cache-fallback (feeds down, last cache kept);
  non-zero only on an unexpected crash, so the scheduler's failure flag means
  something real.

Usage:
    python tools/refresh_sentiment.py             # refresh the cache
    python tools/refresh_sentiment.py --publish   # then git-commit + push it
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

LOCK_FILE = PROJECT_ROOT / "database" / "ai_learning" / ".sentiment.lock"
LOG_FILE = PROJECT_ROOT / "logs" / "sentiment_refresh.log"
STALE_LOCK_SECONDS = 20 * 60  # a lock older than this is treated as abandoned


def _log(line: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"{stamp}  {line}\n")
    print(f"[refresh_sentiment] {line}")


def _acquire_lock() -> bool:
    """Return True if we hold the lock, False if a fresh run is already active."""
    if LOCK_FILE.exists():
        age = time.time() - LOCK_FILE.stat().st_mtime
        if age < STALE_LOCK_SECONDS:
            _log(f"skip: another refresh is in progress (lock age {age:.0f}s)")
            return False
        _log(f"overriding stale lock (age {age:.0f}s)")
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(str(datetime.now(timezone.utc)), encoding="utf-8")
    return True


def _release_lock() -> None:
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _publish() -> None:
    """Best-effort git-commit-on-refresh of the fresh cache. Never fatal."""
    try:
        from tools.publish_outputs import publish

        rc = publish(push=True)
        _log(f"publish returned {rc}")
    except Exception as exc:
        _log(f"publish skipped (non-fatal): {type(exc).__name__}: {exc}")


def main(publish: bool = False) -> int:
    if not _acquire_lock():
        return 0  # not an error — a concurrent run owns it

    try:
        from app.engines.news_sentiment_engine_v1 import (
            run_news_sentiment_engine,
            sentiment_summary,
        )

        started = time.time()
        payload = run_news_sentiment_engine()
        elapsed = time.time() - started
        summary = sentiment_summary(payload)

        source = summary.get("source")
        _log(
            f"done in {elapsed:.0f}s | source={source} "
            f"headlines={summary.get('headline_count')} "
            f"matched={summary.get('matched_headlines')} "
            f"tickers={summary.get('tickers_with_news')} "
            f"model={'ok' if summary.get('model_available') else 'unavailable'}"
        )

        if source == "empty":
            # No fresh headlines AND no cache to fall back to — soft failure.
            _log("warning: no sentiment produced and no cache available")
            return 2

        # Only publish once we actually have a fresh/updated cache on disk.
        if publish:
            _publish()

        return 0

    except Exception as exc:  # unexpected crash — real failure for the scheduler
        _log(f"ERROR: {type(exc).__name__}: {exc}")
        return 1
    finally:
        _release_lock()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Refresh the news sentiment cache.")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="After refreshing, git-commit + push the output files (Render deploy).",
    )
    args = parser.parse_args()
    raise SystemExit(main(publish=args.publish))
