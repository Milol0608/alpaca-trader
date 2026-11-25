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
