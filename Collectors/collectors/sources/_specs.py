"""Row matching shared by the BI workbook collectors.

Both SPIP and SEKI are read the same way: find the header rows, then pull out
components by their Indonesian **label**, never by row number.  BI reshapes
these tables between releases, and a fixed row index fails silently by reading
the wrong component -- which is worse than failing, because the number looks
plausible.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RowSpec:
    """One component to pull out of one workbook."""

    sub: str
    match: str
    unit: str = ""
    exact: bool = False

    def matches(self, label: str) -> bool:
        """Substring match, or whole-label match where a prefix is ambiguous.

        ``exact`` exists because 'Volume Transaksi' is a prefix of 'Volume
        Transaksi Belanja', and 'Dana Float' of 'Dana Float Penerbit ... Bank':
        without it a total would capture its own components and the series
        would quietly be the wrong one.
        """
        left, right = label.casefold().strip(), self.match.casefold().strip()
        return left == right if self.exact else right in left


def unit_from_row(grid, row: int, limit: int = 4) -> str | None:
    """BI writes the unit in its own column, as 'Indonesian/English'."""
    for col in range(limit):
        text = grid.label(row, col)
        if "/" in text and any(
            token in text.lower()
            for token in ("rp", "juta", "ribu", "unit", "transaksi", "%", "satuan")
        ):
            return text.split("/", 1)[0].strip()
    return None


def pick_sheet(grids: dict, sheets: tuple[str, ...], table: str):
    """First named sheet that exists, else the last sheet in the book.

    SEKI workbooks keep retired vintages as earlier sheets ('Th 1990-2003') and
    put the live table last, so the fallback is the right one rather than a
    guess.
    """
    from ..excelio import WorkbookError

    for name in sheets:
        if name in grids:
            return grids[name]
    if not grids:
        raise WorkbookError(f"{table}: workbook has no sheets")
    return list(grids.values())[-1]
