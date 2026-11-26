# Research log

One entry per experiment. The **hypothesis and pass bar are written before running**, and the result and verdict
after. Shared bar (owner, 2026-11-24): stocks must beat buy-and-hold SPY after 5 bps per side costs, with a higher
Sharpe and a worst drop under 35%, out of sample. Kalshi ideas must beat the market price after real fees, out of
sample.

**Out of sample for stocks.** These rules use textbook parameters, set before looking at our data, and nothing is
fitted, so the whole 2017–2026 period is out of sample. Results are also shown for a held-out late window
(2023-01-01 onward), to check that the edge isn't confined to early years.

**Look-ahead and survivorship audit (every entry):** strategies see only data up to their decision day (enforced by
the engine). The universe is point-in-time and includes delisted stocks. Any result beating SPY by a wide margin is
treated as a bug until checked.

---

## R1. Momentum + low volatility (combined rank). Registered 2026-11-24, before running
- **Hypothesis:** ranking stocks on both 12-1 momentum and 60-day volatility (average of the two ranks, top 20,
  monthly) keeps most of momentum's return while cutting its 60% drawdown. Low-vol stocks tend to fall less in
  momentum crashes.
- **Rule:** among the month's point-in-time stocks (no ETFs), rank by 12-1 return (high = good) and by 60-day daily
  volatility (low = good). Average the two ranks and hold the best 20 equally. Rebalance on the first trading day
  of each month. No tuning.
- **Pass bar:** Sharpe > SPY's, worst drop < 35%, final value > SPY's, after costs, Mar 2017–Nov 2026, and not
  losing to SPY in the held-out window from 2023.

## R2. Momentum with a crash filter. Registered 2026-11-24, before running
- **Hypothesis:** momentum's big losses come in bear markets and sharp rebounds. Holding momentum only while SPY is
  above its 200-day average (else cash) cuts the worst drop without giving up most of the return.
- **Rule:** at each monthly rebalance, if SPY's close is above its 200-day average, hold momentum's top 20.
  Otherwise hold cash. Variant R2b holds SH (1x inverse S&P) instead of cash. Checked monthly only. No tuning.
- **Pass bar:** Sharpe > SPY's, worst drop < 35% (and below plain momentum's 60%), final value > SPY's, after costs,
  Mar 2017–Nov 2026, and not losing to SPY in the held-out window from 2023.

## K1. Kalshi favorite-longshot bias (weather markets). Registered 2026-11-24, before running
- **Hypothesis (published for Kalshi overall: Bürgi, Deng & Whelan, "Makers and Takers"):** cheap contracts win
  less often than their price implies, and expensive ones slightly more. If true in our weather markets, buying
  high-price buckets, or selling (buying NO on) longshots, could pay. The bias must survive fees, and it must
  survive in the later data, not only in the oldest.
- **Data:** 44,000 settled weather markets (Sep 2025 – Nov 2026) with bid/ask at 8pm the evening before and at 8am
  on the day. Outcomes come from Kalshi's settlement.
- **Measure:** realised YES rate vs price, in price bins, for the train months (before Mar 2026) and the test months
  (Mar–Nov 2026) separately.
- **Trading check, as a range:**
  - *pessimistic:* a taker buys at the ask and pays the taker fee;
  - *optimistic:* a maker is filled at the bid with no fee, ignoring that resting orders mostly fill when the price
    is moving against them (adverse selection).
- **Pass bar:** a rule fixed on the train months that is positive after fees on the test months in the pessimistic
  (taker) case. Or, if only the maker case is positive, it goes to K2 (a proper fill simulation from trade history)
  rather than to shadow.

---

# Results (run 2026-11-24)

## R1. Momentum + low volatility: **FAIL**
| window | strategy | $200 → | CAGR | Sharpe | worst drop | worst month |
|---|---|---|---|---|---|---|
| Mar 2017 – Nov 2026 | SPY | $699 | 13.7% | **0.80** | 34% | −13% |
| | momentum 12-1 | $1,535 | 23.4% | 0.69 | 60% | −25% |
| | **R1** | **$540** | 10.8% | 0.72 | **34%** | −12% |
| held-out 2023 → | SPY | $398 | 19.4% | **1.23** | 19% | −6% |
| | **R1** | **$308** | 11.8% | 0.92 | **13%** | −6% |

- It halves momentum's drawdown, to SPY's level. But it also gives up most of the return, and its Sharpe stays below SPY's
  in both windows. It lost to SPY in 6 of 10 calendar years.
- **Verdict:** fails the bar (Sharpe and final value both below SPY's). Mixing in low volatility mostly turns momentum
  into a dull, cheaper SPY. Not added to tracking.

## R2 / R2b. Momentum with a SPY 200-day crash filter: **FAIL (badly)**
| | $200 → | CAGR | Sharpe | worst drop |
|---|---|---|---|---|
| R2 → cash | $241 | 1.9% | 0.26 | 63% |
| R2b → SH | $111 | −5.9% | 0.08 | 68% |

- Worse than plain momentum on every measure, including the drawdown it was meant to cut.
- **Why (audited, not a bug):** the filter matched momentum's holdings every month except when SPY dipped under its
  average, and it sold at those lows, then missed the V-shaped rebounds. In Apr 2026 momentum gained +43% while R2 sat
  in cash (−3%). It's the same in 2019 and 2020. The SH variant lost on both legs: short during the rebounds, long
  momentum into the drops.
- **Verdict:** fails. Monthly-checked trend filters whipsaw on fast V-shaped markets, and this decade has had several.

## K1. Kalshi favorite-longshot bias (weather): **the bias is real; taker FAIL; maker → K2**
Data: 43,900 settled weather markets (eve) and 44,000 (am). Train: Sep 2025 – Feb 2026. Test: Mar – Nov 2026.

**Calibration (eve, test months): what the market priced vs how often it happened**

| YES mid | priced | happened |
|---|---|---|
| 0–2¢ | 1.1% | 0.2% |
| 2–5¢ | 3.2% | 2.0% |
| 5–10¢ | 7.0% | 5.6% |
| 10–20¢ | 14.5% | 13.1% |
| 50–65¢ | 56.2% | 59.7% |
| 65–80¢ | 69.6% | 78.2% |

- Longshots are overpriced by about 1–1.5¢ and favorites underpriced, in both train and test and at both decision
  times. This is the published Kalshi pattern, and it's in our weather data.
- **Taker (buy NO on longshots at the YES bid, pay the fee):** the rule chosen on train loses on test, −0.44¢ per
  contract over 13,218 trades (am: −1.02¢). **Fees and the spread eat the whole bias.** Fail.
- **Maker (upper bound: filled at the bid, no fee, no adverse selection):** +1.5¢ to +2.5¢ per contract on test, every
  variant, both decision times, about +$200–300 per contract-size over 9 months. **This is an upper bound, not a
  result.** Resting orders tend to fill exactly when the price is moving against you, and fills aren't guaranteed.
- **Is it shrinking?** Longshot mispricing by month (eve): −1.5¢ in Sep 2025, −0.8¢ in Oct 2026, −0.3¢ in Nov 2026.
  The am trend is similar (−1.1¢ → −0.4¢). **Possibly shrinking.** Recent months are about a third of the older gap.
  That's a guess from 15 monthly points, but it's the main risk to the idea.
- A favorite rule ("buy YES at 65–95¢") showed +4.7¢ per contract as a taker in eve-test, but with only 26 train
  examples, and it was negative at am. Noted, not trusted.
- **Verdict:** the only effect found so far that is real and repeats out of sample. It can only be harvested as a
  maker. Next is **K2**: replay real Kalshi trade history to see which resting orders would actually have filled,
  and what they earned after fills, adverse selection and the 0% maker fee on these series.

---

## K2. Kalshi maker orders on the longshot bias, replayed against real trades. Registered 2026-11-24, before running
- **Hypothesis:** resting (maker) orders that sell overpriced longshots, and buy underpriced favorites, earn money
  after fills and adverse selection. Weather series charge 0% maker fees (to verify against the fee schedule).
- **Markets:** test period only (events from 2026-03-01). Rules come from K1's train months: at 8pm the evening before:
  - **A, longshots:** YES mid in 5–20¢ (K1's train-chosen maker zone). Post a **sell-YES (= buy NO)** limit. A1 joins
    the best ask (P = YES ask). A2 improves by 1¢ when the spread is at least 2¢ (P = ask − 1¢).
  - **B, favorites:** YES mid in 65–95¢. Post a **buy-YES** limit. B1 joins the best bid. B2 improves by 1¢ when the
    spread is at least 2¢.
  - One contract per market, kept until the market closes.
- **Fills, from Kalshi's real trade tape after the order time:**
  - *conservative "through":* filled only if a later trade happened at a price **beyond** ours (a YES buyer paid
    more than our ask, or a YES seller got less than our bid). That can only happen after every order at our price
    was taken.
  - *optimistic "touch":* also filled when a trade happened **at** our price. We might really have been behind the
    queue.
- **Measured:** fill rate, P&L per filled contract, total, by month, plus **adverse selection**: filled orders' P&L
  compared with what the same orders would have made had all of them filled.
- **Pass bar:** conservative-fill P&L > 0 on the test period with a 95% bootstrap CI (over city-days) above zero,
  **and** positive in the later half (Jul–Nov 2026) on its own, since K1 hinted the bias is shrinking. Passing earns a
  shadow slot only after owner approval. It doesn't earn real money.

## K2 result: **favorites (B1) PASS; longshots (A) FAIL**
Run with `uv run python -m app.backtest.makers` (Trading-bot) on every test-period market in the two zones: 9,384
markets' full trade tape from the 8pm decision to close, from Kalshi's `/markets/trades` and `/historical/trades`.
Cents are per contract. The CI is a 95% bootstrap over city-days.

| rule | posted | fill % (through) | ¢/fill, through | 95% CI | Jul–Nov ¢ | ¢/fill, touch | ¢ if every order filled |
|---|---|---|---|---|---|---|---|
| A1 sell YES at the ask | 8,965 | 81% | +0.47 | [−0.21, +1.14] | +0.39 | +1.33 | +2.54 |
| A2 sell YES at ask − 1¢ | 3,884 | 84% | +0.30 | [−0.74, +1.35] | +0.24 | +0.81 | +2.17 |
| **B1 buy YES at the bid** | 419 | 89% | **+7.09** | **[+3.02, +11.09]** | **+5.40** | +8.31 | +9.51 |
| B2 buy YES at bid + 1¢ | 194 | 93% | +6.21 | [+0.03, +12.05] | +2.02 | +6.75 | +8.11 |

- **Fees verified:** Kalshi's API reports `fee_type: "quadratic"` (taker fee only) for KXHIGH*, KXLOWT* and KXTSAW,
  while KXFED, KXCPI and KXNFLGAME are `"quadratic_with_maker_fees"`. So makers pay no fee in weather.
- **Adverse selection is real but not fatal.** Filled orders earn less than all orders would have (B1: 7.09¢ vs
  9.51¢; A1: 0.47¢ vs 2.54¢). It eats almost all of the longshot edge and about a quarter of the favorite edge.
- **Longshots (A):** the CI includes zero and the later months are near zero. **FAIL.** This matches K1's hint that
  the longshot bias is shrinking.
- **Favorites (B1):** it passes both parts of the bar: CI above zero and Jul–Nov positive. Evening favorites
  (65–95¢) won 5–15¢ more often than priced in every month since March 2026. Even a taker at the ask, paying the
  fee, made +4.66¢ (n = 419). That wasn't pre-registered; K1 skipped it because training had only 26 such markets.
- **Capacity is small.** About 1.5 qualifying markets a day, so 374 fills in 9 months, about $25 per contract of size.
  At 5–10 contracts per order that's roughly $15–30 a month on about $35–70 of capital at risk.
- **Caveats:** one contract per market can't show queue position or depth at larger sizes. B is a small sample
  (419 markets, about 130 city-weeks). The test period is the same one K1 looked at, but B's zone and rules were
  fixed before running K2.
- **Verdict:** B1 earns a **shadow slot pending owner approval**: post a buy-YES at the best bid at 8pm on evening
  favorites (mid 65–95¢), one contract, and log fills against the tape. A and B2 don't.

---

## R3. Intraday SPY momentum (Gao, Han, Li & Zhou 2018). Registered 2026-11-24, before running
- **Hypothesis:** SPY's return from the previous close to 10:00 New York time predicts its last half hour
  (15:30–16:00) the same day. Long-only version: on days the first-half-hour return is positive, buy SPY at 15:30
  and sell at the 16:00 close.
- **Variant R3b:** on negative days, buy SH (1x inverse) for the last half hour instead.
- **Data:** SIP 30-minute bars for SPY and SH, regular session only, Jan 2016 – Nov 2026. 5 bps per side, so about
  10 bps per round trip.
- **Pass bar:** average return per trade > 0 after costs, with a 95% CI above zero, in both the full period and the
  held-out window (2023+). It also has to be worth the time out of the market: its Sharpe must beat SPY's. If it
  trades about 250 times a year for tiny gains, report that plainly.

## R3 result: intraday SPY momentum: **FAIL (no signal, even before costs)**
2,738 sessions, Jan 2016 – Nov 2026.

| rule | window | trades | bp/trade | 95% CI | CAGR | Sharpe |
|---|---|---|---|---|---|---|
| R3 net of 5 bp/side | full | 1,529 | −10.8 | [−12.1, −9.5] | −14.1% | −4.7 |
| R3 before costs | full | 1,514 | −0.8 | [−2.0, +0.6] | −1.2% | −0.4 |
| R3 before costs | held-out 2023+ | 563 | +0.2 | [−1.3, +1.9] | +0.3% | 0.1 |
| R3b (+ SH on down days) | full | 2,661 | −10.4 | [−11.5, −9.3] | −22.5% | −5.3 |
| SPY buy-and-hold | full | 2,733 days | | | 14.2% | 0.83 |

- The first half hour's direction matched the last half hour's **48.2%** of the time (50% = coin flip).
- 5 bp per side is harsher than SPY's real spread, but before costs the edge is about zero anyway, so cheaper costs
  can't rescue it.
- The published effect (Gao et al., 1993–2013) hasn't held in 2016–2026 SPY data.
- **Verdict:** fail. Don't build it. Half-days put a few post-market 15:30 bars in the sample, too few to matter.

---

## R4. Insider open-market purchases (SEC Form 4). Registered 2026-11-24, before running
- **Hypothesis (Lakonishok & Lee 2001; Jeng, Metrick & Zeckhauser 2003; Cohen, Malloy & Pomorski 2012):** stocks
  bought by their own officers and directors in open-market purchases (transaction code P) outperform for about a
  month, and more so when several insiders buy within a few days ("cluster" buys).
- **Data:** the SEC's quarterly Form 3/4/5 structured data sets (free, EDGAR) for 2016–2026, joined to our daily SIP
  bars.
- **No look-ahead:** a trade counts only from its **filing date**, never the transaction date. Entry is at the next
  trading day's open after the filing date, which is conservative because filings arrive through the day.
- **Rules (fixed now):**
  - **R4a:** any officer or director purchase of at least $10,000. Hold 21 trading days, equal weight, at most 20
    positions.
  - **R4b (cluster):** at least 2 different insiders buying the same stock within 5 calendar days (by filing date).
    Same holding rule.
  - **Tradable filter, all as of the day before entry:** price ≥ $5 and 60-day median dollar volume ≥ $1M, so $10
    positions are realistic. 5 bps per side.
- **Pass bar:** Sharpe above SPY's, worst drop under 35%, final value above SPY's, after costs, 2017–2026, and not
  losing to SPY in the held-out window from 2023. It must also beat plain momentum's final value, per the brief.

## R4 result: insider purchases: **FAIL (worst drop 44%; the edge does not survive realistic costs)**
Run with `uv run python -m trader.backtest.insider`, 2017-03 to 2026-11, $200 start. Data: 310,798 open-market
purchases from the SEC data sets (filed 2016-01-04 to 2026-09-30).

| strategy, full period | $200 → | CAGR | Sharpe | worst drop |
|---|---|---|---|---|
| SPY (benchmark) | $699 | | 0.80 | 34% |
| IWM (small-cap benchmark) | $427 | 8.1% | 0.45 | 41% |
| momentum 12-1 (baseline) | $1,535 | | 0.69 | 60% |
| **R4a, any officer/director buy, 5 bps** | **$2,233** | 28.2% | **1.06** | **44%** |
| R4b, cluster buys, 5 bps | $1,180 | | 0.79 | 57% |

Held-out 2023+: R4a $200 → $658, Sharpe 1.47, worst drop 25% (IWM: $320, Sharpe 0.69).

**Audit (cost sensitivity, R4a):**

| cost per side | full $200 → | Sharpe | worst drop | held-out Sharpe |
|---|---|---|---|---|
| 5 bps | $2,233 | 1.06 | 44% | 1.47 |
| 15 bps | $351 | 0.35 | 49% | 0.62 |
| 30 bps | $21 | −0.72 | 90% | −0.70 |
| 50 bps | $15 | −1.35 | 93% | 0.36 |

- **Turnover is 194× a year** (43,814 trades), and 20,298 orders were skipped for being under $1. The names are mostly
  small caps whose real spread plus impact is 15–50 bps, not 5. At 15 bps the edge is gone (below SPY and IWM).
- Many of these small caps are **not fractionable** on Alpaca, so $10 positions in them can't be placed at all.
- Before costs the signal is real and matches the papers: insiders' buys do outperform for about a month.
- **Verdict:** fail on the pre-registered bar (worst drop 44% > 35%) even at the optimistic 5 bps, and the result
  disappears at realistic small-cap costs. Don't build it. A large-cap-only, lower-turnover variant would be a new
  idea and needs its own pre-registered entry; the literature says the effect is weakest in large caps.

---

## R5. Insider buys v2: liquid large caps, low turnover. Registered 2026-11-24, before running
- **Why:** R4's signal was real before costs but needed small caps and 194× turnover. This asks whether any of
  it survives where a $10 order is really cheap. The literature expects a weaker effect here, so it may fail.
- **Universe:** a stock counts only if it is in that month's point-in-time top-500 universe
  (`data/universe.parquet`), the same one momentum uses.
- **Rules (fixed now):** an officer or director open-market purchase of at least $50,000, by filing date, with
  entry at the next open. Hold 63 trading days (about 3 months), equal weight, at most 20 names (largest
  purchases first). A repeat buy restarts the clock.
- **Costs:** scored at 10 bps per side, also reported at 30 bps.
- **Pass bar (same as every stock idea):** at 10 bps, over 2017-03 to now, Sharpe above SPY's, final value above
  SPY's, worst drop under 35%, and not losing to SPY in the held-out window from 2023. At 30 bps Sharpe must still
  be at least SPY's.

## C1. Crypto slow trend filter, BTC + ETH (spot, long-only). Registered 2026-11-24, before running
- **Hypothesis (time-series momentum in crypto, e.g. Liu & Tsyvinski 2021):** holding BTC/ETH only while each is
  above its 20-week moving average avoids most of the deep crypto drawdowns and keeps most of the upside.
- **Data:** Coinbase public daily candles (no key), BTC-USD and ETH-USD, from 2017-01.
- **Rules (fixed now):** every Monday's close, for each coin, hold it if its close is above its 140-day simple
  moving average, else hold cash. Half the account each, rebalanced weekly, trading at the next day's open.
- **Costs:** 25 bps per side (Alpaca crypto taker fee), also reported at 50 bps.
- **Benchmarks:** SPY buy-and-hold and BTC buy-and-hold.
- **Pass bar:** at 25 bps, 2017-03 to now, Sharpe above SPY's, worst drop under 35%, final above SPY's, and not
  losing to SPY in the held-out window from 2023. Daily returns use every calendar day (crypto trades 7 days),
  annualised with 365.

## R5 result: large-cap insider buys: **FAIL**
Run with `uv run python -m trader.backtest.insider_v2`: 3,328 signal days in 542 stocks, 22× turnover a year.

| | $200 → full | Sharpe | worst drop | held-out $ | held-out Sharpe |
|---|---|---|---|---|---|
| SPY | $699 | 0.80 | 34% | $398 | 1.23 |
| R5 at 10 bps | $463 | 0.47 | 50% | $466 | 1.16 |
| R5 at 30 bps | $294 | 0.28 | 52% | $397 | 0.97 |

- It fails every part of the bar on the full period. 2022 was −36% against SPY's −18%.
- The held-out years look fine on dollars ($466 vs $398) but not on risk-adjusted return (1.16 vs 1.23).
- Together with R4: insider buying only pays in small caps, and there costs eat it. **Close the insider line.**

## C1 result: crypto slow trend, BTC + ETH: **FAIL**
Run with `uv run python -m trader.backtest.crypto_trend` (Coinbase daily candles, 2016-06 to 2026-11).

| | $200 → full | CAGR | Sharpe | worst drop | held-out $ | held-out Sharpe | held-out worst drop |
|---|---|---|---|---|---|---|---|
| SPY | $698 | 13.7% | 0.80 | 34% | $398 | 1.23 | 19% |
| BTC buy-and-hold | $9,950 | 49.4% | 0.93 | 84% | $737 | 0.95 | 53% |
| BTC + ETH 50/50, no filter | $21,855 | 62.0% | 1.02 | 88% | $481 | 0.69 | 60% |
| **C1 trend, 25 bps** | $45,466 | 74.7% | 1.28 | **61%** | **$356** | **0.59** | 40% |
| C1 trend, 50 bps | $40,616 | 72.6% | 1.26 | 62% | $339 | 0.55 | 40% |

- The filter does what trend filters do: it cuts the worst drop from 84–88% to 61% and raises the full-period
  Sharpe. But 61% is far over the 35% limit.
- The big full-period numbers come mostly from the 2017 run-up, and they don't repeat. Since 2023 the filter
  **lost to SPY** and to plain BTC: whipsaws in sideways markets cost more than the crashes it dodged.
- Fees barely matter (25 vs 50 bps), because it trades about weekly at most.
- **Verdict:** fail. Crypto as a slow trend overlay doesn't meet the owner's 35% drop limit at any setting tested.
  A 10–20% crypto sleeve inside a stock portfolio would be a different, portfolio-level question and isn't
  registered.

---

## K3. K2's favorites rule on Kalshi DAILY LOW temperature markets. Registered 2026-11-24, before running
- **Why:** K2 B1 passed on daily highs. Daily-low series (KXLOWT*) are also maker-fee-free (API `fee_type:
  "quadratic"`, checked 2026-11-24), and the report found NYC lows trade about 31k contracts a day. If the
  same mispricing exists there, it roughly doubles the rule's capacity.
- **Rule, unchanged from K2 (no re-tuning):** at 8pm local standard time the evening before the market's day,
  for each bucket with YES mid in [65¢, 95¢), post a buy-YES at the best bid. 1 contract, held to settlement.
  The price comes from Kalshi's hourly candlesticks (the last candle at or before the decision time), as in K1/K2.
- **Fills:** from the real trade tape after the decision time, with the same "through" (conservative) and "touch"
  rules as K2.
- **Markets:** every settled daily-low market Kalshi has, in all KXLOWT* series. No weather data is needed.
- **Pass bar (same as K2):** conservative-fill P&L > 0 with a 95% bootstrap CI over city-days above zero, **and**
  positive in Jul–Nov 2026 on its own. At least 100 fills, or the result is "not enough data", not a pass.
- **Also reported, not part of the bar:** the same rule as a taker (buy at the ask, pay the fee).

## K3 result: favorites rule on daily LOWS: **PASS**
Run with `uv run python -m app.backtest.lows` (Trading-bot) on 2026-11-24: 35,026 daily-low markets, 34,473 priced,
583 in the favorite zone with a trade tape. Cents are per contract; the CI is a 95% bootstrap over city-days.

| fill rule | posted | filled | ¢/fill | 95% CI | Jul–Nov ¢ (n) | total, 1 contract |
|---|---|---|---|---|---|---|
| **through (conservative)** | 583 | 416 (71%) | **+5.47** | **[+1.80, +9.28]** | **+2.05** (257) | $22.76 |
| touch (optimistic) | 583 | 459 (79%) | +6.78 | [+3.28, +10.22] | +3.86 (283) | $31.11 |

- **Bar:** P&L > 0 with the CI above zero ✔; Jul–Nov positive ✔; 416 fills ≥ 100 ✔. **PASS.**
- If every order had filled: +11.09¢. So adverse selection eats about half the edge, more than in highs (a quarter).
  Taker at the ask plus fee: +1.78¢ (not part of the bar).
- **The edge is shrinking.** Won-minus-mid by month: +9 to +16¢ from Mar to Jun 2026, then +4, +14, +2, +2 and +5¢
  for Jul to Nov. Jul–Nov passes, but only at +2¢ per fill. Live results must be watched for decay.
- Fill rate is 71%, lower than highs' 89%. Capacity is similar: about 1.5 fills a day.
- **Verdict:** eligible to join the live maker shadow (ADR 0006's slot) as a second series family, **pending owner
  approval**, with the same review after about 100 fills.

## K4 result: favorites rule on TSA weekly checkpoints (KXTSAW): **NOT ENOUGH DATA**
From the side session's branch `claude/k4-tsa-maker-aad47a` (registered in a1c1af0 at 10:12, results in 697c7df at
16:48; not merged). 31 conservative fills against a bar of 100. −0.3¢ per fill, CI [−16, +12], Jul–Nov −4.2¢. It
leans negative and the market is too thin to ever reach 100 fills quickly. **Don't add.**

## K5 result: favorites rule on daily/weekly gas prices: **NOT ENOUGH DATA**
From branch `claude/k5-gas-maker-596e39` (registered in dff0841 at 10:13, results in d193ac8 at 11:10; not merged).
54 fills, +1.2¢, CI [−11.4, +14.4], Jul–Nov −13.9¢. Daily gas markets open on their own close day, so the
evening-before rule rarely applies. **Don't add.**

## V1. Kalshi vs Polymarket US gap logger: built, off by default
Branch `claude/v1-gap-logger-046ceb` (registered in 95593d6, logger in 0eacb7e, ADR 0007; not merged). One live
snapshot: 519 matched games, best gap after fees −0.16¢, 0 qualifying. Read-only. Logging for 4 weeks needs the
branch merged and the repo variable `GAP_LOGGER_ENABLED=true`, **pending owner decision**.

---

## R6. Momentum with weekly stop-losses and profit targets. Registered 2026-11-24, before running
- **Why:** the owner asked for stop-losses, profit-taking and mid-month selling, checked weekly. Han, Zhou & Zhu
  (2016) report that a stop-loss tames momentum crashes; other work finds stops mostly add cost. Profit targets
  cut winners, which momentum relies on, so we expect them to hurt. Test before changing the paper account.
- **Base rule (unchanged):** momentum 12-1, top 20, equal weight, re-ranked on the first trading day of each month.
- **Weekly check (first trading day of each week, after the close; trade at the next open):** for each holding,
  return since its entry close. **Stop:** sell if return ≤ −S. **Target:** sell if return ≥ +T. The freed money
  buys the best-ranked stock (current 12-1 score) not held and not sold this month. A sold stock can't come back
  until the next monthly re-rank. Holdings are not re-equal-weighted mid-month (weights drift with prices).
- **Grid (all reported, 11 variants):** S ∈ {none, 10%, 15%} × T ∈ {none, 25%, 30%, adaptive}, minus none/none.
  "Adaptive" is the owner's "25–30% depending on the swings": 30% for stocks whose 60-day volatility is above the
  median of the 20 picks, 25% for the calmer half.
- **Setup:** $200, 5 bps per side, Mar 2017 – now, plus the held-out window from 2023.
- **Pass bar:** a variant passes only if, in **both** the full and the held-out window, its Sharpe beats plain
  momentum **and** SPY, and its worst drop is under 35%. With 11 variants, one may beat momentum by luck, so a
  single-window win isn't enough.

## R6 result: weekly stop-losses and profit targets: **FAIL (all 11 variants)**
Run with `uv run python -m trader.backtest.r6`, $200, 5 bps per side.

| variant | $200 → full | Sharpe | worst drop | held-out CAGR | held-out Sharpe | held-out worst drop |
|---|---|---|---|---|---|---|
| SPY | $699 | **0.80** | 34% | 19.4% | **1.23** | 19% |
| momentum 12-1 (live paper) | **$1,535** | 0.69 | 60% | **37.7%** | 0.87 | 57% |
| target 25% only | $1,402 | 0.67 | 58% | 30.6% | 0.78 | 53% |
| target 30% only | $1,487 | 0.68 | 57% | 32.4% | 0.80 | 55% |
| target adaptive (25/30) | $1,377 | 0.67 | 57% | 30.9% | 0.78 | 54% |
| stop 10% only | $1,112 | 0.63 | 63% | 30.5% | 0.79 | 56% |
| stop 10% + target 25/30/adaptive | $1,048–1,129 | 0.62–0.64 | 60–61% | 27.5–29.6% | 0.75–0.79 | 50–53% |
| stop 15% only | $1,389 | 0.68 | 63% | 35.6% | 0.86 | 53% |
| stop 15% + target 25/30/adaptive | $1,287–1,345 | 0.67–0.68 | 57% | 29.6–29.9% | 0.78–0.79 | 48–51% |

- **No variant beats plain momentum or SPY on Sharpe in either window, and every worst drop is 48–63%.** FAIL.
- **Stops** sell at the bottom of short dips that momentum stocks often recover from. With a weekly check, a
  "10% stop" can sell well below −10% (how far below wasn't measured). A 10% stop cost about $400 of the final $1,535.
- **Targets** cut the big winners that carry momentum (2025: +74% plain vs +60–97% with targets, but 2024: +59% vs
  +38–48%). They also double or triple the trade count.
- **Control check:** the R6 code with no stop and no target ends at $1,595 (2,545 trades) vs momentum's $1,535
  (2,535). The small gap is one difference: R6 skips a stock with no price that day. The control is slightly
  *better* than plain momentum, so every variant also loses to its own control.
- **Verdict:** don't add stops or profit targets. Monthly momentum stays as it is on the paper account.

## R7. A filings-based "news" score on momentum picks. Registered 2026-11-24, before running
- **Why:** the owner asked for a scorer that reads company news and decides whether a stock is good enough to buy
  or should be dropped. Alpaca's news feed only goes back to 2026-04-29 (checked: zero AAPL/NVDA articles before),
  so headline news can't be backtested. SEC 8-K filings (companies' required "current reports") go back to 2001,
  free. Each one carries item codes: 2.02 results, 5.02 officer/director changes, 4.01/4.02 auditor change or
  restatement, and so on. No LLM: the score is item counts and flags.
- **Evidence:** Chan (2003): stocks that moved *with* news keep drifting; big moves *without* news tend to reverse.
- **Data:** EDGAR `company_tickers.json` (ticker → CIK) and `submissions/CIK*.json` for every stock that was ever
  in the monthly momentum top 40. Tickers that EDGAR can't map (often delisted) count as "unknown", not "no news",
  and are kept in their momentum order.
- **R7a, news-confirmed momentum:** each month, take the top 40 by 12-1 momentum. Score each by the number of 8-Ks
  filed during its formation window (12 to 1 months ago). Hold the 20 with the most filings (ties and unknowns
  broken by momentum rank), equal weight.
- **R7b, red-flag filter:** plain top 20, but skip any stock with an 8-K item 5.02, 4.01 or 4.02 filed in the last
  30 days, taking the next-ranked stock instead.
- **Setup and bar (as R1/R6):** $200, 5 bps, Mar 2017 – now plus held-out from 2023. Passes only if Sharpe beats
  plain momentum and SPY in both windows with a worst drop under 35%.
- **Forward, separate from this test:** live headline news (Alpaca, from Apr 2026) could be logged and scored for the
  paper holdings. That evidence would take many months to build up.

## R7 result: filings-based news score: **FAIL (both variants)**
Run with `uv run python -m trader.backtest.r7`. EDGAR mapped 606 of 646 candidate symbols; 71,115 8-Ks since 2015,
13,876 of them with a red-flag item (5.02, 4.01, 4.02).

| | $200 → full | Sharpe | worst drop | held-out CAGR | held-out Sharpe | held-out worst drop |
|---|---|---|---|---|---|---|
| SPY | $699 | **0.80** | 34% | 19.4% | **1.23** | 19% |
| momentum 12-1 | **$1,535** | 0.69 | 60% | 37.7% | 0.87 | 57% |
| R7a news-confirmed | $1,376 | 0.68 | 59% | 29.2% | 0.76 | 59% |
| R7b red-flag filter | $1,268 | 0.66 | 61% | **38.3%** | 0.91 | 55% |

- Neither beats SPY's Sharpe in either window, and both keep momentum's ~60% worst drop. **FAIL.**
- R7b is slightly better than momentum since 2023 (0.91 vs 0.87) but worse over the full period. That's noise, not
  an edge. Executive exits (item 5.02) are routine at big companies, so the filter mostly skips good stocks.
- **Caveat:** 82 mapped companies file no 8-Ks at all (mostly foreign issuers, which file 6-Ks), so R7a counted
  them as "no news" rather than "unknown". It's a small share of the pool and doesn't change the verdict.
- **Verdict:** filing counts and red flags don't improve momentum. A real headline-news scorer can only be judged
  forward (Alpaca news starts Apr 2026), so it would need months of logging before it means anything.

## Kalshi rules simulated like the stock table (descriptive, 2026-11-24; not a new test)
$100 start, every conservative fill from K2/K3/K4/K5 in date order (script: session scratchpad `kalshi_sim.py`).
Stake = share of the current bankroll per bid, capped at 25% of the contracts that traded through our price, and a
day's bids never exceed the bankroll. Sharpe uses calendar days (√365).

| rule | size | period | fills | $100 → | Sharpe | worst drop | losing months |
|---|---|---|---|---|---|---|---|
| B1 highs | 1 contract | Mar–Nov 2026 | 374 | $126.50 | 4.32 | 2% | 0/9 |
| B1 highs | 2% | | | $174.97 | 3.57 | 7% | 0/9 |
| B1 highs | 5% | | | $306.44 | 2.87 | 18% | 1/9 |
| K3 lows | 1 contract | Dec 2025–Nov 2026 | 416 | $122.76 | 3.02 | 4% | 3/12 |
| K3 lows | 2% | | | $108.16 | 0.52 | 23% | 5/12 |
| K3 lows | **5%** | | | **$63.41** | −0.63 | **65%** | 5/12 |
| K4 TSA | 1 contract / 5% | Mar–Nov 2026 | 31 | $99.92 / $99.22 | ≈0 | 3% / 12% | 3–4/10 |
| K5 gas | 1 contract / 5% | Mar–Nov 2026 | 54 | $100.67 / $92.60 | 0.25 / −0.24 | 4% / 29% | 3/9 |
| B1 + K3 | 1 contract | Dec 2025–Nov 2026 | 790 | $149.26 | 5.05 | 3% | 1/12 |
| B1 + K3 | 2% | | | $177.28 | 2.35 | 16% | 4/12 |
| B1 + K3 | 5% | | | $144.40 | 0.91 | 53% | 4/12 |

SPY over the same windows: +1.3% (Mar–Nov) to +7.1% (Dec–Nov), worst drop about 11%.

- **Bet size matters as much as the edge.** Lows are positive per contract (+5.47¢) but lose 37% at a 5% stake:
  their losing months (Sep–Oct 2026) came when the bankroll and the volume caps allowed the biggest bets.
- The 1-contract Sharpe is high only because most of the $100 sits idle. Each bid risks under $1.
- The projections spreadsheet's "5% stake" plan was built on highs alone. With lows added, 2% is the most we'd use,
  and sizing should get its own pre-registered test before the live bot bets more than 1 contract.
- V1 can't be simulated: no Polymarket US price history, and the one live check found 0 qualifying gaps.

---

## S1. Kalshi bet sizing and pauses, chosen on old data, judged on new. Registered 2026-11-24, before running
- **Why:** the simulation above showed bet size decides whether a real edge makes or loses money. The owner wants a
  "decider" for amounts and stops. This tests one without overfitting.
- **Rule sets:** B1 highs (K2), K3 lows, K4 TSA, K5 gas, B1+K3, B1+K3+K5. Conservative ("through") fills only.
- **Split:** choose on fills before 2026-08-01 (train); judge once on 2026-08-01 to 2026-11-23 (test). No re-tuning.
- **Grid (216 per rule set):**
  - size: 1 contract; 1%, 2%, 3% of bankroll per bid; ¼ and ½ Kelly. Kelly uses the train edge at its lower 95%
    bound: f = edge / (1 − price); no bets if that bound ≤ 0.
  - daily spend cap: 10%, 25%, 100% of bankroll.
  - pause: none, or no bids for 14 days once the bankroll is ≥ 20% below its peak (the peak resets after).
  - Always: a bid ≤ 25% of the contracts that traded through our price, ≤ 500 contracts, whole contracts.
- **Simulation:** 2,000 paths of 52 weeks, each built by resampling whole weeks of train fills. Stress: the same with
  every outcome cut by half the train edge per contract.
- **Choice (per rule set):** highest 10th-percentile 12-month bankroll, among configs whose median worst drop is under
  35% and whose half-edge median ends at or above $100. Neighbours of the choice are reported (plateau check).
- **Final exam:** the chosen config, run on the real Aug–Nov path from $100 and on 2,000 resampled test paths.
  Passes if the real path ends above $100 with a worst drop under 35% **and** the test median ends above $100.
  1 contract is always reported as the baseline. 216 configs were tried per rule set, so the choice's train numbers
  are optimistic by construction.

## S2. Alpaca portfolio rules, chosen on 2017–2022, judged on 2023–2026. Registered 2026-11-24, before running
- **Why:** add-ons to single-stock momentum keep failing. These are the best-documented portfolio-level ideas not yet
  tested. Each has fixed settings from its paper or from a stated reason, so there's nothing to tune.
- **Single rules:**
  - **V: volatility-scaled momentum** (Barroso & Santa-Clara 2015): top-20 momentum, scaled by min(1, 20% /
    the picks' 126-day realised volatility); the rest in cash. 20% ≈ SPY's own volatility.
  - **D: dual momentum** (Antonacci): hold SPY or EFA, whichever rose more over 12 months, if it beat SHY; else AGG.
  - **S: sector momentum:** the top 3 of the 11 sector ETFs by 12-1 return; a slot with a negative 12-month return
    goes to SHY.
  - **H: 52-week-high momentum** (George & Hwang 2004): the 20 stocks closest to their 1-year high.
  - **M70 / M50:** 70/30 and 50/50 SPY / momentum, rebalanced monthly.
  - **P: drawdown pause:** momentum, but hold SPY in any month that starts with always-on momentum more than 25%
    below its peak.
- **Pairs (only natural ones):** V with SPY instead of cash; 70/30 SPY / V; P applied to V.
- **Setup:** $200, 5 bps per side (ETFs), monthly. Train 2017-03 to 2022-12, test 2023-01 to now.
- **Pass bar:** Sharpe above SPY's **and** worst drop under 35% in train, then the same again on test. Block
  bootstrap (3-month blocks) gives the range of outcomes for anything that passes.

## S1 result: Kalshi bet sizing: **B1 highs PASS (sizing helps); lows, TSA and gas FAIL; lows' edge is gone since August**
Script: session scratchpad `s1_sizing.py`. Train ends 2026-07-31; test is 2026-08-01 to 2026-11-23 (18 weeks).
"12-month" figures are from 2,000 resampled years of train weeks; "test real" is the actual Aug–Nov path from $100.

| rule set | train edge (lower bound) | test edge | choice | train 12-mo p10 / median | test real $100 → (worst drop) | verdict |
|---|---|---|---|---|---|---|
| B1 highs | +11.8¢ (+3.4¢) | **+4.7¢** | ½ Kelly, no cap, no pause | $285 / $590 | **$181.74** (21%) | **PASS** |
| B1 highs, baseline | | | 1 contract | $121 / $131 | $112.22 (2%) | PASS |
| K3 lows | +7.5¢ (+2.4¢) | **−0.4¢** | 2%, 10% daily cap | $110 / $139 | $92.54 (22%) | FAIL |
| K3 lows, baseline | | | 1 contract | $108 / $119 | $99.27 (8%) | FAIL |
| K4 TSA | −0.3¢ (−22¢) | | no bets (Kelly = 0) | $100 | $100 | FAIL |
| K5 gas | +7.6¢ (−10¢) | | 3%, 10% cap | $102 / $121 | $93.05 (11%) | FAIL |
| B1 + K3 | +8.6¢ (+3.9¢) | +2.7¢ | 3%, 25% cap | $212 / $340 | $115.55 (24%) | PASS (B1 carries it) |
| B1 + K3 + K5 | +8.5¢ (+3.5¢) | | 3%, 10% cap | $213 / $347 | $107.38 (27%) | PASS (barely) |

- **B1 is the only real survivor.** Its edge fell from +11.8¢ (Mar–Jul) to +4.7¢ (Aug–Nov) but stayed positive,
  and bigger bets still paid: ½ Kelly turned $100 into $182 in 18 weeks, with a 21% worst drop.
- **Lows' edge vanished in the test window** (−0.4¢ on 168 fills). K3's earlier PASS rested on Dec–Jul.
  **Withdraw the recommendation to add lows to the live bot.** Adding lows or gas to B1 only dilutes it.
- **No plateau, a warning:** for B1 the train result rises steadily with bet size, so the choice sits at the edge of
  the grid (½ Kelly). That's driven by a train edge that later halved. ½ Kelly bets up to ~17% of the bankroll on
  one 90¢ favourite.
- **Pauses and daily caps never helped** B1 in train (the chosen config uses neither).
- **For the paper bot:** move from 1 contract to **¼ Kelly** (train p10 $182, median $280), not ½. The pre-registered
  choice passed, but with the edge already halved, the smaller size is the prudent first step. Re-check after 100
  live fills.

## S2 result: portfolio rules: **all FAIL; 70/30 SPY/momentum comes closest**
Run with `uv run python -m trader.backtest.s2`. Train Mar 2017 – Dec 2022, test Jan 2023 – Nov 2026, $200, 5 bps.

| rule | train $200 → | Sharpe | worst drop | test $200 → | Sharpe | worst drop | verdict |
|---|---|---|---|---|---|---|---|
| SPY | $351 | 0.59 | 34% | $398 | 1.23 | 19% | benchmark |
| momentum 12-1 (paper) | $445 | 0.54 | 60% | $690 | 0.87 | 57% | fail |
| V vol-scaled momentum | $307 | 0.44 | 35% | $392 | 0.96 | 22% | fail |
| D dual momentum | $217 | 0.17 | 38% | $320 | 0.86 | 19% | fail |
| S sector momentum | $356 | 0.59 | 31% | $359 | 1.09 | 16% | fail on test |
| H 52-week high | $330 | 0.53 | 29% | $294 | 0.61 | 27% | fail |
| **M70 70% SPY / 30% momentum** | $392 | **0.61** | **36%** | $506 | 1.11 | 26% | fail (drop 1 pt over) |
| M50 50/50 | $424 | 0.60 | 37% | $572 | 1.01 | 36% | fail |
| P drawdown pause | $556 | 0.67 | 43% | $433 | 0.67 | 51% | fail |
| V, rest in SPY | $399 | 0.56 | 40% | $538 | 1.08 | 27% | fail |
| 70% SPY / 30% V | $347 | 0.59 | 34% | $401 | 1.24 | 17% | fail (ties SPY) |
| P + V | $328 | 0.49 | 35% | $373 | 0.90 | 22% | fail |

- **Nothing beats SPY on risk-adjusted return in both windows.** Volatility scaling does cut momentum's drop
  (60% → 35%), as the paper says, but it gives up as much return.
- **The SPY/momentum mixes are the most useful finding.** M70 over the full period: $993 vs SPY's $699, Sharpe 0.81
  vs 0.80, worst drop 36% vs 34%. It's essentially SPY's risk with part of momentum's upside. It misses the bar by
  one point of drawdown and loses to SPY on test Sharpe (1.11 vs 1.23), so it is **not a pass**. Picking it after
  seeing these numbers would be the overfitting we're trying to avoid.
- Resampled 5 years from $200 (median / bad case p10): SPY $394 / $263; M70 $483 / $282; momentum $647 / $226.
- **Verdict:** no change to the paper account is justified by the bar. If the owner wants a smoother paper account,
  M70 is the candidate to *register for forward paper testing*, not to adopt.

## K6. B1 favourites rule at 8am instead of 8pm. Registered 2026-11-24, before running
- **Why:** the owner asked. At 8am on the market's own day, forecasts are sharper, so the favourite-longshot gap may
  be smaller (more informed prices), or bigger (more trading, more retail flow). K1 found the bias at both times.
- **Rule, unchanged except the time:** at 8am local standard time on the market's day, for each daily-high bucket
  with YES mid in [65¢, 95¢), post a buy-YES at the best bid. 1 contract, held to settlement. Price from Kalshi's
  hourly candlesticks (the K1 "am" snapshot).
- **Data:** every daily-high market from 2026-03-01 (K2's test period). The trade tape from 8am to close comes from the
  existing K2 download where available (it starts at 8pm the evening before), and from a new download otherwise.
- **Fills, bar:** same as K2. Conservative fills, ¢ > 0 with the 95% CI over city-days above zero, Jul–Nov > 0,
  ≥ 100 fills. **Plus the S1 held-out check:** the Aug–Nov edge must also be > 0.
- **Also reported:** the overlap with the 8pm rule (markets both would buy), and 8am + 8pm together.

## K6 result: B1 at 8am: **FAIL**
Run with `uv run python -m app.backtest.morning` (Trading-bot). 644 extra tapes downloaded; no market lacked one.

| rule | posted | filled | ¢/fill | 95% CI | Jul–Nov | Aug–Nov |
|---|---|---|---|---|---|---|
| **8am B1** | 956 | 868 (91%) | +2.21 | [−0.80, +5.00] | +2.94 | +1.90 |
| 8pm B1 (K2, same code) | 419 | 374 (89%) | **+7.09** | [+2.69, +11.25] | +5.40 | +5.06 |
| 8am, markets not also picked at 8pm | 669 | 620 | +0.62 | [−3.15, +4.03] | +2.01 | +0.82 |

- The CI includes zero. **FAIL.** By 8am, forecasts and prices are better informed and most of the favourite
  discount is gone. The new markets 8am adds (not favourites at 8pm) earn about nothing.
- The 8pm rule reproduces K2 exactly in this code, so the scorer is consistent.

## B1 capacity: profit peaks at ~50 contracts per bid (measured 2026-11-24)
Order size N per bid; we get min(N, 25% of the contracts that traded through our bid). From K2's 374 fills:

| N | $/month (Mar–Nov) | ¢ per contract | $/month (Aug–Nov) | avg $ at risk per bid |
|---|---|---|---|---|
| 1 | $2.84 | +6.9 | $3.06 | $0.69 |
| 10 | $23.44 | +6.0 | $23.67 | $6.63 |
| 20 | $39.48 | +5.2 | $35.46 | $12.80 |
| **50** | **$61.63** | +3.5 | **$40.61** | $29.65 |
| 100 | $61.72 | +1.9 | $2.98 | $54.33 |
| 250 | −$151.82 | −2.3 | −$473.09 | $113.36 |

- **Why:** favourites that few contracts trade through win 93–96% of the time (+22–25¢). Those that thousands
  trade through are collapsing and win 39–67% (−3 to −34¢). Volume isn't known in advance, but a big order fills
  fully on the collapses and only partly on the winners.
- **So B1 is worth about $40–60 a month at most, whatever the bankroll.** About $300–500 of Kalshi bankroll is
  enough to reach that. Bigger bankrolls don't earn more from B1. Kelly sizing is fine while it stays under ~20
  contracts per bid.

## K7. Favourite bias screen on Kalshi's biggest fee-free, fast-settling series. Registered 2026-11-24, before running
- **Why:** B1 is real but capped at ~$40–60 a month. The owner wants more edges of the same kind. A scan of all
  16,934 Kalshi series (2026-11-24) shows 16,771 charge makers nothing (`fee_type: quadratic`). The fast-settling
  volume sits in crypto, index, oil and rain series, not weather. Sports stay research-only (standing rule).
- **Series (7):** KXBTCD (Bitcoin hourly above/below), KXETHD (Ethereum hourly), KXINXU (S&P 500 hourly),
  KXNASDAQ100U (Nasdaq hourly), KXINX (S&P 500 daily range), KXWTI (WTI oil daily), KXRAIN (daily rain).
- **Decision time (fixed now):** hourly series 30 minutes before close (1-minute candles); daily series 6 hours
  before close (hourly candles). Price = the last candle ending at or before that time.
- **Sample:** markets closing 2026-03-01 to 2026-11-23. Per series, 200 random events closing before 2026-08-01
  (train) and 150 after (test). In each event, the 12 markets with the most volume.
- **Stage 1, calibration (no fills):** favourites = YES mid in [65¢, 95¢). Passes if, on train events, outcome minus
  mid is ≥ +3¢ with a 95% bootstrap CI (over events) above zero and at least 200 favourites. This is the bias B1
  harvests; weather showed +5 to +15¢.
- **Stage 2 (only for stage-1 passes, registered separately before running):** a B1-style maker replay on the trade
  tape, with the K2 bar plus the Aug–Nov held-out check.

## K8. Polymarket US daily temperature: the same favourite bias? Registered 2026-11-24, before running
- **Why:** B1 earns at most ~$40–60 a month on Kalshi, capped by volume. Polymarket US (CFTC-regulated, US API)
  lists daily high/low temperature markets for several US cities, settled on the same NWS climate report. Makers
  pay no fee there (docs.polymarket.us/fees: only takers pay Θ·p·(1−p); Θ = 0.095 at the lowest tier). A second
  venue would be a second, separate volume ceiling.
- **Data:** every closed `tc-temp-*` market (`/v1/markets?categories=climate&closed=true`, from Apr 2026). Price at
  8pm local standard time the evening before (same as B1), from `/v1/price-history` with 1-minute points:
  ask = `longPrice`, bid = 1 − `shortPrice`, last point at or before the decision. Outcome from
  `/v1/markets/{slug}/settlement`. The meaning of 1 vs 0 is checked first: each city-day must settle exactly one
  bucket to 1.
- **Stage 1 bar (calibration, like K7):** favourites (mid 65–95¢) before 2026-08-01: outcome − mid ≥ +3¢, 95% CI
  over city-days above zero, ≥ 200 favourites. Aug–Nov reported separately and must also be > 0.
- **Stage 2 (only if stage 1 passes; needs the owner's OK to pull the exchange's daily time-and-sales CSVs):** a fill
  replay. A trade printed below our bid means our bid would have filled (the "through" rule; the CSV has no side).

## K7 result: no underpriced favourites outside weather; **index hourly favourites look OVERpriced**
Run with `uv run python -m app.backtest.k7_screen` (Trading-bot). "won − mid" = how much more often favourites won
than their price implied; CI = 95% bootstrap over events.

| series | train favs | won − mid (train) | 95% CI | test favs | won − mid (test) | 95% CI | stage 1 |
|---|---|---|---|---|---|---|---|
| KXBTCD Bitcoin hourly | 353 | −2.5¢ | [−8.0, +2.7] | 301 | −0.8¢ | [−5.9, +4.2] | fail |
| KXETHD Ethereum hourly | 124 | +3.3¢ | [−2.4, +8.0] | 247 | +0.3¢ | [−6.1, +6.1] | too few |
| KXINXU S&P hourly | 439 | −3.9¢ | [−9.6, +1.4] | 325 | **−6.7¢** | [−13.1, −0.5] | fail |
| KXNASDAQ100U Nasdaq hourly | 416 | **−14.5¢** | [−22.6, −6.2] | 321 | −6.6¢ | [−13.6, +0.6] | fail |
| KXINX S&P daily range | 0 | – | | 1 | | | no favourites 6h out |
| KXWTI oil daily | 256 | −4.6¢ | [−12.6, +3.0] | 185 | −2.5¢ | [−11.5, +6.4] | fail |
| KXRAIN daily rain | 11 | −24.1¢ | | 48 | −5.9¢ | | too few (listed from Jul) |

- **The weather favourite bias doesn't generalise.** Crypto, oil and rain are close to fair or slightly overpriced.
- **New, unregistered observation:** on the S&P and Nasdaq hourly series, favourites 30 minutes before the close
  won **less** often than priced, in both windows. That's the opposite of weather, and it would be harvested by
  *selling* favourites (buying NO at the bid) as a maker. It was found by looking, so it is a hypothesis, not a
  result. It needs its own registration and a fresh sample (K9) before anything is built.
- Not tested: KXINX at 6 hours out had no favourites (range buckets are spread out that early).

## K9. Sell overpriced favourites on S&P/Nasdaq hourly (maker). Registered 2026-11-24, before running
- **Why:** K7 saw index-hourly favourites win less often than priced (S&P −3.9¢/−6.7¢, Nasdaq −14.5¢/−6.6¢). That was
  found by looking, so this test uses **only events K7 did not sample**.
- **Series:** KXINXU, KXNASDAQ100U (maker fee 0, `fee_type: quadratic`).
- **Rule:** 30 minutes before close, for each market with YES mid in [65¢, 95¢), post a **sell-YES at the best ask**
  (= buy NO). 1 contract, held to settlement. P&L per contract = ask − outcome.
- **Fills (conservative "through"):** a later trade before close where a taker bought YES above our ask
  (`taker_outcome_side == "yes"`, price > ask). Trade tape from the decision time to the close.
- **Sample:** per series, 300 fresh events closing 2026-03-01 to 2026-07-31 and 200 fresh events 2026-08-01 to
  2026-11-23; the 8 highest-volume markets in each.
- **Bar (K2's plus the held-out check):** ¢ per fill > 0 with a 95% CI over events above zero, ≥ 100 fills, and the
  Aug–Nov fills > 0 on their own. Calibration on the fresh sample is also reported.

## K9 result: selling index-hourly favourites: **FAIL (adverse selection)**
Run with `uv run python -m app.backtest.k9_index` (Trading-bot) on 1,000 events K7 never sampled.

| series | window | favourites | won − mid | filled | ¢ per fill | 95% CI | ¢ if every order filled |
|---|---|---|---|---|---|---|---|
| S&P hourly | all | 1,066 | −0.2¢ | 946 | −3.33 | [−6.04, −0.37] | +2.49 |
| Nasdaq hourly | all | 1,088 | −8.4¢ | 618 | −3.77 | [−7.28, −0.06] | +11.64 |
| both | Mar–Jul | 1,297 | −4.3¢ | 866 | −3.84 | [−6.60, −0.82] | +7.40 |
| both | Aug–Nov | 857 | −4.4¢ | 698 | −3.09 | [−6.23, +0.22] | +6.67 |

- Nasdaq favourites are overpriced on fresh data too; the S&P effect did not repeat.
- **But the sells that fill lose about 3.5¢ each.** A resting sell is taken when buyers push the price up, i.e. when
  the index is moving toward that favourite. Unfilled orders would have won; filled ones lose. FAIL.
- Lesson (same as B1's capacity finding): on Kalshi, a "price vs outcome" gap says little until the trade tape shows
  who fills you and when. Taking the overpricing as a taker would pay the spread and the fee, which K1 showed is
  worse.

## K10 / D1 / D2. New markets, and a learned "decider" with and without news. Registered 2026-11-25, before running
- **Why:** the owner asked for (a) more Kalshi and Polymarket markets, and (b) an "AI decider" that reads news and
  picks bets and stocks, tested with and without the news, alone and in combinations, with money numbers.
  There is no LLM API key (standing rule), so the decider is a **trained statistical model**. It is fitted only on
  old data and judged once on newer data, like S1/S2.
- **K10, new markets (stage 1, calibration only; same bar as K7).**
  - Kalshi, picked by volume among recurring non-sports series not yet tested and with data: **KXTEMPMIAH** (hourly
    Miami temperature, 30 min before close, 1-minute candles), **KXGOLDD** (daily gold, 6 h before close, hourly
    candles), **KXBTC15M** (15-minute Bitcoin up/down, 5 min before close, 1-minute candles).
  - Polymarket US: the 3 recurring non-temperature series with the most closed markets, chosen from the market list
    before any prices are pulled; price 6 h before close (or 30 min for markets shorter than a day).
  - Bar: favourites (mid 65–95¢) on events before 2026-08-01: outcome − mid ≥ +3¢, 95% CI over events above zero,
    ≥ 200 favourites. Aug–Nov reported separately. Passes would get a stage-2 fill replay, registered separately.
- **D1, Kalshi decider (daily-high weather, the only market with tapes and an edge).**
  - Candidates: every daily-high market at 8pm the evening before with a trade tape (mid 5–20¢: buy NO at 1 − ask;
    mid 65–95¢: buy YES at the bid). Through-fills only, as K2.
  - Three versions: **D1a** = the B1 rule (no model, baseline). **D1b** = model on market data only (log-odds of the
    mid, spread, city, month). **D1c** = D1b plus the "news" for weather: the GFS and ECMWF forecasts available at
    8pm (their mean and spread turned into a probability for the bucket, with each city's bias and error size
    measured on 2024–Feb 2026 only).
  - Models (settings fixed now, no tuning): logistic regression (C = 1) and gradient-boosted trees (depth 3, 200
    rounds, learning rate 0.05). Fitted on every daily-high market with an 8pm price dated before 2026-08-01.
  - Rule: bet when the model's edge over our price is ≥ θ, θ ∈ {0, 2, 4, 6}¢. θ and the model type are chosen on
    Mar–Jul 2026 fills (most profit with ≥ 100 fills), then judged once on Aug–Nov 2026.
  - Pass: on Aug–Nov, ¢/fill > 0 with the event-bootstrap 95% CI above zero, **and** more total profit at one
    contract than D1a (B1) on the same months. Money: $100, one contract and the S1 ¼-Kelly sizing.
- **D2, Alpaca decider (stocks).**
  - Each month, re-rank the 40 top momentum stocks (the R7 pool) and hold the 20 the model likes best.
  - **D2a** without news: 12-1, 6-1 and 1-month returns, 126-day volatility, distance to the 52-week high, log
    dollar volume. **D2b** with news: plus GDELT news for the company (average tone over the last 30 days, log
    article count over 30 days, and both changes vs the 90 days before). Only news dated before the rebalance day.
    Company names come from SEC's ticker file; ambiguous names (e.g. "Target", "Apple") add noise, and that is
    accepted, not hand-fixed.
  - Target: next month's return minus the pool's median. Ridge regression (alpha 10) and gradient-boosted trees (as
    D1). Walk-forward: refit each January on all earlier months; predictions start 2019.
  - Pass (same as S2): Sharpe above SPY's and worst drop under 35% on 2019–2022, then again on 2023–now.
    Pairs: 70/30 SPY / decider. $200, 5 bps per side.
- **Count of tries:** K10 6 series; D1 2 models × 2 feature sets × 4 θ; D2 2 models × 2 feature sets. Everything is
  reported, including the losers.

## K11. Hourly temperature favourites: confirm on other cities, then replay fills. Registered 2026-11-25, before running
- **Why:** K10 found Miami hourly temperature favourites (KXTEMPMIAH, 30 min before close) won +6.2¢ over their mid
  on Aug–Nov (144 favourites, CI [+1.0, +11.2]). The series only starts in August, so K10's train bar can't be met,
  and Miami was picked from a screen, so its number is optimistic. This checks it on data the screen never saw.
- **Stage 1 (independent confirmation, calibration):** the other hourly temperature series with volume — KXTEMPNYCH,
  KXTEMPNYCHS, KXTEMPLAXH, KXTEMPLAXHS, KXTEMPCHIH, KXTEMPCHIHS, KXTEMPAUSH, KXTEMPDCH. Up to 120 random events
  each (all dates they exist, to 2026-11-23), 8 highest-volume markets per event, price 30 min before close
  (1-minute candles). Pass: pooled favourites (mid 65–95¢) outcome − mid ≥ +3¢, 95% CI over events above zero,
  ≥ 200 favourites.
- **Stage 2 (fills, B1-style, all 9 series incl. Miami):** buy YES at the bid 30 min before close, held to settlement,
  one contract, through-fills on the real trade tape. Pass: ¢/fill > 0 with the event-bootstrap CI above zero,
  ≥ 100 fills, and positive in both halves (events before and after 2026-10-01). Stage 2 is reported whatever stage 1
  says, but only counts if stage 1 passes.

## K11 result: hourly temperature: **favourites ARE underpriced (stage 1 PASS), but resting bids lose (stage 2 FAIL)**
- Stage 1, 8 cities the K10 screen never saw (960 events): 1,184 favourites, outcome − mid **+8.22¢**, CI
  [+6.21, +10.13]. Every city positive (+2.5 to +12.4¢).
- Stage 2, B1-style resting bids, 9 series: 1,328 posted, 431 filled, **−4.96¢/fill**, CI [−9.60, −0.73], −$21.37
  at one contract. Halves: before Oct −8.58¢ (305), Oct–Nov +3.81¢ (126). If every bid had filled: +16.53¢.
- Same story as K9 and B1's capacity curve, stronger: the bids that fill are the ones the market is moving away from.

## K12. Hourly temperature favourites bought at the ask (taker). Registered 2026-11-25, before running
- **Why:** K11 shows the bias is large (+8¢ over the mid) but maker bids are picked off. Paying the ask avoids
  adverse selection (we always fill) at the price of half the spread plus Kalshi's taker fee
  (fee schedule, effective 2026-07-07: round up(0.07 × C × P × (1 − P)); temperature series are standard).
- **Honest caveat:** this rule was thought of after seeing K11's data, and it is scored on the same rows. A pass only
  earns a forward paper test; no money is moved on it.
- **Rule:** 30 min before close, for every market with mid 65–95¢, buy YES at the ask; hold to settlement.
  Net per contract = outcome − ask − 0.07 × ask × (1 − ask) (10-contract lots, so rounding is ignored; 1-contract
  rounding to a whole cent is reported too).
- **Pass:** on the 8 unseen cities' rows: net ≥ +2¢ with the event-bootstrap CI above zero, ≥ 200 buys, and positive
  in both halves (before / from 2026-10-01). Miami reported separately.

## K12 result: taker buys of hourly temperature favourites: **FAIL**
- 8 unseen cities: 1,086 buys, net **−0.91¢** after the taker fee (−1.56¢ with 1-contract rounding), CI [−2.83, +0.93];
  both halves negative. Miami: +0.12¢, CI [−5.60, +5.21].
- The +8¢ bias over the mid is real but sits inside the spread: half the spread plus the 0.07·p·(1−p) fee uses it
  up. Makers get picked off (K11), takers pay too much (K12). No way in at our size.

## K8 result: Polymarket US temperature: **NOT ENOUGH DATA, and nothing to chase**
- All 6,853 closed markets (1,143 city-days, Apr–Nov 2026). Settlement 1 = YES confirmed (every city-day sums to 1).
- Before Aug: 24 favourites, outcome − mid +2.5¢, CI [−14.7, +19.0]: too few. Aug–Nov: 66 favourites, −0.5¢,
  CI [−11.0, +9.3].
- Why so few: Polymarket US uses 1°F buckets (Kalshi 2°F), so the evening before, the leading bucket's median mid is
  ~47¢ and only ~6% of city-days have one at 65¢+. B1's rule barely applies. A "leading bucket at any price" rule
  would be new and post-hoc; given K11/K12 (bias real, eaten by spread or adverse selection), not worth the owner's
  OK to pull the exchange's trade files.

## K10 result: new markets: **nothing passes stage 1** (too few before Aug, or the wrong sign)
- Kalshi (favourites, outcome − mid):
  - KXTEMPMIAH: series starts after Aug, so 0 train favourites; Aug–Nov 144, **+6.2¢**, CI [+1.0, +11.2]. Not a
    pass (no train data), but it led to K11, which confirmed the bias on 8 more cities and then failed on fills.
  - KXGOLDD: train 198, **−9.5¢** (favourites overpriced); Aug–Nov −5.0¢.
  - KXBTC15M: train 172, −0.6¢; Aug–Nov 107, +3.9¢, CI [−2.4, +10.0].
- Polymarket US: recurring non-temperature markets are all sports games (cbb 1,484, nba 475, nhl 309 closed). Of
  2,266 games screened, only 41 had a two-sided price 6 h before the end, all before Aug: cbb 20 at +1.9¢, nba 21
  at −14.2¢. Too few; most games have no book until close to tip-off.

## D1 result: Kalshi decider: **FAIL (all versions); D1c makes more dollars but its CI includes zero**
- Aug–Nov 2026, through-fills, one contract:
  - D1a (B1 rule): 261 fills, +5.06¢, CI [−0.38, +10.34], $13.20.
  - D1b (trees on market data, θ = 2¢ chosen on Mar–Jul): 2,385 fills, +0.46¢, $11.08. FAIL.
  - D1c (trees + GFS/ECMWF forecasts, θ = 2¢ chosen): 1,956 fills, +1.36¢, CI [−0.25, +2.88], $26.51. Beats D1a's
    dollars, but the CI includes zero → FAIL by the registered bar.
- $100 from Aug 1: B1 $113.20 (1 contract, worst drop 3%), $139.95 (¼ Kelly, 10%); D1b $110.27 / $110.64 (32%);
  D1c $126.51 (7%) / $187.48 (28%).
- Reading: the forecasts help (D1c ≫ D1b), but per-fill edge is a third of B1's; more trades, thinner, noisier.
  Worth watching live as a shadow, not worth switching to.

## D2a result: stock decider without news: **FAIL (ridge and trees)**
- Walk-forward, refit each January, top 20 of the 40-stock momentum pool, 5 bps per side.
  - SPY: 2019–22 Sharpe 0.68 / worst drop 34%; 2023+ 1.23 / 19%. $200 from Jan 2019 → $652; from Jan 2023 → $398.
  - Momentum 12-1 (live rule): 0.70 / 60%; 0.87 / 57%. $1,563; $690.
  - D2a ridge: 0.50 / 67%; 0.82 / 56%. $934; $592.
  - D2a trees: 0.60 / 59%; 0.85 / 52%. $1,103; $613.
  - 70/30 SPY / D2a ridge 0.65 / 35%, trees 0.69 / 34%; 2023+ 1.10 / 25% and 1.09 / 24%. M70 (70/30 SPY /
    momentum) 0.76 / 36%; 1.11 / 26%.
- The model re-ranking is worse than plain momentum in both periods: it learns nothing the 12-1 ranking doesn't
  already have, and it adds turnover. The pairs are closest to SPY but under it on 2023+ Sharpe.

## D2b: stock decider with news: **NOT RUN (no news data)**
- GDELT's free API rate-blocked this IP (HTTP 429) from ~01:45 to 07:05 on 2026-11-25. One short probe got through
  at 06:10, but the full 2017–2026 queries were refused 10 times in 45 min; 0 of 606 companies downloaded.
- Alpaca's news only starts 2026-04-29 (too short to test). Wikimedia page-views need a contact address in the
  request header, which needs the owner's OK.
- Bar for when it does run: D2b must beat plain momentum, not just D2a (D2a lost to momentum in both periods).
- Options: retry GDELT later from this machine (news_gdelt.py resumes), or the owner OKs a contact address for
  Wikimedia page views as a substitute "attention" signal (a separate pre-registration).

## D2c. Stock decider with Wikipedia attention (news substitute). Registered 2026-11-25, before running
- **Why:** GDELT still refuses this machine (429 again at 14:42). The owner said: retry GDELT, and if it fails use
  Wikimedia. Wikipedia page views are a documented attention signal (e.g. Moat et al. 2013); there is no tone.
- **Data:** for each of the 606 named pool stocks, the top English Wikipedia search hit for the cleaned SEC company
  name (same cleaning as GDELT; ambiguous hits are accepted, not hand-fixed), then daily user page views
  2017-01-01 → now. Request header carries the public repo URL as contact, not the owner's email.
- **Features (added to D2a's six):** log of page views over the last 30 days, and its change vs the 90 days before
  (monthly rate). Only views dated before the rebalance day. Same models, same walk-forward, same costs as D2.
- **Pass:** the D2 bar (Sharpe above SPY and worst drop < 35% on 2019–22 and again on 2023+), **and** better Sharpe
  than D2a on 2023+ (otherwise the news adds nothing). 2 models; both reported. One run, no tuning.
- **Known weakness:** the title map is built from today's Wikipedia; a company whose article is newer just shows
  low or no views early. Accepted.

## D2c result: stock decider with Wikipedia attention: **FAIL (both models)**
- 604 of 606 companies matched (2 with no views); 89% of stock-months have the feature. GDELT still blocked.
  - D2c ridge: 2019–22 Sharpe 0.52 / drop 64%; 2023+ 0.89 / 55%. $200 from 2019 → $1,071; from 2023 → $660.
  - D2c trees: 0.49 / 62%; 0.90 / 53%. $1,004; $660.
  - 70/30 SPY / D2c: 2023+ Sharpe 1.14 (ridge) and 1.12 (trees), drops 24–25%; still under SPY's 1.23 / 19%.
- Attention helps a little on 2023+ (Sharpe +0.05 to +0.07 over D2a, the second part of the bar is met) but nowhere
  near SPY, and the 2019–22 trees version got worse. Not a usable edge. Stock "deciders" are closed for now.

## F1. Forward paper test: B1 1 contract vs B1 ¼ Kelly vs D1c decider ¼ Kelly. Registered 2026-11-25, before running
- **Why:** the owner wants the D1c decider (failed D1's bar, but most backtest dollars) tested live against B1 at
  ¼ Kelly and B1 as it runs. ADR 0007 in kalshi-forecaster; three maker arms on the same live markets.
- **Arms:** `B1-fav-bid` (1 contract), `B1-kelly` (edge 3.42¢), `D1c-kelly` (frozen model, θ = 2¢, favourites buy YES
  at the bid, longshots buy NO at 1 − ask). Kelly arms start with $100 each; sizing and fill rules as in D1's money().
- **Review:** 2027-02-25 (3 months), or earlier only to stop an arm whose bankroll falls 30% from its peak.
- **D1c beats B1-kelly** only if, at review: D1c's settled ¢/contract > 0 with the event-bootstrap 95% CI above zero,
  **and** its bankroll is above B1-kelly's, **and** its worst drop is under 30%. Otherwise B1 stays the rule.
- **¼ Kelly replaces 1 contract for B1** only if B1-kelly's ¢/contract > 0 and worst drop < 25%, with ≥ 100 settled
  fills. Same model, same thresholds for the whole test: no refits, no tuning.

## K13. Bucket-sum mispricing on Kalshi daily highs. Registered 2026-11-25, before running
- **Why:** each daily-high event is a set of buckets that cover every temperature; exactly one pays $1. Buying YES on
  every bucket costs Σ ask and always pays $1; buying NO on every bucket costs Σ(1 − bid) and always pays n − 1.
  If either costs less than it pays after fees, that is an arbitrage, not a forecast. The bucket sums have **not**
  been looked at before this entry (only settlement sums, in K8).
- **Overfitting:** the rule has no fitted parameters (threshold = "net of fees > 0"), so it is run once on all data.
  The real risk runs the other way: hourly candle quotes can be stale and show no size, so a backtest overstates
  arbitrage. Hence the tape check below, and a pass earns only a forward test on live order books.
- **Data:** `prices.json` 8pm-eve and 8am quotes (last hourly candle close before each time) for `markets_kept`
  daily highs. An event counts only if its buckets tile the whole line (one "less", one "greater", "between"
  buckets contiguous, no gaps or overlaps) and every bucket has a quote from the **same candle time**.
  A YES ask of 0 or ≥ $1 is "no offer"; a bid of 0 is "no bid"; a set with a missing leg can't be traded.
- **Net per set:** buy-set = 1 − Σ askᵢ − Σ 0.07·askᵢ(1 − askᵢ); sell-set = Σ bidᵢ − 1 − Σ 0.07·bidᵢ(1 − bidᵢ)
  (NO price 1 − bid has the same fee). Reported for 10-set lots (fee unrounded) and 1-set (each leg's fee rounded
  up to a cent).
- **Tape check ("confirmed"):** every leg must have a trade within ±60 min of the snapshot at a price at or better
  than ours on our side (buy-set: a taker-YES trade at ≤ askᵢ; sell-set: a taker-NO trade at ≥ bidᵢ).
- **Pass:** ≥ 30 confirmed 10-lot opportunities with net ≥ +1¢ per set, at least 10 in each half (before / from
  2026-08-01). Then a money path: $100, 10 sets per confirmed opportunity (capped at cash), the first qualifying
  snapshot per event only.
- **Also reported, not judged:** the distribution of the overround (Σ ask − 1 and 1 − Σ bid) by half, and how many
  unconfirmed opportunities there were. A fail closes the idea for these series; a pass means logging live books.

## K13 result: bucket-sum arbitrage on Kalshi daily highs: **FAIL (no real arbitrage)**
- 13,445 snapshots (7,223 events, Oct 2025 – Nov 2026) where every bucket had a same-candle quote. Skipped:
  ~2,900 per snapshot time with a missing quote, ~500–700 with quotes from different candles, 176 events that don't tile.
- The set is normally **overpriced to the taker**: Σ ask − 1 median +9¢ before Aug, +7¢ from Aug (p10 +2–3¢). Buying
  all buckets costs ~$1.07–1.09 for a $1 payout. Σ bid sits a little under $1 (median 1 − Σ bid = +2–4¢).
- Net ≥ +1¢ after the taker fee (10-lot): **28 snapshots** in total, 25 before Aug and **1 from Aug**, at +1.0 to
  +3.0¢ per set. With 1-set fee rounding (each leg's fee rounds up to a cent, ~6¢ per set) **none** is positive.
- **Confirmed by the tape: 0.** Disclosed gap: only 33 of their 168 legs have trades in our cached tape (it was pulled
  for other tests), so the tape check can't confirm most of them either way. The verdict doesn't depend on it: the
  later half has 1 opportunity (bar: ≥ 10), and even counting every unconfirmed one at 10 sets the total would be
  about **$4.93 over 14 months** before any stale-quote losses.
- **Conclusion:** no free money in the bucket sums; the overround is Kalshi's version of the bookmaker's margin and
  it has narrowed (9¢ → 7¢), which is good for B1 (cheaper favourites) but leaves no arbitrage. Not taking it forward.
  (Σ bid > 1 in ~5–15% of snapshots hints at a maker-side "sell the set" idea, but that would be post-hoc and needs
  every leg to fill, which K11 shows is where makers get picked off. Not pursued.)

## G-series: growth with controlled risk. Registered 2026-11-25, before running
- **Why:** the owner wants faster growth with controlled risk (ADR 0003 sets the growth bar). The only way to earn
  more than an asset with an edge is more exposure to it; for a cash account that means leveraged ETFs, timed by
  rules whose settings come from published papers. Kalshi side: how far B1 scales with budget.
- **Overfitting controls:**
  - every variant listed here is run and reported;
  - each grid is judged by its **median** variant and the share that pass;
  - a deflated Sharpe ratio (Bailey & López de Prado 2014) is given for the best of all 54 stock variants (36 + 12 + 6);
  - only a forward paper test can adopt anything.
- **Common:** $200, 5 bps per side, trade at the next open, BIL as the cash asset; SPY buy-and-hold is the benchmark.
  Train 2017-03 → 2022-12, test 2023-01 → now. **Bar (ADR 0003), in both periods:** CAGR ≥ SPY + 3 pts,
  Sharpe ≥ 0.9 × SPY's, worst drop < 40%. **A grid passes** if its median variant passes **and** ≥ 2/3 of its
  variants do.
- **G1: B1 capacity (Kalshi, measurement, no pass/fail).**
  - Data: the saved Aug–Nov 2026 B1 fills, which include each order's through-volume.
  - Run the D1/S1 money rule at bankrolls $100, $300, $1k, $3k, $10k, $30k, at ¼ and ½ Kelly (edge 3.42¢), each
    with and without the 500-contract cap. Fills are capped at 25% of through-volume.
  - Capacity = the largest bankroll whose % return is at least half of the $100 % return.
  - Caveat: at size our own orders would change the queue, so this is an upper bound.
- **G2: leveraged trend** (Gayed & Bilello 2016, "Leverage for the Long Run"; the rule predates our data).
  - Rule: hold the index fund when its unleveraged index closes above its N-day average, else BIL.
  - Grid: index {S&P: SPY/SSO/UPRO, Nasdaq-100: QQQ/QLD/TQQQ} × leverage {1, 2, 3} × N {150, 200, 250} ×
    check {daily, weekly} = 36 variants.
  - Judged as two grids, 2× and 3× (12 variants each); the 1× variants are reference only.
- **G3: volatility-targeted S&P exposure** (Moreira & Muir 2017; Harvey et al. 2018).
  - Weekly exposure E = min(cap, target / realised vol of SPY over L days), built from SPY/SSO/UPRO with BIL.
  - Grid: target {12, 16, 20}% × L {20, 60} × cap {2, 3} = 12 variants.
- **G4: the M70 near-miss with a vol-targeted S&P sleeve.**
  - 30% momentum 12-1 (top 20, picks refreshed monthly) + 70% G3 sleeve (cap 2), rebalanced weekly.
  - Grid: target {12, 16, 20}% × L {20, 60} = 6 variants. Plain M70 is shown as reference, not judged.
- **Prior, stated now:**
  - G2 likely fails the 40% drop limit: trend filters whipsawed in 2018, 2020 and 2022 (see R2), and leverage
    multiplies that.
  - G3 and G4 have the best evidence, but a pass is far from certain.

## G1 result: B1 capacity: **about $300–1,000; bigger bankrolls LOSE money (adverse selection)**
Script: Trading-bot `app/backtest/g1_capacity.py`, on the 261 saved B1 fills of Aug–Nov 2026 (18 weeks).

| start | ¼ Kelly end (return, worst drop) | ½ Kelly end (return, worst drop) |
|---|---|---|
| $100 | $140 (+40%, 10%) | $187 (+87%, 17%) |
| $300 | $401 (+34%, 11%) | $446 (+49%, 18%) |
| $1,000 | $1,119 (+12%, 16%) | $1,058 (+6%, 23%) |
| $3,000 | $2,672 (−11%, 24%) | $2,063 (−31%, 40%) |
| $10,000 | $5,971 (−40%, 43%) | $3,922 (−61%, 63%) |

- Capacity by the registered rule (return ≥ half of $100's): **$300** for both sizes, with or without the 500 cap.
- **Why it turns negative:** filled losers had a median **2,628** contracts trade through our price vs **557** for
  winners. Fills with ≥ 1,000 through-volume win 54% of the time and average −15.7¢; with ≥ 4,000, 37% and −32.9¢.
  When the favourite is about to lose, sellers swamp the bid and fill a big order completely. When it's about to win,
  only a few contracts trade through. A small order fills either way; a big one is filled mostly on the losers.
- **Conclusion:** B1 is a small-account edge. Adding budget beyond ~$1k does not add profit and, at ¼ Kelly, makes it
  negative. (A per-order contract cap could be the fix, but that's a new rule and would need its own pre-registration.)

## G2–G4 result: leveraged trend, volatility targeting, M70 + vol sleeve: **all FAIL (0 of 42 judged variants)**
Script: `uv run python -m trader.backtest.g_growth`. Bar (ADR 0003): train CAGR ≥ 13.1%, Sharpe ≥ 0.53, drop < 40%;
test CAGR ≥ 22.4%, Sharpe ≥ **1.11**, drop < 40%. SPY: train 10.1% / 0.59 / 34%; test 19.4% / 1.23 / 19%; $200 → $699.

| grid (median variant) | train CAGR / Sharpe / drop | test CAGR / Sharpe / drop | share passing |
|---|---|---|---|
| G2 2× trend | 17.9% / 0.70 / 40% | 26.6% / 0.91 / 28% | 0% |
| G2 3× trend | 23.0% / 0.69 / 55% | 34.9% / 0.87 / 41% | 0% |
| G3 vol target | 9.9% / 0.60 / 27% | 16.7% / 0.97 / 19% | 0% |
| G4 30% mom + vol sleeve | 13.3% / 0.68 / 29% | 25.2% / 1.02 / 27% | 0% |

- **What fails is the test Sharpe.** 2023–26 was an unusually smooth bull market (SPY Sharpe 1.23); every leveraged
  or timed version earned more but was bumpier, topping out at about 1.04–1.10.
- **Closest:**
  - **G4 30% momentum + vol 20% L20:** $200 → $1,218 (vs SPY $699); passes train (15.6% / 0.72 / 30%) and test
    CAGR and drop (28.2%, 28%), but test Sharpe is 1.02.
  - **G2 Nasdaq 2× MA150 weekly:** $200 → $2,664; train 28.2% / 0.92 / 34%, test 34.2% / 1.04 / 28%.
  - Caveat on Nasdaq: that the Nasdaq-100 beat the S&P over 2017–26 is known with hindsight. Picking it now is
    exactly the bias this program guards against.
- **3× fails on drop** (median 55% in train): leverage 3× through 2018/2020/2022 is too much, as stated in the prior.
- **Deflated Sharpe** for the best of the 42 judged variants (Nasdaq 2× MA150 weekly, Sharpe 0.97): probability 0.99
  that its Sharpe is above zero after the number of trials. That says it's real return, **not** that it beats SPY's.
  (The 12 1× variants and M70 were reference, not counted as trials.)
- **Verdict:** nothing changes on the paper account. Leverage buys more money with deeper, longer drops, roughly at
  SPY's risk-adjusted rate or a little worse; no rule tested turns it into a better ratio. If the owner wants the
  higher-growth / higher-drop profile anyway, G4 (published method, no Nasdaq hindsight) is the one to register for
  a forward paper test, with the bar written now. The bar is not to be moved again.
