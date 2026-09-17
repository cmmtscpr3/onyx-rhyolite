"""Bank Indonesia Survei Konsumen: confidence indices, budget shares, discontinued series."""

from __future__ import annotations

import streamlit as st

from .. import catalogue, charts, ui

KEY = "consumer_survey"
SHARES = {
    "Consumption": "share_consumption",
    "Loan instalments": "share_loan_instalment",
    "Saving": "share_saving",
}


def render() -> None:
    dataset = catalogue.BY_KEY[KEY]
    bundle = ui.bundle()
    ui.page_header(dataset, charts.latest_observation(bundle, dataset))

    st.subheader("Confidence indices")
    ui.render_group(bundle, dataset, catalogue.group(KEY, "confidence"), title="")

    st.subheader("Household budget shares by monthly expenditure group")
    switch = ui.Switch(
        "Share of income going to",
        tuple(SHARES),
        help=(
            "Respondents are grouped by their monthly household expenditure "
            '(BI\'s "Pengeluaran per bulan" brackets), not by income.'
        ),
    )
    ui.render_switched(
        bundle, dataset, [catalogue.group(KEY, key) for key in SHARES.values()], switch, key=f"{KEY}:share"
    )

    with st.expander("Discontinued series (last published 2019–2020)"):
        for group in dataset.groups:
            if group.heading == "Discontinued series":
                ui.render_group(bundle, dataset, group)
