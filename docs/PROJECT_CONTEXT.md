# Project context: source of truth

**Last updated: 2026-11-24 (owner decisions on goal, max drop, tennis).** This file is the single source of truth for both trading bots. Read the raw version
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

## Owner decisions (2026-11-24)
- **The goal every test is judged against:** beat buy-and-hold SPY after costs, *risk-adjusted* (higher Sharpe),
  out of sample, with a **worst drop under 35%** (about SPY's own worst in the test period). For Kalshi: beat the
  market price after real fees, out of sample. "X% in a month" is not a goal; a backtest showing it is a bug.
- **Sports:** no sports for trading. **Tennis is allowed as research only.** If the research is good, a thorough
  test gets built before anything runs, still with no paper slot without the owner's approval.
- **Research backlog:** the owner's brief (Nov 24, "research and test backlog") is worked in priority order. Each
  experiment is pre-registered in `docs/RESEARCH.md` (hypothesis and pass bar *before* running), and only passing
  items get a paper or shadow slot, after owner approval.
- **Real money:** not before the 1–2 month review. Suggested start then: $400–500 plus $25–50 a month, the owner's
  call. Separate accounts if friends join, and legal advice before any pooling.

## Bot 1: kalshi-forecaster (https://github.com/Milol0608/kalshi-forecaster, public)

### What Kalshi is and what we trade
- Kalshi is a US-regulated (CFTC) prediction market. Each contract pays **$1 if YES** happens, $0 otherwise, and
  trades between 1¢ and 99¢. The price is roughly the market's probability.
- We trade only **daily high-temperature markets** for 24 US cities (e.g. "Will NYC's high be 44–45°F on Nov 25?").
  Each city-day is an *event* with several buckets that together cover every possible temperature: exactly one
  bucket settles YES.
- **Settlement source:** the official NWS daily climate report for a named station: Central Park (KNYC), Chicago
  Midway (KMDW), Houston Hobby (KHOU), Dallas DFW, DC Reagan (DCA), and so on. Since Aug 2026 Kalshi's rules name
  The Weather Company, using the same stations. The "day" is **midnight to midnight local standard time** (it ignores
  daylight saving).
- **Fees:** taker fee = round up(0.07 × contracts × price × (1 − price)), so it's largest at 50¢. No settlement fee.
  Maker (resting) orders on these series pay 0%.
- No sports, no leverage.

### How the bot works (each hourly run)
1. **Scan:** reads all open temperature markets, prices and order books from Kalshi's production API (read-only, no
   keys needed in shadow).
2. **Parse rules:** a regex parser (no AI) reads each market's rules for station, date and bucket range, and
   cross-checks that the event's buckets cover all temperatures exactly once.
3. **Weather:** downloads NOAA's National Blend of Models (NBM) station bulletin (free, public domain), plus the GFS
   and ECMWF ensembles from Open-Meteo for the old model. Official observed highs come from the IEM archive.
4. **Forecast:** turns NBM's forecast high and its uncertainty into a probability for each bucket, calibrated per
   station on past data. That's then **mixed with the market's own price** (a logistic blend that leans about 80% on
   the market). It only forecasts days that haven't started yet.
5. **Shadow trade:** buys when `edge = our probability − ask price − fee ≥ 3¢`. Sizes with quarter-Kelly, capped at
   5% of bankroll per market, 10% per city-day and 25% total. Walks the real order book for realistic fills.
   **Kill switch** at a 30% drawdown from peak.
6. **Settle:** after the NWS report comes out (usually the next morning), it settles positions with real fee math.
7. **Report:** Brier score and log loss against the market, P&L net of fees, drawdown, and run health.
- Everything is logged in Postgres (Neon free tier) with no look-ahead: each decision records exactly what data it
  used and when.

### Hosting
GitHub Actions, started hourly by a cron-job.org job (GitHub's own scheduler never fired), using a token limited to
starting that repo's runs. Free Neon Postgres. Runs with the owner's laptop off. The report flags gaps over 2 hours.

### What the testing showed
- Full backtest: 24 cities, about 44,000 settled markets. Trained before Mar 2026, tested Mar–Nov 2026.
- **Our own model (`ens-v1.1`, GFS + ECMWF):** clearly worse than the market (Brier 0.132 vs 0.105). Trading it lost
  the whole bankroll in simulation. It's retired from trading and only logs forecasts now.
- **NBM alone:** better than our model, still worse than the market.
- **NBM + market blend (`nbm-blend-v1`, now trading):** Brier +0.0008 better than the market, statistically real but
  tiny. Simulated $100 → $151 with a 71% worst drawdown, and the 30% kill switch would have stopped it in Apr 2026.
  The 8am version was inconsistent. Verdict: **a candidate, not proven.** It's judged by forward shadow results.
- What's probably happening: the blend's gain comes from pushing the market's own prices further from 50%, which
  hints that the market slightly underprices outcomes near 0% and 100%. That edge is smaller than taker fees plus the
  spread, which is why market making (0% maker fee) is the next idea.

### Status 2026-11-24
10 open shadow positions ($24.99 of the $100 fake bankroll), opened by the old model on 2026-11-23. None settled yet,
P&L $0.00. Since the NBM blend took over, it has found no trades (its prices are too close to the market's).

### Open ideas
Walk-forward tuning of min edge and bet size; exiting at 8am when the forecast flips; a daily loss limit; a kill switch
that pauses rather than stops; market making with resting orders (0% maker fee); other Kalshi categories.

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
- **Paper trading (live from 2026-11-24, 10:00 New York):**
  - The owner chose momentum 12-1, top 20 (about $9.80 each, $196 invested, 2% cash buffer), among stocks Alpaca
    allows as fractional shares.
  - It rebalances when the account is empty or on the first weekday run of each month. Weekdays 10:00 New York on
    GitHub Actions, started by cron-job.org.
  - Guards: paper host only, no order over 15% of equity, orders under $1 skipped, never spends more cash than it
    has, and tagged orders, so a double trigger can't trade twice.
  - First planned buys (dry run): MRNA, SNDK, AXTI, TWST, MU, TXG, DELL, AAOI, LITE, MRVL, HPE, ASX, OKTA, RVMD, STX,
    INTC, AMD, VLO, MPC, WDC. Heavy in semiconductors and tech, which is what 12-month momentum picks after a tech run.
  - All five baselines are forward-tracked as simulated $200 portfolios from 2026-11-23. Results are on each run's
    GitHub summary page.
- **Planned next:**
  1. Hourly data and intraday strategies (the owner wants intraday and daily tested).
  2. Walk-forward tuning.
  3. News signals from **SEC EDGAR** (official filings: 8-K events, Form 4 insider trades), **GDELT** (global news
     volume and tone, history since 2015) and **press-release wires** (collected from now on). Scored locally (no
     LLM). Kept only if they beat the price-only baseline out of sample. SEC requests carry a contact email (set,
     kept private).
- **Timeline:** both bots paper/shadow-trade for 1–2 months, then the owner reviews the results and decides.

## Research results so far (details in docs/RESEARCH.md)
- **R1 momentum + low vol: FAIL.** $540 vs SPY's $699, Sharpe 0.72 vs 0.80. It halves momentum's drop (34%) but
  gives up most of the return.
- **R2 momentum + SPY 200-day crash filter: FAIL, badly.** $241 (cash) or $111 (SH). It sells at the lows and misses
  V-shaped rebounds: Apr 2026 momentum +43%, filter −3%.
- **K1 Kalshi favorite-longshot bias: REAL but only a maker could use it.**
  - Longshots are overpriced by about 1–1.5¢ and favorites underpriced, out of sample.
  - Taking it (paying the fee) loses about 0.4–1¢ per contract.
  - As a maker, the upper bound is +1.5–2.5¢ per contract.
  - The gap may be shrinking: about −1.5¢ in late 2025, −0.3¢ to −0.8¢ in Oct–Nov 2026.
  - Next is **K2**, a fill simulation from real Kalshi trade history.
- **Next in the backlog:** K2 (maker fills), the Kalshi liquidity rule, the tracked-portfolio cap, P2 items (intraday
  SPY momentum, insider buying, daily lows, rain, TSA), and tennis as research only.

## How to use this in a phone chat
Discuss and explore ideas, questions and trade-offs. Anything decided should be written back into this file (via the
desktop session) to become true. Mark guesses as guesses, and say plainly when something hasn't been tested.
