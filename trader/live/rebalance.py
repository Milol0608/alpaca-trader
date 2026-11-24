"""Turn target weights into paper orders, safely.

`plan` is pure (no network): account equity and cash, current positions and prices, and target
weights in; a list of orders out. `execute` sends them, sells first, then buys with the cash that's
actually there.

Safety rules (each one tested):
  - paper only: `execute` refuses unless the client points at the paper host;
  - never spend more cash than the account has, and keep a small buffer (`cash_buffer`);
  - no single order above `max_order_pct` of equity (catches a bug that would put it all in one stock);
  - orders under $1 are skipped (Alpaca's fractional minimum);
  - idempotent: every order gets client_order_id "<tag>-<date>-<symbol>-<side>", and a run that finds
    any of today's tagged orders already placed does nothing, so a double trigger can't trade twice.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from datetime import date

from trader.alpaca.client import AlpacaClient, AlpacaError

PAPER_HOST = "paper-api.alpaca.markets"


@dataclass
class Order:
    symbol: str
    side: str            # buy | sell
    notional: float | None = None
    qty: float | None = None
    close_all: bool = False  # sell the whole position (DELETE /v2/positions/{symbol})
    reason: str = ""


@dataclass
class Plan:
    equity: float
    cash: float
    targets: dict[str, float]          # symbol -> dollars
    sells: list[Order] = field(default_factory=list)
    buys: list[Order] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def plan(equity: float, cash: float, positions: dict[str, tuple[float, float]], weights: dict[str, float], *,
         min_order: float = 1.0, cash_buffer: float = 0.02, max_order_pct: float = 0.15,
         tolerance: float = 0.05) -> Plan:
    """positions: symbol -> (qty, price). weights: symbol -> fraction of equity (long-only, sum <= 1).

    A holding within `tolerance` (5%) of its target dollar value is left alone, so tiny price drifts
    don't cause trades. Buys are planned against cash available after sells, minus the buffer.
    """
    w = {s: x for s, x in weights.items() if x > 0}
    tot = sum(w.values())
    if tot > 1:
        w = {s: x / tot for s, x in w.items()}
    investable = equity * (1 - cash_buffer)
    targets = {s: round(x * investable, 2) for s, x in w.items()}
    p = Plan(equity, cash, targets)
    freed = 0.0
    for sym, (qty, price) in sorted(positions.items()):
        value = qty * price
        want = targets.get(sym, 0.0)
        if want == 0.0:
            p.sells.append(Order(sym, "sell", close_all=True, reason="no longer in target"))
            freed += value
        elif value > want * (1 + tolerance) and value - want >= min_order:
            q = math.floor((value - want) / price * 1e6) / 1e6  # round down: never sell more than intended
            if q > 0:
                p.sells.append(Order(sym, "sell", qty=q, reason=f"trim ${value:.2f} -> ${want:.2f}"))
                freed += q * price
    spendable = max(0.0, cash + freed - equity * cash_buffer)
    for sym in sorted(targets, key=lambda s: -targets[s]):
        qty, price = positions.get(sym, (0.0, 0.0))
        have = qty * price
        gap = targets[sym] - have
        if have > 0 and abs(gap) <= targets[sym] * tolerance:
            continue
        if gap < min_order:
            continue
        amount = math.floor(min(gap, spendable, equity * max_order_pct) * 100) / 100
        if amount < min_order:
            p.skipped.append(f"{sym}: wanted ${gap:.2f}, only ${spendable:.2f} cash left")
            continue
        p.buys.append(Order(sym, "buy", notional=amount, reason=f"${have:.2f} -> ${targets[sym]:.2f}"))
        spendable -= amount
    return p


def order_id(tag: str, day: date, symbol: str, side: str) -> str:
    return f"{tag}-{day:%Y%m%d}-{symbol}-{side}"


def already_ran_today(client: AlpacaClient, tag: str, day: date) -> bool:
    prefix = f"{tag}-{day:%Y%m%d}-"
    return any((o.get("client_order_id") or "").startswith(prefix) for o in client.orders(status="all", limit=500))


def wait_for_fills(client: AlpacaClient, ids: set[str], timeout: float = 120, sleep=time.sleep) -> set[str]:
    """Wait until none of our orders are still open. Returns the ids still open at the timeout."""
    deadline = time.monotonic() + timeout
    while True:
        open_ids = {o.get("client_order_id") for o in client.orders(status="open", limit=500)} & ids
        if not open_ids or time.monotonic() > deadline:
            return open_ids
        sleep(3)


def execute(client: AlpacaClient, p: Plan, *, tag: str, day: date, dry_run: bool, log=print,
            sleep=time.sleep) -> list[dict]:
    if PAPER_HOST not in str(client.trading.base_url):
        raise AlpacaError(f"refusing to trade: {client.trading.base_url} is not the paper host")
    for o in p.buys:
        if o.notional is not None and o.notional > p.equity * 0.15 + 0.01:
            raise AlpacaError(f"refusing: {o.symbol} order ${o.notional} exceeds 15% of equity")
    if dry_run:
        for o in p.sells + p.buys:
            log(f"  DRY RUN {o.side:<4} {o.symbol:<6} {('all' if o.close_all else o.qty or f'${o.notional:.2f}')!s:<10} {o.reason}")
        return []
    sent: list[dict] = []
    sell_ids = set()
    for o in p.sells:
        cid = order_id(tag, day, o.symbol, "sell")
        r = client.close_position(o.symbol) if o.close_all else client.submit_order(
            symbol=o.symbol, side="sell", qty=f"{o.qty:.6f}", client_order_id=cid)
        sell_ids.add(r.get("client_order_id") or cid)
        sent.append(r)
        log(f"  sell {o.symbol:<6} {'all' if o.close_all else o.qty}  {o.reason}")
    if sell_ids:
        still_open = wait_for_fills(client, sell_ids, sleep=sleep)
        if still_open:
            log(f"  {len(still_open)} sells still open after waiting; buys use only the cash already there")
    cash = float(client.account().get("cash") or 0)
    spendable = max(0.0, cash - p.equity * 0.02)
    for o in p.buys:
        amount = math.floor(min(o.notional or 0, spendable) * 100) / 100
        if amount < 1.0:
            log(f"  skip buy {o.symbol}: only ${spendable:.2f} cash left")
            continue
        r = client.submit_order(symbol=o.symbol, side="buy", notional=f"{amount:.2f}",
                                client_order_id=order_id(tag, day, o.symbol, "buy"))
        spendable -= amount
        sent.append(r)
        log(f"  buy  {o.symbol:<6} ${amount:.2f}  {o.reason}")
    return sent
