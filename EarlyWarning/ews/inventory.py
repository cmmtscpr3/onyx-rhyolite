"""The list of series this pipeline handles, and their settings.

Read from ``Scope/indicator_inventory.csv`` and narrowed to the datasets in
scope for this step: PIHPS food prices and the three BI SPIP files.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import paths

#: Series id prefixes in scope (PIHPS + BI SPIP).  The consumer survey is not.
SOURCES: tuple[str, ...] = ("pihps.", "bi_card_transactions.", "bi_emoney.", "bi_payment_system.")

#: The SPIP CSV files, by the prefix of the series they hold.
SPIP_FILES: dict[str, str] = {
    "bi_card_transactions": "bi_card_transactions.csv",
    "bi_emoney": "bi_emoney.csv",
    "bi_payment_system": "bi_payment_system.csv",
}

#: Series that sit in the SPIP files but are left out on purpose, with why.
#: Check M6 stays quiet about these and warns only about series it has never seen.
KNOWN_EXCLUDED: dict[str, str] = {
    "bi_payment_system.currency_to_gdp": "quarterly ratio, outside monthly/weekly scope",
    "bi_payment_system.currency_to_household_consumption": "quarterly ratio, outside monthly/weekly scope",
}

COLUMNS = ("series_id", "group_no", "name", "theme", "frequency", "unit", "series_kind", "calendar_adj")


def load_inventory(path: Path = paths.INVENTORY) -> pd.DataFrame:
    """One row per in-scope series, indexed by ``series_id``."""
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    frame = frame[frame["series_id"].str.startswith(SOURCES)]
    frame = frame[list(COLUMNS)].copy()
    frame["group_no"] = pd.to_numeric(frame["group_no"], errors="coerce").astype("Int64")
    return frame.set_index("series_id", drop=False).sort_index()
