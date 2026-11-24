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

import numpy as np

from trader.backtest.engine import Window


def _first_day_of_month(w: Window) -> bool:
    return len(w.days) < 2 or w.days[-1].month != w.days[-2].month


def _first_day_of_week(w: Window) -> bool:
    return len(w.days) < 2 or w.days[-1].isocalendar()[1] != w.days[-2].isocalendar()[1]


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


def buy_hold(symbol: str):
    def strat(w: Window):
        return {symbol: 1.0} if len(w.days) == 1 or _first_day_of_month(w) else None
    return strat


def momentum(etfs: set[str], n: int = 20, lookback: int = 252, skip: int = 21):
    def strat(w: Window):
        if not _first_day_of_month(w) or len(w.days) <= lookback:
            return None
        names, cols = _cols(w, w.allowed - etfs)
        c = w.close[:, cols]
        score = c[-1 - skip] / c[-1 - lookback] - 1
        return _top(names, score, n, highest=True)
    return strat


def reversal(etfs: set[str], n: int = 20, lookback: int = 5):
    def strat(w: Window):
        if not _first_day_of_week(w) or len(w.days) <= lookback:
            return None
        names, cols = _cols(w, w.allowed - etfs)
        c = w.close[:, cols]
        return _top(names, c[-1] / c[-1 - lookback] - 1, n, highest=False)
    return strat


def low_vol(etfs: set[str], n: int = 20, lookback: int = 60):
    def strat(w: Window):
        if not _first_day_of_month(w) or len(w.days) <= lookback:
            return None
        names, cols = _cols(w, w.allowed - etfs)
        c = w.close[-lookback - 1:, cols]
        with np.errstate(invalid="ignore", divide="ignore"):
            r = np.diff(np.log(c), axis=0)
        vol = np.where(np.isnan(r).sum(axis=0) > lookback // 5, np.nan, np.nanstd(r, axis=0))
        return _top(names, vol, n, highest=False)
    return strat


def trend_etfs(etfs: set[str], lookback: int = 200):
    def strat(w: Window):
        if not _first_day_of_month(w) or len(w.days) <= lookback:
            return None
        names, cols = _cols(w, w.allowed & etfs)
        c = w.close[-lookback:, cols]
        with np.errstate(invalid="ignore"):
            above = c[-1] > np.nanmean(c, axis=0)
        held = [s for s, a in zip(names, above) if a and not np.isnan(c[-1][names.index(s)])]
        return {s: 1.0 / len(held) for s in held} if held else {}
    return strat
