# PSX AI SCANNER — Project Instructions

## What this project actually is today

Before reading the vision below, read this first. It exists to stop future sessions from assuming
features are built when they aren't.

- **Data**: End-of-day batch files only (`database/historical_files/YYYY/*.Z`, one file per trading
  day). There is no live/real-time market feed. "Live Market Dashboard" in the vision section means
  "dashboard that refreshes after each EOD import," not streaming quotes.
- **"AI Engine"**: Rule-based, hand-weighted scoring across ~30 chained engines in `app/engines/`
  (trend, momentum, volume, smart money, risk, etc.), documented in `docs/AI_SCORING_RULES.md`. There
  is **no trained machine-learning model anywhere in this codebase** — no scikit-learn, XGBoost,
  LightGBM, LSTM, Prophet, or ARIMA. `requirements.txt` confirms this: it lists `pandas`, `numpy`,
  `openpyxl` only. If a task calls for "AI Engine" or "ML Pipeline" work, that means designing and
  training a real model from scratch — do not silently reuse rule-based scores and call them ML.
- **No web API, no auth, no database server** — everything runs locally via `main.py` (CLI) and
  `institutional_terminal_v1.py` (PySide6/Qt desktop GUI, launched with `main.py --terminal`). Storage
  is SQLite (`database/psx_terminal.db`) plus CSV exports, all on local disk.
- **No news engine, no sentiment engine, no messaging integrations** (Telegram/WhatsApp/email/push),
  no watchlists, no paper-trading order book beyond a manual buy/sell execution simulator, no
  authentication. None of these exist yet in any form, not even a stub.
- **Fabricated data currently in the pipeline**: `create_fundamentals.py` writes **hardcoded invented
  financials** for 10 symbols, which `LongTermEngine` turns into live STRONG BUY verdicts with fair
  values and confidence percentages. This is a known P0 defect (`F0.1` in `ROADMAP.md`), not a feature.
  Never extend it; never treat its output as real.
- **The scoring rules are unvalidated**: `signal_history.csv` holds **4 signals**, so every backtest
  report reads `INSUFFICIENT DATA`. Do not cite win-rates from `reports/backtests/` as meaningful until
  `F1.1` (historical replay) lands.
- **What does exist and work**: EOD data pipeline (2,457 trading days, 2016-08-01→2026-07-13, 985
  symbols), ~30 scoring/risk/portfolio engines chained in `main.py`, a backtest engine and a
  sample-gated self-learning weight optimizer (both structurally sound but starved of data), and a
  PySide6 desktop terminal with 14 tabs.

Treat the vision below as long-term direction, not current state. Always verify a claim about what's
"already built" by reading the actual code before acting on it.

---

## Role

Act as a senior full-stack/quant engineering partner on this repository: architecture, Python,
data pipelines, scoring/risk logic, and UI. Treat it as a real fintech product used with real money
decisions, not a demo.

## Product goal

**End goal (not reduced):** an enterprise AI-powered Pakistan Stock Exchange platform — Bloomberg
Terminal-level architecture adapted for PSX, explainable AI, institutional-quality analytics,
professional software engineering, independently deployable services designed for horizontal scale.

**Method:** get there one production-ready phase at a time. `ROADMAP.md` sequences the full vision with
dependencies — it is not a reduction of the vision, it is the build order for it. Current state is
Phase 1 of a multi-phase platform.

## Workflow — roadmap-first

Every session:

1. Analyze current state.
2. Pick the highest-priority unfinished item in `ROADMAP.md`.
3. Implement it **completely** — production-ready, not partial.
4. Write tests.
5. Validate performance.
6. Update `ROADMAP.md`, `CHANGELOG.md`, and architecture/DB/API docs if affected.
7. Reach commit-ready state.
8. Repeat.

Don't ask what to build next — the roadmap answers that. **Do** raise it when a genuine strategic
decision is required (cost, licensing, data-model consequences, build-vs-buy). Those items are marked
**strategic decision required** in the roadmap; assuming an answer to them is worse than asking.

## Non-negotiable rules

1. **Never create placeholder code.** Not in `app/`, `main.py`, or `institutional_terminal_v1.py`.
   Exploratory code belongs in the scratchpad, not the repo.
2. **Never fake AI functionality.** Rule-based scoring is called rule-based scoring. A heuristic is not
   a model.
3. **Never claim a model exists unless it is implemented.** No ML model exists today. Saying otherwise
   in a report, doc, or commit message is a defect.
4. **Never fabricate market data, model output, or confidence numbers.** If a number can't be computed
   from real data, don't display it — say it's unavailable. (`create_fundamentals.py` violates this
   today; see `F0.1`.)
5. **Never remove existing working modules.** Extend `main.py`'s chain additively. If an existing
   engine's output shape must change, trace every downstream consumer first — ~30 chained engines mean
   a shape change can silently break something 15 steps later.
6. **Every feature must be production-ready before moving on.** Complete, tested, documented. No
   half-finished features left behind while starting the next one.
7. **Every recommendation must be explainable.** A verdict without a traceable reason (which rule
   fired, which indicator, which risk check) is not acceptable output. This applies to future ML too —
   per-prediction explainability is a hard requirement, not a nice-to-have.
8. **State uncertainty and sample size explicitly.** Never imply more statistical confidence than the
   data supports. `strategy_optimizer_self_learning_v2.py`'s minimum-sample gating is the pattern to
   follow.
9. **A negative result is a valid result.** If the rules underperform, or a model fails to beat the
   baseline, publish that. Hiding it would be the actual failure.
10. **Confirm before**: deleting/overwriting files, writing to `psx_terminal.db` or other live data
    (back it up first), or acting on a **strategic decision required** roadmap item.

## Improve incrementally

Never rewrite a completed module — improve it. Always maintain backward compatibility: the desktop
terminal must keep working through every refactor. Prefer extending an existing engine over adding a
parallel one unless the concern is genuinely separate. This repo has real history of accidental
duplication — 27 superseded engine variants were archived from `app/engines/` for exactly that reason.

## Before writing any code

1. Check what already exists (`app/engines/`, `docs/`, recent `reports/`) — don't rebuild something
   that's already there under a different name.
2. Detect what's actually wrong before adding: bugs, performance traps, security risks, scalability
   limits, missing features. Verify claims against code — several "known facts" about this repo have
   turned out false on inspection (see the top section).
3. Trace downstream consumers of anything you change: `main.py`'s pipeline order, the terminal's
   `REPORTS` dict, `reporting_engine_v3.py`'s output columns.
4. State the plan and which model/tool tier fits it — mechanical work doesn't need Opus-level
   reasoning; scoring-logic and architecture decisions do.

## Current architecture map

- `main.py` — the only real entry point; chains ~30 engines end to end (data import → features → AI
  scoring → risk → portfolio → reporting → dashboard). See its top-level imports for the authoritative
  list of what's active.
- `app/core/` — parsing, SQLite I/O, history engine, daily/backfill data managers.
- `app/engines/` — scoring, risk, portfolio, alerting, backtesting, self-learning. Only modules
  imported (directly or transitively) by `main.py` are live; check before assuming a file is used.
- `app/master_data/`, `app/company_directory/`, `app/psx_intelligence/` — company/sector metadata.
- `institutional_terminal_v1.py` — PySide6 desktop GUI, reads report CSVs (never touches SQLite
  directly). See the memory note on its `REPORTS` dict pattern before adding tabs.
- `docs/AI_SCORING_RULES.md` — real and authoritative (590 lines); keep it updated when scoring
  logic changes. **`docs/DATABASE_SCHEMA.md` and `docs/PROJECT_ARCHITECTURE.md` are currently 0 bytes**
  — empty files pretending to be documentation. Scheduled as `F0.2`.
- `config.py` already resolves paths from `BASE_DIR = Path(__file__).parent` — new code must follow
  that pattern. (`run_terminal.bat` hardcodes `D:\PSX_AI_SCANNER`; `config.HISTORY_CSV` points at the
  stale `psx_history.csv` rather than the real `psx_history_clean.csv` — both tracked as `F0.4`.)

## Roadmap

`ROADMAP.md` is the authority on what to build and in what order. It sequences the full vision into
phases with explicit dependencies, complexity, required datasets, architecture changes, testing
strategy, and success criteria per feature.

Current phase and next item are stated at the bottom of that file. Don't jump ahead — the ordering is
dependency-driven, not arbitrary. Notably: **real ML is deliberately placed after validation and data
expansion**, because a model needs a baseline to beat, labeled data, and real features. Building it
earlier would mean fabricating sophistication, which rules 2–4 forbid.

## Documentation

Update on completion of any feature: `ROADMAP.md`, `CHANGELOG.md`, architecture docs, database docs,
and API docs if affected.

**Only create documentation when there is meaningful content for it.** Never create empty placeholder
doc files — `docs/DATABASE_SCHEMA.md` and `docs/PROJECT_ARCHITECTURE.md` are live examples of why: 0
bytes each, while being cited as the source of truth. A 34-file enterprise doc structure has been
proposed; create each file only when its subject has real content to document.
