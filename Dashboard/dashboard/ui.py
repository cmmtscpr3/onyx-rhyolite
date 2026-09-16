"""Streamlit pieces shared by every page: data loading, headers, controls,
and the chart-plus-table block."""

from __future__ import annotations

import datetime as dt
from typing import Sequence

import pandas as pd
import streamlit as st

from . import catalogue, charts, data, definitions, export, theme, transform
from .catalogue import Dataset, Group
from .definitions import Definition

PLOTLY_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
    "toImageButtonOptions": {"format": "png", "scale": 2},
}

WIB = dt.timezone(dt.timedelta(hours=7))


@st.cache_data(show_spinner="Reading the datasets…")
def _load(digest: str) -> charts.Bundle:
    return charts.load_bundle()


def bundle() -> charts.Bundle:
    """The data, cached until any file under Dataset/ changes."""
    return _load(data.fingerprint().digest)


def palette() -> str:
    """Match Plotly's series colours to the theme Streamlit is rendering in."""
    try:
        kind = st.context.theme.type  # Streamlit >= 1.46
    except Exception:  # pragma: no cover - older Streamlit or no browser context
        kind = None
    return "dark" if kind == "dark" else "light"


# ---------------------------------------------------------------------------
# Page furniture


def page_header(dataset: Dataset, latest: pd.Timestamp | None) -> None:
    st.title(dataset.title)
    when = f"latest observation {latest:%d %b %Y}" if latest is not None else "no observations on file"
    st.caption(
        f"{dataset.publisher} · {dataset.cadence} · {when} · "
        f"[source]({dataset.source_url}) · collector `{dataset.collector}`"
    )
    if dataset.notes:
        with st.expander("About this data"):
            for note in dataset.notes:
                st.markdown(f"- {note}")
    described = definitions.for_dataset(dataset.key)
    if described:
        with st.expander("Official description"):
            for definition in described:
                st.markdown(definition_markdown((), definition))


def years_available(frame_index: pd.DatetimeIndex) -> list[int | None]:
    if len(frame_index) == 0:
        return [None]
    first, last = frame_index.min().year, frame_index.max().year
    return [None, *range(last, first - 1, -1)]


def controls(group: Group, key: str, years: list[int | None], frequency: str) -> tuple[list[str], str, int | None]:
    """One row: which series, how to show them, and from which year."""
    left, middle, right = st.columns([3, 2, 1])
    selected = left.multiselect(
        "Series",
        options=list(group.series),
        default=list(group.shown),
        format_func=group.label,
        key=f"{key}:series",
    )
    mode = middle.radio(
        "Show as",
        transform.show_as_options(frequency),
        horizontal=True,
        key=f"{key}:mode",
        help=transform.show_as_help(frequency),
    )
    since = right.selectbox(
        "From",
        options=years,
        format_func=lambda y: "All history" if y is None else str(y),
        key=f"{key}:since",
    )
    if len(selected) > 8:
        st.caption("More than eight series share the grey tone; click a legend entry to isolate one.")
    return selected, mode, since


def show_chart(chart: charts.Chart, key: str) -> None:
    st.plotly_chart(chart.figure, width="stretch", theme="streamlit", config=PLOTLY_CONFIG, key=f"{key}:chart")
    if not chart.table.empty:
        st.dataframe(display_table(chart.table, chart.unit), hide_index=True, width="stretch")
    if chart.note:
        st.caption(chart.note)


def display_table(table: pd.DataFrame, unit: str) -> pd.DataFrame:
    shown = pd.DataFrame(
        {
            "Series": table["Series"],
            "Latest": table["Latest"].map(lambda d: d.strftime("%d %b %Y") if d is not None else ""),
            f"Value ({unit})": table["Value"].map(lambda v: transform.format_number(v, unit)),
            "vs previous": table["vs previous"].map(lambda v: transform.format_change(v, unit)),
            "vs year earlier": table["vs year earlier"].map(lambda v: transform.format_change(v, unit)),
        }
    )
    return shown


def definition_markdown(labels: Sequence[str], definition: Definition) -> str:
    """One official definition: which series it covers, the term, the quote as
    published (and the publisher's English, if any), and where it comes from."""
    head = f"**{', '.join(labels)}** · " if labels else ""
    lines = [f"{head}*{definition.term}*", ""]
    lines += _quoted(definition.text)
    if definition.english:
        lines += [">", *_quoted(definition.english)]
    if definition.note:
        lines += ["", definition.note]
    source = f"Source: [{definition.source}]({definition.url})"
    if definition.english_url:
        source += f" · English text: [{definition.english_source}]({definition.english_url})"
    lines += ["", source]
    return "\n".join(lines)


def _quoted(text: str) -> list[str]:
    """Blockquote lines; two trailing spaces keep the source's own line breaks."""
    return [f"> {line}  " if line else ">" for line in text.splitlines()]


def show_definitions(dataset: Dataset, group: Group) -> None:
    """The publishers' own definitions of what the chart's series measure; series
    without one are named as such rather than given a definition of ours."""
    if not definitions.populated(dataset):
        return
    entries = definitions.for_group(dataset.key, group)
    missing = definitions.undefined(group)
    if not entries and not missing:
        return
    with st.expander("Official definitions"):
        for entry in entries:
            st.markdown(definition_markdown(entry.labels, entry.definition))
        if missing:
            qualifier = "separate " if entries else ""
            st.caption(f"No {qualifier}official definition found for: {', '.join(missing)}.")


def render_group(bundle_: charts.Bundle, dataset: Dataset, group: Group, *, title: str | None = None) -> None:
    key = f"{dataset.key}:{group.key}"
    st.markdown(f"#### {title or group.title}")
    frame = data.wide(bundle_.series, group.series)
    frequency = data.frequency_of(bundle_.series, group.series)
    selected, mode, since = controls(group, key, years_available(frame.index), frequency)
    if not selected:
        st.info("Pick at least one series.")
        return
    chart = charts.group_chart(
        bundle_.series,
        group,
        selected=selected,
        mode=mode,
        since_year=since,
        annotations=dataset.annotations,
        palette=palette(),
    )
    show_chart(chart, key)
    show_definitions(dataset, group)


def render_headings(bundle_: charts.Bundle, dataset: Dataset, headings: list[str] | None = None) -> None:
    """Every group of a dataset, under its sub-heading."""
    for heading in headings or dataset.headings:
        if heading:
            st.subheader(heading)
        for group in dataset.groups:
            if group.heading == heading:
                render_group(bundle_, dataset, group)


def render_dataset(key: str) -> None:
    """The plain page: header, then every group under its heading."""
    dataset = catalogue.BY_KEY[key]
    bundle_ = bundle()
    page_header(dataset, charts.latest_observation(bundle_, dataset))
    render_headings(bundle_, dataset)


# ---------------------------------------------------------------------------
# Sidebar


def sidebar() -> None:
    fp = data.fingerprint()
    with st.sidebar:
        st.caption(
            f"Data files last changed {fp.newest.astimezone(WIB):%d %b %Y %H:%M} WIB "
            f"({fp.files} files, fingerprint `{fp.digest}`)."
        )
        st.caption("Datasets are refreshed by the collectors' scheduled runs; this app re-reads them on every deploy.")
        if st.button("Prepare offline HTML", key="prepare_offline", help="Build a single self-contained file of every chart at its default selection."):
            st.session_state["offline_ready"] = True
        if st.session_state.get("offline_ready"):
            html = _offline_html(fp.digest)
            st.download_button(
                "Download offline HTML",
                data=html,
                file_name=f"indonesia-indicators-{fp.newest.astimezone(WIB):%Y%m%d}.html",
                mime="text/html",
                key="download_offline",
            )
            st.caption(f"{len(html) / 1e6:.1f} MB; opens without a network connection.")


@st.cache_data(show_spinner="Building the offline page…")
def _offline_html(digest: str) -> bytes:
    return export.build_offline_html(_load(digest))
