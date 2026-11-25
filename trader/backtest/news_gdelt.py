"""D2 news (docs/RESEARCH.md): daily GDELT news tone and article counts for every stock that was ever in the monthly
top-40 momentum pool. One full-span query per series (2017 to now, daily resolution), one request every 8 s
(GDELT asks for at most one per 5 s). Resumable; files in data/news/gdelt/{SYMBOL}.json.

  uv run python -m trader.backtest.news_gdelt
"""

from __future__ import annotations

import json
import re
import time
from datetime import date, timedelta

import httpx
import polars as pl

from trader.backtest.engine import build_context
from trader.backtest.r7 import START, candidates
from trader.config import get_settings
from trader.data.bars import load_bars
from trader.data.universe import load_etfs

URL = "https://api.gdeltproject.org/api/v2/doc/doc"
SUFFIX = re.compile(r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|holdings?|group|class [a-z]|"
                    r"the|n\.?v|s\.?a|l\.?p|llc|de|md|nv|tr|trust|international|intl)\b\.?", re.I)


def clean(title: str) -> str:
    t = re.sub(r"/[A-Z]{2,}/?", " ", title)  # "/DE/" state tags
    t = SUFFIX.sub(" ", t.replace(",", " ").replace("&", " and "))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s'.-]", " ", t)).strip(" .-")


def main() -> None:
    s = get_settings()
    out_dir = s.data_dir / "news" / "gdelt"
    out_dir.mkdir(parents=True, exist_ok=True)
    universe = pl.read_parquet(s.data_dir / "universe.parquet")
    daily = load_bars(s.data_dir / "bars", "1Day").select("symbol", "t", "open", "close", "volume").collect()
    ctx = build_context(daily, universe, START - timedelta(days=400), date.today())
    syms = candidates(ctx, set(load_etfs(s.etfs_file)))
    tick = json.loads((s.data_dir / "edgar" / "company_tickers.json").read_text())
    name = {v["ticker"].replace("-", ".").upper(): clean(v["title"]) for v in tick.values()}
    todo = sorted(x for x in syms if name.get(x.replace("-", ".").upper()) and not (out_dir / f"{x}.json").exists())
    print(f"{len(syms)} pool symbols, {len(todo)} to fetch ({len(syms) - len(todo)} done or unnamed)", flush=True)
    last = [0.0]
    with httpx.Client(timeout=90) as http:
        def get(q: str, mode: str) -> list | None:
            for attempt in range(8):
                wait = last[0] + 8.0 - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                last[0] = time.monotonic()
                try:
                    r = http.get(URL, params={"query": f'"{q}" sourcelang:english', "mode": mode, "format": "json",
                                              "startdatetime": "20170101000000", "timelinesmooth": 0,
                                              "enddatetime": date.today().strftime("%Y%m%d000000")})
                except httpx.TransportError:
                    time.sleep(10 * (attempt + 1))
                    continue
                if r.status_code == 429 or r.status_code >= 500:  # GDELT keeps refusing while retries come fast
                    print(f"  {r.status_code} on {q!r}, cooling down", flush=True)
                    time.sleep(90 * (attempt + 1))
                    continue
                try:
                    tl = r.json().get("timeline") or []
                except ValueError:  # GDELT answers some bad queries with plain text
                    return None
                return [[p["date"][:8], p["value"]] for p in (tl[0]["data"] if tl else [])]
            raise RuntimeError(f"GDELT refused {q!r} {mode} 8 times")

        for i, sym in enumerate(todo, 1):
            q = name[sym.replace("-", ".").upper()]
            try:
                tone, vol = get(q, "timelinetone"), get(q, "timelinevolraw")
            except RuntimeError as e:  # leave it for a rerun; never store a gap as "no news"
                print(f"  skipped {sym}: {e}", flush=True)
                continue
            (out_dir / f"{sym}.json").write_text(json.dumps({"query": q, "tone": tone, "count": vol}))
            if i % 25 == 0:
                print(f"  {i}/{len(todo)}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
