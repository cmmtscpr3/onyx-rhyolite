"""OJK Statistik Perbankan Indonesia -- third-party funds (DPK).

DPK is the deposit side of the banking system: what households, firms and
government hold at commercial banks.  OJK publishes one workbook a month, of
fifty-odd sheets, and this collector reads the **national composition** sheet
(``Komp.DPK_1.28.a.-1.32.a.``), which splits total deposits into giro,
tabungan and simpanan berjangka.  The by-province and by-instrument sheets are
not read: these datasets are national-only, so a provincial row has nowhere to
go.

Three things to know before trusting this source:

* **It is stale at source.**  The public index lists releases up to **June
  2025** and no further; every later month's page returns 404.  That is OJK's
  publishing, not a bug here, so a run with nothing new reports staleness and
  carries on.  For a *current* reading of deposits by owner, ``bi_seki.py``
  reads SEKI table I.18, which was refreshed in September 2026.
* **Use ``ojk.go.id``, not ``www.ojk.go.id``.**  The ``www`` host fails from
  some egress points with the TLS connection closing mid-exchange, while the
  bare host answers normally.
* **Each workbook is a snapshot, not a history**, so the series is assembled
  one release at a time and every release adds only its own reference dates.

Note the name collision: OJK's "SPI" is Statistik Perbankan Indonesia; BI's
"SPIP" is the payment-system publication read by ``bi_spip.py``.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from urllib.parse import quote, urljoin

from .. import excelio, incremental, paths
from ..dates import MONTHS, clean_label, month_start
from ..errors import SourceUnavailable
from ..http import fetch
from ..model import Obs

BASE = "https://ojk.go.id"
INDEX_URL = (
    f"{BASE}/id/kanal/perbankan/data-dan-statistik/"
    "statistik-perbankan-indonesia/Default.aspx"
)
PREFIX = "ojk_dpk"

#: How many monthly releases to walk back through.  Each one contributes only
#: its own reference dates, so a few releases widen the series.
DEFAULT_RELEASES = 3

#: Warn once the newest listed release is older than this.
STALE_AFTER_DAYS = 75

#: Sheet lookup, as words that must and must not appear in the sheet name.
#:
#: The workbook holds five DPK sheets whose names nest inside one another --
#: "Komp.DPK_1.28.a.-1.32.a.", "Komp.DPK_KBMI 1.28.-1.32.", "Komp DPK per
#: Lok_1.33.a.", "DPK per Lok_1.34.a." and "Komp DPK BPR_2.7" -- so a plain
#: substring match hands the same sheet to every parser.  Matching on whole
#: words with explicit exclusions says which variant is wanted: the ".a."
#: tables are conventional commercial banks, "KBMI" groups them by capital
#: tier, and "BPR" is the rural banks, a different population that must never
#: be summed with the rest.
SHEET_NATIONAL_COMPOSITION = (("komp", "dpk"), ("lok", "bpr", "kbmi"))

#: Rows of the national composition sheet worth storing.
NATIONAL_ROWS = {
    "giro": "giro",
    "tabungan": "tabungan",
    "simpanan berjangka": "simpanan_berjangka",
    "total dpk": "total",
}


@dataclass(frozen=True, slots=True)
class Release:
    """One monthly SPI publication."""

    month: dt.date
    page_url: str
    title: str

    @property
    def label(self) -> str:
        return f"{self.month:%Y-%m}"


_RELEASE_TITLE = re.compile(
    r"Statistik\s+Perbankan\s+Indonesia\s*[-–]\s*([A-Za-z]+)\s+(\d{4})", re.I
)


def parse_index(html: str, base_url: str = INDEX_URL) -> list[Release]:
    """Release pages from the SPI index, newest first."""
    releases: dict[dt.date, Release] = {}
    for href, text in re.findall(r'href="([^"]+)"[^>]*>(.{0,200}?)</a>', html, re.S):
        title = clean_label(re.sub("<[^>]+>", " ", text))
        match = _RELEASE_TITLE.search(title)
        if not match or "/Pages/" not in href:
            continue
        month = MONTHS.get(match.group(1).lower())
        if not month:
            continue
        ref = month_start(int(match.group(2)), month)
        releases.setdefault(
            ref, Release(month=ref, page_url=urljoin(base_url, href), title=title)
        )
    return sorted(releases.values(), key=lambda r: r.month, reverse=True)


def workbook_url(release: Release, *, sess=None) -> str:
    """The .xlsx attachment on a release page.

    The filename carries literal spaces (and a double space), and the page
    offers both a raw and a percent-encoded href, so quoting with ``%`` left
    safe handles either without double-encoding.
    """
    page = fetch(release.page_url, sess=sess)
    match = re.search(r'href="([^"]+\.xlsx)"', page.text(), re.I)
    if not match:
        raise SourceUnavailable(f"OJK release page {release.page_url} has no .xlsx attachment")
    return urljoin(BASE, quote(match.group(1), safe="/:%?=&"))


def _sheet(grids: dict, rule: tuple[tuple[str, ...], tuple[str, ...]]):
    """First sheet whose name has every wanted word and no unwanted one."""
    wanted, unwanted = rule
    for name, grid in grids.items():
        words = {word for word in re.split(r"[^a-z]+", str(name).lower()) if word}
        if all(word in words for word in wanted) and not any(word in words for word in unwanted):
            return grid
    return None


def _match_key(label: str, table: dict[str, str]) -> str | None:
    folded = clean_label(label).casefold()
    if not folded:
        return None
    for needle, key in table.items():
        if folded.startswith(needle):
            return key
    return None


def parse_workbook(content: bytes, release: Release) -> list[Obs]:
    grids = excelio.load(content, "xlsx")
    grid = _sheet(grids, SHEET_NATIONAL_COMPOSITION)
    if grid is None:
        return []
    sub_row = excelio.find_label_row(grid, "nominal")
    if sub_row is None:
        return []
    label_row = max(0, sub_row - 1)
    columns = excelio.month_year_periods(grid, label_row, sub_row=sub_row, sub_label="Nominal")
    if not columns:
        return []

    out: list[Obs] = []
    claimed: set[str] = set()
    for row in range(sub_row + 1, grid.nrows):
        label = grid.row_label(row, 2)
        key = _match_key(label, NATIONAL_ROWS)
        # The sheet stacks five tables; only the first (commercial banks, all
        # groups) is taken, so each component is claimed exactly once.
        if not key or key in claimed:
            continue
        claimed.add(key)
        for column in columns:
            value = excelio.number(grid.cell(row, column.col))
            if value is None:
                continue
            out.append(
                Obs(
                    series_id=f"{PREFIX}.composition.{key}",
                    ref_date=column.ref_date,
                    ref_period=column.ref_period,
                    value=value,
                    unit="IDR billion",
                    notes={"sheet": grid.name, "release": release.label, "label": label},
                )
            )
    return out


def collect(
    *,
    sess=None,
    since: dt.date | None = None,
    dry_run: bool = False,
    backups=None,
    releases: int = DEFAULT_RELEASES,
    today: dt.date | None = None,
    full: bool = False,
    overlap: int = 0,
):
    """Read the newest OJK releases that are not already on file.

    This is the one collector where narrowing saves real work rather than a
    little parsing: each release is a ~35 MB workbook of fifty-odd sheets, and
    without a watermark it re-downloads the newest three on every run even when
    all three are already stored.  Releases are monthly snapshots, so "already
    on file" is decided by release month, and there is no overlap by default --
    OJK does not restate a published month, it just stops publishing.
    """
    from ..sinks import long_csv

    payload = fetch(INDEX_URL, sess=sess)
    listed = parse_index(payload.text())
    if not listed:
        raise SourceUnavailable("no OJK SPI releases listed on the index page")

    warnings: list[str] = []
    behind = ((today or dt.date.today()) - listed[0].month).days
    if behind > STALE_AFTER_DAYS:
        warnings.append(
            f"newest OJK release is {listed[0].label} ({behind} days old); "
            f"OJK has published nothing since. Use bi_seki deposits_by_owner for a "
            f"current reading."
        )

    watermark = since
    if watermark is None and not full:
        latest = long_csv.latest_ref_date(paths.consumption_csv(PREFIX), PREFIX)
        if latest is not None:
            # Strictly newer: a release whose own month is already stored has
            # nothing left to give.
            watermark = incremental.months_before(latest, overlap) if overlap else latest
            wanted = [r for r in listed if r.month > watermark][:releases]
            if not wanted:
                warnings.append(
                    f"no OJK release newer than {latest:%Y-%m} to read; "
                    f"skipped {min(releases, len(listed))} workbook download(s)"
                )
            observations: list[Obs] = []
            for release in wanted:
                content = fetch(workbook_url(release, sess=sess), sess=sess).content
                observations.extend(parse_workbook(content, release))
            return _finish(observations, warnings, dry_run=dry_run, backups=backups)

    wanted = [r for r in listed if watermark is None or r.month >= watermark][:releases]
    observations: list[Obs] = []
    for release in wanted:
        content = fetch(workbook_url(release, sess=sess), sess=sess).content
        observations.extend(parse_workbook(content, release))

    return _finish(observations, warnings, dry_run=dry_run, backups=backups)


def _finish(observations, warnings, *, dry_run, backups):
    from ..sinks import long_csv

    reports = [
        long_csv.upsert(
            paths.consumption_csv(PREFIX), observations, dry_run=dry_run, backups=backups
        )
    ]
    for report in reports:
        report.warnings = warnings
    return reports
