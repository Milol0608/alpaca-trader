# Backtest results

`uv run python -m trader.backtest.run --capital 200 --cost-bps 5`

## Setup
- **Data:** SIP (whole-market) daily bars, adjusted for splits and dividends, 2016 to today. 14,631 US stocks and
  share classes, including 2,000+ delisted.
- **Universe:** each month, the 500 most-traded stocks priced at least $5, plus 40 ETFs (including SH, a 1x inverse
  S&P fund). It uses only data from before that month. 107 delisted stocks appear in it over the decade.
- **Engine:** decides after the close and trades at the next open. Long-only, no leverage (cash account). Costs are
  5 bps per side. Orders under $1 are skipped. A strategy only ever sees data up to its decision day. A holding with
  no bar for 5 trading days is closed at its last price (delisting). Zero prices are treated as missing.
- **Parameters:** textbook values, fixed before looking at this data. Nothing was tuned.

## Baselines, 2017-03-01 to 2026-11-23, $200 start (2026-11-24)

| strategy | final | CAGR | vol | Sharpe | max drawdown | turnover/yr |
|---|---|---|---|---|---|---|
| **SPY buy-and-hold** | **$699** | **13.7%** | 18.1% | **0.80** | 34% | 0.1x |
| momentum 12-1, top 20 | $1,535 | 23.4% | 46.3% | 0.69 | 60% | 7.6x |
| reversal 5d, top 20 | $487 | 9.6% | 41.4% | 0.43 | 66% | 94x |
| low volatility 60d, top 20 | $456 | 8.9% | 13.6% | 0.69 | 28% | 9.4x |
| trend-following ETFs 200d | $375 | 6.7% | 11.8% | 0.61 | 22% | 4.5x |

Year by year: momentum's lead comes from 2019–2020 and 2024–2025. It lost to SPY in 2017, 2021, 2022 and 2023.

**Reading:** none of the baselines beats SPY on risk-adjusted terms (Sharpe). Momentum made more money, but with
2.5× SPY's volatility and a 60% drawdown, which is close to what leveraged SPY would have done. Low volatility and
trend-following give smaller drawdowns at the cost of return. That matches the published evidence: these effects
are real but small after costs, and none is a free lunch. These are the baselines that news signals, intraday
strategies and combinations have to beat.

## Bugs found on the way (fixed before these numbers)
1. **Money leak.** A holding with no price that day was counted as spendable and also kept. Cash went negative and
   was clipped to zero, creating money. Low-vol showed $1.6M (152% a year) before the fix. The engine now sells first,
   never spends money it doesn't have, and asserts cash ≥ 0. Tests check that money is conserved.
2. **Wrong feed.** `.env` still said `DATA_FEED=iex`, which has no data before Aug 2020. Re-downloaded on SIP.
3. **Reused tickers and zero prices** (AMTD, VAL): handled by the delisting rule and by treating zero prices as missing.
