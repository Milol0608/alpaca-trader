"""C1 (docs/RESEARCH.md): BTC + ETH, each held only above its 140-day SMA; weekly; spot, long-only.

  uv run python -m trader.backtest.crypto_trend

Data: Coinbase Exchange public daily candles (no key), cached to data/crypto/{product}.parquet.
Decision at Monday's close (UTC day), trade at Tuesday's open. Equal weight per coin (half each for BTC + ETH).
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import numpy as np
import polars as pl

from trader.data.bars import load_bars

OUT = Path("data/crypto")
START, HELD_OUT, SMA = date(2017, 3, 1), date(2023, 1, 1), 140
URL = "https://api.exchange.coinbase.com/products/{p}/candles"


def candles(product: str) -> pl.DataFrame:
    path = OUT / f"{product}.parquet"
    if path.exists():
        return pl.read_parquet(path)
    OUT.mkdir(parents=True, exist_ok=True)
    rows, t = [], datetime(2016, 6, 1, tzinfo=timezone.utc)
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    with httpx.Client(timeout=30, headers={"User-Agent": "alpaca-trader research"}) as http:
        while t < end:
            t2 = min(t + timedelta(days=299), end)
            r = http.get(URL.format(p=product), params={"granularity": 86400, "start": t.isoformat(), "end": t2.isoformat()})
            r.raise_for_status()
            rows += r.json()  # [time, low, high, open, close, volume]
            t = t2
            time.sleep(0.4)
    df = (pl.DataFrame(rows, schema=["t", "low", "high", "open", "close", "volume"], orient="row")
          .with_columns(pl.from_epoch("t").dt.date().alias("day")).unique("day").sort("day")
          .filter(pl.col("day") < end.date()).select("day", "open", "close"))
    df.write_parquet(path)
    return df


def simulate(px: dict[str, pl.DataFrame], bps: float, trend: bool) -> tuple[list[date], np.ndarray]:
    days = sorted(set.intersection(*[set(d["day"].to_list()) for d in px.values()]))
    days = [d for d in days if d >= START - timedelta(days=SMA + 10)]
    o = {k: dict(zip(v["day"], v["open"])) for k, v in px.items()}
    c = {k: dict(zip(v["day"], v["close"])) for k, v in px.items()}
    closes = {k: np.array([c[k][d] for d in days]) for k in px}
    units = {k: 0.0 for k in px}
    cash, eq, out_days, pending = 200.0, [], [], None
    for i, d in enumerate(days):
        if pending is not None and d >= START:  # trade at this day's open
            value = cash + sum(units[k] * o[k][d] for k in px)
            for k in px:
                target = value / len(px) * pending[k]
                delta = target - units[k] * o[k][d]
                cash -= delta + abs(delta) * bps / 1e4
                units[k] += delta / o[k][d]
            pending = None
        if d.weekday() == 0 and i >= SMA:  # Monday close: decide
            pending = {k: (1.0 if (closes[k][i] > closes[k][i - SMA + 1:i + 1].mean() or not trend) else 0.0)
                       for k in px}
        if d >= START:
            out_days.append(d)
            eq.append(cash + sum(units[k] * c[k][d] for k in px))
    return out_days, np.array(eq)


def stats(days: list[date], eq: np.ndarray, start: date, per_year: int) -> dict:
    i = next(j for j, d in enumerate(days) if d >= start)
    e = eq[i:]
    r = np.diff(e) / e[:-1]
    years = (days[-1] - days[i]).days / 365.25
    dd = 1 - e / np.maximum.accumulate(e)
    return {"final": 200 * e[-1] / e[0], "cagr": (e[-1] / e[0]) ** (1 / years) - 1,
            "sharpe": r.mean() / r.std() * np.sqrt(per_year), "max_dd": dd.max()}


def main() -> None:
    px = {"BTC": candles("BTC-USD"), "ETH": candles("ETH-USD")}
    for k, v in px.items():
        print(f"{k}: {v.height} days {v['day'].min()} .. {v['day'].max()}")
    spy = (load_bars(Path("data/bars"), "1Day").filter(pl.col("symbol") == "SPY").collect()
           .with_columns(pl.col("t").dt.convert_time_zone("America/New_York").dt.date().alias("day")).sort("day"))
    sd = [d for d in spy["day"].to_list() if d >= START]
    se = spy.filter(pl.col("day") >= START)["close"].to_numpy() / spy.filter(pl.col("day") >= START)["close"][0] * 200
    res = {"SPY buy-and-hold": (sd, se, 252),
           "BTC buy-and-hold": (*simulate({"BTC": px["BTC"]}, 0, trend=False), 365)}
    for bps in (25, 50):
        res[f"C1 trend at {bps} bps"] = (*simulate(px, bps, trend=True), 365)
    res["BTC+ETH 50/50 no filter, 25bps"] = (*simulate(px, 25, trend=False), 365)
    for label, a in (("FULL 2017-03 .. now", START), ("HELD-OUT 2023-01 .. now", HELD_OUT)):
        print(f"\n{label}\n{'strategy':<32}{'$200 ->':>9}{'CAGR':>8}{'Sharpe':>8}{'maxDD':>7}")
        for k, (d, e, n) in res.items():
            x = stats(d, e, a, n)
            print(f"{k:<32}{x['final']:>9.0f}{x['cagr']:>8.1%}{x['sharpe']:>8.2f}{x['max_dd']:>7.0%}")


if __name__ == "__main__":
    main()
