# Edge Validation (F1.3) — does the signal predict returns?

**Date:** 2026-08-12 · **Data:** SQLite `daily_prices`, 2016-08 → 2026-08-11,
~500 liquid symbols, **859,752 stock-days** with a forward-10-day return.
**Reproduce:** `python tools/validate_edge.py`

## Why this exists

The user asked us to make the BUY/WATCH/AVOID calls trustworthy (everything was
showing AVOID). Before changing any threshold, we had to answer the only question
that matters: **do the signals the engine relies on actually predict forward
returns on PSX?** A BUY label on a signal that doesn't predict is worse than no
label. This is a no-look-ahead study: signals are computed from data up to day *t*,
the target is the strictly-future next-10-trading-day return.

## Result (pooled, 859,752 stock-days; market avg fwd-10d = +1.16%)

| Signal | Spearman IC | Top−bottom decile fwd-10d |
|--------|------------:|--------------------------:|
| mom_21 — 1-month momentum | **−0.038** | **−1.59%** |
| mom_63 — 3-month momentum | **−0.031** | **−1.81%** |
| above_ma50 — trend | −0.029 | −0.28% |
| above_ma200 — trend | −0.020 | −0.41% |
| vol_ratio — volume vs 20d avg | +0.020 | +0.98% |
| rev_5 — short-term mean-reversion | +0.037 | +1.30% |

### Per-year top−bottom decile spread (fwd-10d %)

| Year | mom_63 | rev_5 | vol_ratio | market |
|------|-------:|------:|----------:|-------:|
| 2016 | −5.19 | 2.20 | −0.63 | 4.85 |
| 2017 | −2.65 | 1.51 | 1.29 | −0.78 |
| 2018 | −4.28 | 3.18 | 1.41 | −0.28 |
| 2019 | −0.98 | 2.31 | 1.69 | 0.66 |
| 2020 | −6.34 | 3.89 | 0.07 | 2.09 |
| 2021 | −1.29 | 1.64 | 1.32 | 0.44 |
| 2022 | −3.49 | 4.91 | 0.04 | −0.99 |
| 2023 | −1.10 | 2.46 | 0.23 | 2.13 |
| 2024 | −1.52 | −0.22 | 1.12 | 2.47 |
| 2025 | −1.31 | 0.15 | 0.81 | 2.41 |
| 2026 | −5.45 | −2.01 | 1.93 | 1.09 |

## Honest conclusions

1. **Momentum / trend-following is robustly *anti-predictive* on PSX.** High-momentum
   and above-MA stocks *under-perform* over the next 10 days, in **every year**
   2016–2026. The scoring engine (`ai_score_engine_v5`, smart-money, trend) is built
   largely on these — i.e. it leans the **wrong way**. This is the real reason its
   edge is weak/negative, not a threshold setting.
2. **Mean-reversion (buy recent losers)** had a genuine edge 2016–2023 (+1.5 to +4.9%)
   but has **decayed and flipped in 2024–2026** — not reliable going forward.
3. **Volume** carries a small, more stable positive signal (~+1% decile spread), but
   far too weak on its own to base BUY calls on.
4. **Therefore: no simple signal currently predicts PSX returns reliably enough to
   issue a trustworthy BUY.** Lowering the decision thresholds would only stamp "BUY"
   on momentum leaders — exactly the group that tends to under-perform. We will not do
   that.

## What this means for the product

- The engine's decisions (BUY/WATCH/AVOID) and buy_probability should **not** be
  treated as return predictions. They are a rules snapshot with an unproven — and, for
  the momentum parts, negative — edge.
- The tool's honest value today is as a **market monitor + screener + multi-timeframe
  analysis** aid for a human, not an automated "what to buy" oracle.
- A genuinely predictive signal requires real model research: combine the weak-but-real
  pieces (volume, reversion, others) with proper walk-forward validation and
  transaction-cost modelling, and only ship BUY logic that beats the market
  out-of-sample **after costs**. That is the ML phase in `ROADMAP.md`, deliberately
  placed after this validation — now with a measured baseline to beat.

*A negative result is a valid result. Publishing it is the honest outcome (project rule 9).*

---

## Update — a COMBINED model does have a small real edge (`tools/build_model.py`)

Individually the signals are weak/negative. But a **cross-sectional linear model**
that combines them, tested **walk-forward out-of-sample** (each year fit only on
prior years), does beat the market:

| Test year | OOS top−bottom decile (10d) | net of ~0.6% cost | IC |
|-----------|----------------------------:|------------------:|----:|
| 2019 | +5.72% | +5.12% | 0.107 |
| 2020 | +6.22% | +5.62% | 0.119 |
| 2021 | +3.57% | +2.97% | 0.073 |
| 2022 | +4.14% | +3.54% | 0.063 |
| 2023 | +4.37% | +3.77% | 0.088 |
| 2024 | +1.53% | +0.93% | 0.053 |
| 2025 | +0.30% | **−0.30%** | 0.050 |
| 2026 | +4.26% | +3.66% | 0.084 |

**Average +3.76% (net +3.16%) over 10 days; positive net in 7 of 8 years.** The
fitted model is essentially **contrarian + volume**: it shorts momentum / stocks
near 52-week highs / high-RSI, and favours beaten-down names with volume coming in
(coefficients: dist_52w_high −0.27, dist_ma50 −0.23, rsi14 −0.15, rev_5 +0.13,
vol_ratio +0.13, mom_21 +0.12, rvol_5 +0.08).

### This is real, but read the caveats
- It is a **diversified-basket** edge over ~2 weeks (IC ~0.08) — **not** a per-stock
  80% prediction.
- Much of the spread is **long-SHORT**; shorting is impractical on PSX, so a
  long-only user captures roughly half.
- Costs/slippage/illiquidity in small names erode the net edge; **2025 was flat**.
- Past OOS performance ≠ future results.

Shipped as **`app/engines/model_engine_v1.py`** (fits on history, ranks today's
stocks) → `GET /model` → the "Model picks" card. This is the honest version of a
"what to consider" model: a small, validated edge, labelled with its real track
record and limits — never an 80% guarantee.
