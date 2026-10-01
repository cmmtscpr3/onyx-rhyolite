"""Calendar rules: ISO weeks, week-ending day, 53-week years, regular spacing."""

from __future__ import annotations

import datetime as dt

import pandas as pd

from ews import calendar


def test_iso_monday_and_week_ending():
    thursday = dt.date(2026, 9, 24)
    assert calendar.iso_monday(thursday) == pd.Timestamp(2026, 9, 21)
    assert calendar.week_ending(calendar.iso_monday(thursday)) == pd.Timestamp(2026, 9, 27)
    assert calendar.iso_monday(dt.date(2026, 9, 21)) == pd.Timestamp(2026, 9, 21)  # a Monday maps to itself


def test_53_week_years():
    assert calendar.weeks_in_iso_year(2020) == 53
    assert calendar.weeks_in_iso_year(2026) == 53
    assert calendar.weeks_in_iso_year(2025) == 52
    assert calendar.weeks_in_iso_year(2032) == 53
    assert calendar.is_week53(dt.date(2020, 12, 31))
    assert calendar.seasonal_week(53) == 52
    assert calendar.seasonal_week(12) == 12


def test_days_in_month():
    assert calendar.days_in_month(dt.date(2024, 2, 1)) == 29
    assert calendar.days_in_month(dt.date(2026, 2, 1)) == 28
    assert calendar.days_in_month(dt.date(2026, 3, 1)) == 31


def test_thursday_rule_for_week_to_month():
    # Week of Mon 29 Dec 2025: its Thursday is 1 Jan 2026, so it belongs to January.
    assert calendar.week_month(dt.date(2025, 12, 29)) == pd.Timestamp(2026, 1, 1)
    assert calendar.week_month(dt.date(2026, 9, 28)) == pd.Timestamp(2026, 10, 1)


def test_week_to_month_needs_three_weeks():
    weeks = pd.date_range("2026-01-05", periods=5, freq="7D")  # all in January
    frame = pd.DataFrame({"series_id": "s", "ref_date": weeks, "value": [1.0, 2.0, None, None, None]})
    out = calendar.week_to_month(frame)
    assert out["value"].isna().all()  # only 2 weeks with a value
    frame.loc[2, "value"] = 3.0
    assert calendar.week_to_month(frame)["value"].iloc[0] == 2.0


def test_weekly_series_are_mondays_seven_days_apart(obs):
    weekly = obs[obs["frequency"] == "weekly"]
    assert (weekly["ref_date"].dt.weekday == 0).all()
    assert (weekly["week_ending"].dt.weekday == 6).all()
    gaps = weekly.groupby("series_id")["ref_date"].diff().dropna()
    assert (gaps == pd.Timedelta(days=7)).all()


def test_monthly_series_are_firsts_one_month_apart(obs):
    monthly = obs[obs["frequency"] == "monthly"]
    assert (monthly["ref_date"].dt.day == 1).all()
    for _, group in monthly.groupby("series_id"):
        months = group["ref_date"].dt.year * 12 + group["ref_date"].dt.month
        assert (months.diff().dropna() == 1).all()


def test_pihps_has_404_weeks_per_series_through_sep_2026(obs):
    weekly = obs[(obs["frequency"] == "weekly") & (obs["ref_date"] <= "2026-09-21")]
    counts = weekly.groupby("series_id").size()
    assert len(counts) == 30
    assert (counts == 404).all()


def test_week_53_kept(obs):
    week53 = obs[(obs["iso_year"] == 2020) & (obs["iso_week"] == 53)]
    assert len(week53) == 30  # every PIHPS series has a 2020-W53 row


def test_four_year_end_clashes_resolved(findings):
    clashes = [f for f in findings if f.check_id == "D3"]
    assert sorted(f.ref_date for f in clashes) == ["2019-12-30", "2020-12-28", "2024-12-30", "2025-12-29"]


def test_clash_keeps_later_date_with_a_price(obs):
    # Traditional market: 1 Jan 2020 is a dash, so 31 Dec 2019 is kept for that week.
    row = obs[(obs["series_id"] == "pihps.traditional.01_beras") & (obs["ref_date"] == "2019-12-30")].iloc[0]
    assert row["source_date"] == pd.Timestamp(2019, 12, 31)
    assert pd.notna(row["value"])
    # Modern market has 1 Jan 2020, so the later date wins.
    row = obs[(obs["series_id"] == "pihps.modern.01_beras") & (obs["ref_date"] == "2019-12-30")].iloc[0]
    assert row["source_date"] == pd.Timestamp(2020, 1, 1)
