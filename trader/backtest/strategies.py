"""Baseline daily strategies. Parameters are the textbook ones, fixed before looking at our data,
so they aren't tuned to this history. Each one is a research candidate, not a recommendation.

  buy_hold        100% in one symbol (SPY is the benchmark everything must beat after costs)
  momentum        each month, the stocks with the best 12-month return excluding the last month
                  (Jegadeesh-Titman 12-1), top N, equal weight
  reversal        each week, last week's biggest losers among large caps (short-term reversal), top N
  low_vol         each month, the N least volatile stocks over 60 days (low-volatility anomaly)
  trend_etfs      each month, the ETFs above their 200-day average, equal weight; cash if none
                  (time-series trend following)
"""

from __future__ import annotations

from datetime import date

import numpy as np

from trader.backtest.engine import Window


def _first_day_of_month(w: Window) -> bool:
    return len(w.days) < 2 or w.days[-1].month != w.days[-2].month


def _first_day_of_week(w: Window) -> bool:
    return len(w.days) < 2 or w.days[-1].isocalendar()[1] != w.days[-2].isocalendar()[1]


def _due(w: Window, every: str, force: bool, also_on: date | None) -> bool:
    """Rebalance on schedule; `force` decides every time (live: the paper runner decides when);
    `also_on` adds one extra decision day (forward tracking starts invested, not in cash)."""
    if force or (also_on is not None and w.today == also_on):
        return True
    return _first_day_of_month(w) if every == "month" else _first_day_of_week(w)


def _cols(w: Window, symbols: set[str]) -> tuple[list[str], np.ndarray]:
    names = sorted(s for s in symbols if s in w.index)
    return names, np.array([w.index[s] for s in names], dtype=int)


def _top(names: list[str], score: np.ndarray, n: int, highest: bool) -> dict[str, float]:
    ok = ~np.isnan(score)
    if not ok.any():
        return {}
    names_ok, s = [x for x, k in zip(names, ok) if k], score[ok]
    order = np.argsort(-s if highest else s)[:n]
    return {names_ok[k]: 1.0 / len(order) for k in order}


def buy_hold(symbol: str, *, force: bool = False, also_on: date | None = None):
    def strat(w: Window):
        return {symbol: 1.0} if len(w.days) == 1 or _due(w, "month", force, also_on) else None
    return strat


def momentum(etfs: set[str], n: int = 20, lookback: int = 252, skip: int = 21, *, force: bool = False, also_on: date | None = None):
    def strat(w: Window):
        if not _due(w, "month", force, also_on) or len(w.days) <= lookback:
            return None
        names, cols = _cols(w, w.allowed - etfs)
        c = w.close[:, cols]
        score = c[-1 - skip] / c[-1 - lookback] - 1
        return _top(names, score, n, highest=True)
    return strat


def reversal(etfs: set[str], n: int = 20, lookback: int = 5, *, force: bool = False, also_on: date | None = None):
    def strat(w: Window):
        if not _due(w, "week", force, also_on) or len(w.days) <= lookback:
            return None
        names, cols = _cols(w, w.allowed - etfs)
        c = w.close[:, cols]
        return _top(names, c[-1] / c[-1 - lookback] - 1, n, highest=False)
    return strat


def low_vol(etfs: set[str], n: int = 20, lookback: int = 60, *, force: bool = False, also_on: date | None = None):
    def strat(w: Window):
        if not _due(w, "month", force, also_on) or len(w.days) <= lookback:
            return None
        names, cols = _cols(w, w.allowed - etfs)
        c = w.close[-lookback - 1:, cols]
        with np.errstate(invalid="ignore", divide="ignore"):
            r = np.diff(np.log(c), axis=0)
        vol = np.where(np.isnan(r).sum(axis=0) > lookback // 5, np.nan, np.nanstd(r, axis=0))
        return _top(names, vol, n, highest=False)
    return strat


def trend_etfs(etfs: set[str], lookback: int = 200, *, force: bool = False, also_on: date | None = None):
    def strat(w: Window):
        if not _due(w, "month", force, also_on) or len(w.days) <= lookback:
            return None
        names, cols = _cols(w, w.allowed & etfs)
        c = w.close[-lookback:, cols]
        with np.errstate(invalid="ignore"):
            above = c[-1] > np.nanmean(c, axis=0)
        held = [s for s, a in zip(names, above) if a and not np.isnan(c[-1][names.index(s)])]
        return {s: 1.0 / len(held) for s in held} if held else {}
    return strat


def momentum_low_vol(etfs: set[str], n: int = 20, lookback: int = 252, skip: int = 21, vol_days: int = 60, *,
                     force: bool = False, also_on: date | None = None):
    """R1 (docs/RESEARCH.md): average of the 12-1 momentum rank and the 60-day volatility rank."""
    def strat(w: Window):
        if not _due(w, "month", force, also_on) or len(w.days) <= lookback:
            return None
        names, cols = _cols(w, w.allowed - etfs)
        c = w.close[:, cols]
        mom = c[-1 - skip] / c[-1 - lookback] - 1
        with np.errstate(invalid="ignore", divide="ignore"):
            r = np.diff(np.log(c[-vol_days - 1:]), axis=0)
        vol = np.where(np.isnan(r).sum(axis=0) > vol_days // 5, np.nan, np.nanstd(r, axis=0))
        ok = ~np.isnan(mom) & ~np.isnan(vol)
        if not ok.any():
            return {}
        idx = np.nonzero(ok)[0]
        mom_rank = np.argsort(np.argsort(-mom[idx]))   # 0 = strongest momentum
        vol_rank = np.argsort(np.argsort(vol[idx]))    # 0 = calmest
        score = (mom_rank + vol_rank) / 2.0
        best = idx[np.argsort(score, kind="stable")[:n]]
        return {names[k]: 1.0 / len(best) for k in best}
    return strat


def momentum_crash_filter(etfs: set[str], n: int = 20, lookback: int = 252, skip: int = 21, trend_days: int = 200,
                          hedge: str | None = None, *, force: bool = False, also_on: date | None = None):
    """R2 (docs/RESEARCH.md): momentum only while SPY is above its 200-day average; else cash
    (hedge=None) or the hedge ETF (R2b: SH)."""
    mom = momentum(etfs, n, lookback, skip, force=True)

    def strat(w: Window):
        if not _due(w, "month", force, also_on) or len(w.days) <= max(lookback, trend_days):
            return None
        k = w.index.get("SPY")
        spy = w.close[-trend_days:, k] if k is not None else None
        if spy is None or np.isnan(spy[-1]):
            return mom(w)
        if spy[-1] > np.nanmean(spy):
            return mom(w)
        return {hedge: 1.0} if hedge and hedge in w.index and not np.isnan(w.close[-1, w.index[hedge]]) else {}
    return strat


def momentum_stops(etfs: set[str], stop: float | None, target: float | str | None, n: int = 20, lookback: int = 252,
                   skip: int = 21, vol_days: int = 60):
    """R6 (docs/RESEARCH.md): momentum 12-1 top n, re-ranked monthly; each week a holding is sold if it is down
    `stop` or up `target` from its entry close, and the money goes to the best-ranked stock not held and not sold
    this month. target="adaptive": 30% for picks with above-median 60-day volatility, 25% for the rest.
    Weights drift with prices between decisions (no mid-month re-equal-weighting)."""
    st: dict = {"units": {}, "entry": {}, "tgt": {}, "banned": set(), "med_vol": None}

    def vols(c: np.ndarray) -> np.ndarray:
        with np.errstate(invalid="ignore", divide="ignore"):
            r = np.diff(np.log(c[-vol_days - 1:]), axis=0)
        return np.nanstd(r, axis=0)

    def last_px(w: Window, s: str) -> float:
        col = w.close[-10:, w.index[s]]
        ok = col[~np.isnan(col)]
        return float(ok[-1]) if len(ok) else float("nan")

    def tgt_for(v: float) -> float | None:
        if target == "adaptive":
            return 0.30 if v > st["med_vol"] else 0.25
        return target

    def ranked(w: Window) -> tuple[list[str], np.ndarray, np.ndarray]:
        names, cols = _cols(w, w.allowed - etfs)
        c = w.close[:, cols]
        score = c[-1 - skip] / c[-1 - lookback] - 1
        ok = ~np.isnan(score) & ~np.isnan(c[-1])
        idx = np.nonzero(ok)[0]
        order = idx[np.argsort(-score[idx], kind="stable")]
        return [names[k] for k in order], vols(c)[order], c[-1][order]

    def strat(w: Window):
        if len(w.days) <= lookback:
            return None
        if _first_day_of_month(w):
            names, v, px = ranked(w)
            pick = list(range(min(n, len(names))))
            if not pick:
                st["units"] = {}
                return {}
            st["med_vol"] = float(np.nanmedian(v[pick]))
            st["banned"] = set()
            st["units"] = {names[k]: (1.0 / len(pick)) / px[k] for k in pick}
            st["entry"] = {names[k]: px[k] for k in pick}
            st["tgt"] = {names[k]: tgt_for(v[k]) for k in pick}
            return {s: 1.0 / len(pick) for s in st["units"]}
        if not _first_day_of_week(w) or not st["units"]:
            return None
        now = {s: last_px(w, s) for s in st["units"]}
        out = []
        for s, p in now.items():
            if np.isnan(p):
                continue
            r = p / st["entry"][s] - 1
            t = st["tgt"][s]
            if (stop is not None and r <= -stop) or (t is not None and r >= t):
                out.append(s)
        if not out:
            return None
        val = {s: st["units"][s] * now[s] for s in st["units"] if not np.isnan(now[s])}
        names, v, px = ranked(w)
        cands = [(names[k], v[k], px[k]) for k in range(len(names))
                 if names[k] not in st["units"] and names[k] not in st["banned"]]
        for s in out:
            st["banned"].add(s)
            amt = val.pop(s)
            del st["units"][s], st["entry"][s], st["tgt"][s]
            if cands:
                name, vv, p = cands.pop(0)
                st["units"][name] = amt / p
                st["entry"][name] = p
                st["tgt"][name] = tgt_for(vv)
                val[name] = amt
        tot = sum(val.values())
        return {s: x / tot for s, x in val.items()} if tot > 0 else {}
    return strat
