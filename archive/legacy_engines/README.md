These 27 files were moved out of `app/engines/` on 2026-07-17 during cleanup.

Each one was confirmed unused by tracing `main.py`'s actual import graph (direct + transitive)
and grepping the rest of the repo for any other reference — none were found. They are superseded
versions from earlier development iterations (e.g. `ai_engine_v3.py`/`ai_engine_v4.py` superseded by
`ai_engine_v5.py`, `portfolio_engine.py` through `portfolio_engine_v4.py` superseded by
`portfolio_engine_v5.py`, etc.).

Kept here instead of deleted in case anything needs to be referenced later. Safe to delete this
whole folder once confirmed unnecessary.
