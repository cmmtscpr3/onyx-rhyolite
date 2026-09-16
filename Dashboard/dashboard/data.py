"""Loading the datasets into pandas, through the collectors' own readers.

Three shapes come out:

* :func:`load_series` -- every long series CSV under ``Dataset/Consumption``
  as one tidy frame (``dataset, series_id, ref_date, value, unit, frequency``).
* :func:`load_pihps` -- the 24 weekly PIHPS workbooks as one tidy frame
  (``market, commodity, level, group, week, price``).
* :func:`load_lots` -- the two ibid listings files as one frame of lots.

Nothing here caches; the app wraps these in ``st.cache_data`` keyed on
:func:`fingerprint`, so a collector commit landing under ``Dataset/`` is
picked up on the next run.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from . import paths

paths.collectors_importable()

from collectors.dates import MONTHS  # noqa: E402
from collectors.model import listing_id  # noqa: E402
from collectors.sinks.long_csv import is_long_table  # noqa: E402
from collectors.sinks.long_csv import read_csv as read_long_csv  # noqa: E402
from collectors.sinks.wide_xlsx import is_value, read_grid  # noqa: E402

# ---------------------------------------------------------------------------
# Fingerprint

DATA_DIRS = (paths.CONSUMPTION, paths.FOOD_PRICES)


@dataclass(frozen=True)
class Fingerprint:
    """What is on disk, compactly: changes when any data file changes."""

    digest: str
    newest: dt.datetime
    files: int


def fingerprint(roots: Iterable[Path] = DATA_DIRS) -> Fingerprint:
    """Hash of every data file's path, size and mtime.

    Backups are excluded on purpose: a collector run snapshots files there
    even when nothing the dashboard shows has changed.
    """
    digest = hashlib.sha256()
    newest = 0.0
    count = 0
    for root in roots:
        for path in sorted(p for p in Path(root).rglob("*") if p.is_file()):
            stat = path.stat()
            digest.update(f"{Path(root).name}/{path.relative_to(root)}|{stat.st_size}|{stat.st_mtime_ns}\n".encode())
            newest = max(newest, stat.st_mtime)
            count += 1
    return Fingerprint(
        digest=digest.hexdigest()[:16],
        newest=dt.datetime.fromtimestamp(newest, tz=dt.timezone.utc),
        files=count,
    )


# ---------------------------------------------------------------------------
# Long series CSVs

#: Median gap between observations, in days, for each publication frequency.
FREQUENCY_BANDS: tuple[tuple[str, int, int], ...] = (
    ("weekly", 5, 10),
    ("monthly", 25, 35),
    ("quarterly", 80, 100),
    ("annual", 350, 380),
)


def infer_frequency(dates: Sequence) -> str:
    """Publication frequency from the spacing of a series' dates.

    Three of the eight series files carry no ``frequency`` column, and two of
    the series in ``bi_payment_system.csv`` are quarterly ratios sitting
    beside monthly stocks, so the frequency has to be read off each series.
    """
    days = sorted({pd.Timestamp(d).normalize() for d in dates})
    if len(days) < 2:
        return "irregular"
    gaps = [(later - earlier).days for earlier, later in zip(days, days[1:])]
    median = statistics.median(gaps)
    for name, low, high in FREQUENCY_BANDS:
        if low <= median <= high:
            return name
    return "irregular"


def long_csv_paths() -> list[Path]:
    """The series CSVs, selected on their header so the listings files stay out."""
    out = []
    for path in sorted(paths.CONSUMPTION.glob("*.csv")):
        with open(path, encoding="utf-8-sig", newline="") as handle:
            header = handle.readline().rstrip("\r\n").split(",")
        if is_long_table(header):
            out.append(path)
    return out


SERIES_COLUMNS = ("dataset", "series_id", "ref_date", "value", "unit", "frequency")


def load_series() -> pd.DataFrame:
    frames = []
    for path in long_csv_paths():
        header, rows = read_long_csv(path)
        frame = pd.DataFrame(rows, columns=header)
        frame["dataset"] = path.stem
        if "frequency" not in frame.columns:
            frame["frequency"] = ""
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=SERIES_COLUMNS)
    series = pd.concat(frames, ignore_index=True)
    series["ref_date"] = pd.to_datetime(series["ref_date"])
    series["value"] = pd.to_numeric(series["value"], errors="coerce")
    series["frequency"] = series["frequency"].fillna("").astype(str)
    blank = series["frequency"] == ""
    if blank.any():
        inferred = (
            series.loc[blank]
            .groupby("series_id")["ref_date"]
            .apply(lambda dates: infer_frequency(dates.tolist()))
        )
        series.loc[blank, "frequency"] = series.loc[blank, "series_id"].map(inferred)
    series = series[list(SERIES_COLUMNS)].sort_values(["dataset", "series_id", "ref_date"])
    return series.reset_index(drop=True)


def wide(series: pd.DataFrame, ids: Sequence[str]) -> pd.DataFrame:
    """The chosen series as columns on a shared date index, in the order given."""
    subset = series[series["series_id"].isin(ids)]
    frame = subset.pivot_table(index="ref_date", columns="series_id", values="value", aggfunc="first")
    frame = frame.reindex(columns=[sid for sid in ids if sid in frame.columns])
    return frame.sort_index()


def frequency_of(series: pd.DataFrame, ids: Sequence[str]) -> str:
    """The frequency shared by a group of series (the most common one)."""
    values = series.loc[series["series_id"].isin(ids), "frequency"]
    if values.empty:
        return "irregular"
    return str(values.mode().iloc[0])


def latest_by_dataset(series: pd.DataFrame) -> dict[str, pd.Timestamp]:
    return series.groupby("dataset")["ref_date"].max().to_dict()


# ---------------------------------------------------------------------------
# PIHPS workbooks

MARKETS: tuple[str, ...] = ("Traditional Market", "Modern Market", "Wholesale")
_WORKBOOK_YEAR = re.compile(r"(\d{4})\.xlsx$")

PIHPS_COLUMNS = ("market", "commodity", "level", "group", "order", "week", "price")


def load_pihps() -> pd.DataFrame:
    """All three markets, all years, one row per (market, commodity, week).

    Prices arrive as text with thousands commas (``'15,750'``) and ``'-'``
    for a week a market did not report; they become floats and NaN.  The
    Traditional Market 2023 workbook also carries all of 2024, identical to
    the 2024 file, so duplicates are dropped keeping the year's own workbook.
    """
    records = []
    for market in MARKETS:
        for path in sorted((paths.FOOD_PRICES / market).glob("*.xlsx")):
            match = _WORKBOOK_YEAR.search(path.name)
            file_year = int(match.group(1)) if match else -1
            grid = read_grid(path)
            group = ""
            for order, row in enumerate(grid.rows):
                name = row.name.strip()
                if row.level == 1:
                    group = name
                for week in grid.weeks:
                    text = grid.cell(row, week)
                    price = float(str(text).replace(",", "")) if is_value(text) else float("nan")
                    records.append((market, name, row.level, group, order, week, price, file_year))
    frame = pd.DataFrame.from_records(records, columns=[*PIHPS_COLUMNS, "file_year"])
    if frame.empty:
        return frame[list(PIHPS_COLUMNS)]
    frame["week"] = pd.to_datetime(frame["week"])
    frame["own_year"] = frame["file_year"] == frame["week"].dt.year
    frame = frame.sort_values(["market", "commodity", "week", "own_year"], ascending=[True, True, True, False])
    frame = frame.drop_duplicates(subset=["market", "commodity", "week"], keep="first")
    return frame[list(PIHPS_COLUMNS)].reset_index(drop=True)


def pihps_commodities(pihps: pd.DataFrame) -> pd.DataFrame:
    """The 31 commodity rows in workbook order: commodity, level, group."""
    rows = pihps[["order", "commodity", "level", "group"]].drop_duplicates("commodity")
    return rows.sort_values("order").reset_index(drop=True)


# ---------------------------------------------------------------------------
# ibid listings

LISTING_FILES: dict[str, str] = {
    "cars": "ibid_car_data.csv",
    "motorcycles": "ibid_motor_data.csv",
}
_AUCTION_DATE = re.compile(r"^\s*(\d{1,2})\s+([A-Za-z]{3,4})\.?\s+(\d{4})")
_CITY = re.compile(r"\d{1,2}\s+[A-Za-z]{3,4}\.?\s+\d{4}\s+(.+?)\s+(?:LIVE|FLASH|TIMED)\b")
_BRANCH_SUFFIX = re.compile(r"\s+[AB]$")
_YEAR_IN_TITLE = re.compile(r"\((\d{4})\s*-\s*(?:MT|AT)")
_YEAR_AT_START = re.compile(r"^\s*(\d{4})\b")

#: Auctions dated before this are stray rows (five lots carry a 2024 date
#: although the scrape only started in mid 2026).
EARLIEST_AUCTION = dt.date(2025, 1, 1)

LOT_COLUMNS = (
    "category",
    "listing_id",
    "title",
    "brand",
    "model",
    "model_year",
    "transmission",
    "plate",
    "grade",
    "price_idr",
    "auction_date",
    "sold",
    "city",
    "first_seen",
)


def parse_auction_date(text: str) -> dt.date | None:
    """``'18 Agt 2026'`` -> a date; ``'Segera Dilelang'`` (coming soon) -> None."""
    match = _AUCTION_DATE.match(text or "")
    if not match:
        return None
    day, month_name, year = match.groups()
    month = MONTHS.get(month_name.lower())
    if month is None:
        return None
    try:
        return dt.date(int(year), month, int(day))
    except ValueError:
        return None


def parse_family(title: str) -> tuple[str, str]:
    """``'TOYOTA AVANZA 1.3 E MT (2019 - MT)'`` -> ``('TOYOTA', 'AVANZA')``.

    The model is the words between the brand and the first number, minus
    trailing one- or two-letter trim codes (``AVANZA E``, ``GRAN MAX BV AC``),
    which is what makes lots of the same vehicle comparable.
    """
    head = (title or "").split("(")[0].strip()
    tokens = head.split()
    if not tokens:
        return "", ""
    brand = tokens[0]
    rest: list[str] = []
    for token in tokens[1:]:
        if token == "-" or any(ch.isdigit() for ch in token):
            break
        rest.append(token)
    while len(rest) > 1 and len(rest[-1]) <= 2:
        rest.pop()
    return brand, " ".join(rest)


def parse_city(card_text: str) -> str:
    match = _CITY.search(card_text or "")
    if not match:
        return ""
    return _BRANCH_SUFFIX.sub("", match.group(1).strip())


def parse_model_year(year_build: str, title: str) -> float:
    match = _YEAR_AT_START.match(year_build or "") or _YEAR_IN_TITLE.search(title or "")
    return float(match.group(1)) if match else float("nan")


def load_lots() -> pd.DataFrame:
    """Every lot on file, with the fields the charts need parsed out.

    Rows without an auction date and rows dated before the scrape began are
    dropped, and the counts recorded in ``frame.attrs`` so the page can say so.
    """
    records = []
    dropped_undated = 0
    dropped_stray = 0
    for category, filename in LISTING_FILES.items():
        path = paths.CONSUMPTION / filename
        if not path.exists():
            continue
        with open(path, encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                auction_date = parse_auction_date(row.get("listed_left", ""))
                if auction_date is None:
                    dropped_undated += 1
                    continue
                if auction_date < EARLIEST_AUCTION:
                    dropped_stray += 1
                    continue
                segments = [part.strip() for part in (row.get("year_build") or "").split("|")]
                brand, model = parse_family(row.get("title", ""))
                price = row.get("price_idr") or ""
                records.append(
                    (
                        category,
                        listing_id(row.get("url", "")),
                        row.get("title", ""),
                        brand,
                        model or brand,
                        parse_model_year(row.get("year_build", ""), row.get("title", "")),
                        segments[1] if len(segments) > 1 and segments[1] in {"MT", "AT"} else "",
                        segments[2] if len(segments) > 2 else "",
                        (row.get("grade") or "").replace("Grade", "").strip() or "-",
                        float(price) if price.strip().isdigit() else float("nan"),
                        auction_date,
                        (row.get("sold") or "").strip() == "True",
                        parse_city(row.get("card_text", "")),
                        row.get("scraped_at_utc", ""),
                    )
                )
    frame = pd.DataFrame.from_records(records, columns=LOT_COLUMNS)
    frame["auction_date"] = pd.to_datetime(frame["auction_date"])
    frame["first_seen"] = pd.to_datetime(frame["first_seen"], errors="coerce")
    frame.attrs["dropped_undated"] = dropped_undated
    frame.attrs["dropped_stray"] = dropped_stray
    return frame
