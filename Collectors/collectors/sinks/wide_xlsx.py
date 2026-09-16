"""Merge weekly PIHPS prices into the wide per-year workbooks already uploaded.

These workbooks are the odd one out: everything else in ``Dataset/`` is long,
but ``Tabel Harga Berdasarkan Daerah <year>.xlsx`` is wide — one row per
commodity, one column per survey week — because that is the shape the PIHPS
portal exports.  The uploaded files are a byte-exact capture of one
``GetGridDataDaerah`` call, so an update is a merge into that same shape.

What the files look like, and therefore what must survive a write:

* exactly one sheet, named ``Sheet``, with the header row frozen;
* row 1 is ``No`` | ``Komoditas (Rp)`` | one ``DD/ MM/ YYYY`` per week — note
  the space after each slash, which is not what the API sends;
* 31 commodity rows in a two-level hierarchy: a Roman numeral in ``No`` marks a
  group, an Arabic numeral a variety within the group above it;
* **every cell is text**, prices included, carrying thousands commas
  (``'15,050'``).  The API returns them in exactly that form, so values pass
  straight through and never become floats;
* missing is the literal string ``'-'``.

The write is a fresh workbook rather than a ``load_workbook``/``save``
round-trip.  The uploaded files carry stale metadata from whatever exported
them — ``dimension`` claims ``A1:C1`` and a defined name points at
``$A$1:$F$6332``, neither of which describes the real grid — and there is no
reason to carry that forward.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..dates import parse_dmy

SHEET_NAME = "Sheet"
HEADER_NO = "No"
HEADER_COMMODITY = "Komoditas (Rp)"

#: How the portal writes "no report for this market this week".  A dash is
#: missing, not zero, and never carries forward.
MISSING = "-"

_WHITESPACE = re.compile(r"\s+")
_COLUMN_WIDTHS = {"A": 6.43, "B": 35.0}
_DATE_COLUMN_WIDTH = 8.86


def header_date(day: dt.date) -> str:
    """``date(2026, 1, 1)`` -> ``'01/ 01/ 2026'``, the on-disk spelling."""
    return f"{day.day:02d}/ {day.month:02d}/ {day.year:04d}"


def parse_header_date(text: object) -> dt.date | None:
    """Read either spelling: ``'01/ 01/ 2026'`` on disk, ``'01/01/2026'`` from the API."""
    if text is None:
        return None
    return parse_dmy(_WHITESPACE.sub("", str(text)))


def is_value(cell: object) -> bool:
    """True for a real price, false for a dash, a blank or nothing at all."""
    return bool(cell is not None and str(cell).strip() not in {"", MISSING})


@dataclass(frozen=True, slots=True)
class Row:
    """One commodity line, as the workbook spells it."""

    no: str
    name: str
    level: int

    @property
    def key(self) -> tuple[int, str]:
        """Match key: level plus a normalised name.

        Rows are matched on this, never on position.  The 31 labels happen to
        be identical across all 24 uploaded files, but BI reshapes tables
        without notice and a positional match fails silently by writing one
        commodity's price onto another.  Normalising also absorbs the trailing
        space in ``'Cabai Merah Keriting '`` -- which is still written back
        verbatim, because ``name`` keeps the original.
        """
        return (self.level, _WHITESPACE.sub(" ", self.name).strip().casefold())


@dataclass
class Grid:
    """A whole workbook sheet: its commodity rows and its weekly cells."""

    rows: list[Row] = field(default_factory=list)
    #: (row key, week) -> the cell text exactly as it should be written
    values: dict[tuple[tuple[int, str], dt.date], str] = field(default_factory=dict)

    @property
    def weeks(self) -> list[dt.date]:
        return sorted({week for _, week in self.values})

    def cell(self, row: Row, week: dt.date) -> str:
        return self.values.get((row.key, week), MISSING)

    def snapshot(self) -> tuple:
        """A comparable view, for deciding whether a write is needed at all."""
        return (
            tuple((row.no, row.name, row.level) for row in self.rows),
            tuple(sorted(((key, week.isoformat()), text) for (key, week), text in self.values.items())),
        )


@dataclass
class MergeReport:
    path: Path
    added_weeks: list[dt.date] = field(default_factory=list)
    revised: list[tuple[str, dt.date, str, str]] = field(default_factory=list)
    filled: int = 0
    added_rows: list[str] = field(default_factory=list)
    ignored_dashes: int = 0
    written: bool = False
    created: bool = False

    @property
    def changed(self) -> bool:
        return bool(self.added_weeks or self.revised or self.filled or self.added_rows)

    def describe(self) -> str:
        if not self.changed:
            return f"{self.path.name}: no change"
        parts = []
        if self.added_weeks:
            parts.append(
                f"{len(self.added_weeks)} new week(s) to "
                f"{max(self.added_weeks):%d %b %Y}"
            )
        if self.filled:
            parts.append(f"{self.filled} gap(s) filled")
        if self.revised:
            parts.append(f"{len(self.revised)} revised")
        if self.added_rows:
            parts.append(f"{len(self.added_rows)} new commodity: {', '.join(self.added_rows)}")
        prefix = "created" if self.created else "updated"
        return f"{self.path.name}: {prefix}, {', '.join(parts)}"


def read_grid(path: Path) -> Grid:
    """Load an existing workbook.  An absent file is an empty grid."""
    grid = Grid()
    if not Path(path).exists():
        return grid

    import openpyxl

    # Not ``read_only``: that mode trusts the sheet's declared ``dimension``,
    # and in these files the declaration is stale -- it claims ``A1:C1`` for a
    # 32-row, 39-column grid, so a read-only pass silently yields almost
    # nothing and the merge would blank the workbook.
    book = openpyxl.load_workbook(path, data_only=True)
    try:
        sheet = book[SHEET_NAME] if SHEET_NAME in book.sheetnames else book[book.sheetnames[0]]
        rows = list(sheet.iter_rows(values_only=True))
    finally:
        book.close()
    if not rows:
        return grid

    header = rows[0]
    weeks: dict[int, dt.date] = {}
    for index, cell in enumerate(header):
        if index < 2:
            continue
        week = parse_header_date(cell)
        if week is not None:
            weeks[index] = week

    for raw in rows[1:]:
        if raw is None or len(raw) < 2:
            continue
        no = "" if raw[0] is None else str(raw[0]).strip()
        name = "" if raw[1] is None else str(raw[1])
        if not name.strip():
            continue
        # A Roman numeral in the No column is a group total; an Arabic one is a
        # variety underneath it.  That is the file's own convention and it is
        # what lets a fetched row be matched to the right line.
        level = 1 if not no.strip().isdigit() else 2
        row = Row(no=no, name=name, level=level)
        grid.rows.append(row)
        for index, week in weeks.items():
            if index < len(raw):
                cell = raw[index]
                if cell is not None and str(cell).strip():
                    grid.values[(row.key, week)] = str(cell).strip()
    return grid


def existing_weeks(path: Path) -> list[dt.date]:
    """The week columns a workbook already has, oldest first.

    An incremental PIHPS fetch has to start from one of these and no other
    date: the portal re-anchors its weekly grid to whatever ``start_date`` it
    is given, so a start two days off this lattice comes back on a different
    weekday and would add a second, parallel set of columns.
    """
    return read_grid(Path(path)).weeks


def merge(existing: Grid, fetched: Grid, *, path: Path) -> tuple[Grid, MergeReport]:
    """Fold ``fetched`` into ``existing``, preserving anything it does not cover.

    The rules, in order of precedence:

    1. Row order and spelling come from the existing file.  A commodity the
       portal has stopped publishing keeps its history; a genuinely new one is
       appended after the group it belongs to and reported.
    2. Columns are the chronological union.  A week the API no longer returns
       is retained.
    3. A real fetched value replaces a real existing one -- PIHPS does revise --
       and the change is reported rather than applied silently.
    4. **A dash never overwrites a real value.**  ``'-'`` means the market did
       not report, which is not evidence that last week's price was wrong.
    """
    report = MergeReport(path=Path(path), created=not existing.rows)
    merged = Grid(rows=list(existing.rows), values=dict(existing.values))

    known = {row.key for row in merged.rows}
    for row in fetched.rows:
        if row.key in known:
            continue
        merged.rows.append(row)
        known.add(row.key)
        report.added_rows.append(row.name.strip())

    before = set(existing.weeks)
    for (key, week), text in fetched.values.items():
        current = merged.values.get((key, week))
        if not is_value(text):
            if is_value(current):
                report.ignored_dashes += 1
                continue
            merged.values.setdefault((key, week), MISSING)
            continue
        if current is None or not is_value(current):
            merged.values[(key, week)] = text
            if week in before:
                report.filled += 1
        elif current != text:
            merged.values[(key, week)] = text
            name = next((r.name.strip() for r in merged.rows if r.key == key), key[1])
            report.revised.append((name, week, current, text))

    report.added_weeks = sorted(set(merged.weeks) - before)
    return merged, report


def write_grid(path: Path, grid: Grid) -> None:
    """Write a fresh workbook matching the uploaded files' shape and styling."""
    import openpyxl
    from openpyxl.styles import Alignment, Font
    from openpyxl.utils import get_column_letter

    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = SHEET_NAME

    header_font = Font(bold=True, name="Calibri", size=11)
    header_align = Alignment(horizontal="center", vertical="top", wrap_text=True)
    body_align = Alignment(horizontal="left", vertical="top", wrap_text=True)

    weeks = grid.weeks
    for column, text in enumerate([HEADER_NO, HEADER_COMMODITY] + [header_date(w) for w in weeks], start=1):
        cell = sheet.cell(row=1, column=column, value=text)
        cell.font = header_font
        cell.alignment = header_align

    for index, row in enumerate(grid.rows, start=2):
        for column, text in enumerate([row.no, row.name] + [grid.cell(row, week) for week in weeks], start=1):
            # Written as text, never coerced: the portal's own export stores
            # every price as a string with thousands commas, and turning them
            # into numbers here would change the file's type profile and the
            # way every downstream reader sees it.
            cell = sheet.cell(row=index, column=column, value=str(text))
            cell.alignment = body_align

    for letter, width in _COLUMN_WIDTHS.items():
        sheet.column_dimensions[letter].width = width
    for column in range(3, len(weeks) + 3):
        sheet.column_dimensions[get_column_letter(column)].width = _DATE_COLUMN_WIDTH
    sheet.freeze_panes = "A2"

    # Pinned so the only run-to-run difference in the bytes is the zip's own
    # timestamps; the grid comparison in `write` is what actually prevents
    # pointless rewrites.
    book.properties.creator = "Indonesia-Indicators Collectors"
    book.properties.created = dt.datetime(2026, 1, 1)
    book.properties.modified = dt.datetime(2026, 1, 1)

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    book.save(path)


def write(path: Path, fetched: Grid, *, dry_run: bool = False, backups=None) -> MergeReport:
    """Merge and persist, skipping the write when nothing changed."""
    path = Path(path)
    existing = read_grid(path)
    merged, report = merge(existing, fetched, path=path)

    if path.exists() and merged.snapshot() == existing.snapshot():
        return report
    if dry_run:
        return report

    if backups is not None:
        backups.snapshot(path)
    write_grid(path, merged)
    report.written = True
    return report
