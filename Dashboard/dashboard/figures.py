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
