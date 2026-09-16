"""Narrowing a run to what is actually missing, without losing anything.

Two failure modes are worth more than the speed this buys, and both are tested
here rather than trusted: a duplicate in one payload being reported as a
revision of the file, and a derived start date that lands off the source's own
grid.
"""

from __future__ import annotations

import datetime as dt
import shutil

import pytest

from collectors import incremental, paths
from collectors.model import Listing, Obs
from collectors.sinks import listings_csv, long_csv, wide_xlsx
from collectors.sources import ibid, pihps

# ------------------------------------------------------------------- dedupe


def test_a_duplicate_reading_is_dropped_not_reported_as_a_revision(tmp_path):
    """It used to count as a revision against a file it never touched.

    Two observations of the same (series_id, ref_date) in one run gave
    added=1, revised=1 -- a revision that never happened.
    """
    target = tmp_path / "x.csv"
    report = long_csv.upsert(
        target,
        [
            Obs("a.b", dt.date(2026, 1, 1), 1.0, "percent"),
            Obs("a.b", dt.date(2026, 1, 1), 2.0, "percent"),
        ],
    )
    assert (report.added, report.revised, report.duplicates, report.total) == (1, 0, 1, 1)
    assert ",1.0," in target.read_text()  # first wins


def test_the_series_dedupe_keeps_the_first_of_a_duplicate_pair():
    """A duplicate is a defect in the payload, not a restatement.

    Nothing marks the second copy as the better one, so the first is kept.
    """
    first = Obs("a.b", dt.date(2026, 1, 1), 1.0, "percent")
    second = Obs("a.b", dt.date(2026, 1, 1), 2.0, "percent")
    kept, dropped = long_csv.deduplicate([first, second])
    assert dropped == 1 and [obs.value for obs in kept] == [1.0]


def test_the_listings_dedupe_keeps_the_later_sighting():
    """Deliberately the opposite rule, because the later state is the truer one.

    A paginated scrape can see the same listing twice while inventory shifts,
    and a vehicle that sold mid-scrape should end up sold.
    """
    url = "https://www.ibid.astra.co.id/detail-lelang/motor/x/12345"
    earlier = Listing(url=url, page=1, position=1, sold=False)
    later = Listing(url=url, page=2, position=3, sold=True, sold_label="Terjual")
    kept, dropped = listings_csv.deduplicate([earlier, later])
    assert dropped == 1
    assert kept[0].sold and kept[0].sold_label == "Terjual"


def test_a_duplicated_listing_is_counted_and_collapsed(tmp_path):
    target = tmp_path / "ibid_motor_data.csv"
    url = "https://www.ibid.astra.co.id/detail-lelang/motor/x/12345"
    report = listings_csv.upsert(
        target,
        [
            Listing(url=url, page=1, position=1, sold=False, scraped_at="2026-09-16T00:00:00"),
            Listing(url=url, page=1, position=1, sold=True, sold_label="Terjual",
                    scraped_at="2026-09-16T00:00:00"),
        ],
    )
    assert (report.added, report.duplicates, report.total) == (1, 1, 1)
    assert ",True,Terjual," in target.read_text()


# --------------------------------------------------------------- watermarks


def test_the_watermark_is_the_newest_date_on_file_less_the_overlap():
    latest = long_csv.latest_ref_date(paths.consumption_csv("bi_emoney"), "bi_emoney")
    assert latest is not None
    assert incremental.auto_since(
        paths.consumption_csv("bi_emoney"), "bi_emoney", overlap=3
    ) == incremental.months_before(latest, 3)


def test_the_watermark_is_per_series_family_not_per_file():
    """bi_seki.csv holds monthly deposits beside quarterly national accounts.

    Their newest dates are months apart, so one watermark for the whole file
    would skip quarters that are genuinely missing.
    """
    path = paths.consumption_csv("bi_seki")
    monthly = incremental.auto_since(path, "bi_seki.deposits_by_owner")
    quarterly = incremental.auto_since(path, "bi_seki.gdp_expenditure_current")
    assert monthly and quarterly and monthly > quarterly


def test_full_disables_narrowing_entirely():
    path = paths.consumption_csv("bi_emoney")
    assert incremental.auto_since(path, "bi_emoney", full=True) is None


def test_a_missing_or_unmatched_file_means_a_full_pass():
    assert incremental.auto_since(paths.consumption_csv("does_not_exist"), "x") is None
    assert incremental.auto_since(paths.consumption_csv("bi_emoney"), "no.such.prefix") is None


@pytest.mark.parametrize("months", [0, 1, 3, 12, 13])
def test_months_before_stays_on_the_first_of_a_real_month(months):
    moved = incremental.months_before(dt.date(2026, 1, 1), months)
    assert moved.day == 1 and moved <= dt.date(2026, 1, 1)


# ------------------------------------------------------- the PIHPS lattice


REAL_2026 = paths.market_workbook(1, 2026)


def test_the_pihps_start_is_always_a_date_the_file_already_has():
    """The rule that keeps the weekly grid aligned.

    The portal re-anchors its grid to whatever start_date it is given.  Measured
    against this workbook -- 37 Thursday columns -- a start eight columns back
    returns Thursdays, while that date plus two days returns Mondays, which
    would add a second parallel set of columns instead of extending these.
    """
    weeks = wide_xlsx.existing_weeks(REAL_2026)
    start = pihps.start_for(REAL_2026, 2026)
    assert start in weeks
    assert start == weeks[-pihps.OVERLAP_WEEKS]


def test_the_pihps_start_narrows_the_request_a_lot():
    weeks = wide_xlsx.existing_weeks(REAL_2026)
    start = pihps.start_for(REAL_2026, 2026)
    assert len([w for w in weeks if w >= start]) < len(weeks) / 2


@pytest.mark.parametrize(
    "case",
    ["full", "absent", "other-year"],
)
def test_pihps_falls_back_to_january_when_there_is_nothing_to_align_to(case, tmp_path):
    if case == "full":
        assert pihps.start_for(REAL_2026, 2026, full=True) == dt.date(2026, 1, 1)
    elif case == "absent":
        assert pihps.start_for(tmp_path / "nope.xlsx", 2026) == dt.date(2026, 1, 1)
    else:
        # A 2025 workbook says nothing about where 2026's grid starts.
        assert pihps.start_for(paths.market_workbook(1, 2025), 2026) == dt.date(2026, 1, 1)


def test_a_short_workbook_starts_at_its_first_column_not_before_it():
    """Fewer columns than the overlap must not index off the front of the list."""
    grid = wide_xlsx.read_grid(REAL_2026)
    trimmed = wide_xlsx.Grid(
        rows=grid.rows,
        values={
            (key, week): text
            for (key, week), text in grid.values.items()
            if week in grid.weeks[:3]
        },
    )
    target = paths.DATASET.parent / "short.xlsx"
    try:
        wide_xlsx.write_grid(target, trimmed)
        assert pihps.start_for(target, 2026) == grid.weeks[0]
    finally:
        target.unlink(missing_ok=True)


def test_the_window_ends_at_today_or_the_year_end():
    assert pihps.window(2026, today=dt.date(2026, 9, 16))[1] == dt.date(2026, 9, 16)
    assert pihps.window(2025, today=dt.date(2026, 9, 16))[1] == dt.date(2025, 12, 31)


# ------------------------------------------------------------------- browser


def test_chromium_path_auto_lets_playwright_choose(monkeypatch):
    """ubuntu-latest ships /usr/bin/google-chrome, which the candidates prefer."""
    monkeypatch.setenv("CHROMIUM_PATH", "auto")
    assert ibid.chromium_path() is None
    monkeypatch.setenv("CHROMIUM_PATH", "/somewhere/chrome")
    assert ibid.chromium_path() == "/somewhere/chrome"
