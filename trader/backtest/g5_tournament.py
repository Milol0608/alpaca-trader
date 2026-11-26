"""G5 (docs/RESEARCH.md): year-by-year strategy tournament, profit-first, every calendar year its own test.

  uv run python -m trader.backtest.g5_tournament

8 families x 2-3 versions + references, simulated day by day (decide at the close, trade at the next open, all gains
reinvested). Scored three ways (A/B profit-first, C = ADR 0003). Writes data/results/g5_tournament.json.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import date, datetime, timedelta, timezone

import numpy as np
import polars as pl

from trader.backtest import g_growth as g
from trader.backtest import portfolio_rules as pr
from trader.backtest import strategies as st
from trader.backtest.engine import Window, build_context, run
from trader.backtest.scorecard import stats, window
from trader.backtest.strategies import _first_day_of_month, _first_day_of_week
from trader.config import get_settings
from trader.data.bars import load_bars
from trader.data.universe import load_etfs

START, TEST = date(2017, 3, 1), date(2023, 1, 1)
ETFS = ["SPY", "QQQ", "SSO", "UPRO", "QLD", "TQQQ", "BIL", "TMF", "TLT", "UGL", "UBT"]
COINS = ["BTC", "ETH"]
ADV_MIN = 20e6
CRYPTO_SMA = 96  # ~140 calendar days in stock trading days


def liquid(w: Window) -> Window:
    """Only stocks whose 20-day average dollar volume is at least $20M."""
    keep = set()
    for s in w.allowed:
        k = w.index.get(s)
        if k is None:
            continue
        dv = w.close[-20:, k] * w.volume[-20:, k]
        if not np.isnan(dv).any() and dv.mean() >= ADV_MIN:
            keep.add(s)
    return dataclasses.replace(w, allowed=keep)


def momentum(etfs: set[str], n: int, liquid_only: bool = False):
    inner = st.momentum(etfs, n=n, force=True)

    def strat(w: Window):
        if not _first_day_of_month(w) or len(w.days) <= 252:
            return None
        return inner(liquid(w) if liquid_only else w)
    return strat


def high52(etfs: set[str], n: int, liquid_only: bool = False):
    inner = pr.high52_momentum(etfs, n=n)

    def strat(w: Window):
        return inner(liquid(w) if liquid_only else w)
    return strat


def quarterly_mix(mix: dict[str, float], bond_filter: str | None = None):
    def strat(w: Window):
        first_q = _first_day_of_month(w) and w.today.month in (1, 4, 7, 10)
        if not first_q and len(w.days) > 2:
            return None
        out = dict(mix)
        if bond_filter:
            k = w.index[bond_filter]
            c = w.close[-200:, k]
            if not np.isnan(c).any() and c[-1] < c.mean():
                for s in [x for x in out if x in ("TMF", "TLT", "UBT")]:
                    out["BIL"] = out.get("BIL", 0.0) + out.pop(s)
        return out
    return strat


def rotation(pool: list[str], top: int, lookback: int = 126):
    def strat(w: Window):
        if not _first_day_of_month(w) or len(w.days) <= lookback:
            return None
        sc = {}
        for s in pool:
            c = w.close[:, w.index[s]]
            if not np.isnan(c[-1]) and not np.isnan(c[-1 - lookback]):
                sc[s] = c[-1] / c[-1 - lookback] - 1
        out: dict[str, float] = {}
        for s in sorted(sc, key=lambda x: -sc[x])[:top]:
            k = s if sc[s] > 0 else "BIL"
            out[k] = out.get(k, 0.0) + 1.0 / top
        return out or {"BIL": 1.0}
    return strat


def crypto_trend(weight: float, rest: str | None = None):
    state: dict = {"on": None}

    def strat(w: Window):
        on = []
        for s in COINS:
            k = w.index.get(s)
            if k is None or len(w.days) <= CRYPTO_SMA:
                return None
            c = w.close[-CRYPTO_SMA:, k]
            on.append(bool(not np.isnan(c).any() and c[-1] > c.mean()))
        key = (tuple(on), w.today.month if rest else 0)
        if key == state["on"]:
            return None
        state["on"] = key
        out = {s: weight / 2 for s, o in zip(COINS, on) if o}
        if rest:
            out[rest] = 1 - weight
        return out
    return strat


def hold(sym: str):
    return st.buy_hold(sym)


def year_marks(days: list[date], first: int) -> list[tuple[str, int, int]]:
    """(label, start index, end index) per calendar year; start = last close of the prior year (or the start)."""
    out, s = [], first
    for i in range(first + 1, len(days)):
        if i == len(days) - 1 or days[i + 1].year != days[i].year:
            label = str(days[i].year) + (" (Mar-)" if days[i].year == 2017 else " (to date)" if i == len(days) - 1 else "")
            out.append((label, s, i))
            s = i
    return out


def main() -> None:
    s = get_settings()
    universe = pl.read_parquet(s.data_dir / "universe.parquet").select("month", "symbol")
    months = universe["month"].unique().to_list()
    extra = ETFS + COINS
    universe = pl.concat([universe, pl.DataFrame({"month": [m for m in months for _ in extra],
                                                  "symbol": [x for _ in months for x in extra]}).cast(universe.schema)]).unique()
    daily = load_bars(s.data_dir / "bars", "1Day").select("symbol", "t", "open", "close", "volume").collect()
    stock_days = set(daily.filter(pl.col("symbol") == "SPY")
                     .with_columns(pl.col("t").dt.convert_time_zone("America/New_York").dt.date().alias("d"))["d"].to_list())
    coins = []
    for c in COINS:
        df = pl.read_parquet(s.data_dir / "crypto" / f"{c}-USD.parquet").filter(pl.col("day").is_in(list(stock_days)))
        coins.append(df.select(pl.lit(c).alias("symbol"),
                               pl.col("day").cast(pl.Datetime("us")).dt.offset_by("16h").dt.replace_time_zone("UTC")
                               .dt.cast_time_unit(daily.schema["t"].time_unit).alias("t"),
                               "open", "close", pl.lit(1e12).alias("volume")).cast(daily.schema))
    daily = pl.concat([daily] + coins)
    ctx = build_context(daily, universe, START - timedelta(days=400), date.today())
    e = set(load_etfs(s.etfs_file)) | set(extra)
    first = next(i for i, d in enumerate(ctx.days) if d >= START)
    cut = next(i for i, d in enumerate(ctx.days) if d >= TEST)

    F = {  # name: (family, cost bps, factory)
        "1a momentum top 10": ("1 momentum", 10, lambda: momentum(e, 10)),
        "1b momentum top 20": ("1 momentum", 10, lambda: momentum(e, 20)),
        "1c momentum top 20 liquid": ("1 momentum", 10, lambda: momentum(e, 20, True)),
        "2a 2x S&P trend MA200": ("2 lev trend", 5, lambda: g.lev_trend("SPY", "SSO", 200, "weekly")),
        "2b 3x S&P trend MA200": ("2 lev trend", 5, lambda: g.lev_trend("SPY", "UPRO", 200, "weekly")),
        "2c 3x S&P trend MA150": ("2 lev trend", 5, lambda: g.lev_trend("SPY", "UPRO", 150, "weekly")),
        "3a vol target 20% cap3": ("3 vol target", 5, lambda: g.vol_target(0.20, 20, 3.0)),
        "3b vol target 25% cap3": ("3 vol target", 5, lambda: g.vol_target(0.25, 20, 3.0)),
        "3c vol target 30% cap3": ("3 vol target", 5, lambda: g.vol_target(0.30, 20, 3.0)),
        "4a G4: 30% mom + sleeve 16% (F2)": ("4 mom+sleeve", 10, lambda: g.m70_vol(e, 0.16, 20)),
        "4b 50% mom + sleeve 25%": ("4 mom+sleeve", 10, lambda: m50(e)),
        "5a 55 UPRO / 45 TMF": ("5 lev stock+bond", 5, lambda: quarterly_mix({"UPRO": 0.55, "TMF": 0.45})),
        "5b 60 SSO / 40 TLT": ("5 lev stock+bond", 5, lambda: quarterly_mix({"SSO": 0.60, "TLT": 0.40})),
        "5c 55 UPRO / 45 TMF, bond filter": ("5 lev stock+bond", 5,
                                             lambda: quarterly_mix({"UPRO": 0.55, "TMF": 0.45}, bond_filter="TLT")),
        "6a rotation top1 2x": ("6 lev rotation", 5, lambda: rotation(["SSO", "QLD", "UGL", "UBT"], 1)),
        "6b rotation top2 2x": ("6 lev rotation", 5, lambda: rotation(["SSO", "QLD", "UGL", "UBT"], 2)),
        "6c rotation top1 3x": ("6 lev rotation", 5, lambda: rotation(["UPRO", "TQQQ", "TMF"], 1)),
        "7a 52w-high top 10": ("7 52w high", 10, lambda: high52(e, 10)),
        "7b 52w-high top 10 liquid": ("7 52w high", 10, lambda: high52(e, 10, True)),
        "8a crypto trend 100%": ("8 crypto", 25, lambda: crypto_trend(1.0)),
        "8b 25% crypto trend + 75% SPY": ("8 crypto", 25, lambda: crypto_trend(0.25, "SPY")),
        "R SPY": ("ref", 5, lambda: hold("SPY")),
        "R QQQ (hindsight)": ("ref", 5, lambda: hold("QQQ")),
        "R UPRO buy-hold": ("ref", 5, lambda: hold("UPRO")),
        "R TQQQ buy-hold (hindsight)": ("ref", 5, lambda: hold("TQQQ")),
        "R BTC buy-hold": ("ref", 25, lambda: hold("BTC")),
    }
    res, years = {}, None
    for k, (fam, bps, f) in F.items():
        r = run(ctx, f(), k, capital=200.0, cost_bps=float(bps), start_index=first)
        eq = r.equity
        years = years or year_marks(ctx.days, first)
        yr = {}
        for label, a, b in years:
            seg = eq[a:b + 1]
            yr[label] = {"ret": float(seg[-1] / seg[0] - 1), "drop": float(np.max(1 - seg / np.maximum.accumulate(seg)))}
        res[k] = {"family": fam, "bps": bps, "years": yr, "final_200": float(eq[-1]),
                  "train": stats(*window(r, first, cut + 1)), "test": stats(*window(r, cut)), "trades": r.trades}
        print(f"{k:<36}" + "".join(f"{v['ret']:>8.0%}" for v in yr.values()) + f"  ${eq[-1]:>9,.0f}", flush=True)

    labels = [y[0] for y in years]
    spy = res["R SPY"]
    spy_ret = [spy["years"][y]["ret"] for y in labels]
    judged = [k for k, v in res.items() if v["family"] != "ref"]

    def score(rets: list[float], v: dict | None) -> dict:
        med, beats, worst = float(np.median(rets)), sum(a > b for a, b in zip(rets, spy_ret)), min(rets)
        a = med >= float(np.median(spy_ret)) + 0.05 and beats >= 6 and worst >= -0.40
        b = med >= float(np.median(spy_ret)) + 0.05 and beats >= 6
        c = None
        if v is not None:
            c = all(v[p]["cagr"] >= spy[p]["cagr"] + 0.03 and v[p]["sharpe"] >= 0.9 * spy[p]["sharpe"] and v[p]["max_dd"] < 0.40
                    for p in ("train", "test"))
        return {"median_year": med, "beats_spy_years": beats, "worst_year": worst, "A": a, "B": b, "C": c}

    for k in res:
        res[k]["score"] = score([res[k]["years"][y]["ret"] for y in labels], res[k])
    # walk-forward chooser: each January, the version with the best compounded return over all prior periods
    chooser = {}
    for i, y in enumerate(labels[1:], start=1):
        past = {k: float(np.prod([1 + res[k]["years"][p]["ret"] for p in labels[:i]])) for k in judged}
        pick = max(past, key=past.get)
        chooser[y] = {"pick": pick, "ret": res[pick]["years"][y]["ret"]}
    firsts = [next(k for k in judged if res[k]["family"] == fam) for fam in dict.fromkeys(res[k]["family"] for k in judged)]
    blend = {y: float(np.mean([res[k]["years"][y]["ret"] for k in firsts])) for y in labels}
    ch_rets = [chooser[y]["ret"] for y in labels[1:]]
    spy_ret_ch = spy_ret[1:]
    ch_score = {"median_year": float(np.median(ch_rets)), "beats_spy_years": sum(a > b for a, b in zip(ch_rets, spy_ret_ch)),
                "of": len(ch_rets), "worst_year": min(ch_rets), "final_200": 200 * float(np.prod([1 + x for x in ch_rets]))}
    bl_score = score(list(blend.values()), None) | {"final_200": 200 * float(np.prod([1 + x for x in blend.values()]))}

    print(f"\n{'':<36}" + "".join(f"{y[:4]:>8}" for y in labels))
    print(f"{'chooser (blind pick each Jan)':<36}{'':>8}" + "".join(f"{chooser[y]['ret']:>8.0%}" for y in labels[1:]))
    print(f"{'blend of 8 families':<36}" + "".join(f"{blend[y]:>8.0%}" for y in labels))
    print("chooser picks:", {y[:4]: chooser[y]["pick"] for y in labels[1:]})
    print(f"\n{'RANKED by median year':<36}{'median':>8}{'beats':>7}{'worst yr':>9}{'worst drop':>11}{'$200 ->':>10}"
          f"{'A':>4}{'B':>4}{'C':>4}")
    for k in sorted(res, key=lambda k: -res[k]["score"]["median_year"]):
        sc = res[k]["score"]
        wd = max(v["drop"] for v in res[k]["years"].values())
        flag = lambda x: "-" if res[k]["family"] == "ref" else ("Y" if x else "n")  # noqa: E731
        print(f"{k:<36}{sc['median_year']:>8.0%}{sc['beats_spy_years']:>5}/10{sc['worst_year']:>9.0%}{wd:>11.0%}"
              f"{res[k]['final_200']:>10,.0f}{flag(sc['A']):>4}{flag(sc['B']):>4}{flag(sc['C']):>4}")
    print(f"chooser: {ch_score}\nblend: {bl_score}")
    (s.data_dir / "results").mkdir(exist_ok=True)
    json.dump({"years": labels, "versions": res, "chooser": chooser, "chooser_score": ch_score, "blend": blend,
               "blend_score": bl_score}, open(s.data_dir / "results" / "g5_tournament.json", "w"), default=float, indent=1)


def m50(e: set[str]):
    """4b: 50% momentum + 50% vol sleeve (25% target, L20, cap 2), weekly; picks refreshed monthly."""
    mom = st.momentum(e, force=True)
    picks: dict = {"w": None}

    def strat(w: Window):
        if picks["w"] is None or _first_day_of_month(w):
            picks["w"] = mom(w) if len(w.days) > 252 else None
        if not _first_day_of_week(w) or not picks["w"]:
            return None
        sl = g.sleeve(w, 0.25, 20, 2.0)
        if sl is None:
            return None
        out = {k: 0.5 * v for k, v in picks["w"].items()}
        for k, v in sl.items():
            out[k] = out.get(k, 0.0) + 0.5 * v
        return out
    return strat


if __name__ == "__main__":
    main()
