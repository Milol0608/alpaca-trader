"""D2 (docs/RESEARCH.md): a trained decider that re-ranks the monthly top-40 momentum pool, with and without news.
  uv run --with scikit-learn python -m trader.backtest.d2      (needs data/news/gdelt/ from trader.backtest.news_gdelt)

Walk-forward: each January the models are refitted on every earlier month whose next-month return is known, and pick
that year's stocks. Predictions start 2019. Writes data/results/d2.json (stats, yearly returns, monthly returns)."""

from __future__ import annotations

import json
import math
from bisect import bisect_left
from datetime import date, datetime, timedelta

import numpy as np
import polars as pl
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from trader.backtest import portfolio_rules as pr
from trader.backtest import strategies as st
from trader.backtest.engine import build_context, run
from trader.backtest.r7 import LOOKBACK, POOL, SKIP, START
from trader.backtest.s2 import boot
from trader.backtest.scorecard import monthly, stats, window, yearly
from trader.config import get_settings
from trader.data.bars import load_bars
from trader.data.universe import load_etfs

FIRST_PRED, TEST = date(2019, 1, 1), date(2023, 1, 1)
N = 20
BASE = ["mom12_1", "mom6_1", "ret1m", "vol126", "off_high", "log_dvol"]
NEWS = ["tone30", "lcount30", "dtone", "dlcount"]


def news_table(folder) -> dict[str, tuple[list[int], np.ndarray, np.ndarray]]:
    out = {}
    for f in folder.glob("*.json"):
        j = json.loads(f.read_text())
        tone = {int(d): v for d, v in (j.get("tone") or [])}
        cnt = {int(d): v for d, v in (j.get("count") or [])}
        days = sorted(set(tone) | set(cnt))
        if days:
            out[f.stem] = (days, np.array([tone.get(d, np.nan) for d in days], float),
                           np.array([cnt.get(d, 0.0) for d in days], float))
    return out


def news_feats(tbl, sym: str, d: date) -> list[float]:
    if sym not in tbl:
        return [np.nan] * 4
    days, tone, cnt = tbl[sym]
    key = lambda x: int(x.strftime("%Y%m%d"))  # noqa: E731
    a, b, c = bisect_left(days, key(d - timedelta(120))), bisect_left(days, key(d - timedelta(30))), bisect_left(days, key(d))
    if c - b < 5:
        return [np.nan] * 4
    t30, t90 = np.nanmean(tone[b:c]) if np.any(~np.isnan(tone[b:c])) else np.nan, \
        (np.nanmean(tone[a:b]) if b > a and np.any(~np.isnan(tone[a:b])) else np.nan)
    c30, c90 = cnt[b:c].sum(), cnt[a:b].sum() / 3 if b > a else np.nan
    return [t30, math.log1p(c30), t30 - t90, math.log1p(c30) - math.log1p(c90) if c90 == c90 else np.nan]


def panel(ctx, etfs: set[str], tbl) -> list[dict]:
    """One row per (month start, pool stock): features known that morning, and the next month's excess return."""
    starts = [i for i in range(LOOKBACK + 1, len(ctx.days)) if ctx.days[i].month != ctx.days[i - 1].month]
    rows = []
    for j, i in enumerate(starts):
        names = sorted(s for s in ctx.allowed(i) - etfs if s in ctx._index)
        cols = np.array([ctx._index[s] for s in names], dtype=int)
        c = ctx.close[: i + 1, cols]
        sc = c[-1 - SKIP] / c[-1 - LOOKBACK] - 1
        ok = np.nonzero(~np.isnan(sc))[0]
        pool = ok[np.argsort(-sc[ok], kind="stable")][:POOL]
        nxt = starts[j + 1] if j + 1 < len(starts) else None
        fwd = (ctx.close[nxt, cols[pool]] / c[-1, pool] - 1) if nxt is not None else np.full(len(pool), np.nan)
        med = np.nanmedian(fwd) if nxt is not None else np.nan
        with np.errstate(all="ignore"):
            r = np.diff(np.log(c[-127:, pool]), axis=0)
            vol = np.nanstd(r, axis=0) * math.sqrt(252)
            hi = np.nanmax(c[-252:, pool], axis=0)
            dv = np.nanmean(c[-21:, pool] * ctx.volume[i - 20: i + 1, cols[pool]], axis=0)
        for k, p in enumerate(pool):
            f = {"mom12_1": sc[p], "mom6_1": c[-1 - SKIP, p] / c[-1 - 126, p] - 1, "ret1m": c[-1, p] / c[-1 - SKIP, p] - 1,
                 "vol126": vol[k], "off_high": c[-1, p] / hi[k] - 1, "log_dvol": math.log1p(dv[k]) if dv[k] == dv[k] else np.nan}
            f.update(dict(zip(NEWS, news_feats(tbl, names[p], ctx.days[i]))))
            rows.append({"day": ctx.days[i], "sym": names[p], "y": float(fwd[k] - med) if nxt is not None else np.nan,
                         "next": ctx.days[nxt] if nxt is not None else None, **f})
    return rows


def predict(rows: list[dict], feats: list[str], kind: str) -> dict[tuple[date, str], float]:
    out = {}
    for year in range(FIRST_PRED.year, date.today().year + 1):
        jan = date(year, 1, 1)
        tr = [r for r in rows if r["next"] is not None and r["next"] < jan and r["y"] == r["y"]]
        te = [r for r in rows if jan <= r["day"] < date(year + 1, 1, 1)]
        if not tr or not te:
            continue
        X = np.array([[r[f] for f in feats] for r in tr], float)
        Xt = np.array([[r[f] for f in feats] for r in te], float)
        y = np.array([r["y"] for r in tr])
        if kind == "ridge":
            X, Xt = np.where(np.isfinite(X), X, np.nan), np.where(np.isfinite(Xt), Xt, np.nan)
            with np.errstate(all="ignore"):
                med = np.nan_to_num(np.nanmedian(X, axis=0))  # a column with no data at all becomes 0
            X, Xt = np.where(np.isnan(X), med, X), np.where(np.isnan(Xt), med, Xt)
            m = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
        else:
            keep = ~np.all(np.isnan(X), axis=0)  # a column with no data yet (e.g. news before it exists) is dropped
            X, Xt = X[:, keep], Xt[:, keep]
            m = HistGradientBoostingRegressor(max_depth=3, max_iter=200, learning_rate=0.05, random_state=0)
        y = np.clip(y, -0.5, 0.5)  # a handful of buyout jumps should not steer the fit
        m.fit(X, y)
        for r, p in zip(te, m.predict(Xt)):
            out[(r["day"], r["sym"])] = float(p)
    return out


def decider(pred: dict, rows: list[dict]):
    by_day: dict[date, list[str]] = {}
    for r in rows:
        by_day.setdefault(r["day"], []).append(r["sym"])

    def strat(w):
        if not st._first_day_of_month(w) or len(w.days) <= LOOKBACK:
            return None
        d = w.days[-1]
        pool = by_day.get(d, [])
        scored = [(pred[(d, s)], s) for s in pool if (d, s) in pred]
        if not scored:  # before 2019: plain momentum, so every version starts from the same money
            pick = pool[:N]
        else:
            pick = [s for _, s in sorted(scored, reverse=True)[:N]]
        return {s: 1.0 / len(pick) for s in pick} if pick else {}
    return strat


def main() -> None:
    s = get_settings()
    universe = pl.read_parquet(s.data_dir / "universe.parquet")
    daily = load_bars(s.data_dir / "bars", "1Day").select("symbol", "t", "open", "close", "volume").collect()
    ctx = build_context(daily, universe, START - timedelta(days=400), date.today())
    e = set(load_etfs(s.etfs_file))
    tbl = news_table(s.data_dir / "news" / "gdelt")
    rows = panel(ctx, e, tbl)
    have = sum(1 for r in rows if r["tone30"] == r["tone30"])
    print(f"panel: {len(rows)} stock-months, news for {have} ({have / len(rows):.0%}); {len(tbl)} news files", flush=True)
    plans = {"SPY (benchmark)": st.buy_hold("SPY"), "momentum 12-1 (live paper)": st.momentum(e)}
    for kind in ("ridge", "trees"):
        for label, feats in (("D2a no news", BASE), ("D2b with news", BASE + NEWS)):
            p = predict(rows, feats, kind)
            plans[f"{label} ({kind})"] = decider(p, rows)
    for k in [k for k in plans if k.startswith("D2")]:
        plans[f"70/30 SPY / {k}"] = pr.spy_mix(plans[k], 0.70)
    plans["70/30 SPY / momentum (M70)"] = pr.spy_mix(st.momentum(e), 0.70)
    i19 = next(i for i, d in enumerate(ctx.days) if d >= FIRST_PRED)
    i23 = next(i for i, d in enumerate(ctx.days) if d >= TEST)
    out = {}
    print(f"{'strategy':<40}{'2019-22 Shp':>12}{'DD':>6}{'2023+ Shp':>11}{'DD':>6}{'$200 2019->':>13}{'$200 2023->':>13}  verdict")
    spy = None
    for k, f in plans.items():
        r = run(ctx, f, k, capital=200.0, cost_bps=5.0, start_index=i19)
        a, b = stats(*window(r, i19, i23)), stats(*window(r, i23))
        full = stats(*window(r, i19))
        mret = np.array(list(monthly(*window(r, i19)).values()))
        out[k] = {"train": a, "test": b, "full": full, "years": {str(y): v for y, v in yearly(*window(r, i19)).items()},
                  "monthly": {f"{y}-{m:02d}": v for (y, m), v in monthly(*window(r, i19)).items()},
                  "boot_3y": boot(mret, 3)}
        if spy is None:
            spy = (a, b)
        ok = a["sharpe"] > spy[0]["sharpe"] and a["max_dd"] < 0.35 and b["sharpe"] > spy[1]["sharpe"] and b["max_dd"] < 0.35
        out[k]["pass"] = bool(ok) if k != "SPY (benchmark)" else None
        print(f"{k:<40}{a['sharpe']:>12.2f}{a['max_dd']:>6.0%}{b['sharpe']:>11.2f}{b['max_dd']:>6.0%}"
              f"{full['final']:>13.0f}{200 * b['final'] / b['deposited']:>13.0f}  {'' if k.startswith('SPY') else ('PASS' if ok else 'fail')}",
              flush=True)
    json.dump(out, open(s.data_dir / "results" / "d2.json", "w"), default=float, indent=1)


if __name__ == "__main__":
    main()
