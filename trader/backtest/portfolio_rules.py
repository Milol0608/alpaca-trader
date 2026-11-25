"""S2 (docs/RESEARCH.md): portfolio-level rules with fixed settings from their papers; nothing is tuned."""

from __future__ import annotations

import numpy as np

from trader.backtest.engine import Window
from trader.backtest.strategies import _cols, _first_day_of_month, _top

SECTORS = ["XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC"]


def _ret(w: Window, sym: str, lookback: int, skip: int = 0) -> float:
    k = w.index.get(sym)
    if k is None or len(w.days) <= lookback:
        return float("nan")
    return float(w.close[-1 - skip, k] / w.close[-1 - lookback, k] - 1)


def _momentum_picks(w: Window, etfs: set[str], n: int = 20, lookback: int = 252, skip: int = 21) -> list[str]:
    names, cols = _cols(w, w.allowed - etfs)
    c = w.close[:, cols]
    return list(_top(names, c[-1 - skip] / c[-1 - lookback] - 1, n, highest=True))


def vol_scaled_momentum(etfs: set[str], target: float = 0.20, rest: str | None = None, vol_days: int = 126):
    """V: momentum top 20 scaled by min(1, target / the picks' realised volatility); the rest in cash or `rest`."""
    def strat(w: Window):
        if not _first_day_of_month(w) or len(w.days) <= 252:
            return None
        picks = _momentum_picks(w, etfs)
        if not picks:
            return {}
        cols = np.array([w.index[s] for s in picks])
        c = w.close[-vol_days - 1:, cols]
        with np.errstate(invalid="ignore", divide="ignore"):
            r = np.nanmean(c[1:] / c[:-1] - 1, axis=1)
        vol = float(np.nanstd(r) * np.sqrt(252))
        scale = min(1.0, target / vol) if vol > 0 else 1.0
        out = {s: scale / len(picks) for s in picks}
        if rest and scale < 1:
            out[rest] = out.get(rest, 0.0) + 1 - scale
        return out
    return strat


def dual_momentum():
    """D: SPY or EFA, whichever rose more over 12 months, if it beat SHY; else AGG."""
    def strat(w: Window):
        if not _first_day_of_month(w) or len(w.days) <= 252:
            return None
        spy, efa, shy = _ret(w, "SPY", 252), _ret(w, "EFA", 252), _ret(w, "SHY", 252)
        win, r = ("EFA", efa) if efa > spy else ("SPY", spy)
        return {win: 1.0} if r > shy else {"AGG": 1.0}
    return strat


def sector_momentum(top: int = 3):
    """S: top 3 sector ETFs by 12-1 return; a slot with a negative 12-month return goes to SHY."""
    def strat(w: Window):
        if not _first_day_of_month(w) or len(w.days) <= 252:
            return None
        sc = {s: _ret(w, s, 252, 21) for s in SECTORS}
        sc = {s: v for s, v in sc.items() if not np.isnan(v) and not np.isnan(w.close[-1, w.index[s]])}
        out: dict[str, float] = {}
        for s in sorted(sc, key=lambda x: -sc[x])[:top]:
            k = s if _ret(w, s, 252) > 0 else "SHY"
            out[k] = out.get(k, 0.0) + 1.0 / top
        return out
    return strat


def high52_momentum(etfs: set[str], n: int = 20):
    """H: the n stocks closest to their 52-week high (George & Hwang 2004)."""
    def strat(w: Window):
        if not _first_day_of_month(w) or len(w.days) <= 252:
            return None
        names, cols = _cols(w, w.allowed - etfs)
        c = w.close[-252:, cols]
        full = np.isnan(c).sum(axis=0) == 0
        hi = np.where(full, np.nan_to_num(c).max(axis=0), 1.0)
        return _top(names, np.where(full, c[-1] / hi, np.nan), n, highest=True)
    return strat


def spy_mix(inner, spy_weight: float):
    """M: spy_weight in SPY, the rest in `inner`'s weights, rebalanced monthly. `inner` must decide when asked."""
    def strat(w: Window):
        if not _first_day_of_month(w) or len(w.days) <= 252:
            return None
        d = inner(w) or {}
        out = {s: x * (1 - spy_weight) for s, x in d.items()}
        out["SPY"] = out.get("SPY", 0.0) + spy_weight
        return out
    return strat


def drawdown_pause(inner, limit: float = 0.25):
    """P: track `inner` as if always on (a shadow value); hold SPY in any month that starts with the shadow more
    than `limit` below its peak. `inner` must decide on every month's first day."""
    st: dict = {"units": {}, "cash": 0.0, "nav": 1.0, "peak": 1.0}

    def price(w: Window, s: str) -> float:
        col = w.close[-10:, w.index[s]]
        ok = col[~np.isnan(col)]
        return float(ok[-1]) if len(ok) else 0.0

    def strat(w: Window):
        if st["units"]:
            st["nav"] = st["cash"] + sum(u * price(w, s) for s, u in st["units"].items())
            st["peak"] = max(st["peak"], st["nav"])
        if not _first_day_of_month(w) or len(w.days) <= 252:
            return None
        d = inner(w) or {}
        st["units"] = {s: x * st["nav"] / price(w, s) for s, x in d.items() if price(w, s) > 0}
        st["cash"] = (1.0 - sum(x for s, x in d.items() if s in st["units"])) * st["nav"]
        if st["nav"] < (1 - limit) * st["peak"]:
            return {"SPY": 1.0}
        return d
    return strat
