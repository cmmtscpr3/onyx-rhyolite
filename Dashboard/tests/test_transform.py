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


def test_show_as_yoy_and_index():
    frame = monthly([100.0] * 12 + [110.0] * 12)
    yoy = transform.show_as(frame, transform.SHOW_AS[1], "monthly")
    assert yoy.loc["2025-01-01", "a"] == pytest.approx(10.0)
    assert np.isnan(yoy.loc["2024-06-01", "a"])
    index = transform.show_as(frame, transform.SHOW_AS[2], "monthly")
    assert index.iloc[0, 0] == 100.0 and index.iloc[-1, 0] == pytest.approx(110.0)
    assert transform.show_as(frame, transform.SHOW_AS[0], "monthly").equals(frame.sort_index())


def test_weekly_yoy_uses_52_weeks():
    index = pd.date_range("2025-01-02", periods=60, freq="7D")
    frame = pd.DataFrame({"a": np.arange(60, dtype=float) + 100}, index=index)
    yoy = transform.show_as(frame, transform.SHOW_AS[1], "weekly")
    assert yoy.iloc[52, 0] == pytest.approx((152 / 100 - 1) * 100)
    assert np.isnan(yoy.iloc[51, 0])


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


def test_weekly_median_groups_monday_weeks():
    lots = pd.DataFrame(
        {
            "auction_date": pd.to_datetime(["2026-08-11", "2026-08-13", "2026-08-18"]),
            "price_idr": [100.0, 300.0, 50.0],
        }
    )
    table = transform.weekly_median(lots)
    assert list(table.index) == [pd.Timestamp("2026-08-10"), pd.Timestamp("2026-08-17")]
    assert table.loc["2026-08-10", "median_price"] == 200.0
    assert table.loc["2026-08-10", "lots"] == 2


def test_freshness_status():
    today = dt.date(2026, 9, 16)
    assert transform.freshness_status(pd.Timestamp("2026-09-10"), 21, today) == ("fresh", 6)
    assert transform.freshness_status(pd.Timestamp("2026-06-01"), 75, today) == ("late", 107)
    assert transform.freshness_status(pd.Timestamp("2025-06-01"), 75, today)[0] == "stale"
    assert transform.freshness_status(pd.Timestamp("2025-06-01"), 75, today, forced="stale") == ("stale", 472)
    assert transform.freshness_status(pd.Timestamp("2026-03-01"), None, today)[0] == "manual"
    assert transform.freshness_status(None, 21, today) == ("no data", None)
