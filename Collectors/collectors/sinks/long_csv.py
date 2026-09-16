"""Upsert observations into a long/tidy CSV without disturbing the rest of it.

The four files already in ``Dataset/Consumption`` set the rules, and they are
not uniform:

* ``bi_seki.csv`` carries eight columns
  (``series_id,geo_id,geo_name,ref_date,ref_period,frequency,value,unit``);
  the other three carry six, with no ``ref_period`` or ``frequency``.
  **The file's own header wins** — a six-column file is never "upgraded".
* Line endings are CRLF throughout, including the final line.
* Rows are ordered by ``series_id`` then ``ref_date``, so appending to the tail
  would only ever be correct for the alphabetically last series.  A write is a
  full rewrite in sorted order.
* Values are full-precision reprs (``819.1179999999999``).  Rows this run did
  not touch are re-emitted as the exact strings that were read, never parsed to
  float and back, so untouched history cannot drift.
* ``geo_id`` is the four-character string ``0000``; parsing it as an integer
  would strip the leading zeros.

Quarterly dating is *per file* and is preserved, not normalised: ``bi_seki.csv``
dates a quarter to its start month and flags it ``Q``/``quarterly``, while
``bi_payment_system.csv`` has no frequency column and dates its two ``percent``
ratio series to the quarter-end month.  Both are correct as published.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from ..model import Obs, SchemaError

#: The column set for a dataset file this tool creates.  Existing files keep
#: whatever header they already have.
DEFAULT_HEADER: tuple[str, ...] = (
    "series_id",
    "geo_id",
    "geo_name",
    "ref_date",
    "ref_period",
    "frequency",
    "value",
    "unit",
)

_KEY_COLUMNS = ("series_id", "ref_date")

#: The columns that make a file a long series table.  Checked before writing,
#: because pointing this sink at some other CSV is catastrophic rather than
#: merely wrong: every row of, say, a listings file has an empty ``series_id``
#: and ``ref_date``, so all of them collapse onto one upsert key and the file
#: is rewritten as a single row.
_REQUIRED_COLUMNS = ("series_id", "ref_date", "value")


class NotALongTable(SchemaError):
    """The target file is not a long series table, so this sink must not write it."""


def is_long_table(header: Sequence[str]) -> bool:
    """True when a header has the columns a long series table is keyed on."""
    return all(name in header for name in _REQUIRED_COLUMNS)


@dataclass
class UpsertReport:
    """What a write did, so a dry run can describe it without doing it."""

    path: Path
    added: int = 0
    revised: int = 0
    unchanged: int = 0
    #: Same reading listed twice in one run -- a payload defect, not a revision.
    duplicates: int = 0
    total: int = 0
    written: bool = False
    created: bool = False
    revisions: list[tuple[str, str, str, str]] = field(default_factory=list)
    #: Things the run should surface but that are not failures -- a source that
    #: is readable but has published nothing for months, for instance.
    warnings: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.added or self.revised)

    def describe(self) -> str:
        if self.created:
            return f"{self.path.name}: created, {self.added} rows"
        if not self.changed:
            return f"{self.path.name}: no change ({self.total} rows)"
        parts = []
        if self.added:
            parts.append(f"{self.added} new")
        if self.revised:
            parts.append(f"{self.revised} revised")
        if self.duplicates:
            parts.append(f"{self.duplicates} duplicate(s) dropped")
        return f"{self.path.name}: {', '.join(parts)} ({self.total} rows)"


def deduplicate(observations: Iterable[Obs]) -> tuple[list[Obs], int]:
    """One reading per ``(series_id, ref_date)``, first wins, and say how many went.

    A source that lists the same reading twice in one run must not be reported
    as revising the file: before this existed, the merge loop saw the second
    copy as a change to the first and counted a revision that never happened.
    First wins rather than last because the duplicate is a defect in the
    payload, not a restatement -- there is nothing to say the later copy is the
    better one.
    """
    seen: set[tuple[str, str]] = set()
    kept: list[Obs] = []
    total = 0
    for obs in observations:
        total += 1
        if obs.key in seen:
            continue
        seen.add(obs.key)
        kept.append(obs)
    return kept, total - len(kept)


def latest_ref_date(path: Path, prefix: str | None = None) -> dt.date | None:
    """The newest ``ref_date`` already on file, for an incremental collector.

    ``prefix`` narrows to one series family, because a file can hold more than
    one -- ``qris_transactions.csv`` carries both a collector's ids and a
    hand-transcribed set, and the newest date of one says nothing about the
    other.  ``None`` when the file does not exist or holds nothing matching, so
    a caller falls back to a full pass.
    """
    _, rows = read_csv(Path(path))
    dates = [
        row["ref_date"]
        for row in rows
        if row.get("ref_date")
        and (prefix is None or row.get("series_id", "").startswith(prefix))
    ]
    if not dates:
        return None
    try:
        return dt.date.fromisoformat(max(dates))
    except ValueError:
        return None


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Header and rows of an existing long CSV, values kept as read."""
    if not path.exists():
        return [], []
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        rows = [{name: (row.get(name) or "") for name in header} for row in reader]
    return header, rows


def render(header: Sequence[str], rows: Iterable[dict[str, str]]) -> bytes:
    """The file's bytes: CRLF, no quoting, sorted by series then date."""
    ordered = sorted(rows, key=lambda row: (row.get("series_id", ""), row.get("ref_date", "")))
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(list(header))
    for row in ordered:
        writer.writerow([row.get(name, "") for name in header])
    return buffer.getvalue().encode("utf-8")


def upsert(
    path: Path,
    observations: Iterable[Obs],
    *,
    header: Sequence[str] | None = None,
    dry_run: bool = False,
    backups=None,
) -> UpsertReport:
    """Merge ``observations`` into ``path`` on ``(series_id, ref_date)``.

    Existing rows the observations do not mention are left exactly as they are.
    The file is rewritten only when something actually changed, so a re-run is
    a no-op and leaves no backup snapshot.
    """
    path = Path(path)
    existing_header, rows = read_csv(path)
    created = not existing_header
    columns = list(existing_header or header or DEFAULT_HEADER)

    if not is_long_table(columns):
        raise NotALongTable(
            f"{path.name} has columns {list(columns)}, which is not a long series "
            f"table; this sink would collapse every row onto one key"
        )

    index = {tuple(row.get(name, "") for name in _KEY_COLUMNS): row for row in rows}
    report = UpsertReport(path=path, created=created)

    observations, report.duplicates = deduplicate(observations)
    for obs in observations:
        candidate = {name: obs.column(name) for name in columns}
        current = index.get(obs.key)
        if current is None:
            index[obs.key] = candidate
            report.added += 1
        elif current.get("value", "") != candidate.get("value", ""):
            report.revisions.append(
                (obs.series_id, obs.ref_date.isoformat(), current.get("value", ""), candidate["value"])
            )
            # A revision replaces the row wholesale: a restated value can come
            # with a corrected unit, and leaving half the old row would make
            # the file internally inconsistent.
            index[obs.key] = candidate
            report.revised += 1
        else:
            report.unchanged += 1

    merged = list(index.values())
    report.total = len(merged)
    payload = render(columns, merged)
    on_disk = path.read_bytes() if path.exists() else b""
    if payload == on_disk:
        return report
    if dry_run:
        report.written = False
        return report

    if backups is not None:
        backups.snapshot(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    report.written = True
    return report
