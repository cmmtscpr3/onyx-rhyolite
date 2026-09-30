"""BPS table 908, from a page saved in a browser.

The two table fixtures are synthetic: BPS serves the real page only to
browsers, and no saved copy was to hand when this was written.  They lay one
set of simulated rates out two opposite ways -- years down the rows, months
across the columns -- and the numbers come from a simulated index per
component, so they obey the identities BPS's own rates must.  The challenge
page is the one BPS really served, reduced to its visible text.
"""

from __future__ import annotations

import datetime as dt

import pytest

from collectors import cli
from collectors.errors import SourceUnavailable
from collectors.sources import bps_inflation
from collectors.sources.bps_inflation import TableError

SERIES = {
    f"bps_inflation.{component}.{measure}"
    for component in ("headline", "core", "administered", "volatile")
    for measure in ("mtm", "ytd")
}


def _read(fixtures, name):
    return bps_inflation.read_saved(fixtures / name)


def _rates(observations):
    return {(o.series_id, o.ref_date): o.value for o in observations}


def test_every_rate_is_read_with_years_down_the_rows(fixtures):
    """A year merged over its months, written once above eleven blanks, and
    written on every row: the three ways a spreadsheet export stacks a year."""
    observations, warnings = _read(fixtures, "bps_inflation_rows.html")
    assert {o.series_id for o in observations} == SERIES
    months = {o.ref_date for o in observations}
    assert min(months) == dt.date(2024, 1, 1) and max(months) == dt.date(2026, 8, 1)
    # 2024 and 2025 whole, 2026 to August: the blank months after it are not rates.
    assert len(months) == 32 and len(observations) == 32 * len(SERIES)
    assert warnings == []
    assert {o.unit for o in observations} == {"percent"}
    assert {o.ref_period for o in observations} == {"M"}


def test_the_same_rates_are_read_when_months_run_across_the_columns(fixtures):
    """The parser places numbers by their labels, not by where they sit, so
    turning the table round must not change a single reading."""
    rows, _ = _read(fixtures, "bps_inflation_rows.html")
    columns, warnings = _read(fixtures, "bps_inflation_columns.html")
    assert warnings == []
    by_rows, by_columns = _rates(rows), _rates(columns)
    assert len(by_columns) == 20 * len(SERIES)
    assert set(by_columns) <= set(by_rows)
    assert all(by_rows[key] == by_columns[key] for key in by_columns)


def test_rates_land_on_the_right_component_measure_and_month(fixtures):
    """Pinned against the fixture's own cells, one per decimal style."""
    rates = _rates(_read(fixtures, "bps_inflation_rows.html")[0])
    assert rates["bps_inflation.headline.mtm", dt.date(2024, 1, 1)] == -0.09
    assert rates["bps_inflation.volatile.mtm", dt.date(2025, 6, 1)] == 0.16
    assert rates["bps_inflation.volatile.ytd", dt.date(2025, 6, 1)] == 2.96
    assert rates["bps_inflation.administered.ytd", dt.date(2026, 8, 1)] == 0.75


def test_a_label_naming_several_things_names_none_of_them():
    """The title lists every component, both measures and a range of years;
    read as a heading it would give every number all of them."""
    label = bps_inflation.Label.read(
        "Inflasi Umum, Inti, Harga Diatur Pemerintah, dan Bergejolak Nasional "
        "(M-to-M dan Y-to-D), 2009-2026"
    )
    assert len(label.components) == 4 and len(label.measures) == 2 and len(label.years) == 2
    single = bps_inflation.Label.read("Harga Diatur Pemerintah")
    assert single.components == {"administered"} and not single.measures


@pytest.mark.parametrize(
    "text, expected",
    [("0,26", 0.26), ("-0,09", -0.09), ("−0,09", -0.09), ("1.07", 1.07), ("0,26*", 0.26), ("0,26%", 0.26),
     ("2024", None), ("-", None), ("", None), ("Januari", None)],
)
def test_a_rate_reads_with_either_decimal_mark_and_a_year_is_a_label(text, expected):
    assert bps_inflation.value(text) == expected


def test_the_challenge_page_is_named_for_what_it_is(fixtures):
    """What a save made before the table rendered holds."""
    with pytest.raises(SourceUnavailable, match="Cloudflare"):
        _read(fixtures, "bps_challenge.html")


def test_a_page_with_no_inflation_table_is_skipped_not_failed():
    """A wrong file is nothing to collect, not a broken parser."""
    page = "<table><tr><th>Bulan</th><th>Nilai</th></tr><tr><td>Januari 2026</td><td>5,1</td></tr></table>"
    with pytest.raises(SourceUnavailable, match="no table naming an inflation component"):
        bps_inflation.parse(page)


def test_measures_read_under_each_others_headings_write_nothing(fixtures):
    """January cannot see this -- its m-to-m and y-to-d are equal -- so it is
    the compounding identity that has to."""
    page = (fixtures / "bps_inflation_rows.html").read_text(encoding="utf-8")
    swapped = page.replace("<td>M-to-M</td><td>Y-to-D</td>", "<td>Y-to-D</td><td>M-to-M</td>")
    assert swapped != page
    with pytest.raises(TableError, match="compound"):
        bps_inflation.parse(swapped)


def test_a_header_row_one_cell_short_writes_nothing(fixtures):
    """Every measure heading slides one column left, under the wrong rate."""
    page = (fixtures / "bps_inflation_rows.html").read_text(encoding="utf-8")
    short = page.replace("<tr><td>M-to-M</td><td>Y-to-D</td>", "<tr><td>Y-to-D</td>", 1)
    with pytest.raises(TableError):
        bps_inflation.parse(short)


def test_two_numbers_under_the_same_labels_fail_rather_than_pick_one():
    page = """<table>
      <tr><th>Bulan</th><th>Umum M-to-M</th><th>Umum Y-to-D</th></tr>
      <tr><td>Januari 2026</td><td>0,50</td><td>0,50</td></tr>
      <tr><td>Januari 2026</td><td>0,70</td><td>0,70</td></tr>
    </table>"""
    with pytest.raises(TableError, match="misread"):
        bps_inflation.parse(page)


def test_numbers_the_labels_cannot_place_are_reported(fixtures):
    """A year-to-date summary row names two months, so it names none."""
    page = (fixtures / "bps_inflation_rows.html").read_text(encoding="utf-8")
    summary = "<tr><td>2026</td><td>Januari-Agustus</td>" + "<td>1,00</td>" * 8 + "</tr>"
    page = page.replace('<tr><td colspan="10">Sumber', summary + '<tr><td colspan="10">Sumber', 1)
    observations, warnings = bps_inflation.parse(page)
    assert len(observations) == 32 * len(SERIES)
    assert any(w.startswith("skipped 8 number(s) with no month") for w in warnings), warnings


def test_the_collector_needs_a_saved_page():
    with pytest.raises(SourceUnavailable, match="--html"):
        bps_inflation.collect(dry_run=True)


def test_the_inflation_target_reads_a_saved_page_end_to_end(fixtures, capsys):
    """Through run.py, as it is meant to be run.  Dry, so nothing is written."""
    path = fixtures / "bps_inflation_rows.html"
    assert cli.main(["inflation", "--html", str(path), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "bps_inflation.csv" in out and f"{32 * len(SERIES)} rows" in out
    assert "dry run: nothing written" in out
