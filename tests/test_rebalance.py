from __future__ import annotations

from datetime import date

import httpx
import pytest

from trader.alpaca.client import AlpacaClient, AlpacaError
from trader.live.rebalance import already_ran_today, execute, order_id, plan


def test_empty_account_buys_each_target_within_cash() -> None:
    p = plan(200.0, 200.0, {}, {f"S{k}": 0.05 for k in range(20)})
    assert len(p.buys) == 20 and not p.sells
    assert all(abs(o.notional - 9.8) < 0.011 for o in p.buys)  # 5% of $196 (2% cash buffer)
    assert sum(o.notional for o in p.buys) <= 200 * 0.98 + 1e-9


def test_never_spends_more_than_cash() -> None:
    p = plan(200.0, 50.0, {"OLD": (1.0, 150.0)}, {"OLD": 0.75, "NEW": 0.25})
    # OLD is already at target (150 of 147 wanted, within 5%); only $50 - $4 buffer can be spent.
    assert sum(o.notional for o in p.buys) <= 46.0 + 1e-9


def test_drops_and_trims_go_first_and_fund_buys() -> None:
    positions = {"GONE": (2.0, 50.0), "BIG": (1.0, 100.0)}  # $100 + $100 held, $0 cash
    p = plan(200.0, 0.0, positions, {"BIG": 0.25, "NEW": 0.5})
    assert [(o.symbol, o.close_all) for o in p.sells] == [("BIG", False), ("GONE", True)]
    trim = next(o for o in p.sells if o.symbol == "BIG")
    assert abs(trim.qty * 100 - (100 - 49.0)) < 0.01  # trim BIG from $100 to $49
    assert p.buys and p.buys[0].symbol == "NEW"


def test_small_drift_is_left_alone() -> None:
    p = plan(200.0, 4.0, {"A": (1.0, 100.0), "B": (1.0, 96.0)}, {"A": 0.5, "B": 0.5})
    assert not p.sells and not p.buys  # both within 5% of $98


def test_one_order_is_capped_at_15_percent_of_equity() -> None:
    p = plan(200.0, 200.0, {}, {"ONLY": 1.0})
    assert len(p.buys) == 1 and p.buys[0].notional <= 30.0


def test_tiny_orders_are_skipped() -> None:
    p = plan(200.0, 200.0, {}, {"A": 0.004})  # $0.78 < $1 minimum
    assert not p.buys


def _client(handler, base="https://paper-api.alpaca.markets") -> AlpacaClient:
    return AlpacaClient(base, "https://data.test", "K", "S", transport=httpx.MockTransport(handler),
                        sleep=lambda s: None, allow_orders=True)


def test_execute_refuses_a_non_paper_host() -> None:
    with _client(lambda r: httpx.Response(200, json={}), base="https://api.alpaca.markets") as c, \
            pytest.raises(AlpacaError, match="not the paper host"):
        execute(c, plan(200.0, 200.0, {}, {"A": 0.1}), tag="mom", day=date(2026, 11, 24), dry_run=False)


def test_read_only_client_cannot_place_orders() -> None:
    c = AlpacaClient("https://paper-api.alpaca.markets", "https://d", "K", "S",
                     transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    with pytest.raises(AlpacaError, match="read-only"):
        c.submit_order(symbol="A", side="buy", notional="5.00", client_order_id="x")


def test_execute_sends_sells_then_buys_with_tagged_ids() -> None:
    sent: list[tuple[str, str, dict]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        import json
        body = json.loads(req.content) if req.content else {}
        sent.append((req.method, req.url.path, body))
        if req.method == "GET" and req.url.path == "/v2/orders":
            return httpx.Response(200, json=[])  # nothing open: sells "filled"
        if req.method == "GET" and req.url.path == "/v2/account":
            return httpx.Response(200, json={"cash": "150.00", "equity": "200"})
        return httpx.Response(200, json={"client_order_id": body.get("client_order_id", "close"), "status": "accepted"})

    p = plan(200.0, 50.0, {"GONE": (1.0, 100.0), "KEEP": (1.0, 50.0)}, {"KEEP": 0.25, "NEW": 0.5})
    with _client(handler) as c:
        execute(c, p, tag="mom", day=date(2026, 11, 24), dry_run=False)
    writes = [(m, path, b) for m, path, b in sent if m in ("POST", "DELETE")]
    assert writes[0][:2] == ("DELETE", "/v2/positions/GONE")
    buys = [b for m, path, b in writes if m == "POST"]
    assert buys and buys[0]["client_order_id"] == order_id("mom", date(2026, 11, 24), "NEW", "buy")
    assert buys[0]["type"] == "market" and buys[0]["time_in_force"] == "day" and "notional" in buys[0]


def test_dry_run_sends_nothing() -> None:
    writes = []

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method != "GET":
            writes.append(req)
        return httpx.Response(200, json={})

    with _client(handler) as c:
        execute(c, plan(200.0, 200.0, {}, {"A": 0.1}), tag="mom", day=date(2026, 11, 24), dry_run=True, log=lambda *a: None)
    assert writes == []


def test_a_second_run_the_same_day_is_detected() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"client_order_id": "mom-20261124-AAPL-buy"}])

    with _client(handler) as c:
        assert already_ran_today(c, "mom", date(2026, 11, 24))
        assert not already_ran_today(c, "mom", date(2026, 11, 25))
