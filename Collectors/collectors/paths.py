"""Where everything lives, anchored to this file rather than the cwd.

The pipeline these collectors were ported from used bare relative paths
(``Path("config/...")``), so it only ran from the repository root.  Anchoring
on ``__file__`` instead means a collector works from any working directory,
which is what makes the scheduled runs and the tests interchangeable.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent          # Collectors/collectors
COLLECTORS_ROOT = PACKAGE_ROOT.parent                   # Collectors
REPO_ROOT = COLLECTORS_ROOT.parent                      # the repository

DATASET = REPO_ROOT / "Dataset"
BACKUP = DATASET / "Backup"
CONSUMPTION = DATASET / "Consumption"
FOOD_PRICES = DATASET / "Food Prices" / "PIHPS"
CONFIG = PACKAGE_ROOT / "config"

#: ``price_type_id`` on the PIHPS portal -> the folder that already holds that
#: market's workbooks.  Produsen (4) is published but has no folder here, so it
#: is deliberately absent rather than silently collected into the wrong place.
MARKET_DIRS = {
    1: "Traditional Market",
    2: "Modern Market",
    3: "Wholesale",
}

#: The workbook name PIHPS exports under, which the uploaded files already use.
WORKBOOK_NAME = "Tabel Harga Berdasarkan Daerah {year}.xlsx"


def market_workbook(price_type_id: int, year: int) -> Path:
    return FOOD_PRICES / MARKET_DIRS[price_type_id] / WORKBOOK_NAME.format(year=year)


def consumption_csv(prefix: str) -> Path:
    """The long CSV that holds one series prefix."""
    return CONSUMPTION / f"{prefix}.csv"


def run_stamp(now: dt.datetime | None = None) -> str:
    """One backup directory name per run, so a run's snapshots group together."""
    now = now or dt.datetime.now(dt.timezone.utc)
    return now.strftime("%Y-%m-%dT%H%M%SZ")
