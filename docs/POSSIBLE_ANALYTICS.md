# PSX Analytics — everything we can build from the data

The full menu of options we can compute for the Pakistan Stock Exchange from what
we have: **end-of-day OHLCV** (open/high/low/close/volume) for ~985 symbols,
2016→today, plus news headlines. Each item is tagged honestly:

- ✅ **BUILT** — already live in the app
- 🟢 **FACT** — a direct measurement, reliable, no prediction claimed
- 🟡 **HEURISTIC** — an inference (e.g. "accumulation") — reasonable but not proven
- 🔬 **PREDICTIVE / RESEARCH** — claims about the future; must be validated before trusting
- 🚫 **NEEDS DATA WE DON'T HAVE** — impossible until we buy/obtain another dataset

> Reality check from our validation (`docs/EDGE_VALIDATION.md`): on PSX, **momentum
> is anti-predictive** and the only weakly-predictive footprint that still works is
> **sustained volume**. So most items below are honest *information/analysis*; very
> few are *predictions*, and none are "sure things".

---

## 1. Price & return analytics — 🟢 FACT
- Returns over any window: 1d ✅, 1w ✅, 1m ✅, 200d ✅, plus 3m, 6m, 1y, YTD, since-listing
- 52-week high / low + distance from them ✅ (near-52w-high built)
- All-time high / low + distance
- Volatility (return std-dev), Average True Range (ATR)
- Max drawdown from peak, current drawdown
- Gap analysis (today's open vs yesterday's close)
- Consecutive up / down day streaks
- Best/worst day, week, month per stock

## 2. Trend & moving averages — 🟢 FACT
- SMA / EMA 20 / 50 / 100 / 200: above/below ✅ (MA50/MA200 built), distance, slope
- Golden cross / death cross (MA50 × MA200) ✅ (aligned-uptrend built)
- Multi-MA "trend stack" (price > MA20 > MA50 > MA200)
- Trend age (how many days in current trend)

## 3. Momentum indicators — 🟢 FACT (⚠️ but anti-predictive on PSX)
- RSI, MACD, Stochastic, Rate-of-Change, Williams %R
- Overbought / oversold flags
- *Note: our data shows high momentum → lower forward returns. Show these as info,
  do NOT trade them as "buy signals".*

## 4. Volume & accumulation — 🟢 FACT / 🟡 HEURISTIC
- Relative volume (today vs 20d avg) ✅ (volume-spike built)
- **Sustained volume (5d vs 20d) — Accumulation Radar** ✅ (🔬 small real edge)
- On-Balance-Volume, Volume-Price-Trend, Accumulation/Distribution line
- Value traded / turnover ranking ✅ (most-active built)
- Up-volume vs down-volume (buying vs selling pressure)
- Volume dry-up then surge (base-breakout precursor)
- Liquidity tier (tradeable vs illiquid)

## 5. Circuit / limit analytics — 🟢 FACT
- Upper-lock / lower-lock today ✅ (built)
- Frequency of circuit hits (how often a stock locks)
- Days spent at upper vs lower circuit

## 6. Market breadth — 🟢 FACT
- Advances vs declines ✅ (daily signal), advance/decline ratio & line
- % of stocks above MA50 / MA200 ✅ (briefing)
- New 52-week highs vs new lows (breadth thrust)
- Up-volume vs down-volume for the whole market
- Breadth by price tier / by sector

## 7. Sector & rotation — ✅ BUILT / 🟢 FACT  *(your "crocodiles rotate" idea, at sector level)*
- Sector performance leaderboard (1d/1w/1m/200d) ✅
- **Sector rotation flag** — accelerating vs fading (this week's pace vs last month's) ✅
- Sector breadth (% above MA50) + sustained-volume + value share ✅
- "Hot sector → strongest stocks in it" drill-down (top stocks per sector) ✅
- Still to add: relative strength vs a KSE-index proxy; week-over-week rank shift history

## 8. Relative strength & ranking — 🟢 FACT
- Rank every stock by return / volume / RS ✅ (All-Stocks list built)
- Relative strength vs KSE index proxy
- Percentile / tier tags ✅ (Top 10/25/50% built)
- Leaders & laggards boards

## 9. Pattern & level detection — ✅ BUILT / 🟢 FACT
- Breakout on volume (new 20-day high + sustained volume) ✅
- Near-breakout (within 3% under the 20-day high) ✅
- Tight consolidation / coil (20-day range in tightest ~20%) ✅
- Pullback to MA50 inside an uptrend ✅
- 52-week-high breakouts ✅ (near-52w-high)
- Still to add: horizontal support/resistance levels, base-count, reversal day patterns

## 10. Statistics & relationships — 🟢 FACT
- Beta vs the market, correlation matrix between stocks
- Co-moving pairs (pairs-trading candidates)
- Seasonality: day-of-week, month-of-year, Ramadan/results-season effects
- Return distribution / skew per stock

## 11. Risk & position tools — 🟢 FACT
- Stop-loss / target / risk-reward calc ✅ (in scan)
- Position sizing from account size + risk %
- Portfolio simulation & equity curve ✅ (partial)
- Correlation-aware diversification check
- "What-if" backtest of a screener as a strategy

## 12. Alerts & monitoring — 🟢 FACT (to build)
- Volume-surge alert, breakout alert, circuit alert, 52w-high alert
- "My watchlist moved" daily digest
- Push notification to the mobile app

## 13. Validation & backtesting — 🔬 RESEARCH
- Signal edge validation ✅ (built — validate_edge / validate_accumulation)
- Strategy backtest with costs, walk-forward out-of-sample
- Regime detection (when does a signal work vs not — we saw reversion decay)

## 14. News & sentiment — ✅ BUILT / 🟡 HEURISTIC
- Headline sentiment per ticker ✅
- News volume spikes, event flags (could extend to global/commodity/FX news)

## 15. A real predictive model — 🔬 RESEARCH (the honest path to "what to buy")
- Combine the weak-but-real pieces (sustained volume + regime-aware reversion + breadth)
  into a model, validated walk-forward, only shipped if it beats the market **after costs**.
- Realistic target: a small, honest edge (~53–58% directional) — **not** 80%.

---

## 🚫 What we CANNOT do without buying more data
- **Fundamentals** — P/E, EPS, earnings, dividends, book value, growth (need a financial-data source)
- **Real institutional / broker activity** — FIPI/LIPI, foreign flows (need NCCPL/CDC data)
- **Intraday / tick / order-book** — bid-ask, VWAP, intraday patterns (we only have EOD)
- **Short interest, futures open-interest**
- **Corporate-action calendar** — splits, bonuses, results dates (need a separate feed)

*Anything above the line is buildable from data we already have. Everything below
the line requires a new dataset — a cost/licensing decision, not a coding task.*
