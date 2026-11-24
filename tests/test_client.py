from __future__ import annotations

import httpx
import pytest

from trader.alpaca.client import AlpacaClient, AlpacaError, RateLimiter


def bar(t: str, c: float) -> dict:
    return {"t": t, "o": c, "h": c, "l": c, "c": c, "v": 100, "n": 3, "vw": c}


def make(handler, **kw) -> AlpacaClient:
    return AlpacaClient("https://paper.test", "https://data.test", "KEY", "SECRET",
                        transport=httpx.MockTransport(handler), sleep=lambda s: None, **kw)


def test_bars_follow_pages_and_send_auth_and_params() -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if "page_token" not in req.url.params:
            return httpx.Response(200, json={"bars": {"AAA": [bar("2026-01-02T05:00:00Z", 1.0)]}, "next_page_token": "p2"})
        return httpx.Response(200, json={"bars": {"BBB": [bar("2026-01-02T05:00:00Z", 2.0)]}, "next_page_token": None})

    with make(handler) as c:
        got = list(c.bars(["AAA", "BBB"], "1Day", "2026-01-01", "2026-01-31"))
    assert [(s, b["c"]) for s, b in got] == [("AAA", 1.0), ("BBB", 2.0)]
    first = seen[0]
    assert first.headers["APCA-API-KEY-ID"] == "KEY" and first.headers["APCA-API-SECRET-KEY"] == "SECRET"
    assert first.url.host == "data.test" and first.url.path == "/v2/stocks/bars"
    p = first.url.params
    assert (p["symbols"], p["timeframe"], p["limit"], p["adjustment"], p["feed"]) == ("AAA,BBB", "1Day", "10000", "all", "iex")
    assert seen[1].url.params["page_token"] == "p2"


def test_retries_429_then_succeeds() -> None:
    n = {"calls": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        n["calls"] += 1
        return httpx.Response(429, headers={"X-RateLimit-Reset": "0"}) if n["calls"] < 3 else httpx.Response(200, json=[])

    with make(handler) as c:
        assert c.assets(status="active") == []
    assert n["calls"] == 3


def test_client_error_is_raised_not_retried() -> None:
    n = {"calls": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        n["calls"] += 1
        return httpx.Response(422, text="invalid timeframe")

    with make(handler) as c, pytest.raises(AlpacaError, match="422"):
        list(c.bars(["AAA"], "7Min", "2026-01-01", "2026-01-02"))
    assert n["calls"] == 1


def test_missing_keys_refuse_to_start() -> None:
    with pytest.raises(AlpacaError, match="required"):
        AlpacaClient("https://p", "https://d", "", "")


def test_rate_limiter_waits_when_window_is_full() -> None:
    t = {"now": 0.0}
    slept: list[float] = []

    def sleep(s: float) -> None:
        slept.append(s)
        t["now"] += s

    rl = RateLimiter(2, clock=lambda: t["now"], sleep=sleep)
    rl.wait(); rl.wait()
    rl.wait()  # third call within 60 s must wait for the first to age out
    assert slept and 59.9 < slept[0] <= 60.1
