"""
CLI for the PSX natural-language assistant (Phase 2 #3).

    python tools/ask.py                 # interactive REPL
    python tools/ask.py "is today good for buying?"   # one-shot question

Requires ANTHROPIC_API_KEY in a .env file at the project root (see .env.example).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.engines.nl_query_engine import (  # noqa: E402
    run_repl,
    get_client,
    load_context,
    build_system_prompt,
    stream_answer,
)


def main() -> int:
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:]).strip()
        try:
            client = get_client()
            system_prompt = build_system_prompt(load_context())
            for chunk in stream_answer(client, system_prompt, [{"role": "user", "content": question}]):
                print(chunk, end="", flush=True)
            print()
        except Exception as exc:  # auth / billing / network — report cleanly
            print(f"[error] {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        return 0
    return run_repl()


if __name__ == "__main__":
    raise SystemExit(main())
