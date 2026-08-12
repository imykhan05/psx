# How to use the PSX AI Scanner — and what's next

Open your tunnel URL, enter your API key once, and everything below is on one page
(also on mobile). **Honest framing:** this is a research + monitoring + risk tool
for *you* to make better-informed decisions. It is **not** an auto "buy this"
oracle — we proved (docs/EDGE_VALIDATION.md) that no such tradeable signal exists
here. Its biggest value is real data, one-glance context, and discipline.

## Daily workflow (what to actually do)

1. **Morning briefing (auto ~9 AM)** — market mood (bull/bear), day/week/month/
   200-day trend, %-above-MA, the relatively strongest names, and news. 30-second
   overview before the open.
2. **Today's Highlights** — one card: who broke out on volume, who's accumulating,
   new 52-week highs, upper-locks, coils, most active, accelerating sectors, news.
   *Where the action is today.* Tap any symbol to drill in.
3. **Screeners (click & go)** — filter to your kind of setup: breakout-on-volume,
   Accumulation radar (large-buyer footprints), near-breakout, coil, pullback-to-MA50,
   above MA50/MA200, near 52-week high, **Value — low P/E** (real fundamentals).
4. **Sector rotation** — which sectors money is flowing into/out of, and the
   strongest stocks inside a hot sector (your "big players rotate" idea).
5. **Stock lookup** — full homework on one name: returns (1w–1y), RSI, volatility,
   ATR, 1-yr drawdown, 52-week position, distance from MA50/MA200, **fundamentals
   (P/E, EPS, market cap, free float)**, and news sentiment.
6. **Watchlist** — add the names you like; see their moves + which triggers fired today.
7. **Position calculator** — BEFORE you buy: capital + risk% + entry + stop → exact
   shares, position value, R:R, potential profit. **The single most money-protecting
   tool here** — it keeps you sized right and stopped.
8. **All-stocks ranked + Seasonality** — market-wide context (Monday weak / Friday
   strong; Nov best, Feb worst — averages, not rules).
9. **Model ranking** — a *contrarian research lens* (beaten-down + volume). Read its
   warning: it does **not** beat the market on tradeable stocks — a starting point,
   not a buy list.

## Biggest real benefits
- **Risk discipline** (position sizing + stops) — the #1 way this saves money.
- **All the data in one place** — no flipping between sites.
- **Honest context** — no fake "buy" signals to lose money on.
- **Automation** — data + analysis refresh themselves (6 PM scan, 9 AM briefing).

---

## Pending / can still be added

### A — Deploy & access
- **Permanent URL `psx.educativz.com`** — once nameservers go Active on Cloudflare (named tunnel)
- **Mobile push notifications** — needs a (free) Firebase project on your account
- **AI chat (/query)** — needs Anthropic credits, or switch to Google Gemini's free tier
- **Fundamentals weekly auto-refresh** — a scheduled task (currently manual)
- **Always-on cloud** (works with PC off) — needs a host with a card, or a paid tier

### B — Analytics buildable now (no new data)
- Beta / correlation matrix / co-moving pairs (diversification & pairs)
- New-highs-vs-new-lows breadth; circuit-hit frequency; MACD / Stochastic
- Per-stock threshold alerts (in-app)
- "What-if" backtest of ANY screener as a strategy (with the liquidity filter, honestly)
- Model refinements: a liquid-only ranking view; a regime filter

### C — Needs new / paid data (cannot do free)
- Per-stock institutional flows (FIPI per stock) — not freely available
- Deep fundamentals (earnings history, dividends, book value, growth) — fuller data source
- Intraday / order-book / short-interest — paid feed

### D — Product polish
- Refresh the React web dashboard to match this built-in page (or retire it)
- Wire the new engines into the PySide6 desktop terminal tabs
- Email / Telegram alert delivery
