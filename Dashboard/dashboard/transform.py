"""The arithmetic between a loaded frame and a chart.

Everything here is a pure function of a wide frame (dates down, series
across) so it can be unit-tested without Streamlit or Plotly.
"""

from __future__ import annotations

import datetime as dt
from typing import Mapping

import numpy as np
import pandas as pd

SHOW_AS = ("Level", "Year-on-year % change", "Index (100 at start)")

#: How far back "a year earlier" is, and how far off that date an observation
#: may sit and still count.  Weekly data is compared 52 weeks back so the
#: comparison stays on the same weekday lattice; irregular data gets a wide
#: tolerance because its release months drift.
_YEAR_BACK: dict[str, tuple[pd.DateOffset | pd.Timedelta, pd.Timedelta]] = {
    "weekly": (pd.Timedelta(days=364), pd.Timedelta(days=3)),
    "monthly": (pd.DateOffset(years=1), pd.Timedelta(days=3)),
    "quarterly": (pd.DateOffset(years=1), pd.Timedelta(days=3)),
    "annual": (pd.DateOffset(years=1), pd.Timedelta(days=10)),
    "irregular": (pd.DateOffset(years=1), pd.Timedelta(days=20)),
}

#: Units whose changes read better as differences than as percentages.
POINT_UNITS = frozenset({"percent", "index"})


def _clean(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame[~frame.index.duplicated(keep="first")].sort_index()
    frame.index = pd.DatetimeIndex(frame.index)
    return frame


def year_earlier(frame: pd.DataFrame, frequency: str) -> pd.DataFrame:
    """Each row's value one year earlier, aligned to the row's own date."""
    frame = _clean(frame)
    if frame.empty:
        return frame.copy()
    offset, tolerance = _YEAR_BACK.get(frequency, _YEAR_BACK["irregular"])
    targets = pd.DatetimeIndex(frame.index - offset)
    previous = frame.reindex(targets, method="nearest", tolerance=tolerance)
    previous.index = frame.index
    return previous


def show_as(frame: pd.DataFrame, mode: str, frequency: str) -> pd.DataFrame:
    """Level, year-on-year % change, or an index with 100 at each series' first value."""
    frame = _clean(frame)
    if mode == SHOW_AS[1]:
        previous = year_earlier(frame, frequency)
        return (frame / previous - 1.0) * 100.0
    if mode == SHOW_AS[2]:
        base = frame.apply(lambda column: column.dropna().iloc[0] if column.notna().any() else np.nan)
        return frame / base * 100.0
    return frame


def since(frame: pd.DataFrame, year: int | None) -> pd.DataFrame:
    """Rows from 1 January of ``year`` onward (all rows when ``year`` is None)."""
    if year is None or frame.empty:
        return frame
    return frame[frame.index >= pd.Timestamp(year=year, month=1, day=1)]


def latest_table(
    frame: pd.DataFrame, frequency: str, labels: Mapping[str, str], unit: str
) -> pd.DataFrame:
    """One row per series: latest date and value, change on the previous
    observation and on a year earlier.

    Changes are percentages, except for series measured in percent or as an
    index, where a difference in points is what a reader wants.
    """
    frame = _clean(frame)
    previous_year = year_earlier(frame, frequency)
    points = unit in POINT_UNITS
    rows = []
    for column in frame.columns:
        values = frame[column].dropna()
        if values.empty:
            continue
        latest_date = values.index[-1]
        latest = float(values.iloc[-1])
        prior = float(values.iloc[-2]) if len(values) > 1 else np.nan
        a_year_ago = previous_year.at[latest_date, column] if latest_date in previous_year.index else np.nan
        rows.append(
            {
                "Series": labels.get(column, column),
                "Latest": latest_date.date(),
                "Value": latest,
                "vs previous": _change(latest, prior, points),
                "vs year earlier": _change(latest, a_year_ago, points),
            }
        )
    return pd.DataFrame(rows, columns=["Series", "Latest", "Value", "vs previous", "vs year earlier"])


def _change(now: float, then: float, points: bool) -> float:
    if then is None or np.isnan(then) or (not points and then == 0):
        return np.nan
    return now - then if points else (now / then - 1.0) * 100.0


def change_label(unit: str) -> str:
    return "points" if unit in POINT_UNITS else "%"


def format_number(value: float, unit: str = "") -> str:
    """Thousands-separated, with the precision the magnitude calls for."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "–"
    magnitude = abs(value)
    if unit in POINT_UNITS or magnitude < 100:
        return f"{value:,.1f}"
    return f"{value:,.0f}"


def format_change(value: float, unit: str) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "–"
    suffix = " pts" if unit in POINT_UNITS else "%"
    return f"{value:+,.1f}{suffix}"


def weekly_median(lots: pd.DataFrame, price: str = "price_idr", date: str = "auction_date") -> pd.DataFrame:
    """Median listed price and lot count per auction week (weeks start Monday)."""
    if lots.empty:
        return pd.DataFrame(columns=["median_price", "lots"], index=pd.DatetimeIndex([], name="week"))
    week = lots[date].dt.to_period("W-SUN").dt.start_time
    grouped = lots.assign(week=week).groupby("week")
    table = pd.DataFrame({"median_price": grouped[price].median(), "lots": grouped.size()})
    table.index.name = "week"
    return table.sort_index()


def freshness_status(latest, late_after_days: int | None, now: dt.date, forced: str = "") -> tuple[str, int | None]:
    """``(status, age_in_days)`` for the overview table."""
    if latest is None or pd.isna(latest):
        return ("no data", None)
    age = (pd.Timestamp(now) - pd.Timestamp(latest)).days
    if forced:
        return (forced, age)
    if late_after_days is None:
        return ("manual", age)
    if age <= late_after_days:
        return ("fresh", age)
    if age <= 2 * late_after_days:
        return ("late", age)
    return ("stale", age)
