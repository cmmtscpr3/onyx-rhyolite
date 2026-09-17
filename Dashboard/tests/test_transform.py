"""The arithmetic between a frame and a chart, on tiny hand-made frames."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from dashboard import transform


def monthly(values, start="2024-01-01"):
    index = pd.date_range(start, periods=len(values), freq="MS")
    return pd.DataFrame({"a": values}, index=index)


def test_year_earlier_aligns_by_date_not_position():
    frame = monthly(list(range(1, 25)))
    frame = frame.drop(frame.index[5])  # a gap must not shift the comparison
    previous = transform.year_earlier(frame, "monthly")
    assert previous.loc["2025-03-01", "a"] == 3
    assert np.isnan(previous.loc["2025-06-01", "a"])  # its year-earlier month is the gap
    assert np.isnan(previous.loc["2024-02-01", "a"])


@pytest.mark.parametrize(
    "frequency, label",
    [
        ("weekly", "Week-on-week % change"),
        ("monthly", "Month-on-month % change"),
        ("quarterly", "Year-on-year % change"),
        ("annual", "Year-on-year % change"),
        ("irregular", "Year-on-year % change"),
        ("something else", "Year-on-year % change"),
    ],
)
def test_the_comparison_follows_the_publication_frequency(frequency, label):
    assert transform.show_as_options(frequency) == ("Level", label)
    assert transform.comparison(frequency).label == label


def test_show_as_compares_a_monthly_series_with_the_month_before():
    frame = monthly([100.0] * 12 + [110.0] * 12)
    change = transform.show_as(frame, transform.comparison("monthly").label, "monthly")
    assert change.loc["2025-01-01", "a"] == pytest.approx(10.0)  # the step month
    assert change.loc["2025-02-01", "a"] == pytest.approx(0.0)
    assert np.isnan(change.loc["2024-01-01", "a"])  # nothing a month earlier
    assert transform.show_as(frame, transform.LEVEL, "monthly").equals(frame.sort_index())


def test_weekly_compares_the_week_before_while_the_table_keeps_52_weeks():
    index = pd.date_range("2025-01-02", periods=60, freq="7D")
    frame = pd.DataFrame({"a": np.arange(60, dtype=float) + 100}, index=index)
    change = transform.show_as(frame, transform.comparison("weekly").label, "weekly")
    assert change.iloc[1, 0] == pytest.approx((101 / 100 - 1) * 100)
    assert np.isnan(change.iloc[0, 0])
    # The latest-value table still looks 52 weeks back for its own column.
    previous = transform.year_earlier(frame, "weekly")
    assert previous.iloc[52, 0] == 100.0
    assert np.isnan(previous.iloc[51, 0])


def test_a_week_a_source_skipped_leaves_a_gap():
    index = pd.DatetimeIndex(["2026-01-05", "2026-01-12", "2026-01-26"])
    frame = pd.DataFrame({"a": [100.0, 110.0, 121.0]}, index=index)
    change = transform.show_as(frame, transform.comparison("weekly").label, "weekly")
    assert change.iloc[1, 0] == pytest.approx(10.0)
    assert np.isnan(change.iloc[2, 0])  # a fortnight back is not a week


def test_quarterly_is_compared_with_a_year_earlier():
    index = pd.date_range("2024-01-01", periods=8, freq="QS")
    frame = pd.DataFrame({"a": [100.0] * 4 + [125.0] * 4}, index=index)
    change = transform.show_as(frame, transform.comparison("quarterly").label, "quarterly")
    assert change.iloc[4, 0] == pytest.approx(25.0)
    assert np.isnan(change.iloc[3, 0])


def test_since_slices_from_january():
    frame = monthly(list(range(24)))
    assert transform.since(frame, 2025).index[0] == pd.Timestamp("2025-01-01")
    assert transform.since(frame, None).equals(frame)


def test_latest_table_percent_and_points():
    frame = monthly([100.0] * 12 + [110.0] * 11 + [121.0])
    table = transform.latest_table(frame, "monthly", {"a": "Series A"}, "IDR billion")
    row = table.iloc[0]
    assert row["Series"] == "Series A"
    assert row["Latest"] == dt.date(2025, 12, 1)
    assert row["Value"] == 121.0
    assert row["vs previous"] == pytest.approx(10.0)
    assert row["vs year earlier"] == pytest.approx(21.0)
    points = transform.latest_table(frame, "monthly", {}, "index").iloc[0]
    assert points["vs previous"] == pytest.approx(11.0)
    assert points["vs year earlier"] == pytest.approx(21.0)


def test_latest_table_skips_empty_series():
    frame = monthly([1.0, 2.0])
    frame["b"] = np.nan
    table = transform.latest_table(frame, "monthly", {}, "x")
    assert list(table["Series"]) == ["a"]


def test_formatting():
    assert transform.format_number(1234567.891, "IDR billion") == "1,234,568"
    assert transform.format_number(12.345, "IDR billion") == "12.3"
    assert transform.format_number(118.5, "index") == "118.5"
    assert transform.format_number(float("nan")) == "–"
    assert transform.format_change(10.04, "IDR billion") == "+10.0%"
    assert transform.format_change(-1.25, "percent") == "-1.2 pts" or transform.format_change(-1.25, "percent") == "-1.3 pts"
    assert transform.change_label("index") == "points"


def test_freshness_status():
    today = dt.date(2026, 9, 16)
    assert transform.freshness_status(pd.Timestamp("2026-09-10"), 21, today) == ("fresh", 6)
    assert transform.freshness_status(pd.Timestamp("2026-06-01"), 75, today) == ("late", 107)
    assert transform.freshness_status(pd.Timestamp("2025-06-01"), 75, today)[0] == "stale"
    assert transform.freshness_status(pd.Timestamp("2025-06-01"), 75, today, forced="stale") == ("stale", 472)
    assert transform.freshness_status(pd.Timestamp("2026-03-01"), None, today)[0] == "manual"
    assert transform.freshness_status(None, 21, today) == ("no data", None)


def test_weekly_lots_counts_auction_weeks_and_flags_the_part_scraped_ones():
    # Two scrapes, each seeing a window of auctions around it.
    lots = pd.DataFrame(
        {
            "auction_date": pd.to_datetime(
                ["2026-08-06", "2026-08-11", "2026-08-13", "2026-08-18", "2026-08-25", "2026-08-27"]
            ),
            "sold": [True, True, True, True, False, False],
            "first_seen": pd.to_datetime(["2026-08-14"] * 3 + ["2026-08-26"] * 3),
        }
    )
    table = transform.weekly_lots(lots)
    assert list(table.index) == [pd.Timestamp(d) for d in ("2026-08-03", "2026-08-10", "2026-08-17", "2026-08-24")]
    assert list(table["lots"]) == [1, 2, 1, 2]
    # The first scrape saw 06 to 13 August, so only the week of the 10th is cut
    # off at both ends by nothing; every other week here runs past a scrape's reach.
    assert list(table["complete"]) == [False, False, False, False]
    wide = transform.weekly_lots(
        lots.assign(first_seen=pd.to_datetime(["2026-09-01"] * 6), auction_date=lots["auction_date"])
    )
    assert wide.loc["2026-08-10", "complete"]  # one scrape covering Monday to Sunday
    assert not wide.loc["2026-08-24", "complete"]  # its week runs past the scrape


def test_weekly_lots_is_empty_rather_than_broken_without_lots():
    table = transform.weekly_lots(pd.DataFrame(columns=["auction_date", "sold", "first_seen"]))
    assert table.empty and list(table.columns) == ["lots", "held", "complete"]
