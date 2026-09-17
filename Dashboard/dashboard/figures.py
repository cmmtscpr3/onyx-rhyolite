"""Plotly figures.  One kind: the line chart, built the same way everywhere.

The frame comes in wide (dates down, series across, already transformed by
``transform.show_as``), and goes out as a figure with unified hover, a range
selector and a range slider, one y-axis, a legend whenever there are two or
more series, and colours fixed per series id.
"""

from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import theme
from .catalogue import Annotation
from .transform import AXIS_TITLES, LEVEL, POINT_UNITS

RANGE_BUTTONS = (
    dict(count=1, label="1y", step="year", stepmode="backward"),
    dict(count=3, label="3y", step="year", stepmode="backward"),
    dict(count=5, label="5y", step="year", stepmode="backward"),
    dict(step="all", label="All"),
)


def precision(frame: pd.DataFrame, unit: str, mode: str = LEVEL) -> int:
    """Decimals for hover and axis: what the magnitude of the values calls for."""
    if mode != LEVEL or unit in POINT_UNITS:
        return 1
    raw = frame.to_numpy(dtype=float).ravel() if not frame.empty else np.array([], dtype=float)
    finite = np.abs(raw[np.isfinite(raw)])
    if finite.size == 0:
        return 1
    median = float(np.median(finite))
    if median >= 1000:
        return 0
    if median >= 10:
        return 1
    return 2


LEGEND_ROW_PX = 19
LEGEND_PAD_PX = 10
BUTTONS_PX = 30
GAP_PX = 2


def legend_height(labels: Sequence[str]) -> int:
    """Height of the vertical legend: one row per series, none for a single series.

    Measured in Chromium: Plotly draws legend rows 19 px apart with 10 px of
    padding.  A vertical legend has exactly one row per series at every
    width, which is what makes the top margin below exact on a phone and on
    a desktop alike; a horizontal legend re-wraps with the width, so the
    space it needs cannot be known in advance.
    """
    if len(labels) < 2:
        return 0
    return LEGEND_PAD_PX + LEGEND_ROW_PX * len(labels)


def top_margin(labels: Sequence[str]) -> int:
    """Room for the legend, the range buttons under it, and breathing space."""
    legend = legend_height(labels)
    return 6 + legend + (GAP_PX if legend else 0) + BUTTONS_PX + 2


def axis_title(unit: str, mode: str) -> str:
    """The unit on levels; what the change compares against otherwise."""
    return unit if mode == LEVEL else AXIS_TITLES.get(mode, "% change")


def line_chart(
    frame: pd.DataFrame,
    *,
    labels: Mapping[str, str],
    unit: str,
    colours: Mapping[str, str],
    dashes: Mapping[str, str] | None = None,
    mode: str = LEVEL,
    markers: bool = False,
    title: str | None = None,
    annotations: Sequence[Annotation] = (),
    palette: str = "light",
    height: int = 440,
    range_slider: bool = True,
) -> go.Figure:
    chrome = theme.CHROME[palette]
    fig = go.Figure()
    decimals = precision(frame, unit, mode)
    hover = f"%{{fullData.name}}: %{{y:,.{decimals}f}}<extra></extra>"
    for column in frame.columns:
        colour = colours.get(column, chrome["muted"])
        dash = (dashes or {}).get(column, "solid")
        fig.add_trace(
            go.Scatter(
                x=frame.index,
                y=frame[column],
                name=labels.get(column, column),
                mode="lines+markers" if markers else "lines",
                line=dict(width=2, color=colour, dash=dash, shape="linear"),
                marker=dict(size=7, color=colour, line=dict(width=2, color=chrome["surface"])),
                connectgaps=False,
                hovertemplate=hover,
            )
        )
    if frame.empty or all(frame[c].isna().all() for c in frame.columns):
        fig.add_annotation(
            text="No observations in this range",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(color=chrome["muted"], size=13),
        )
    for note in annotations:
        fig.add_vline(x=note.date, line_width=1, line_dash="dot", line_color=chrome["muted"])
        fig.add_annotation(
            x=note.date,
            y=1.0,
            yref="paper",
            text=note.text,
            showarrow=False,
            xanchor="left",
            yanchor="top",
            xshift=4,
            font=dict(size=11, color=chrome["secondary"]),
        )
    names = [labels.get(column, column) for column in frame.columns]
    fig.update_layout(
        template=theme.template(palette),
        title=dict(text=title, yref="container", y=1, yanchor="top", pad=dict(t=8)) if title else None,
        height=height + (24 if title else 0),
        hovermode="x unified",
        showlegend=len(frame.columns) >= 2,
        # Pinned to the top edge of the figure, in the margin reserved for it,
        # so the range buttons (which sit just above the plot) stay clear of it.
        # A vertical list pinned to the top edge of the figure, in the margin
        # reserved for it; the range buttons sit just above the plot, below it.
        legend=dict(
            orientation="v",
            yref="container",
            yanchor="top",
            y=1 if not title else 0.94,
            xanchor="left",
            x=0,
            tracegroupgap=0,
        ),
        margin=dict(l=8, r=8, t=top_margin(names) + (24 if title else 0), b=8),
        xaxis=dict(
            rangeselector=dict(
                buttons=list(RANGE_BUTTONS),
                bgcolor="rgba(0,0,0,0)",
                activecolor=chrome["grid"],
                bordercolor=chrome["axis"],
                borderwidth=1,
                font=dict(size=11, color=chrome["secondary"]),
            ),
            rangeslider=dict(visible=range_slider, thickness=0.06, bordercolor=chrome["grid"], borderwidth=1),
            type="date",
            hoverformat="%d %b %Y",
        ),
        yaxis=dict(
            title=dict(text=axis_title(unit, mode)),
            tickformat=f",.{decimals}f",
            separatethousands=True,
            rangemode="tozero" if mode == LEVEL and _all_positive(frame) else "normal",
        ),
    )
    return fig


def _all_positive(frame: pd.DataFrame) -> bool:
    if frame.empty:
        return True
    values = frame.to_numpy(dtype=float)
    finite = values[np.isfinite(values)]
    return bool(finite.size == 0 or finite.min() >= 0)


def two_panel_note(unit: str) -> str:
    return f"One axis per chart; series in {unit}."


# ---------------------------------------------------------------------------
# Distributions: how many of each, and the spread of a value within each

#: One bar per row, plus the room the title and the value labels need.
BAR_ROW_PX = 30
BAR_CHROME_PX = 60
#: Room at the right for the value written at the end of the longest bar.
BAR_LABEL_PX = 72


def bar_height(rows: int, title: str | None = None) -> int:
    return BAR_CHROME_PX + BAR_ROW_PX * max(rows, 1) + (24 if title else 0)


#: A column chart is read at a glance, so it needs no row-by-row height.
COLUMN_HEIGHT_PX = 360


def count_bar(
    labels: Sequence[str],
    values: Sequence[float],
    *,
    text: Sequence[str],
    hovertemplate: str,
    colour: str,
    unit: str = "lots",
    vertical: bool = False,
    empty: str = "Nothing to show",
    palette: str = "light",
    title: str | None = None,
) -> go.Figure:
    """One bar per category, in the order given.

    One colour for every bar: the bar's length already carries the count, so a
    colour ramp would encode the same number twice.  Names run down the side
    with the count written at the end of each bar, which lets the value axis
    go away; an ordered scale runs along the bottom and keeps its axis, because
    a label on each of thirty columns is unreadable.
    """
    chrome = theme.CHROME[palette]
    bar = dict(
        marker=dict(color=colour, cornerradius=4),
        hovertemplate=hovertemplate,
        cliponaxis=False,
    )
    if vertical:
        fig = go.Figure(go.Bar(x=list(labels), y=list(values), **bar))
        axes = dict(
            xaxis=dict(type="category", showgrid=False, zeroline=False, title=None),
            yaxis=dict(showgrid=True, gridcolor=chrome["grid"], zeroline=False, ticks="", title=dict(text=unit)),
        )
        margin = dict(l=8, r=8, t=32 if title else 8, b=8)
        height = COLUMN_HEIGHT_PX + (24 if title else 0)
    else:
        fig = go.Figure(
            go.Bar(
                x=list(values),
                y=list(labels),
                orientation="h",
                text=list(text),
                textposition="outside",
                textfont=dict(color=chrome["secondary"], size=12),
                **bar,
            )
        )
        axes = dict(
            xaxis=dict(visible=False, showgrid=False),
            yaxis=dict(autorange="reversed", showgrid=False, zeroline=False, ticks="", title=None),
        )
        margin = dict(l=8, r=BAR_LABEL_PX, t=32 if title else 8, b=8)
        height = bar_height(len(labels), title)
    fig.update_layout(
        template=theme.template(palette),
        title=dict(text=title, yref="container", y=1, yanchor="top", pad=dict(t=8)) if title else None,
        height=height,
        bargap=0.34,
        showlegend=False,
        margin=margin,
        **axes,
    )
    if not len(labels):
        _say_empty(fig, empty, palette)
    return fig


def range_box(
    rows: pd.DataFrame,
    *,
    colour: str,
    unit: str,
    vertical: bool = False,
    empty: str = "Nothing to show",
    palette: str = "light",
    title: str | None = None,
) -> go.Figure:
    """One box per category: the quartiles, with whiskers at the 5th and 95th.

    The quantiles are computed by the caller and handed over, which keeps the
    figure small however many observations sit behind it.  The whiskers stop
    at the 5th and 95th percentile rather than at the extremes, because one
    lot at eight times the price of the rest flattens every box in the chart
    into a line; the cheapest and the dearest are in the table and the hover.

    Plotly labels a precomputed box's fences "min" and "max", which those are
    not, so the boxes carry no hover of their own and one scatter layer over
    the medians answers for all of them.
    """
    chrome = theme.CHROME[palette]
    value_axis = dict(
        showgrid=True,
        gridcolor=chrome["grid"],
        showline=False,
        ticks="",
        title=dict(text=unit),
        rangemode="tozero",
        separatethousands=True,
    )
    category_axis = dict(showgrid=False, zeroline=False, ticks="", title=None)
    fig = go.Figure()
    for row in rows.itertuples(index=False):
        along = dict(x=[row.label]) if vertical else dict(y=[row.label], orientation="h")
        fig.add_trace(
            go.Box(
                name=row.label,
                q1=[row.p25],
                median=[row.median],
                q3=[row.p75],
                lowerfence=[row.p5],
                upperfence=[row.p95],
                marker=dict(color=colour),
                fillcolor=theme.translucent(colour, 0.18),
                line=dict(width=2),
                hoverinfo="skip",
                showlegend=False,
                **along,
            )
        )
    if not rows.empty:
        medians = list(rows["median"])
        labels = list(rows["label"])
        fig.add_trace(
            go.Scatter(
                x=labels if vertical else medians,
                y=medians if vertical else labels,
                mode="markers",
                marker=dict(size=20, color="rgba(0,0,0,0)"),
                customdata=rows[["label", "lots", "minimum", "p5", "p25", "median", "p75", "p95", "maximum"]].to_numpy(),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "%{customdata[1]:,} lots<br>"
                    "Median %{customdata[5]:,.1f}<br>"
                    "Middle half %{customdata[4]:,.1f} to %{customdata[6]:,.1f}<br>"
                    "5th to 95th %{customdata[3]:,.1f} to %{customdata[7]:,.1f}<br>"
                    "Cheapest %{customdata[2]:,.1f}, dearest %{customdata[8]:,.1f}"
                    "<extra></extra>"
                ),
                showlegend=False,
            )
        )
    fig.update_layout(
        template=theme.template(palette),
        title=dict(text=title, yref="container", y=1, yanchor="top", pad=dict(t=8)) if title else None,
        height=(COLUMN_HEIGHT_PX + (24 if title else 0)) if vertical else bar_height(len(rows), title),
        boxgap=0.34,
        margin=dict(l=8, r=16, t=32 if title else 8, b=8),
        xaxis=dict(type="category", **category_axis) if vertical else value_axis,
        yaxis=value_axis if vertical else dict(autorange="reversed", **category_axis),
    )
    if rows.empty:
        _say_empty(fig, empty, palette)
    return fig


def _say_empty(fig: go.Figure, message: str, palette: str) -> None:
    """A cut that narrowed everything away says so, rather than drawing nothing."""
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(color=theme.CHROME[palette]["muted"], size=13),
    )


def weekly_volume(
    table: pd.DataFrame,
    *,
    label: str,
    unit: str,
    colour: str,
    share: bool = False,
    palette: str = "light",
) -> go.Figure:
    """Auctions held per week: one line, because the weeks are one measure over time.

    ``share`` divides each week by the whole period instead of leaving it as a
    count, so the weeks are read against each other rather than against an axis
    of lots.  The shape does not change; only what the axis calls it does.
    """
    chrome = theme.CHROME[palette]
    weeks = list(table.index)
    held = [int(n) for n in table["held"]] if "held" in table else []
    total = sum(held)
    values = [seen / total * 100 if total else 0.0 for seen in held] if share else held
    fig = go.Figure(
        go.Scatter(
            x=weeks,
            y=values,
            name=label,
            mode="lines+markers",
            line=dict(width=2, color=colour),
            marker=dict(size=9, color=colour, line=dict(width=2, color=chrome["surface"])),
            customdata=[[seen, total] for seen in held],
            hovertemplate=(
                "%{y:.1f}% – %{customdata[0]:,} of %{customdata[1]:,} lots<extra></extra>"
                if share
                else "%{y:,} lots<extra></extra>"
            ),
        )
    )
    if table.empty:
        _say_empty(fig, "No auction weeks on file", palette)
    fig.update_layout(
        template=theme.template(palette),
        height=COLUMN_HEIGHT_PX,
        hovermode="x unified",
        showlegend=False,
        margin=dict(l=8, r=8, t=16, b=8),
        xaxis=dict(type="date", hoverformat="%d %b %Y", showgrid=False, ticks="outside"),
        yaxis=dict(
            title=dict(text=unit),
            rangemode="tozero",
            separatethousands=True,
            **(dict(ticksuffix="%") if share else {}),
        ),
    )
    return fig
