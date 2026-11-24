"""Run pre-registered stock experiments (docs/RESEARCH.md) with the scorecard.

  uv run python -m trader.backtest.research
Full window Mar 2017 - today, plus the held-out window from 2023, plus the contribution scenario
($500 start + $0 / $25 / $50 a month) the owner's brief asks for.
"""

from __future__ import annotations

from datetime import date, timedelta

import polars as pl

from trader.backtest import strategies as st
from trader.backtest.engine import build_context, run
from trader.backtest.scorecard import stats, window, yearly
from trader.config import get_settings
from trader.data.bars import load_bars
from trader.data.universe import load_etfs

START, HELD_OUT = date(2017, 3, 1), date(2023, 1, 1)


def main() -> None:
    s = get_settings()
    universe = pl.read_parquet(s.data_dir / "universe.parquet")
    daily = load_bars(s.data_dir / "bars", "1Day").select("symbol", "t", "open", "close", "volume").collect()
    ctx = build_context(daily, universe, START - timedelta(days=400), date.today())
    e = set(load_etfs(s.etfs_file))
    first = next(i for i, d in enumerate(ctx.days) if d >= START)
    held = next(i for i, d in enumerate(ctx.days) if d >= HELD_OUT)
    plans = {
        "SPY (benchmark)": lambda: st.buy_hold("SPY"),
        "momentum 12-1 (baseline)": lambda: st.momentum(e),
        "R1 momentum + low vol": lambda: st.momentum_low_vol(e),
        "R2 momentum, crash filter -> cash": lambda: st.momentum_crash_filter(e),
        "R2b momentum, crash filter -> SH": lambda: st.momentum_crash_filter(e, hedge="SH"),
    }
    res = {k: run(ctx, f(), k, capital=200.0, cost_bps=5.0, start_index=first) for k, f in plans.items()}
    hdr = f"{'strategy':<36}{'final':>9}{'CAGR':>8}{'Sharpe':>8}{'maxDD':>7}{'worst mo':>10}{'trades':>8}"
    for label, a in (("FULL 2017-03 .. now ($200)", first), ("HELD-OUT 2023-01 .. now (rescaled)", held)):
        print(f"\n{label}\n{hdr}")
        for k, r in res.items():
            x = stats(*window(r, a))
            grown = 200.0 * (1 + x["cagr"]) ** ((len(r.days) - a - 1) / 252)  # $200 put in at the window start
            print(f"{k:<36}{grown:>9.0f}{x['cagr']:>8.1%}{x['sharpe']:>8.2f}{x['max_dd']:>7.0%}{x['worst_month']:>10.0%}"
                  f"{r.trades:>8}")
    print("\nCALENDAR YEARS")
    yrs = sorted(yearly(*window(res["SPY (benchmark)"], first)))
    print(f"{'strategy':<36}" + "".join(f"{y:>6}" for y in yrs))
    for k, r in res.items():
        yy = yearly(*window(r, first))
        print(f"{k:<36}" + "".join(f"{yy.get(y, 0):>6.0%}" for y in yrs))
    print("\nCONTRIBUTIONS: $500 start (final value; total put in shown in brackets)")
    for k, f in plans.items():
        cells = []
        for dep in (0.0, 25.0, 50.0):
            r = run(ctx, f(), k, capital=500.0, cost_bps=5.0, start_index=first, monthly_deposit=dep)
            x = stats(*window(r, first))
            cells.append(f"+${dep:.0f}/mo: ${x['final']:,.0f} (${x['deposited']:,.0f})")
        print(f"{k:<36}" + "   ".join(cells))


if __name__ == "__main__":
    main()
