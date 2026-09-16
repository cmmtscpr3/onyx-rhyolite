"""The one row shape every collector produces.

The datasets in ``Dataset/Consumption`` are long/tidy: one row per date per
series.  An ``Obs`` is exactly that row, before it is rendered into whichever
column set the target file already uses.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

NATIONAL = "0000"
NATIONAL_NAME = "Indonesia (national)"

#: ``ref_period`` -> the spelling the ``frequency`` column uses.
FREQUENCY = {
    "D": "daily",
    "W": "weekly",
    "M": "monthly",
    "Q": "quarterly",
    "A": "annual",
}


class SchemaError(ValueError):
    """An observation that must not reach a dataset file."""


@dataclass(frozen=True, slots=True)
class Obs:
    """One reading of one series at one date."""

    series_id: str
    ref_date: dt.date
    value: float
    unit: str
    ref_period: str = "M"
    geo_id: str = NATIONAL
    geo_name: str = NATIONAL_NAME
    #: Provenance that does not belong in the canonical columns.  Never written.
    notes: dict[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        if not self.series_id:
            raise SchemaError("series_id is empty")
        if not self.geo_id:
            raise SchemaError(f"{self.series_id}: geo_id is empty")
        # A datetime would serialise with a time component and break the
        # (series_id, ref_date) upsert key against existing YYYY-MM-DD rows.
        if not isinstance(self.ref_date, dt.date) or isinstance(self.ref_date, dt.datetime):
            raise SchemaError(f"{self.series_id}: ref_date must be a date, not {self.ref_date!r}")
        if self.ref_period not in FREQUENCY:
            raise SchemaError(f"{self.series_id}: unknown ref_period {self.ref_period!r}")
        if self.value is None or self.value != self.value:  # NaN guard
            raise SchemaError(f"{self.series_id} at {self.ref_date}: value is not a number")
        if not self.unit:
            raise SchemaError(f"{self.series_id}: unit is empty")

    @property
    def key(self) -> tuple[str, str]:
        """The upsert key: the same reading of the same thing."""
        return (self.series_id, self.ref_date.isoformat())

    @property
    def frequency(self) -> str:
        return FREQUENCY[self.ref_period]

    def column(self, name: str) -> str:
        """This observation rendered into one named CSV column."""
        if name == "series_id":
            return self.series_id
        if name == "geo_id":
            return self.geo_id
        if name == "geo_name":
            return self.geo_name
        if name == "ref_date":
            return self.ref_date.isoformat()
        if name == "ref_period":
            return self.ref_period
        if name == "frequency":
            return self.frequency
        if name == "unit":
            return self.unit
        if name == "value":
            # repr of a float is the shortest string that round-trips, which is
            # the form already on disk (819.1179999999999, 3865581.295).  Never
            # round or reformat: the existing precision is data.
            return repr(float(self.value))
        raise SchemaError(f"no rule for column {name!r}")


#: The 16 columns the uploaded ibid files already use, in their order.
LISTING_COLUMNS: tuple[str, ...] = (
    "page",
    "position",
    "grade",
    "title",
    "year_build",
    "price_raw",
    "price_idr",
    "listed_raw",
    "listed_left",
    "listed_right",
    "sold",
    "sold_label",
    "url",
    "image",
    "scraped_at_utc",
    "card_text",
)


def listing_id(url: str) -> str:
    """The auction's own id, from the last path segment of its url.

    ``.../detail-lelang/motor/honda-beat---110--2019---at-/722340913165?entry_point=Product Listing``
    identifies listing ``722340913165``.  Taking the id rather than the whole
    url means the ``entry_point`` tracking parameter -- which the site varies
    and which contains a literal space -- cannot split one listing into two
    rows.  It is unique across every row of both uploaded files.
    """
    path = str(url or "").split("?", 1)[0].rstrip("/")
    tail = path.rsplit("/", 1)[-1]
    return tail if tail.isdigit() else path


@dataclass(frozen=True, slots=True)
class Listing:
    """One vehicle in one auction listing.

    Unlike :class:`Obs` this is not a time series: it is a record with a dozen
    heterogeneous fields, keyed by the auction's own id.  Hence its own sink.
    """

    url: str
    page: int
    position: int
    grade: str = ""
    title: str = ""
    year_build: str = ""
    price_raw: str = ""
    price_idr: int | None = None
    listed_raw: str = ""
    listed_left: str = ""
    listed_right: str = ""
    sold: bool = False
    sold_label: str = ""
    image: str = ""
    #: When this listing was *first* seen.  Written to ``scraped_at_utc`` and
    #: never refreshed -- see the sink for why that matters.
    scraped_at: str = ""
    card_text: str = ""

    def __post_init__(self) -> None:
        if not str(self.url).strip():
            raise SchemaError("listing has no url, so it cannot be identified")
        if self.page is None or self.position is None:
            raise SchemaError(f"{self.key}: page and position are required")
        if self.price_idr is not None and self.price_idr < 0:
            raise SchemaError(f"{self.key}: price_idr is negative")

    @property
    def key(self) -> str:
        """The upsert key: this auction's id."""
        return listing_id(self.url)

    def column(self, name: str) -> str:
        """This listing rendered into one named CSV column."""
        if name == "page":
            return str(self.page)
        if name == "position":
            return str(self.position)
        if name == "grade":
            return self.grade
        if name == "title":
            return self.title
        if name == "year_build":
            return self.year_build
        if name == "price_raw":
            return self.price_raw
        if name == "price_idr":
            # Blank rather than 0 when the card carried no figure: a missing
            # price is missing, and zero is a price.
            return "" if self.price_idr is None else str(int(self.price_idr))
        if name == "listed_raw":
            return self.listed_raw
        if name == "listed_left":
            return self.listed_left
        if name == "listed_right":
            return self.listed_right
        if name == "sold":
            # The uploaded files carry Python's own repr, not true/false.
            return "True" if self.sold else "False"
        if name == "sold_label":
            return self.sold_label
        if name == "url":
            return self.url
        if name == "image":
            return self.image
        if name == "scraped_at_utc":
            return self.scraped_at
        if name == "card_text":
            return self.card_text
        raise SchemaError(f"no rule for column {name!r}")
