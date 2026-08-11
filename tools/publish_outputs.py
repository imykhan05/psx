"""
git-commit-on-refresh publisher (Deploy Priority 1, item 2).

Commits the small set of output files the deployed API serves, and (by default)
pushes them to EVERY configured git remote. A push to `main` is what triggers a
redeploy on the host (Hugging Face Space / Render / etc.), so this is the bridge
between "scan ran on my PC" and "the cloud API shows fresh data". Pushing to all
remotes means GitHub (code backup) and the deploy host both stay in sync.

Design choices:
- Only the whitelisted OUTPUT_FILES are touched. They are force-added
  (`git add -f`) so a broad .gitignore rule can never silently drop them.
- It NEVER commits the heavy stuff (DB, historical data, model weights) — it only
  ever names the four small artifacts below.
- It is non-fatal by nature: if this isn't a git repo yet, or there's no `origin`
  remote, or nothing changed, it prints why and returns 0. A scan/refresh must
  not fail just because publishing isn't set up. A real push failure returns 2 so
  a scheduler can flag it, but callers wrap it best-effort.

Usage:
    python tools/publish_outputs.py            # commit + push to origin
    python tools/publish_outputs.py --no-push  # commit locally only
"""

from __future__ import annotations

import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# The exact files the deployed API reads (see api/main.py / nl_query_engine.py).
# Kept in sync with the whitelist at the bottom of .gitignore.
OUTPUT_FILES = [
    "database/ai_learning/daily_signal.json",
    "database/ai_learning/sentiment_cache.json",
    "reports/latest/top_buys.csv",
    "reports/latest/full_market_scan.csv",
    "reports/latest/metadata.json",
]


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=check,
    )


def _is_git_repo() -> bool:
    try:
        result = _git("rev-parse", "--is-inside-work-tree", check=False)
        return result.returncode == 0 and result.stdout.strip() == "true"
    except FileNotFoundError:
        # git not installed / not on PATH
        return False


def _all_remotes() -> list[str]:
    result = _git("remote", check=False)
    return [r for r in result.stdout.split() if r]


def _current_branch() -> str:
    result = _git("rev-parse", "--abbrev-ref", "HEAD", check=False)
    return result.stdout.strip() or "main"


def publish(push: bool = True, quiet: bool = False) -> int:
    """
    Commit (and optionally push) the output files. Returns:
      0 — committed, or nothing to do, or setup incomplete (all non-fatal)
      2 — a git operation genuinely failed (e.g. push rejected)
    """

    def say(msg: str) -> None:
        if not quiet:
            print(f"[publish] {msg}")

    if not _is_git_repo():
        say(
            "not a git repository yet — skipping. Set it up with the steps in "
            "docs/DEPLOYMENT.md, then this will start publishing automatically."
        )
        return 0

    # Force-add only the files that actually exist, so gitignore can't drop them
    # and a missing artifact doesn't abort the whole publish.
    present = [f for f in OUTPUT_FILES if (PROJECT_ROOT / f).exists()]
    missing = [f for f in OUTPUT_FILES if f not in present]
    if missing:
        say(f"note: {len(missing)} output file(s) not present yet: {', '.join(missing)}")
    if not present:
        say("no output files present to publish — run a scan first. Skipping.")
        return 0

    add = _git("add", "-f", *present, check=False)
    if add.returncode != 0:
        say(f"git add failed: {add.stderr.strip()}")
        return 2

    # Anything actually staged? (git diff --cached exits 1 when there are changes.)
    staged = _git("diff", "--cached", "--quiet", *present, check=False)
    if staged.returncode == 0:
        say("output files unchanged since last publish — nothing to commit.")
        return 0

    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    commit = _git("commit", "-m", f"chore(data): refresh outputs {stamp}", check=False)
    if commit.returncode != 0:
        # Most common cause: git user.name/user.email not configured.
        say(f"git commit failed: {commit.stderr.strip() or commit.stdout.strip()}")
        return 2
    say(f"committed {len(present)} output file(s) @ {stamp}")

    if not push:
        say("--no-push set; committed locally only.")
        return 0

    remotes = _all_remotes()
    if not remotes:
        say(
            "no git remote configured — commit is local only. Add a remote "
            "(see docs/DEPLOYMENT.md) and the next publish will push."
        )
        return 0

    branch = _current_branch()
    failed = []
    for remote in remotes:
        pushed = _git("push", remote, branch, check=False)
        if pushed.returncode != 0:
            say(f"push to '{remote}' failed: {pushed.stderr.strip()}")
            failed.append(remote)
        else:
            say(f"pushed to {remote}/{branch}")
    if failed:
        return 2
    say("all remotes updated — the deployed API will pick up the fresh data.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish scanner output files to git.")
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Commit locally but do not push to origin.",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output.")
    args = parser.parse_args()
    return publish(push=not args.no_push, quiet=args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
