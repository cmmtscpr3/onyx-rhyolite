"""PIHPS weekly food prices: one chart, market and commodity selectable."""

from __future__ import annotations

import streamlit as st

from .. import catalogue, charts, data, ui
from ..transform import SHOW_AS

KEY = "pihps"


def render() -> None:
    dataset = catalogue.BY_KEY[KEY]
    bundle = ui.bundle()
    pihps = bundle.pihps
    ui.page_header(dataset, charts.latest_observation(bundle, dataset))

    rows = data.pihps_commodities(pihps)
    commodities = rows["commodity"].tolist()
    indent = {row.commodity: (row.commodity if row.level == 1 else f"   ↳ {row.commodity}") for row in rows.itertuples()}

    top_left, top_right = st.columns([2, 3])
    market = top_left.radio("Market level", list(data.MARKETS), horizontal=True, key=f"{KEY}:market")
    chosen = top_right.multiselect(
        "Commodities",
        options=commodities,
        default=[c for c in charts.PIHPS_DEFAULT if c in commodities],
        format_func=lambda c: indent[c],
        key=f"{KEY}:commodities",
    )
    left, right = st.columns([3, 1])
    mode = left.radio("Show as", SHOW_AS, horizontal=True, key=f"{KEY}:mode")
    years = ui.years_available(pihps["week"].drop_duplicates())
    since = right.selectbox(
        "From", options=years, format_func=lambda y: "All history" if y is None else str(y), key=f"{KEY}:since"
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
