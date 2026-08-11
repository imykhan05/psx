# Project Architecture

**Scope:** the *current, implemented* architecture, verified against `main.py`, the `app/` package, and
`institutional_terminal_v1.py` on 2026-07-20. For where this is heading (service-oriented, API, ML),
see `ROADMAP.md` — this document is present state only.

---

## 1. What the system is

A local, single-user, end-of-day PSX scanning and decision-support tool. It ingests daily PSX market
files, runs them through a chain of ~30 rule-based engines, and produces trading reports plus a desktop
terminal to view them.

- **No live market feed** — input is EOD batch files.
- **No trained ML model** — all scoring is rule-based and hand-weighted (see `docs/AI_SCORING_RULES.md`).
- **No web API, no auth, no DB server** — everything runs locally; storage is SQLite + CSV.

## 2. Entry points

| Entry | What it does |
|---|---|
| `python main.py` | Runs the full pipeline: import → features → scoring → risk → portfolio → reporting → dashboard. |
| `python main.py --terminal` | Subprocess-launches the desktop GUI. |
| `python main.py --backfill` | Re-imports the whole `database/historical_files/` archive. |
| `python main.py --order-list / --execute-buy / --execute-sell` | Manual order-execution simulator. |
| `institutional_terminal_v1.py` | PySide6 desktop terminal (14 tabs). Reads report CSVs; never touches SQLite directly. |

`main.py` is the **only** orchestration entry point. It chains every engine in-process, sequentially.

## 3. Layered package map (`app/`)

```
app/
├── core/               Data layer: file parsing, SQLite I/O, history engine,
│                       daily/backfill import managers, indicators.
├── engines/            The engine chain: scoring, risk, portfolio, alerting,
│   ├── backtesting/    reporting, dashboards.
│   └── long_term/      Fundamental/valuation/growth/dividend/quality sub-engines
│                       (provenance-gated — see ROADMAP F0.1).
├── master_data/        Company master build/sync/merge.
├── company_directory/  Sector mapping from scan data.
├── psx_intelligence/   Company enrichment (sector/industry/website metadata).
└── utils/              Shared loaders (strategy rules, long-term rules).
```

Only modules imported (directly or transitively) by `main.py` are live. Superseded variants live in
`archive/` (see `archive/README.md`).

## 4. The pipeline (order as chained in `main.py`)

Each stage consumes the previous stage's DataFrame (`final`) and adds columns. **Additive by design** —
a stage must not break the columns a later stage reads.

1. **Data acquisition** — `run_daily_data_manager_v2()` (or `--file` manual override) → latest-day snapshot.
2. **Freshness Firewall (SOURCE)** — `run_freshness_firewall()` cross-checks filename/parser/snapshot/
   SQLite dates and **blocks the run** on any mismatch. Prevents scoring stale data.
3. **Persistence + history** — `update_sqlite_database()` → `prepare_history_v2()` → `add_indicators()`.
4. **Feature build** — `build_features_v3()`.
5. **Company intelligence** — PSX enrichment + sector directory build.
6. **Market context** — `MarketEngine.summary()`.
7. **AI scoring (rule-based)** — `apply_ai_engine_v5()`.
8. **Decision pipeline** — `build_recommendations()` → `decision_engine_v2` → `trade_validation` →
   `entry_timing` → `risk_management_v2`.
9. **Calibration + consensus** — `institutional_v5_calibration` → `signal_consensus` →
   `apply_consensus_master_decision()` (consensus becomes the master decision).
10. **Long-term engine** — `merge_fundamentals()` → `LongTermEngine.apply()`. Provenance-gated: emits a
    verdict only for `REAL`-sourced fundamentals; otherwise "NO FUNDAMENTAL DATA".
11. **Company master** — build/sync/merge metadata onto `final`.
12. **Freshness Firewall (FINAL)** — re-check before capital allocation.
13. **Portfolio** — `build_portfolio_plan_v5()` → `align_final_recommendations_with_portfolio()`
    (Portfolio V5 is the final authority on deployable capital).
14. **Market structure** — `market_breadth` → `smart_money_tracker_v2` → `opportunity_ranking`.
15. **Position lifecycle** — `trade_lifecycle` → `exit_intelligence` → `live_portfolio_monitor`.
16. **Portfolio analytics** — `equity_curve` → `portfolio_analytics_pro` → `trade_journal_pro` →
    `strategy_analytics` → `strategy_optimizer_self_learning_v2`.
17. **Institutional surfaces** — `institutional_alert_center` → `ai_institutional_assistant` →
    `ai_command_center`.
18. **Backtesting loop** — `record_signals_v1` → `run_backtest_v1` → `performance_analyzer_v1` →
    `learning_engine_v1`. (Starved of data until ROADMAP F1.1.)
19. **Reporting** — `generate_reports_v2()` writes the CSV artifacts.
20. **Dashboard** — `run_performance_dashboard_v3()` writes `reports/dashboard/dashboard_v3.html`.

## 5. Outputs

`generate_reports_v2()` writes a timestamped `reports/TRADING_<date>__RUN_<ts>/` folder and copies it to
`reports/latest/`. Key artifacts in `latest/`: `top_buys.csv`, `full_market_scan.csv`, `portfolio.csv`,
`trade_lifecycle.csv`, `exit_intelligence.csv`, `open_positions.csv`, `closed_positions.csv`,
`pending_entries.csv`, `sectors.csv`, `long_term.csv`, `daily_action_plan.csv`, `summary.md`,
`metadata.json`.

Per-category engines write their own folders: `reports/market_breadth/`, `smart_money/`,
`opportunity_ranking/`, `alerts/`, `command_center/`, `ai_assistant/`, `live_portfolio/`, `performance/`,
`portfolio_analytics/`, `trade_journal/`, `strategy_analytics/`, `strategy_optimizer/`, `backtests/`,
`dashboard/`.

Old timestamped run-folders are pruned by `tools/prune_reports.py` (keeps newest 10).

## 6. Desktop terminal

`institutional_terminal_v1.py` (PySide6/Qt). A read-only reporting shell over the report CSVs — it never
queries SQLite. A `REPORTS` dict maps logical keys to `(folder, filename)`; 14 pages render those CSVs.
It can also shell out to `main.py` (run scanner, execute orders) and open the HTML dashboard externally.
See the project memory note on its `REPORTS`/page-index pattern before adding tabs.

## 7. Configuration

`config.py` resolves all paths from `BASE_DIR = Path(__file__).parent`. `DATABASE_DIR = database/`;
`DATA_DIR` is an alias of it (the former separate `data/` tree was consolidated in F0.4);
`HISTORY_CSV = database/psx_history_clean.csv`. Only `run_terminal.bat` still hardcodes an absolute path.

## 8. Direction of travel

The target (ROADMAP) is to extract these in-process engines into independently deployable, API-fronted
services (Market Data, Scanner, Technical/Fundamental Analysis, Portfolio, Risk, ML Prediction, etc.).
The migration path is **extract interface → wrap in service → split process**, one module at a time,
never a big-bang rewrite. Real ML is deliberately sequenced after historical-replay validation (F1.1)
and real fundamentals ingestion (F3.3).

---

## Change log for this document
- 2026-07-20: created from live `main.py` pipeline (ROADMAP F0.2/F0.4). Previously a 0-byte placeholder.
