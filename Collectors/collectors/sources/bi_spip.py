"""BI payment and transaction system statistics (SPIP).

BI publishes this family as one ``.xlsx`` per table under
``/id/statistik/ekonomi-keuangan/spip/Documents/``, each holding the **full
monthly history** -- e-money back to 2009, the headline indicators to 2012 --
so one fetch both backfills and extends, and there is no pagination to walk.

Which file is live has changed twice, so both are read.  The tables were
``.xls``; in September 2026 every ``.xls`` URL began redirecting to BI's 404
page and only the ``.xlsx`` beside it was served; by November the ``.xls``
names were back and carrying new months, while the ``.xlsx`` copies stayed
frozen at their 18 September upload -- still answering 200, so the collector
ran green and found nothing.  Each run therefore fetches both and keeps
whichever reaches the later month.  BI's index links ``.xls`` throughout and
was wrong for two months, so it is not consulted.

Naming, because it is a trap: BI renamed "SPI" to SPIP and moved the tables;
the index now lives at ``/spip/Default.aspx`` (``/ssp/`` redirects there) and
``/spi/Default.aspx`` is gone.
OJK's "SPI" is an entirely different publication, collected in ``ojk_dpk.py``.

Normalisation is deliberately *not* done here.  Raw e-money and card growth is
adoption, not spending; counts and values are landed unaltered with their own
units so that anything reading the dataset can divide them itself.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import yaml

from .. import excelio, incremental, paths
from ..dates import normalise_unit
from ..http import FetchError, fetch
from ..model import Obs
from ._specs import RowSpec, unit_from_row

INDEX_URL = "https://www.bi.go.id/id/statistik/ekonomi-keuangan/spip/Default.aspx"
DOCUMENT_URL = "https://www.bi.go.id/id/statistik/ekonomi-keuangan/spip/Documents/{table}.{suffix}"
#: Every format BI has served a table in, the one its index links first; on a
#: tie in the newest month the earlier entry wins.
FORMATS = ("xls", "xlsx")
CONFIG_PATH = paths.CONFIG / "bi_spip.yaml"


@dataclass(frozen=True, slots=True)
class TableSpec:
    table: str
    title: str
    prefix: str
    rows: tuple[RowSpec, ...]

    @property
    def urls(self) -> tuple[str, ...]:
        return tuple(DOCUMENT_URL.format(table=self.table, suffix=suffix) for suffix in FORMATS)


def load_config(path: Path | str = CONFIG_PATH) -> tuple[TableSpec, ...]:
    with open(path, encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    return tuple(
        TableSpec(
            table=entry["table"],
            title=entry["title"],
            prefix=entry["prefix"],
            rows=tuple(RowSpec(**row) for row in entry["rows"]),
        )
        for entry in document["tables"]
    )


def _layout(content: bytes, spec: TableSpec):
    grids = excelio.load(content)
    grid = next(iter(grids.values()))
    year_row, period_row = excelio.detect_header(grid)
    columns = excelio.periods(grid, year_row, period_row)
    if not columns:
        raise excelio.WorkbookError(f"{spec.table}: no month columns found")
    return grid, period_row, columns


def latest_month(content: bytes, spec: TableSpec) -> dt.date:
    """The newest month a workbook has a column for."""
    _, _, columns = _layout(content, spec)
    return max(column.ref_date for column in columns)


def fetch_table(spec: TableSpec, *, sess=None) -> bytes:
    """The copy of a table that reaches the latest month, whichever format.

    A copy that cannot be fetched, or is not a workbook, is passed over as
    long as another one can be read: one of the two names being dead is the
    normal state of this source.
    """
    best: tuple[dt.date, bytes] | None = None
    problems: list[str] = []
    for url in spec.urls:
        try:
            content = fetch(url, sess=sess).content
            month = latest_month(content, spec)
        except (FetchError, excelio.WorkbookError) as exc:
            problems.append(f"{url}: {exc}")
            continue
        if best is None or month > best[0]:
            best = (month, content)
    if best is None:
        raise FetchError(
            f"{spec.table}: no readable copy -- " + "; ".join(problems), url=spec.urls[0]
        )
    return best[1]


def parse_table(content: bytes, spec: TableSpec, *, since: dt.date | None = None) -> list[Obs]:
    grid, period_row, columns = _layout(content, spec)

    out: list[Obs] = []
    unmatched = {row_spec.sub for row_spec in spec.rows}
    for row_index, label in excelio.data_rows(grid, period_row + 1):
        for row_spec in spec.rows:
            if not row_spec.matches(label):
                continue
            unmatched.discard(row_spec.sub)
            unit = normalise_unit(unit_from_row(grid, row_index), row_spec.unit)
            for column in columns:
                if since and column.ref_date < since:
                    continue
                value = excelio.number(grid.cell(row_index, column.col))
                if value is None:
                    continue
                out.append(
                    Obs(
                        series_id=f"{spec.prefix}.{row_spec.sub}",
                        ref_date=column.ref_date,
                        ref_period=column.ref_period,
                        value=value,
                        unit=unit,
                        notes={"table": spec.table, "label": label},
                    )
                )
    if unmatched:
        # A relabelled row otherwise just stops: the run stays green and the
        # series goes stale with nothing to say why.
        raise excelio.WorkbookError(
            f"{spec.table}: no row matches {sorted(unmatched)}; BI has most likely relabelled it"
        )
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
    """Fetch every SPIP table and upsert each prefix into its own dataset file.

    The download cannot be narrowed: each URL is a static workbook carrying the
    whole history, with no date parameter to ask for less.  What narrowing does
    is stop re-emitting months already on file, per target prefix -- the three
    files run to different months, so one watermark for all of them would
    either skip real gaps or re-read history needlessly.
    """
    from ..sinks import long_csv

    by_prefix: dict[str, list[Obs]] = {}
    for spec in load_config():
        window = since or incremental.auto_since(
            paths.consumption_csv(spec.prefix), spec.prefix, overlap=overlap, full=full
        )
        for obs in parse_table(fetch_table(spec, sess=sess), spec, since=window):
            by_prefix.setdefault(spec.prefix, []).append(obs)

    return [
        long_csv.upsert(
            paths.consumption_csv(prefix), observations, dry_run=dry_run, backups=backups
        )
        for prefix, observations in sorted(by_prefix.items())
    ]
