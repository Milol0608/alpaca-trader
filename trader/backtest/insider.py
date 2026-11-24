"""R4 (docs/RESEARCH.md): insider open-market purchases, after costs, vs SPY and momentum.

  uv run python -m trader.backtest.insider

Signals are dated by FILING date. The engine decides at the close of each day using filings dated
on or before that day and trades at the next open, so a filing is never used before it was public.
R4a: officer/director purchase >= $10k. R4b: >= 2 distinct insiders within 5 calendar days.
Tradable as of the day before the filing: close >= $5 and 60-day median dollar volume >= $1M.
Hold 21 trading days, equal weight, at most 20 names (largest purchases first), 5 bps per side.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import polars as pl

from trader.backtest import strategies as st
from trader.backtest.engine import Window, build_context, run
from trader.backtest.scorecard import stats, window, yearly
from trader.data.bars import load_bars
from trader.data.universe import load_etfs

START, HELD_OUT, HOLD, MAX_NAMES = date(2017, 3, 1), date(2023, 1, 1), 21, 20


def signals(daily: pl.DataFrame) -> dict[str, pl.DataFrame]:
    p = pl.read_parquet("data/insiders/purchases.parquet").filter(
        pl.col("relationship").str.contains("(?i)director|officer"), pl.col("value") >= 10_000,
        pl.col("filed").is_not_null())
    # tradability on the trading day BEFORE the filing date, from bars only
    d = (daily.with_columns(pl.col("t").dt.convert_time_zone("America/New_York").dt.date().alias("day"))
         .sort(["symbol", "day"])
         .with_columns((pl.col("close") * pl.col("volume")).rolling_median(60).over("symbol").alias("mdv"))
         .select("symbol", "day", "close", "mdv"))
    p = p.sort("filed").join_asof(d.sort("day").rename({"day": "bar_day"}), left_on="filed", right_on="bar_day",
                                  by="symbol", strategy="backward", allow_exact_matches=False)
    ok = p.filter((pl.col("close") >= 5) & (pl.col("mdv") >= 1_000_000))
    a = ok.group_by("symbol", "filed").agg(pl.col("value").sum(), pl.col("owner").n_unique().alias("owners"))
    # cluster: distinct owners filing within the 5 calendar days up to and including this filing date
    rows = ok.select("symbol", "filed", "owner").unique()
    cl = (rows.join(rows, on="symbol", suffix="_o")
          .filter((pl.col("filed_o") <= pl.col("filed")) & (pl.col("filed_o") >= pl.col("filed") - timedelta(days=4)))
          .group_by("symbol", "filed").agg(pl.col("owner_o").n_unique().alias("cluster")))
    a = a.join(cl, on=["symbol", "filed"], how="left")
    return {"R4a any officer/director buy": a, "R4b cluster (2+ insiders, 5d)": a.filter(pl.col("cluster") >= 2)}


def insider_strategy(sig: pl.DataFrame, hold: int = HOLD, max_names: int = MAX_NAMES):
    by_day: dict[date, list[tuple[str, float]]] = {}
    for sym, filed, value in sig.select("symbol", "filed", "value").iter_rows():
        by_day.setdefault(filed, []).append((sym, value))
    held: dict[str, tuple[int, float]] = {}  # symbol -> (days held, purchase value)
    last_day: list[date | None] = [None]

    def strat(w: Window):
        today = w.today
        # new filings dated after the previous decision and up to today (weekend filings roll forward)
        start = last_day[0] + timedelta(days=1) if last_day[0] else today
        new = []
        d = start
        while d <= today:
            new += by_day.get(d, [])
            d += timedelta(days=1)
        last_day[0] = today
        changed = False
        for s in list(held):
            n, v = held[s]
            if n + 1 >= hold:
                del held[s]
                changed = True
            else:
                held[s] = (n + 1, v)
        for s, v in sorted(new, key=lambda x: -x[1]):
            if s in w.index and not np.isnan(w.close[-1, w.index[s]]):
                if s not in held:
                    changed = True
                held[s] = (0, v)  # a fresh purchase restarts the holding clock
        if len(held) > max_names:
            keep = sorted(held.items(), key=lambda kv: (kv[1][0], -kv[1][1]))[:max_names]
            held.clear()
            held.update(dict(keep))
        if not changed:
            return None
        return {s: 1.0 / len(held) for s in held} if held else {}
    return strat


def main() -> None:
    daily = load_bars(Path("data/bars"), "1Day").select("symbol", "t", "open", "close", "volume").collect()
    sigs = signals(daily)
    syms = sorted(set().union(*[set(s["symbol"].to_list()) for s in sigs.values()]) | {"SPY"})
    months = pl.date_range(date(2016, 1, 1), date.today(), "1mo", eager=True)
    uni = pl.DataFrame({"month": [m for m in months for _ in syms], "symbol": [s for _ in months for s in syms]})
    mom_uni = pl.read_parquet("data/universe.parquet")
    ctx = build_context(daily, uni, START - timedelta(days=60), date.today())
    first = next(i for i, d in enumerate(ctx.days) if d >= START)
    held = next(i for i, d in enumerate(ctx.days) if d >= HELD_OUT)
    for name, s in sigs.items():
        print(f"{name}: {s.height} signal days, {s['symbol'].n_unique()} stocks")
    res = {"SPY (benchmark)": run(ctx, st.buy_hold("SPY"), "SPY", start_index=first)}
    for name, s in sigs.items():
        res[name] = run(ctx, insider_strategy(s), name, start_index=first)
    mctx = build_context(daily, mom_uni, START - timedelta(days=400), date.today())
    mfirst = next(i for i, d in enumerate(mctx.days) if d >= START)
    etfs = set(load_etfs(Path("data/etfs.json")))
    mom = run(mctx, st.momentum(etfs), "momentum", start_index=mfirst)
    for label, a, ma in (("FULL 2017-03 .. now", first, mfirst),
                         ("HELD-OUT 2023-01 .. now", held, next(i for i, d in enumerate(mctx.days) if d >= HELD_OUT))):
        print(f"\n{label}\n{'strategy':<34}{'$200 ->':>9}{'CAGR':>8}{'Sharpe':>8}{'maxDD':>7}{'worst mo':>10}{'trades':>8}")
        for k, r in list(res.items()) + [("momentum 12-1 (baseline)", mom)]:
            x = stats(*window(r, ma if r is mom else a))
            n = (len(r.days) - (ma if r is mom else a) - 1) / 252
            print(f"{k:<34}{200 * (1 + x['cagr']) ** n:>9.0f}{x['cagr']:>8.1%}{x['sharpe']:>8.2f}{x['max_dd']:>7.0%}"
                  f"{x['worst_month']:>10.0%}{r.trades:>8}")
    print("\nCALENDAR YEARS")
    for k, r in res.items():
        yy = yearly(*window(r, first))
        print(f"{k:<34}" + "".join(f"{y % 100:>4}:{v:>5.0%}" for y, v in sorted(yy.items())))


if __name__ == "__main__":
    main()
