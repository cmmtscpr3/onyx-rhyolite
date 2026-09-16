"""BI Survei Konsumen -- the consumer confidence index and the income split.

Not PDF-only, which is the usual assumption: alongside the monthly PDF, BI
publishes ``Data-Series-SK-<Bulan>-<Tahun>.zip`` holding one workbook with the
**full monthly history from 2012**.  Reading that is both more reliable than
PDF table extraction and backfills the whole series in one fetch.

Release pages are ``/id/publikasi/laporan/Pages/SK-<Bulan>-<Tahun>.aspx`` and
there is no index API -- the listing is rendered by SharePoint search -- so the
newest release is found by walking months back from today until a page answers.
BI publishes around the eighth of the following month, so the current month's
page usually does not exist yet.

Sheets read here are the **national** ones: Tabel 1 (IKK/IKE/IEK and their six
sub-indices, plus three price-expectation indices), Tabel 5 (the share of
income going to consumption, loan instalments and saving) and Tabel 9 (what
respondents expect those to do next).  Tabel 6 repeats IKK for eighteen survey
cities and is deliberately **not** collected: these datasets are national-only,
so a city row has nowhere to go.  It stays in the configuration because it
documents the source, and enabling it later is a one-line change.

Tabel 5 and Tabel 1's durable-goods index are the two halves of the
ability-versus-willingness question and are kept as separate series, never
collapsed into one number.

Two source quirks that are features, not bugs: BI ships discontinued rows with
its own ``*) Data diskontinu`` footnote -- the price-expectation rows in Tabel 1
are empty after December 2019 and Tabel 9 stops in March 2020 -- so those
series simply end, and are never zero-filled.  And ``IKK`` is the mean of
``IKE`` and ``IEK``, which makes a useful sanity check on any parse.
"""

from __future__ import annotations

import datetime as dt
import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

from .. import excelio, incremental, paths
from ..dates import clean_label
from ..errors import SourceUnavailable
from ..http import FetchError, fetch
from ..model import Obs

BASE = "https://www.bi.go.id"
INDEX_URL = f"{BASE}/id/publikasi/laporan/Default.aspx?id=survei-konsumen"
PAGE_URL = f"{BASE}/id/publikasi/laporan/Pages/SK-{{month}}-{{year}}.aspx"
CONFIG_PATH = paths.CONFIG / "bi_consumer_survey.yaml"
PREFIX = "bi_consumer_survey"

#: Month names as they appear in the release-page slug.
MONTH_NAMES = (
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
)

#: How many months back to look for the newest release before giving up.
SEARCH_MONTHS = 6

#: Only national sheets are collected; see the module docstring.
SCOPES = ("national",)


@dataclass(frozen=True, slots=True)
class SheetSpec:
    sheet: str
    scope: str
    kind: str
    rows: tuple[dict[str, str], ...]
    unit: str = "index"
    group_prefix: str = ""


def load_config(path: Path | str = CONFIG_PATH) -> tuple[tuple[SheetSpec, ...], dict[str, str]]:
    with open(path, encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    sheets = tuple(
        SheetSpec(
            sheet=entry["sheet"],
            scope=entry["scope"],
            kind=entry["kind"],
            rows=tuple(entry["rows"]),
            unit=entry.get("unit", "index"),
            group_prefix=entry.get("group_prefix", ""),
        )
        for entry in document["sheets"]
    )
    return sheets, dict(document.get("expenditure_groups") or {})


def release_url(year: int, month: int) -> str:
    return PAGE_URL.format(month=MONTH_NAMES[month - 1], year=year)


def previous_months(start: dt.date, count: int) -> Iterable[tuple[int, int]]:
    year, month = start.year, start.month
    for _ in range(count):
        yield year, month
        month -= 1
        if month == 0:
            year, month = year - 1, 12


def find_release(*, sess=None, on: dt.date | None = None):
    """The Data Series zip of the newest release page that exists."""
    on = on or dt.date.today()
    tried: list[str] = []
    for year, month in previous_months(on, SEARCH_MONTHS):
        url = release_url(year, month)
        tried.append(url)
        try:
            page = fetch(url, sess=sess)
        except FetchError:
            continue
        link = _zip_link(page.text())
        if not link:
            continue
        return fetch(_absolute(link), sess=sess)
    raise SourceUnavailable(
        f"no BI Survei Konsumen data-series zip in the last {SEARCH_MONTHS} months; "
        f"tried {', '.join(tried)}"
    )


def parse_workbook(content: bytes, *, since: dt.date | None = None) -> list[Obs]:
    sheets, groups = load_config()
    grids = excelio.load(content, "xlsx")
    out: list[Obs] = []
    for spec in sheets:
        if spec.scope not in SCOPES:
            continue
        grid = grids.get(spec.sheet)
        if grid is None:
            continue
        out.extend(_parse_sheet(grid, spec, groups, since=since))
    return out


def _parse_sheet(grid, spec: SheetSpec, groups: dict[str, str], *, since) -> list[Obs]:
    year_row, period_row = excelio.detect_header(grid)
    columns = excelio.periods(grid, year_row, period_row)
    out: list[Obs] = []
    group_suffix = ""
    for row in range(grid.nrows):
        label = _deep_label(grid, row)
        if not label:
            continue
        # Tabel 5 repeats its three rows under each expenditure bracket, so the
        # bracket heading becomes part of the series id rather than a new row.
        if spec.group_prefix:
            mapped = groups.get(label)
            if mapped is not None:
                group_suffix = mapped
                continue
        for row_spec in spec.rows:
            if not _matches(label, row_spec["match"]):
                continue
            parts = [p for p in (spec.group_prefix, row_spec["sub"], group_suffix) if p]
            series_id = f"{PREFIX}." + ".".join(parts)
            for column in columns:
                if since and column.ref_date < since:
                    continue
                value = excelio.number(grid.cell(row, column.col))
                if value is None:
                    continue
                out.append(
                    Obs(
                        series_id=series_id,
                        ref_date=column.ref_date,
                        ref_period=column.ref_period,
                        value=value,
                        unit=spec.unit,
                        notes={"sheet": spec.sheet, "label": label},
                    )
                )
            break
    return out


def collect(
    *,
    sess=None,
    since: dt.date | None = None,
    dry_run: bool = False,
    backups=None,
    full: bool = False,
    overlap: int = incremental.DEFAULT_OVERLAP,
):
    """Fetch the newest Data Series zip and upsert it into its dataset file.

    The zip is the whole history from 2012 and there is no way to ask for less,
    so narrowing only stops months already on file from being re-emitted.
    """
    from ..sinks import long_csv

    window = since or incremental.auto_since(
        paths.consumption_csv(PREFIX), PREFIX, overlap=overlap, full=full
    )
    payload = find_release(sess=sess)
    workbook, _member = _extract_workbook(payload.content)
    observations = parse_workbook(workbook, since=window)
    return [
        long_csv.upsert(
            paths.consumption_csv(PREFIX), observations, dry_run=dry_run, backups=backups
        )
    ]


def _matches(label: str, needle: str) -> bool:
    return _fold(needle) in _fold(label)


def _fold(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).replace("\n", " ").casefold().strip()


def _deep_label(grid, row: int, first_col: int = 0, last_col: int = 6) -> str:
    """The deepest label cell in a row.

    BI indents these sheets: a bullet '-' sits in one column and the component
    name in the next, so the last non-empty text cell before the data starts is
    the name rather than the bullet.
    """
    found = ""
    for col in range(first_col, min(last_col, grid.ncols)):
        value = grid.cell(row, col)
        if not isinstance(value, str):
            continue
        text = clean_label(value.replace("\n", " "))
        if text and text not in {"-", "–", "—"}:
            found = text
    return found


def _zip_link(html: str) -> str | None:
    match = re.search(r'href="([^"]*Data-Series-SK[^"]*\.zip)"', html, re.I)
    return match.group(1) if match else None


def _absolute(url: str) -> str:
    return url if url.startswith("http") else f"{BASE}{url}"


def _extract_workbook(archive_bytes: bytes) -> tuple[bytes, str]:
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        members = [n for n in archive.namelist() if n.lower().endswith((".xlsx", ".xls"))]
        if not members:
            raise SourceUnavailable(
                f"Data Series zip holds no workbook; members: {archive.namelist()}"
            )
        return archive.read(members[0]), members[0]
