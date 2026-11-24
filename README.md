# alpaca-trader

Systematic US stock strategies: backtested walk-forward on years of history, then paper-traded on Alpaca with
fake money. Live trading is locked until a strategy passes a forward test and you choose to unlock it.

Sister project to [kalshi-forecaster](https://github.com/Milol0608/kalshi-forecaster), with the same rules: the
benchmark is the market (buy-and-hold SPY), costs are counted, no look-ahead, and the forward test is what counts.

## Status
- **Milestone 1 (done):** settings and live lock, Alpaca client (data plus read-only account), the history
  download, and the point-in-time universe.
- Next: backtest engine (walk-forward, costs, SPY benchmark), daily and intraday strategies, paper execution,
  hourly hosting, reports.

## Setup
1. `uv sync`
2. In the Alpaca dashboard, switch to **Paper Trading**, create a paper account ($200 for this project), and generate
   its API key. Save it with `copy .env.example .env` and fill `ALPACA_PAPER_KEY_ID` / `ALPACA_PAPER_SECRET_KEY`
   in an editor. Never paste keys in chat or commit them.
3. `uv run pytest`

## Data
```
uv run python -m trader.data.download assets
uv run python -m trader.data.download daily --start 2016-01-01
uv run python -m trader.data.download universe
uv run python -m trader.data.download intraday --timeframe 1Hour --start 2019-01-01
```
- **Bars:** `data/bars/{timeframe}/{year}.parquet`, adjusted for splits and dividends. They're large, re-creatable,
  and gitignored.
- **Feed:** SIP, the whole market. The free plan serves it from Jan 2016, for daily and hourly bars, and withholds
  only the latest 15 minutes, so decisions use bars that closed at least 15 minutes earlier (tested 2026-11-24).
  Hourly bars include pre-market and after-hours (04:00–20:00 New York time). IEX alone starts in Aug 2020.
- **Universe (`data/universe.parquet`):** each month, the 500 most-traded stocks by median dollar volume over the
  previous 60 trading days (price ≥ $5), plus the ETFs in `data/etfs.json`. It uses only data from before that
  month, so a backtest can't pick stocks with hindsight. Delisted stocks are included where Alpaca has them, to
  limit survivorship bias. Leveraged and inverse funds are filtered out by name, and the filtered names are listed in
  `data/excluded_as_funds.csv`.

## Modes
`MODE=paper` (default) or `live`. Live needs all three: `MODE=live`, `LIVE_TRADING_CONFIRMED=yes-i-understand-real-money`,
and a `gate_passed.json` younger than 30 days. Paper and live use separate hosts and separate keys.
