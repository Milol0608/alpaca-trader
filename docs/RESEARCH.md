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
| A1 sell YES at the ask | 8,505 | 81% | +0.55 | [−0.16, +1.28] | +0.34 | +1.40 | +2.62 |
| A2 sell YES at ask − 1¢ | 3,671 | 84% | +0.32 | [−0.77, +1.39] | +0.08 | +0.82 | +2.21 |
| **B1 buy YES at the bid** | 396 | 89% | **+6.98** | **[+2.76, +11.20]** | **+5.10** | +8.28 | +9.51 |
| B2 buy YES at bid + 1¢ | 179 | 93% | +6.52 | [+0.49, +12.43] | +1.59 | +6.98 | +8.45 |

- **Fees verified:** Kalshi's API reports `fee_type: "quadratic"` (taker fee only) for KXHIGH*, KXLOWT* and KXTSAW,
  while KXFED, KXCPI and KXNFLGAME are `"quadratic_with_maker_fees"`. So makers pay no fee in weather.
- **Adverse selection is real but not fatal.** Filled orders earn less than all orders would have (B1: 6.98¢ vs
  9.51¢; A1: 0.55¢ vs 2.62¢). It eats almost all of the longshot edge and about a quarter of the favorite edge.
- **Longshots (A):** the CI includes zero and the later months are near zero. **FAIL.** This matches K1's hint that
  the longshot bias is shrinking.
- **Favorites (B1):** it passes both parts of the bar: CI above zero and Jul–Nov positive. Evening favorites
  (65–95¢) won 5–15¢ more often than priced in every month since March 2026. Even a taker at the ask, paying the
  fee, made +4.66¢ (n = 419). That wasn't pre-registered; K1 skipped it because training had only 26 such markets.
- **Capacity is small.** About 1.5 qualifying markets a day, so 352 fills in 9 months, about $25 per contract of size.
  At 5–10 contracts per order that's roughly $15–30 a month on about $35–70 of capital at risk.
- **Caveats:** one contract per market can't show queue position or depth at larger sizes. B is a small sample
  (396 markets, about 130 city-weeks). The test period is the same one K1 looked at, but B's zone and rules were
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
