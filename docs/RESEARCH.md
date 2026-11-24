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
