"""Daily paper-trading run (placeholder until order placement lands this session): checks the account."""

from __future__ import annotations

from trader.alpaca.client import client_from_settings
from trader.config import Mode, get_settings


def main() -> None:
    s = get_settings()
    assert s.mode is Mode.PAPER, "trader.paper only runs in paper mode"
    with client_from_settings(s) as c:
        a = c.account()
    print(f"paper account {a.get('status')}: equity ${a.get('equity')}, cash ${a.get('cash')}")


if __name__ == "__main__":
    main()
