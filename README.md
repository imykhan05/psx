---
title: PSX AI Scanner API
emoji: 📈
colorFrom: green
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# PSX AI Scanner API

Read-only FastAPI backend for the **PSX AI Scanner** — a Pakistan Stock Exchange
end-of-day, rule-based scanner. It serves the daily market signal, ranked
opportunities, and per-stock scoring from the pipeline's committed output files.
It does **not** recompute anything and loads **no** ML model.

## Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/health` | none | Liveness + which data files are present |
| GET | `/signal` | `X-API-Key` | Today's BULLISH/BEARISH/NEUTRAL verdict + reasons |
| GET | `/opportunities?limit=N` | `X-API-Key` | Top ranked opportunities |
| GET | `/stock/{ticker}` | `X-API-Key` | Price + scoring + news sentiment for one symbol |
| POST | `/query` | `X-API-Key` | Grounded NL assistant (needs `ANTHROPIC_API_KEY`) |

Send the header `X-API-Key: <PSX_API_KEY>`. Set `PSX_API_KEY` (and optionally
`ANTHROPIC_API_KEY`) as **Space secrets** under Settings → Variables and secrets.

## Data freshness

Data is refreshed via **git-commit-on-refresh**: the local scanner runs the
end-of-day pipeline and pushes the small output files
(`daily_signal.json`, `sentiment_cache.json`, `top_buys.csv`,
`full_market_scan.csv`), which triggers a Space rebuild. It is an end-of-day
snapshot, not live market data, and is **not** financial advice.

Full deployment docs: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).
