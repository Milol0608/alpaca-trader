"""S2 (docs/RESEARCH.md): portfolio-level rules, chosen on 2017-2022, judged on 2023-now.
  uv run python -m trader.backtest.s2"""

from __future__ import annotations

import json
from datetime import date, timedelta

import numpy as np
import polars as pl

from trader.backtest import portfolio_rules as pr
from trader.backtest import strategies as st
from trader.backtest.engine import build_context, run
from trader.backtest.scorecard import monthly, stats, window, yearly
from trader.config import get_settings
from trader.data.bars import load_bars
from trader.data.universe import load_etfs

START, TEST = date(2017, 3, 1), date(2023, 1, 1)


def boot(mret: np.ndarray, years: int, n: int = 2000, block: int = 3, seed: int = 5) -> dict[str, float]:
    """$200 after `years`, resampling 3-month blocks of the real monthly returns."""
    rng = np.random.default_rng(seed)
    need = years * 12
    out = []
    for _ in range(n):
        g: list[float] = []
        while len(g) < need:
            i = int(rng.integers(0, len(mret) - block + 1))
            g.extend(mret[i:i + block])
        out.append(200 * float(np.prod(1 + np.array(g[:need]))))
    return {"p10": float(np.percentile(out, 10)), "median": float(np.median(out)), "p90": float(np.percentile(out, 90))}


def main() -> None:
    s = get_settings()
    universe = pl.read_parquet(s.data_dir / "universe.parquet")
    daily = load_bars(s.data_dir / "bars", "1Day").select("symbol", "t", "open", "close", "volume").collect()
    ctx = build_context(daily, universe, START - timedelta(days=400), date.today())
    e = set(load_etfs(s.etfs_file))
    first = next(i for i, d in enumerate(ctx.days) if d >= START)
    cut = next(i for i, d in enumerate(ctx.days) if d >= TEST)

    def mom():
        return st.momentum(e, force=True)  # inner rule: decides whenever asked

    plans = {
        "SPY (benchmark)": lambda: st.buy_hold("SPY"),
        "momentum 12-1 (live paper)": lambda: st.momentum(e),
        "V vol-scaled momentum": lambda: pr.vol_scaled_momentum(e),
        "D dual momentum (SPY/EFA/AGG)": lambda: pr.dual_momentum(),
        "S sector momentum (top 3)": lambda: pr.sector_momentum(),
        "H 52-week-high momentum": lambda: pr.high52_momentum(e),
        "M70 70% SPY / 30% momentum": lambda: pr.spy_mix(mom(), 0.70),
        "M50 50% SPY / 50% momentum": lambda: pr.spy_mix(mom(), 0.50),
        "P momentum, SPY in 25% drawdowns": lambda: pr.drawdown_pause(mom()),
        "V+SPY vol-scaled, rest in SPY": lambda: pr.vol_scaled_momentum(e, rest="SPY"),
        "M70+V 70% SPY / 30% vol-scaled": lambda: pr.spy_mix(pr.vol_scaled_momentum(e), 0.70),
        "P+V vol-scaled, SPY in drawdowns": lambda: pr.drawdown_pause(pr.vol_scaled_momentum(e)),
    }
    res, out = {}, {}
    print(f"{'rule':<36}{'TRAIN $':>8}{'Shp':>6}{'DD':>5}  {'TEST $':>7}{'Shp':>6}{'DD':>5}  "
          f"{'FULL $':>7}{'Shp':>6}{'DD':>5}{'trades':>7}")
    for k, f in plans.items():
        r = run(ctx, f(), k, capital=200.0, cost_bps=5.0, start_index=first)
        res[k] = r
        tr, te, fu = stats(*window(r, first, cut + 1)), stats(*window(r, cut)), stats(*window(r, first))
        g_tr = 200 * float(r.equity[cut]) / float(r.equity[first])
        g_te = 200 * float(r.equity[-1]) / float(r.equity[cut])
        out[k] = {"train": tr, "test": te, "full": fu, "trades": r.trades, "train_g": g_tr, "test_g": g_te,
                  "years": {str(y): v for y, v in yearly(*window(r, first)).items()}}
        print(f"{k:<36}{g_tr:>8.0f}{tr['sharpe']:>6.2f}{tr['max_dd']:>5.0%}  {g_te:>7.0f}{te['sharpe']:>6.2f}"
              f"{te['max_dd']:>5.0%}  {fu['final']:>7.0f}{fu['sharpe']:>6.2f}{fu['max_dd']:>5.0%}{r.trades:>7}", flush=True)
    spy = out["SPY (benchmark)"]
    print("\nVERDICTS (pass = Sharpe above SPY and worst drop under 35%, in train AND test)")
    for k, v in out.items():
        m = np.array(list(monthly(*window(res[k], first)).values()))
        v["boot"] = {str(y): boot(m, y) for y in (1, 2, 5, 10)}
        if k.startswith("SPY"):
            v["verdict"] = "BENCHMARK"
        else:
            t_ok = v["train"]["sharpe"] > spy["train"]["sharpe"] and v["train"]["max_dd"] < 0.35
            e_ok = v["test"]["sharpe"] > spy["test"]["sharpe"] and v["test"]["max_dd"] < 0.35
            v["verdict"] = "PASS" if t_ok and e_ok else ("FAIL on test" if t_ok else "FAIL on train")
        b5 = v["boot"]["5"]
        print(f"  {k:<36}{v['verdict']:<15} 5y from $200 (resampled): p10 ${b5['p10']:,.0f}  median "
              f"${b5['median']:,.0f}  p90 ${b5['p90']:,.0f}")
    (s.data_dir / "results").mkdir(exist_ok=True)
    json.dump(out, open(s.data_dir / "results" / "s2.json", "w"), default=float, indent=1)


if __name__ == "__main__":
    main()
