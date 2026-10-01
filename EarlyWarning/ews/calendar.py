"""Step 2 -- put every series on a regular timeline.

Only dates change here, never values:

* Weekly (PIHPS): each source date moves to the **Monday** of its ISO week
  (``ref_date``).  The Sunday of that week is kept as ``week_ending``.  PIHPS
  dates fall on a different weekday each year, and this makes the spacing an
  even 7 days.  If two source dates land in one ISO week (it happens at year
  end), the later one that has a price is kept.
* Monthly (SPIP): ``ref_date`` is already the 1st of the month; each month gets
  ``days_in_month`` for the per-day adjustment in ``transform``.
* Every gap between a series' first and last period becomes an empty row, so
  "one period back" always means one week or one month.
"""

from __future__ import annotations

import calendar as _calendar
import datetime as dt

import pandas as pd

from .findings import INFO, Findings

CALENDAR_COLUMNS = (
    "series_id", "frequency", "unit", "ref_date", "week_ending", "iso_year", "iso_week",
    "days_in_month", "source_date", "source_file", "raw_text", "raw_value",
)


# ---------------------------------------------------------------------------
# Date helpers

def iso_monday(day: dt.date | pd.Timestamp) -> pd.Timestamp:
    """The Monday of the ISO week containing ``day``."""
    stamp = pd.Timestamp(day).normalize()
    return stamp - pd.Timedelta(days=stamp.weekday())


def week_ending(monday: dt.date | pd.Timestamp) -> pd.Timestamp:
    """The Sunday that closes the week starting on ``monday``."""
    return pd.Timestamp(monday) + pd.Timedelta(days=6)


def iso_year_week(day: dt.date | pd.Timestamp) -> tuple[int, int]:
    iso = pd.Timestamp(day).isocalendar()
    return int(iso[0]), int(iso[1])


def weeks_in_iso_year(year: int) -> int:
    """52 or 53.  28 December is always in the last ISO week of its year."""
    return dt.date(year, 12, 28).isocalendar()[1]


def is_week53(day: dt.date | pd.Timestamp) -> bool:
    return iso_year_week(day)[1] == 53


def seasonal_week(iso_week: int) -> int:
    """Seasonal slot for a week number: week 53 shares week 52's slot (for Phase 2)."""
    return 52 if iso_week == 53 else iso_week


def days_in_month(day: dt.date | pd.Timestamp) -> int:
    stamp = pd.Timestamp(day)
    return _calendar.monthrange(stamp.year, stamp.month)[1]


def week_month(monday: dt.date | pd.Timestamp) -> pd.Timestamp:
    """The month a week belongs to: the month containing its Thursday (the ISO rule)."""
    thursday = pd.Timestamp(monday) + pd.Timedelta(days=3)
    return pd.Timestamp(thursday.year, thursday.month, 1)


def week_to_month(weekly: pd.DataFrame, value: str = "value", min_weeks: int = 3) -> pd.DataFrame:
    """Weekly rows -> monthly means, by the Thursday rule.

    A month with fewer than ``min_weeks`` weeks that have a value is missing.
    Not used in this step's outputs; it is here for later phases that compare
    weekly prices with monthly data.
    """
    frame = weekly[["series_id", "ref_date", value]].copy()
    frame["month"] = frame["ref_date"].map(week_month)
    grouped = frame.groupby(["series_id", "month"])[value]
    out = pd.DataFrame({"mean": grouped.mean(), "weeks_with_value": grouped.count()}).reset_index()
    out.loc[out["weeks_with_value"] < min_weeks, "mean"] = float("nan")
    return out.rename(columns={"month": "ref_date", "mean": value})


# ---------------------------------------------------------------------------
# Alignment

def _weekly(frame: pd.DataFrame, findings: Findings) -> pd.DataFrame:
    frame = frame.copy()
    frame["ref_date"] = frame["source_date"].map(iso_monday)
    frame["has_value"] = frame["raw_value"].notna()
    # Within an ISO week keep the latest source date that has a value; if none
    # has one, the latest source date (so the week is present but missing).
    frame = frame.sort_values(["series_id", "ref_date", "has_value", "source_date"])
    clashes = frame[frame.duplicated(["series_id", "ref_date"], keep=False)]
    kept = frame.drop_duplicates(["series_id", "ref_date"], keep="last")
    _report_clashes(clashes, kept, findings)
    return kept.drop(columns="has_value")


def _report_clashes(clashes: pd.DataFrame, kept: pd.DataFrame, findings: Findings) -> None:
    """Check D3: one finding per ISO week, not per series, to keep the log readable."""
    if clashes.empty:
        return
    kept_dates = kept.set_index(["series_id", "ref_date"])["source_date"]
    for monday, group in clashes.groupby("ref_date"):
        dates = sorted({d.strftime("%Y-%m-%d") for d in group["source_date"]})
        chosen = kept_dates.loc[[(s, monday) for s in group["series_id"].unique()]]
        tally = chosen.dt.strftime("%Y-%m-%d").value_counts().sort_index()
        kept_text = ", ".join(f"{d} for {n} series" for d, n in tally.items())
        findings.add(
            "D3", INFO,
            f"two source dates in one ISO week ({', '.join(dates)}): kept {kept_text} "
            f"(the later date with a price)",
            ref_date=monday,
        )


def _grid(frame: pd.DataFrame, frequency: str) -> pd.DataFrame:
    """Reindex each series to every period between its first and last ref_date."""
    step = "7D" if frequency == "weekly" else "MS"
    parts = []
    for series_id, group in frame.groupby("series_id", sort=True):
        full = pd.date_range(group["ref_date"].min(), group["ref_date"].max(), freq=step)
        filled = group.set_index("ref_date").reindex(full)
        filled.index.name = "ref_date"
        filled["series_id"] = series_id
        for column in ("frequency", "unit"):
            filled[column] = group[column].iloc[0]
        parts.append(filled.reset_index())
    return pd.concat(parts, ignore_index=True) if parts else frame


def align(deduped: pd.DataFrame, findings: Findings) -> pd.DataFrame:
    """Loaded (and de-duplicated) readings -> one row per series per regular period."""
    weekly = deduped[deduped["frequency"] == "weekly"]
    monthly = deduped[deduped["frequency"] == "monthly"].copy()
    monthly["ref_date"] = monthly["source_date"]

    weekly = _grid(_weekly(weekly, findings), "weekly")
    monthly = _grid(monthly, "monthly")

    weekly["week_ending"] = weekly["ref_date"].map(week_ending)
    iso = weekly["ref_date"].dt.isocalendar()
    weekly["iso_year"] = iso["year"].astype("Int64")
    weekly["iso_week"] = iso["week"].astype("Int64")
    weekly["days_in_month"] = pd.array([pd.NA] * len(weekly), dtype="Int64")

    # Typed empty columns, so the concat below keeps the dtypes stable.
    monthly["week_ending"] = pd.Series(pd.NaT, index=monthly.index, dtype="datetime64[ns]")
    monthly["iso_year"] = pd.array([pd.NA] * len(monthly), dtype="Int64")
    monthly["iso_week"] = pd.array([pd.NA] * len(monthly), dtype="Int64")
    monthly["days_in_month"] = monthly["ref_date"].map(days_in_month).astype("Int64")

    weekly = weekly[list(CALENDAR_COLUMNS)]
    monthly = monthly[list(CALENDAR_COLUMNS)]
    weekly["week_ending"] = weekly["week_ending"].astype("datetime64[ns]")
    out = pd.concat([weekly, monthly], ignore_index=True)
    return out.sort_values(["series_id", "ref_date"]).reset_index(drop=True)
