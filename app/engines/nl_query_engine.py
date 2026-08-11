"""
Natural-Language Query Engine (Phase 2 #3).

A grounded question-answering layer over the scanner's own output. It loads a
compact snapshot of today's state (daily signal, per-ticker news sentiment, top
opportunities, and market-wide summary statistics) and answers free-text
questions — English or Urdu — via the Anthropic API (claude-sonnet-4-6).

GROUNDING / HONESTY
- The assistant answers ONLY from the provided snapshot. The system prompt
  forbids inventing prices, forecasts, or figures not in the data, and requires
  it to say plainly when the snapshot doesn't contain the answer.
- This is the scanner's rule-based output surfaced through a language model. It
  is NOT a trained market model and NOT financial advice — the prompt states
  both. The data is an end-of-day snapshot for a specific trading date, not live.

AUTH
- Reads ANTHROPIC_API_KEY from a .env file (python-dotenv) or the environment.
  The key is never hard-coded. See .env.example.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

try:
    from dotenv import load_dotenv
except ImportError:  # optional dep; env vars still work without it
    load_dotenv = None

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 2048

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DAILY_SIGNAL = PROJECT_ROOT / "database" / "ai_learning" / "daily_signal.json"
SENTIMENT_CACHE = PROJECT_ROOT / "database" / "ai_learning" / "sentiment_cache.json"
TOP_BUYS = PROJECT_ROOT / "reports" / "latest" / "top_buys.csv"
FULL_SCAN = PROJECT_ROOT / "reports" / "latest" / "full_market_scan.csv"

ENGINE_VERSION = "nl_query_engine_v1"


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------
def _read_json(path: Path) -> dict:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        return pd.DataFrame()


def _full_scan_summary(df: pd.DataFrame) -> dict:
    """Summary statistics only — never the full row set."""
    if df.empty:
        return {"scored": 0}

    change = pd.to_numeric(df.get("change_pct"), errors="coerce")
    score = pd.to_numeric(df.get("final_score"), errors="coerce")

    summary = {
        "scored": int(len(df)),
        "advancers": int((change > 0).sum()),
        "decliners": int((change < 0).sum()),
        "flat": int((change == 0).sum()),
        "avg_final_score": round(float(score.mean()), 1) if score.notna().any() else None,
        "decision_distribution": (
            df["final_decision"].astype(str).str.upper().value_counts().to_dict()
            if "final_decision" in df.columns
            else {}
        ),
    }

    # Highest-scored names (a short list, not the universe).
    if "final_score" in df.columns and "symbol" in df.columns:
        top = df.assign(_s=score).sort_values("_s", ascending=False).head(10)
        summary["highest_scored"] = [
            {
                "symbol": str(r.get("symbol")),
                "sector": str(r.get("sector", "")),
                "final_score": round(float(r.get("_s", 0) or 0), 1),
                "decision": str(r.get("final_decision", "")),
                "change_pct": round(float(pd.to_numeric(r.get("change_pct"), errors="coerce") or 0), 2),
            }
            for _, r in top.iterrows()
        ]

    # Sector breadth — best and worst by average move.
    if "sector" in df.columns:
        sec = (
            df.assign(_c=change)
            .groupby("sector")["_c"]
            .agg(["mean", "count"])
            .dropna()
            .sort_values("mean", ascending=False)
        )
        summary["sectors_strongest"] = [
            {"sector": s, "avg_change_pct": round(float(row["mean"]), 2), "stocks": int(row["count"])}
            for s, row in sec.head(5).iterrows()
        ]
        summary["sectors_weakest"] = [
            {"sector": s, "avg_change_pct": round(float(row["mean"]), 2), "stocks": int(row["count"])}
            for s, row in sec.tail(5).iterrows()
        ]

    return summary


def _top_buys_rows(df: pd.DataFrame, limit: int = 15) -> list[dict]:
    if df.empty:
        return []
    keep = [
        "symbol", "company", "sector", "close", "change_pct",
        "final_decision", "final_score", "buy_probability", "risk_permission",
        "entry_timing_action", "suggested_entry_price", "stop_loss",
        "target_1", "target_2",
    ]
    cols = [c for c in keep if c in df.columns]
    return df[cols].head(limit).to_dict(orient="records")


def _sentiment_rows(sentiment: dict) -> dict:
    tickers = sentiment.get("tickers", {}) if isinstance(sentiment, dict) else {}
    compact = {}
    for sym, t in tickers.items():
        compact[sym] = {
            "label": t.get("sentiment_label"),
            "score": t.get("sentiment_score"),
            "headlines": t.get("n_headlines"),
            "sample": [h.get("title") for h in (t.get("sample_headlines") or [])][:2],
        }
    return {
        "source": sentiment.get("source"),
        "generated_at": sentiment.get("generated_at"),
        "tickers": compact,
    }


def load_context() -> dict:
    """Assemble the compact snapshot passed to the model on every query."""
    return {
        "daily_signal": _read_json(DAILY_SIGNAL),
        "news_sentiment": _sentiment_rows(_read_json(SENTIMENT_CACHE)),
        "top_opportunities": _top_buys_rows(_read_csv(TOP_BUYS)),
        "market_summary": _full_scan_summary(_read_csv(FULL_SCAN)),
    }


def build_system_prompt(context: dict) -> str:
    snapshot = json.dumps(context, indent=2, ensure_ascii=False, default=str)
    return (
        "You are the assistant for a Pakistan Stock Exchange (PSX) end-of-day "
        "scanner. Answer the user's questions using ONLY the DATA SNAPSHOT below, "
        "which is this scanner's own output for one trading day.\n\n"
        "Rules:\n"
        "- Answer strictly from the snapshot. Do NOT invent prices, targets, "
        "forecasts, fundamentals, or any figure that is not present. If the "
        "snapshot does not contain what is needed, say so plainly.\n"
        "- The data is a rule-based scan, not a trained prediction model, and it "
        "is end-of-day (not live). Never imply real-time quotes or guaranteed "
        "outcomes.\n"
        "- This is decision-support, not financial advice. Do not tell the user "
        "to buy or sell; explain what the scanner's signals say and why.\n"
        "- Every claim should be traceable to a field in the snapshot (a verdict, "
        "a score, a decision, a breadth number, a sentiment label). Briefly cite "
        "the reason.\n"
        "- If the user writes in Urdu (or Roman Urdu), reply in the same style. "
        "If in English, reply in English. Keep answers concise and direct.\n"
        "- When a stock is rated AVOID or no opportunities are flagged, say that "
        "honestly rather than manufacturing a bullish case.\n\n"
        f"DATA SNAPSHOT (trading date {context.get('daily_signal', {}).get('date', 'unknown')}):\n"
        f"{snapshot}\n"
    )


# ---------------------------------------------------------------------------
# Anthropic client + streaming
# ---------------------------------------------------------------------------
def _load_env() -> None:
    if load_dotenv is not None:
        load_dotenv(PROJECT_ROOT / ".env")


def get_client():
    """Construct the Anthropic client; raises a clear error if the key is absent."""
    _load_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to a .env file at the project "
            "root (see .env.example) or export it in your environment."
        )
    import anthropic

    return anthropic.Anthropic()


def stream_answer(client, system_prompt: str, messages: list[dict]):
    """
    Yield response text chunks for the given conversation. `messages` is the
    running user/assistant history (the newest user turn last). The large,
    stable snapshot lives in `system_prompt` with a cache breakpoint so repeated
    questions in a session reuse it cheaply.
    """
    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text


# ---------------------------------------------------------------------------
# Terminal REPL
# ---------------------------------------------------------------------------
def run_repl() -> int:
    print("=" * 70)
    print("PSX AI Assistant  |  model:", MODEL)
    print("Ask anything about today's scan (English or Urdu). Type 'exit' to quit.")
    print("=" * 70)

    try:
        client = get_client()
    except RuntimeError as exc:
        print(f"\n[error] {exc}")
        return 1

    context = load_context()
    system_prompt = build_system_prompt(context)
    print(
        f"Loaded snapshot for {context.get('daily_signal', {}).get('date', 'unknown')} "
        f"| verdict: {context.get('daily_signal', {}).get('verdict', 'N/A')}\n"
    )

    history: list[dict] = []
    while True:
        try:
            question = input("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        if question.lower() in {"exit", "quit"}:
            break

        history.append({"role": "user", "content": question})
        print("ai  > ", end="", flush=True)
        answer_parts: list[str] = []
        try:
            for chunk in stream_answer(client, system_prompt, history):
                print(chunk, end="", flush=True)
                answer_parts.append(chunk)
        except Exception as exc:  # network / auth / API error
            print(f"\n[error] {type(exc).__name__}: {exc}")
            history.pop()  # don't keep a turn with no answer
            continue
        print("\n")
        history.append({"role": "assistant", "content": "".join(answer_parts)})

    print("Goodbye.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_repl())
