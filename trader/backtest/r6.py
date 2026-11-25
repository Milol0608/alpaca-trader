"""R6 (docs/RESEARCH.md): momentum with weekly stop-losses and profit targets, plus yearly returns of every
stock strategy for the review table.  uv run python -m trader.backtest.r6"""

from __future__ import annotations

import json
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
        "momentum 12-1 (live paper)": lambda: st.momentum(e),
        "short-term reversal (weekly)": lambda: st.reversal(e),
        "low volatility": lambda: st.low_vol(e),
        "ETF trend (200-day)": lambda: st.trend_etfs(e),
        "R1 momentum + low vol": lambda: st.momentum_low_vol(e),
        "R2 momentum + crash filter": lambda: st.momentum_crash_filter(e),
    }
    for stop in (None, 0.10, 0.15):
        for tgt in (None, 0.25, 0.30, "adaptive"):
            if stop is None and tgt is None:
                continue
            lab = f"R6 stop {'-' if stop is None else f'{stop:.0%}'} / target {'-' if tgt is None else (tgt if isinstance(tgt, str) else f'{tgt:.0%}')}"
            plans[lab] = (lambda a, b: lambda: st.momentum_stops(e, a, b))(stop, tgt)
    out = {}
    hdr = f"{'strategy':<40}{'final':>8}{'CAGR':>8}{'Sharpe':>8}{'maxDD':>7} |{'HO CAGR':>9}{'HO Shp':>8}{'HO DD':>7}{'trades':>8}"
    print(hdr)
    for k, f in plans.items():
        r = run(ctx, f(), k, capital=200.0, cost_bps=5.0, start_index=first)
        a, b = stats(*window(r, first)), stats(*window(r, held))
        yy = yearly(*window(r, first))
        out[k] = {"full": a, "held": b, "years": {str(y): v for y, v in yy.items()}, "trades": r.trades}
        print(f"{k:<40}{a['final']:>8.0f}{a['cagr']:>8.1%}{a['sharpe']:>8.2f}{a['max_dd']:>7.0%} |"
              f"{b['cagr']:>9.1%}{b['sharpe']:>8.2f}{b['max_dd']:>7.0%}{r.trades:>8}", flush=True)
    (s.data_dir / "results").mkdir(exist_ok=True)
    json.dump(out, open(s.data_dir / "results" / "r6_and_yearly.json", "w"), default=float, indent=1)


if __name__ == "__main__":
    main()
