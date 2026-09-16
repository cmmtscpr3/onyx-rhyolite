"""From loaded data and a reader's choices to a finished chart.

Nothing here imports Streamlit, so the same functions serve the app, the
offline export and the tests.  A :class:`Chart` is a figure plus the table of
latest values that sits under it.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Sequence

import pandas as pd
import plotly.graph_objects as go

from . import catalogue, data, figures, theme, transform
from .catalogue import Annotation, Dataset, Group
from .transform import LEVEL


@dataclass
class Bundle:
    """Everything the tracker reads, loaded once."""

    series: pd.DataFrame
    pihps: pd.DataFrame
    lots: pd.DataFrame
    fingerprint: data.Fingerprint


def load_bundle() -> Bundle:
    return Bundle(
        series=data.load_series(),
        pihps=data.load_pihps(),
        lots=data.load_lots(),
        fingerprint=data.fingerprint(),
    )


@dataclass
class Chart:
    key: str
    title: str
    unit: str
    figure: go.Figure
    #: Latest value per series, always on levels whatever the chart shows.
    table: pd.DataFrame
    frequency: str = ""
    note: str = ""
    mode: str = LEVEL
    #: The sub-heading the chart's group sits under on its page.
    heading: str = ""


# ---------------------------------------------------------------------------
# Long series groups


def group_chart(
    series: pd.DataFrame,
    group: Group,
    *,
    selected: Sequence[str] | None = None,
    mode: str = LEVEL,
    since_year: int | None = None,
    annotations: Sequence[Annotation] = (),
    palette: str = "light",
    title: str | None = None,
) -> Chart:
    chosen = set(selected if selected is not None else group.shown)
    ids = [sid for sid in group.series if sid in chosen]
    frame = data.wide(series, ids)
    # The group's own frequency, not the selection's: deselecting a series
    # must not change what the y-axis means.
    frequency = data.frequency_of(series, group.series)
    shown = transform.show_as(transform.since(frame, since_year), mode, frequency)
    figure = figures.line_chart(
        shown,
        labels=group.labels,
        unit=group.unit,
        colours=theme.colour_map(group.series, palette),
        dashes=theme.dash_map(group.series),
        mode=mode,
        markers=group.markers,
        annotations=annotations,
        palette=palette,
        title=title,
    )
    table = transform.latest_table(frame, frequency, group.labels, group.unit)
    return Chart(group.key, group.title, group.unit, figure, table, frequency, group.note, mode, group.heading)


# ---------------------------------------------------------------------------
# PIHPS

PIHPS_DEFAULT: tuple[str, ...] = (
    "Beras",
    "Daging Ayam",
    "Daging Sapi",
    "Telur Ayam",
    "Bawang Merah",
    "Bawang Putih",
    "Cabai Merah",
    "Cabai Rawit",
)
PIHPS_UNIT = "IDR per kg or litre"


def pihps_styles(commodities: pd.DataFrame, palette: str = "light") -> tuple[dict[str, str], dict[str, str]]:
    """Colour by commodity group, dash by variety, fixed for every selection.

    Ten groups share eight hues: the ninth and tenth reuse the first two with a
    long dash so every commodity keeps one look whatever else is selected.
    Varieties take their group's hue with a distinct dash; the group row is
    solid.
    """
    hues = theme.CATEGORICAL[palette]
    groups = commodities.loc[commodities["level"] == 1, "commodity"].tolist()
    colours: dict[str, str] = {}
    dashes: dict[str, str] = {}
    variety_dashes = ("dash", "dot", "dashdot", "longdash", "longdashdot", "dash")
    for index, group_name in enumerate(groups):
        hue = hues[index % len(hues)]
        overflow = index >= len(hues)
        colours[group_name] = hue
        dashes[group_name] = "longdash" if overflow else "solid"
        varieties = commodities.loc[
            (commodities["level"] == 2) & (commodities["group"] == group_name), "commodity"
        ].tolist()
        for position, variety in enumerate(varieties):
            colours[variety] = hue
            dashes[variety] = variety_dashes[position % len(variety_dashes)]
    return colours, dashes


def pihps_frame(pihps: pd.DataFrame, market: str, commodities: Sequence[str]) -> pd.DataFrame:
    subset = pihps[(pihps["market"] == market) & (pihps["commodity"].isin(commodities))]
    frame = subset.pivot_table(index="week", columns="commodity", values="price", aggfunc="first")
    order = [c for c in data.pihps_commodities(pihps)["commodity"] if c in frame.columns]
    return frame.reindex(columns=order).sort_index()


def pihps_chart(
    pihps: pd.DataFrame,
    *,
    market: str = "Traditional Market",
    commodities: Sequence[str] = PIHPS_DEFAULT,
    mode: str = LEVEL,
    since_year: int | None = None,
    palette: str = "light",
    title: str | None = None,
) -> Chart:
    rows = data.pihps_commodities(pihps)
    frame = pihps_frame(pihps, market, commodities)
    colours, dashes = pihps_styles(rows, palette)
    labels = {c: c for c in frame.columns}
    shown = transform.show_as(transform.since(frame, since_year), mode, "weekly")
    figure = figures.line_chart(
        shown,
        labels=labels,
        unit=PIHPS_UNIT,
        colours=colours,
        dashes=dashes,
        mode=mode,
        palette=palette,
        title=title,
    )
    table = transform.latest_table(frame, "weekly", labels, PIHPS_UNIT)
    return Chart(
        key=f"pihps_{market}",
        title=f"{market}: weekly prices",
        unit=PIHPS_UNIT,
        figure=figure,
        table=table,
        frequency="weekly",
        note="Group rows (e.g. Beras) are the average of their varieties.",
        mode=mode,
    )


# ---------------------------------------------------------------------------
# ibid lots

CATEGORY_LABEL = {"cars": "Cars", "motorcycles": "Motorcycles"}


def top_models(lots: pd.DataFrame, category: str, limit: int = 15) -> list[str]:
    subset = lots[lots["category"] == category]
    counts = subset.groupby(["brand", "model"]).size().sort_values(ascending=False).head(limit)
    return [f"{brand} {model}" for brand, model in counts.index]


def lots_subset(lots: pd.DataFrame, category: str, model: str | None = None, sold_only: bool = True) -> pd.DataFrame:
    subset = lots[lots["category"] == category]
    if sold_only:
        subset = subset[subset["sold"]]
    if model:
        subset = subset[(subset["brand"] + " " + subset["model"]) == model]
    return subset


def lots_charts(
    lots: pd.DataFrame,
    *,
    category: str = "cars",
    model: str | None = None,
    sold_only: bool = True,
    mode: str = LEVEL,
    palette: str = "light",
) -> list[Chart]:
    subset = lots_subset(lots, category, model, sold_only)
    weekly = transform.weekly_median(subset)
    what = model or CATEGORY_LABEL[category].lower()
    qualifier = "sold lots" if sold_only else "all lots"
    hues = theme.CATEGORICAL[palette]

    price = weekly[["median_price"]].rename(columns={"median_price": "median"})
    price_labels = {"median": f"Median listed price, {what} ({qualifier})"}
    price_fig = figures.line_chart(
        transform.show_as(price, mode, "weekly"),
        labels=price_labels,
        unit="IDR",
        colours={"median": hues[0]},
        mode=mode,
        markers=True,
        palette=palette,
        range_slider=False,
    )
    count = weekly[["lots"]]
    count_labels = {"lots": f"Lots per auction week, {what} ({qualifier})"}
    count_fig = figures.line_chart(
        transform.show_as(count, mode, "weekly"),
        labels=count_labels,
        unit="lots",
        colours={"lots": hues[1]},
        mode=mode,
        markers=True,
        palette=palette,
        range_slider=False,
    )
    return [
        Chart(
            key=f"ibid_price_{category}",
            title=f"{CATEGORY_LABEL[category]}: median listed price per auction week",
            unit="IDR",
            figure=price_fig,
            table=transform.latest_table(price, "weekly", price_labels, "IDR"),
            frequency="weekly",
            note="Weeks start on Monday. The price is the one shown on the lot card, not a confirmed hammer price.",
            mode=mode,
        ),
        Chart(
            key=f"ibid_count_{category}",
            title=f"{CATEGORY_LABEL[category]}: lots per auction week",
            unit="lots",
            figure=count_fig,
            table=transform.latest_table(count, "weekly", count_labels, "lots"),
            frequency="weekly",
            note="Lots, not vehicles: a vehicle relisted after an auction counts again.",
            mode=mode,
        ),
    ]


# ---------------------------------------------------------------------------
# Freshness and defaults


def latest_observation(bundle: Bundle, dataset: Dataset) -> pd.Timestamp | None:
    if dataset.key == "pihps":
        return bundle.pihps["week"].max() if not bundle.pihps.empty else None
    if dataset.key == "ibid":
        return bundle.lots["auction_date"].max() if not bundle.lots.empty else None
    latest = data.latest_by_dataset(bundle.series)
    dates = [latest[source] for source in dataset.sources if source in latest]
    return max(dates) if dates else None


def freshness_table(bundle: Bundle, now: dt.date | None = None) -> pd.DataFrame:
    today = now or dt.date.today()
    rows = []
    for dataset in catalogue.DATASETS:
        latest = latest_observation(bundle, dataset)
        status, age = transform.freshness_status(latest, dataset.late_after_days, today, dataset.forced_status)
        rows.append(
            {
                "key": dataset.key,
                "Dataset": dataset.title,
                "Publisher": dataset.publisher.split(" (")[0],
                "Cadence": dataset.cadence,
                "Latest observation": latest.date() if latest is not None else None,
                "Age (days)": age,
                "Status": status,
                "Collector": dataset.collector,
            }
        )
    return pd.DataFrame(rows)


def default_charts(bundle: Bundle, palette: str = "light") -> list[tuple[Dataset, list[Chart]]]:
    """Every dataset's charts at their default selections, for the export."""
    out: list[tuple[Dataset, list[Chart]]] = []
    for dataset in catalogue.DATASETS:
        if dataset.key == "pihps":
            charts = [pihps_chart(bundle.pihps, market=market, palette=palette) for market in data.MARKETS]
        elif dataset.key == "ibid":
            charts = lots_charts(bundle.lots, category="cars", palette=palette) + lots_charts(
                bundle.lots, category="motorcycles", palette=palette
            )
        else:
            charts = [
                group_chart(bundle.series, group, annotations=dataset.annotations, palette=palette)
                for group in dataset.groups
                if group.heading != "Discontinued series"
            ]
        out.append((dataset, charts))
    return out
