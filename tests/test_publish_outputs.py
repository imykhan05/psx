"""
Tests for the git-commit-on-refresh publisher (Deploy Priority 1, item 2).

These drive tools/publish_outputs.publish() against a REAL temporary git repo
(no network, no remote) by monkeypatching PROJECT_ROOT / OUTPUT_FILES. They lock
in the safety contract: non-fatal when git isn't set up, commits only when the
whitelisted outputs actually change, and never crashes the caller.
"""

import shutil
import subprocess

import pytest

import tools.publish_outputs as pub

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="git not available on PATH"
)

FILES = ["database/ai_learning/daily_signal.json", "reports/latest/top_buys.csv"]


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    )


def _init_repo(repo):
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test Runner")
    _git(repo, "config", "commit.gpgsign", "false")


def _seed(repo, files, content="data"):
    for rel in files:
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def _commit_count(repo):
    out = _git(repo, "rev-list", "--count", "HEAD")
    return int(out.stdout.strip() or "0")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(pub, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(pub, "OUTPUT_FILES", FILES)
    return tmp_path


def test_not_a_repo_is_non_fatal(repo):
    # tmp_path is not git-initialised.
    _seed(repo, FILES)
    assert pub.publish(push=True) == 0  # returns cleanly, no crash


def test_commits_outputs_without_origin(repo):
    _init_repo(repo)
    _seed(repo, FILES)
    # push=True but there is no 'origin' — must still commit and return 0.
    assert pub.publish(push=True) == 0
    assert _commit_count(repo) == 1
    # Both whitelisted files are tracked.
    tracked = _git(repo, "ls-files").stdout.split()
    assert set(FILES).issubset(set(tracked))


def test_no_new_commit_when_unchanged(repo):
    _init_repo(repo)
    _seed(repo, FILES)
    assert pub.publish(push=False) == 0
    assert _commit_count(repo) == 1
    # Second run with identical content: no new commit.
    assert pub.publish(push=False) == 0
    assert _commit_count(repo) == 1


def test_new_commit_when_changed(repo):
    _init_repo(repo)
    _seed(repo, FILES, content="v1")
    assert pub.publish(push=False) == 0
    _seed(repo, FILES, content="v2")
    assert pub.publish(push=False) == 0
    assert _commit_count(repo) == 2


def test_missing_files_are_skipped_not_fatal(repo):
    _init_repo(repo)
    # Only seed the first output; the second is absent.
    _seed(repo, [FILES[0]])
    assert pub.publish(push=False) == 0
    tracked = _git(repo, "ls-files").stdout.split()
    assert FILES[0] in tracked
    assert FILES[1] not in tracked


def test_no_outputs_present_is_non_fatal(repo):
    _init_repo(repo)
    # No output files seeded at all.
    assert pub.publish(push=False) == 0
    assert _commit_count(repo) == 0
