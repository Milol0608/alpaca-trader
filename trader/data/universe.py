"""Point-in-time universe: which symbols a strategy may hold in each month.

For each month, using ONLY daily bars dated before that month's first day:
  - stocks: the `size` most-traded by median daily dollar volume (close x volume) over the last
    `lookback` trading days, priced at least `min_price`, with at least 80% of those days present;
  - ETFs: the fixed list in data/etfs.json, whenever they have data.
Funds and leveraged/inverse products that rank high on volume are kept out of the stock list by a
name filter (Alpaca's asset list has no ETF flag). *Assumption:* names reliably identify funds; the
excluded names are logged so this can be checked.

Volumes come from the IEX feed on the free plan, a fraction of the whole market's. Ranking only
needs relative volume, so that's fine for choosing which stocks count as large and liquid.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import polars as pl

FUND_NAME = re.compile(
    r"\b(ETF|ETN|ETP|Exchange[- ]Traded|Fund|ProShares|Direxion|iShares|SPDR|Vanguard|WisdomTree|VanEck|"
    r"Grayscale|GraniteShares|Leveraged|Inverse|UltraPro|UltraShort|[23]X|Trust,? Series \d+)\b", re.IGNORECASE)
# Deliberately not "Trust", "Shares", "Index" or a fund company's own name: real companies use them
# ("Northern Trust Corporation", "... Common Shares", "The Charles Schwab Corporation").


def load_etfs(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return sorted({s for k, v in data.items() if not k.startswith("_") for s in v})


def is_fund(name: str) -> bool:
    return bool(FUND_NAME.search(name or ""))


def month_starts(first: date, last: date) -> list[date]:
    out, y, m = [], first.year, first.month
    while date(y, m, 1) <= last:
        out.append(date(y, m, 1))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def build_universe(daily: pl.DataFrame, assets: pl.DataFrame, etfs: list[str], *, size: int = 500,
                   min_price: float = 5.0, lookback: int = 60) -> pl.DataFrame:
    """daily: symbol, t, close, volume. Returns month, symbol, kind (stock|etf), rank, dollar_volume."""
    funds = set(assets.filter(pl.col("name").map_elements(is_fund, return_dtype=pl.Boolean))["symbol"].to_list())
    funds -= set(etfs)
    d = (daily.select("symbol", pl.col("t").dt.date().alias("day"), "close", "volume")
         .with_columns((pl.col("close") * pl.col("volume")).alias("dv")).sort(["symbol", "day"]))
    days = d["day"]
    last = days.max()
    nxt = date(last.year + (last.month == 12), last.month % 12 + 1, 1)
    # From the second month (the first has no history before it) through the month after the
    # data ends, which is the one a live run trades next.
    months = month_starts(days.min(), nxt)[1:]
    out = []
    for m in months:
        hist = d.filter(pl.col("day") < m)  # strictly before the month: nothing it couldn't have known
        recent = hist.group_by("symbol").tail(lookback)
        stats = recent.group_by("symbol").agg(
            pl.col("dv").median().alias("dollar_volume"),
            pl.col("close").last().alias("last_close"),
            pl.len().alias("n"),
        )
        ok = stats.filter((pl.col("n") >= int(0.8 * lookback)) & (pl.col("last_close") >= min_price))
        stocks = (ok.filter(~pl.col("symbol").is_in(list(funds | set(etfs))))
                  .sort("dollar_volume", descending=True).head(size)
                  .with_columns(pl.lit("stock").alias("kind")))
        etf_rows = ok.filter(pl.col("symbol").is_in(etfs)).with_columns(pl.lit("etf").alias("kind"))
        both = pl.concat([stocks, etf_rows]).with_columns(
            pl.col("dollar_volume").rank("ordinal", descending=True).over("kind").cast(pl.Int32).alias("rank"),
            pl.lit(m).alias("month"))
        out.append(both.select("month", "symbol", "kind", "rank", "dollar_volume"))
    if not out:
        return pl.DataFrame(schema={"month": pl.Date, "symbol": pl.Utf8, "kind": pl.Utf8, "rank": pl.Int32,
                                    "dollar_volume": pl.Float64})
    return pl.concat(out).sort(["month", "kind", "rank"])
