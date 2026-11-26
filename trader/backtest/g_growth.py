"""G2-G4 (docs/RESEARCH.md, ADR 0003): growth with controlled risk, using leveraged ETFs in a cash account.

  uv run python -m trader.backtest.g_growth

G2 leveraged trend (Gayed & Bilello 2016), G3 volatility-targeted S&P exposure (Moreira & Muir 2017),
G4 30% momentum + 70% vol-targeted S&P sleeve. Every variant is run; grids are judged by their median variant.
Writes data/results/g_growth.json.
"""

from __future__ import annotations

import json
import math
from datetime import date, timedelta
from statistics import NormalDist

import numpy as np
import polars as pl

from trader.backtest import strategies as st
from trader.backtest.engine import Window, build_context, run
from trader.backtest.scorecard import stats, window
from trader.backtest.strategies import _first_day_of_month, _first_day_of_week
from trader.config import get_settings
from trader.data.bars import load_bars
from trader.data.universe import load_etfs

START, TEST = date(2017, 3, 1), date(2023, 1, 1)
EXTRA = ["SSO", "UPRO", "QLD", "TQQQ", "BIL", "QQQ", "SPY"]
FAMILY = {"S&P": {1: "SPY", 2: "SSO", 3: "UPRO"}, "Nasdaq": {1: "QQQ", 2: "QLD", 3: "TQQQ"}}
CASH = "BIL"


def lev_trend(index: str, hold: str, n: int, check: str):
    state: dict = {"on": None}

    def strat(w: Window):
        if check == "weekly" and not _first_day_of_week(w) and state["on"] is not None:
            return None
        k = w.index.get(index)
        if k is None or len(w.days) <= n:
            return None
        c = w.close[-n:, k]
        if np.isnan(c).any():
            return None
        on = bool(c[-1] > c.mean())
        if on == state["on"]:
            return None
        state["on"] = on
        return {hold: 1.0} if on else {CASH: 1.0}
    return strat


def exposure_weights(e: float) -> dict[str, float]:
    """Exposure e (0-3) to the S&P from SPY/SSO/UPRO, the rest in BIL."""
    if e <= 1:
        return {"SPY": e, CASH: 1 - e}
    if e <= 2:
        return {"SSO": e - 1, "SPY": 2 - e}
    return {"UPRO": e - 2, "SSO": 3 - e}


def sleeve(w: Window, target: float, lookback: int, cap: float) -> dict[str, float] | None:
    k = w.index.get("SPY")
    if k is None or len(w.days) <= lookback + 1:
        return None
    c = w.close[-lookback - 1:, k]
    if np.isnan(c).any():
        return None
    vol = float(np.std(np.diff(np.log(c))) * math.sqrt(252))
    return exposure_weights(min(cap, target / max(vol, 1e-6)))


def vol_target(target: float, lookback: int, cap: float):
    def strat(w: Window):
        if not _first_day_of_week(w):
            return None
        return sleeve(w, target, lookback, cap)
    return strat


def m70_vol(etfs: set[str], target: float, lookback: int, cap: float = 2.0):
    mom = st.momentum(etfs, force=True)
    picks: dict = {"w": None}

    def strat(w: Window):
        if picks["w"] is None or _first_day_of_month(w):
            picks["w"] = mom(w) if len(w.days) > 252 else None
        if not _first_day_of_week(w) or not picks["w"]:
            return None
        s = sleeve(w, target, lookback, cap)
        if s is None:
            return None
        out = {k: 0.3 * v for k, v in picks["w"].items()}
        for k, v in s.items():
            out[k] = out.get(k, 0.0) + 0.7 * v
        return out
    return strat


def passes(x: dict, spy: dict) -> bool:
    return x["cagr"] >= spy["cagr"] + 0.03 and x["sharpe"] >= 0.9 * spy["sharpe"] and x["max_dd"] < 0.40


def deflated_sharpe(returns: dict[str, np.ndarray]) -> dict:
    """Bailey & López de Prado (2014): probability the best Sharpe is real after N trials (daily returns)."""
    srs = {k: float(np.mean(r) / np.std(r)) for k, r in returns.items()}
    best = max(srs, key=srs.get)
    r = returns[best]
    t, n, nd = len(r), len(srs), NormalDist()
    v = float(np.var(list(srs.values()), ddof=1))
    g = 0.5772156649
    sr0 = math.sqrt(v) * ((1 - g) * nd.inv_cdf(1 - 1 / n) + g * nd.inv_cdf(1 - 1 / (n * math.e)))
    z = (r - r.mean()) / r.std()
    skew, kurt = float(np.mean(z ** 3)), float(np.mean(z ** 4))
    sr = srs[best]
    dsr = nd.cdf((sr - sr0) * math.sqrt(t - 1) / math.sqrt(1 - skew * sr + (kurt - 1) / 4 * sr ** 2))
    return {"best": best, "best_sharpe_annual": sr * math.sqrt(252), "sr0_annual": sr0 * math.sqrt(252),
            "deflated_sharpe_prob": dsr, "trials": n}


def main() -> None:
    s = get_settings()
    universe = pl.read_parquet(s.data_dir / "universe.parquet")
    months = universe["month"].unique().to_list()
    add = pl.DataFrame({"month": [m for m in months for _ in EXTRA], "symbol": [x for _ in months for x in EXTRA]})
    universe = pl.concat([universe.select("month", "symbol"), add.cast(universe.select("month", "symbol").schema)]).unique()
    daily = load_bars(s.data_dir / "bars", "1Day").select("symbol", "t", "open", "close", "volume").collect()
    ctx = build_context(daily, universe, START - timedelta(days=400), date.today())
    for x in EXTRA:
        k = ctx.col(x)
        print(f"  {x}: first bar {ctx.days[int(np.argmax(~np.isnan(ctx.close[:, k])))]}")
    e = set(load_etfs(s.etfs_file)) | set(EXTRA)
    first = next(i for i, d in enumerate(ctx.days) if d >= START)
    cut = next(i for i, d in enumerate(ctx.days) if d >= TEST)

    plans: dict[str, tuple[str, object]] = {"SPY (benchmark)": ("ref", lambda: st.buy_hold("SPY"))}
    for fam, legs in FAMILY.items():
        for lev, hold in legs.items():
            for n in (150, 200, 250):
                for check in ("daily", "weekly"):
                    plans[f"G2 {fam} {lev}x MA{n} {check}"] = (f"G2 {lev}x" if lev > 1 else "ref",
                                                             lambda i=legs[1], h=hold, n=n, c=check: lev_trend(i, h, n, c))
    for tgt in (0.12, 0.16, 0.20):
        for lb in (20, 60):
            for cap in (2.0, 3.0):
                plans[f"G3 vol {tgt:.0%} L{lb} cap{cap:g}"] = ("G3", lambda t=tgt, l=lb, c=cap: vol_target(t, l, c))
    for tgt in (0.12, 0.16, 0.20):
        for lb in (20, 60):
            plans[f"G4 30% mom + vol {tgt:.0%} L{lb}"] = ("G4", lambda t=tgt, l=lb: m70_vol(e, t, l))
    plans["M70 reference (70% SPY / 30% momentum)"] = (
        "ref", lambda: __import__("trader.backtest.portfolio_rules", fromlist=["spy_mix"]).spy_mix(st.momentum(e, force=True), 0.70))

    out, rets = {}, {}
    print(f"\n{'variant':<40}{'TR CAGR':>8}{'Shp':>6}{'DD':>5}  {'TE CAGR':>8}{'Shp':>6}{'DD':>5}  {'$200 full':>10}")
    for k, (grid, f) in plans.items():
        r = run(ctx, f(), k, capital=200.0, cost_bps=5.0, start_index=first)
        tr, te, fu = stats(*window(r, first, cut + 1)), stats(*window(r, cut)), stats(*window(r, first))
        out[k] = {"grid": grid, "train": tr, "test": te, "full": fu, "trades": r.trades}
        if grid != "ref":
            rets[k] = r.returns()[first:]
        print(f"{k:<40}{tr['cagr']:>8.1%}{tr['sharpe']:>6.2f}{tr['max_dd']:>5.0%}  {te['cagr']:>8.1%}{te['sharpe']:>6.2f}"
              f"{te['max_dd']:>5.0%}  {fu['final']:>10,.0f}", flush=True)
    spy = out["SPY (benchmark)"]
    for k, v in out.items():
        v["pass"] = v["grid"] != "ref" and passes(v["train"], spy["train"]) and passes(v["test"], spy["test"])
    verdict = {}
    for grid in ("G2 2x", "G2 3x", "G3", "G4"):
        vs = [v for v in out.values() if v["grid"] == grid]
        med = {p: {m: float(np.median([v[p][m] for v in vs])) for m in ("cagr", "sharpe", "max_dd")} for p in ("train", "test")}
        share = sum(v["pass"] for v in vs) / len(vs)
        ok = passes(med["train"], spy["train"]) and passes(med["test"], spy["test"]) and share >= 2 / 3
        verdict[grid] = {"variants": len(vs), "median": med, "share_pass": share, "PASS": ok}
        print(f"\n{grid}: {len(vs)} variants, {share:.0%} pass; median train CAGR {med['train']['cagr']:.1%} Shp "
              f"{med['train']['sharpe']:.2f} DD {med['train']['max_dd']:.0%} | test CAGR {med['test']['cagr']:.1%} Shp "
              f"{med['test']['sharpe']:.2f} DD {med['test']['max_dd']:.0%}  -> {'PASS' if ok else 'FAIL'}")
    print(f"\nSPY: train CAGR {spy['train']['cagr']:.1%} Shp {spy['train']['sharpe']:.2f} DD {spy['train']['max_dd']:.0%} | "
          f"test CAGR {spy['test']['cagr']:.1%} Shp {spy['test']['sharpe']:.2f} DD {spy['test']['max_dd']:.0%}")
    print("passing variants:", [k for k, v in out.items() if v["pass"]])
    dsr = deflated_sharpe(rets)
    print("deflated Sharpe:", dsr)
    (s.data_dir / "results").mkdir(exist_ok=True)
    json.dump({"variants": out, "grids": verdict, "deflated_sharpe": dsr}, open(s.data_dir / "results" / "g_growth.json", "w"),
              default=float, indent=1)


if __name__ == "__main__":
    main()
