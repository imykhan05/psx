# Fabricated fundamentals — quarantined 2026-07-20 (ROADMAP.md F0.1)

These two files were moved out of the live pipeline because they injected
**fabricated financial data** into production investment recommendations.

- `create_fundamentals.py` — wrote hardcoded, invented financials (EPS, book
  value, ROE, ROA, P/E, `fair_value`, …) for 10 of ~985 symbols. The numbers
  were typed into a Python string literal. They originated from no financial
  statement.
- `fundamentals.csv` — the output of that script.

`LongTermEngine` consumed these and emitted live verdicts. Before quarantine,
`reports/latest/long_term.csv` asserted, for example:

> `LUCK — fair value 980.00, upside 113.29%, DEEPLY UNDERVALUED, STRONG BUY, confidence 95%`

— a STRONG BUY built entirely on invented inputs. This violates the project's
first rule: *never fabricate market data, model output, or confidence numbers.*

## What replaced them

`app/engines/long_term/fundamental_loader.py` now tags every fundamentals row
with `data_provenance` (`REAL` / `SEED` / `ABSENT`) and `LongTermEngine` refuses
to compute a verdict, fair value, or confidence for any row that is not `REAL`.
With no real fundamentals present, the long-term report is now empty rather than
fabricated — the correct state until real data is ingested (ROADMAP.md F3.3).

**Do not restore these files.** When real fundamentals are sourced, they enter
through the provenance-aware loader labelled `REAL`, not by reviving this script.
