"""OJK third-party funds: stale at source, and says so."""

from __future__ import annotations

import streamlit as st

from .. import catalogue, charts, ui

KEY = "ojk"


def render() -> None:
    dataset = catalogue.BY_KEY[KEY]
    bundle = ui.bundle()
    ui.page_header(dataset, charts.latest_observation(bundle, dataset))
    st.warning(
        "Stale at source: from the July 2025 data period OJK publishes SPI only through its Portal Data, "
        "and the PDF and Excel releases the collector reads end with June 2025. "
        "The SEKI page carries a current monthly reading of deposits by owner group.",
        icon="⚠️",
    )
    ui.render_headings(bundle, dataset)
