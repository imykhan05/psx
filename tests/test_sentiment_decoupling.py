"""
Decoupling tests for Priority-1 item 1.

These lock in the invariant that the heavy transformer model
(cardiffnlp/twitter-roberta-base-sentiment via torch/transformers) stays OFF the
normal scan / API request path. The only place allowed to load it is the
standalone refresher (tools/refresh_sentiment.py) and the explicit
``--refresh-news`` opt-in.

No network and no model are used here.
"""

import json
import runpy
import sys
from pathlib import Path

import app.engines.news_sentiment_engine_v1 as nse


def test_read_cached_sentiment_reads_without_model(tmp_path, monkeypatch):
    """read_cached_sentiment() returns the JSON payload and imports no model."""
    fake = {
        "engine_version": "test",
        "generated_at": "2026-08-11T05:00:00+00:00",
        "source": "live",
        "headline_count": 3,
        "matched_headlines": 1,
        "tickers_with_news": 1,
        "model_available": True,
        "tickers": {},
    }
    cache = tmp_path / "sentiment_cache.json"
    cache.write_text(json.dumps(fake), encoding="utf-8")
    monkeypatch.setattr(nse, "CACHE_PATH", cache)

    # Ensure a clean slate, then read.
    sys.modules.pop("torch", None)
    sys.modules.pop("transformers", None)

    payload = nse.read_cached_sentiment()
    assert payload is not None
    assert payload["source"] == "live"
    assert payload["headline_count"] == 3

    # The read path must not have pulled in the heavy stack.
    assert "torch" not in sys.modules
    assert "transformers" not in sys.modules


def test_read_cached_sentiment_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(nse, "CACHE_PATH", tmp_path / "does_not_exist.json")
    assert nse.read_cached_sentiment() is None


def test_api_and_signal_paths_do_not_import_model():
    """Static guard: request-path modules never reference torch/transformers."""
    root = Path(__file__).resolve().parent.parent
    for rel in (
        "api/main.py",
        "app/engines/nl_query_engine.py",
        "app/engines/daily_signal_engine.py",
    ):
        src = (root / rel).read_text(encoding="utf-8")
        assert "import torch" not in src, f"{rel} must not import torch"
        assert "transformers" not in src, f"{rel} must not import transformers"


def test_refresher_reports_success_on_cached_engine(tmp_path, monkeypatch, capsys):
    """tools/refresh_sentiment.py exits 0 when the engine returns a payload,
    without touching the real lock/log locations or the network."""
    import tools.refresh_sentiment as refresher

    monkeypatch.setattr(refresher, "LOCK_FILE", tmp_path / ".sentiment.lock")
    monkeypatch.setattr(refresher, "LOG_FILE", tmp_path / "sentiment_refresh.log")

    payload = {
        "source": "live",
        "generated_at": "2026-08-11T05:00:00+00:00",
        "headline_count": 10,
        "matched_headlines": 2,
        "tickers_with_news": 2,
        "model_available": True,
        "tickers": {},
    }
    monkeypatch.setattr(nse, "run_news_sentiment_engine", lambda: payload)

    rc = refresher.main()
    assert rc == 0
    # Lock is released and a log line was written.
    assert not (tmp_path / ".sentiment.lock").exists()
    assert (tmp_path / "sentiment_refresh.log").read_text(encoding="utf-8").strip()


def test_refresher_soft_fails_when_no_cache(tmp_path, monkeypatch):
    """Exit code 2 when the engine yields an 'empty' payload (no cache to fall
    back to) — distinct from a real crash (1)."""
    import tools.refresh_sentiment as refresher

    monkeypatch.setattr(refresher, "LOCK_FILE", tmp_path / ".sentiment.lock")
    monkeypatch.setattr(refresher, "LOG_FILE", tmp_path / "sentiment_refresh.log")
    monkeypatch.setattr(
        nse, "run_news_sentiment_engine", lambda: {"source": "empty", "tickers": {}}
    )

    assert refresher.main() == 2
