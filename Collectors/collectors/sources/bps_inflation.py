"""BPS national inflation: headline, core, administered prices and volatile food.

Month-to-month and year-to-date rates from BPS static table 908, *Inflasi
Umum, Inti, Harga Diatur Pemerintah, dan Bergejolak Nasional (M-to-M dan
Y-to-D)*, which runs from 2009.

**BPS serves this table to browsers only.**  ``www.bps.go.id`` answers any
other client with a Cloudflare challenge (HTTP 403, "Just a moment..."), and
its WebAPI answers networks outside Indonesia -- GitHub's runners included --
with a "Perimeter WAF Block" before a key is even looked at.  So there is no
live fetch here, only a page saved from a browser::

    python Collectors/run.py inflation --html bps_inflasi.html

Open the table, wait for it to render, and save the page; any copy whose
markup holds the table will do.

**The parser assumes no layout.**  It was written before a saved copy of the
page was available, and BPS reshapes tables without notice, so rather than read
fixed rows and columns it places every number by the labels around it: the text
cells to its left in its row, and the header cells above it in its column.
Merged cells are spread over everything they span, a blank row label inherits
the one above it, and a label naming more than one of a thing -- the title's
"Umum, Inti, Harga Diatur Pemerintah, dan Bergejolak", or "2009-2026" -- names
none of them.  For each of year, month, component and measure the nearest label
that names exactly one wins, looking along the row first and then up the column.
A number is kept only when all four are named, whichever way round the table
puts them.

Two identities check that numbers were read under the right headings, since a
column read under its neighbour's still looks like inflation:

* January's y-to-d *is* its m-to-m, because the year starts that month.  That
  catches a rate read under another component's heading.
* Each later month compounds, ``(1 + ytd[m-1]) (1 + mtm[m]) = 1 + ytd[m]``, to
  the two decimals BPS publishes.  That catches what January cannot: m-to-m
  and y-to-d read under each other's headings, which January leaves equal.

BPS derives all four components' rates from index series, so both hold for
every month of a table read correctly.  When either breaks for most of the
months it can be checked on, the table was misread and nothing is written; a
stray break is reported and the rest kept.

Nothing parsed means nothing written.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from .. import paths
from ..dates import MONTHS, clean_label, month_start
from ..errors import SourceUnavailable
from ..model import Obs

URL = (
    "https://www.bps.go.id/id/statistics-table/1/OTA4IzE=/inflasi-umum--inti--harga-diatur-"
    "pemerintah--dan-bergejolak-nasional--m-to-m-dan-y-to-d---2009-2026.html"
)
PREFIX = "bps_inflation"
UNIT = "percent"

#: Series suffix -> the words that name the component on BPS pages, Indonesian
#: first.  Matched as whole words on a folded label.
COMPONENTS: dict[str, tuple[str, ...]] = {
    "headline": ("umum", "headline"),
    "core": ("inti", "core"),
    "administered": ("diatur pemerintah", "administered"),
    "volatile": ("bergejolak", "volatile"),
}

#: Series suffix -> spellings of the measure, matched on a label with every
#: non-alphanumeric removed, so "M-to-M", "M to M" and "MtM" all read alike.
MEASURES: dict[str, tuple[str, ...]] = {
    "mtm": ("mtom", "mtm", "monthtomonth", "bulanan"),
    "ytd": ("ytod", "ytd", "yeartodate", "tahunkalender"),
    "yoy": ("yony", "yoy", "yearonyear"),
}

#: Rates are published to two decimals, so an identity can be off by the
#: rounding of the three numbers in it and no more.
TOLERANCE = 0.02

_YEAR = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
_NUMBER = re.compile(r"[+-]?(?:\d+(?:[.,]\d+)?|[.,]\d+)")
_WORD = re.compile(r"[a-z]+")
_SPACE_TAGS = frozenset({"br", "p", "div", "li"})


class TableError(ValueError):
    """The table was found and read, but its numbers do not hang together."""


# -------------------------------------------------------------- the markup
class _Tables(HTMLParser):
    """Every ``<table>`` in a page, as rows of ``(text, colspan, rowspan)``."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[tuple[str, int, int]]]] = []
        self._open: list[list[list[tuple[str, int, int]]]] = []
        self._cell: list[str] | None = None
        self._span = (1, 1)

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._close_cell()
            self._open.append([])
        elif not self._open:
            return
        elif tag == "tr":
            self._close_cell()
            self._open[-1].append([])
        elif tag in ("td", "th"):
            self._close_cell()
            found = dict(attrs)
            self._cell = []
            self._span = (_span(found.get("colspan")), _span(found.get("rowspan")))
        elif tag in _SPACE_TAGS and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if not self._open:
            return
        if tag in ("td", "th", "tr"):
            self._close_cell()
        elif tag == "table":
            self._close_cell()
            self.tables.append(self._open.pop())
        elif tag in _SPACE_TAGS and self._cell is not None:
            self._cell.append(" ")

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def _close_cell(self) -> None:
        if self._cell is None or not self._open:
            return
        rows = self._open[-1]
        if not rows:
            rows.append([])
        rows[-1].append((clean_label("".join(self._cell)), *self._span))
        self._cell = None


def _span(value: str | None) -> int:
    """A colspan or rowspan; anything missing, zero or absurd counts as 1."""
    return int(value) if value and value.strip().isdigit() and 0 < int(value) <= 500 else 1


def tables(markup: str) -> list[list[list[str]]]:
    """Every table in the page as a rectangular grid of cell text.

    A merged cell is written into every position it spans, so a year heading
    over eight columns labels all eight, and a year stacked over twelve rows
    labels all twelve.
    """
    reader = _Tables()
    reader.feed(markup)
    reader.close()
    return [_grid(rows) for rows in reader.tables]


def _grid(rows: list[list[tuple[str, int, int]]]) -> list[list[str]]:
    grid: list[list[str | None]] = []
    for r, row in enumerate(rows):
        while len(grid) <= r:
            grid.append([])
        c = 0
        for text, colspan, rowspan in row:
            # Skip the positions a rowspan from above already holds.
            while c < len(grid[r]) and grid[r][c] is not None:
                c += 1
            for dr in range(rowspan):
                while len(grid) <= r + dr:
                    grid.append([])
                line = grid[r + dr]
                if len(line) < c + colspan:
                    line.extend([None] * (c + colspan - len(line)))
                for dc in range(colspan):
                    line[c + dc] = text
            c += colspan
    width = max((len(line) for line in grid), default=0)
    return [[cell or "" for cell in line] + [""] * (width - len(line)) for line in grid]


# -------------------------------------------------------------- the labels
def value(text: str) -> float | None:
    """A rate from a cell, whether BPS wrote a decimal comma or a point.

    A bare year is a label, never a value: it sits beside the rates in the
    same column of row headings.
    """
    compact = clean_label(text).replace("\u2212", "-").replace(" ", "").removesuffix("%")
    if not compact or _YEAR.fullmatch(compact) or not _NUMBER.fullmatch(compact):
        return None
    return float(compact.replace(",", "."))


@dataclass(frozen=True, slots=True)
class Label:
    """What one heading cell names, each as a set so that a heading naming two
    of something -- a title, a range -- can be told from one naming one."""

    text: str
    years: frozenset[int]
    months: frozenset[int]
    components: frozenset[str]
    measures: frozenset[str]

    @classmethod
    def read(cls, text: str) -> Label:
        lowered = text.lower()
        words = " ".join(re.findall(r"[a-z0-9]+", lowered))
        squeezed = words.replace(" ", "")
        return cls(
            text=text,
            years=frozenset(int(y) for y in _YEAR.findall(text)),
            months=frozenset(MONTHS[w] for w in _WORD.findall(lowered) if w in MONTHS),
            components=frozenset(
                name
                for name, spellings in COMPONENTS.items()
                if any(re.search(rf"\b{re.escape(s)}\b", words) for s in spellings)
            ),
            measures=frozenset(
                name for name, spellings in MEASURES.items() if any(s in squeezed for s in spellings)
            ),
        )


_FACETS = ("years", "months", "components", "measures")


def _nearest(labels: list[Label], facet: str):
    """The first label, nearest first, that names exactly one of ``facet``."""
    for label in labels:
        named = getattr(label, facet)
        if len(named) == 1:
            return next(iter(named))
    return None


# ------------------------------------------------------------ the placing
@dataclass(slots=True)
class Placed:
    observations: list[Obs]
    #: Numbers the labels could not place, by what was missing.
    unplaced: Counter
    examples: dict[str, str]


def place(grid: list[list[str]]) -> Placed:
    """Every number in ``grid`` that its labels name completely, as an ``Obs``."""
    values = [[value(cell) for cell in row] for row in grid]
    labels = [
        [Label.read(cell) if cell and v is None else None for cell, v in zip(row, vrow)]
        for row, vrow in zip(grid, values)
    ]

    # A row heading left blank inherits the one above it: BPS writes a year
    # once and leaves the next eleven rows empty.  Only in columns that hold
    # headings and never a number, so a missing rate is never filled in, and a
    # column of row numbers does not hide the headings beside it.
    rows = [r for r, vrow in enumerate(values) if any(v is not None for v in vrow)]
    width = len(grid[0]) if grid else 0
    heading_columns = [
        c
        for c in range(width)
        if any(labels[r][c] is not None for r in rows)
        and all(values[r][c] is None for r in rows)
    ]
    carried: dict[int, Label] = {}
    for r in rows:
        for c in heading_columns:
            if labels[r][c] is not None:
                carried[c] = labels[r][c]
            elif c in carried:
                labels[r][c] = carried[c]

    found: dict[tuple[str, dt.date], Obs] = {}
    unplaced: Counter = Counter()
    examples: dict[str, str] = {}
    for r, vrow in enumerate(values):
        for c, rate in enumerate(vrow):
            if rate is None:
                continue
            around = [labels[r][k] for k in range(c - 1, -1, -1) if labels[r][k] is not None]
            around += [labels[k][c] for k in range(r - 1, -1, -1) if labels[k][c] is not None]
            year, month, component, measure = (_nearest(around, facet) for facet in _FACETS)
            missing = [
                facet.rstrip("s")
                for facet, got in zip(_FACETS, (year, month, component, measure))
                if got is None
            ]
            if missing:
                reason = "no " + " or ".join(missing)
                unplaced[reason] += 1
                examples.setdefault(
                    reason, f"{grid[r][c]!r} at row {r + 1}, column {c + 1}, under {[l.text for l in around[:4]]}"
                )
                continue
            obs = Obs(
                series_id=f"{PREFIX}.{component}.{measure}",
                ref_date=month_start(year, month),
                value=rate,
                unit=UNIT,
                notes={"table": 908, "cell": (r + 1, c + 1)},
            )
            earlier = found.setdefault(obs.key, obs)
            if earlier.value != obs.value:
                raise TableError(
                    f"{obs.series_id} {obs.ref_date:%Y-%m} is {earlier.value} at cell "
                    f"{earlier.notes['cell']} and {obs.value} at {obs.notes['cell']}: "
                    f"two numbers carry the same labels, so the table was misread"
                )
    return Placed(list(found.values()), unplaced, examples)


# ------------------------------------------------------------ the checking
def check(observations: list[Obs]) -> list[str]:
    """Warnings for the identities the rates must satisfy; raises when either
    breaks for most of the months it can be checked on, because then the
    numbers were read under the wrong headings."""
    rates = {(o.series_id, o.ref_date): o.value for o in observations}
    components = sorted({o.series_id.split(".")[1] for o in observations})
    years = sorted({o.ref_date.year for o in observations})

    january_breaks, january_checked, compound_breaks, compound_checked = [], 0, [], 0
    for component in components:
        mtm, ytd = f"{PREFIX}.{component}.mtm", f"{PREFIX}.{component}.ytd"
        for year in years:
            jan = dt.date(year, 1, 1)
            if (mtm, jan) in rates and (ytd, jan) in rates:
                january_checked += 1
                if abs(rates[mtm, jan] - rates[ytd, jan]) > TOLERANCE:
                    january_breaks.append(f"{component} {year}")
            for month in range(2, 13):
                now, before = dt.date(year, month, 1), dt.date(year, month - 1, 1)
                if not all(key in rates for key in ((ytd, before), (mtm, now), (ytd, now))):
                    continue
                compound_checked += 1
                implied = ((1 + rates[ytd, before] / 100) * (1 + rates[mtm, now] / 100) - 1) * 100
                if abs(implied - rates[ytd, now]) > TOLERANCE:
                    compound_breaks.append(f"{component} {now:%Y-%m}")

    if january_checked and len(january_breaks) * 2 > january_checked:
        raise TableError(
            f"January's y-to-d differs from its m-to-m in {len(january_breaks)} of "
            f"{january_checked} years ({', '.join(january_breaks[:4])}...), so rates were "
            f"read under another component's heading; nothing written"
        )
    if compound_checked and len(compound_breaks) * 2 > compound_checked:
        raise TableError(
            f"y-to-d does not compound from m-to-m in {len(compound_breaks)} of "
            f"{compound_checked} months ({', '.join(compound_breaks[:4])}...), so the two "
            f"measures were read under each other's headings; nothing written"
        )
    warnings = []
    if january_breaks:
        warnings.append(f"January y-to-d differs from m-to-m for {', '.join(january_breaks)}")
    if compound_breaks:
        warnings.append(
            f"y-to-d does not compound from m-to-m for {len(compound_breaks)} month(s), "
            f"first {', '.join(compound_breaks[:3])}"
        )
    return warnings


# ------------------------------------------------------------ the entry
def parse(markup: str) -> tuple[list[Obs], list[str]]:
    """Every observation the saved page yields, and anything worth a warning."""
    grids = [grid for grid in tables(markup) if grid]
    if not grids:
        if "just a moment" in markup.lower():
            raise SourceUnavailable(
                "the saved page is Cloudflare's challenge, not the table: open it in a "
                "browser, wait for the table to appear, then save it"
            )
        raise SourceUnavailable("the saved page holds no table; save it once the table has rendered")

    # Only a table that names a component is the inflation table; a page's
    # other tables would otherwise fill the report with numbers skipped.
    inflation = [grid for grid in grids if any(Label.read(cell).components for row in grid for cell in row)]
    if not inflation:
        raise SourceUnavailable("the saved page holds no table naming an inflation component")

    observations: dict[tuple[str, dt.date], Obs] = {}
    unplaced: Counter = Counter()
    examples: dict[str, str] = {}
    for grid in inflation:
        placed = place(grid)
        unplaced.update(placed.unplaced)
        for reason, example in placed.examples.items():
            examples.setdefault(reason, example)
        for obs in placed.observations:
            earlier = observations.setdefault(obs.key, obs)
            if earlier.value != obs.value:
                raise TableError(
                    f"{obs.series_id} {obs.ref_date:%Y-%m} reads {earlier.value} in one table "
                    f"and {obs.value} in another"
                )

    if not observations:
        # The right table, read wrongly: a failure to see, not a skip.
        detail = "; ".join(f"{n} with {reason}, e.g. {examples[reason]}" for reason, n in unplaced.items())
        raise TableError(
            "found the inflation table but could not name a year, month, component and "
            f"measure for any number in it ({detail or 'it holds no numbers'})"
        )

    found = sorted(observations.values(), key=lambda o: (o.series_id, o.ref_date))
    warnings = check(found)
    for reason, n in unplaced.most_common():
        warnings.append(f"skipped {n} number(s) with {reason}, e.g. {examples[reason]}")
    return found, warnings


def read_saved(path: Path | str) -> tuple[list[Obs], list[str]]:
    """Parse a page saved from a browser.  No network, and fully testable."""
    return parse(Path(path).read_text(encoding="utf-8", errors="replace"))


def collect(
    *,
    sess=None,
    since: dt.date | None = None,
    dry_run: bool = False,
    backups=None,
    html: str | None = None,
):
    """Parse a saved copy of the table into ``bps_inflation.csv``."""
    from ..sinks import long_csv

    if not html:
        raise SourceUnavailable(
            "BPS serves this table only to a browser; save the page and run "
            "`run.py inflation --html PATH`"
        )
    observations, warnings = read_saved(html)
    if since:
        observations = [obs for obs in observations if obs.ref_date >= since]
    report = long_csv.upsert(
        paths.consumption_csv(PREFIX), observations, dry_run=dry_run, backups=backups
    )
    report.warnings.extend(warnings)
    return [report]
