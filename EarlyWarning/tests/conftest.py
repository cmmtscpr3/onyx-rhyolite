"""Test fixtures.  Every test runs offline against the real ``Dataset/``, read-only,
the same way the Dashboard and collectors tests do."""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]  # EarlyWarning
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ews import run  # noqa: E402

#: The date the tests check freshness against (data in the repo is complete to here).
TODAY = dt.date(2026, 9, 30)


@pytest.fixture(scope="session")
def result():
    return run.pipeline(TODAY)


@pytest.fixture(scope="session")
def obs(result):
    return result.observations


@pytest.fixture(scope="session")
def findings(result):
    return result.findings.items
