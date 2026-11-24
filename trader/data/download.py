"""Download market history for backtests. Needs paper API keys in .env (data access is free).

  uv run python -m trader.data.download assets                 # US equity list, incl. delisted
  uv run python -m trader.data.download daily --start 2016-01-01
  uv run python -m trader.data.download universe               # monthly point-in-time universe
  uv run python -m trader.data.download intraday --timeframe 1Hour --start 2019-01-01

Daily bars cover every listed stock (needed to rank the universe without hindsight). Intraday
bars cover only symbols that were ever in the universe, which keeps the download manageable.
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta

import polars as pl

from trader.alpaca.client import client_from_settings
from trader.config import get_settings
from trader.data.bars import download, fetch_assets, load_bars
from trader.data.universe import build_universe, is_fund, load_etfs

log = logging.getLogger("download")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["assets", "daily", "universe", "intraday"])
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--end", default=(date.today() - timedelta(days=1)).isoformat())
    ap.add_argument("--timeframe", default="1Hour")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    s = get_settings()
    d = s.data_dir
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)

    if args.what == "universe":
        assets = pl.read_parquet(d / "assets.parquet")
        daily = load_bars(d / "bars", "1Day").select("symbol", "t", "close", "volume").collect()
        uni = build_universe(daily, assets, load_etfs(s.etfs_file), size=s.universe_size,
                             min_price=s.universe_min_price, lookback=s.universe_lookback_days)
        uni.write_parquet(d / "universe.parquet")
        funds = assets.filter(pl.col("name").map_elements(is_fund, return_dtype=pl.Boolean))
        funds.select("symbol", "name").write_csv(d / "excluded_as_funds.csv")
        log.info("universe: %d months, %d distinct symbols; %d names excluded as funds (see %s)",
                 uni["month"].n_unique(), uni["symbol"].n_unique(), funds.height, d / "excluded_as_funds.csv")
        return

    with client_from_settings(s) as client:
        if args.what == "assets":
            a = fetch_assets(client, d / "assets.parquet")
            log.info("assets: %d (%d active)", a.height, a.filter(pl.col("status") == "active").height)
        elif args.what == "daily":
            symbols = pl.read_parquet(d / "assets.parquet")["symbol"].to_list()
            download(client, symbols, "1Day", start, end, d / "bars", feed=s.data_feed)
        else:
            symbols = sorted(pl.read_parquet(d / "universe.parquet")["symbol"].unique().to_list())
            download(client, symbols, args.timeframe, start, end, d / "bars", feed=s.data_feed)
        log.info("done: %d API calls", client.calls)


if __name__ == "__main__":
    main()
