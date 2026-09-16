"""Colours and the Plotly template.

The palette is the dataviz skill's validated default: eight categorical hues
in a fixed order that clears the colour-vision checks for adjacent series,
plus neutral chrome.  Series colours are assigned by position in a group's
fixed series order, never by what happens to be selected, so deselecting a
line never repaints the others.
"""

from __future__ import annotations

from typing import Mapping, Sequence

import plotly.graph_objects as go

CATEGORICAL: dict[str, tuple[str, ...]] = {
    "light": ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"),
    "dark": ("#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"),
}

CHROME: dict[str, dict[str, str]] = {
    "light": {
        "surface": "#fcfcfb",
        "page": "#f9f9f7",
        "primary": "#0b0b0b",
        "secondary": "#52514e",
        "muted": "#898781",
        "grid": "#e1e0d9",
        "axis": "#c3c2b7",
        "border": "rgba(11,11,11,0.10)",
    },
    "dark": {
        "surface": "#1a1a19",
        "page": "#0d0d0d",
        "primary": "#ffffff",
        "secondary": "#c3c2b7",
        "muted": "#898781",
        "grid": "#2c2c2a",
        "axis": "#383835",
        "border": "rgba(255,255,255,0.10)",
    },
}

#: Fixed status colours; each is always paired with a text label.
STATUS: dict[str, str] = {
    "fresh": "#0ca30c",
    "late": "#fab219",
    "stale": "#d03b3b",
    "manual": "#898781",
    "no data": "#898781",
}

FONT_FAMILY = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'

#: Dash patterns for series past the eighth slot, which share the muted grey
#: and are told apart by the legend and the dash rather than by hue.
OVERFLOW_DASHES: tuple[str, ...] = ("dash", "dot", "dashdot", "longdash", "longdashdot")


def colour_map(series_ids: Sequence[str], mode: str = "light") -> dict[str, str]:
    """A fixed colour per series id, by position in the group's order."""
    palette = CATEGORICAL[mode]
    muted = CHROME[mode]["muted"]
    return {sid: (palette[i] if i < len(palette) else muted) for i, sid in enumerate(series_ids)}


def dash_map(series_ids: Sequence[str]) -> dict[str, str]:
    """Solid for the first eight series; a distinct dash for each one after."""
    out: dict[str, str] = {}
    for i, sid in enumerate(series_ids):
        out[sid] = "solid" if i < 8 else OVERFLOW_DASHES[(i - 8) % len(OVERFLOW_DASHES)]
    return out


def template(mode: str = "light") -> go.layout.Template:
    chrome = CHROME[mode]
    return go.layout.Template(
        layout=go.Layout(
            font=dict(family=FONT_FAMILY, size=13, color=chrome["secondary"]),
            title=dict(font=dict(size=15, color=chrome["primary"]), x=0, xanchor="left"),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            colorway=list(CATEGORICAL[mode]),
            xaxis=dict(
                automargin=True,
                showgrid=False,
                showline=True,
                linecolor=chrome["axis"],
                linewidth=1,
                ticks="outside",
                tickcolor=chrome["axis"],
                tickfont=dict(color=chrome["muted"]),
                zeroline=False,
            ),
            yaxis=dict(
                automargin=True,
                showgrid=True,
                gridcolor=chrome["grid"],
                gridwidth=1,
                zeroline=True,
                zerolinecolor=chrome["axis"],
                zerolinewidth=1,
                showline=False,
                ticks="",
                tickfont=dict(color=chrome["muted"]),
                title=dict(font=dict(color=chrome["muted"], size=12)),
            ),
            legend=dict(
                bgcolor="rgba(0,0,0,0)",
                font=dict(color=chrome["secondary"], size=12),
                itemsizing="constant",
            ),
            hoverlabel=dict(
                bgcolor=chrome["surface"],
                bordercolor=chrome["grid"],
                font=dict(family=FONT_FAMILY, color=chrome["primary"], size=12),
            ),
            margin=dict(l=8, r=8, t=24, b=8),
        )
    )


def status_swatch(status: str) -> str:
    return STATUS.get(status, STATUS["no data"])


def describe(colours: Mapping[str, str]) -> str:
    """For tests and debugging: ``id=hex, …``."""
    return ", ".join(f"{k}={v}" for k, v in colours.items())
