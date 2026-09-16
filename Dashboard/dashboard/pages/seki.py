"""Bank Indonesia SEKI: GDP by expenditure (a price-basis switch) and deposits by owner."""

from __future__ import annotations

import streamlit as st

from .. import catalogue, charts, ui

KEY = "seki"


def render() -> None:
    dataset = catalogue.BY_KEY[KEY]
    bundle = ui.bundle()
    ui.page_header(dataset, charts.latest_observation(bundle, dataset))

    st.subheader("National accounts: GDP by expenditure")
    basis = st.radio("Price basis", ["Current prices", "Constant prices"], horizontal=True, key=f"{KEY}:basis")
    group = catalogue.group(KEY, "gdp_current" if basis == "Current prices" else "gdp_constant")
    ui.render_group(bundle, dataset, group, title=f"GDP by expenditure, {basis.lower()}")

    st.subheader("Bank deposits by owner group")
    ui.render_group(bundle, dataset, catalogue.group(KEY, "deposits"))
