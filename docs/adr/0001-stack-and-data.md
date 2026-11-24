# 0001: Separate repo, Parquet history, raw HTTP client, point-in-time liquidity universe

## Context
The user wants a stock bot on Alpaca beside the Kalshi bot. It should paper-trade daily and intraday strategies on
about 500 large caps plus major ETFs, with a $200 paper account, for 1–2 months before any decision about real money.
It has to run without the user's laptop. Private-repo Actions minutes are used up, so hosting needs a public repo.
Market history since 2016 for every listed stock is tens of millions of rows.

## Decision
- **A new public repo**, `alpaca-trader`, with its own workflow, secrets and database. No keys ever live in the code.
- **History in Parquet files** (polars), one file per timeframe and year. Postgres, the same free Neon project as
  kalshi-forecaster but a separate database, will hold only live paper-trading state.
- **A raw httpx client** for the few endpoints used, with shapes checked against Alpaca's API reference.
- **IEX feed** (free plan). A paid feed can be switched in with `DATA_FEED`.
- **Universe:** each month, the top 500 stocks by trailing 60-day median dollar volume, using only prior data, plus
  a fixed ETF list. Delisted stocks are included.

## Alternatives considered
- **Same repo as kalshi-forecaster.** Shares hosting, but tangles two bots' code, secrets and failures. Rejected.
- **Store history in Postgres/Neon.** The free tier is 0.5 GB and history is several GB. Rejected for history.
- **alpaca-py SDK.** It's official and covers more endpoints. But it's another fast-moving dependency, and we use
  five endpoints. Rejected for now. The SDK can replace the client later without changing callers.
- **Today's S&P 500 list as the universe.** Easy, but it bakes in survivorship bias (only today's winners) and needs
  a scraped source. Rejected.
- **Paid SIP data ($99/month).** Better intraday volumes. Not justified before anything shows an edge.

## Consequences
- Intraday volume figures are IEX-only and understate the market. Fine for ranking, but don't treat them as market
  volume.
- Fund detection is by name (Alpaca has no ETF flag). That's an assumption, and the excluded list is written out for
  review.
- A reused ticker (a delisted company's symbol reassigned) can mix two companies' histories. Not yet handled.

## Status
Accepted, 2026-11-24.
