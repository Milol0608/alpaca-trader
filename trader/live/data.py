"""Fresh market data for a live run, fetched straight from Alpaca (the runner has no stored history).

Two pulls, both ending YESTERDAY (complete daily bars; the free plan withholds only the latest 15 min):
  1. every listed stock, last ~130 calendar days -> this month's point-in-time universe
     (the same build_universe the backtest uses);
  2. universe members only, last ~400 calendar days -> enough history for 12-month momentum and
     every other baseline.
About 250-350 API calls, 2-3 minutes at the free plan's rate limit.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import polars as pl

from trader.alpaca.client import AlpacaClient
from trader.data.bars import DEFAULT_CHUNK, MAJOR_EXCHANGES, TICKER, _fetch_batch
from trader.data.universe import build_universe

log = logging.getLogger(__name__)


def active_assets(client: AlpacaClient) -> pl.DataFrame:
    rows = [{"symbol": a["symbol"], "name": a.get("name") or "", "fractionable": bool(a.get("fractionable"))}
            for a in client.assets(status="active")
            if a.get("exchange") in MAJOR_EXCHANGES and TICKER.match(a["symbol"]) and a.get("tradable")]
    return pl.DataFrame(rows, schema={"symbol": pl.Utf8, "name": pl.Utf8, "fractionable": pl.Boolean})


def fetch_daily(client: AlpacaClient, symbols: list[str], start: date, end: date, feed: str) -> pl.DataFrame:
    chunk = DEFAULT_CHUNK["1Day"]
    frames = [_fetch_batch(client, symbols[i:i + chunk], "1Day", start.isoformat(), end.isoformat(), feed)
              for i in range(0, len(symbols), chunk)]
    return pl.concat(frames).unique(["symbol", "t"]).sort(["symbol", "t"]) if frames else pl.DataFrame()


def live_inputs(client: AlpacaClient, today: date, etfs: list[str], *, feed: str = "sip", size: int = 500,
                min_price: float = 5.0, lookback: int = 60, history_days: int = 400,
                universe_days: int = 130) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Returns (daily bars for universe members, universe table, active assets)."""
    end = today - timedelta(days=1)
    assets = active_assets(client)
    all_syms = sorted(set(assets["symbol"].to_list()) | set(etfs))
    recent = fetch_daily(client, all_syms, today - timedelta(days=universe_days), end, feed)
    universe = build_universe(recent.select("symbol", "t", "close", "volume"), assets, etfs, size=size,
                              min_price=min_price, lookback=lookback)
    members = sorted(set(universe["symbol"].to_list()))
    log.info("universe: %d symbols this period (from %d listed)", len(members), len(all_syms))
    history = fetch_daily(client, members, today - timedelta(days=history_days), end, feed)
    return history, universe, assets
