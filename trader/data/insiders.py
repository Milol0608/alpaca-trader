"""SEC insider transactions (Forms 3/4/5) from the SEC's quarterly structured data sets.

  uv run python -m trader.data.insiders

Source: https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets (free; file
links are read from that page, since the SEC moved newer quarters to a different path). Requests carry
the SEC-requested User-Agent "<project> <contact email>" (SEC_CONTACT_EMAIL) and stay well under the
SEC's 10 requests/second.

Writes data/insiders/purchases.parquet: one row per open-market PURCHASE (transaction code P) by a
reporting owner, with the FILING DATE (when the public could know) and the owner's relationship.
"""

from __future__ import annotations

import io
import logging
import re
import time
import zipfile
from pathlib import Path

import httpx
import polars as pl

from trader.config import get_settings

PAGE = "https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets"
OUT = Path("data/insiders")
log = logging.getLogger("insiders")


def _tsv(z: zipfile.ZipFile, name: str, cols: list[str]) -> pl.DataFrame:
    member = next(n for n in z.namelist() if n.upper().endswith(name))
    df = pl.read_csv(io.BytesIO(z.read(member)), separator="\t", infer_schema_length=0, quote_char=None,
                     truncate_ragged_lines=True)
    return df.select([c for c in cols if c in df.columns])


def parse_quarter(raw: bytes) -> pl.DataFrame:
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        sub = _tsv(z, "SUBMISSION.TSV", ["ACCESSION_NUMBER", "FILING_DATE", "ISSUERTRADINGSYMBOL", "DOCUMENT_TYPE"])
        own = _tsv(z, "REPORTINGOWNER.TSV", ["ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNER_RELATIONSHIP",
                                              "RPTOWNER_TITLE"])
        tr = _tsv(z, "NONDERIV_TRANS.TSV", ["ACCESSION_NUMBER", "TRANS_CODE", "TRANS_DATE", "TRANS_SHARES",
                                             "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD"])
    buys = tr.filter((pl.col("TRANS_CODE") == "P") & (pl.col("TRANS_ACQUIRED_DISP_CD") == "A"))
    own1 = own.unique("ACCESSION_NUMBER", keep="first")  # joint filings: one owner row is enough to classify
    df = buys.join(sub, on="ACCESSION_NUMBER").join(own1, on="ACCESSION_NUMBER", how="left")
    return df.select(
        pl.col("ACCESSION_NUMBER").alias("accession"),
        pl.col("ISSUERTRADINGSYMBOL").str.strip_chars().str.to_uppercase().alias("symbol"),
        pl.col("FILING_DATE").str.to_date("%d-%b-%Y", strict=False).alias("filed"),
        pl.col("TRANS_DATE").str.to_date("%d-%b-%Y", strict=False).alias("traded"),
        pl.col("RPTOWNERCIK").alias("owner"),
        pl.col("RPTOWNER_RELATIONSHIP").alias("relationship"),
        pl.col("RPTOWNER_TITLE").alias("title"),
        pl.col("TRANS_SHARES").cast(pl.Float64, strict=False).alias("shares"),
        pl.col("TRANS_PRICEPERSHARE").cast(pl.Float64, strict=False).alias("price"),
    ).with_columns((pl.col("shares") * pl.col("price")).alias("value"))


def main(first_year: int = 2016) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    email = get_settings().sec_contact_email
    if not email:
        raise SystemExit("Set SEC_CONTACT_EMAIL in .env (the SEC requires a contact in the User-Agent)")
    ua = {"User-Agent": f"alpaca-trader research {email}"}
    (OUT / "quarters").mkdir(parents=True, exist_ok=True)
    with httpx.Client(headers=ua, timeout=120, follow_redirects=True) as http:
        links = sorted(set(re.findall(r'href="([^"]+?(\d{4})q(\d)_form345\.zip)"', http.get(PAGE).text)))
        links = [(f"https://www.sec.gov{h}" if h.startswith("/") else h, int(y), int(q)) for h, y, q in links]
        frames = []
        for url, y, q in sorted(links, key=lambda x: (x[1], x[2])):
            if y < first_year:
                continue
            part = OUT / "quarters" / f"{y}q{q}.parquet"
            if not part.exists():
                r = http.get(url)
                r.raise_for_status()
                parse_quarter(r.content).write_parquet(part)
                log.info("%dq%d: %d purchases", y, q, pl.read_parquet(part).height)
                time.sleep(0.5)  # polite: far below the SEC's 10 requests/second
            frames.append(pl.read_parquet(part))
    allp = pl.concat(frames).unique(["accession", "owner", "traded", "shares", "price"])
    allp.write_parquet(OUT / "purchases.parquet")
    log.info("total purchases: %d, %s .. %s", allp.height, allp["filed"].min(), allp["filed"].max())


if __name__ == "__main__":
    main()
