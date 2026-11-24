from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import polars as pl

from trader.alpaca.client import AlpacaClient
from trader.data.bars import download, load_bars
from trader.data.universe import build_universe


def fake_client(calls: list[dict]) -> AlpacaClient:
    def handler(req: httpx.Request) -> httpx.Response:
        p = dict(req.url.params)
        calls.append(p)
        out = {}
        for s in p["symbols"].split(","):
            out[s] = [{"t": f"{p['start']}T05:00:00Z", "o": 1, "h": 1, "l": 1, "c": 10.0, "v": 5, "n": 1, "vw": 10.0}]
        return httpx.Response(200, json={"bars": out, "next_page_token": None})
    return AlpacaClient("https://p", "https://d", "K", "S", transport=httpx.MockTransport(handler), sleep=lambda s: None)


def test_download_writes_one_file_per_year_and_skips_finished_years(tmp_path: Path) -> None:
    calls: list[dict] = []
    with fake_client(calls) as c:
        download(c, ["AAA", "BBB", "CCC"], "1Day", date(2024, 6, 1), date(2025, 2, 1), tmp_path, chunk=2,
                 today=date(2025, 3, 1))
        assert len(calls) == 4  # 2 years x 2 batches
        assert {p["start"] for p in calls} == {"2024-06-01", "2025-01-01"}
        df = load_bars(tmp_path, "1Day").collect()
        assert df.height == 6 and set(df["symbol"]) == {"AAA", "BBB", "CCC"}
        assert df.schema["t"] == pl.Datetime("us", "UTC")
        calls.clear()
        download(c, ["AAA", "BBB", "CCC"], "1Day", date(2024, 6, 1), date(2025, 2, 1), tmp_path, chunk=2,
                 today=date(2025, 3, 1))
        assert {p["start"] for p in calls} == {"2025-01-01"}  # 2024 is finished; only the current year refetches


def test_interrupted_year_resumes_from_saved_batches(tmp_path: Path) -> None:
    calls: list[dict] = []
    parts = tmp_path / "1Day" / "2025.parts"
    parts.mkdir(parents=True)
    pl.DataFrame({"symbol": ["AAA"], "t": [datetime(2025, 1, 2, 5, tzinfo=timezone.utc)], "open": [1.0], "high": [1.0],
                  "low": [1.0], "close": [10.0], "volume": [5.0], "trades": [1], "vwap": [10.0]}).with_columns(
        pl.col("t").cast(pl.Datetime("us", "UTC"))).write_parquet(parts / "00000.parquet")
    with fake_client(calls) as c:
        download(c, ["AAA", "BBB"], "1Day", date(2025, 1, 1), date(2025, 1, 31), tmp_path, chunk=1, today=date(2025, 2, 1))
    assert [p["symbols"] for p in calls] == ["BBB"]  # batch 0 was already saved
    assert not parts.exists()


def _daily(symbols_dv: dict[str, float], start: date, days: int, price: float = 20.0) -> pl.DataFrame:
    rows = []
    for k in range(days):
        d = start + timedelta(days=k)
        for s, dv in symbols_dv.items():
            rows.append({"symbol": s, "t": datetime(d.year, d.month, d.day, 5, tzinfo=timezone.utc),
                         "close": price, "volume": dv / price})
    return pl.DataFrame(rows).with_columns(pl.col("t").cast(pl.Datetime("us", "UTC")))


def test_universe_uses_only_data_before_each_month() -> None:
    assets = pl.DataFrame({"symbol": ["BIG", "SMALL", "TQQQ", "SPY"],
                           "name": ["Big Co", "Small Co", "ProShares UltraPro QQQ", "SPDR S&P 500 ETF Trust"]})
    jan = _daily({"BIG": 1e9, "SMALL": 1e6, "TQQQ": 5e9, "SPY": 9e9}, date(2026, 1, 1), 31)
    # In February SMALL suddenly trades 1000x more. March's universe may know it; February's must not.
    feb = _daily({"BIG": 1e9, "SMALL": 1e12, "TQQQ": 5e9, "SPY": 9e9}, date(2026, 2, 1), 28)
    uni = build_universe(pl.concat([jan, feb]), assets, ["SPY"], size=1, lookback=20)
    feb_u = uni.filter(pl.col("month") == date(2026, 2, 1))
    mar_u = uni.filter(pl.col("month") == date(2026, 3, 1))
    assert feb_u.filter(pl.col("kind") == "stock")["symbol"].to_list() == ["BIG"]
    assert mar_u.filter(pl.col("kind") == "stock")["symbol"].to_list() == ["SMALL"]
    assert "TQQQ" not in uni["symbol"].to_list()  # leveraged fund kept out despite its volume
    assert feb_u.filter(pl.col("kind") == "etf")["symbol"].to_list() == ["SPY"]


def test_universe_drops_penny_stocks_and_thin_history() -> None:
    assets = pl.DataFrame({"symbol": ["CHEAP", "NEW", "OK"], "name": ["a", "b", "c"]})
    base = _daily({"OK": 1e8}, date(2026, 1, 1), 31)
    cheap = _daily({"CHEAP": 9e9}, date(2026, 1, 1), 31, price=2.0)
    new = _daily({"NEW": 9e9}, date(2026, 1, 25), 7)
    uni = build_universe(pl.concat([base, cheap, new]), assets, [], size=5, lookback=20)
    assert uni.filter(pl.col("month") == date(2026, 2, 1))["symbol"].to_list() == ["OK"]
