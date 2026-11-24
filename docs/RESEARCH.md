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
