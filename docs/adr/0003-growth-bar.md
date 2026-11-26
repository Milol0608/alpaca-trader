# 0003: A growth bar for new stock tests

## Status
Accepted 2026-11-25 (owner chose "Growth bar, 40% drop" when asked). Applies to tests registered from G2 on.
Earlier results keep the bar they were registered with.

## Context
- The 2026-11-24 bar was: Sharpe above SPY's **and** worst drop under 35%, in both periods. Nothing on stocks passed.
- The owner's goal changed: grow faster than SPY over the first 1–1.5 years, accepting somewhat more risk, but with
  the risk controlled ("I can't have the same risk as them if I make more profits").
- Under the old bar a strategy that earns much more than SPY with a slightly lower Sharpe always fails, even if its
  downside is capped. M70 (70/30 SPY/momentum) missed by one drawdown point.

## Decision
New stock tests pass only if, in **both** periods (train 2017-03 → 2022-12, test 2023-01 → now):
- CAGR ≥ SPY's CAGR + 3 percentage points,
- Sharpe ≥ 0.9 × SPY's Sharpe,
- worst drop < 40%.
Grids are judged by their **median** variant plus the share of variants that pass, never by the best one. A pass
earns a forward paper test (the only truly unseen data), not adoption.

## Alternatives considered
- **Keep the old bar plus a CAGR requirement.** Strictest; would reject every leveraged design by construction.
- **Growth bar with a 50% drop limit.** Lets a halving of the account count as acceptable. Rejected by the owner.
- **No bar, pick by eye.** That is how backtests get overfitted. Rejected.

## Consequences
- **M70 is not re-scored under this bar.** Choosing the bar after seeing M70 would be moving the goalposts; it is
  only a candidate for forward paper.
- Leveraged ETFs (SSO, UPRO, QLD, TQQQ) and BIL are added to the backtest universe for these tests only.
- Bigger drops are now possible; the 30%-from-peak stop rule for forward arms still applies.
