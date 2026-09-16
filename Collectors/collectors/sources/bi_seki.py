"""BI SEKI -- GDP by expenditure, and bank deposits by owner group.

Two of the requested datasets are reachable here without a BPS API key.

*Household consumption* is a BPS number, and the BPS WebAPI needs a credential.
BI republishes the quarterly national accounts in SEKI table **VII.3** (current
prices) and **VII.4** (constant prices) with BPS credited as the source.  The
number is the same; the route is not.  It carries its own ``bi_seki.*`` series
ids so that a future BPS collector can never silently mix with it.

*Deposits by owner* is the other, and it is the better answer to "total
deposits by households and businesses in banks".  OJK splits third-party funds
by instrument and by province but not by who owns them; SEKI table **I.18**
does, and ``Perseorangan`` against the two ``Badan Usaha Bukan Keuangan`` rows
is exactly the household-versus-business split.  It was last refreshed on
2026-09-03, where OJK's public channel stops at June 2025.

One trap worth knowing before summing anything: the groups **do not all add
up**.  ``households`` nests inside ``other_private_sector``, alongside
cooperatives and foundations, so adding the two double-counts.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import yaml

from .. import excelio, incremental, paths
from ..http import fetch
from ..model import Obs
from ._specs import RowSpec, pick_sheet

INDEX_URL = "https://www.bi.go.id/id/statistik/ekonomi-keuangan/seki/Default.aspx"
DOCUMENT_URL = "https://www.bi.go.id/SEKI/tabel/{table}.xls"
CONFIG_PATH = paths.CONFIG / "bi_seki.yaml"
PREFIX = "bi_seki"


@dataclass(frozen=True, slots=True)
class TableSpec:
    table: str
    title: str
    sheets: tuple[str, ...]
    prefix: str
    group: str
    unit: str
    rows: tuple[RowSpec, ...]
    stop_at: str = ""

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
            sheets=tuple(entry["sheets"]),
            prefix=entry["prefix"],
            group=entry["group"],
            unit=entry["unit"],
            rows=tuple(RowSpec(**row) for row in entry["rows"]),
            stop_at=entry.get("stop_at", ""),
        )
        for entry in document["tables"]
    )


def parse_table(content: bytes, spec: TableSpec, *, since: dt.date | None = None) -> list[Obs]:
    grids = excelio.load(content, "xls")
    grid = pick_sheet(grids, spec.sheets, spec.table)
    year_row, period_row = excelio.detect_header(grid, min_periods=4)
    columns = excelio.periods(grid, year_row, period_row)
    if not columns:
        raise excelio.WorkbookError(f"{spec.table}: no period columns found")

    # I.18 continues past the table into memo items that repeat the same
    # labels against a different population; stopping is not optional.
    stop_row = grid.nrows
    if spec.stop_at:
        found = grid.find_row(spec.stop_at, start=period_row + 1)
        if found is not None:
            stop_row = found

    out: list[Obs] = []
    claimed: set[str] = set()
    for row_index, label in excelio.data_rows(grid, period_row + 1):
        if row_index >= stop_row:
            break
        for row_spec in spec.rows:
            # First match wins: these tables repeat sub-category labels under
            # several parents, and the parent rows come first.
            if row_spec.sub in claimed or not row_spec.matches(label):
                continue
            claimed.add(row_spec.sub)
            for column in columns:
                if since and column.ref_date < since:
                    continue
                value = excelio.number(grid.cell(row_index, column.col))
                if value is None:
                    continue
                out.append(
                    Obs(
                        series_id=f"{spec.prefix}.{spec.group}.{row_spec.sub}",
                        ref_date=column.ref_date,
                        ref_period=column.ref_period,
                        value=value,
                        unit=spec.unit,
                        notes={"table": spec.table, "sheet": grid.name, "label": label},
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
    """Fetch the SEKI tables and upsert them into ``bi_seki.csv``.

    The watermark is per ``prefix.group`` rather than per file, because this one
    file holds monthly deposits alongside quarterly national accounts.  The
    newest monthly date is months ahead of the newest quarter, so narrowing on
    the file as a whole would skip quarters that are genuinely missing.
    """
    from ..sinks import long_csv

    observations: list[Obs] = []
    for spec in load_config():
        window = since or incremental.auto_since(
            paths.consumption_csv(spec.prefix),
            f"{spec.prefix}.{spec.group}",
            overlap=overlap,
            full=full,
        )
        payload = fetch(spec.url, sess=sess)
        observations.extend(parse_table(payload.content, spec, since=window))
    return [
        long_csv.upsert(
            paths.consumption_csv(PREFIX), observations, dry_run=dry_run, backups=backups
        )
    ]
