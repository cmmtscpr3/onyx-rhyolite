"""Working out what a collector can skip, and what it must not.

Every collector here is idempotent, so re-reading history is safe — it is just
wasteful.  The point of this module is to narrow each run to the periods that
are actually missing, without quietly losing the two things a naive watermark
would cost.

**Revisions.**  A hard watermark ("everything after the newest date I have")
never sees a source restate an *earlier* month, and BI does restate them.  So
the watermark is pulled back by an overlap of a few periods: recent history is
re-read and re-checked on every run, older history is trusted.  ``--full``
turns the narrowing off entirely when a complete pass is wanted.

**Grid alignment.**  Some sources do not answer "give me data after date X" —
they answer "give me a grid anchored on date X", which is not the same
question.  PIHPS is one, and its anchoring rule is measured and enforced in
``pihps.start_for``.  Nothing in this module should be used to derive a start
date for that kind of source without checking what the source does with it.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from .sinks import long_csv

#: How many periods of already-collected history to re-read anyway, so a
#: restatement inside that window is still noticed.
DEFAULT_OVERLAP = 3


def months_before(date: dt.date, count: int) -> dt.date:
    """``date`` moved back ``count`` whole months, to the first of the month."""
    total = (date.year * 12 + date.month - 1) - count
    return dt.date(total // 12, total % 12 + 1, 1)


def auto_since(
    path: Path,
    prefix: str,
    *,
    overlap: int = DEFAULT_OVERLAP,
    full: bool = False,
) -> dt.date | None:
    """The earliest period a run needs to emit, or ``None`` for a full pass.

    ``None`` means "no narrowing": either it was asked for, or the target file
    does not exist yet, or it holds nothing under ``prefix`` — in all three
    cases there is no watermark to trust and the whole history is wanted.

    ``prefix`` should be as specific as the series family whose dates are being
    read.  ``bi_seki.csv`` is the reason: it carries monthly deposits alongside
    quarterly national accounts, and the newest monthly date says nothing about
    how far the quarterly series runs, so narrowing on the file as a whole
    would skip quarters that are genuinely missing.
    """
    if full:
        return None
    latest = long_csv.latest_ref_date(Path(path), prefix)
    if latest is None:
        return None
    return months_before(latest, max(0, overlap))
