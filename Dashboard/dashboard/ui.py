"""Streamlit pieces shared by every page: data loading, headers, the filter
bar, and the chart-plus-table block."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
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


@dataclass(frozen=True)
class Switch:
    """The picker that chooses which of a page's charts the filter bar scopes.

    It shares the bar with that chart's own controls rather than sitting above
    it, so a page never stacks one row of inputs on another.
    """

    label: str
    options: tuple[str, ...]
    help: str = ""
    #: Buttons do not fit a long list, so those pages ask for a dropdown.
    dropdown: bool = False


def choice(container, label: str, options: Sequence[str], key: str, **kwargs) -> str:
    """A one-of-N picker, as one row of buttons rather than a column of dots.

    Clicking the chosen option clears a segmented control, which would leave
    the page with nothing selected, so an empty answer falls back to the first.
    """
    picked = container.segmented_control(label, list(options), default=options[0], key=key, **kwargs)
    return picked if picked else options[0]


def since_control(container, label: str, years: list[int | None], key: str):
    return container.selectbox(
        label,
        options=years,
        format_func=lambda y: "All history" if y is None else str(y),
        key=key,
    )


def pick(container, switch: Switch, key: str) -> str:
    """The switch itself: a row of buttons, or a dropdown when it asks for one."""
    if switch.dropdown:
        return container.selectbox(switch.label, switch.options, key=key, help=switch.help)
    return choice(container, switch.label, switch.options, key, help=switch.help)


def controls(
    bundle_: charts.Bundle,
    groups: Sequence[Group],
    key: str,
    switch: Switch | None = None,
) -> tuple[Group, list[str], str, int | None]:
    """The filter bar: one bordered block holding everything a reader can change.

    The pickers run along the top -- which chart, when the page offers a
    switch, then how to show it and from which year -- and the series list,
    which is the one control that needs the width, sits under them once the
    switch has taken a cell of its own.
    """
    with st.container(border=True):
        group = groups[0]
        if switch is not None:
            # The switch decides which series the rest of the bar offers, so it
            # is read first and the long list it picks gets a row of its own.
            picker, shown, first = st.columns([3, 4, 2], vertical_alignment="bottom")
            group = groups[switch.options.index(pick(picker, switch, f"{key}:switch"))]
            series_cell = st
        else:
            series_cell, shown, first = st.columns([4, 4, 2], vertical_alignment="bottom")
        scoped = f"{key}:{group.key}"
        frequency = data.frequency_of(bundle_.series, group.series)
        selected = series_cell.multiselect(
            "Series",
            options=list(group.series),
            default=list(group.shown),
            format_func=group.label,
            key=f"{scoped}:series",
        )
        mode = choice(
            shown,
            "Show as",
            transform.show_as_options(frequency),
            f"{scoped}:mode",
            help=transform.show_as_help(frequency),
        )
        since = since_control(
            first, "From", years_available(data.wide(bundle_.series, group.series).index), f"{scoped}:since"
        )
    if len(selected) > 8:
        st.caption("More than eight series share the grey tone; click a legend entry to isolate one.")
    return group, selected, mode, since


def show_chart(chart: charts.Chart, key: str) -> None:
    st.plotly_chart(chart.figure, width="stretch", theme="streamlit", config=PLOTLY_CONFIG, key=f"{key}:chart")
    if not chart.table.empty:
        st.dataframe(display_table(chart.table, chart.unit), hide_index=True, width="stretch")
    if chart.note:
        st.caption(chart.note)


def show_panel(panel: charts.Panel, key: str) -> None:
    """A distribution figure with its own already-formatted table underneath."""
    st.markdown(f"#### {panel.title}")
    st.plotly_chart(panel.figure, width="stretch", theme="streamlit", config=PLOTLY_CONFIG, key=f"{key}:chart")
    if not panel.table.empty:
        st.dataframe(panel.table, hide_index=True, width="stretch")
    if panel.note:
        st.caption(panel.note)


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
    """One chart, with the filter bar that scopes it."""
    _render(bundle_, dataset, [group], dataset.key, None, title)


def render_switched(
    bundle_: charts.Bundle,
    dataset: Dataset,
    groups: Sequence[Group],
    switch: Switch,
    *,
    key: str = "",
    title: str | None = "",
) -> None:
    """Several charts behind one switch, which shares their filter bar.

    The switch is the heading by default: it sits at the head of the bar and
    names the chart under it, so repeating that name above the bar says the
    same thing twice.
    """
    _render(bundle_, dataset, list(groups), key or dataset.key, switch, title)


def _render(
    bundle_: charts.Bundle,
    dataset: Dataset,
    groups: Sequence[Group],
    key: str,
    switch: Switch | None,
    title: str | None,
) -> None:
    heading = groups[0].title if title is None else title
    if heading:
        st.markdown(f"#### {heading}")
    group, selected, mode, since = controls(bundle_, groups, key, switch)
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
    show_chart(chart, f"{key}:{group.key}")
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
