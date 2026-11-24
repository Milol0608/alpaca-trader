"""One scorecard per strategy (owner's brief, setup task 1): return vs SPY after costs, worst drop,
Sharpe, trades, turnover, and month-by-month results. Returns are time-weighted, so deposits in the
contribution scenarios never count as gains."""

from __future__ import annotations

from datetime import date

import numpy as np

from trader.backtest.engine import Result


def window(r: Result, first: int, last: int | None = None) -> tuple[list[date], np.ndarray, np.ndarray]:
    last = len(r.equity) if last is None else last
    flows = r.flows if r.flows is not None else np.zeros_like(r.equity)
    return r.days[first:last], r.equity[first:last], flows[first:last]


def stats(days: list[date], eq: np.ndarray, flows: np.ndarray) -> dict[str, float]:
    rets = (eq[1:] - flows[1:]) / eq[:-1] - 1
    growth = np.cumprod(1 + rets)
    years = len(rets) / 252
    peak = np.maximum.accumulate(np.concatenate([[1.0], growth]))
    dd = float(np.max(1 - np.concatenate([[1.0], growth]) / peak))
    sd = float(np.std(rets))
    return {"final": float(eq[-1]), "deposited": float(eq[0] + flows[1:].sum()),
            "cagr": float(growth[-1] ** (1 / years) - 1) if years > 0 else 0.0,
            "vol": sd * np.sqrt(252), "sharpe": float(np.mean(rets) / sd * np.sqrt(252)) if sd > 0 else 0.0,
            "max_dd": dd, "worst_month": float(min(monthly(days, eq, flows).values() or [0.0]))}


def monthly(days: list[date], eq: np.ndarray, flows: np.ndarray) -> dict[tuple[int, int], float]:
    rets = (eq[1:] - flows[1:]) / eq[:-1] - 1
    out: dict[tuple[int, int], float] = {}
    for d, x in zip(days[1:], rets):
        k = (d.year, d.month)
        out[k] = (1 + out.get(k, 0.0)) * (1 + x) - 1
    return out


def yearly(days: list[date], eq: np.ndarray, flows: np.ndarray) -> dict[int, float]:
    out: dict[int, float] = {}
    for (y, _), x in monthly(days, eq, flows).items():
        out[y] = (1 + out.get(y, 0.0)) * (1 + x) - 1
    return out
