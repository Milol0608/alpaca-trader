"""R5 (docs/RESEARCH.md): insider purchases restricted to the point-in-time top-500 universe, 63-day hold.

  uv run python -m trader.backtest.insider_v2
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import polars as pl

from trader.backtest import strategies as st
from trader.backtest.engine import build_context, run
from trader.backtest.insider import HELD_OUT, START, insider_strategy
from trader.backtest.scorecard import stats, window, yearly
from trader.data.bars import load_bars

MIN_VALUE, HOLD = 50_000, 63


def signals(daily: pl.DataFrame) -> pl.DataFrame:
    p = pl.read_parquet("data/insiders/purchases.parquet").filter(
        pl.col("relationship").str.contains("(?i)director|officer"), pl.col("value") >= MIN_VALUE,
        pl.col("filed").is_not_null())
    uni = pl.read_parquet("data/universe.parquet").select("month", "symbol")
    # universe membership for the month of the filing (built from data before that month)
    p = p.with_columns(pl.col("filed").dt.truncate("1mo").alias("month")).join(uni, on=["month", "symbol"], how="semi")
    return p.group_by("symbol", "filed").agg(pl.col("value").sum(), pl.col("owner").n_unique().alias("owners"))


def main() -> None:
    daily = load_bars(Path("data/bars"), "1Day").select("symbol", "t", "open", "close", "volume").collect()
    sig = signals(daily)
    print(f"R5 signals: {sig.height} signal days, {sig['symbol'].n_unique()} stocks")
    syms = sorted(set(sig["symbol"].to_list()) | {"SPY"})
    months = pl.date_range(date(2016, 1, 1), date.today(), "1mo", eager=True)
    uni = pl.DataFrame({"month": [m for m in months for _ in syms], "symbol": [s for _ in months for s in syms]})
    ctx = build_context(daily, uni, START - timedelta(days=60), date.today())
    first = next(i for i, d in enumerate(ctx.days) if d >= START)
    held = next(i for i, d in enumerate(ctx.days) if d >= HELD_OUT)
    res = {"SPY (benchmark)": run(ctx, st.buy_hold("SPY"), "SPY", start_index=first)}
    for bps in (10, 30):
        res[f"R5 at {bps} bps"] = run(ctx, insider_strategy(sig, hold=HOLD), "R5", start_index=first, cost_bps=bps)
    for label, a in (("FULL 2017-03 .. now", first), ("HELD-OUT 2023-01 .. now", held)):
        print(f"\n{label}\n{'strategy':<20}{'$200 ->':>9}{'CAGR':>8}{'Sharpe':>8}{'maxDD':>7}{'worst mo':>10}{'trades':>8}")
        for k, r in res.items():
            x = stats(*window(r, a))
            n = (len(r.days) - a - 1) / 252
            print(f"{k:<20}{200 * (1 + x['cagr']) ** n:>9.0f}{x['cagr']:>8.1%}{x['sharpe']:>8.2f}{x['max_dd']:>7.0%}"
                  f"{x['worst_month']:>10.0%}{r.trades:>8}")
    r = res["R5 at 10 bps"]
    print(f"\nR5 turnover: {r.traded_value / float(r.equity[first:].mean()) / ((len(r.days) - first) / 252):.0f}x a year;"
          f" skipped < $1: {r.skipped_small}")
    print("\nCALENDAR YEARS")
    for k, r in res.items():
        yy = yearly(*window(r, first))
        print(f"{k:<20}" + "".join(f"{y % 100:>4}:{v:>5.0%}" for y, v in sorted(yy.items())))


if __name__ == "__main__":
    main()
