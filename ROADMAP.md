# PSX AI Scanner — Implementation Roadmap

**End goal:** An enterprise AI-powered Pakistan Stock Exchange platform — Bloomberg Terminal-level
architecture adapted for PSX, with explainable AI, institutional-quality analytics, and professional
software engineering. The vision is not reduced. This document sequences it.

**Working rule:** roadmap-first. Each session: analyze state → pick highest-priority unfinished item →
implement completely → test → validate performance → update docs → commit-ready → repeat.

**Status legend:** `DONE` · `IN PROGRESS` · `TODO` · `BLOCKED`
**Complexity:** S (≤1 session) · M (2–4 sessions) · L (1–2 weeks) · XL (multi-week, needs decomposition)

---

## Ground truth (verified 2026-07-17, re-verify before trusting)

What actually exists, so no phase is planned on a false premise:

| Area | Reality |
|---|---|
| Market data | EOD batch files only (`database/historical_files/YYYY/*.Z`). **No live feed.** 2,457 trading days, 2016-08-01→2026-07-13, 985 symbols, 905,195 rows in `psx_terminal.db`. |
| "AI Engine" | ~30 chained **rule-based, hand-weighted** engines. **Zero ML libraries** in the codebase (`requirements.txt` = pandas, numpy, openpyxl). No trained model exists. |
| Backtest | Engine exists and works, but `signal_history.csv` holds **4 signals**. All win-rate reports read `INSUFFICIENT DATA`. The rule weights are **unvalidated**. |
| Fundamentals | `fundamentals.csv` = **10 symbols of hardcoded invented numbers** (1% of universe) written by `create_fundamentals.py`. Feeds live STRONG BUY verdicts. **Integrity violation.** |
| Company metadata | `create_psx_seed_data.py` seeds sector/industry/website, marked `source=SEED`. Descriptive reference data, verifiable — acceptable, but should be sourced properly. |
| API / auth / multi-user | None. Single-user, local-only. |
| News / sentiment / watchlists / notifications / paper trading | Do not exist in any form. |
| Storage | SQLite + CSV on local disk. No server DB, no cache layer. |
| Config | `config.py` correctly uses `BASE_DIR = Path(__file__).parent`. Only `run_terminal.bat` hardcodes `D:\PSX_AI_SCANNER`. |
| Docs | `AI_SCORING_RULES.md` real (590 lines). `DATABASE_SCHEMA.md` and `PROJECT_ARCHITECTURE.md` are **0 bytes**. |

---

## Target architecture (Phase 3+)

Modules become independently deployable, loosely coupled services behind APIs. Today they are Python
modules chained in-process by `main.py`. The migration path is: **extract interface → wrap in service →
split process**, one module at a time, never a big-bang rewrite.

```
                    ┌─────────────┐   ┌──────────┐   ┌──────────────┐
   Clients ────────▶│   Gateway   │──▶│   Auth   │   │  AI Chat Svc │
  (Desktop/PWA/API) └──────┬──────┘   └──────────┘   └──────────────┘
                           │
    ┌──────────┬───────────┼───────────┬──────────────┬──────────────┐
    ▼          ▼           ▼           ▼              ▼              ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐
│Market  │ │Scanner │ │Tech    │ │Fundamental│ │ML Predict │ │Portfolio │
│Data Svc│ │Service │ │Analysis│ │ Analysis  │ │  Service  │ │ Service  │
└───┬────┘ └────────┘ └────────┘ └──────────┘ └───────────┘ └────┬─────┘
    │                                                             │
    ▼          ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────▼──┐
┌────────┐     │Dividend  │ │News Intel│ │Sentiment │ │Risk / Strategy│
│ Store  │     │ Service  │ │ Service  │ │  Engine  │ │    Engines    │
│(PG+TS) │     └──────────┘ └──────────┘ └──────────┘ └───────────────┘
└────────┘     ┌──────────┐ ┌──────────┐ ┌──────────┐
               │Backtest  │ │  Paper   │ │Notificat.│
               │ Service  │ │ Trading  │ │ Service  │
               └──────────┘ └──────────┘ └──────────┘
```

**Scalability assumptions to design against:** millions of rows (already at ~1M; live tick data would
add ~2 orders of magnitude), multi-user concurrent access, horizontal scaling of stateless services.
SQLite is adequate through Phase 2 and becomes the binding constraint at Phase 3 (concurrent writers)
— see F3.1.

---

# PHASE 0 — Integrity (P0, blocks everything)

The system currently emits claims it cannot support. Nothing else matters until this is false.

### F0.1 — Quarantine fabricated fundamental data · `DONE` (2026-07-20) · **P0** · S
The single most severe defect in the codebase. **Resolved** — see CHANGELOG 2026-07-20.

Implemented: provenance-aware `fundamental_loader.py` (`REAL`/`SEED`/`ABSENT`), an authoritative
`enforce_provenance_gate` in `LongTermEngine` that refuses any verdict/fair-value/confidence for
non-`REAL` rows (overwriting even input-origin columns like a fabricated `fair_value`), the fabricated
`create_fundamentals.py` + `fundamentals.csv` moved to `archive/fabricated_fundamentals/`, and 10
passing tests in `tests/test_fundamentals_provenance.py`. Verified end-to-end: a full pipeline run
turned `reports/latest/long_term.csv` from 10 fabricated STRONG BUY/BUY verdicts into an empty report.

- **Problem:** `create_fundamentals.py` contains hardcoded invented financials (EPS, book value, ROE,
  fair_value) for 10 symbols. `merge_fundamentals()` → `LongTermEngine` converts them into live output:
  `reports/latest/long_term.csv` currently states *"LUCK — fair value 980.00, upside 113.29%, DEEPLY
  UNDERVALUED, STRONG BUY, confidence 95%"*. That 980 is a Python string literal, not a financial
  statement. Violates the project's own first rule.
- **Dependencies:** none. Do this first.
- **Datasets:** none required (removal, not addition).
- **Architecture changes:** add a `data_provenance` field (`REAL` / `SEED` / `ABSENT`) to the
  fundamentals loader. `LongTermEngine` must refuse to emit a verdict, fair value, or confidence for any
  symbol whose provenance ≠ `REAL`. Long-term report shows "fundamentals unavailable" rather than a
  fabricated verdict. Move `create_fundamentals.py` to `archive/` with a README explaining why.
- **Testing:** unit test asserting `LongTermEngine` emits no verdict/fair_value for `SEED`/`ABSENT`
  provenance; regression test that `long_term.csv` contains zero rows until F3.3 lands real data.
- **Success criteria:** no fabricated number reaches any report, ever. `grep` for the invented fair
  values in `reports/` returns nothing after a clean run.

### F0.2 — Correct empty/false documentation · `DONE` (2026-07-20) · **P0** · S
Resolved alongside F0.4: `docs/DATABASE_SCHEMA.md` (98 lines) and `docs/PROJECT_ARCHITECTURE.md`
(123 lines) written from live code — actual `daily_prices` schema/indexes/counts and the real `main.py`
pipeline order. No longer 0-byte placeholders.
- **Problem:** `docs/DATABASE_SCHEMA.md` and `docs/PROJECT_ARCHITECTURE.md` are 0 bytes but are
  referenced as authoritative. Empty files that claim to be documentation are worse than absent ones.
- **Dependencies:** none.
- **Architecture changes:** none — write real content: actual `daily_prices` schema (15 columns, from
  `sqlite_database.py`), actual engine chain order (from `main.py`), actual report artifact map.
- **Testing:** n/a (docs). Verify every claim against code before writing it.
- **Success criteria:** both files describe the system as it is; no aspirational content.

### F0.3 — Complete and pin `requirements.txt` · `DONE` (2026-07-20) · **P0** · S
Resolved — see CHANGELOG 2026-07-20. Cross-referenced every third-party import in the live tree
(`main.py` + terminal + all of `app/`): the real runtime deps are `pandas`, `numpy`, `PySide6`, and
`unlzw3` (lazy parser import). Split into `requirements.txt` (core, pinned), `requirements-dev.txt`
(pytest), and `requirements-optional.txt` (playwright, for the standalone downloaders only). Dropped the
unused `openpyxl`. Verified by a fresh-venv `pip install -r requirements.txt` followed by a full
`main.py` pipeline run (exit 0, no import errors), the desktop terminal (14 pages), and the test suite
(10 passing) — all green with only the pinned deps.
- **Problem:** lists `pandas`, `numpy`, `openpyxl` — unpinned. **`PySide6` is missing entirely** despite
  the desktop terminal hard-depending on it. A fresh clone cannot run the GUI.
- **Dependencies:** none.
- **Architecture changes:** pin exact versions; split `requirements.txt` / `requirements-dev.txt`.
- **Testing:** clean-venv install → `main.py --order-list` and `main.py --terminal` both start.
- **Success criteria:** reproducible environment from a fresh clone on a clean machine.

### F0.4 — Root junk & dead-module cleanup · `DONE` (2026-07-20) · **P1** · S
Resolved — see CHANGELOG 2026-07-20. Archived dead `app/ai/` (12), `app/backtesting/` (4),
`app/reports/` (2), `app/core/database.py`, and 3 dead root scripts to `archive/`; deleted 15 zero-byte
junk files + `files.txt`; added `tools/prune_reports.py` (kept newest 10 run-folders, removed 39);
consolidated the root `data/` tree into `database/` via `config.py` (`DATA_DIR` now aliases
`DATABASE_DIR`, `HISTORY_CSV` repointed to `psx_history_clean.csv`). Full pipeline + 10 tests + terminal
all verified green after. Original spec below.
- **Problem:** 15 zero-byte files in root (`1.1`, `100000`, `sma20`, `float`, `pd.DataFrame`, …) from
  stray shell redirects. `files.txt` (164 KB `dir /s` dump). Unused root scripts
  (`bafs_live_scanner.py`, `psx_scanner.py`, `psx_scanner_v0_backup.py`). `app/core/database.py` and
  `sqlite_database.import_csv_history_to_sqlite()` have **no callers**.
- **Latent trap:** `config.HISTORY_CSV` points at `psx_history.csv` — the **stale 5-day file**, not the
  real 2,457-day `psx_history_clean.csv`. Only dead code reads it today, but it will mislead someone.
- **Dependencies:** none.
- **Architecture changes:** delete junk; archive unused scripts; either fix `HISTORY_CSV` to point at
  the real file or remove it with its dead consumers. Rename `psx_history_clean.csv` → `psx_history.csv`
  once the stale files are gone.
- **Testing:** `main.py --order-list` + terminal launch + full scan all pass post-cleanup.
- **Success criteria:** no dead code paths; one unambiguous history file.

---

# PHASE 1 — Validation (P1) — *current phase*

**Rationale:** we have 2,457 days of history and a scoring engine whose weights have **never been
validated against it**. Every quality claim, and all future ML, depends on this. This is the highest-value
work in the entire roadmap.

### F1.1 — Historical signal replay engine · `TODO` · **P1** · **L** · ⭐ highest value
The unlock for the whole roadmap.

- **Problem:** `record_signals_v1` only saves signals **going forward**, for portfolio-selected stocks
  only (`save_only_selected=True`) — hence 4 rows total. At ~5 signals/day it would take years to
  validate the rules. Meanwhile 2,457 days of history sit unused.
- **Solution:** a replay harness that walks history day by day, runs the existing scoring chain using
  **only data available up to that day**, records every verdict, then evaluates outcomes against
  subsequent prices. Converts 4 data points into ~500k labeled examples.
- **Dependencies:** F0.1 (don't replay fabricated fundamentals into the training set).
- **Datasets:** `psx_terminal.db` (have it — 905k rows, 2016–2026).
- **Architecture changes:** the hard part is **look-ahead bias**. Engines currently receive a full
  history frame and a `latest_date`; must guarantee no engine reads beyond the as-of date. Requires an
  explicit as-of cutoff in `build_features_v3` and every downstream consumer, plus an audit that no
  engine touches future rows. Replay must be resumable and parallel-safe (2,457 × ~500 symbols).
  Reuse the scoring chain unchanged — no logic rewrite.
- **Testing:** **look-ahead bias test is non-negotiable** — replay day N with full history vs. history
  truncated at N must produce byte-identical verdicts. Determinism test: same day replayed twice =
  identical output. Spot-check ≥3 known events against raw archives.
- **Success criteria:** ≥100k labeled signals; a *reproducible* per-tier win rate; look-ahead test green.
  A believable number, even a disappointing one, is the deliverable.

### F1.2 — Real backtest validation report · `TODO` · **P1** · M
- **Dependencies:** F1.1.
- **Datasets:** replay output from F1.1.
- **Architecture changes:** none — `performance_analyzer_v1` already computes per-decision/sector/
  consensus breakdowns; it has simply never had data. Point it at replay output.
- **Testing:** reconcile aggregate win rate against a hand-computed sample; verify tier counts sum to total.
- **Success criteria:** honest published win-rate per verdict tier (STRONG BUY / BUY / WATCH) and per
  rule, with sample sizes and confidence intervals. **If the rules underperform, that is a valid and
  useful result — publish it.** Feeds the Backtest & Learning terminal tab (already built).

### F1.3 — Test suite for scoring & risk engines · `TODO` · **P1** · M
- **Problem:** `tests/` is empty. ~30 chained engines where an output-shape change can silently break
  something 15 steps downstream (already seen: blank `code` field crashed SQLite insert).
- **Dependencies:** F1.1 (gives real fixtures).
- **Datasets:** frozen historical slices as fixtures.
- **Architecture changes:** pytest + fixtures; golden-master tests over the chain.
- **Testing:** self-referential — target meaningful coverage of `ai_engine_v5`, `risk_management_engine_v2`,
  `portfolio_engine_v5`, `signal_consensus_engine`, and the parser (all format variants: zip, gzip,
  nested-zip, blank `code`).
- **Success criteria:** engine changes verifiable by test run, not eyeballing. CI-ready.

### F1.4 — Performance baseline · `TODO` · **P2** · S
- **Dependencies:** F1.1 (replay makes performance matter — 2,457 sequential days).
- **Architecture changes:** timing instrumentation per engine; identify hot spots. Note
  `save_daily_prices` does **row-by-row `INSERT OR REPLACE` in a Python loop** — will dominate replay cost.
- **Testing:** benchmark harness; regression threshold.
- **Success criteria:** documented per-stage timings; replay completes in a tolerable window.

---

# PHASE 2 — Service extraction & API (P2)

**Rationale:** unlocks non-local access, multi-user, mobile, and the chat/notification surfaces. Do it
*after* validation so we expose numbers we trust.

### F2.1 — Data-access layer extraction · `TODO` · **P2** · M
- **Dependencies:** F1.3 (tests to refactor safely).
- **Architecture changes:** repository pattern over SQLite; every engine reads through it rather than
  hand-rolled `sqlite3.connect` / `pd.read_csv`. Prerequisite for swapping the store (F3.1) without
  touching engine logic. Fixes the `database is locked` failures already seen under concurrency.
- **Testing:** repository unit tests with an in-memory DB; existing engine tests must pass untouched.
- **Success criteria:** zero direct DB access outside the repository layer.

### F2.2 — FastAPI service layer · `TODO` · **P2** · M
- **Dependencies:** F2.1, F1.2 (don't serve unvalidated numbers).
- **Architecture changes:** FastAPI wrapping existing engines — **no scoring/risk rewrites**. Endpoints:
  `/scan/today`, `/watchlist`, `/portfolio`, `/stock/{symbol}`, `/backtest/{rule}`. Reports become an
  API response shape, not just CSVs. Pydantic schemas as the contract.
- **Testing:** endpoint contract tests; response-shape snapshots; load test at expected concurrency.
- **Success criteria:** desktop terminal *could* run against the API instead of CSVs. `docs/API.md` created.

### F2.3 — Authentication · `TODO` · **P3** · M
- **Dependencies:** F2.2. **Strategic decision required:** single-user local vs. multi-tenant SaaS —
  this changes the data model materially (per-user portfolios), so confirm before building.
- **Architecture changes:** JWT/session auth; per-user data isolation; secrets out of source.
- **Testing:** authz tests (user A cannot read user B's portfolio); token expiry; injection/XSS probes.
- **Success criteria:** no unauthenticated access to user data; secrets never in the repo.

---

# PHASE 3 — Data expansion (P3)

**Rationale:** whole vision categories (fundamentals, dividends, DCF, Piotroski, Altman-Z) are
**blocked on data we do not have**. No amount of engineering substitutes for the dataset. This phase is
the real unlock for the "Fundamental Analysis" half of the vision — and it is mostly a data-sourcing
problem, not a coding one.

### F3.1 — Storage migration assessment · `TODO` · **P3** · M
- **Dependencies:** F2.1.
- **Problem:** SQLite already produced `database is locked` under a single concurrent writer. At
  multi-user + live data it fails.
- **Architecture changes:** evaluate PostgreSQL (+ TimescaleDB for time series). Repository layer (F2.1)
  makes this a driver swap. **Strategic decision required** (hosting/cost).
- **Testing:** parity test — identical query results SQLite vs. Postgres on the same dataset; concurrent
  writer test.
- **Success criteria:** decision documented with evidence; migration path proven on a copy.

### F3.2 — Corporate actions & dividend data · `TODO` · **P3** · L
- **Dependencies:** F3.1 (schema).
- **Problem:** **not present in the EOD files.** Without it, split/bonus-adjusted history is wrong —
  which silently corrupts every long-window indicator and backtest across a corporate action.
- **Datasets:** PSX announcements/notices — **needs a real source** (PSX website/data feed; licensing
  and reliability to be assessed).
- **Architecture changes:** corporate actions table; price-adjustment layer applied before indicators.
- **Testing:** verify a known split adjusts correctly end-to-end; indicator continuity across the event.
- **Success criteria:** adjusted price series verified against ≥3 known real corporate actions.

### F3.3 — Real fundamentals ingestion · `TODO` · **P3** · **XL** · replaces F0.1's quarantine
- **Dependencies:** F0.1, F3.1, F3.2.
- **Datasets:** financial statements for ~985 symbols — **the binding constraint**. Sources: PSX/company
  filings (PDF), commercial data vendor, or manual entry. **Strategic decision required:** this is a
  build-vs-buy call with real cost and legal implications; scope depends entirely on the answer.
- **Architecture changes:** fundamentals schema (quarterly + annual, point-in-time to avoid look-ahead
  in backtests — *reported-as-of*, not *restated*), ingestion pipeline, provenance tracking from F0.1.
- **Testing:** cross-check ≥10 symbols against published statements; point-in-time correctness test.
- **Success criteria:** real, sourced, provenance-tracked fundamentals. Only then may `LongTermEngine`,
  DCF, Graham, Piotroski, Altman-Z emit verdicts — computed, never typed.

---

# PHASE 4 — Machine learning (P4)

**Rationale:** currently zero ML. Deliberately placed *after* validation and data — an ML model needs
(a) a baseline to beat, (b) labeled data, (c) real features. F1.1 supplies (a) and (b); F3.3 supplies (c).
Building it earlier would mean fabricating sophistication — exactly what the rules forbid.

### F4.1 — Feature store & ML data pipeline · `TODO` · **P4** · L
- **Dependencies:** F1.1, F2.1.
- **Datasets:** replay output (F1.1) — labeled outcomes already produced by the backtest engine.
- **Architecture changes:** point-in-time-correct feature store; strict train/validation/test split by
  **time** (never random — that leaks future into past); walk-forward harness.
- **Testing:** leakage test (a model given only pre-cutoff data cannot see post-cutoff outcomes);
  reproducibility from a seed.
- **Success criteria:** a dataset a model can train on without leakage. Leakage test green.

### F4.2 — First ML model · `TODO` · **P4** · L
- **Dependencies:** F4.1, F1.2 (the baseline to beat).
- **Scope discipline:** **one** well-scoped model, not the vision's full list (XGBoost/LSTM/GRU/
  Transformer/Prophet/ARIMA/AutoML) at once. Recommended first target: a classifier predicting the
  rule engine's own **false positives** — narrow, immediately useful, and honestly evaluable. Additional
  model families only after the first is in production and measured.
- **Datasets:** F4.1 output.
- **Architecture changes:** model registry + versioning; inference behind the repository/service layer;
  every prediction carries model version + confidence + **the features that drove it** (explainability
  is a hard requirement — SHAP or equivalent, not a black box).
- **Testing:** walk-forward validation; **must beat the F1.2 rule baseline on out-of-sample data or it
  does not ship**; stability across regimes (2018 bear vs. 2020 covid vs. 2026).
- **Success criteria:** measurable out-of-sample improvement over the rule baseline, with explainable
  per-prediction reasoning. **If it does not beat the baseline, publish that and keep the rules** — a
  negative result is a legitimate outcome, not a failure to hide.

### F4.3 — Learning engine (real) · `TODO` · **P4** · M
- **Dependencies:** F4.2.
- **Note:** `strategy_optimizer_self_learning_v2` already does sample-gated weight adjustment — good
  design, but it has had no data to learn from. F1.1 fixes that; this item extends it to model retraining.
- **Architecture changes:** prediction/outcome store; drift detection; retraining triggers; never delete
  learning history.
- **Testing:** drift detection fires on synthetic drift; retraining improves or holds accuracy.
- **Success criteria:** measurable accuracy tracking over time; no silent degradation.

---

# PHASE 5 — Live data (P5)

### F5.1 — Live market data service · `TODO` · **P5** · XL
- **Dependencies:** F3.1 (SQLite cannot take tick volume), F2.2.
- **Datasets:** **needs a real-time PSX feed — does not exist in this project today.** Vendor/licensing
  is a **strategic decision** and likely a paid commercial agreement. Everything "live" in the vision
  (Live Dashboard, Market Depth, realtime alerts, intraday scanners) is blocked on this single item.
- **Architecture changes:** streaming ingestion; hot/cold storage split; websocket push; cache layer.
- **Testing:** replay a recorded session; failover; latency budget.
- **Success criteria:** sub-second quotes without breaking EOD engines. EOD remains the fallback.

---

# PHASE 6 — Intelligence surfaces (P6)

Each is substantial and scoped when its turn comes. All depend on F2.2.

| Feature | Priority | Cx | Key dependency / blocking dataset |
|---|---|---|---|
| **F6.1** News Intelligence Service | P6 | L | Needs a news source + licensing. Sentiment must be measured against price outcomes, not asserted. |
| **F6.2** Sentiment Engine | P6 | L | F6.1. Urdu/English mixed-language handling is a real, underestimated problem. |
| **F6.3** Notification Service | P6 | M | F2.2. Telegram/email/push. Delivery guarantees + rate limits. |
| **F6.4** Watchlists | P6 | S | F2.3 (per-user data). Small, high user value. |
| **F6.5** Paper Trading Service | P6 | M | F5.1 for realistic fills; EOD-approximate is possible sooner. Order-execution simulator exists as a seed. |
| **F6.6** Mobile PWA | P6 | M | F2.2. Thin client — no logic duplication. |
| **F6.7** AI Chat Service | P7 | L | F2.2 + most engines. Must answer **from real system output**, never generate market claims of its own. Highest hallucination risk in the platform — needs strict grounding. |

---

## Cross-cutting standards (every feature, every phase)

- **Explainability:** every recommendation carries a traceable reason. A verdict without a reason chain
  is a defect, not a feature.
- **Uncertainty:** state sample size and confidence. Never imply more certainty than the data supports.
  Follow the existing sample-gating pattern in `strategy_optimizer_self_learning_v2`.
- **Provenance:** every number is traceable to a real source. `REAL` / `SEED` / `ABSENT` — never blur them.
- **Additive change:** extend the engine chain; never break a working engine. Trace all downstream
  consumers before changing an output shape.
- **Backward compatibility:** the desktop terminal must keep working through every refactor.
- **On completion of any feature:** update `ROADMAP.md`, `CHANGELOG.md`, architecture docs, DB docs, and
  API docs if affected. Documentation only when it has real content — never empty placeholders.

---

## Immediate execution order

1. ~~**F0.1** — quarantine fabricated fundamentals~~ ✅ **DONE 2026-07-20**
2. ~~**F0.2** — real architecture + schema docs~~ ✅ **DONE 2026-07-20**
3. ~~**F0.4** — junk/dead-code cleanup~~ ✅ **DONE 2026-07-20**
4. ~~**F0.3** — pin/scope requirements, add PySide6~~ ✅ **DONE 2026-07-20**
5. **F1.1** — historical signal replay ⭐ *(next — the roadmap's key unlock)*
6. **F1.2** — real backtest validation
7. **F1.3** — test suite *(seeded: `tests/` now exists with the F0.1 provenance suite + pytest)*

**Phase 0 (Integrity) is COMPLETE.** Next: **Phase 1 — F1.1 historical signal replay**, the highest-value
item in the roadmap. It is complexity **L** and its look-ahead-bias guarantee is non-trivial — a good
point to align on approach before diving in.

Items marked **strategic decision required** (F2.3 multi-tenancy, F3.1 storage, F3.3 fundamentals
build-vs-buy, F5.1 live feed vendor) will be raised for a decision rather than assumed — each carries
cost, licensing, or data-model consequences that are not an engineering call.
