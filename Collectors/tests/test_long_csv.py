"""The long-CSV sink: merge without disturbing what is already there."""

from __future__ import annotations

import datetime as dt
import shutil

import pytest

from collectors.model import Obs
from collectors.sinks import long_csv
from collectors.paths import DATASET
from conftest import long_series_csvs

#: Only the long series tables; the ibid listings files in the same folder are
#: a different shape and have their own suite.
REAL = long_series_csvs()


@pytest.mark.parametrize("source", REAL, ids=lambda p: p.name)
def test_read_then_render_is_byte_identical(source):
    """Rendering what we read must reproduce the file exactly.

    This is the whole contract in one assertion: CRLF line endings including
    the final line, no quoting, rows ordered by series then date, and every
    value's full precision left alone.
    """
    header, rows = long_csv.read_csv(source)
    assert long_csv.render(header, rows) == source.read_bytes()


@pytest.mark.parametrize("source", REAL, ids=lambda p: p.name)
def test_upserting_nothing_writes_nothing(source, tmp_path):
    target = tmp_path / source.name
    shutil.copy2(source, target)
    before = target.read_bytes()
    report = long_csv.upsert(target, [])
    assert not report.written
    assert target.read_bytes() == before


def test_existing_header_wins_over_the_default(tmp_path):
    """A six-column file stays six columns; it is never 'upgraded'."""
    target = tmp_path / "bi_emoney.csv"
    shutil.copy2(DATASET / "Consumption" / "bi_emoney.csv", target)
    long_csv.upsert(
        target,
        [Obs("bi_emoney.value", dt.date(2026, 7, 1), 100.5, "IDR billion")],
    )
    header, rows = long_csv.read_csv(target)
    assert header == ["series_id", "geo_id", "geo_name", "ref_date", "value", "unit"]
    assert "ref_period" not in header


def test_eight_column_file_keeps_its_frequency_columns(tmp_path):
    target = tmp_path / "bi_seki.csv"
    shutil.copy2(DATASET / "Consumption" / "bi_seki.csv", target)
    long_csv.upsert(
        target,
        [Obs("bi_seki.deposits_by_owner.households", dt.date(2026, 8, 1), 1.0, "IDR billion")],
    )
    header, rows = long_csv.read_csv(target)
    assert header[4:6] == ["ref_period", "frequency"]
    added = next(r for r in rows if r["ref_date"] == "2026-08-01" and "households" in r["series_id"])
    assert (added["ref_period"], added["frequency"]) == ("M", "monthly")


def test_a_new_row_lands_in_sorted_position_not_at_the_tail(tmp_path):
    """Files are ordered by series then date, so appending would corrupt that."""
    target = tmp_path / "bi_emoney.csv"
    shutil.copy2(DATASET / "Consumption" / "bi_emoney.csv", target)
    long_csv.upsert(
        target,
        [Obs("bi_emoney.float_funds", dt.date(2026, 7, 1), 42.0, "IDR billion")],
    )
    _, rows = long_csv.read_csv(target)
    keys = [(r["series_id"], r["ref_date"]) for r in rows]
    assert keys == sorted(keys)


def test_untouched_rows_keep_their_exact_precision(tmp_path):
    """Full float64 reprs already on disk must not be reformatted."""
    target = tmp_path / "bi_emoney.csv"
    shutil.copy2(DATASET / "Consumption" / "bi_emoney.csv", target)
    long_csv.upsert(
        target,
        [Obs("bi_emoney.volume_topup", dt.date(2026, 7, 1), 1.0, "thousand transactions")],
    )
    _, rows = long_csv.read_csv(target)
    march = next(
        r for r in rows if r["series_id"] == "bi_emoney.volume_topup" and r["ref_date"] == "2026-03-01"
    )
    assert march["value"] == "674479.8950000051"


def test_a_changed_value_is_a_revision(tmp_path):
    target = tmp_path / "bi_emoney.csv"
    shutil.copy2(DATASET / "Consumption" / "bi_emoney.csv", target)
    report = long_csv.upsert(
        target,
        [Obs("bi_emoney.volume_topup", dt.date(2026, 3, 1), 674480.0, "thousand transactions")],
    )
    assert (report.added, report.revised) == (0, 1)
    assert report.revisions[0][2:] == ("674479.8950000051", "674480.0")


def test_an_identical_value_is_neither_added_nor_revised(tmp_path):
    target = tmp_path / "bi_emoney.csv"
    shutil.copy2(DATASET / "Consumption" / "bi_emoney.csv", target)
    report = long_csv.upsert(
        target,
        [Obs("bi_emoney.volume_topup", dt.date(2026, 3, 1), 674479.8950000051, "thousand transactions")],
    )
    assert (report.added, report.revised, report.unchanged) == (0, 0, 1)
    assert not report.written


def test_a_second_identical_run_is_byte_identical(tmp_path):
    target = tmp_path / "bi_emoney.csv"
    shutil.copy2(DATASET / "Consumption" / "bi_emoney.csv", target)
    observations = [Obs("bi_emoney.value", dt.date(2026, 7, 1), 55.25, "IDR billion")]
    long_csv.upsert(target, observations)
    first = target.read_bytes()
    report = long_csv.upsert(target, observations)
    assert not report.written
    assert target.read_bytes() == first


def test_crlf_survives_a_write(tmp_path):
    target = tmp_path / "bi_emoney.csv"
    shutil.copy2(DATASET / "Consumption" / "bi_emoney.csv", target)
    long_csv.upsert(target, [Obs("bi_emoney.value", dt.date(2026, 7, 1), 1.0, "IDR billion")])
    raw = target.read_bytes()
    assert raw.endswith(b"\r\n")
    assert raw.count(b"\r\n") == raw.count(b"\n")


def test_geo_id_keeps_its_leading_zeros(tmp_path):
    target = tmp_path / "new.csv"
    long_csv.upsert(target, [Obs("x.y", dt.date(2026, 1, 1), 1.0, "percent")])
    assert b",0000," in target.read_bytes()


def test_a_new_file_gets_the_default_eight_column_header(tmp_path):
    target = tmp_path / "ojk_dpk.csv"
    report = long_csv.upsert(target, [Obs("ojk_dpk.total", dt.date(2025, 6, 1), 9.0, "IDR billion")])
    assert report.created and report.added == 1
    header, _ = long_csv.read_csv(target)
    assert header == list(long_csv.DEFAULT_HEADER)


def test_dry_run_reports_without_writing(tmp_path):
    target = tmp_path / "bi_emoney.csv"
    shutil.copy2(DATASET / "Consumption" / "bi_emoney.csv", target)
    before = target.read_bytes()
    report = long_csv.upsert(
        target,
        [Obs("bi_emoney.value", dt.date(2026, 7, 1), 1.0, "IDR billion")],
        dry_run=True,
    )
    assert report.added == 1 and not report.written
    assert target.read_bytes() == before
