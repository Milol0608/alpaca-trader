# alpaca-trader: project rules

- **Paper first.** Nothing trades real money unless every live-gate condition in `trader/config.py` passes. Never
  weaken that check, and never place a live order on the user's behalf.
- **Never handle keys.** The user puts them in `.env` and in GitHub secrets themselves. Never print one.
- **The benchmark is buy-and-hold SPY after costs.** A strategy that doesn't beat it out of sample isn't a result.
- **No look-ahead.** Every decision uses only data stamped before it. Universe membership is point-in-time.
- **Walk-forward or it didn't happen.** Fit on the past, score on the next unseen period, roll forward. Keep the
  number of strategies and knobs tried small and written down. Each extra one makes the best backtest look better
  than the future will.
- **Count real costs.** Half the bid/ask spread plus slippage per trade. Paper fills don't simulate market impact,
  so high-turnover strategies get extra suspicion.
- **Verify Alpaca's API against its docs** (docs.alpaca.markets), not memory. Note the date it was checked.
- A real decision gets an ADR in `docs/adr/`.
