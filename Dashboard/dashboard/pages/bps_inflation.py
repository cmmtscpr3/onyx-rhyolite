"""BPS inflation: headline rates, the province table and BI's components.

Three tabs, each with its own bordered filter bar: headline inflation with
the year-on-year and month-on-month rates together or one at a time; the
provinces' year-on-year rates month by month, red where a province runs
above Indonesia and green where it runs below; and Bank Indonesia's
disaggregation month-on-month.  The Show-as switch the other pages carry is
left out, since a percentage change of a rate says nothing.
"""

from __future__ import annotations

import streamlit as st

from .. import catalogue, charts, data, ui

KEY = charts.INFLATION_KEY
#: Rows of the province table are 35px tall in Streamlit's grid; the table
#: shows every region rather than hiding most behind an inner scrollbar.
ROW_PX = 35
HEADER_PX = 38
TABS = ("Overall", "Provinces", "Components")


def render() -> None:
    dataset = catalogue.BY_KEY[KEY]
    bundle = ui.bundle()
    inflation = bundle.inflation
    ui.page_header(dataset, charts.latest_observation(bundle, dataset))

    headline, provinces, components = st.tabs(list(TABS))
    with headline:
        _headline(inflation)
    with provinces:
        _provinces(inflation)
    with components:
        _components(inflation)


def _headline(inflation: data.Inflation) -> None:
    st.subheader("Inflation")
    with st.container(border=True):
        left, right = st.columns([6, 2], vertical_alignment="bottom")
        measures = left.multiselect(
            "Measure",
            options=list(data.INFLATION_MEASURES),
            default=list(data.INFLATION_MEASURES),
            format_func=lambda m: charts.INFLATION_LABELS[m],
            key=f"{KEY}:headline:measures",
            help="Either rate on its own, or both together on the one axis.",
        )
        since = ui.since_control(right, "From", ui.years_available(inflation.national.index), f"{KEY}:headline:since")
    if not measures:
        st.info("Pick at least one measure.")
        return
    chart = charts.inflation_chart(inflation, measures=measures, since_year=since, palette=ui.palette())
    ui.show_chart(chart, f"{KEY}:headline")


def _provinces(inflation: data.Inflation) -> None:
    st.subheader("Year-on-year inflation by province")
    with st.container(border=True):
        (left,) = st.columns([2])
        since = ui.since_control(left, "From", ui.years_available(inflation.provinces.index), f"{KEY}:provinces:since")
    table = charts.province_table(inflation, since_year=since)
    if table.empty or table.shape[1] < 2:
        st.info("No province figures in this range.")
        return
    verdict = charts.province_vs_national(table)
    months = [column for column in table.columns if column != charts.REGION]
    css = {v: f"background-color: {colour}; color: white" for v, colour in charts.VERDICT_COLOUR.items()}
    styles = verdict.map(lambda v: css.get(v, ""))
    styled = (
        table.style.apply(lambda _: styles, axis=None)
        .format(f"{{:.{charts.INFLATION_DECIMALS}f}}", subset=months, na_rep="–")
    )
    st.dataframe(
        styled,
        hide_index=True,
        width="stretch",
        height=HEADER_PX + ROW_PX * len(table),
        column_config={charts.REGION: st.column_config.TextColumn(charts.REGION, pinned=True)},
        key=f"{KEY}:provinces:table",
    )
    st.caption(
        "Red: Province's rate is above Indonesia's for that month. Green: Province rate is above National Level"
    )


def _components(inflation: data.Inflation) -> None:
    st.subheader("Inflation by component, month-on-month")
    with st.container(border=True):
        left, right = st.columns([6, 2], vertical_alignment="bottom")
        selected = left.multiselect(
            "Series",
            options=list(data.INFLATION_COMPONENTS),
            default=list(data.INFLATION_COMPONENTS),
            format_func=lambda c: charts.COMPONENT_LABELS[c],
            key=f"{KEY}:components:series",
        )
        since = ui.since_control(right, "From", ui.years_available(inflation.components.index), f"{KEY}:components:since")
    if not selected:
        st.info("Pick at least one series.")
        return
    chart = charts.inflation_components_chart(inflation, selected=selected, since_year=since, palette=ui.palette())
    ui.show_chart(chart, f"{KEY}:components")
