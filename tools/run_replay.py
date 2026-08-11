"""
CLI runner for the Historical Signal Replay Engine (ROADMAP.md F1.1).

Examples:
    python tools/run_replay.py --max-dates 5 --no-label        # quick smoke test
    python tools/run_replay.py --start 2018-01-01 --end 2022-12-31
    python tools/run_replay.py                                 # full history
    python tools/run_replay.py --resume                        # continue a run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.engines.backtesting.replay_engine_v1 import (  # noqa: E402
    run_historical_replay,
    DEFAULT_OUTPUT,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="PSX historical signal replay")
    parser.add_argument("--capital", type=int, default=50000)
    parser.add_argument("--max-price", type=float, default=500.0)
    parser.add_argument("--max-holding-days", type=int, default=5)
    parser.add_argument("--start", default=None, help="ISO start date, e.g. 2018-01-01")
    parser.add_argument("--end", default=None, help="ISO end date")
    parser.add_argument("--max-dates", type=int, default=None)
    parser.add_argument(
        "--stride",
        type=int,
        default=1,
        help="Sample every Nth trading date across the range (regime coverage).",
    )
    parser.add_argument("--warmup-dates", type=int, default=60)
    parser.add_argument(
        "--decisions",
        default=None,
        help="Comma list to record only these tiers, e.g. 'STRONG BUY,BUY,WATCH'. Default: all.",
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--no-label", action="store_true", help="Skip outcome labelling.")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    decisions = (
        tuple(d.strip() for d in args.decisions.split(",")) if args.decisions else None
    )

    summary = run_historical_replay(
        capital=args.capital,
        max_price=args.max_price,
        max_holding_days=args.max_holding_days,
        start_date=args.start,
        end_date=args.end,
        max_dates=args.max_dates,
        stride=args.stride,
        warmup_dates=args.warmup_dates,
        record_decisions=decisions,
        output_file=Path(args.output),
        label_outcomes=not args.no_label,
        resume=args.resume,
    )
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
