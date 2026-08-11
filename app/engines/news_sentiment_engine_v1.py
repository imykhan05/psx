"""
News Sentiment Engine V1 (Phase 2 / ROADMAP F6.1-F6.2 brought forward).

Pipeline:
  1. Fetch business-news headlines from free RSS feeds (Dawn, ARY) via feedparser.
  2. Match headlines to PSX tickers using the company directory.
  3. Score sentiment with a pretrained transformer
     (cardiffnlp/twitter-roberta-base-sentiment).
  4. Aggregate to a per-ticker sentiment (BULLISH / BEARISH / NEUTRAL).
  5. Cache to database/ai_learning/sentiment_cache.json with a timestamp;
     fall back to the last cache if the feeds are unavailable.

HONESTY NOTES
- The transformer is a PRETRAINED third-party model we USE — we do not claim to
  have trained it. Its outputs are model estimates, labelled as such.
- Sentiment's *predictive value for PSX prices is not yet validated* (that needs
  the same outcome-correlation treatment the scoring rules got in F1.2). Until
  then this is an information signal, not a proven edge.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

FEEDS = {
    "dawn_business": "https://www.dawn.com/feeds/business",
    "ary_news": "https://arynews.tv/feed/",
}

CACHE_PATH = Path("database/ai_learning/sentiment_cache.json")
MODEL_NAME = "cardiffnlp/twitter-roberta-base-sentiment"

ENGINE_VERSION = "news_sentiment_engine_v1"

BULLISH_THRESHOLD = 0.15
BEARISH_THRESHOLD = -0.15

# Only corporate/trading-marker suffixes are stripped. Distinctive words
# (PAKISTAN, PETROLEUM, MODARABA, TEXTILE, ...) are KEPT so names stay
# multi-word and specific -- stripping them turned "Pakistan Petroleum" into the
# generic "PETROLEUM" and produced false positives.
_NAME_SUFFIXES = re.compile(
    r"\b(LIMITED|LTD|LTDXD|LTDXB|LTDXR|XD|XB|XR|XBXD|XBXR)\b",
    re.IGNORECASE,
)
_NON_ALNUM = re.compile(r"[^A-Za-z0-9 ]+")

# Single English/finance words that are also PSX symbols or name fragments and
# therefore too generic to match on their own (they produced false positives:
# "Next", "Power", "Image", "Equity", ...). Multi-word names and ALL-CAPS symbol
# mentions are unaffected by this list.
_COMMON_WORDS = {
    "NEXT", "POWER", "IMAGE", "EQUITY", "WORLD", "FIRST", "GLOBAL", "UNITED",
    "NATIONAL", "GENERAL", "PREMIER", "PIONEER", "MODERN", "SERVICE", "SERVICES",
    "SECURITY", "SYSTEMS", "SYSTEM", "DATA", "SMART", "SUPER", "PRIME", "GRAND",
    "ROYAL", "CROWN", "STAR", "SUN", "MOON", "GOLD", "SILVER", "METAL", "STEEL",
    "GAS", "OIL", "FUEL", "BANK", "TRUST", "FUND", "GROWTH", "VALUE", "INCOME",
    "TRADE", "TRADING", "MARKET", "CAPITAL", "FINANCE", "INVEST", "HOLDINGS",
    "GROUP", "INTERNATIONAL", "PAKISTAN", "ASIA", "EAST", "WEST", "NORTH",
    "SOUTH", "CENTRAL", "UNION", "ALLIED", "AGRO", "FOODS", "FOOD", "SUGAR",
    "CEMENT", "TEXTILE", "PAPER", "GLASS", "LEATHER", "AUTO", "MOTORS", "ENGINE",
    "IMAGE", "NETWORK", "DIGITAL", "TECH", "MEDIA", "NEWS", "TV", "AIR", "SEA",
    "LAND", "CITY", "TOWN", "HOUSE", "HOME", "LIFE", "HEALTH", "CARE", "MEDICAL",
    # Political parties / institutions that collide with real ticker symbols.
    "PPP", "PTI", "PMLN", "PML", "ANP", "MQM", "JUI", "ECP", "NAB", "IHC",
    "SBP", "FBR", "IMF", "GDP", "CPI", "CDWP", "ADB",
}


# ---------------------------------------------------------------------------
# 1. Feeds
# ---------------------------------------------------------------------------
def fetch_headlines(feeds: dict[str, str] = FEEDS) -> tuple[list[dict], list[str]]:
    """Return (headlines, errors). Never raises; a broken feed is skipped."""
    import feedparser

    headlines: list[dict] = []
    errors: list[str] = []

    for source, url in feeds.items():
        try:
            parsed = feedparser.parse(url)
            if parsed.bozo and not parsed.entries:
                errors.append(f"{source}: parse error ({parsed.bozo_exception})")
                continue
            for entry in parsed.entries:
                title = str(entry.get("title", "")).strip()
                summary = re.sub(r"<[^>]+>", " ", str(entry.get("summary", ""))).strip()
                if not title:
                    continue
                headlines.append(
                    {
                        "source": source,
                        "title": title,
                        "summary": summary,
                        "link": str(entry.get("link", "")),
                        "published": str(entry.get("published", "")),
                    }
                )
        except Exception as exc:  # network / parser failure -> skip this feed
            errors.append(f"{source}: {type(exc).__name__}: {exc}")

    return headlines, errors


# ---------------------------------------------------------------------------
# 2. Ticker matching
# ---------------------------------------------------------------------------
def _clean_name(name: str) -> str:
    name = _NON_ALNUM.sub(" ", str(name).upper())
    name = _NAME_SUFFIXES.sub(" ", name)
    return re.sub(r"\s+", " ", name).strip()


def build_ticker_aliases() -> dict[str, dict]:
    """
    symbol -> {"symbol_token": SYM|None, "names": [distinctive name aliases]}.

    Precision-first aliasing to avoid attaching news to the wrong ticker:
    - A symbol is matchable only as an ALL-CAPS token (real "PPL"/"OGDC"
      mentions), so title-case English words like "Next"/"Power" never match it.
    - A company name is matchable if it is multi-word (distinctive, e.g.
      "K ELECTRIC") or a single word that is not a common English/finance word.
    """
    from app.company_directory.company_loader import load_companies

    companies = load_companies()
    aliases: dict[str, dict] = {}

    for _, row in companies.iterrows():
        symbol = str(row.get("symbol", "")).upper().strip()
        if not symbol:
            continue

        symbol_token = (
            symbol
            if (symbol.isalpha() and len(symbol) >= 3 and symbol not in _COMMON_WORDS)
            else None
        )

        # Precision-first: only MULTI-WORD names are distinctive enough to match
        # on. Single-word names (even distinctive ones like ENGRO) are dropped to
        # avoid generic-word false positives; those tickers can still match via
        # an ALL-CAPS symbol mention.
        names: list[str] = []
        cleaned = _clean_name(row.get("company", ""))
        if cleaned and " " in cleaned and len(cleaned) >= 6:
            names.append(cleaned)

        if symbol_token or names:
            aliases[symbol] = {"symbol_token": symbol_token, "names": names}

    return aliases


def match_headlines_to_tickers(
    headlines: list[dict],
    aliases: dict[str, dict],
) -> list[dict]:
    """Return match records: {symbol, alias, source, title, text}. A headline may
    match multiple tickers."""
    matches: list[dict] = []

    prepared = []
    for h in headlines:
        text = f"{h['title']} {h['summary']}".strip()
        original = text  # case preserved: for ALL-CAPS symbol detection
        upper = f" {_NON_ALNUM.sub(' ', text.upper())} "
        upper_tokens = set(upper.split())
        # Case-sensitive uppercase tokens actually present in the headline.
        caps_tokens = {
            tok for tok in _NON_ALNUM.sub(" ", original).split() if tok.isupper()
        }
        prepared.append((h, text, upper, upper_tokens, caps_tokens))

    for symbol, spec in aliases.items():
        symbol_token = spec["symbol_token"]
        names = spec["names"]

        for h, text, upper, upper_tokens, caps_tokens in prepared:
            hit_alias = None

            # 1) Real ALL-CAPS symbol mention.
            if symbol_token and symbol_token in caps_tokens:
                hit_alias = symbol_token

            # 2) Distinctive company-name mention (case-insensitive).
            if hit_alias is None:
                for name in names:
                    if " " in name:
                        if f" {name} " in upper:
                            hit_alias = name
                            break
                    elif name in upper_tokens:
                        hit_alias = name
                        break

            if hit_alias:
                matches.append(
                    {
                        "symbol": symbol,
                        "alias": hit_alias,
                        "source": h["source"],
                        "title": h["title"],
                        "text": text,
                    }
                )

    return matches


# ---------------------------------------------------------------------------
# 3. Sentiment scoring (pretrained transformer, lazy-loaded)
# ---------------------------------------------------------------------------
class SentimentScorer:
    """Lazy wrapper around the cardiffnlp RoBERTa sentiment pipeline."""

    _LABEL_MAP = {
        "LABEL_0": "negative",
        "LABEL_1": "neutral",
        "LABEL_2": "positive",
        "negative": "negative",
        "neutral": "neutral",
        "positive": "positive",
    }
    _SIGN = {"negative": -1.0, "neutral": 0.0, "positive": 1.0}

    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self._pipeline = None
        self.available = None  # None=untried, True/False after load attempt
        self.load_error = None

    def _load(self) -> bool:
        if self.available is not None:
            return self.available
        try:
            from transformers import pipeline

            self._pipeline = pipeline(
                "sentiment-analysis",
                model=self.model_name,
                tokenizer=self.model_name,
                truncation=True,
                max_length=256,
            )
            self.available = True
        except Exception as exc:
            self.available = False
            self.load_error = f"{type(exc).__name__}: {exc}"
        return self.available

    def score_texts(self, texts: list[str]) -> list[dict]:
        if not self._load():
            return [{"label": "neutral", "score": 0.0, "signed": 0.0} for _ in texts]

        results = []
        # Batch through the pipeline.
        raw = self._pipeline(texts, batch_size=16)
        for item in raw:
            label = self._LABEL_MAP.get(item["label"], "neutral")
            conf = float(item["score"])
            results.append(
                {
                    "label": label,
                    "score": round(conf, 4),
                    "signed": round(self._SIGN[label] * conf, 4),
                }
            )
        return results


# ---------------------------------------------------------------------------
# 4. Aggregation
# ---------------------------------------------------------------------------
def _tier(mean_signed: float) -> str:
    if mean_signed >= BULLISH_THRESHOLD:
        return "BULLISH"
    if mean_signed <= BEARISH_THRESHOLD:
        return "BEARISH"
    return "NEUTRAL"


def aggregate(matches: list[dict], scored: list[dict]) -> dict[str, dict]:
    by_symbol: dict[str, dict] = {}
    for match, sentiment in zip(matches, scored):
        symbol = match["symbol"]
        bucket = by_symbol.setdefault(
            symbol,
            {"symbol": symbol, "n_headlines": 0, "signed_sum": 0.0, "headlines": []},
        )
        bucket["n_headlines"] += 1
        bucket["signed_sum"] += sentiment["signed"]
        if len(bucket["headlines"]) < 3:
            bucket["headlines"].append(
                {
                    "source": match["source"],
                    "title": match["title"],
                    "label": sentiment["label"],
                    "score": sentiment["score"],
                }
            )

    result = {}
    for symbol, bucket in by_symbol.items():
        n = bucket["n_headlines"]
        mean_signed = round(bucket["signed_sum"] / n, 4) if n else 0.0
        result[symbol] = {
            "symbol": symbol,
            "n_headlines": n,
            "sentiment_score": mean_signed,
            "sentiment_label": _tier(mean_signed),
            "sample_headlines": bucket["headlines"],
        }
    return result


# ---------------------------------------------------------------------------
# 5. Caching + fallback + orchestration
# ---------------------------------------------------------------------------
def _write_cache(payload: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _read_cache() -> dict | None:
    if not CACHE_PATH.exists() or CACHE_PATH.stat().st_size == 0:
        return None
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def read_cached_sentiment() -> dict | None:
    """
    Public, read-only access to the last cached sentiment payload.

    This deliberately never touches the network or loads the transformer model.
    main.py's normal scan, the FastAPI backend, and the daily-signal engine all
    use this so the heavy model stays confined to the standalone refresher
    (tools/refresh_sentiment.py) and the explicit ``--refresh-news`` opt-in.
    Returns None if no cache has been produced yet.
    """
    return _read_cache()


def run_news_sentiment_engine(
    feeds: dict[str, str] = FEEDS,
    scorer: SentimentScorer | None = None,
    use_cache_on_failure: bool = True,
) -> dict:
    """
    Fetch -> match -> score -> aggregate -> cache. On feed failure, fall back to
    the last cached result (flagged), so the pipeline never breaks on a network
    hiccup.
    """
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    headlines, errors = fetch_headlines(feeds)

    if not headlines:
        # Graceful fallback to last cache.
        if use_cache_on_failure:
            cached = _read_cache()
            if cached:
                cached["source"] = "cache_fallback"
                cached["fallback_reason"] = "; ".join(errors) or "no headlines fetched"
                cached["fallback_at"] = generated_at
                return cached
        return {
            "engine_version": ENGINE_VERSION,
            "generated_at": generated_at,
            "source": "empty",
            "errors": errors,
            "headline_count": 0,
            "matched_headlines": 0,
            "tickers_with_news": 0,
            "model": None,
            "tickers": {},
        }

    aliases = build_ticker_aliases()
    matches = match_headlines_to_tickers(headlines, aliases)

    scorer = scorer or SentimentScorer()
    scored = scorer.score_texts([m["text"] for m in matches]) if matches else []

    tickers = aggregate(matches, scored)

    payload = {
        "engine_version": ENGINE_VERSION,
        "generated_at": generated_at,
        "source": "live",
        "errors": errors,
        "headline_count": len(headlines),
        "matched_headlines": len(matches),
        "tickers_with_news": len(tickers),
        "model": MODEL_NAME if scorer.available else None,
        "model_available": bool(scorer.available),
        "model_error": scorer.load_error,
        "tickers": tickers,
    }

    _write_cache(payload)
    return payload


def sentiment_summary(payload: dict) -> dict:
    """Compact summary for main.py's print_dict."""
    return {
        "source": payload.get("source"),
        "generated_at": payload.get("generated_at"),
        "headline_count": payload.get("headline_count", 0),
        "matched_headlines": payload.get("matched_headlines", 0),
        "tickers_with_news": payload.get("tickers_with_news", 0),
        "model_available": payload.get("model_available", False),
        "model_error": payload.get("model_error"),
    }


if __name__ == "__main__":
    result = run_news_sentiment_engine()
    print(json.dumps(sentiment_summary(result), indent=2))
    ranked = sorted(
        result.get("tickers", {}).values(),
        key=lambda t: (-t["n_headlines"], -abs(t["sentiment_score"])),
    )
    for t in ranked[:25]:
        print(
            f"{t['symbol']:8} {t['sentiment_label']:8} "
            f"score={t['sentiment_score']:+.3f} n={t['n_headlines']}"
        )
