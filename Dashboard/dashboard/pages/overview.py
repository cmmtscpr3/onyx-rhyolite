"""Landing page: how up to date each dataset is, and where to go."""

from __future__ import annotations

import streamlit as st

from .. import catalogue, charts, theme, ui

STATUS_TEXT = {
    "fresh": "Updated",
    "late": "Late",
    "stale": "Outdated",
    "manual": "Manual",
    "no data": "No data",
}
STATUS_ICON = {"fresh": "🟢", "late": "🟡", "stale": "🔴", "manual": "⚪", "no data": "⚪"}
#: The datasets the table lists, in the sidebar's order, with the tag their
#: sidebar page carries.  A dataset whose page is not in the sidebar (OJK
#: DPK, Magpie IQ e-commerce) is left out.  QRIS is the last tab of the
#: payment page, so it follows SPIP.
ROWS = (
    ("bps_inflation", "Official"),
    ("pihps", "Exploratory"),
    ("consumer_survey", "Official"),
    ("seki", "Official"),
    ("spip", "Exploratory"),
    ("qris", "Exploratory"),
    ("ibid", "Exploratory"),
)


def render() -> None:
    bundle = ui.bundle()
    st.title("Indonesia Indicators")
    st.caption(
        "Line charts for every indicator the collectors maintain, bucketed by the dataset it comes from. "
        "Pick a dataset in the sidebar; each page shows its series with a table of latest values."
    )
    table = charts.freshness_table(bundle).set_index("key")
    shown = table.loc[[key for key, _ in ROWS]].drop(columns=["Collector"]).reset_index(drop=True)
    shown.insert(1, "Type", [tier for _, tier in ROWS])
    shown["Status"] = shown["Status"].map(lambda s: f"{STATUS_ICON.get(s, '⚪')} {STATUS_TEXT.get(s, s)}")
    st.subheader("Updatedness")
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
        "Updated: within the dataset's normal publication lag. Late: past it. Outdated: more than twice past it, "
        "or the source has stopped publishing. Manual: no schedule, updated by hand. "
        "Official: a publisher's own statistic. Exploratory: a proxy, or a source still being assessed."
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
