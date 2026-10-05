"""Payment system transactions: Bank Indonesia's SPIP and ASPI's QRIS.

One tab per main category and one chart at a time inside it, chosen with a
measure switch at the head of the tab's filter bar; the page used to stack
twelve charts under three headings.  The SPIP tabs (e-money, cards, and
currency and BI-RTGS) come first and ASPI's QRIS, which used to be a page of
its own, is the last tab: it is a different publisher at a different cadence,
so it stays a dataset of its own in the catalogue and introduces itself with
its own caption at the head of its tab.
"""

from __future__ import annotations

import streamlit as st

from .. import catalogue, charts, ui

KEY = "spip"
#: The ASPI dataset drawn on the last tab, which is named after it.
QRIS_KEY = "qris"
QRIS_TAB = "QRIS"
TITLE = "Payment system transactions: BI SPIP and ASPI QRIS"


def render() -> None:
    dataset = catalogue.BY_KEY[KEY]
    qris = catalogue.BY_KEY[QRIS_KEY]
    bundle = ui.bundle()
    ui.page_header(dataset, charts.latest_observation(bundle, dataset), title=TITLE)

    headings = dataset.headings
    tabs = st.tabs([*headings, QRIS_TAB])
    for tab, heading in zip(tabs, headings):
        with tab:
            groups = [group for group in dataset.groups if group.heading == heading]
            # A dropdown rather than buttons: several of these measures are a
            # line long, and a row of them would not fit the bar's first cell.
            switch = ui.Switch("Measure", tuple(group.title for group in groups), dropdown=True)
            ui.render_switched(bundle, dataset, groups, switch, key=f"{KEY}:{heading}")
    with tabs[-1]:
        ui.dataset_caption(qris, charts.latest_observation(bundle, qris))
        switch = ui.Switch("Measure", tuple(group.title for group in qris.groups), dropdown=True)
        ui.render_switched(bundle, qris, list(qris.groups), switch, key=f"{KEY}:{QRIS_TAB}")
