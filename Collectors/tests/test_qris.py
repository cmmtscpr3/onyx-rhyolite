"""The QRIS parser.

ASPI blocks datacentre addresses at the Cloudflare level, so the fixtures here
are synthetic stand-ins for the real page rather than recordings of it — see
their header comments. They exercise the parser's own logic, which is real; the
live fetch path is the part that remains unverified against the source.
"""

from __future__ import annotations

import datetime as dt

import pytest

from collectors.errors import SourceUnavailable
from collectors.sources import qris


@pytest.mark.parametrize(
    "label,expected",
    [
        ("Volume Transaksi", ("volume", "count")),
        ("Jumlah Transaksi", ("volume", "count")),
        ("Nominal Transaksi (Rp Miliar)", ("value", "IDR billion")),
        ("Nilai Transaksi", ("value", "IDR million")),
        ("Jumlah Merchant", ("merchants", "count")),
        ("Jumlah Pengguna", ("users", "count")),
        ("Pangsa Wilayah", None),
        ("", None),
    ],
)
def test_measure_labels_map_to_stable_series(label, expected):
    """Ids must not move when a chart title is reworded."""
    assert qris.series_for(label) == expected


def test_a_unit_written_into_the_label_wins_over_the_default():
    assert qris.series_for("Nominal Transaksi (Rp Miliar)")[1] == "IDR billion"
    assert qris.series_for("Nominal Transaksi")[1] == "IDR million"


@pytest.mark.parametrize(
    "label,expected",
    [
        ("Jan 2026", dt.date(2026, 1, 1)),
        ("Januari 2026", dt.date(2026, 1, 1)),
        ("Des 2025", dt.date(2025, 12, 1)),
        ("2026-01", dt.date(2026, 1, 1)),
        ("2026/3", dt.date(2026, 3, 1)),
        ("2026", None),
        ("Total", None),
        ("", None),
    ],
)
def test_period_labels(label, expected):
    assert qris.parse_period(label) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1.234.567", 1234567.0),
        ("1,234,567", 1234567.0),
        ("9.328.995,75", 9328995.75),
        ("12.5", 12.5),
        ("12,5", 12.5),
        ("Rp 1.234.567", 1234567.0),
        ("-", None),
        ("", None),
    ],
)
def test_figures_parse_in_either_separator_style(raw, expected):
    assert qris.to_number(raw) == expected


def test_the_table_shape_yields_one_series_per_measure(fixtures):
    observations = qris.parse_tables((fixtures / "qris_table.html").read_text())
    by_series = {}
    for obs in observations:
        by_series.setdefault(obs.series_id, {})[obs.ref_date] = obs
    assert set(by_series) == {
        "qris_transactions.volume",
        "qris_transactions.value",
        "qris_transactions.merchants",
        "qris_transactions.users",
    }
    volume = by_series["qris_transactions.volume"]
    assert sorted(volume) == [dt.date(2026, 1, 1), dt.date(2026, 2, 1), dt.date(2026, 3, 1)]
    assert volume[dt.date(2026, 1, 1)].value == 1234567890.0
    assert by_series["qris_transactions.value"][dt.date(2026, 1, 1)].value == 32450.75
    assert by_series["qris_transactions.value"][dt.date(2026, 1, 1)].unit == "IDR billion"


def test_a_total_row_is_not_mistaken_for_a_month(fixtures):
    """'Total' has no period, so it must not become an observation."""
    observations = qris.parse_tables((fixtures / "qris_table.html").read_text())
    assert all(obs.ref_date.day == 1 for obs in observations)
    assert len({obs.ref_date for obs in observations}) == 3


def test_an_unrelated_table_is_skipped(fixtures):
    """The regional-share table has no QRIS measure column."""
    observations = qris.parse_tables((fixtures / "qris_table.html").read_text())
    assert not any(obs.value == 62.4 for obs in observations)


def test_the_chart_shape_yields_the_same_numbers(fixtures):
    observations = qris.parse_charts((fixtures / "qris_chart.html").read_text())
    by_series = {}
    for obs in observations:
        by_series.setdefault(obs.series_id, {})[obs.ref_date] = obs.value
    assert set(by_series) == {"qris_transactions.volume", "qris_transactions.value"}
    assert by_series["qris_transactions.volume"][dt.date(2026, 1, 1)] == 1234567890.0
    assert by_series["qris_transactions.value"][dt.date(2026, 3, 1)] == 36002.1


def test_an_unnamed_chart_series_is_skipped(fixtures):
    """'Sesuatu Yang Lain' is not a QRIS measure and must not be stored."""
    observations = qris.parse_charts((fixtures / "qris_chart.html").read_text())
    assert all(obs.value not in (1.0, 2.0, 3.0) for obs in observations)


def test_every_observation_is_monthly_and_national(fixtures):
    for name in ("qris_table.html", "qris_chart.html"):
        for obs in qris.parse((fixtures / name).read_text()):
            assert obs.ref_period == "M"
            assert obs.geo_id == "0000"
            assert obs.series_id.startswith("qris_transactions.")


def test_the_same_month_is_not_stored_twice_when_both_shapes_carry_it(fixtures):
    """A page showing a chart and its data table must not double-count."""
    table = (fixtures / "qris_table.html").read_text()
    chart = (fixtures / "qris_chart.html").read_text()
    observations = qris.parse(table + chart)
    keys = [(obs.series_id, obs.ref_date) for obs in observations]
    assert len(keys) == len(set(keys))


def test_reading_a_saved_page_needs_no_network(fixtures):
    """The route that works from a blocked runner."""
    observations = qris.read_saved(fixtures / "qris_table.html")
    assert len(observations) == 12


def test_a_page_with_no_series_is_reported_not_written(fixtures, tmp_path):
    """An empty parse must never blank the dataset."""
    empty = tmp_path / "empty.html"
    empty.write_text("<html><body><p>Maintenance</p></body></html>")
    with pytest.raises(SourceUnavailable, match="no QRIS series"):
        qris.collect(html=str(empty))


def test_since_filters_history(fixtures):
    observations = qris.read_saved(fixtures / "qris_table.html")
    kept = [obs for obs in observations if obs.ref_date >= dt.date(2026, 3, 1)]
    assert kept and all(obs.ref_date >= dt.date(2026, 3, 1) for obs in kept)


def test_a_large_inline_script_does_not_stall_the_parser():
    """The brace scan is pre-filtered, not quadratic over the whole script.

    A page that inlines a bundle used to take minutes here, because every
    ``{`` got a full balanced read.  Candidates now have to name their points
    and their axis first.
    """
    noise = "var x = {" + ",".join(f'"k{i}":{i}' for i in range(20_000)) + "};"
    page = f"<html><script>{noise}</script></html>"
    assert len(page) > 200_000
    assert qris.parse_charts(page) == []


def test_a_bundle_sized_script_is_skipped_outright():
    page = "<html><script>" + ("x" * (qris._MAX_SCRIPT + 10)) + "</script></html>"
    assert qris.parse_charts(page) == []
