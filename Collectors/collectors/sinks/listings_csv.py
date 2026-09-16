"""Accumulate auction listings into a flat CSV, one row per listing.

This is the third sink, and it exists because the other two cannot carry this
shape.  ``long_csv`` is built on :class:`~collectors.model.Obs`, which has one
numeric payload field and an upsert key of ``(series_id, ref_date)``; a listing
is sixteen heterogeneous columns keyed by the auction's own id.  Forcing one
into the other would mean discarding every text field, or minting a thousand
one-observation "series" -- and in fact pointing ``long_csv`` at a listings file
collapses all of its rows onto a single empty key, which is why that sink now
refuses outright.

The two uploaded ibid files set the rules, and two of them differ from the
series CSVs next door:

* **LF line endings**, where ``bi_seki.csv`` and friends are CRLF.
* **Quoting**, because ``card_text`` contains commas.  ``QUOTE_MINIMAL``.

Also: ``sold`` is Python's ``True``/``False``, ``price_idr`` is a bare integer,
and row order is ``(page, position)`` ascending -- which is unique across both
files as uploaded, so sorting on it reproduces them exactly.

**Accumulating, never replacing.**  A listing is matched on its id, so a
re-scrape updates the mutable facts of a vehicle already on file and appends
the ones it has not seen.  Nothing is ever dropped: a vehicle that has been
sold and has left the site keeps its row, which is the point -- that is what
turns a listings page into a resale price series.

**Two columns are frozen at first sight**, and this is what makes a re-run a
no-op rather than a rewrite:

* ``scraped_at_utc`` records when a listing was *first* seen.  Stamping it
  afresh each run would change the file's bytes on every run even when no
  vehicle had changed, which would rewrite the file, and drop an identical
  backup snapshot every time.
* ``page`` and ``position`` record where the listing sat in the scrape that
  found it.  In an accumulating file they are provenance, not live state --
  today's page 1 is next month's page 5 -- so tracking the current pagination
  would churn every row whenever inventory shifted.

Everything else is updated in place: price, sold status, grade, title, dates,
image and card text.  Comparison is over the **whole row**, not one column, so
a vehicle that sells at an unchanged price still registers as a revision.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from ..model import LISTING_COLUMNS, Listing, SchemaError, listing_id

DEFAULT_HEADER: tuple[str, ...] = LISTING_COLUMNS

#: Written once, when a listing first appears, and carried across unchanged on
#: every later run.  See the module docstring.
FROZEN_COLUMNS = ("page", "position", "scraped_at_utc")

#: Columns where a blank from the site must not erase what is already on file.
#: Missing is missing, the same rule the food-price sink applies to its dashes:
#: ibid renders a placeholder image for listings whose photo is not published,
#: and taking that as the new value replaced real photo URLs with nothing.
#: Applied to every column, because a transient extraction failure should never
#: cost data that was successfully read before.
STICKY_WHEN_BLANK = True

#: Identifies a listings table, so this sink cannot be pointed at a series CSV.
_REQUIRED_COLUMNS = ("url", "price_idr", "sold")


class NotAListingsTable(SchemaError):
    """The target file is not a listings table, so this sink must not write it."""


def is_listings_table(header: Sequence[str]) -> bool:
    return all(name in header for name in _REQUIRED_COLUMNS)


@dataclass
class ListingReport:
    """What a write did, so a dry run can describe it without doing it."""

    path: Path
    added: int = 0
    revised: int = 0
    unchanged: int = 0
    #: Same auction id seen twice in one scrape; the later sighting is kept.
    duplicates: int = 0
    total: int = 0
    written: bool = False
    created: bool = False
    #: (listing id, field, old, new) -- the shape the CLI prints.
    revisions: list[tuple[str, str, str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.added or self.revised)

    def describe(self) -> str:
        if self.created:
            return f"{self.path.name}: created, {self.added} listings"
        if not self.changed:
            return f"{self.path.name}: no change ({self.total} listings)"
        parts = []
        if self.added:
            parts.append(f"{self.added} new")
        if self.revised:
            parts.append(f"{self.revised} updated")
        if self.duplicates:
            parts.append(f"{self.duplicates} duplicate(s) collapsed")
        return f"{self.path.name}: {', '.join(parts)} ({self.total} listings)"


def deduplicate(listings: Iterable[Listing]) -> tuple[list[Listing], int]:
    """One row per auction id within a run -- the LAST one wins.

    Opposite of the series sinks, and deliberately so.  A paginated scrape can
    legitimately see the same listing twice when inventory shifts between page
    requests, and the later sighting is the fresher state: a vehicle that sold
    mid-scrape should end up sold.
    """
    kept: dict[str, Listing] = {}
    total = 0
    for listing in listings:
        total += 1
        kept[listing.key] = listing
    return list(kept.values()), total - len(kept)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Header and rows of an existing listings CSV, values kept as read."""
    if not path.exists():
        return [], []
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        rows = [{name: (row.get(name) or "") for name in header} for row in reader]
    return header, rows


def _sort_key(row: dict[str, str]) -> tuple[int, int, str]:
    """``(page, position)`` ascending, numerically, with the id to break ties.

    The uploaded files are in exactly this order and their ``(page, position)``
    pairs are unique, so it reproduces them byte for byte.  Once frozen pages
    accumulate, new listings can repeat a pair, hence the tie-breaker.
    """
    def number(name: str) -> int:
        try:
            return int(row.get(name) or 0)
        except ValueError:
            return 0

    return (number("page"), number("position"), listing_id(row.get("url", "")))


def render(header: Sequence[str], rows: Iterable[dict[str, str]]) -> bytes:
    """The file's bytes: LF endings, minimal quoting, (page, position) order."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(list(header))
    for row in sorted(rows, key=_sort_key):
        writer.writerow([row.get(name, "") for name in header])
    return buffer.getvalue().encode("utf-8")


def upsert(
    path: Path,
    listings: Iterable[Listing],
    *,
    header: Sequence[str] | None = None,
    dry_run: bool = False,
    backups=None,
) -> ListingReport:
    """Merge ``listings`` into ``path``, keyed on the auction id.

    Listings already on file keep their frozen columns and their row if nothing
    substantive changed; the file is rewritten only when something actually
    differs, so a re-run is a no-op and leaves no backup snapshot.
    """
    path = Path(path)
    existing_header, rows = read_csv(path)
    created = not existing_header
    columns = list(existing_header or header or DEFAULT_HEADER)

    if not is_listings_table(columns):
        raise NotAListingsTable(
            f"{path.name} has columns {list(columns)}, which is not a listings table"
        )

    index = {listing_id(row.get("url", "")): row for row in rows}
    report = ListingReport(path=path, created=created)

    listings, report.duplicates = deduplicate(listings)
    for listing in listings:
        candidate = {name: listing.column(name) for name in columns}
        current = index.get(listing.key)
        if current is None:
            index[listing.key] = candidate
            report.added += 1
            continue
        # Provenance stays as first recorded; everything else follows the site.
        for name in FROZEN_COLUMNS:
            if name in candidate:
                candidate[name] = current.get(name, candidate[name])
        if STICKY_WHEN_BLANK:
            for name in columns:
                if not candidate.get(name, "") and current.get(name, ""):
                    candidate[name] = current[name]
        differences = [
            (name, current.get(name, ""), candidate[name])
            for name in columns
            if current.get(name, "") != candidate[name]
        ]
        if not differences:
            report.unchanged += 1
            continue
        for name, was, now in differences:
            report.revisions.append((listing.key, name, was, now))
        index[listing.key] = candidate
        report.revised += 1

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
