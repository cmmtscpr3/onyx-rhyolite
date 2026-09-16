"""Invariants on the transcribed QRIS dataset.

The figures in ``Dataset/Consumption/qris_transactions.csv`` were read off the
data labels of a published chart, by hand. That is a different risk profile
from a parsed source: the failure mode is a mistyped digit, not a layout
change. These checks are what a mistyped digit would break — the Off-Us share
moves smoothly in the real series, so a wrong digit shows up as a kink or as a
share outside the plausible band.
"""

from __future__ import annotations

import csv

import pytest

from collectors.paths import CONSUMPTION
from collectors.sinks import long_csv

PATH = CONSUMPTION / "qris_transactions.csv"


@pytest.fixture(scope="module")
def series() -> dict:
    with open(PATH, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    out: dict = {}
    for row in rows:
        out.setdefault(row["series_id"], {})[row["ref_date"]] = float(row["value"])
    return out


def test_the_four_transcribed_series_are_present(series):
    assert set(series) == {
        "qris_transactions.volume.total",
        "qris_transactions.volume.off_us",
        "qris_transactions.value.total",
        "qris_transactions.value.off_us",
    }
    assert all(len(points) == 13 for points in series.values())


def test_every_period_is_a_quarter_end_month(series):
    for points in series.values():
        assert {date[5:7] for date in points} == {"03", "06", "09", "12"}


@pytest.mark.parametrize(
    "name", ["volume.total", "volume.off_us", "value.total", "value.off_us"]
)
def test_each_series_rises_monotonically(series, name):
    """QRIS grew every quarter in this window; a dip would be a typo."""
    points = series[f"qris_transactions.{name}"]
    ordered = [points[date] for date in sorted(points)]
    assert all(b >= a for a, b in zip(ordered, ordered[1:])), ordered


def _share_tolerance(total: float) -> float:
    """How much a share can move on label rounding alone.

    The chart prints integers, so a value of 13 carries +/-0.5 -- worth about
    seven points of share. Ignoring that makes the early, small-magnitude
    quarters look like errors when they are just coarse labels.
    """
    return 0.5 / total * 2


@pytest.mark.parametrize("measure", ["volume", "value"])
def test_off_us_is_a_smooth_and_plausible_share_of_the_total(series, measure):
    """Off-Us runs 77-91% and climbs steadily, with no real quarter-on-quarter jolt.

    A single mistyped digit in either series would show here before anywhere
    else -- as a share outside the band, or as a step bigger than the labels'
    own rounding can explain.
    """
    total = series[f"qris_transactions.{measure}.total"]
    off_us = series[f"qris_transactions.{measure}.off_us"]
    dates = sorted(total)
    shares = [off_us[date] / total[date] for date in dates]
    assert all(0.75 <= share <= 0.95 for share in shares), shares
    assert all(off_us[date] <= total[date] for date in dates)
    for date, later_date, earlier, later in zip(dates, dates[1:], shares, shares[1:]):
        allowed = 0.03 + _share_tolerance(total[date]) + _share_tolerance(total[later_date])
        assert abs(later - earlier) < allowed, (date, later_date, earlier, later, allowed)


def test_the_off_us_share_trends_upward_over_the_window(series):
    """It went 78% -> 90% on volume; a transcription error would flatten that."""
    for measure in ("volume", "value"):
        total = series[f"qris_transactions.{measure}.total"]
        off_us = series[f"qris_transactions.{measure}.off_us"]
        dates = sorted(total)
        first = off_us[dates[0]] / total[dates[0]]
        last = off_us[dates[-1]] / total[dates[-1]]
        assert last > first + 0.05


def test_the_file_is_a_long_table_in_the_house_format(series):
    header, rows = long_csv.read_csv(PATH)
    assert header == list(long_csv.DEFAULT_HEADER)
    assert long_csv.render(header, rows) == PATH.read_bytes()
    assert PATH.read_bytes().endswith(b"\r\n")


def test_the_aspi_collector_cannot_clobber_these_rows():
    """The blocked ASPI collector writes this same file.

    It emits two-level ids (``qris_transactions.volume``) while the transcribed
    rows are three-level (``qris_transactions.volume.total``), so the upsert key
    never collides and the two sources coexist rather than overwrite.
    """
    from collectors.sources import qris

    transcribed = {
        "qris_transactions.volume.total",
        "qris_transactions.volume.off_us",
        "qris_transactions.value.total",
        "qris_transactions.value.off_us",
    }
    emitted = {f"{qris.PREFIX}.{suffix}" for _, suffix, _ in qris.SERIES_ALIASES}
    assert not (emitted & transcribed)
