"""Test fixtures.  Every test here runs offline.

A test that needs the network is not a test of the parser or the merge.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURES = Path(__file__).resolve().parent / "fixtures"



#: The real dataset root, used read-only as merge input.  Tests copy a file
#: into tmp_path before touching it.
DATASET = ROOT.parent / "Dataset"


def long_series_csvs() -> list[Path]:
    """The dataset CSVs that are long series tables.

    ``Dataset/Consumption`` also holds the ibid listings files, which are a
    different shape entirely, so a bare glob would conscript them into the
    long-table contract.  Select on the header rather than on a filename
    pattern, so a new series file is picked up automatically and a new
    non-series file is not.
    """
    from collectors.sinks.long_csv import is_long_table

    out = []
    for path in sorted((DATASET / "Consumption").glob("*.csv")):
        with open(path, encoding="utf-8-sig", newline="") as handle:
            header = (handle.readline().rstrip("\r\n")).split(",")
        if is_long_table(header):
            out.append(path)
    return out


def listings_csvs() -> list[Path]:
    """The dataset CSVs that are listings tables."""
    from collectors.sinks.long_csv import is_long_table

    return [
        path
        for path in sorted((DATASET / "Consumption").glob("*.csv"))
        if path not in set(long_series_csvs())
    ]


@pytest.fixture(scope="session")
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def pihps_grid() -> list[dict]:
    return json.loads((FIXTURES / "pihps_grid_daerah.json").read_text())["data"]


@pytest.fixture(scope="session")
def ibid_cards() -> dict:
    """Two pages of recorded ibid cards: unsold on page 1, sold on page 40."""
    return json.loads((FIXTURES / "ibid_cards.json").read_text())


@pytest.fixture
def obtained_at() -> dt.datetime:
    return dt.datetime(2026, 9, 15, 2, 0, tzinfo=dt.timezone.utc)
