from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from trader.backtest.engine import Context, Window, run

DAYS = [date(2026, 1, 5) + timedelta(days=k) for k in range(5)]


def ctx(opens: list[list[float]], closes: list[list[float]], symbols=("A", "B")) -> Context:
    o, c = np.array(opens, dtype=float), np.array(closes, dtype=float)
    return Context(DAYS[: len(o)], list(symbols), c, o, np.ones_like(c), {date(2026, 1, 1): set(symbols)})


def test_decision_at_close_trades_at_next_open_and_pays_costs() -> None:
    # A: opens 10, 20, 20...; closes 10, 20, 22. Buying "after day 0's close" fills at day 1's OPEN (20), not 10.
    c = ctx([[10, 1], [20, 1], [20, 1]], [[10, 1], [20, 1], [22, 1]])
    seen: list[tuple[int, date]] = []

    def strat(w: Window):
        seen.append((w.close.shape[0], w.today))
        return {"A": 1.0} if w.today == DAYS[0] else None

    r = run(c, strat, "t", capital=100.0, cost_bps=10, start_index=0)
    # Day 1: buy at the open (20), leaving room for the 10 bps fee: 100 / (20 * 1.001) shares, all
    # cash spent including the fee. Equity at day 1's close (20) is 100 - fee; day 2 marks at 22.
    shares = 100 / (20 * 1.001)
    assert r.trades == 1 and abs(r.costs - shares * 20 * 0.001) < 1e-9
    assert np.allclose(r.equity, [100.0, shares * 20, shares * 22])
    # The strategy only ever saw rows up to its own day: 1 row on day 0, 2 on day 1, 3 on day 2.
    assert seen == [(1, DAYS[0]), (2, DAYS[1]), (3, DAYS[2])]


def test_no_trade_keeps_holdings_and_none_means_hold() -> None:
    c = ctx([[10, 1]] * 4, [[10, 1], [11, 1], [12, 1], [13, 1]])
    def strat(w: Window):
        return {"A": 1.0} if w.today == DAYS[0] else None

    r = run(c, strat, "t", capital=100.0, cost_bps=0, start_index=0)
    assert r.trades == 1  # bought once, never re-traded
    assert np.allclose(r.equity[1:], [100 / 10 * 11, 100 / 10 * 12, 100 / 10 * 13])


def test_orders_under_min_are_skipped() -> None:
    c = ctx([[10, 10]] * 3, [[10, 10]] * 3)

    def strat(w: Window):
        return {"A": 0.995, "B": 0.005} if w.today == DAYS[0] else None  # B would be $1 * 0.5 = $0.50 on a $100 account

    r = run(c, strat, "t", capital=100.0, cost_bps=0, start_index=0)
    assert r.skipped_small == 1 and r.trades == 1


def test_weights_above_one_are_scaled_and_negative_ignored() -> None:
    c = ctx([[10, 10]] * 3, [[10, 10]] * 3)
    r = run(c, lambda w: {"A": 1.5, "B": 1.5} if w.today == DAYS[0] else None, "t", capital=100.0, cost_bps=0, start_index=0)
    assert abs(r.traded_value - 100.0) < 1e-9  # 50 + 50, never leverage
    r2 = run(c, lambda w: {"A": -1.0} if w.today == DAYS[0] else None, "t", capital=100.0, cost_bps=0, start_index=0)
    assert r2.trades == 0  # long-only: a short is dropped


def test_a_symbol_with_no_bar_today_is_valued_at_last_close() -> None:
    nan = float("nan")
    c = ctx([[10, 1], [10, 1], [nan, 1], [12, 1]], [[10, 1], [10, 1], [nan, 1], [12, 1]])
    r = run(c, lambda w: {"A": 1.0} if w.today == DAYS[0] else None, "t", capital=100.0, cost_bps=0, start_index=0)
    assert np.allclose(r.equity, [100, 100, 100, 120])


def test_money_is_conserved_when_a_holding_cannot_trade() -> None:
    # Hold A; A then has no bar for two days while the strategy wants to rotate into B. The old engine
    # counted A's value as spendable AND kept A, pushing cash negative and then zeroing it: free money.
    nan = float("nan")
    c = ctx([[10, 10], [10, 10], [nan, 10], [nan, 10], [10, 10]],
            [[10, 10], [10, 10], [nan, 10], [nan, 10], [10, 10]])

    def strat(w: Window):
        return {"A": 1.0} if w.today == DAYS[0] else {"B": 1.0}

    r = run(c, strat, "t", capital=100.0, cost_bps=0, start_index=0)
    # Prices never change and there are no costs, so equity must stay exactly 100 every day.
    assert np.allclose(r.equity, 100.0), r.equity


def test_flat_prices_lose_exactly_the_costs() -> None:
    c = ctx([[10, 10]] * 5, [[10, 10]] * 5)
    flip = {0: {"A": 1.0}, 1: {"B": 1.0}, 2: {"A": 1.0}, 3: {"B": 1.0}}
    r = run(c, lambda w: flip.get(DAYS.index(w.today)), "t", capital=100.0, cost_bps=10, start_index=0)
    assert abs((100.0 - r.equity[-1]) - r.costs) < 1e-9 and r.costs > 0


def test_a_long_gap_closes_the_position_so_a_reused_ticker_cannot_reprice_it() -> None:
    nan = float("nan")
    days = [DAYS[0] + timedelta(days=k) for k in range(10)]
    closes = [[10.0]] * 2 + [[nan]] * 6 + [[500.0]] * 2  # delisted at 10; a new company reuses it at 500
    c = Context(days, ["A"], np.array(closes), np.array(closes), np.ones((10, 1)), {date(2026, 1, 1): {"A"}})
    r = run(c, lambda w: {"A": 1.0} if w.today == days[0] else None, "t", capital=100.0, cost_bps=0,
            start_index=0, delist_after=5)
    assert r.delisted == 1
    assert np.allclose(r.equity[-1], 100.0)  # cashed out at 10, never marked at 500


def test_zero_prices_are_treated_as_missing() -> None:
    import polars as pl
    from datetime import datetime, timezone
    from trader.backtest.engine import build_context
    t = [datetime(2026, 1, 5 + k, 15, tzinfo=timezone.utc) for k in range(3)]
    daily = pl.DataFrame({"symbol": ["A"] * 3, "t": t, "open": [10.0, 0.0, 10.0], "close": [10.0, 0.0, 10.0],
                          "volume": [1.0] * 3}).with_columns(pl.col("t").cast(pl.Datetime("us", "UTC")))
    uni = pl.DataFrame({"month": [date(2026, 1, 1)], "symbol": ["A"]})
    cx = build_context(daily, uni, date(2026, 1, 1), date(2026, 1, 31))
    assert np.isnan(cx.close[1, 0]) and np.isnan(cx.open[1, 0])
