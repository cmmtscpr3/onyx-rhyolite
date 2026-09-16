"""The listings sink: accumulate auctions without rewriting what is on file."""

from __future__ import annotations

import csv
import shutil

import pytest

from collectors.model import Listing, listing_id
from collectors.paths import DATASET
from collectors.sinks import listings_csv, long_csv
from conftest import listings_csvs

REAL = listings_csvs()
MOTOR = DATASET / "Consumption" / "ibid_motor_data.csv"


def test_the_listings_files_are_discovered():
    """Guards the fixture itself: an empty list would make the suite vacuous."""
    assert [p.name for p in REAL] == ["ibid_car_data.csv", "ibid_motor_data.csv"]


@pytest.mark.parametrize("source", REAL, ids=lambda p: p.name)
def test_read_then_render_is_byte_identical(source):
    """The whole contract in one assertion.

    LF line endings where the series CSVs use CRLF, minimal quoting for the
    commas in ``card_text``, ``(page, position)`` ordering, and every value
    left exactly as it was read.
    """
    header, rows = listings_csv.read_csv(source)
    assert listings_csv.render(header, rows) == source.read_bytes()


@pytest.mark.parametrize("source", REAL, ids=lambda p: p.name)
def test_the_real_files_use_lf_not_crlf(source):
    raw = source.read_bytes()
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n")


@pytest.mark.parametrize("source", REAL, ids=lambda p: p.name)
def test_upserting_nothing_writes_nothing(source, tmp_path):
    target = tmp_path / source.name
    shutil.copy2(source, target)
    before = target.read_bytes()
    report = listings_csv.upsert(target, [])
    assert not report.written
    assert target.read_bytes() == before


def _row(path, key):
    _, rows = listings_csv.read_csv(path)
    return next(r for r in rows if listing_id(r["url"]) == key)


def _listing_from(row, **overrides):
    """Rebuild a Listing from a file row, so a re-scrape can be simulated."""
    fields = dict(
        url=row["url"],
        page=int(row["page"]),
        position=int(row["position"]),
        grade=row["grade"],
        title=row["title"],
        year_build=row["year_build"],
        price_raw=row["price_raw"],
        price_idr=int(row["price_idr"]) if row["price_idr"] else None,
        listed_raw=row["listed_raw"],
        listed_left=row["listed_left"],
        listed_right=row["listed_right"],
        sold=row["sold"] == "True",
        sold_label=row["sold_label"],
        image=row["image"],
        scraped_at=row["scraped_at_utc"],
        card_text=row["card_text"],
    )
    fields.update(overrides)
    return Listing(**fields)


def test_rescraping_the_same_listings_writes_nothing(tmp_path):
    """Re-running must be a true no-op, not a rewrite with identical content."""
    target = tmp_path / "ibid_motor_data.csv"
    shutil.copy2(MOTOR, target)
    _, rows = listings_csv.read_csv(target)
    before = target.read_bytes()
    report = listings_csv.upsert(target, [_listing_from(r) for r in rows])
    assert (report.added, report.revised, report.written) == (0, 0, False)
    assert report.unchanged == len(rows)
    assert target.read_bytes() == before


def test_scraped_at_is_frozen_at_first_sight(tmp_path):
    """A fresh stamp every run would rewrite the file and back it up every run."""
    target = tmp_path / "ibid_motor_data.csv"
    shutil.copy2(MOTOR, target)
    _, rows = listings_csv.read_csv(target)
    row = rows[0]
    key = listing_id(row["url"])
    original = row["scraped_at_utc"]

    listings_csv.upsert(
        target,
        [_listing_from(row, scraped_at="2099-01-01T00:00:00", price_idr=1)],
    )
    assert _row(target, key)["scraped_at_utc"] == original


def test_page_and_position_are_frozen_at_first_sight(tmp_path):
    """They say where a listing sat when found; tracking today's page churns."""
    target = tmp_path / "ibid_motor_data.csv"
    shutil.copy2(MOTOR, target)
    _, rows = listings_csv.read_csv(target)
    row = rows[0]
    key = listing_id(row["url"])

    listings_csv.upsert(target, [_listing_from(row, page=99, position=7, price_idr=1)])
    after = _row(target, key)
    assert (after["page"], after["position"]) == (row["page"], row["position"])


def test_a_price_change_is_a_revision(tmp_path):
    target = tmp_path / "ibid_motor_data.csv"
    shutil.copy2(MOTOR, target)
    _, rows = listings_csv.read_csv(target)
    row = rows[0]
    report = listings_csv.upsert(
        target, [_listing_from(row, price_idr=1, price_raw="Rp 1")]
    )
    assert (report.added, report.revised) == (0, 1)
    assert report.written
    assert _row(target, listing_id(row["url"]))["price_idr"] == "1"


def test_a_sale_at_an_unchanged_price_is_still_a_revision(tmp_path):
    """The comparison is over the whole row, not one value column."""
    target = tmp_path / "ibid_motor_data.csv"
    shutil.copy2(MOTOR, target)
    _, rows = listings_csv.read_csv(target)
    unsold = next(r for r in rows if r["sold"] == "False")
    report = listings_csv.upsert(
        target, [_listing_from(unsold, sold=True, sold_label="Terjual")]
    )
    assert report.revised == 1
    after = _row(target, listing_id(unsold["url"]))
    assert (after["sold"], after["sold_label"]) == ("True", "Terjual")
    assert after["price_idr"] == unsold["price_idr"]


def test_a_new_listing_is_added_and_nothing_is_dropped(tmp_path):
    """Accumulating: the row count only ever grows."""
    target = tmp_path / "ibid_motor_data.csv"
    shutil.copy2(MOTOR, target)
    _, before = listings_csv.read_csv(target)
    fresh = Listing(
        url="https://www.ibid.astra.co.id/detail-lelang/motor/brand-new/999999999999",
        page=1,
        position=1,
        title="HONDA VARIO - 125 (2024 - AT)",
        price_raw="Rp 15.000.000",
        price_idr=15000000,
        scraped_at="2026-09-15T00:00:00",
    )
    report = listings_csv.upsert(target, [fresh])
    _, after = listings_csv.read_csv(target)
    assert (report.added, report.revised) == (1, 0)
    assert len(after) == len(before) + 1
    urls = {r["url"] for r in after}
    assert all(r["url"] in urls for r in before)


def test_an_absent_listing_keeps_its_row(tmp_path):
    """A vehicle that sold and left the site is exactly what we want to keep."""
    target = tmp_path / "ibid_motor_data.csv"
    shutil.copy2(MOTOR, target)
    _, before = listings_csv.read_csv(target)
    listings_csv.upsert(
        target,
        [
            Listing(
                url="https://www.ibid.astra.co.id/detail-lelang/motor/x/999999999999",
                page=1,
                position=1,
                scraped_at="2026-09-15T00:00:00",
            )
        ],
    )
    _, after = listings_csv.read_csv(target)
    assert len(after) == len(before) + 1


def test_lf_endings_and_quoting_survive_a_write(tmp_path):
    target = tmp_path / "ibid_motor_data.csv"
    shutil.copy2(MOTOR, target)
    _, rows = listings_csv.read_csv(target)
    commas = next(r for r in rows if "," in r["card_text"])
    listings_csv.upsert(target, [_listing_from(commas, price_idr=2)])
    raw = target.read_bytes()
    assert b"\r\n" not in raw and raw.endswith(b"\n")
    # The comma-bearing field must come back intact, i.e. it was quoted.
    assert _row(target, listing_id(commas["url"]))["card_text"] == commas["card_text"]


def test_a_second_run_after_a_real_change_is_a_no_op(tmp_path):
    target = tmp_path / "ibid_motor_data.csv"
    shutil.copy2(MOTOR, target)
    _, rows = listings_csv.read_csv(target)
    change = [_listing_from(rows[0], price_idr=123)]
    assert listings_csv.upsert(target, change).written
    first = target.read_bytes()
    assert not listings_csv.upsert(target, change).written
    assert target.read_bytes() == first


def test_dry_run_reports_without_writing(tmp_path):
    target = tmp_path / "ibid_motor_data.csv"
    shutil.copy2(MOTOR, target)
    _, rows = listings_csv.read_csv(target)
    before = target.read_bytes()
    report = listings_csv.upsert(
        target, [_listing_from(rows[0], price_idr=5)], dry_run=True
    )
    assert report.revised == 1 and not report.written
    assert target.read_bytes() == before


def test_a_created_file_gets_the_sixteen_column_header(tmp_path):
    target = tmp_path / "new.csv"
    report = listings_csv.upsert(
        target,
        [
            Listing(
                url="https://x/detail-lelang/motor/y/12345",
                page=1,
                position=1,
                scraped_at="2026-09-15T00:00:00",
            )
        ],
    )
    assert report.created and report.added == 1
    header, _ = listings_csv.read_csv(target)
    assert header == list(listings_csv.DEFAULT_HEADER)
    assert len(header) == 16


# ------------------------------------------------- the two sinks stay apart


def test_the_listings_sink_refuses_a_series_csv(tmp_path):
    """Cross-wiring the sinks would destroy the target, so both sinks check."""
    target = tmp_path / "bi_seki.csv"
    shutil.copy2(DATASET / "Consumption" / "bi_seki.csv", target)
    with pytest.raises(listings_csv.NotAListingsTable):
        listings_csv.upsert(target, [])


def test_the_series_sink_refuses_a_listings_csv(tmp_path):
    """Without this guard every listing collapses onto one empty key.

    ``series_id`` and ``ref_date`` are absent from a listings row, so the whole
    file was rewritten as a single row before the guard existed.
    """
    target = tmp_path / "ibid_motor_data.csv"
    shutil.copy2(MOTOR, target)
    before = target.read_bytes()
    with pytest.raises(long_csv.NotALongTable):
        long_csv.upsert(target, [])
    assert target.read_bytes() == before


def test_a_blank_value_never_erases_what_is_on_file(tmp_path):
    """Missing is missing -- the same rule the food-price sink gives its dashes.

    ibid renders a bundled placeholder for listings whose photo is not
    published. Taking that as the new value replaced real photo URLs with a
    placeholder across thousands of rows, which is how this rule was found.
    """
    target = tmp_path / "ibid_motor_data.csv"
    shutil.copy2(MOTOR, target)
    _, rows = listings_csv.read_csv(target)
    with_image = next(r for r in rows if r["image"])
    key = listing_id(with_image["url"])

    report = listings_csv.upsert(target, [_listing_from(with_image, image="")])
    assert report.revised == 0 and not report.written
    assert _row(target, key)["image"] == with_image["image"]


def test_a_real_value_still_replaces_a_blank_one(tmp_path):
    """Sticky-when-blank must not freeze a column that was empty."""
    target = tmp_path / "ibid_motor_data.csv"
    shutil.copy2(MOTOR, target)
    _, rows = listings_csv.read_csv(target)
    blank = next((r for r in rows if not r["sold_label"]), None)
    assert blank is not None
    listings_csv.upsert(target, [_listing_from(blank, sold=True, sold_label="Terjual")])
    assert _row(target, listing_id(blank["url"]))["sold_label"] == "Terjual"
