\# PSX AI Scanner Pro

\## AI Scoring Rules

Version: 1.0



\---



\# Objective



The AI scoring system ranks PSX stocks for short-term trading using a 100-point model.



The system must not recommend stocks only because they are top gainers.



Every score must combine:



\- Trend

\- Momentum

\- Volume

\- Price action

\- Historical strength

\- Risk control



\---



\# Final Score Structure



| Category | Points |

|---|---:|

| Trend Score | 25 |

| Momentum Score | 20 |

| Volume Score | 20 |

| Price Action Score | 15 |

| Historical Score | 10 |

| Risk Adjustment | -10 to -50 |

| Final Score | 0–100 |



\---



\# Verdict Rules



| Final Score | Verdict |

|---:|---|

| 85–100 | STRONG BUY |

| 75–84 | BUY/WATCH |

| 60–74 | WATCH |

| Below 60 | AVOID |



\---



\# Trend Score — 25 Points



| Rule | Points |

|---|---:|

| Close above EMA20 | +5 |

| Close above EMA50 | +5 |

| Close above EMA100 | +5 |

| Close above EMA200 | +5 |

| EMA20 above EMA50 | +5 |



Important:



If database has fewer than 20 days, EMA20 is allowed but low confidence.



If database has fewer than 50 days, EMA50 must be treated as low confidence.



If database has fewer than 100 days, EMA100 must be ignored for high-confidence recommendations.



If database has fewer than 200 days, EMA200 must be ignored for high-confidence recommendations.



\---



\# Momentum Score — 20 Points



| Rule | Points |

|---|---:|

| RSI14 between 50 and 70 | +8 |

| RSI14 between 40 and 50 | +4 |

| RSI14 above 75 | Risk penalty |

| MACD histogram positive | +6 |

| 3-day return between 3% and 15% | +3 |

| 5-day return between 5% and 25% | +3 |



Important:



If RSI is unavailable because history is less than 14 days, do not penalize the stock.



If 3-day return is above 15%, mark as extended.



If 5-day return is above 25%, mark as extended.



\---



\# Volume Score — 20 Points



| Rule | Points |

|---|---:|

| Volume above 5-day average | +5 |

| Volume above 20-day average | +5 |

| Relative volume above 1.5x | +5 |

| Daily volume above 1,000,000 | +5 |

| Daily volume above 300,000 | +3 |



Important:



Volume is the most important confirmation factor for short-term trading.



A stock with strong price movement but weak volume should not receive a high final score.



\---



\# Price Action Score — 15 Points



| Rule | Points |

|---|---:|

| Close near day high | +5 |

| Strong close | +3 |

| Daily gain between 2% and 10% | +5 |

| Daily gain above 10% | +3 but add risk |

| Narrow range breakout | +5 when available |



\---



\# Historical Score — 10 Points



| Rule | Points |

|---|---:|

| 3-day momentum confirmed | +4 |

| 5-day momentum confirmed | +4 |

| Momentum status is MOMENTUM or STRONG MOMENTUM | +2 |



Future additions:



\- Consecutive green candles

\- Volume growth sequence

\- Higher high / higher low

\- Breakout success history

\- Similar pattern win-rate



\---



\# Risk Penalty



| Risk | Penalty |

|---|---:|

| WINDING-UP company | -25 |

| NON-COMPLIANT company | -20 |

| Price below 5 PKR | -8 |

| Volume below 50,000 | -10 |

| 3-day return above 15% | -3 |

| 5-day return above 25% | -5 |

| RSI above 75 | -4 |

| Daily gain above 10% | -4 |

| Extreme illiquidity | -15 |



\---



\# Risk Level



| Risk Penalty | Risk Level |

|---:|---|

| 0–5 | LOW |

| 6–14 | MEDIUM |

| 15+ | HIGH |



\---



\# Confidence Score



Confidence is different from AI Score.



AI Score answers:



"How good is this setup?"



Confidence answers:



"How reliable is this score?"



Confidence depends on:



\- Historical days available

\- Indicator availability

\- Volume quality

\- Price liquidity

\- Risk flags



Rules:



| Condition | Confidence Effect |

|---|---:|

| Less than 5 days history | Low confidence |

| 5–13 days history | Medium-low confidence |

| 14–49 days history | Medium confidence |

| 50–199 days history | High confidence |

| 200+ days history | Very high confidence |



\---



\# Recommendation Rules



A stock can be STRONG BUY only if:



\- Final score >= 85

\- Risk level is not HIGH

\- Volume is acceptable

\- It is not WINDING-UP

\- It is not NON-COMPLIANT

\- It is not extremely extended



A stock can be BUY/WATCH if:



\- Final score >= 75

\- Risk level is LOW or MEDIUM

\- Volume confirms movement



A stock should be AVOID if:



\- Risk level is HIGH

\- Volume is weak

\- Corporate risk exists

\- Score below 60



\---



\# Entry Rules



Entry is not automatic.



Evening scanner creates a watchlist.



Morning scanner confirms entry.



Entry must be confirmed using:



\- Opening range

\- Live price

\- Live volume

\- Market sentiment

\- Stock holding above support

\- No aggressive selling pressure



\---



\# Position Sizing



Capital should not be fully invested in one signal unless confidence is very high.



Default short-term allocation:



| Signal Quality | Capital Allocation |

|---|---:|

| STRONG BUY + High confidence | 40–50% |

| BUY/WATCH | 20–30% |

| WATCH | 0–15% |

| AVOID | 0% |



For 50,000 PKR:



\- Best trade: 20,000–25,000

\- Second trade: 10,000–15,000

\- Cash reserve: 10,000–20,000



\---



\# Exit Rules



Always define exit before entry.



Default exits:



\- Stop loss: 4–6%

\- Target 1: 6–8%

\- Target 2: 10–14%

\- Trail stop after Target 1

\- Exit if momentum fails

\- Exit if stock breaks previous support



\---



\# Important Philosophy



The system must prefer:



\- Fewer but higher-quality trades

\- Risk-controlled entries

\- Historical confirmation

\- Volume-backed moves

\- Clear exit plan



The system must avoid:



\- Blind chasing

\- One-day pump stocks

\- Illiquid stocks

\- Corporate-risk stocks

\- Overconfident recommendations with limited data

