"""Where everything lives, anchored to this file rather than the cwd.

Streamlit runs the app from wherever it is launched and Community Cloud runs
it from the repository root, so nothing here may depend on the working
directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent          # Dashboard/dashboard
DASHBOARD_ROOT = PACKAGE_ROOT.parent                     # Dashboard
REPO_ROOT = DASHBOARD_ROOT.parent                        # the repository

DATASET = REPO_ROOT / "Dataset"
CONSUMPTION = DATASET / "Consumption"
FOOD_PRICES = DATASET / "Food Prices" / "PIHPS"
COLLECTORS = REPO_ROOT / "Collectors"
DIST = DASHBOARD_ROOT / "dist"


def collectors_importable() -> None:
    """Make the ``collectors`` package importable.

    Its CSV and workbook readers already know the datasets' quirks (text
    prices with thousands commas, ``'-'`` for missing, ``0000`` geo ids), so
    they are reused rather than re-implemented.
    """
    if str(COLLECTORS) not in sys.path:
        sys.path.insert(0, str(COLLECTORS))
