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
            for trace in figure.data:
                assert any(y is not None and y == y for y in trace.y), f"{chart.key}: {trace.name} is empty"
            assert not chart.table.empty
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
    lots = charts.lots_charts(bundle.lots, category="cars", mode=comparison("weekly").label)[0]
    assert lots.figure.layout.yaxis.title.text == "% change on a week earlier"
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


def test_lots_charts_and_models(bundle):
    models = charts.top_models(bundle.lots, "cars")
    assert models[0] == "TOYOTA AVANZA" and len(models) == 15
    assert charts.top_models(bundle.lots, "motorcycles")[0] == "HONDA BEAT"
    price, count = charts.lots_charts(bundle.lots, category="cars", model="TOYOTA AVANZA")
    assert price.unit == "IDR" and count.unit == "lots"
    assert len(price.figure.data) == 1 and len(count.figure.data) == 1
    weeks = list(count.figure.data[0].x)
    assert len(weeks) >= 8


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


def test_brand_and_model_distributions_count_sold_lots(bundle):
    brands = charts.brand_counts(bundle.lots, "cars")
    assert list(brands["label"][:2]) == ["TOYOTA", "DAIHATSU"]
    assert brands["lots"].sum() == int(bundle.lots.query("category == 'cars' and sold").shape[0])
    assert brands["share"].sum() == pytest.approx(100.0)
    assert brands["lots"].is_monotonic_decreasing
    models = charts.model_counts(bundle.lots, "cars")
    assert models["label"].iloc[0] == "TOYOTA AVANZA"
    assert "DAIHATSU GRAN MAX" in list(models["label"][:4])
    bikes = charts.model_counts(bundle.lots, "motorcycles")
    assert bikes["label"].iloc[0] == "HONDA BEAT"
    # Unsold lots are in scope only when asked for.
    assert charts.brand_counts(bundle.lots, "cars", sold_only=False)["lots"].sum() > brands["lots"].sum()


def test_price_ranges_are_quartiles_and_true_extremes(bundle):
    ranges = charts.price_ranges(bundle.lots, "cars")
    assert len(ranges) == charts.TOP_PRICED
    # Chosen by how many sold, then ordered by price so the ranges read against each other.
    assert set(ranges["label"]) >= {"TOYOTA AVANZA", "DAIHATSU GRAN MAX"}
    assert ranges["median"].is_monotonic_decreasing
    for row in ranges.itertuples(index=False):
        assert row.minimum <= row.p25 <= row.median <= row.p75 <= row.maximum
        assert row.lots > 0
    # In millions of rupiah, so a car reads as a two- or three-digit number.
    assert 10 < ranges["median"].iloc[0] < 1000


def test_distribution_panels_carry_a_figure_and_the_whole_table(bundle):
    brands = charts.brand_panel(bundle.lots, "cars")
    assert len(brands.figure.data) == 1
    bars = brands.figure.data[0]
    assert len(bars.y) == charts.TOP_SHOWN and bars.orientation == "h"
    # One hue for every bar: the categories are names, not an ordered scale.
    assert isinstance(bars.marker.color, str)
    assert not brands.figure.layout.showlegend
    # The chart is cut to the top rows; the table keeps all of them.
    assert len(brands.table) == len(charts.brand_counts(bundle.lots, "cars"))
    assert "Brand" in brands.table.columns and "Share of lots" in brands.table.columns
    prices = charts.price_panel(bundle.lots, "motorcycles")
    assert len(prices.figure.data) == charts.TOP_PRICED
    assert prices.figure.data[0].lowerfence is not None
    assert list(prices.table.columns)[:3] == ["Model", "Lots", "Lowest"]
    # The unit is named once, on the axis and in the note, not twice.
    assert prices.figure.layout.xaxis.title.text == charts.PRICE_UNIT
    assert charts.PRICE_UNIT not in prices.title and "million" in prices.note
