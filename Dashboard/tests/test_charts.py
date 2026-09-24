"""Figures and chart assembly: every default chart builds, one axis each,
colours fixed per series."""

from __future__ import annotations

import pytest

from dashboard import catalogue, charts, data, figures, theme, transform
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
    brands = charts.counts(charts.lots_subset(bundle.lots, "cars"), by["brand"])
    assert list(brands["label"][:2]) == ["TOYOTA", "DAIHATSU"]
    assert brands["lots"].is_monotonic_decreasing
    assert brands["lots"].sum() == len(charts.lots_subset(bundle.lots, "cars"))
    assert brands["share"].sum() == pytest.approx(100.0)
    models = charts.counts(charts.lots_subset(bundle.lots, "cars"), by["model"])
    assert models["label"].iloc[0] == "TOYOTA AVANZA"
    assert charts.counts(charts.lots_subset(bundle.lots, "motorcycles"), by["model"])["label"].iloc[0] == "HONDA BEAT"
    # Grades keep ibid's own order, best first and ungraded last, however many sold.
    grades = charts.counts(charts.lots_subset(bundle.lots, "cars"), by["grade"])
    assert list(grades["label"]) == ["A", "B", "C", "D", "E", charts.UNGRADED]
    years = charts.counts(charts.lots_subset(bundle.lots, "cars"), by["year"])
    assert years["label"].is_monotonic_increasing
    # Unsold lots are in scope only when asked for.
    assert charts.counts(charts.lots_subset(bundle.lots, "cars", sold_only=False), by["brand"])["lots"].sum() > brands["lots"].sum()


def test_price_ranges_are_quartiles_and_true_extremes(bundle):
    by = charts.BY_BREAKDOWN
    cars = charts.lots_subset(bundle.lots, "cars")
    models = charts.price_ranges(cars, by["model"])
    assert len(models) == charts.TOP_SHOWN
    # Names run most lots first, the order the chart of lots above uses, so the
    # two read down the side together rather than each in an order of its own.
    assert models["lots"].is_monotonic_decreasing
    assert list(models["label"]) == list(charts.counts(cars, by["model"])["label"].head(charts.TOP_SHOWN))
    for row in models.itertuples(index=False):
        assert row.minimum <= row.p5 <= row.p25 <= row.median <= row.p75 <= row.p95 <= row.maximum
        assert row.lots >= charts.MIN_PRICED_LOTS
    assert 10 < models["median"].iloc[0] < 1000  # millions of rupiah, so a car is a two- or three-digit number
    # An ordered scale keeps its sequence and is not cut to the top rows.
    grades = charts.price_ranges(charts.lots_subset(bundle.lots, "cars"), by["grade"])
    assert list(grades["label"]) == ["A", "B", "C", "D", "E", charts.UNGRADED]
    assert grades.loc[grades["label"] == "A", "median"].iloc[0] > grades.loc[grades["label"] == "E", "median"].iloc[0]
    years = charts.price_ranges(charts.lots_subset(bundle.lots, "cars"), by["year"])
    assert years["label"].is_monotonic_increasing and len(years) > charts.TOP_SHOWN
    assert (years["lots"] >= charts.MIN_PRICED_LOTS).all()  # a year of one lot has no range worth drawing


def test_panels_carry_a_figure_and_the_whole_table(bundle):
    by = charts.BY_BREAKDOWN
    brands = charts.count_panel(charts.lots_subset(bundle.lots, "cars"), by["brand"])
    bars = brands.figure.data[0]
    assert len(bars.y) == charts.TOP_SHOWN and bars.orientation == "h"
    assert isinstance(bars.marker.color, str)  # one hue: the bar length already carries the count
    assert not brands.figure.layout.showlegend
    # The chart is cut to the top rows; the table keeps all of them.
    assert len(brands.table) == len(charts.counts(charts.lots_subset(bundle.lots, "cars"), by["brand"]))
    assert "Brand" in brands.table.columns and "Share of lots" in brands.table.columns
    # An ordered scale runs along the bottom instead, so its sequence reads left to right.
    years = charts.count_panel(charts.lots_subset(bundle.lots, "cars"), by["year"])
    assert years.figure.data[0].orientation != "h"
    assert years.figure.layout.xaxis.type == "category"
    ranges = charts.price_ranges(charts.lots_subset(bundle.lots, "motorcycles"), by["grade"])
    prices = charts.price_panel(charts.lots_subset(bundle.lots, "motorcycles"), by["grade"])
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
    assert prices.note == ""


def test_the_export_carries_the_ibid_panels(bundle):
    built = dict((dataset.key, items) for dataset, items in charts.default_charts(bundle))
    panels = built["ibid"]
    assert [panel.title for panel in panels] == [
        "Lots in auction and lots sold each week, Cars",
        "Lots by brand, Cars",
        "Listed price by brand, Cars",
        "Lots in auction and lots sold each week, Motorcycles",
        "Lots by brand, Motorcycles",
        "Listed price by brand, Motorcycles",
    ]
    assert all(isinstance(panel, charts.Panel) for panel in panels)


def test_the_second_layer_narrows_to_one_brand_or_model(bundle):
    by = charts.BY_BREAKDOWN
    cars = charts.lots_subset(bundle.lots, "cars")
    toyota = charts.narrowed(bundle.lots, "cars", by["brand"], "TOYOTA")
    assert 0 < len(toyota) < len(cars)
    assert set(toyota["brand"]) == {"TOYOTA"}
    avanza = charts.narrowed(bundle.lots, "cars", by["model"], "TOYOTA AVANZA")
    assert set(charts.family(avanza)) == {"TOYOTA AVANZA"}
    assert len(avanza) < len(toyota)
    # No name given means the whole category, which is what the top layer shows.
    assert len(charts.narrowed(bundle.lots, "cars", by["brand"])) == len(cars)
    # Within one model, the layer below is grade or year rather than the name again.
    years = charts.counts(avanza, by["year"])
    assert years["label"].is_monotonic_increasing and len(years) > 1
    assert years["lots"].sum() == len(avanza)


def test_only_brands_and_models_worth_opening_are_offered(bundle):
    by = charts.BY_BREAKDOWN
    cars = charts.lots_subset(bundle.lots, "cars")
    brands = charts.drillable(cars, by["brand"])
    assert brands[0] == "TOYOTA"  # most lots first
    tally = charts.counts(cars, by["brand"]).set_index("label")["lots"]
    assert all(tally[name] >= charts.MIN_PRICED_LOTS for name in brands)
    assert set(brands) < set(tally.index)  # the long tail is left out
    assert "TOYOTA AVANZA" in charts.drillable(cars, by["model"])


def test_a_scoped_panel_names_what_it_narrowed_to(bundle):
    by = charts.BY_BREAKDOWN
    avanza = charts.narrowed(bundle.lots, "cars", by["model"], "TOYOTA AVANZA")
    panel = charts.price_panel(avanza, by["grade"], scope="TOYOTA AVANZA")
    assert panel.title == "Listed price by grade, TOYOTA AVANZA"
    assert "avanza" in panel.key and panel.unit == charts.PRICE_UNIT
    assert charts.count_panel(avanza, by["year"], scope="TOYOTA AVANZA").title == "Lots by model year, TOYOTA AVANZA"
    # Unscoped, the same builder keeps the plain title.
    assert charts.count_panel(charts.lots_subset(bundle.lots, "cars"), by["brand"]).title == "Lots by brand"


def test_a_cut_that_narrows_everything_away_says_so(bundle):
    by = charts.BY_BREAKDOWN
    empty = charts.narrowed(bundle.lots, "cars", by["brand"], "NO SUCH BRAND")
    assert empty.empty
    panel = charts.price_panel(empty, by["grade"], scope="NO SUCH BRAND")
    assert panel.table.empty
    assert [note.text for note in panel.figure.layout.annotations] == ["No grades here with 8 lots or more"]
    counted = charts.count_panel(empty, by["grade"], scope="NO SUCH BRAND")
    assert [note.text for note in counted.figure.layout.annotations] == ["No lots to count"]


def test_the_weekly_panel_pairs_lots_in_auction_with_lots_sold(bundle):
    panel = charts.weekly_panel(bundle.lots, "cars")
    assert panel.title == "Lots in auction and lots sold each week" and panel.unit == "lots"
    weekly = transform.weekly_lots(charts.lots_subset(bundle.lots, "cars", sold_only=False))
    traces = {trace.name: trace for trace in panel.figure.data}
    assert set(traces) == set(charts.WEEKLY_LABELS)
    listed, sold = traces["Lots in auction"], traces["Lots sold"]
    assert list(listed.y) == [int(n) for n in weekly["lots"]]
    assert list(sold.y) == [int(n) for n in weekly["held"]]
    # One axis, both counts in lots, and the gap between them washed in.
    assert "yaxis2" not in panel.figure.layout
    assert listed.fill == "tonexty" and sold.fill is None
    # Sold is drawn first and lots in auction dashed over it, so the weeks where
    # the two meet still show both lines; the legend still reads the other way.
    assert [trace.name for trace in panel.figure.data] == ["Lots sold", "Lots in auction"]
    assert listed.line.dash == "dash" and sold.line.dash == "solid"
    assert panel.figure.layout.legend.traceorder == "reversed"
    assert panel.figure.layout.showlegend
    # A week a scrape saw only in part is drawn hollow, and the note names those weeks.
    hollow = theme.CHROME["light"]["surface"]
    assert [colour == hollow for colour in listed.marker.color] == list(~weekly["complete"].astype(bool))
    for week in weekly.index[~weekly["complete"].astype(bool)]:
        assert week.strftime("%d %b") in panel.note
    # Terjual is the auction having been held, not a buyer having been found,
    # and the note says so rather than letting the label speak for itself.
    assert "Terjual" in panel.note and "found a buyer" in panel.note


def test_the_weekly_table_carries_the_share_sold(bundle):
    panel = charts.weekly_panel(bundle.lots, "motorcycles")
    weekly = transform.weekly_lots(charts.lots_subset(bundle.lots, "motorcycles", sold_only=False))
    assert list(panel.table.columns) == [
        "Auction week",
        "Lots in auction",
        "Lots sold",
        "Share sold",
        "Week seen whole",
    ]
    assert len(panel.table) == len(weekly)
    # The share is the one number the two lines do not give a reader directly.
    assert list(panel.table["Share sold"]) == [
        f"{sold / listed * 100:.0f}%" for listed, sold in zip(weekly["lots"], weekly["held"])
    ]
    # Most settled weeks sold every lot, and the ones that did not are the lots
    # that left the site before a scrape could see them sold.
    settled = panel.table[panel.table["Week seen whole"] == "Yes"]
    assert (settled["Share sold"] == "100%").sum() > len(settled) / 2
    assert (panel.table["Week seen whole"] == "In part").any()


def test_the_weekly_panel_survives_a_category_with_no_lots(bundle):
    empty = bundle.lots.head(0)
    panel = charts.weekly_panel(empty, "cars")
    assert [note.text for note in panel.figure.layout.annotations] == ["No auction weeks on file"]
    assert panel.table.empty and not panel.figure.layout.showlegend
