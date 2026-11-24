# 0002: How the paper account trades

## Context
The owner chose momentum 12-1 (top 20) for the $200 paper account, after a backtest in which no baseline beat SPY
risk-adjusted. Runs are daily on GitHub Actions with no stored history. The account is cash-only, fractional, with a
$1 minimum. A double trigger, a network error or a bug must never place duplicate or oversized orders.

## Decision
- **Alpaca is the source of truth** for positions and orders. Nothing is stored between runs, and each run fetches
  fresh data (about 25 s).
- **When to trade:** if the account is empty, or on the first run in a new month (judged from our own filled,
  tagged orders). Market orders, `day`, at about 10:00 New York.
- **How:** sells first (whole positions closed, trims by fractional qty), wait for fills, then dollar-amount buys
  against the cash actually there, keeping a 2% buffer.
- **Guards:**
  - paper host only;
  - the client refuses writes unless built with `allow_orders=True`;
  - no order over 15% of equity;
  - orders under $1 skipped;
  - holdings within 5% of target left alone;
  - every order tagged `mom-YYYYMMDD-SYMBOL-side`, and a run that finds today's tags does nothing;
  - a failed order is never retried blindly.
- **Picks restricted to fractionable stocks** (58% of tradable stocks). The simulated tracking isn't restricted.
- **Forward tracking** of all five baselines as simulated $200 portfolios from 2026-11-23, recomputed each run.

## Alternatives considered
- **Store state in Postgres/Neon.** It's another secret and failure point, and Alpaca already holds positions and
  orders. Rejected for now. Tracking is recomputed, not stored.
- **Whole shares only.** With $10 positions most stocks would round to zero shares. Rejected.
- **Limit orders.** Better prices, but partial and missed fills complicate a once-a-day run. Market orders at
  10:00 on large caps, with the spread counted. Revisit if fills look poor.
- **Trade at the open (09:30).** The first minutes are the most volatile and the SIP data has a 15-minute delay.
  10:00 is used instead.

## Consequences
- The paper account and the simulated "momentum" line can differ: different fill times (10:00 vs the open) and the
  fractionable restriction. The comparison is reported side by side.
- A month's first weekday run may fall on a holiday. The market-closed check then skips it, and the next run does it.

## Status
Accepted, 2026-11-24.
