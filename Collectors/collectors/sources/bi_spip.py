"""BI payment and transaction system statistics (SPIP).

BI publishes this family as one ``.xls`` per table under
``/id/statistik/ekonomi-keuangan/spip/Documents/``, each holding the **full
monthly history** -- e-money back to 2009, the headline indicators to 2012 --
so one fetch both backfills and extends, and there is no pagination to walk.

Naming, because it is a trap: BI renamed "SPI" to SPIP and moved the tables;
the index now lives at ``/ssp/Default.aspx`` and ``/spi/Default.aspx`` is gone.
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
from ..http import fetch
from ..model import Obs
from ._specs import RowSpec, unit_from_row

INDEX_URL = "https://www.bi.go.id/id/statistik/ekonomi-keuangan/ssp/Default.aspx"
DOCUMENT_URL = "https://www.bi.go.id/id/statistik/ekonomi-keuangan/spip/Documents/{table}.xls"
CONFIG_PATH = paths.CONFIG / "bi_spip.yaml"


@dataclass(frozen=True, slots=True)
class TableSpec:
    table: str
    title: str
    prefix: str
    rows: tuple[RowSpec, ...]

    @property
    def url(self) -> str:
        return DOCUMENT_URL.format(table=self.table)


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


def parse_table(content: bytes, spec: TableSpec, *, since: dt.date | None = None) -> list[Obs]:
    grids = excelio.load(content, "xls")
    grid = next(iter(grids.values()))
    year_row, period_row = excelio.detect_header(grid)
    columns = excelio.periods(grid, year_row, period_row)
    if not columns:
        raise excelio.WorkbookError(f"{spec.table}: no month columns found")

    out: list[Obs] = []
    for row_index, label in excelio.data_rows(grid, period_row + 1):
        for row_spec in spec.rows:
            if not row_spec.matches(label):
                continue
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

    The download cannot be narrowed: each URL is a static ``.xls`` carrying the
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
        payload = fetch(spec.url, sess=sess)
        for obs in parse_table(payload.content, spec, since=window):
            by_prefix.setdefault(spec.prefix, []).append(obs)

    return [
        long_csv.upsert(
            paths.consumption_csv(prefix), observations, dry_run=dry_run, backups=backups
        )
        for prefix, observations in sorted(by_prefix.items())
    ]
