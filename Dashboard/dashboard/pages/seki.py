"""Bank Indonesia SEKI: one tab for GDP by expenditure (a price-basis switch)
and one for deposits by owner."""

from __future__ import annotations

import streamlit as st

from .. import catalogue, charts, ui

KEY = "seki"
BASES = ("gdp_current", "gdp_constant")


def render() -> None:
    dataset = catalogue.BY_KEY[KEY]
    bundle = ui.bundle()
    ui.page_header(dataset, charts.latest_observation(bundle, dataset))

    gdp_tab, deposits_tab = st.tabs(["SEKI - GDP by Expenditure", "SEKI - Bank Deposits"])

    with gdp_tab:
        groups = [catalogue.group(KEY, key) for key in BASES]
        switch = ui.Switch("Price basis", tuple(group.title for group in groups))
        ui.render_switched(bundle, dataset, groups, switch, key=f"{KEY}:gdp")

    with deposits_tab:
        ui.render_group(bundle, dataset, catalogue.group(KEY, "deposits"), title="")
