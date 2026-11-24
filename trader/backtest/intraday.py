"""R3 (docs/RESEARCH.md): intraday SPY momentum, long-only, after costs.

  uv run python -m trader.backtest.intraday
Signal: SPY return from the previous regular-session close (16:00 New York) to 10:00.
R3:  if positive, buy SPY at 15:30 (open of the 15:30 bar), sell at 16:00 (that bar's close).
R3b: also, if negative, buy SH for the same half hour.
5 bps per side. Bars are SIP 30-minute bars stamped by their START time.
"""

from __future__ import annotations

import random
from datetime import date

import numpy as np
import polars as pl

COST = 5e-4
HELD_OUT = date(2023, 1, 1)


def sessions(df: pl.DataFrame, sym: str) -> pl.DataFrame:
    d = (df.filter(pl.col("symbol") == sym)
         .with_columns(pl.col("t").dt.convert_time_zone("America/New_York").alias("ny"))
         .with_columns(pl.col("ny").dt.date().alias("day"), pl.col("ny").dt.strftime("%H:%M").alias("hm")))
    first = d.filter(pl.col("hm") == "09:30").select("day", pl.col("close").alias("c1000"))
    last = d.filter(pl.col("hm") == "15:30").select("day", pl.col("open").alias("o1530"), pl.col("close").alias("c1600"))
    return first.join(last, on="day").sort("day").with_columns(pl.col("c1600").shift(1).alias("prev_close")).drop_nulls()


def ci(x: np.ndarray, n: int = 2000) -> tuple[float, float]:
    rng = random.Random(3)
    m = sorted(float(np.mean(rng.choices(list(x), k=len(x)))) for _ in range(n))
    return m[int(0.025 * n)], m[int(0.975 * n) - 1]


def report(label: str, days: list[date], r: np.ndarray, held: list[bool]) -> None:
    for name, sel in (("full", np.ones(len(r), bool)), ("held-out 2023+", np.array(held))):
        x = r[sel]
        traded = x[x != 0]
        lo, hi = ci(traded) if len(traded) > 30 else (float("nan"), float("nan"))
        yrs = sel.sum() / 252
        sharpe = np.mean(x) / np.std(x) * np.sqrt(252) if np.std(x) > 0 else 0
        print(f"{label:<28}{name:<16}{len(traded):>7}{np.mean(traded) * 1e4 if len(traded) else 0:>9.2f}"
              f"{f'[{lo * 1e4:+.2f}, {hi * 1e4:+.2f}]':>18}{np.prod(1 + x) ** (1 / yrs) - 1:>9.2%}{sharpe:>8.2f}")


def main() -> None:
    df = pl.read_parquet("data/bars/30Min/spy_sh.parquet")
    spy = sessions(df, "SPY")
    sh = sessions(df, "SH").select("day", pl.col("o1530").alias("sh_o"), pl.col("c1600").alias("sh_c"))
    x = spy.join(sh, on="day", how="left")
    sig = (x["c1000"] / x["prev_close"] - 1).to_numpy()
    spy_last = (x["c1600"] / x["o1530"]).to_numpy() * (1 - COST) ** 2 - 1
    sh_last = np.nan_to_num((x["sh_c"] / x["sh_o"]).to_numpy() * (1 - COST) ** 2 - 1)
    days = x["day"].to_list()
    held = [d >= HELD_OUT for d in days]
    r3 = np.where(sig > 0, spy_last, 0.0)
    r3b = np.where(sig > 0, spy_last, np.where(sig < 0, sh_last, 0.0))
    gross = np.where(sig > 0, (x["c1600"] / x["o1530"]).to_numpy() - 1, 0.0)
    hold = (x["c1600"] / x["prev_close"]).to_numpy() - 1  # SPY close-to-close, the benchmark
    print(f"{len(days)} sessions {days[0]} .. {days[-1]}")
    print(f"{'rule':<28}{'window':<16}{'trades':>7}{'bp/trade':>9}{'95% CI (bp)':>18}{'CAGR':>9}{'Sharpe':>8}")
    report("R3 SPY last 30m (net)", days, r3, held)
    report("R3 before costs", days, gross, held)
    report("R3b + SH on down days", days, r3b, held)
    report("SPY buy-and-hold", days, hold, held)
    hit = np.mean(np.sign(sig[sig != 0]) == np.sign((x["c1600"] / x["o1530"]).to_numpy()[sig != 0] - 1))
    print(f"\nsign agreement, first half hour vs last half hour: {hit:.1%} (50% = no signal)")


if __name__ == "__main__":
    main()
