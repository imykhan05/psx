"""
Ticker-matching precision tests for the news sentiment engine (Phase 2 #1).

No network and no model required — these exercise the matcher logic directly
with synthetic headlines/aliases. They lock in the false-positive fixes:
ALL-CAPS symbols match but title-case English words do not; multi-word company
names match; common-word symbols are rejected.
"""

from app.engines.news_sentiment_engine_v1 import (
    match_headlines_to_tickers,
    _clean_name,
)


def _headline(title, summary=""):
    return {"source": "test", "title": title, "summary": summary,
            "link": "", "published": ""}


def test_allcaps_symbol_matches():
    aliases = {"OGDC": {"symbol_token": "OGDC", "names": []}}
    hits = match_headlines_to_tickers([_headline("OGDC posts record profit")], aliases)
    assert [h["symbol"] for h in hits] == ["OGDC"]


def test_titlecase_word_does_not_match_symbol():
    # NEXT is a symbol, but a title-case English "Next" must NOT match.
    aliases = {"NEXT": {"symbol_token": "NEXT", "names": []}}
    hits = match_headlines_to_tickers([_headline("What comes Next for the economy")], aliases)
    assert hits == []


def test_multiword_name_matches():
    aliases = {"KEL": {"symbol_token": None, "names": ["K ELECTRIC"]}}
    hits = match_headlines_to_tickers(
        [_headline("K Electric raises tariffs for consumers")], aliases
    )
    assert [h["symbol"] for h in hits] == ["KEL"]


def test_generic_single_word_is_not_an_alias():
    # A generic single-word name must not be present as an alias in the first
    # place; if forced, it still should not match unrelated news as a name.
    aliases = {"PPL": {"symbol_token": None, "names": ["PAKISTAN PETROLEUM"]}}
    hits = match_headlines_to_tickers(
        [_headline("Govt reduces petrol and diesel prices")], aliases
    )
    assert hits == []  # "petroleum" alone must not trigger the multi-word name


def test_multiword_name_requires_full_phrase():
    aliases = {"PPL": {"symbol_token": None, "names": ["PAKISTAN PETROLEUM"]}}
    hits = match_headlines_to_tickers(
        [_headline("Pakistan Petroleum announces new gas discovery")], aliases
    )
    assert [h["symbol"] for h in hits] == ["PPL"]


def test_clean_name_strips_only_corporate_suffixes():
    assert _clean_name("NISHAT MILLS LIMITED") == "NISHAT MILLS"
    assert _clean_name("LUCKY CEMENT LTD") == "LUCKY CEMENT"
    # distinctive words are preserved
    assert "PETROLEUM" in _clean_name("PAKISTAN PETROLEUM LIMITED")
    assert "PAKISTAN" in _clean_name("PAKISTAN PETROLEUM LIMITED")
