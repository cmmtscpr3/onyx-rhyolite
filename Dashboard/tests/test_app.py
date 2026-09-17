"""The Streamlit app itself, run headless through Streamlit's test harness."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["overview", "pihps", "spip", "seki", "consumer_survey", "ojk", "qris", "ecommerce", "ibid"]


def _page_script(page_name, root):
    import sys

    sys.path.insert(0, root)
    import importlib

    module = importlib.import_module(f"dashboard.pages.{page_name}")
    module.render()


def test_entrypoint_runs_without_exceptions():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=300)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert at.title[0].value == "Indonesia Indicators"


@pytest.mark.parametrize("page", PAGES)
def test_each_page_renders(page):
    at = AppTest.from_function(_page_script, kwargs={"page_name": page, "root": str(ROOT)}, default_timeout=300)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert at.title, "every page has a title"
    if page != "overview":
        assert at.dataframe, "every dataset page shows a latest-values table"


@pytest.mark.parametrize(
    "page, expected",
    [
        ("pihps", "Week-on-week % change"),
        ("spip", "Month-on-month % change"),
        ("ecommerce", "Month-on-month % change"),
        ("qris", "Year-on-year % change"),
    ],
)
def test_show_as_offers_levels_and_the_frequencys_own_comparison(page, expected):
    at = AppTest.from_function(_page_script, kwargs={"page_name": page, "root": str(ROOT)}, default_timeout=300)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    shown = [control for control in at.segmented_control if control.label == "Show as"]
    assert shown, f"{page} has no Show-as control"
    for control in shown:
        assert list(control.options) == ["Level", expected]


def test_spip_page_groups_charts_by_category_tabs():
    at = AppTest.from_function(_page_script, kwargs={"page_name": "spip", "root": str(ROOT)}, default_timeout=300)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert [tab.label for tab in at.tabs] == ["E-money", "Cards", "Currency and BI-RTGS"]
    # One chart per tab, chosen with a measure switch, instead of a stack of twelve.
    # The switch shares the filter bar with the chart's own controls, and is a
    # dropdown here because several of these measures are a line long.
    measures = [box for box in at.selectbox if box.label == "Measure"]
    assert [len(box.options) for box in measures] == [5, 3, 4]
    assert len(at.dataframe) == 3


def test_every_page_gathers_its_inputs_into_one_filter_bar():
    """Every input a page offers is a segmented control or a dropdown in its
    bar; nothing is left as a loose row of radio buttons beside the chart."""
    for page in PAGES:
        at = AppTest.from_function(_page_script, kwargs={"page_name": page, "root": str(ROOT)}, default_timeout=300)
        at.run()
        assert not at.exception, [e.message for e in at.exception]
        assert not at.radio, f"{page} still has a loose radio: {[r.label for r in at.radio]}"


def test_a_switch_and_the_chart_it_picks_share_one_bar():
    at = AppTest.from_function(_page_script, kwargs={"page_name": "seki", "root": str(ROOT)}, default_timeout=300)
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
