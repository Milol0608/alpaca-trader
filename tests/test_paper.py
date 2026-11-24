from __future__ import annotations

from datetime import date

from trader.paper import rebalance_due


def filled(cid: str, at: str) -> dict:
    return {"client_order_id": cid, "status": "filled", "filled_at": at}


def test_empty_account_rebalances_now() -> None:
    assert rebalance_due([], [], date(2026, 11, 24))[0]


def test_same_month_does_not_rebalance_again() -> None:
    orders = [filled("mom-20261124-AAPL-buy", "2026-11-24T15:01:00Z")]
    assert not rebalance_due(orders, [{"symbol": "AAPL"}], date(2026, 11, 30))[0]


def test_first_run_of_a_new_month_rebalances() -> None:
    orders = [filled("mom-20261124-AAPL-buy", "2026-11-24T15:01:00Z")]
    due, why = rebalance_due(orders, [{"symbol": "AAPL"}], date(2026, 12, 1))
    assert due and "December" in why


def test_only_our_tagged_filled_orders_count() -> None:
    orders = [filled("manual-1", "2026-12-01T15:00:00Z"),
              {"client_order_id": "mom-20261201-AAPL-buy", "status": "canceled", "filled_at": None}]
    assert rebalance_due(orders, [{"symbol": "AAPL"}], date(2026, 12, 2))[0]  # nothing of ours filled
