"""PIHPS weekly food prices, by market level.

Bank Indonesia's Pusat Informasi Harga Pangan Strategis publishes a weekly
national average price for 31 commodities at four market levels.  The uploaded
workbooks cover three of them, one file per market per year.

Two things about this source are worth stating because they are easy to get
wrong:

* **The portal moved.**  PIHPS was built on ``hargapangan.id``; since July 2023
  it lives inside the Bank Indonesia site and the old domain answers a
  Cloudflare 522 because nothing is behind it any more.  Only
  ``www.bi.go.id/hargapangan`` works, and it needs no session or cookie.
* **The week grid is anchored to the start date you ask for.**  Requesting
  ``start_date=2026-01-01`` returns Thursdays, because 1 January 2026 was a
  Thursday; 2025 returns Wednesdays, 2024 Mondays.  That is exactly the
  per-year weekday shift visible in the uploaded files, so asking from 1
  January of the file's own year reproduces its columns rather than
  interleaving a second, offset set.

``start_date``/``end_date`` go out in ISO form and the day keys come back as
``dd/mm/yyyy`` -- the opposite convention, in the same request.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from .. import paths
from ..http import fetch
from ..sinks import wide_xlsx
from ..sinks.wide_xlsx import Grid, Row

BASE = "https://www.bi.go.id/hargapangan"
API = f"{BASE}/WebSite/TabelHarga"
GRID_ENDPOINT = f"{API}/GetGridDataDaerah"
REFERER = f"{BASE}/TabelHarga/PasarTradisionalDaerah"

#: ``tipe_laporan`` on the portal: 1 daily, 4 weekly, 5 monthly, 6 chart.
REPORT_WEEKLY = 4

#: The portal serves history back to January 2018 and nothing before it.
EARLIEST_YEAR = 2018

#: How many already-collected weeks to re-request anyway, so a restatement
#: inside that window is still noticed.  Eight weeks costs about a second.
OVERLAP_WEEKS = 8

_JSON_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": REFERER,
}

#: Keys in each response row that are metadata rather than a week.
_META_KEYS = {"no", "name", "level"}


@dataclass(frozen=True, slots=True)
class Market:
    price_type_id: int
    directory: str


MARKETS = tuple(
    Market(price_type_id=pid, directory=name) for pid, name in sorted(paths.MARKET_DIRS.items())
)


def grid_from_response(data: list[dict]) -> Grid:
    """Turn one ``GetGridDataDaerah`` payload into a mergeable grid.

    Values are carried across as the strings the portal sends -- ``'16,200'``,
    or ``'-'`` where a market did not report.  That is already the on-disk
    form, so nothing is parsed into a float and nothing can be lost to
    rounding or to a locale guess about which separator is the decimal one.
    """
    grid = Grid()
    for item in data or []:
        name = str(item.get("name") or "")
        if not name.strip():
            continue
        try:
            level = int(item.get("level") or 0)
        except (TypeError, ValueError):
            level = 0
        # The portal numbers groups with Roman numerals and varieties with
        # Arabic ones, which is the convention the workbooks already use.
        row = Row(no=str(item.get("no", "")).strip(), name=name, level=level)
        if row.key not in {existing.key for existing in grid.rows}:
            grid.rows.append(row)
        for key, value in item.items():
            if key in _META_KEYS:
                continue
            week = wide_xlsx.parse_header_date(key)
            if week is None:
                continue
            grid.values[(row.key, week)] = str(value).strip() if value is not None else wide_xlsx.MISSING
    return grid


def start_for(
    path, year: int, *, overlap: int = OVERLAP_WEEKS, full: bool = False
) -> dt.date:
    """Where to start the request so the returned grid lines up with the file.

    The portal does not answer "data since X" -- it answers "a weekly grid
    anchored on X".  Measured against the real 2026 workbook, whose 37 columns
    are Thursdays: starting from an existing column eight weeks back returns
    eight Thursdays that are a subset of the file's own columns, while starting
    two days later returns *Mondays*.  An off-lattice start would therefore add
    a second, parallel set of columns to the workbook rather than extending it.

    So the start is always either 1 January -- which is how the file was built,
    and the fallback whenever there is nothing to align to -- or one of the
    dates already in it.  Never an arithmetic offset from the newest one.
    """
    january = dt.date(year, 1, 1)
    if full:
        return january
    weeks = [week for week in wide_xlsx.existing_weeks(path) if week.year == year]
    if not weeks:
        return january
    return weeks[-overlap] if len(weeks) > overlap else weeks[0]


def window(
    year: int, *, today: dt.date | None = None, start: dt.date | None = None
) -> tuple[dt.date, dt.date]:
    """The request window for one year, ending at the earlier of today or year end."""
    today = today or dt.date.today()
    start = start or dt.date(year, 1, 1)
    end = min(today, dt.date(year, 12, 31))
    return start, end


def fetch_market(
    market: Market,
    year: int,
    *,
    sess=None,
    today: dt.date | None = None,
    start: dt.date | None = None,
) -> Grid:
    start, end = window(year, today=today, start=start)
    payload = fetch(
        GRID_ENDPOINT,
        sess=sess,
        headers=_JSON_HEADERS,
        params={
            "price_type_id": market.price_type_id,
            "province_id": "",
            "regency_id": "",
            "market_id": "",
            "tipe_laporan": REPORT_WEEKLY,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    )
    body = payload.json()
    return grid_from_response(body.get("data") if isinstance(body, dict) else body)


def collect(
    *,
    sess=None,
    years: list[int] | None = None,
    dry_run: bool = False,
    backups=None,
    today: dt.date | None = None,
    full: bool = False,
    overlap: int = OVERLAP_WEEKS,
) -> list[wide_xlsx.MergeReport]:
    """Update one workbook per market per requested year.

    Defaults to the current year alone.  That keeps each request inside the
    portal's fast window (180 days answers in about 17 seconds, two years in
    about three minutes) and it means the odd two-years-wide
    ``Traditional Market/... 2023.xlsx`` is never rewritten unless a backfill
    asks for 2023 explicitly.
    """
    today = today or dt.date.today()
    years = sorted(set(years or [today.year]))
    reports: list[wide_xlsx.MergeReport] = []
    for year in years:
        if year < EARLIEST_YEAR:
            raise ValueError(f"PIHPS has no history before {EARLIEST_YEAR}; got {year}")
        for market in MARKETS:
            path = paths.market_workbook(market.price_type_id, year)
            start = start_for(path, year, overlap=overlap, full=full)
            fetched = fetch_market(market, year, sess=sess, today=today, start=start)
            reports.append(
                wide_xlsx.write(path, fetched, dry_run=dry_run, backups=backups)
            )
    return reports
