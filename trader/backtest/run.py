"""Run the baseline daily strategies against buy-and-hold SPY, after costs.

  uv run python -m trader.backtest.run --capital 200 --cost-bps 5

Prints each strategy's full-period stats and its return year by year next to SPY's, so a strategy
that only won in one lucky year is visible. Saves equity curves to data/results/daily_baselines.parquet.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

import numpy as np
import polars as pl

from trader.backtest import strategies as st
from trader.backtest.engine import build_context, run
from trader.config import get_settings
from trader.data.bars import load_bars
from trader.data.universe import load_etfs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2017-03-01",
                    help="first scored day; strategies need up to a year of history before it")
    ap.add_argument("--end", default=date.today().isoformat())
    ap.add_argument("--capital", type=float, default=200.0)
    ap.add_argument("--cost-bps", type=float, default=5.0)
    args = ap.parse_args()
    s = get_settings()
    universe = pl.read_parquet(s.data_dir / "universe.parquet")
    daily = load_bars(s.data_dir / "bars", "1Day").select("symbol", "t", "open", "close", "volume").collect()
    ctx = build_context(daily, universe, date.fromisoformat(args.start) - timedelta(days=400),
                        date.fromisoformat(args.end))
    etfs = set(load_etfs(s.etfs_file))
    first = next(i for i, d in enumerate(ctx.days) if d >= date.fromisoformat(args.start))
    plans = {
        "SPY (benchmark)": st.buy_hold("SPY"),
        "momentum 12-1, top 20": st.momentum(etfs),
        "reversal 5d, top 20": st.reversal(etfs),
        "low vol 60d, top 20": st.low_vol(etfs),
        "trend ETFs 200d": st.trend_etfs(etfs),
    }
    results = {name: run(ctx, f, name, capital=args.capital, cost_bps=args.cost_bps, start_index=first)
               for name, f in plans.items()}
    days = ctx.days[first:]
    print(f"\n{days[0]} .. {days[-1]}  capital ${args.capital:.0f}  cost {args.cost_bps:g} bps/side  (long-only, no leverage)")
    print(f"{'strategy':<24}{'final':>10}{'CAGR':>8}{'vol':>7}{'Sharpe':>8}{'maxDD':>7}{'trades':>8}{'costs':>9}{'turnover/yr':>13}")
    for name, r in results.items():
        x = r.stats()
        eq = r.equity[first:]
        rr = np.diff(eq) / eq[:-1]
        cagr = (eq[-1] / eq[0]) ** (252 / len(rr)) - 1
        dd = float(np.max(1 - eq / np.maximum.accumulate(eq)))
        print(f"{name:<24}{eq[-1]:>10.2f}{cagr:>8.1%}{np.std(rr) * np.sqrt(252):>7.1%}"
              f"{np.mean(rr) / np.std(rr) * np.sqrt(252):>8.2f}{dd:>7.0%}{x['trades']:>8}{x['costs']:>9.2f}"
              f"{r.traded_value / float(np.mean(eq)) / (len(rr) / 252):>12.1f}x")
    years = sorted({d.year for d in days})
    print("\nreturn by calendar year")
    print(f"{'strategy':<24}" + "".join(f"{y:>7}" for y in years))
    for name, r in results.items():
        eq = r.equity[first:]
        cells = []
        for y in years:
            idx = [k for k, d in enumerate(days) if d.year == y]
            prev = eq[idx[0] - 1] if idx[0] > 0 else eq[0]
            cells.append(f"{eq[idx[-1]] / prev - 1:>7.0%}")
        print(f"{name:<24}" + "".join(cells))
    out = pl.DataFrame({"day": days} | {name: r.equity[first:] for name, r in results.items()})
    (s.data_dir / "results").mkdir(exist_ok=True)
    out.write_parquet(s.data_dir / "results" / "daily_baselines.parquet")


if __name__ == "__main__":
    main()
