"""Daily backtest engine: target weights in, equity curve and trades out.

Timing (no look-ahead):
  after the close of day t   a strategy sees bars up to and including day t and returns target weights;
  at the open of day t+1     the portfolio trades to those weights at the open price, paying costs;
  through day t+1            holdings earn open(t+1) -> close(t+1), then close -> close after that.
Long-only, no leverage: the paper account is a cash account (multiplier 1). Weights are clipped at 0 and
scaled down if they sum above 1; the rest is cash earning nothing (conservative).
Costs: `cost_bps` per side on traded value (half the spread plus slippage). Orders under `min_order`
dollars are skipped, like Alpaca's ~$1 fractional minimum, which matters for a $200 account.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import polars as pl

# strategy(window) -> {symbol: weight}; None means "keep current holdings".
Strategy = Callable[["Window"], dict[str, float] | None]


@dataclass
class Window:
    """All a strategy can see on a decision day: rows up to and including today's close, never
    later ones. The arrays are views, so this costs nothing, and the future simply isn't there."""

    today: date
    days: list[date]
    symbols: list[str]
    close: np.ndarray   # [day, symbol]; last row is today
    open: np.ndarray
    volume: np.ndarray
    allowed: set[str]   # this month's point-in-time universe
    index: dict[str, int]


@dataclass
class Context:
    """What a strategy may look at on day i: everything up to and including that day's close."""

    days: list[date]
    symbols: list[str]
    close: np.ndarray        # [day, symbol], NaN where no bar
    open: np.ndarray
    volume: np.ndarray
    universe: dict[date, set[str]]  # month start -> allowed symbols (point-in-time)

    def allowed(self, i: int) -> set[str]:
        d = self.days[i]
        return self.universe.get(date(d.year, d.month, 1), set())

    def col(self, symbol: str) -> int:
        return self._index[symbol]

    def __post_init__(self) -> None:
        self._index = {s: k for k, s in enumerate(self.symbols)}


@dataclass
class Result:
    name: str
    days: list[date]
    equity: np.ndarray
    trades: int = 0
    traded_value: float = 0.0
    costs: float = 0.0
    skipped_small: int = 0
    delisted: int = 0
    weights_log: list[tuple[date, dict[str, float]]] = field(default_factory=list)

    def returns(self) -> np.ndarray:
        return np.diff(self.equity) / self.equity[:-1]

    def stats(self) -> dict[str, float]:
        r = self.returns()
        years = len(r) / 252
        cagr = (self.equity[-1] / self.equity[0]) ** (1 / years) - 1 if years > 0 else 0.0
        vol = float(np.std(r) * np.sqrt(252))
        peak = np.maximum.accumulate(self.equity)
        dd = float(np.max(1 - self.equity / peak))
        return {"final": float(self.equity[-1]), "cagr": float(cagr), "vol": vol,
                "sharpe": float(np.mean(r) / np.std(r) * np.sqrt(252)) if np.std(r) > 0 else 0.0,
                "max_dd": dd, "trades": self.trades, "costs": self.costs,
                "turnover_per_year": self.traded_value / float(np.mean(self.equity)) / years if years > 0 else 0.0}


def build_context(daily: pl.DataFrame, universe: pl.DataFrame, start: date, end: date) -> Context:
    """daily: symbol, t, open, close, volume (adjusted). Only universe symbols are loaded."""
    keep = set(universe["symbol"].to_list())
    d = (daily.filter(pl.col("symbol").is_in(list(keep)))
         .with_columns(pl.col("t").dt.convert_time_zone("America/New_York").dt.date().alias("day"))
         .filter((pl.col("day") >= start) & (pl.col("day") <= end)))
    days = sorted(d["day"].unique().to_list())
    symbols = sorted(d["symbol"].unique().to_list())
    di = {x: k for k, x in enumerate(days)}
    si = {x: k for k, x in enumerate(symbols)}
    shape = (len(days), len(symbols))
    close, opn, vol = np.full(shape, np.nan), np.full(shape, np.nan), np.full(shape, np.nan)
    r = np.array([di[x] for x in d["day"].to_list()])
    c = np.array([si[x] for x in d["symbol"].to_list()])
    close[r, c] = d["close"].to_numpy()
    opn[r, c] = d["open"].to_numpy()
    # A price of zero or below is a data error (seen around bankruptcies), never a tradable price.
    close[close <= 0] = np.nan
    opn[opn <= 0] = np.nan
    vol[r, c] = d["volume"].to_numpy()
    uni: dict[date, set[str]] = {}
    for m, s in universe.select("month", "symbol").iter_rows():
        uni.setdefault(m, set()).add(s)
    return Context(days, symbols, close, opn, vol, uni)


def run(ctx: Context, strategy: Strategy, name: str, *, capital: float = 200.0, cost_bps: float = 5.0,
        min_order: float = 1.0, start_index: int = 1, delist_after: int = 5) -> Result:
    """delist_after: a holding with no bar for this many trading days in a row is closed at its last
    close (roughly a delisting or takeover cash-out). Without it, a reused ticker (AMTD was TD
    Ameritrade, later a different company) would re-price an old position at the new company's price."""
    n_days, n_sym = ctx.close.shape
    shares = np.zeros(n_sym)
    cash = capital
    equity = np.full(n_days, np.nan)
    equity[:start_index] = capital
    res = Result(name, ctx.days, equity)
    target: dict[str, float] | None = None
    last_px = np.full(n_sym, np.nan)  # last known close, for valuing a holding on a day it has no bar
    missing = np.zeros(n_sym, dtype=int)  # consecutive days without a bar
    cost_rate = cost_bps / 1e4
    for i in range(start_index, n_days):
        cl, op = ctx.close[i], ctx.open[i]
        if target is not None:  # trade at today's open toward yesterday's decision
            px = np.where(np.isnan(op), np.nan, op)
            tradable = ~np.isnan(px)
            # A holding with no price today (halted, delisted) can't be sold, so its value can't be
            # spent either: only cash plus tradable holdings are allocated.
            alloc = cash + float(np.sum(shares[tradable] * px[tradable]))
            w = {s: max(0.0, x) for s, x in target.items() if x > 0 and s in ctx._index}
            tot = sum(w.values())
            if tot > 1:
                w = {s: x / tot for s, x in w.items()}
            want = np.where(tradable, 0.0, shares)  # untradable holdings stay as they are
            for s, x in w.items():
                k = ctx._index[s]
                if tradable[k]:
                    want[k] = x * alloc / (px[k] * (1 + cost_rate))  # leave room for the fee
            delta = want - shares
            order = [k for k in np.nonzero(tradable & (delta != 0))[0]]
            order.sort(key=lambda k: delta[k])  # sells (negative) first, so their cash funds the buys
            for k in order:
                d = delta[k]
                if d > 0:  # never spend cash we don't have
                    d = min(d, max(0.0, cash) / (px[k] * (1 + cost_rate)))
                notional = abs(d) * px[k]
                if notional < min_order:
                    res.skipped_small += 1
                    continue
                fee = notional * cost_rate
                cash -= d * px[k] + fee
                shares[k] += d
                res.trades += 1
                res.traded_value += notional
                res.costs += fee
            assert cash > -1e-6, f"cash went negative ({cash}) on {ctx.days[i]}"
        missing = np.where(np.isnan(cl), missing + 1, 0)
        gone = (missing >= delist_after) & (shares != 0)
        if gone.any():
            cash += float(np.sum(shares[gone] * np.nan_to_num(last_px[gone])))  # no fee: not our trade
            shares[gone] = 0.0
            res.delisted += int(gone.sum())
        last_px = np.where(np.isnan(cl), last_px, cl)
        equity[i] = cash + np.nansum(shares * last_px)
        decision = strategy(Window(ctx.days[i], ctx.days[: i + 1], ctx.symbols, ctx.close[: i + 1],
                                   ctx.open[: i + 1], ctx.volume[: i + 1], ctx.allowed(i), ctx._index))
        if decision is not None:
            target = decision
            res.weights_log.append((ctx.days[i], decision))
        else:
            target = None
    return res
