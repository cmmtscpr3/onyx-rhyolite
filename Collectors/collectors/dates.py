"""Date parsing shared across collectors.

Indonesian sources write dates in at least four shapes: ``dd/mm/yyyy`` from
PIHPS, Indonesian month names from BI workbooks, three-letter English
abbreviations in the same workbooks, and ISO from JSON APIs.
"""

from __future__ import annotations

import datetime as dt
import re

#: Indonesian month names and the abbreviations BI and OJK actually use,
#: including the English ones that appear in the same header rows.
MONTHS: dict[str, int] = {}
for _index, _names in enumerate(
    [
        ("januari", "jan", "january"),
        ("februari", "feb", "pebruari", "february"),
        ("maret", "mar", "march"),
        ("april", "apr"),
        ("mei", "may"),
        ("juni", "jun", "june"),
        ("juli", "jul", "july"),
        ("agustus", "agu", "ags", "aug", "agt", "august"),
        ("september", "sep", "sept"),
        ("oktober", "okt", "oct", "october"),
        ("november", "nov", "nopember"),
        ("desember", "des", "dec", "december"),
    ],
    start=1,
):
    for _name in _names:
        MONTHS[_name] = _index

#: Quarter labels, as they appear in SEKI headers.
QUARTERS = {"q1": 1, "q2": 2, "q3": 3, "q4": 4, "tw1": 1, "tw2": 2, "tw3": 3, "tw4": 4}

_WHITESPACE = re.compile(r"[\u00a0\s]+")
#: Footnote and provisional marks BI and OJK append to labels: ``Mar*``,
#: ``Des r)``, ``Diskrepansi Statistik 1)``, ``Dana Float1)``.
_FOOTNOTE = re.compile(r"(?:\s*\*+|\s*\d+\s*\)|\s+[a-z]\s*\))+\s*$")


def clean_label(text: object) -> str:
    """Collapse whitespace and strip trailing footnote marks.

    Only *trailing* marks go: a parenthesis inside a label is part of the name
    — 'Indeks Keyakinan Konsumen (IKK)' must survive intact, because the
    acronym is how the series is matched.
    """
    collapsed = _WHITESPACE.sub(" ", str(text or "")).strip()
    previous = None
    while previous != collapsed:
        previous = collapsed
        collapsed = _FOOTNOTE.sub("", collapsed).strip()
    return collapsed


def parse_month(label: object) -> int | None:
    """Month number from an Indonesian or English month label, else ``None``.

    OJK and BI mark revised and provisional figures inside the header cell —
    ``'Des r)'``, ``'Mar*'``, ``'Apr **'`` — so the first token is tried when
    the whole label does not resolve.
    """
    key = clean_label(label).lower().rstrip(".")
    if not key:
        return None
    if key.isdigit():
        number = int(key)
        return number if 1 <= number <= 12 else None
    if key in MONTHS:
        return MONTHS[key]
    head = re.split(r"[\s)(*,.]+", key, maxsplit=1)[0]
    return MONTHS.get(head)


def parse_quarter(label: object) -> int | None:
    key = clean_label(label).lower().replace(" ", "").replace("-", "")
    return QUARTERS.get(key)


def parse_year(label: object) -> int | None:
    """Year from a header cell, which may be ``2026``, ``2026.0`` or ``'2026'``."""
    key = clean_label(label)
    if not key:
        return None
    try:
        year = int(float(key))
    except ValueError:
        match = re.search(r"(19|20)\d{2}", key)
        if not match:
            return None
        year = int(match.group(0))
    return year if 1900 <= year <= 2100 else None


def parse_dmy(text: str) -> dt.date | None:
    """``dd/mm/yyyy`` — the shape PIHPS uses for its column keys."""
    match = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*", text or "")
    if not match:
        return None
    day, month, year = (int(part) for part in match.groups())
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


def month_start(year: int, month: int) -> dt.date:
    return dt.date(year, month, 1)


def quarter_start(year: int, quarter: int) -> dt.date:
    return dt.date(year, 3 * (quarter - 1) + 1, 1)


def now_utc() -> dt.datetime:
    """The vintage key.  One call per collector run, so a run is one vintage."""
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


#: Units as BI and OJK write them, mapped to the catalogue's spellings.  The
#: store carries one unit string per meaning so that two collectors reading the
#: same quantity cannot disagree about what it is called.
UNIT_ALIASES = {
    "rp miliar": "IDR billion",
    "miliar rp": "IDR billion",
    "rp milyar": "IDR billion",
    "rp juta": "IDR million",
    "juta unit": "million units",
    "juta instrumen": "million instruments",
    "ribu transaksi": "thousand transactions",
    "juta transaksi": "million transactions",
    "satuan": "count",
    "unit": "count",
    "bank": "count",
    "%": "percent",
    "persen": "percent",
    "rp/unit": "IDR per unit",
    "index": "index",
}


def normalise_unit(text: object, fallback: str = "") -> str:
    """Map a source's unit label onto the catalogue spelling."""
    key = clean_label(text).lower().strip(" .")
    if not key:
        return fallback
    if key in UNIT_ALIASES:
        return UNIT_ALIASES[key]
    for alias, canonical in UNIT_ALIASES.items():
        if key.startswith(alias):
            return canonical
    return fallback or clean_label(text)
