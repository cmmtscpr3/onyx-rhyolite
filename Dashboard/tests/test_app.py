"""The Streamlit app itself, run headless through Streamlit's test harness."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["overview", "pihps", "bps_inflation", "spip", "seki.render_gdp", "seki.render_deposits", "consumer_survey", "ojk", "ecommerce", "ibid"]


def _page_script(page_name, root):
    import sys

    sys.path.insert(0, root)
    import importlib

    # "module" runs its render(); "module.function" runs that function, for a
    # module that serves more than one page.
    module_name, _, function = page_name.partition(".")
    module = importlib.import_module(f"dashboard.pages.{module_name}")
    getattr(module, function or "render")()


def test_entrypoint_runs_without_exceptions():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=300)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert at.title[0].value == "Indonesia Indicators"


def test_code_changed_under_a_running_app_is_imported_again():
    """Streamlit Community Cloud pulls each commit into the running app
    without a restart.  The app has to import the changed code rather than
    keep serving what it first loaded, or new data appears under old code."""
    import os
    import sys

    AppTest.from_file(str(ROOT / "app.py"), default_timeout=300).run()
    before = sys.modules["dashboard.charts"]
    source = ROOT / "dashboard" / "charts.py"
    stat = source.stat()
    # The app looks for the newest file of either package, so the edit has to
    # be dated past every file -- in a checkout where other files were edited
    # since, a minute on top of this file's own time is not enough.
    newest = max(path.stat().st_mtime for folder in (ROOT / "dashboard", ROOT.parent / "Collectors" / "collectors") for path in folder.rglob("*.py"))
    try:
        AppTest.from_file(str(ROOT / "app.py"), default_timeout=300).run()
        assert sys.modules["dashboard.charts"] is before, "unchanged code is not imported again"
        os.utime(source, (stat.st_atime, newest + 60))
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=300)
        at.run()
        assert not at.exception, [e.message for e in at.exception]
        assert sys.modules["dashboard.charts"] is not before, "changed code is imported again"
    finally:
        os.utime(source, (stat.st_atime, stat.st_mtime))


@pytest.mark.parametrize("page", PAGES)
def test_each_page_renders(page):
    at = AppTest.from_function(_page_script, kwargs={"page_name": page, "root": str(ROOT)}, default_timeout=300)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert at.title, "every page has a title"
    if page != "overview":
        assert at.dataframe, "every dataset page shows a latest-values table"


@pytest.mark.parametrize(
    "page, bar, expected",
    [
        ("pihps", "", "Week-on-week % change"),
        ("spip", "spip:E-money:", "Month-on-month % change"),
        ("ecommerce", "", "Month-on-month % change"),
        # ASPI's quarterly QRIS shares the payment page, on a tab of its own,
        # and keeps the comparison its own cadence calls for.
        ("spip", "spip:QRIS:", "Year-on-year % change"),
    ],
)
def test_show_as_offers_levels_and_the_frequencys_own_comparison(page, bar, expected):
    at = AppTest.from_function(_page_script, kwargs={"page_name": page, "root": str(ROOT)}, default_timeout=300)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    shown = [control for control in at.segmented_control if control.label == "Show as" and control.key.startswith(bar)]
    assert shown, f"{page} has no Show-as control under {bar!r}"
    for control in shown:
        assert list(control.options) == ["Level", expected]


def test_spip_page_groups_charts_by_category_tabs():
    at = AppTest.from_function(_page_script, kwargs={"page_name": "spip", "root": str(ROOT)}, default_timeout=300)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert [tab.label for tab in at.tabs] == ["E-money", "Cards", "Currency and BI-RTGS", "QRIS"]
    # One chart per tab, chosen with a measure switch, instead of a stack of twelve.
    # The switch shares the filter bar with the chart's own controls, and is a
    # dropdown here because several of these measures are a line long.
    measures = [box for box in at.selectbox if box.label == "Measure"]
    assert [len(box.options) for box in measures] == [5, 3, 4, 2]
    assert len(at.dataframe) == 4
    # The last tab is ASPI's QRIS, a dataset of its own: it introduces itself
    # with its own notes and official description, as its page used to.
    assert "ASPI" in at.title[0].value
    labels = [expander.label for expander in at.expander]
    assert labels.count("About this data") == 2 and labels.count("Official description") == 2


def test_bps_inflation_page_puts_each_visualisation_on_its_own_tab():
    at = AppTest.from_function(_page_script, kwargs={"page_name": "bps_inflation", "root": str(ROOT)}, default_timeout=300)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert [tab.label for tab in at.tabs] == ["Headline", "Provinces", "Components"]
    # The headline tab offers both measures and starts with both on; the
    # components tab offers BI's four series.
    # The harness reports the options as labelled on screen.
    measures = at.multiselect(key="bps_inflation:headline:measures")
    assert list(measures.options) == ["Year-on-year", "Month-on-month"] and list(measures.value) == ["yoy", "mtm"]
    assert len(at.multiselect(key="bps_inflation:components:series").options) == 4
    # Two latest-value tables and the province table.
    assert len(at.dataframe) == 3
    # No Show-as: a percentage change of a rate says nothing.
    assert not [control for control in at.segmented_control if control.label == "Show as"]


def test_overview_lists_the_sidebars_datasets_in_its_order():
    at = AppTest.from_function(_page_script, kwargs={"page_name": "overview", "root": str(ROOT)}, default_timeout=300)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    table = at.dataframe[0].value
    assert list(table.columns)[:2] == ["Dataset", "Type"]
    assert list(table["Dataset"]) == [
        "BPS Inflation",
        "PIHPS: weekly food prices",
        "Survei Konsumen: consumer survey",
        "SEKI: economic and financial statistics",
        "SPIP: payment system statistics",
        "QRIS transactions",
        "ibid vehicle auctions",
    ]
    assert list(table["Type"]) == ["Official", "Exploratory", "Official", "Official", "Exploratory", "Exploratory", "Exploratory"]
    # The Datasets list under the table is built from the same rows.
    bullets = [m.value for m in at.markdown if m.value.startswith("- ")]
    assert [b.split("**")[1] for b in bullets] == list(table["Dataset"])
    assert [b.split("(")[1].split(")")[0] for b in bullets] == list(table["Type"])


def test_qris_is_a_tab_of_the_payment_page_not_a_page_of_its_own(monkeypatch):
    import runpy

    import streamlit as st

    captured = {}

    class _Nav:
        def run(self):
            pass

    def navigation(pages, **kwargs):
        captured.update(pages)
        return _Nav()

    # st.Page needs a running app, so record its arguments instead.
    monkeypatch.setattr(st, "Page", lambda page, **kwargs: kwargs)
    monkeypatch.setattr(st, "navigation", navigation)
    runpy.run_path(str(ROOT / "app.py"))
    paths = {page["url_path"]: page["title"] for section in captured.values() for page in section if "url_path" in page}
    assert "qris" not in paths
    assert "ASPI" in paths["spip"]
    assert "seki-gdp" in paths


def test_seki_deposits_page_has_no_gdp_switch():
    at = AppTest.from_function(_page_script, kwargs={"page_name": "seki.render_deposits", "root": str(ROOT)}, default_timeout=300)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert not [control for control in at.segmented_control if control.key == "seki:gdp:switch"]
    assert at.dataframe


def test_every_page_gathers_its_inputs_into_one_filter_bar():
    """Every input a page offers is a segmented control or a dropdown in its
    bar; nothing is left as a loose row of radio buttons beside the chart."""
    for page in PAGES:
        at = AppTest.from_function(_page_script, kwargs={"page_name": page, "root": str(ROOT)}, default_timeout=300)
        at.run()
        assert not at.exception, [e.message for e in at.exception]
        assert not at.radio, f"{page} still has a loose radio: {[r.label for r in at.radio]}"


def test_a_switch_and_the_chart_it_picks_share_one_bar():
    at = AppTest.from_function(_page_script, kwargs={"page_name": "seki.render_gdp", "root": str(ROOT)}, default_timeout=300)
    at.run()
    basis = at.segmented_control(key="seki:gdp:switch")
    assert list(basis.options) == ["Current prices", "Constant prices"]
    # The switch names the chart, so the heading above the bar does not repeat it.
    assert "Current prices" not in [markdown.value.lstrip("# ") for markdown in at.markdown]
    # Flipping it re-reads the rest of the bar for the chart it landed on: BI
    # publishes fewer expenditure components at constant prices.
    assert len(at.multiselect(key="seki:gdp:gdp_current:series").options) == 6
    at.segmented_control(key="seki:gdp:switch").set_value("Constant prices").run()
    assert not at.exception, [e.message for e in at.exception]
    assert len(at.multiselect(key="seki:gdp:gdp_constant:series").options) == 4


def test_consumer_survey_page_shows_official_definitions():
    at = AppTest.from_function(_page_script, kwargs={"page_name": "consumer_survey", "root": str(ROOT)}, default_timeout=300)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    labels = [expander.label for expander in at.expander]
    assert "Official description" in labels
    assert labels.count("Official definitions") >= 2  # the confidence chart and the budget-share chart
