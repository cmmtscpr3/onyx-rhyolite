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


def lots_subset(lots: pd.DataFrame, category: str, *, sold_only: bool = True) -> pd.DataFrame:
    """One category's lots, narrowed to the ones that found a buyer by default."""
    subset = lots[lots["category"] == category]
    return subset[subset["sold"]] if sold_only else subset


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


def default_charts(bundle: Bundle, palette: str = "light") -> list[tuple[Dataset, list[Chart | Panel]]]:
    """Every dataset's charts at their default selections, for the export."""
    out: list[tuple[Dataset, list[Chart | Panel]]] = []
    for dataset in catalogue.DATASETS:
        if dataset.key == "pihps":
            charts = [pihps_chart(bundle.pihps, market=market, palette=palette) for market in data.MARKETS]
        elif dataset.key == "ibid":
            charts = ibid_panels(bundle.lots, TOP_BREAKDOWNS[0], palette=palette)
        else:
            charts = [
                group_chart(bundle.series, group, annotations=dataset.annotations, palette=palette)
                for group in dataset.groups
                if group.heading != "Discontinued series"
            ]
        out.append((dataset, charts))
    return out


# ---------------------------------------------------------------------------
# ibid breakdowns: what sold, and what it went for

PRICE_UNIT = "IDR million"
#: Rows drawn when the categories are names.  The table under each chart lists
#: every row, so nothing is hidden by the cut.
TOP_SHOWN = 12
#: A category with fewer lots than this has a "range" that is an accident of
#: which two vehicles happened to come up, so it is left out of the price chart.
MIN_PRICED_LOTS = 8
#: Grades as ibid awards them, best first; anything ungraded sits at the end.
GRADE_ORDER: tuple[str, ...] = ("A", "B", "C", "D", "E")
UNGRADED = "Ungraded"


@dataclass(frozen=True)
class Breakdown:
    """One way of cutting a category's lots, and how to draw it.

    Names (brand, model) are ranked by how many lots there are and read down
    the side of the chart.  An ordered scale (grade, model year) keeps its own
    order and runs along the bottom, because its sequence is the point.
    """

    key: str
    label: str
    noun: str
    #: Ranked by lots, and drawn with the names down the side.
    ranked: bool = True

    @property
    def vertical(self) -> bool:
        return not self.ranked


#: The top layer: what the vehicle is called.
TOP_BREAKDOWNS: tuple[Breakdown, ...] = (
    Breakdown("brand", "Brand", "brands"),
    Breakdown("model", "Model", "models"),
)
#: The layer below it: what that vehicle's condition and age do to its price.
SECOND_BREAKDOWNS: tuple[Breakdown, ...] = (
    Breakdown("grade", "Grade", "grades", ranked=False),
    Breakdown("year", "Model year", "model years", ranked=False),
)
BREAKDOWNS: tuple[Breakdown, ...] = TOP_BREAKDOWNS + SECOND_BREAKDOWNS
BY_BREAKDOWN: dict[str, Breakdown] = {spec.key: spec for spec in BREAKDOWNS}


@dataclass
class Panel:
    """A figure with the table that carries the same numbers, already formatted."""

    key: str
    title: str
    figure: go.Figure
    table: pd.DataFrame
    note: str = ""
    unit: str = ""
    heading: str = ""


def family(lots: pd.DataFrame) -> pd.Series:
    """``'TOYOTA AVANZA'``: the brand and the model, which is how a reader names a car."""
    return lots["brand"].str.cat(lots["model"], sep=" ").str.strip()


def labelled(lots: pd.DataFrame, spec: Breakdown) -> pd.Series:
    """The lots labelled by the chosen breakdown, dropping rows it cannot place."""
    if spec.key == "brand":
        return lots["brand"].replace("", pd.NA).dropna()
    if spec.key == "model":
        return family(lots).replace("", pd.NA).dropna()
    if spec.key == "grade":
        return lots["grade"].replace({"-": UNGRADED, "": UNGRADED})
    years = lots["model_year"].dropna()
    return years.astype(int).astype(str)


def _ordered(labels: pd.Series, spec: Breakdown) -> list[str]:
    """The categories in the order the chart draws them."""
    if spec.ranked:
        return list(labels.value_counts().index)
    seen = set(labels)
    if spec.key == "grade":
        return [grade for grade in (*GRADE_ORDER, UNGRADED) if grade in seen] + sorted(
            seen - {*GRADE_ORDER, UNGRADED}
        )
    return sorted(seen)


def narrowed(
    lots: pd.DataFrame, category: str, spec: Breakdown, value: str = "", *, sold_only: bool = True
) -> pd.DataFrame:
    """One category's lots, narrowed to a single brand or model when one is named."""
    subset = lots_subset(lots, category, sold_only=sold_only)
    if not value:
        return subset
    labels = labelled(subset, spec)
    return subset.loc[labels.index[labels == value]]


def drillable(subset: pd.DataFrame, spec: Breakdown, *, min_lots: int = MIN_PRICED_LOTS) -> list[str]:
    """The brands or models worth opening up, most lots first.

    One with only a handful of lots has nothing left to say once it is cut
    again by grade or by year, so it is not offered.
    """
    tally = labelled(subset, spec).value_counts()
    return [str(name) for name, lots in tally.items() if lots >= min_lots]


def counts(subset: pd.DataFrame, spec: Breakdown) -> pd.DataFrame:
    """Lots per category, in the breakdown's own order, with each one's share."""
    labels = labelled(subset, spec)
    tally = labels.value_counts()
    order = _ordered(labels, spec)
    return pd.DataFrame(
        {
            "label": order,
            "lots": [int(tally[name]) for name in order],
            "share": [tally[name] / max(len(labels), 1) * 100.0 for name in order],
        }
    )


def price_ranges(
    subset: pd.DataFrame,
    spec: Breakdown,
    *,
    limit: int = TOP_SHOWN,
    min_lots: int = MIN_PRICED_LOTS,
) -> pd.DataFrame:
    """The spread of listed prices within each category, in millions of rupiah.

    Quartiles, the 5th and 95th percentiles that the whiskers are drawn to, and
    the true extremes for the table.  Categories with too few lots to have a
    meaningful spread are left out, and when the categories are names only the
    ones with the most lots are kept, in that order, so that the brands and
    models read down the side in the same order as the chart of lots above;
    an ordered scale keeps all of them so the sequence is not broken by a gap.
    """
    subset = subset[subset["price_idr"].notna()]
    labels = labelled(subset, spec)
    subset = subset.loc[labels.index]
    tally = labels.value_counts()
    keep = [name for name in _ordered(labels, spec) if tally[name] >= min_lots]
    if spec.ranked:
        keep = keep[:limit]
    rows = []
    for name in keep:
        prices = subset.loc[labels == name, "price_idr"] / 1e6
        rows.append(
            {
                "label": name,
                "lots": len(prices),
                "minimum": float(prices.min()),
                "p5": float(prices.quantile(0.05)),
                "p25": float(prices.quantile(0.25)),
                "median": float(prices.median()),
                "p75": float(prices.quantile(0.75)),
                "p95": float(prices.quantile(0.95)),
                "maximum": float(prices.max()),
            }
        )
    ranges = pd.DataFrame(
        rows, columns=["label", "lots", "minimum", "p5", "p25", "median", "p75", "p95", "maximum"]
    )
    return ranges


def _titled(what: str, spec: Breakdown, scope: str) -> str:
    return f"{what} by {spec.label.lower()}" + (f", {scope}" if scope else "")


def count_panel(subset: pd.DataFrame, spec: Breakdown, *, scope: str = "", palette: str = "light") -> Panel:
    tally = counts(subset, spec)
    shown = tally.head(TOP_SHOWN) if spec.ranked else tally
    figure = figures.count_bar(
        list(shown["label"]),
        list(shown["lots"]),
        text=[f"{int(n):,}" for n in shown["lots"]],
        hovertemplate=("%{x}<br>%{y:,} lots<extra></extra>" if spec.vertical else "%{y}<br>%{x:,} lots<extra></extra>"),
        colour=theme.CATEGORICAL[palette][0],
        vertical=spec.vertical,
        empty="No lots to count",
        palette=palette,
    )
    table = pd.DataFrame(
        {
            spec.label: tally["label"],
            "Lots": tally["lots"].map(lambda n: f"{int(n):,}"),
            "Share of lots": tally["share"].map(lambda s: f"{s:.1f}%"),
        }
    )
    hidden = len(tally) - len(shown)
    note = f"The {len(shown)} largest of {len(tally)} {spec.noun}; the table lists all of them." if hidden else ""
    return Panel(
        f"lots_by_{spec.key}_{_slug(scope)}", _titled("Lots", spec, scope), figure, table, note, "lots"
    )


def price_panel(subset: pd.DataFrame, spec: Breakdown, *, scope: str = "", palette: str = "light") -> Panel:
    ranges = price_ranges(subset, spec)
    figure = figures.range_box(
        ranges,
        colour=theme.CATEGORICAL[palette][0],
        unit=PRICE_UNIT,
        vertical=spec.vertical,
        empty=f"No {spec.noun} here with {MIN_PRICED_LOTS} lots or more",
        palette=palette,
    )
    money = lambda value: f"{value:,.1f}"  # noqa: E731
    table = pd.DataFrame(
        {
            spec.label: ranges["label"],
            "Lots": ranges["lots"].map(lambda n: f"{int(n):,}"),
            "Lowest": ranges["minimum"].map(money),
            "5th pct": ranges["p5"].map(money),
            "25th pct": ranges["p25"].map(money),
            "Median": ranges["median"].map(money),
            "75th pct": ranges["p75"].map(money),
            "95th pct": ranges["p95"].map(money),
            "Highest": ranges["maximum"].map(money),
        }
    )
    ordering = "most lots first" if spec.ranked else f"in {spec.label.lower()} order"
    note = (
        f"{len(ranges)} {spec.noun} with at least {MIN_PRICED_LOTS} lots, {ordering}, in {PRICE_UNIT.lower()}. "
        "The box spans the middle half of the lots and the line in it is the median; the whiskers stop at the 5th "
        "and 95th percentile, because a single lot at several times the price of the rest would flatten every box "
        "in the chart. The cheapest and the dearest are in the table. Prices are the ones shown on the lot card, "
        "not confirmed hammer prices."
    )
    return Panel(
        f"price_by_{spec.key}_{_slug(scope)}",
        _titled("Listed price", spec, scope),
        figure,
        table,
        note,
        PRICE_UNIT,
    )


def _slug(text: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in text).strip("_").lower() or "all"


def ibid_panels(lots: pd.DataFrame, spec: Breakdown, *, palette: str = "light") -> list[Panel]:
    """What a category's tab opens on: its weekly counts, then the top layer."""
    out: list[Panel] = []
    for category, scope in CATEGORY_LABEL.items():
        subset = lots_subset(lots, category)
        out += [
            weekly_panel(lots, category, scope=scope, palette=palette),
            count_panel(subset, spec, scope=scope, palette=palette),
            price_panel(subset, spec, scope=scope, palette=palette),
        ]
    return out


#: The two weekly counts, in the order :func:`figures.weekly_volume` draws them.
WEEKLY_LABELS: tuple[str, str] = ("Lots in auction", "Lots sold")


def weekly_panel(lots: pd.DataFrame, category: str, *, scope: str = "", palette: str = "light") -> Panel:
    """The lots ibid put up each week and, of those, the ones it sold.

    The two counts together are the weekly sold volume: the lower line is the
    volume itself and the band above it is what has yet to go under the
    hammer, so the week a scrape caught mid-flight is visibly mid-flight
    rather than a collapse in sales.
    """
    subset = lots_subset(lots, category, sold_only=False)
    weekly = transform.weekly_lots(subset)
    figure = figures.weekly_volume(
        weekly,
        labels=WEEKLY_LABELS,
        colours=theme.CATEGORICAL[palette][:2],
        unit="lots",
        palette=palette,
    )
    listed, sold = weekly["lots"], weekly["held"]
    table = pd.DataFrame(
        {
            "Auction week": [week.strftime("%d %b %Y") for week in weekly.index],
            WEEKLY_LABELS[0]: [f"{int(n):,}" for n in listed],
            WEEKLY_LABELS[1]: [f"{int(n):,}" for n in sold],
            "Share sold": [f"{s / n * 100:.0f}%" if n else "–" for n, s in zip(listed, sold)],
            "Week seen whole": ["Yes" if seen else "In part" for seen in weekly["complete"]],
        }
    )
    partial = [week.strftime("%d %b") for week in weekly.index[~weekly["complete"].astype(bool)]]
    caveat = (
        " A scrape sees only the few weeks ibid still lists, so the hollow points "
        f"({', '.join(partial)}) are weeks the scrapes did not cover day by day and count short on both lines for "
        "that reason alone."
        if partial
        else ""
    )
    return Panel(
        f"weekly_{category}",
        "Lots in auction and lots sold each week" + (f", {scope}" if scope else ""),
        figure,
        table,
        "ibid marks a lot Terjual once its auction has been held and nothing on file is marked unsold, so the sold "
        "line counts the lots whose auction had been run when each was last read rather than the ones that found a "
        "buyer. The lines part where the auctions are still to come, and where a lot dropped off the site before a "
        f"scrape could see it sold.{caveat}",
        "lots",
    )
