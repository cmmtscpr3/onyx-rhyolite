"""Where everything lives, anchored to this file rather than the working directory."""

from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent          # EarlyWarning/ews
EWS_ROOT = PACKAGE_ROOT.parent                           # EarlyWarning
REPO_ROOT = EWS_ROOT.parent                              # the repository

# Inputs -- read only.  Nothing in this package writes under Dataset/.
DATASET = REPO_ROOT / "Dataset"
CONSUMPTION = DATASET / "Consumption"
FOOD_PRICES = DATASET / "Food Prices" / "PIHPS"
COLLECTORS = REPO_ROOT / "Collectors"

# Settings kept in git next to the code.
INVENTORY = EWS_ROOT / "Scope" / "indicator_inventory.csv"
DATA_ISSUES = EWS_ROOT / "data_issues.csv"

# Outputs: the datasets the early warning system uses.
DATA_OUT = EWS_ROOT / "data"


def collectors_importable() -> None:
    """Make the ``collectors`` package importable.

    Its CSV and workbook readers already know the datasets' quirks (text
    prices with thousands commas, ``'-'`` for missing, stale sheet
    dimensions), so they are reused rather than re-implemented -- the same
    approach as ``Dashboard/dashboard/paths.py``.
    """
    if str(COLLECTORS) not in sys.path:
        sys.path.insert(0, str(COLLECTORS))


def relative(path: Path) -> str:
    """A repository-relative path, for messages and the ``source_file`` column."""
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)
