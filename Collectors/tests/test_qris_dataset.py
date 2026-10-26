"""Invariants on the transcribed QRIS dataset.

The figures in ``Dataset/Consumption/qris_transactions.csv`` were read off the
data labels of two published charts, by hand: one printing the last month of
each quarter from March 2023 to March 2026, and one printing every month from
December 2024 to June 2026. That is a different risk profile from a parsed
source: the failure mode is a mistyped digit, not a layout change. These checks
are what a mistyped digit would break — the Off-Us share moves smoothly in the
real series, so a wrong digit shows up as a kink or as a share outside the
plausible band, and both charts print growth rates their labels must reproduce.
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
    assert all(len(points) == 26 for points in series.values())


def test_months_are_quarter_ends_until_the_monthly_chart_begins(series):
    """Every month from December 2024; before it only the months the
    quarterly chart printed, which are single months, not quarter totals."""
    monthly = ["2024-12-01"] + [f"{year}-{month:02d}-01" for year in (2025, 2026) for month in range(1, 13)]
    monthly = [date for date in monthly if date <= "2026-06-01"]
    for points in series.values():
        earlier = [date for date in points if date < "2024-12-01"]
        assert {date[5:7] for date in earlier} == {"03", "06", "09", "12"}
        assert sorted(date for date in points if date >= "2024-12-01") == monthly


@pytest.mark.parametrize(
    "name", ["volume.total", "volume.off_us", "value.total", "value.off_us"]
)
def test_every_month_is_up_on_a_year_earlier(series, name):
    """QRIS grew year on year throughout; month to month it does dip (February
    is short), so a fall on a year earlier is what would be a typo."""
    points = series[f"qris_transactions.{name}"]
    compared = 0
    for date, value in points.items():
        earlier = f"{int(date[:4]) - 1}{date[4:]}"
        if earlier in points:
            assert value > points[earlier], (date, value, points[earlier])
            compared += 1
    assert compared >= 12


def _growth_bounds(later: float, earlier: float, rounding: float) -> tuple[float, float]:
    """The % growth two rounded labels allow, each off by up to ``rounding``."""
    return (
        ((later - rounding) / (earlier + rounding) - 1) * 100,
        ((later + rounding) / (earlier - rounding) - 1) * 100,
    )


@pytest.mark.parametrize(
    "name, later, earlier, months, printed",
    [
        # The monthly chart: "Vol Tx QRIS Jun 2026 to Jun 2025 97,99%".
        ("volume.total", "2026-06", "2025-06", 1, 97.99),
        ("value.total", "2026-06", "2025-06", 1, 87.92),
        # The quarterly chart's Q1 2026 annotations, on Q1 2025 and on Q4 2025.
        # They are three-month totals, which the monthly labels now let us add up.
        ("volume.total", "2026-03", "2025-03", 3, 116.43),
        ("volume.total", "2026-03", "2025-12", 3, 9.56),
    ],
)
def test_the_labels_reproduce_the_growth_the_charts_print(series, name, later, earlier, months, printed):
    points = series[f"qris_transactions.{name}"]

    def total(end: str) -> float:
        year, month = int(end[:4]), int(end[5:7])
        dates = []
        for _ in range(months):
            dates.append(f"{year}-{month:02d}-01")
            year, month = (year, month - 1) if month > 1 else (year - 1, 12)
        return sum(points[date] for date in dates)

    low, high = _growth_bounds(total(later), total(earlier), 0.5 * months)
    assert low <= printed <= high, (low, printed, high)


def _share_tolerance(total: float) -> float:
    """How much a share can move on label rounding alone.

    The charts print integers, so a value of 13 carries +/-0.5 -- worth about
    seven points of share. Ignoring that makes the early, small-magnitude
    months look like errors when they are just coarse labels.
    """
    return 0.5 / total * 2


@pytest.mark.parametrize("measure", ["volume", "value"])
def test_off_us_is_a_smooth_and_plausible_share_of_the_total(series, measure):
    """Off-Us runs 77-91% and climbs steadily, with no real jolt from one point to the next.

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
