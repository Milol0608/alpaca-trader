"""D2c (docs/RESEARCH.md): daily English-Wikipedia page views for every stock that was ever in the monthly top-40
momentum pool, as a news/attention signal while GDELT blocks us. Title = top search hit for the cleaned SEC company
name. Resumable; files in data/news/wiki/{SYMBOL}.json as {"query", "title", "count": [[yyyymmdd, views], ...]}.

  uv run python -m trader.backtest.news_wiki
"""

from __future__ import annotations

import json
import time
from datetime import date, timedelta
from urllib.parse import quote

import httpx
import polars as pl

from trader.backtest.engine import build_context
from trader.backtest.news_gdelt import clean
from trader.backtest.r7 import START, candidates
from trader.config import get_settings
from trader.data.bars import load_bars
from trader.data.universe import load_etfs

UA = "alpaca-trader-research/0.1 (https://github.com/Milol0608/alpaca-trader)"  # Wikimedia requires a contact
SEARCH = "https://en.wikipedia.org/w/api.php"
VIEWS = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{}/daily/{}/{}"


def main() -> None:
    s = get_settings()
    out_dir = s.data_dir / "news" / "wiki"
    out_dir.mkdir(parents=True, exist_ok=True)
    universe = pl.read_parquet(s.data_dir / "universe.parquet")
    daily = load_bars(s.data_dir / "bars", "1Day").select("symbol", "t", "open", "close", "volume").collect()
    ctx = build_context(daily, universe, START - timedelta(days=400), date.today())
    syms = candidates(ctx, set(load_etfs(s.etfs_file)))
    tick = json.loads((s.data_dir / "edgar" / "company_tickers.json").read_text())
    name = {v["ticker"].replace("-", ".").upper(): clean(v["title"]) for v in tick.values()}
    todo = sorted(x for x in syms if name.get(x.replace("-", ".").upper()) and not (out_dir / f"{x}.json").exists())
    print(f"{len(syms)} pool symbols, {len(todo)} to fetch", flush=True)
    end = (date.today() - timedelta(1)).strftime("%Y%m%d")
    with httpx.Client(timeout=60, headers={"User-Agent": UA}) as http:
        def get(url: str, **params) -> httpx.Response | None:
            for attempt in range(5):
                time.sleep(0.25)
                try:
                    r = http.get(url, params=params or None)
                except httpx.TransportError:
                    time.sleep(5 * (attempt + 1))
                    continue
                if r.status_code == 429 or r.status_code >= 500:
                    time.sleep(10 * (attempt + 1))
                    continue
                return r
            return None

        miss = 0
        for i, sym in enumerate(todo, 1):
            q = name[sym.replace("-", ".").upper()]
            r = get(SEARCH, action="query", list="search", srsearch=q, srlimit=1, format="json")
            hits = (r.json().get("query", {}).get("search") or []) if r is not None and r.status_code == 200 else None
            if hits is None:
                print(f"  skipped {sym}: search failed", flush=True)  # rerun picks it up
                continue
            title, count = (hits[0]["title"] if hits else None), []
            if title:
                r = get(VIEWS.format(quote(title.replace(" ", "_"), safe=""), "20170101", end))
                if r is None or r.status_code not in (200, 404):
                    print(f"  skipped {sym}: views failed", flush=True)
                    continue
                if r.status_code == 200:
                    count = [[it["timestamp"][:8], it["views"]] for it in r.json().get("items", [])]
            miss += not count
            (out_dir / f"{sym}.json").write_text(json.dumps({"query": q, "title": title, "count": count}))
            if i % 50 == 0:
                print(f"  {i}/{len(todo)} ({miss} with no views)", flush=True)
    print(f"done; {miss} with no views", flush=True)


if __name__ == "__main__":
    main()
