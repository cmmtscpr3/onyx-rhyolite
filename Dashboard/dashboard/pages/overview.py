"""Landing page: how fresh each dataset is, and where to go."""

from __future__ import annotations

import streamlit as st

from .. import catalogue, charts, theme, ui

STATUS_TEXT = {
    "fresh": "Fresh",
    "late": "Late",
    "stale": "Stale",
    "manual": "Manual",
    "no data": "No data",
}
STATUS_ICON = {"fresh": "🟢", "late": "🟡", "stale": "🔴", "manual": "⚪", "no data": "⚪"}


def render() -> None:
    bundle = ui.bundle()
    st.title("Indonesia Indicators")
    st.caption(
        "Line charts for every indicator the collectors maintain, bucketed by the dataset it comes from. "
        "Pick a dataset in the sidebar; each page shows its series with a table of latest values."
    )
    table = charts.freshness_table(bundle)
    shown = table.drop(columns=["key", "Collector"]).copy()
    shown["Status"] = shown["Status"].map(lambda s: f"{STATUS_ICON.get(s, '⚪')} {STATUS_TEXT.get(s, s)}")
    st.subheader("Freshness")
    st.dataframe(
        shown,
        hide_index=True,
        width="stretch",
        column_config={
            "Latest observation": st.column_config.DateColumn(format="DD MMM YYYY"),
            "Age (days)": st.column_config.NumberColumn(format="%d"),
        },
    )
    st.caption(
        "Fresh: within the dataset's normal publication lag. Late: past it. Stale: more than twice past it, "
        "or the source has stopped publishing. Manual: no schedule, updated by hand."
    )
    st.subheader("Datasets")
    for section in catalogue.SECTIONS[1:]:
        datasets = catalogue.datasets_in(section)
        if not datasets:
            continue
        st.markdown(f"**{section}**")
        for dataset in datasets:
            groups = len(dataset.groups) if dataset.groups else (3 if dataset.key == "pihps" else 4)
            st.markdown(f"- {dataset.title}: {dataset.publisher}. {groups} chart{'s' if groups != 1 else ''}.")
