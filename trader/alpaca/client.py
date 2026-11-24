"""Alpaca REST client: market data and read-only account calls.

Shapes verified against Alpaca's API reference (2026-11-24):
  GET {data}/v2/stocks/bars   symbols, timeframe, start, end, limit (<= 10000 points across ALL
                              symbols per page), adjustment, feed, sort, page_token
                              -> {"bars": {SYM: [{t,o,h,l,c,v,n,vw}]}, "next_page_token": str|null}
  GET {trading}/v2/assets     status, asset_class, exchange, attributes -> [asset]
  GET {trading}/v2/account    money fields are strings
  GET {trading}/v2/calendar   legacy calendar: [{date, open, close, session_open, session_close, ...}]
Auth headers: APCA-API-KEY-ID, APCA-API-SECRET-KEY. Paper and live use different hosts and keys.

Orders (verified 2026-11-24): POST {trading}/v2/orders with symbol, side, type, time_in_force, and
either qty (fractional only for market/day) or notional (market/day only); client_order_id <= 128 chars.
A day order sent while the market is closed is queued for the next session. DELETE
{trading}/v2/positions/{symbol} closes a whole position and returns the closing order.
Orders are only allowed when the client is created with allow_orders=True, which only the paper
runner does, and only after checking it's talking to the paper host.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Iterator
from typing import Any

import httpx

log = logging.getLogger(__name__)

MAX_BARS_PER_PAGE = 10_000
RETRY_STATUSES = {429, 500, 502, 503, 504}


class AlpacaError(RuntimeError):
    pass


class RateLimiter:
    """At most `per_minute` calls in any rolling 60 s window."""

    def __init__(self, per_minute: int, clock=time.monotonic, sleep=time.sleep):
        self.per_minute, self.clock, self.sleep = per_minute, clock, sleep
        self.calls: deque[float] = deque()
        self.lock = threading.Lock()

    def wait(self) -> None:
        with self.lock:
            while True:
                now = self.clock()
                while self.calls and now - self.calls[0] >= 60:
                    self.calls.popleft()
                if len(self.calls) < self.per_minute:
                    self.calls.append(now)
                    return
                self.sleep(60 - (now - self.calls[0]) + 0.01)


class AlpacaClient:
    def __init__(self, trading_url: str, data_url: str, key_id: str, secret_key: str,
                 requests_per_minute: int = 180, transport: httpx.BaseTransport | None = None,
                 sleep=time.sleep, max_retries: int = 5, allow_orders: bool = False):
        if not key_id or not secret_key:
            raise AlpacaError("Alpaca key id and secret are required (see .env.example)")
        headers = {"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret_key}
        self.trading = httpx.Client(base_url=trading_url, headers=headers, timeout=30, transport=transport)
        self.data = httpx.Client(base_url=data_url, headers=headers, timeout=60, transport=transport)
        self.limiter = RateLimiter(requests_per_minute, sleep=sleep)
        self.sleep, self.max_retries = sleep, max_retries
        self.calls = 0
        self.allow_orders = allow_orders

    def __enter__(self) -> AlpacaClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self.trading.close()
        self.data.close()

    def _get(self, http: httpx.Client, path: str, params: dict[str, Any] | None = None) -> Any:
        for attempt in range(self.max_retries + 1):
            self.limiter.wait()
            try:
                r = http.get(path, params=params)
                self.calls += 1
            except httpx.TransportError as e:
                if attempt == self.max_retries:
                    raise AlpacaError(f"GET {path}: {type(e).__name__}") from e
                self.sleep(min(2 ** attempt, 30))
                continue
            if r.status_code in RETRY_STATUSES and attempt < self.max_retries:
                self.sleep(self._retry_after(r, attempt))
                continue
            if r.status_code >= 400:
                # The body explains bad parameters; it never contains our keys.
                raise AlpacaError(f"GET {path} -> {r.status_code}: {r.text[:300]}")
            return r.json()
        raise AlpacaError(f"GET {path}: gave up after {self.max_retries} retries")

    @staticmethod
    def _retry_after(r: httpx.Response, attempt: int) -> float:
        reset = r.headers.get("X-RateLimit-Reset")
        if r.status_code == 429 and reset and reset.isdigit():
            return max(0.5, min(int(reset) - time.time() + 0.5, 60))
        return min(2 ** attempt, 30)

    def _write(self, method: str, path: str, *, params: dict[str, Any] | None = None,
               body: dict[str, Any] | None = None) -> Any:
        """One write request. Retried only on 429 (the request was refused, so nothing happened).
        Any other failure is raised: retrying an order blindly could place it twice, so the caller
        checks by client_order_id instead."""
        if not self.allow_orders:
            raise AlpacaError("this client is read-only (allow_orders=False)")
        for attempt in range(self.max_retries + 1):
            self.limiter.wait()
            r = self.trading.request(method, path, params=params, json=body)
            self.calls += 1
            if r.status_code == 429 and attempt < self.max_retries:
                self.sleep(self._retry_after(r, attempt))
                continue
            if r.status_code >= 400:
                raise AlpacaError(f"{method} {path} -> {r.status_code}: {r.text[:300]}")
            return r.json() if r.content else None
        raise AlpacaError(f"{method} {path}: rate-limited {self.max_retries} times")

    def submit_order(self, *, symbol: str, side: str, client_order_id: str, notional: str | None = None,
                     qty: str | None = None) -> dict[str, Any]:
        if (notional is None) == (qty is None):
            raise ValueError("give exactly one of notional or qty")
        body: dict[str, Any] = {"symbol": symbol, "side": side, "type": "market", "time_in_force": "day",
                                "client_order_id": client_order_id[:128]}
        body["notional" if notional is not None else "qty"] = notional if notional is not None else qty
        return self._write("POST", "/v2/orders", body=body)

    def close_position(self, symbol: str) -> dict[str, Any]:
        return self._write("DELETE", f"/v2/positions/{symbol}")

    # ---------------------------------------------------------------- trading API (read-only)

    def clock(self) -> dict[str, Any]:
        """Legacy clock: {timestamp, is_open, next_open, next_close}."""
        return self._get(self.trading, "/v2/clock")

    def positions(self) -> list[dict[str, Any]]:
        return self._get(self.trading, "/v2/positions")

    def orders(self, status: str = "all", after: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"status": status, "limit": limit, "direction": "desc"}
        if after:
            params["after"] = after
        return self._get(self.trading, "/v2/orders", params)

    def account(self) -> dict[str, Any]:
        return self._get(self.trading, "/v2/account")

    def assets(self, status: str | None = None, asset_class: str = "us_equity") -> list[dict[str, Any]]:
        params: dict[str, Any] = {"asset_class": asset_class}
        if status:
            params["status"] = status
        return self._get(self.trading, "/v2/assets", params)

    def calendar(self, start: str, end: str) -> list[dict[str, Any]]:
        return self._get(self.trading, "/v2/calendar", {"start": start, "end": end})

    # ---------------------------------------------------------------- market data

    def bars(self, symbols: list[str], timeframe: str, start: str, end: str, *, feed: str = "iex",
             adjustment: str = "all") -> Iterator[tuple[str, dict[str, Any]]]:
        """Yield (symbol, bar) for every bar, following next_page_token to the end."""
        params: dict[str, Any] = {"symbols": ",".join(symbols), "timeframe": timeframe, "start": start, "end": end,
                                  "limit": MAX_BARS_PER_PAGE, "adjustment": adjustment, "feed": feed, "sort": "asc"}
        while True:
            page = self._get(self.data, "/v2/stocks/bars", params)
            for sym, rows in (page.get("bars") or {}).items():
                for bar in rows:
                    yield sym, bar
            token = page.get("next_page_token")
            if not token:
                return
            params["page_token"] = token


def client_from_settings(settings, *, allow_orders: bool = False) -> AlpacaClient:
    key_id, secret = settings.credentials()
    return AlpacaClient(settings.trading_url, settings.alpaca_data_url, key_id, secret,
                        requests_per_minute=settings.data_requests_per_minute, allow_orders=allow_orders)
