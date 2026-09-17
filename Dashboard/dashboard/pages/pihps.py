"""PIHPS weekly food prices: one chart, market and commodity selectable."""

from __future__ import annotations

import streamlit as st

from .. import catalogue, charts, data, transform, ui

KEY = "pihps"
#: PIHPS publishes one column per week, so changes are week on week.
FREQUENCY = "weekly"


def render() -> None:
    dataset = catalogue.BY_KEY[KEY]
    bundle = ui.bundle()
    pihps = bundle.pihps
    ui.page_header(dataset, charts.latest_observation(bundle, dataset))

    rows = data.pihps_commodities(pihps)
    commodities = rows["commodity"].tolist()
    indent = {row.commodity: (row.commodity if row.level == 1 else f"   ↳ {row.commodity}") for row in rows.itertuples()}

    # One bordered bar, as on every other page: what to show along the top,
    # and the long commodity list on its own row underneath rather than
    # squeezed in beside the rest.
    with st.container(border=True):
        left, middle, right = st.columns([3, 3, 2], vertical_alignment="bottom")
        # "Market" is already in the control's own label, and repeating it in
        # every option pushed the last one off the end of the cell.
        market = ui.choice(
            left,
            "Market level",
            list(data.MARKETS),
            f"{KEY}:market",
            format_func=lambda name: name.replace(" Market", ""),
        )
        mode = ui.choice(
            middle,
            "Show as",
            transform.show_as_options(FREQUENCY),
            f"{KEY}:mode",
            help=transform.show_as_help(FREQUENCY),
        )
        since = ui.since_control(right, "From", ui.years_available(pihps["week"].drop_duplicates()), f"{KEY}:since")
        chosen = st.multiselect(
            "Commodities",
            options=commodities,
            default=[c for c in charts.PIHPS_DEFAULT if c in commodities],
            format_func=lambda c: indent[c],
            key=f"{KEY}:commodities",
        )
    if not chosen:
        st.info("Pick at least one commodity.")
        return
    if len(chosen) > 8:
        st.caption("Varieties share their group's colour and differ by dash; click a legend entry to isolate one.")
    chart = charts.pihps_chart(
        pihps, market=market, commodities=chosen, mode=mode, since_year=since, palette=ui.palette()
    )
    ui.show_chart(chart, f"{KEY}:{market}")
