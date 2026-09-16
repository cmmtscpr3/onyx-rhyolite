"""Figures and chart assembly: every default chart builds, one axis each,
colours fixed per series."""

from __future__ import annotations

import pytest

from dashboard import catalogue, charts, data, figures, theme
from dashboard.transform import SHOW_AS


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


def test_show_as_modes_change_axis_and_values(bundle):
    group = catalogue.group("consumer_survey", "confidence")
    yoy = charts.group_chart(bundle.series, group, mode=SHOW_AS[1], since_year=2024)
    index = charts.group_chart(bundle.series, group, mode=SHOW_AS[2], since_year=2024)
    assert "year earlier" in yoy.figure.layout.yaxis.title.text
    assert "index" in index.figure.layout.yaxis.title.text
    first = [y for y in index.figure.data[0].y if y == y][0]
    assert first == pytest.approx(100.0)
    # The table stays on levels whatever the chart shows.
    assert yoy.table.loc[yoy.table["Series"].str.startswith("Consumer Confidence"), "Value"].iloc[0] == pytest.approx(118.5)


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
    assert figures.precision(big, "IDR billion", SHOW_AS[1]) == 1
