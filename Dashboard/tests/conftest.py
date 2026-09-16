"""Test fixtures.  Every test runs offline against the real ``Dataset/``,
read-only, the same way the collectors' tests do."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]  # Dashboard
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard import data  # noqa: E402


@pytest.fixture(scope="session")
def series():
    return data.load_series()


@pytest.fixture(scope="session")
def pihps():
    return data.load_pihps()


@pytest.fixture(scope="session")
def lots():
    return data.load_lots()
