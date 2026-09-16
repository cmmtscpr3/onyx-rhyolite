"""Bank Indonesia SPIP: e-money, cards, and currency and BI-RTGS indicators.

One tab per main category and one chart at a time inside it, chosen with a
measure switch; the page used to stack twelve charts under three headings.
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
            titles = [group.title for group in groups]
            chosen = st.radio("Measure", titles, horizontal=True, key=f"{KEY}:{heading}:measure")
            group = groups[titles.index(chosen)]
            ui.render_group(bundle, dataset, group, title=f"{heading}: {group.title.lower()}")
