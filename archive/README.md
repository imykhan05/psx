# archive/ — quarantined, out of the live path

Nothing in here is imported or executed by the live application (`main.py`,
`institutional_terminal_v1.py`, or the `app/` package). Files were moved here —
not deleted — so they remain recoverable. Each subfolder records why.

| Folder | What / why |
|---|---|
| `legacy_engines/` | 27 superseded engine versions (old `ai_engine_v3/v4`, `portfolio_engine` v1–v4, etc.). Confirmed unused via full transitive import-graph trace. (2026-07-17) |
| `fabricated_fundamentals/` | `create_fundamentals.py` + fabricated `fundamentals.csv` that injected invented financials into live STRONG BUY verdicts. Quarantined for ROADMAP F0.1. **Do not restore.** (2026-07-20) |
| `dead_ai/` | Former `app/ai/` (12 files). Zero live importers — a parallel/abandoned AI tree superseded by `app/engines/`. (F0.4, 2026-07-20) |
| `dead_app_backtesting/` | Former `app/backtesting/` (4 files). Zero importers. The live backtesting code is `app/engines/backtesting/`. (F0.4) |
| `dead_app_reports/` | Former `app/reports/` (`html_dashboard.py` + `__init__`). Zero importers. Live reporting is `app/engines/reporting_engine_v3.py` + `performance_dashboard_v3.py`. (F0.4) |
| `dead_root_scripts/` | `bafs_live_scanner.py`, `psx_scanner.py`, `psx_scanner_v0_backup.py`. Root-level scanners superseded by `main.py`. Zero importers. (F0.4) |
| `dead_core/` | `app/core/database.py` — dead CSV-history helper (zero importers), the only reader of the stale `HISTORY_CSV`. Superseded by `app/core/sqlite_database.py`. (F0.4) |
| `dead_data_tree/` | The root `data/` directory: a near-empty parallel data tree (only a stale 5-day `psx_history.csv`). Live data lives in `database/`. (F0.4) |

Safe to delete any subfolder once you're confident it's not needed.
