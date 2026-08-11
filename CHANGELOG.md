# Changelog

All notable changes to PSX AI Scanner.

Format: reverse-chronological. Each entry states what changed, why, and how it was verified.
Roadmap item IDs (e.g. `F1.1`) refer to [ROADMAP.md](ROADMAP.md).

---

## 2026-08-11 (Deploy Priority 1 · item 2) — Render.com deployment prep (git-commit-on-refresh)

### Why
Make the read-only API publicly reachable (HTTPS) for the mobile/web clients, on Render's free tier,
with data synced from the local PC via git (the user's chosen mechanism: simplest, free, no extra infra).

### Added
- **`tools/publish_outputs.py`** — git-commit-on-refresh publisher. Force-commits **only** the four
  small artifacts the API serves (`daily_signal.json`, `sentiment_cache.json`, `top_buys.csv`,
  `full_market_scan.csv`, + tiny `metadata.json`) and pushes to `origin`, which triggers Render's
  auto-deploy. Non-fatal by design: no repo / no origin / nothing-changed all return 0; a real push
  failure returns 2. Never touches heavy data.
- **`.gitignore`** — commits code + the whitelisted outputs; ignores the SQLite DB, `historical_files/`,
  `psx_history*.csv`, model weights, venv, caches, logs, and frontend/mobile build dirs. Verified in an
  isolated temp repo: `git add .` stages **only** code + the 5 outputs, nothing heavy.
- **`render.yaml`** — Render Blueprint: one free Python web service, `pip install -r
  requirements-api.txt`, `uvicorn api.main:app --host 0.0.0.0 --port $PORT`, health check `/health`,
  `autoDeploy: true`, env vars (`PSX_API_KEY`/`ANTHROPIC_API_KEY` marked `sync:false` = dashboard-only).
- **`main.py --publish`** and **`tools/refresh_sentiment.py --publish`** — run the publisher after a
  scan / sentiment refresh (best-effort; never fail the scan).
- **`docs/DEPLOYMENT.md`** — full step-by-step: create GitHub repo + first commit, connect to Render
  via Blueprint, set env vars, verify with `curl`, and schedule `--publish` runs.
- **`tests/test_publish_outputs.py`** — 6 tests against a real temp git repo (non-fatal when no repo,
  commits without origin, no-op when unchanged, new commit when changed, missing files skipped).

### Changed
- **`requirements-api.txt`** — completed and made the sole Render install target. Added the missing
  **pandas/numpy** (imported at module load — the API would otherwise crash on Render) and **anthropic**
  (for `/query`). Deliberately **not** `requirements.txt`, which pulls in PySide6 (desktop Qt, unneeded
  and heavy for a headless service). Confirmed no torch/transformers/PySide6/feedparser/playwright.
- **`.env.example`** — documents `PSX_API_KEY` and `PSX_CORS_ORIGINS` alongside `ANTHROPIC_API_KEY`.

### Verified
- `.gitignore` isolation test: only code + 5 outputs staged; DB/historical/.env/venv/caches/backtests
  all ignored (`git check-ignore` confirms each).
- FastAPI smoke test via `TestClient`: `/health` 200 (all data_files present), `/signal` 401 without
  key / 200 with key (verdict BEARISH), `/opportunities` 200. Importing `api.main` pulls no
  PySide6/torch/transformers.
- `render.yaml` parses; secrets correctly marked dashboard-only. Publisher runs non-fatally in the
  current (non-git) tree. Full suite **41 passed** (35 prior + 6 new).

### Not done here (requires the user's own accounts — left as exact instructions in docs/DEPLOYMENT.md)
- Creating the GitHub repo, connecting Render, setting env-var values, and the first push/deploy. No
  git repo was initialised and nothing was pushed, per the user's instruction.

---

## 2026-08-11 (Deploy Priority 1 · item 1) — Decouple news sentiment from the scan/API path

### Why
Deploying the FastAPI backend to a free-tier host (Render, 512MB RAM) is impossible while any request
or scan path can trigger a ~500MB transformer load (`cardiffnlp/twitter-roberta-base-sentiment`,
`torch`+`transformers` ~2GB). The model had to move to a single scheduled job; everything else must
only read the cache it writes.

### Added
- **`tools/refresh_sentiment.py`** — standalone refresher the scheduler calls (2×/day). Runs
  `run_news_sentiment_engine()` → writes `database/ai_learning/sentiment_cache.json`. Lock file
  (`database/ai_learning/.sentiment.lock`, 20-min stale override) prevents overlapping model loads;
  appends to `logs/sentiment_refresh.log`. Exit codes: `0` success/graceful cache-fallback, `1` crash,
  `2` no headlines and no cache to fall back to.
- **`app/engines/news_sentiment_engine_v1.py`** — new public `read_cached_sentiment()`: read-only cache
  access that never touches the network or loads the model. Used by all consumers.
- **`main.py --refresh-news`** — explicit opt-in to load the model and refresh inline during a scan.
- **`docs/DEPLOYMENT.md`** — decoupling architecture diagram, the refresher, and `schtasks` (Windows,
  08:00/15:00 PKT) + `cron` (UTC 03:00/10:00) schedule examples.
- **`tests/test_sentiment_decoupling.py`** — 5 tests: cache read imports no model; missing-cache →
  None; static guard that `api/main.py`, `nl_query_engine.py`, `daily_signal_engine.py` never import
  torch/transformers; refresher exit codes 0 and 2.

### Changed
- **`main.py`** normal scan no longer loads the transformer. It now READS the cache and prints its age
  (`cache_age_hours`, `stale` flag at >12h). Model load happens only under `--refresh-news` or in the
  standalone refresher.

### Verified
- `python tools/refresh_sentiment.py` → `source=live headlines=280 matched=19 tickers=16 model=ok`,
  exit 0, lock released, log written.
- Default read path and importing `main.py` pull in **no** `torch`/`transformers` (checked via
  `sys.modules`).
- `--refresh-news` present in `--help`. Full suite **35 passed** (30 prior + 5 new).

---

## 2026-07-20 (Phase 2 #6) — Flutter mobile app

### Added — `mobile/` (Flutter, Android + iOS)
Native mobile client mirroring the React dashboard, talking to the same FastAPI backend.
- **Screens:** Login/Setup (API base URL + key → `flutter_secure_storage`), Home (colour-coded verdict
  card, confidence, breadth/sentiment chips, reasons, top-opportunity pills), Opportunities (cards with
  decision badges, buy prob, stop, targets), Stock Lookup (search → price/scoring/sentiment), AI Chat
  (bubbles; billing/other errors shown as a red bubble, never crashes). Bottom-nav shell + settings.
- **Requirements met:** `http` for API calls; `flutter_secure_storage` for the key; dark theme matching
  the React palette; **pull-to-refresh** on Home and Opportunities (`RefreshIndicator`); a dedicated
  **"Not connected"** state (wifi-off icon + base URL + same-WiFi hint) distinguishing connection
  failures from HTTP errors; Android manifest allows cleartext to reach `http://<PC-IP>:8000`;
  `minSdk` bumped to 23 for secure storage.
- **Verified:** `flutter analyze` → **No issues found**; `flutter build apk --debug` →
  **app-debug.apk built successfully** (JDK path fixed to Adoptium 17). iOS shares the same Dart/UI;
  an iOS build needs a Mac (not available here).

---

## 2026-07-20 (Phase 2 #5) — React web dashboard

### Added — `frontend/` (Vite + React)
Dark, trading-terminal-styled, mobile-responsive dashboard over the FastAPI backend. Four sections plus
settings:
- **Home** — big colour-coded verdict card (BULLISH/BEARISH/NEUTRAL), confidence %, breadth + sentiment
  chips, the three reasons, top-opportunity pills, generated time.
- **Top Opportunities** — table from `/opportunities` (symbol/company, sector, decision badge, close,
  change %, buy prob, stop, targets); horizontal-scroll on mobile.
- **Stock Lookup** — search box → `/stock/{ticker}`; price, rule scoring, and news sentiment cards; clean
  404 handling.
- **AI Chat** — calls `/query`; on failure (e.g. the Anthropic billing error) it shows a red error bubble
  and keeps working — verified, does not crash.
- **Settings/login** — API base URL + `X-API-Key`, saved to `localStorage`, with a "Test connection"
  button. Base URL also configurable via `frontend/.env` (`VITE_API_BASE_URL`).

- Dark theme consistent with the desktop terminal; sidebar collapses to a hamburger drawer under 820px.
  axios client injects the key from localStorage; loading spinners and error boxes on every page.
- **Tested live**: `npm install` → `vite dev` against the running API; captured desktop Home,
  Opportunities table, Stock lookup, mobile (390px), and the graceful chat-error screenshots. Run with
  `cd frontend && npm run dev` (needs the API on :8000 and a key set in Settings).

---

## 2026-07-20 (Phase 2 #4) — FastAPI backend

### Added — HTTP API (`api/main.py`)
Thin, read-only HTTP layer over the scanner's existing output (no recomputation). Endpoints:
- `GET /health` — liveness + which data artifacts are present (no auth).
- `GET /signal` — today's daily market signal (`daily_signal.json`).
- `GET /stock/{ticker}` — price + rule scoring (from `full_market_scan.csv`) + news sentiment (from
  `sentiment_cache.json`) for one symbol; 404 if not in today's scan.
- `GET /opportunities?limit=N` — `top_buys.csv` as JSON records (NaN → null).
- `POST /query {"question": "..."}` — forwards to the NL engine; full JSON answer by default, or
  `?stream=true` for a `text/plain` streamed response.

- **Auth:** a single shared API key via the `X-API-Key` header (`PSX_API_KEY` env, dev fallback). The
  simple gate requested — a real per-user JWT/auth system stays deferred as the strategic F2.3 item.
- **CORS** middleware (origins via `PSX_CORS_ORIGINS`, `*` for dev) for the future React/Flutter clients.
- **Clean JSON errors, never tracebacks:** exception handlers wrap every failure as
  `{"error", "detail"}`. Verified even under a real upstream failure — the `/query` billing error surfaces
  as a clean HTTP 502 JSON, and empty input as a 422 validation error.
- Reuses the engine's file locations/helpers (single source of truth). `requirements-api.txt` added.

**Tested:** all endpoints via `TestClient` (health, auth on/off → 401, signal, opportunities, stock
valid/404, query error path, validation) **and** as a real `uvicorn` server via `curl`. Run with
`uvicorn api.main:app --port 8000`, header `X-API-Key: <key>`.

**Architectural note:** the API reads the report files directly. The repository-layer extraction (F2.1)
that would let the store swap to Postgres without touching endpoints is still pending — fine for a
read-only file-backed API today, revisit before F3.1.

---

## 2026-07-20 (Phase 2 #3) — natural-language assistant

### Added — NL Query Engine (`app/engines/nl_query_engine.py`)
- Grounded question-answering over the scanner's own output via the Anthropic API (`claude-sonnet-4-6`,
  the model the user specified). Loads a compact snapshot before every query — `daily_signal.json`,
  `sentiment_cache.json`, `top_buys.csv`, and **summary statistics only** from `full_market_scan.csv`
  (breadth, decision distribution, top-scored names, sector strength — not all ~465 rows).
- Streams responses (`client.messages.stream`), handles English and Urdu, and puts the stable snapshot
  in a cached system block so repeated questions in a session reuse it cheaply.
- **Grounding guardrails** in the system prompt: answer only from the snapshot; never invent prices/
  targets/forecasts; state plainly when the data doesn't contain the answer; label it decision-support
  (rule-based EOD scan), not financial advice or a trained model.
- Auth via `ANTHROPIC_API_KEY` in a git-ignored `.env` (python-dotenv); key never hard-coded. Added
  `.env.example`, `.gitignore` entry, and `anthropic`/`python-dotenv` to `requirements-optional.txt`.
- **`tools/ask.py`**: REPL + one-shot CLI (`python tools/ask.py "is today good for buying?"`).

### Added — "AI Assistant" terminal tab (`institutional_terminal_v1.py`)
- Chat history display, input box + Send (Enter to send), responses streamed in real time via a
  `ChatWorker(QThread)` so the UI never blocks. Terminal now 16 tabs. Reads the same `.env` key.

### Status
- Engine, CLI, and tab are built and structurally verified (context assembly, compile, terminal
  instantiation, and a clean no-key error path all pass). **The live 3-question test is pending the
  user's `ANTHROPIC_API_KEY` in `.env`** — no key/`ant` credential is available in this environment,
  and API keys are handled by the user, not committed or entered by the assistant.

---

## 2026-07-20 (Phase 2 #2) — daily market signal

### Added — Daily Market Signal Engine (`app/engines/daily_signal_engine.py`)
- Combines the rule-scoring output with the news sentiment tilt into one daily verdict
  (BULLISH / BEARISH / NEUTRAL) + confidence + three plain-English reasons + top opportunities.
- Breadth is measured as **advancers vs decliners** from `full_market_scan.csv` (`change_pct`) and the
  BUY/WATCH decision distribution — both real. Deliberately **no "% above 20MA" reason**: the report
  carries no moving-average column, so inventing that stat would break the no-fabrication rule.
- Composite bullishness = advance-ratio (primary) + actionable-ratio bonus + a small (0.08) sentiment
  tilt. Sentiment is intentionally light because its predictive value is not yet validated — a unit test
  (`test_bearish_day_sentiment_does_not_flip`) pins that news alone can't flip a directional-breadth day.
- Output → `database/ai_learning/daily_signal.json`. Integrated into `main.py` after the news step
  (non-blocking). 7 unit tests in `tests/test_daily_signal.py`; full suite 30 passing.
- First live run (2026-07-13): **BEARISH, confidence 0.69** — 70% of stocks declined, 0 rated BUY/WATCH,
  mild positive news (MCB) insufficient to offset. Top opportunities: MCB, CNERGY, AHL, JSCL, FEM.

### Added — "Market Signal" terminal tab (`institutional_terminal_v1.py`)
- New first tab (landing view): large colour-coded verdict (green/red/gray), confidence, the three
  reasons, top-opportunities list, and generated/updated time + sentiment counts. Reads
  `daily_signal.json`. Terminal now 15 tabs.

---

## 2026-07-20 (Phase 2 #1) — news sentiment engine

### Added — News Sentiment Engine V1 (`app/engines/news_sentiment_engine_v1.py`)
- Fetches business headlines from free RSS feeds (Dawn Business, ARY) via `feedparser` — no API key.
- Matches headlines to PSX tickers from `database/company_directory/companies.csv`, precision-first:
  ALL-CAPS symbol mentions (real "OGDC"/"PPL") and multi-word company names ("K ELECTRIC") match;
  title-case English words, generic single-word names, and common/political acronyms (PPP, PTI, SBP…)
  are rejected. Locked by `tests/test_news_sentiment.py` (6 tests).
- Scores sentiment with the pretrained `cardiffnlp/twitter-roberta-base-sentiment` transformer
  (a model we USE, not one we trained), aggregated to a per-ticker BULLISH/BEARISH/NEUTRAL verdict.
- Caches to `database/ai_learning/sentiment_cache.json` with a timestamp; falls back to the last cache
  if feeds are unavailable (verified: dead feed → `source: cache_fallback`).
- Integrated into `main.py` as an **optional, non-blocking** step: it runs only if feedparser/
  transformers are importable and any failure (missing dep, offline, model error) is caught and logged
  so the core scan never breaks. Toggle off with `--skip-news`. Heavy deps (feedparser, transformers,
  torch — ~2GB, ~500MB model) are declared in `requirements-optional.txt`, kept OUT of core requirements.
- First live run: 222 headlines → 10 tickers with news; MCB BULLISH (+0.62) from a profit headline,
  the rest NEUTRAL (a quiet news day; formal news reads neutral to this model).

**Caveat:** the sentiment signal's *predictive value for PSX prices is not yet validated* — that needs
the same outcome-correlation treatment the scoring rules got in F1.2. Until then it is an information
signal, not a proven edge. Residual matcher false positives remain for short acronyms appearing in
unrelated articles (low harm — they scored neutral).

---

## 2026-07-20 (F1.2) — accurate multi-horizon validation

### Added — F1.2: measure accurately (no rule changes)
- **Recorded signal-day close** (`signal_close`) in the replay schema so forward returns can be measured
  from a market-on-close entry basis that always fills — isolating predictive power from the limit-entry
  fill question.
- **`app/engines/backtesting/replay_horizon_analyzer_v1.py`**: per-tier win rate at 3/5/10-day horizons
  (close-to-close forward return from `signal_close`), 95% Wilson CIs, plus limit-entry fill rate. Forward
  arithmetic locked by `tests/test_replay_horizons.py` (4 tests).
- **Dense full-history replay**: 2,387 dates (all 2016-08→2026-07), **819,282 signals, 4,316 actionable
  (3,027 BUY + 1,289 WATCH)** — 7x the F1.1 sample. File `database/backtesting/replay_signals_dense.csv`.

### Result — corrected: the rule engine has a small but statistically real edge
Win rate (fwd return > 0), 95% CI:

| tier | n | 3-day | 5-day | 10-day | avg 10d return | fill rate |
|---|---|---|---|---|---|---|
| BUY | 3027 | 49.3% [47.5,51.1] | 49.6% [47.8,51.4] | 51.8% [50.0,53.6] | +1.71% | 97.9% |
| WATCH | 1289 | 49.9% | 49.4% | 51.4% | +2.58% | 94.1% |
| AVOID | ~815k | 46.4% [46.3,46.5] | 46.8% | 47.3% [47.2,47.5] | +1.16% | 96.3% |

BUY/WATCH beat AVOID by ~3–4.5 pts of win rate at every horizon with **non-overlapping CIs**, and ~2x the
average forward return at short horizons; the edge grows with horizon. **This corrects the F1.1
preliminary read** (which found no clear edge) — the difference was the 7x sample plus measuring
close-to-close predictive power instead of the target/stop-resolved outcome on 620 signals.
**Caveats:** BUY≈WATCH (tier split adds little); **STRONG BUY & ACCUMULATE never fire in 10 years**; edge
is modest; rules were hand-tuned so this is effectively in-sample (true out-of-sample walk-forward is F4.x);
entry-fill is NOT a problem (94–98% fill), resolving that F1.1 caveat. **No scoring rules were changed.**

---

## 2026-07-20 (F1.1) — historical signal replay

### Added — F1.1: historical replay engine + first rule-engine validation
- **`tests/test_lookahead_replay.py`** (3 tests, passing): the standing look-ahead guard. Proves feature
  values at date D are **byte-identical** (`check_exact=True`) whether computed over full history or over
  history truncated at D — validating the harness's precompute-once optimization as leak-free.
- **`app/engines/backtesting/replay_engine_v1.py`**: walks history day-by-day, runs the verified-pure
  scoring→verdict subset on each as-of snapshot, records every symbol's verdict in the signal-history
  schema, and labels outcomes against future prices. Runs only the scoring subset (no portfolio/lifecycle/
  reporting/company-master/live-signal writes) and outputs to its own `database/backtesting/replay_signals.csv`
  — the live `signal_history.csv` is never touched.
- **`label_outcomes_grouped`**: pre-groups prices by symbol to reuse `BacktestEngineV1.evaluate_signal`'s
  exact outcome logic without its per-signal full-frame scan — ~12x faster (237 vs 19 sig/s), verified
  **0 outcome mismatches** vs the stock engine.
- **`tools/run_replay.py`**: CLI (`--stride/--start/--end/--max-dates/--decisions/--resume/--no-label`).

### Result — first real validation (preliminary, weak/negative)
First replay: 341 dates (2016-11→2026-06), **116,998 labeled closed signals** (vs 4 before). Win-rate
(5-day return>0, 95% CI): BUY 38.8% [34.4,43.3] (n=449), WATCH 40.4% [33.3,47.8] (n=171), AVOID 36.1%
[35.9,36.4] (n=116,378). **The rule engine does not convincingly beat its AVOID baseline** — BUY's CI
overlaps AVOID, ordering isn't monotonic (WATCH>BUY), and 5-day avg return is negative across all tiers.
Published honestly per project rule 9. **Caveats to resolve before any firm conclusion (F1.2):** only 620
actionable signals in ~10y (rules ~99% AVOID); zero STRONG BUY/ACCUMULATE in sample; outcome model assumes
entries always fill (signal-day close not yet recorded); fixed 5-day horizon; stride-7 sampling.

---

## 2026-07-20 (later still) — F0.3 dependencies

### Fixed — F0.3: requirements pinned, scoped, and completed
- **Cross-referenced every third-party import** in the live tree (`main.py`, `institutional_terminal_v1.py`,
  and all of `app/`). Actual runtime deps: `pandas`, `numpy`, `PySide6`, `unlzw3` (lazily imported by
  `app/core/parser.py` for genuine UNIX-LZW `.Z` files).
- **`requirements.txt`** now pins exactly those, at verified-working versions on Python 3.14:
  `pandas==3.0.3`, `numpy==2.5.0`, `PySide6==6.11.1`, `unlzw3==0.2.3`. Previously it listed unpinned
  `pandas/numpy/openpyxl` and **omitted `PySide6` entirely** — a fresh clone could not launch the GUI.
- **Dropped `openpyxl`** — no live code imports it or does any Excel I/O.
- **Split by purpose:** `requirements-dev.txt` (`pytest==9.1.1`) and `requirements-optional.txt`
  (`playwright==1.61.0`, needed only by the standalone `psx_*_downloader.py` utilities, which are not part
  of the live pipeline).
- **Verified in a fresh venv:** `pip install -r requirements.txt` pulled only the 4 deps + legitimate
  transitives (no openpyxl, no playwright, none of the unrelated global-env packages). Then, on that venv:
  a full `main.py` pipeline run (exit 0, zero import errors), the desktop terminal (14 pages, offscreen
  Qt), and `pytest` (10 passing) — all green. Confirms no engine has a hidden third-party dependency.

**Phase 0 (Integrity) is now complete** (F0.1–F0.4 all done). Next is Phase 1 / F1.1 (historical replay).

---

## 2026-07-20 (later) — F0.4 cleanup + F0.2 docs

### Changed — F0.4: repository cleanup
- **Archived dead code** to `archive/` (moved, not deleted — see `archive/README.md`), all confirmed
  zero live importers via grep:
  - `app/ai/` (12 files) → `archive/dead_ai/` — abandoned parallel AI tree, superseded by `app/engines/`.
  - `app/backtesting/` (4) → `archive/dead_app_backtesting/` — live one is `app/engines/backtesting/`.
  - `app/reports/` (2) → `archive/dead_app_reports/` — live one is `reporting_engine_v3` + dashboards.
  - `app/core/database.py` → `archive/dead_core/` — dead CSV-history helper, only reader of the stale
    `HISTORY_CSV`.
  - `bafs_live_scanner.py`, `psx_scanner.py`, `psx_scanner_v0_backup.py` → `archive/dead_root_scripts/`.
- **Deleted root junk:** 15 zero-byte stray files (`1.1`, `100000`, `sma20`, `float`, `pd.DataFrame`, …)
  with a size==0 guard, plus `files.txt` (164 KB stray `dir /s` dump).
- **Added `tools/prune_reports.py`** — keeps the newest 10 timestamped scanner run-folders and removes
  the rest; never touches `reports/latest/` or the named category folders. First run removed 39 of 49
  run-folders. Dry-run by default; `--apply` to delete.
- **Consolidated the data tree (`config.py`):** the near-empty root `data/` tree (only a stale 5-day
  `psx_history.csv`) was archived to `archive/dead_data_tree/`. `DATA_DIR` now aliases `DATABASE_DIR`,
  `RAW_DATA_DIR` points under `database/`, and `HISTORY_CSV` was repointed from the stale
  `psx_history.csv` to the real `psx_history_clean.csv` (nothing live read the old value).
- **Untouched** (as scoped): `main.py`, `institutional_terminal_v1.py`, `app/engines/`, `app/core/*`
  (except the dead `database.py`), `psx_terminal.db`, `psx_history_clean.csv`.
- **Verified:** `main.py` imports, all 10 tests, terminal (14 pages), and a full end-to-end pipeline run
  (reports + dashboard regenerated) all green after cleanup. DB backed up to `database/backups/` first.

### Added — F0.2: real documentation (was 0-byte placeholders)
- `docs/DATABASE_SCHEMA.md` (98 lines) — actual `daily_prices` schema, indexes, the DDMMMYYYY-text
  date caveat, CSV/state-file map; all counts read live from the DB (905,195 rows / 2,457 dates / 985
  symbols).
- `docs/PROJECT_ARCHITECTURE.md` (123 lines) — entry points, `app/` layer map, the 20-stage `main.py`
  pipeline in execution order, outputs, terminal wiring, and direction of travel.

---

## 2026-07-20

### Fixed — F0.1: fabricated fundamental data quarantined (P0)
The most severe defect in the codebase: `create_fundamentals.py` wrote hardcoded, invented financials
for 10 symbols, and `LongTermEngine` turned them into live investment verdicts. Before this fix,
`reports/latest/long_term.csv` asserted (among others) *"LUCK — fair value 980.00, upside 113.29%,
DEEPLY UNDERVALUED, STRONG BUY, confidence 95%"* and *"EFERT — STRONG BUY, confidence 95%"* — all
derived from numbers that existed only as a Python string literal. Violated the project's first rule.

- **Provenance-aware loader** (`app/engines/long_term/fundamental_loader.py`): every fundamentals row
  now carries `data_provenance` ∈ {`REAL`, `SEED`, `ABSENT`}. A file with no provenance column is
  treated as `SEED` (un-tradeable) — we cannot vouch for un-labelled hand-maintained numbers. The
  loader no longer raises on a missing/empty file; "no fundamentals" is a valid state, not a crash.
- **Authoritative provenance gate** (`app/engines/long_term/long_term_engine.py`): `LongTermEngine`
  refuses to emit a verdict, fair value, or confidence for any row that is not `REAL`. Implemented at
  two layers — a per-row early return, plus `enforce_provenance_gate()` which overwrites *every*
  long-term output column for non-`REAL` rows. The DataFrame-level gate is required because
  input-origin columns (a fabricated `fair_value`) survive `pd.concat`/`remove_duplicate_columns` and
  would otherwise leak the fabricated number — a bug the test suite caught before it shipped. Gated
  rows get confidence=0 and fair_value=0, so `filter_meaningful_long_term_rows` drops them entirely.
- **Quarantined the fabricated data**: `create_fundamentals.py` and the fabricated `fundamentals.csv`
  moved to `archive/fabricated_fundamentals/` with a README. Do not restore.
- **Tests** (`tests/test_fundamentals_provenance.py`, 10 cases, all passing): non-REAL provenance
  yields no verdict; REAL still scores; gated rows are dropped by the report filter; missing file
  doesn't raise; unmatched symbols labelled ABSENT; no-provenance file defaults to SEED. Also
  bootstrapped the test harness (`tests/__init__.py`, `tests/conftest.py`, pytest 9.1.1).
- **Verified end-to-end**: a full `main.py` pipeline run regenerated all reports; `long_term.csv` went
  from 10 fabricated verdicts to empty (header only), and no fabricated verdict language remains
  anywhere in `reports/latest/`. DB backed up to `database/backups/` before the run.

**Net effect:** with no real fundamentals present, the long-term report is now correctly empty rather
than fabricated. It stays that way until real fundamentals are ingested (F3.3).

---

## 2026-07-17

### Added
- **Desktop terminal: 5 new tabs** (`institutional_terminal_v1.py`, 9 → 14 pages). Eight engine outputs
  were being computed and written to disk every run but were unreachable from the GUI.
  - **Full Market** — every scanned symbol with AI score/verdict, filterable by symbol/company/sector.
    Previously every view showed only curated top-N subsets; there was no way to see the full universe.
  - **Positions** (`trade_lifecycle.csv`) and **Exit Signals** (`exit_intelligence.csv`) — core trading
    state, previously invisible.
  - **Live Monitor** — open-position P/L from `live_portfolio_monitor_v1`.
  - **Backtest & Learning** — win-rate by verdict tier + self-learning optimizer weight state.
  - **AI Assistant brief** — market narrative panel added to the existing Command Center page.
  - Verified by headlessly instantiating `TerminalWindow` and confirming each tab loads real data from
    existing report files — not merely that the code compiles.
- **`full_market_scan.csv`** report artifact (`reporting_engine_v3.py`) — full `final_df` without the
  `.head(100)` truncation applied to `top_buys.csv`. Backs the Full Market tab.
- **`CLAUDE.md`** — project instructions grounded in verified current state.
- **`ROADMAP.md`** — phased implementation roadmap; every feature carries priority, dependencies,
  complexity, required datasets, architecture changes, testing strategy, success criteria.
- **`CHANGELOG.md`** — this file.

### Fixed
- **472 trading days missing from the database** (`F1` data integrity). `psx_terminal.db` and
  `psx_history_clean.csv` covered only 2018-03-19 → 2026-07-13 despite the archive holding data from
  2016. Root cause: `historical_backfill_log.csv` showed 467 files failing with `"File is not a zip
  file"` — those files are plain **GZIP** despite a `.Z` extension, and the backfill had never been
  re-run after `parser.py` gained GZIP support. Two further days (2023-05-17/18) use a nested-folder ZIP
  layout. Re-ran the backfill and recovered all of them; regenerated `psx_history_clean.csv` from the
  updated DB.
  - **Coverage: 1,988 → 2,457 trading days** (2016-08-01 → 2026-07-13); 738,285 → 905,195 rows.
  - Only 2026-07-14/15/16 remain unimported — normal daily-import lag, not a defect.
  - `psx_terminal.db` and `psx_history_clean.csv` backed up to `database/backups/` before the write.
- **`save_daily_prices` crash on blank `code` field** (`app/core/sqlite_database.py`). `int(row.get("code"))`
  raised `ValueError: invalid literal for int() with base 10: ''` for instruments with an empty (not
  NaN) code — hit on 2021-10-25 via `MZNPETF` and `P05PIB151025`. Blank strings now map to `NULL`
  alongside NaN. Affected historical backfill and would affect future daily imports of similar
  bond/ETF instruments.

### Changed
- **Archived 27 unused legacy engine files** from `app/engines/` → `archive/legacy_engines/`
  (superseded versions: `ai_engine_v3`/`v4`, `portfolio_engine` v1–v4, `decision_engine` v1,
  `feature_builder` v1–v2, `reporting_engine` v1–v2, `performance_dashboard` v1–v2, and others).
  Confirmed unused by tracing `main.py`'s full **transitive** import graph plus a repo-wide grep — not
  just direct imports. `app/engines/` : 66 → 39 files. Archived rather than deleted; see
  `archive/legacy_engines/README.md`. `main.py` and the terminal both verified working afterward.

### Known issues (see ROADMAP.md)
- **`create_fundamentals.py` writes fabricated financial data** (`F0.1`, P0). Hardcoded invented EPS /
  book value / ROE / fair value for 10 of 985 symbols, flowing through `LongTermEngine` into live
  output — `reports/latest/long_term.csv` currently asserts *"LUCK — fair value 980.00, upside 113.29%,
  DEEPLY UNDERVALUED, STRONG BUY, confidence 95%"* from numbers that exist only as a Python string
  literal. Violates the project's never-fabricate rule. Quarantine is the next scheduled work item.
- **Rule weights are unvalidated** (`F1.1`, P1). `signal_history.csv` holds **4 signals**; all
  backtest reports read `INSUFFICIENT DATA`. Signals are only recorded going forward, for
  portfolio-selected stocks — so 2,457 days of history have never been scored. Historical replay is the
  roadmap's key unlock.
- `docs/DATABASE_SCHEMA.md` and `docs/PROJECT_ARCHITECTURE.md` are 0 bytes (`F0.2`).
- `requirements.txt` omits `PySide6` and pins nothing (`F0.3`).
- `config.HISTORY_CSV` points at the stale 5-day `psx_history.csv`, not the real
  `psx_history_clean.csv`. Only dead code reads it today (`F0.4`).
