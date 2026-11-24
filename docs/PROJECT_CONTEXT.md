# Project context: source of truth

**Last updated: 2026-11-24.** This file is the single source of truth for both trading bots. Read the raw version
before answering: https://raw.githubusercontent.com/Milol0608/alpaca-trader/main/docs/PROJECT_CONTEXT.md.
If anything said in chat contradicts this file, the file wins until it's updated. Ideas discussed in chat are
proposals until they're written here.

## Owner and ground rules
- The owner decides everything involving money. Assistants explain, build and test, and never give personalized
  investment advice or claim a strategy will make money.
- **Fake money only today.** Both bots run in paper or shadow mode. Live trading is hard-locked in code behind
  three conditions (MODE=live, a typed confirmation phrase, a passed forward-test gate file younger than 30 days).
- **Honesty rules.** The benchmark is the market (buy-and-hold SPY for stocks, market prices for Kalshi). Costs are
  counted. No look-ahead: decisions use only data available at decision time. Walk-forward or out-of-sample tests
  only. Keep the number of strategies tried small, because every extra one makes the best backtest look better than
  the future. A result that looks too good is treated as a bug until proven otherwise; that has happened twice.
- No Anthropic or LLM API key: scoring and parsing are local (regex, statistics, small local models).
- Keys live only in a local `.env` (gitignored) and GitHub secrets. Never paste keys in chat.

## Bot 1: kalshi-forecaster (https://github.com/Milol0608/kalshi-forecaster, public)
- **What it does:** forecasts Kalshi daily high-temperature markets (24 US cities) and places simulated trades with
  real fee math. Shadow mode with a $100 fake bankroll.
- **Hosting:** GitHub Actions, started hourly by a cron-job.org job (GitHub's own scheduler never fired). Free Neon
  Postgres. Runs with the owner's laptop off.
- **Model history:**
  - `ens-v1.1` (GFS + ECMWF ensembles) lost to the market in a full backtest at both decision times.
  - It was replaced as the trading model by `nbm-blend-v1`: NOAA's National Blend of Models, calibrated per station
    and mixed with the market price.
  - Backtest Mar–Nov 2026: Brier +0.0008 better than the market (statistically real but tiny). The simulation turned
    $100 into $151 with a 71% worst drawdown.
  - Verdict: "a candidate, not proven." It's judged by forward shadow results.
- **Status 2026-11-24:** 10 open shadow positions ($24.99), none settled yet, P&L $0.00.
- **Open ideas:** walk-forward tuning of min edge and bet size; exiting at 8am when the forecast flips; daily loss
  limit; a kill switch that pauses rather than stops; market making (0% maker fee); other categories.

## Bot 2: alpaca-trader (https://github.com/Milol0608/alpaca-trader, public)
- **What it does:** systematic US stock strategies, paper-traded on Alpaca. The paper account has $200, cash only:
  no shorting, no margin, long-only, fractional shares, $1 minimum order.
- **Data:**
  - Alpaca free plan, SIP (whole market) daily and hourly bars since 2016. Only the latest 15 minutes are withheld.
  - About 14,600 stocks, including delisted ones (to avoid survivorship bias), stored locally as Parquet.
  - Monthly point-in-time universe: the 500 most-traded stocks priced ≥ $5, plus 40 ETFs, including SH (1x inverse
    S&P) as the long-only way to hold a falling market.
- **Backtest engine:** decides after the close and trades at the next open. 5 bps cost per side. A strategy only sees
  data up to its decision day. Delistings are cashed out. Tested for money conservation.
- **Baselines, Mar 2017 – Nov 2026, $200 start, after costs:**

  | strategy | ends at | CAGR | worst drop | Sharpe |
  |---|---|---|---|---|
  | **SPY buy-and-hold** | **$699** | **13.7%** | 34% | **0.80** |
  | momentum 12-1, top 20 | $1,535 | 23.4% | 60% | 0.69 |
  | reversal 5d | $487 | 9.6% | 66% | 0.43 |
  | low volatility | $456 | 8.9% | 28% | 0.69 |
  | trend ETFs | $375 | 6.7% | 22% | 0.61 |

  None beats SPY risk-adjusted. Momentum earns more, with leverage-like risk.
- **Paper trading (being built 2026-11-24):**
  - The owner chose momentum 12-1, top 20, about $10 each, to place paper orders.
  - It rebalances on the first run of each month. Since the account starts empty, the first run buys immediately.
  - GitHub Actions run weekdays at 10:00 New York time, started by cron-job.org.
  - All five strategies are also tracked as simulated portfolios on live prices from 2026-11-23.
- **Planned next:**
  1. Hourly data and intraday strategies (the owner wants intraday and daily tested).
  2. Walk-forward tuning.
  3. News signals from **SEC EDGAR** (official filings: 8-K events, Form 4 insider trades), **GDELT** (global news
     volume and tone, history since 2015) and **press-release wires** (collected from now on). Scored locally (no
     LLM). Kept only if they beat the price-only baseline out of sample. SEC requests carry a contact email (set,
     kept private).
- **Timeline:** both bots paper/shadow-trade for 1–2 months, then the owner reviews the results and decides.

## How to use this in a phone chat
Discuss and explore ideas, questions and trade-offs. Anything decided should be written back into this file (via the
desktop session) to become true. Mark guesses as guesses, and say plainly when something hasn't been tested.
