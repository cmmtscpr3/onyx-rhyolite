"""Figures and chart assembly: every default chart builds, one axis each,
colours fixed per series."""

from __future__ import annotations

import pytest

from dashboard import catalogue, charts, data, figures, theme
from dashboard.transform import LEVEL, comparison


@pytest.fixture(scope="session")
def bundle(series, pihps, lots):
    return charts.Bundle(series=series, pihps=pihps, lots=lots, fingerprint=data.fingerprint())


def test_every_default_chart_builds(bundle):
    built = charts.default_charts(bundle)
    assert [dataset.key for dataset, _ in built] == [d.key for d in catalogue.DATASETS]
    for dataset, chart_list in built:
        assert chart_list, dataset.key
        for chart in chart_list:
            figure = chart.figure
            assert figure.data, f"{dataset.key}/{chart.key} has no traces"
            assert "yaxis2" not in figure.layout, "one axis per chart"
            assert not chart.table.empty, f"{dataset.key}/{chart.key} has no table"
            if isinstance(chart, charts.Panel):
                continue  # a distribution: bars or boxes, checked in their own tests
            for trace in figure.data:
                assert any(y is not None and y == y for y in trace.y), f"{chart.key}: {trace.name} is empty"
            assert figure.layout.showlegend == (len(figure.data) >= 2)
            assert all(trace.line.width == 2 for trace in figure.data)


def test_group_chart_keeps_group_order_and_colours(bundle):
    group = catalogue.group("spip", "emoney_value")
    full = charts.group_chart(bundle.series, group)
    partial = charts.group_chart(bundle.series, group, selected=["bi_emoney.value_topup"])
    colours_full = {trace.name: trace.line.color for trace in full.figure.data}
    colours_partial = {trace.name: trace.line.color for trace in partial.figure.data}
    assert list(colours_full) == [group.label(s) for s in group.series]
    # Deselecting series does not repaint the survivors.
    assert colours_partial["Top-ups"] == colours_full["Top-ups"]
    assert full.frequency == "monthly"


def test_each_chart_compares_over_its_own_publication_interval(bundle):
    monthly = charts.group_chart(
        bundle.series, catalogue.group("consumer_survey", "confidence"), mode=comparison("monthly").label, since_year=2024
    )
    assert monthly.frequency == "monthly"
    assert monthly.figure.layout.yaxis.title.text == "% change on a month earlier"
    quarterly = charts.group_chart(
        bundle.series, catalogue.group("seki", "gdp_current"), mode=comparison("quarterly").label, since_year=2020
    )
    assert quarterly.frequency == "quarterly"
    assert quarterly.figure.layout.yaxis.title.text == "% change on a year earlier"
    weekly = charts.pihps_chart(bundle.pihps, mode=comparison("weekly").label, since_year=2025)
    assert weekly.figure.layout.yaxis.title.text == "% change on a week earlier"
    # The table under each chart stays on levels whatever the chart shows.
    assert monthly.table.loc[monthly.table["Series"].str.startswith("Consumer Confidence"), "Value"].iloc[0] == pytest.approx(118.5)


def test_a_chart_shows_levels_or_one_change_and_nothing_else(bundle):
    group = catalogue.group("spip", "emoney_value")
    assert charts.group_chart(bundle.series, group).mode == LEVEL
    assert figures.axis_title("IDR billion", LEVEL) == "IDR billion"
    # Deselecting a series must not change what the comparison means.
    frequency = charts.group_chart(bundle.series, group, selected=["bi_emoney.value_topup"]).frequency
    assert frequency == charts.group_chart(bundle.series, group).frequency == "monthly"


def test_ecommerce_break_is_marked(bundle):
    dataset = catalogue.BY_KEY["ecommerce"]
    chart = charts.group_chart(bundle.series, dataset.groups[0], annotations=dataset.annotations)
    texts = [a.text for a in chart.figure.layout.annotations]
    assert "Total market rebased" in texts
    assert any(str(shape.x0).startswith("2025-04-01") for shape in chart.figure.layout.shapes)


def test_pihps_chart_defaults_and_styles(bundle):
    chart = charts.pihps_chart(bundle.pihps)
    names = [trace.name for trace in chart.figure.data]
    assert names == list(charts.PIHPS_DEFAULT)
    colours, dashes = charts.pihps_styles(data.pihps_commodities(bundle.pihps))
    assert len(colours) == 31
    assert colours["Beras Kualitas Medium I"] == colours["Beras"]
    assert dashes["Beras"] == "solid" and dashes["Beras Kualitas Medium I"] != "solid"
    # Ten groups, eight hues: the last two reuse hues but with a long dash.
    assert colours["Minyak Goreng"] == colours["Beras"] and dashes["Minyak Goreng"] == "longdash"
    beras = chart.table[chart.table["Series"] == "Beras"].iloc[0]
    assert beras["Value"] == 16350 or beras["Latest"].year >= 2026


def test_freshness_table_marks_the_known_states(bundle):
    import datetime as dt

    table = charts.freshness_table(bundle, now=dt.date(2026, 9, 16)).set_index("key")
    assert table.loc["pihps", "Status"] == "fresh"
    assert table.loc["ojk", "Status"] == "stale"
    assert table.loc["qris", "Status"] == "manual"
    assert table.loc["ibid", "Status"] == "manual"
    assert table.loc["consumer_survey", "Status"] in {"fresh", "late"}
    assert table.loc["pihps", "Latest observation"] >= dt.date(2026, 9, 10)


def test_colour_map_never_generates_a_ninth_hue():
    ids = [f"s{i}" for i in range(11)]
    colours = theme.colour_map(ids)
    assert len(set(colours[s] for s in ids[:8])) == 8
    assert colours["s8"] == colours["s9"] == theme.CHROME["light"]["muted"]
    dashes = theme.dash_map(ids)
    assert dashes["s0"] == "solid" and dashes["s8"] != dashes["s9"]


def test_precision_follows_magnitude():
    import pandas as pd

    big = pd.DataFrame({"a": [1500.0, 2500.0]})
    small = pd.DataFrame({"a": [1.5, 2.5]})
    assert figures.precision(big, "IDR billion") == 0
    assert figures.precision(small, "IDR billion") == 2
    assert figures.precision(big, "index") == 1
    assert figures.precision(big, "IDR billion", comparison("monthly").label) == 1


def test_breakdowns_label_every_lot_they_can_place(bundle):
    cars = charts.lots_subset(bundle.lots, "cars")
    by = charts.BY_BREAKDOWN
    assert len(charts.labelled(cars, by["brand"])) == len(cars)
    assert charts.labelled(cars, by["model"]).iloc[0].count(" ") >= 1
    # Ungraded lots are named, not dropped, and years read as plain years.
    assert charts.UNGRADED in set(charts.labelled(cars, by["grade"]))
    assert charts.labelled(cars, by["year"]).str.fullmatch(r"\d{4}").all()


def test_counts_rank_names_and_keep_an_ordered_scale_in_order(bundle):
    by = charts.BY_BREAKDOWN
    brands = charts.counts(bundle.lots, "cars", by["brand"])
    assert list(brands["label"][:2]) == ["TOYOTA", "DAIHATSU"]
    assert brands["lots"].is_monotonic_decreasing
    assert brands["lots"].sum() == len(charts.lots_subset(bundle.lots, "cars"))
    assert brands["share"].sum() == pytest.approx(100.0)
    models = charts.counts(bundle.lots, "cars", by["model"])
    assert models["label"].iloc[0] == "TOYOTA AVANZA"
    assert charts.counts(bundle.lots, "motorcycles", by["model"])["label"].iloc[0] == "HONDA BEAT"
    # Grades keep ibid's own order, best first and ungraded last, however many sold.
    grades = charts.counts(bundle.lots, "cars", by["grade"])
    assert list(grades["label"]) == ["A", "B", "C", "D", "E", charts.UNGRADED]
    years = charts.counts(bundle.lots, "cars", by["year"])
    assert years["label"].is_monotonic_increasing
    # Unsold lots are in scope only when asked for.
    assert charts.counts(bundle.lots, "cars", by["brand"], sold_only=False)["lots"].sum() > brands["lots"].sum()


def test_price_ranges_are_quartiles_and_true_extremes(bundle):
    by = charts.BY_BREAKDOWN
    models = charts.price_ranges(bundle.lots, "cars", by["model"])
    assert len(models) == charts.TOP_SHOWN
    assert models["median"].is_monotonic_decreasing  # names read against each other in price order
    for row in models.itertuples(index=False):
        assert row.minimum <= row.p5 <= row.p25 <= row.median <= row.p75 <= row.p95 <= row.maximum
        assert row.lots >= charts.MIN_PRICED_LOTS
    assert 10 < models["median"].iloc[0] < 1000  # millions of rupiah, so a car is a two- or three-digit number
    # An ordered scale keeps its sequence and is not cut to the top rows.
    grades = charts.price_ranges(bundle.lots, "cars", by["grade"])
    assert list(grades["label"]) == ["A", "B", "C", "D", "E", charts.UNGRADED]
    assert grades.loc[grades["label"] == "A", "median"].iloc[0] > grades.loc[grades["label"] == "E", "median"].iloc[0]
    years = charts.price_ranges(bundle.lots, "cars", by["year"])
    assert years["label"].is_monotonic_increasing and len(years) > charts.TOP_SHOWN
    assert (years["lots"] >= charts.MIN_PRICED_LOTS).all()  # a year of one lot has no range worth drawing


def test_panels_carry_a_figure_and_the_whole_table(bundle):
    by = charts.BY_BREAKDOWN
    brands = charts.count_panel(bundle.lots, "cars", by["brand"])
    bars = brands.figure.data[0]
    assert len(bars.y) == charts.TOP_SHOWN and bars.orientation == "h"
    assert isinstance(bars.marker.color, str)  # one hue: the bar length already carries the count
    assert not brands.figure.layout.showlegend
    # The chart is cut to the top rows; the table keeps all of them.
    assert len(brands.table) == len(charts.counts(bundle.lots, "cars", by["brand"]))
    assert "Brand" in brands.table.columns and "Share of lots" in brands.table.columns
    # An ordered scale runs along the bottom instead, so its sequence reads left to right.
    years = charts.count_panel(bundle.lots, "cars", by["year"])
    assert years.figure.data[0].orientation != "h"
    assert years.figure.layout.xaxis.type == "category"
    ranges = charts.price_ranges(bundle.lots, "motorcycles", by["grade"])
    prices = charts.price_panel(bundle.lots, "motorcycles", by["grade"])
    # One box per grade, plus the single hover layer that answers for all of them.
    assert len(prices.figure.data) == len(ranges) + 1
    assert prices.figure.layout.yaxis.title.text == charts.PRICE_UNIT  # vertical: price on the y-axis
    assert list(prices.table.columns)[:3] == ["Grade", "Lots", "Lowest"]
    # The whiskers are the 5th and 95th percentile, and say so rather than claiming to be the extremes.
    box = prices.figure.data[0]
    assert box.lowerfence[0] == pytest.approx(ranges["p5"].iloc[0])
    assert box.upperfence[0] == pytest.approx(ranges["p95"].iloc[0])
    assert box.hoverinfo == "skip"
    assert "5th to 95th" in prices.figure.data[-1].hovertemplate
    assert "5th and 95th percentile" in prices.note


def test_the_export_carries_the_ibid_panels(bundle):
    built = dict((dataset.key, items) for dataset, items in charts.default_charts(bundle))
    panels = built["ibid"]
    assert [panel.title for panel in panels] == [
        "Lots by brand", "Listed price by brand", "Lots by brand", "Listed price by brand",
    ]
    assert all(isinstance(panel, charts.Panel) for panel in panels)
