"""Bank Indonesia SPIP: e-money, cards, and currency and BI-RTGS indicators.

One tab per main category and one chart at a time inside it, chosen with a
measure switch at the head of the tab's filter bar; the page used to stack
twelve charts under three headings.
"""

from __future__ import annotations

import streamlit as st

from .. import catalogue, charts, ui

KEY = "spip"


def render() -> None:
    dataset = catalogue.BY_KEY[KEY]
    bundle = ui.bundle()
    ui.page_header(dataset, charts.latest_observation(bundle, dataset))

    headings = dataset.headings
    for tab, heading in zip(st.tabs(headings), headings):
        with tab:
            groups = [group for group in dataset.groups if group.heading == heading]
            # A dropdown rather than buttons: several of these measures are a
            # line long, and a row of them would not fit the bar's first cell.
            switch = ui.Switch("Measure", tuple(group.title for group in groups), dropdown=True)
            ui.render_switched(bundle, dataset, groups, switch, key=f"{KEY}:{heading}")
