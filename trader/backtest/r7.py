"""R7 (docs/RESEARCH.md): SEC 8-K filings as a news score on momentum picks.
  uv run python -m trader.backtest.r7     (downloads EDGAR submissions once into data/edgar/, then scores)"""

from __future__ import annotations

import json
import time
from bisect import bisect_left, bisect_right
from datetime import date, timedelta

import httpx
import numpy as np
import polars as pl

from trader.backtest import strategies as st
from trader.backtest.engine import Window, build_context, run
from trader.backtest.scorecard import stats, window, yearly
from trader.config import get_settings
from trader.data.bars import load_bars
from trader.data.universe import load_etfs

START, HELD_OUT = date(2017, 3, 1), date(2023, 1, 1)
LOOKBACK, SKIP, N, POOL = 252, 21, 20, 40
RED = {"5.02", "4.01", "4.02"}


def candidates(ctx, etfs) -> set[str]:
    """Every symbol that was in the monthly momentum top POOL at some month start."""
    out = set()
    for i in range(LOOKBACK + 1, len(ctx.days)):
        if ctx.days[i].month == ctx.days[i - 1].month:
            continue
        names = sorted(s for s in ctx.allowed(i) - etfs if s in ctx._index)
        cols = np.array([ctx._index[s] for s in names], dtype=int)
        c = ctx.close[: i + 1, cols]
        sc = c[-1 - SKIP] / c[-1 - LOOKBACK] - 1
        ok = np.nonzero(~np.isnan(sc))[0]
        out |= {names[k] for k in ok[np.argsort(-sc[ok])][:POOL]}
    return out


def download(symbols: set[str], email: str, folder) -> dict[str, list[tuple[date, set[str]]]]:
    folder.mkdir(parents=True, exist_ok=True)
    ua = {"User-Agent": f"alpaca-trader research {email}"}
    with httpx.Client(headers=ua, timeout=60) as http:
        def get(url: str):
            for attempt in range(6):
                time.sleep(0.15)  # SEC asks for at most 10 requests a second
                r = http.get(url)
                if r.status_code == 200:
                    return r.json()
                if r.status_code == 404:
                    return None
                time.sleep(2 ** attempt)
            r.raise_for_status()

        tick_file = folder / "company_tickers.json"
        if not tick_file.exists():
            tick_file.write_text(json.dumps(get("https://www.sec.gov/files/company_tickers.json")))
        cik = {v["ticker"].replace("-", ".").upper(): int(v["cik_str"]) for v in json.loads(tick_file.read_text()).values()}
        out: dict[str, list[tuple[date, set[str]]]] = {}
        todo = sorted(s for s in symbols if s.replace("-", ".").upper() in cik)
        print(f"EDGAR: {len(todo)} of {len(symbols)} candidate symbols map to a CIK", flush=True)
        for n, s in enumerate(todo):
            c = cik[s.replace("-", ".").upper()]
            f = folder / f"{c}.json"
            if not f.exists():
                sub = get(f"https://data.sec.gov/submissions/CIK{c:010d}.json")
                chunks = [sub["filings"]["recent"]] if sub else []
                for extra in (sub or {}).get("filings", {}).get("files", []):
                    if extra.get("filingTo", "9999") >= "2015-01-01":
                        chunks.append(get(f"https://data.sec.gov/submissions/{extra['name']}") or {})
                rows = [(d, it) for ch in chunks for fm, d, it in zip(ch.get("form", []), ch.get("filingDate", []),
                                                                         ch.get("items", [])) if fm == "8-K" and d >= "2015"]
                f.write_text(json.dumps(rows))
            rows = json.loads(f.read_text())
            out[s] = sorted((date.fromisoformat(d), set(x.strip() for x in it.split(",") if x.strip())) for d, it in rows)
            if n % 100 == 0:
                print(f"  {n}/{len(todo)}", flush=True)
    return out


def r7(etfs: set[str], filings: dict, variant: str):
    dates = {s: [d for d, _ in v] for s, v in filings.items()}

    def strat(w: Window):
        if not st._first_day_of_month(w) or len(w.days) <= LOOKBACK:
            return None
        names, cols = st._cols(w, w.allowed - etfs)
        c = w.close[:, cols]
        sc = c[-1 - SKIP] / c[-1 - LOOKBACK] - 1
        ok = np.nonzero(~np.isnan(sc))[0]
        ranked = [names[k] for k in ok[np.argsort(-sc[ok], kind="stable")]]
        if variant == "a":
            lo, hi = w.days[-1 - LOOKBACK], w.days[-1 - SKIP]
            pool = ranked[:POOL]
            count = {s: (bisect_right(dates[s], hi) - bisect_left(dates[s], lo)) if s in dates else -1 for s in pool}
            # unknown (-1) keeps its momentum place: score it as the pool's median count
            known = [v for v in count.values() if v >= 0]
            med = float(np.median(known)) if known else 0.0
            pick = sorted(pool, key=lambda s: (-(count[s] if count[s] >= 0 else med), pool.index(s)))[:N]
        else:
            cut = w.days[-1] - timedelta(days=30)
            def red(s):
                return any(d > cut and d <= w.days[-1] and (items & RED) for d, items in filings.get(s, []))
            pick = [s for s in ranked if not red(s)][:N]
        return {s: 1.0 / len(pick) for s in pick} if pick else {}
    return strat


def main() -> None:
    s = get_settings()
    if not s.sec_contact_email:
        raise SystemExit("Set SEC_CONTACT_EMAIL in .env (the SEC requires a contact in the User-Agent)")
    universe = pl.read_parquet(s.data_dir / "universe.parquet")
    daily = load_bars(s.data_dir / "bars", "1Day").select("symbol", "t", "open", "close", "volume").collect()
    ctx = build_context(daily, universe, START - timedelta(days=400), date.today())
    e = set(load_etfs(s.etfs_file))
    first = next(i for i, d in enumerate(ctx.days) if d >= START)
    held = next(i for i, d in enumerate(ctx.days) if d >= HELD_OUT)
    filings = download(candidates(ctx, e), s.sec_contact_email, s.data_dir / "edgar")
    plans = {"SPY (benchmark)": st.buy_hold("SPY"), "momentum 12-1 (live paper)": st.momentum(e),
             "R7a news-confirmed momentum": r7(e, filings, "a"), "R7b red-flag filter": r7(e, filings, "b")}
    out = {}
    print(f"{'strategy':<32}{'final':>8}{'CAGR':>8}{'Sharpe':>8}{'maxDD':>7} |{'HO CAGR':>9}{'HO Shp':>8}{'HO DD':>7}{'trades':>8}")
    for k, f in plans.items():
        r = run(ctx, f, k, capital=200.0, cost_bps=5.0, start_index=first)
        a, b = stats(*window(r, first)), stats(*window(r, held))
        out[k] = {"full": a, "held": b, "years": {str(y): v for y, v in yearly(*window(r, first)).items()}}
        print(f"{k:<32}{a['final']:>8.0f}{a['cagr']:>8.1%}{a['sharpe']:>8.2f}{a['max_dd']:>7.0%} |"
              f"{b['cagr']:>9.1%}{b['sharpe']:>8.2f}{b['max_dd']:>7.0%}{r.trades:>8}", flush=True)
    json.dump(out, open(s.data_dir / "results" / "r7.json", "w"), default=float, indent=1)


if __name__ == "__main__":
    main()
