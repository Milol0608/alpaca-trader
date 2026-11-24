"""Download Alpaca bars to Parquet, one file per timeframe and calendar year.

data/bars/{timeframe}/{year}.parquet, columns:
  symbol, t (UTC), open, high, low, close, volume, trades, vwap
Prices are adjusted for splits and dividends (`adjustment=all`), so returns across corporate
actions are right. Past years are written once; the current year is refetched on each run.
Each request batch is saved as a part file first, so an interrupted year resumes where it stopped.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import polars as pl

from trader.alpaca.client import AlpacaClient

log = logging.getLogger(__name__)

MAJOR_EXCHANGES = {"NYSE", "NASDAQ", "ARCA", "NYSEARCA", "AMEX", "BATS"}
SCHEMA = {"symbol": pl.Utf8, "t": pl.Datetime("us", "UTC"), "open": pl.Float64, "high": pl.Float64,
          "low": pl.Float64, "close": pl.Float64, "volume": pl.Float64, "trades": pl.Int64, "vwap": pl.Float64}
# Symbols per request: a page holds 10,000 bars across all symbols, so fewer symbols per
# request for finer timeframes keeps each request to a handful of pages.
DEFAULT_CHUNK = {"1Day": 200, "1Hour": 20}


def fetch_assets(client: AlpacaClient, path: Path) -> pl.DataFrame:
    """Active AND inactive US equities on major exchanges. Inactive ones matter: leaving out
    delisted stocks would make every backtest look better than history was (survivorship bias)."""
    rows = []
    for status in ("active", "inactive"):
        for a in client.assets(status=status):
            if a.get("exchange") in MAJOR_EXCHANGES:
                rows.append({"symbol": a["symbol"], "name": a.get("name") or "", "exchange": a["exchange"],
                             "status": a["status"], "tradable": bool(a.get("tradable")),
                             "fractionable": bool(a.get("fractionable"))})
    df = pl.DataFrame(rows, schema={"symbol": pl.Utf8, "name": pl.Utf8, "exchange": pl.Utf8, "status": pl.Utf8,
                                    "tradable": pl.Boolean, "fractionable": pl.Boolean})
    df = df.unique("symbol", keep="first").sort("symbol")  # active listed first, so it wins a reused ticker
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path)
    return df


def _rows(pairs) -> pl.DataFrame:
    recs = [{"symbol": s, "t": b["t"], "open": b["o"], "high": b["h"], "low": b["l"], "close": b["c"],
             "volume": float(b["v"]), "trades": int(b.get("n") or 0), "vwap": b.get("vw")} for s, b in pairs]
    if not recs:
        return pl.DataFrame(schema=SCHEMA)
    df = pl.DataFrame(recs)
    return df.with_columns(pl.col("t").str.to_datetime(time_unit="us", time_zone="UTC")).select(
        [pl.col(c).cast(t) for c, t in SCHEMA.items()])


def download_year(client: AlpacaClient, symbols: list[str], timeframe: str, year: int, out_dir: Path,
                  *, start: date | None = None, end: date | None = None, feed: str = "iex",
                  chunk: int | None = None) -> Path:
    chunk = chunk or DEFAULT_CHUNK.get(timeframe, 20)
    tf_dir = out_dir / timeframe
    parts = tf_dir / f"{year}.parts"
    parts.mkdir(parents=True, exist_ok=True)
    s = max(start or date(year, 1, 1), date(year, 1, 1)).isoformat()
    e = min(end or date(year, 12, 31), date(year, 12, 31)).isoformat()
    batches = [symbols[i:i + chunk] for i in range(0, len(symbols), chunk)]
    for i, batch in enumerate(batches):
        part = parts / f"{i:05d}.parquet"
        if part.exists():
            continue
        _rows(client.bars(batch, timeframe, s, e, feed=feed)).write_parquet(part)
        if (i + 1) % 10 == 0 or i + 1 == len(batches):
            log.info("%s %d: %d/%d batches, %d calls so far", timeframe, year, i + 1, len(batches), client.calls)
    frames = [pl.read_parquet(p) for p in sorted(parts.glob("*.parquet"))]
    out = tf_dir / f"{year}.parquet"
    df = pl.concat(frames) if frames else pl.DataFrame(schema=SCHEMA)
    df.unique(["symbol", "t"], keep="last").sort(["symbol", "t"]).write_parquet(out)
    for p in parts.glob("*.parquet"):
        p.unlink()
    parts.rmdir()
    return out


def download(client: AlpacaClient, symbols: list[str], timeframe: str, start: date, end: date, out_dir: Path,
             *, feed: str = "iex", chunk: int | None = None, today: date | None = None) -> list[Path]:
    today = today or date.today()
    written = []
    for year in range(start.year, end.year + 1):
        out = out_dir / timeframe / f"{year}.parquet"
        if out.exists() and year < today.year:
            log.info("%s %d: already downloaded", timeframe, year)
            written.append(out)
            continue
        written.append(download_year(client, symbols, timeframe, year, out_dir, start=start, end=end,
                                     feed=feed, chunk=chunk))
    return written


def load_bars(out_dir: Path, timeframe: str) -> pl.LazyFrame:
    return pl.scan_parquet(str(out_dir / timeframe / "*.parquet"))
