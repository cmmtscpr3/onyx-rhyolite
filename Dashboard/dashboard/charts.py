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
    inflation: data.Inflation


def load_bundle() -> Bundle:
    return Bundle(
        series=data.load_series(),
        pihps=data.load_pihps(),
        lots=data.load_lots(),
        fingerprint=data.fingerprint(),
        inflation=data.load_bps_inflation(),
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
    #: Decimals in the table and hover, when the publisher's own precision
    #: should be kept rather than read off the magnitude.
    decimals: int | None = None


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

#: English names for the PIHPS commodities, for display only: the data, the
#: collector and every key stay in Bank Indonesia's Indonesian.  The ten foods
#: are named as BI's own English inflation releases name them -- "shallots",
#: "bird's eye chili", "purebred chicken eggs", "broiler chicken meat",
#: "cooking oil", "granulated sugar" -- spelt "chilli" here.  Each variety adds
#: the qualifier its Indonesian name carries, read against the PIHPS FAQ's
#: description of it; that is also why the top rice tier, "Super" on BI's
#: tables, is "premium", which is what the FAQ calls it.
PIHPS_ENGLISH: dict[str, str] = {
    "Beras": "Rice",
    "Beras Kualitas Bawah I": "Rice, low quality I",
    "Beras Kualitas Bawah II": "Rice, low quality II",
    "Beras Kualitas Medium I": "Rice, medium quality I",
    "Beras Kualitas Medium II": "Rice, medium quality II",
    "Beras Kualitas Super I": "Rice, premium quality I",
    "Beras Kualitas Super II": "Rice, premium quality II",
    "Daging Ayam": "Chicken meat",
    "Daging Ayam Ras Segar": "Chicken meat, broiler, fresh",
    "Daging Sapi": "Beef",
    "Daging Sapi Kualitas 1": "Beef, quality 1",
    "Daging Sapi Kualitas 2": "Beef, quality 2",
    "Telur Ayam": "Chicken eggs",
    "Telur Ayam Ras Segar": "Chicken eggs, purebred, fresh",
    "Bawang Merah": "Shallots",
    "Bawang Merah Ukuran Sedang": "Shallots, medium size",
    "Bawang Putih": "Garlic",
    "Bawang Putih Ukuran Sedang": "Garlic, medium size",
    "Cabai Merah": "Red chilli",
    "Cabai Merah Besar": "Red chilli, large",
    "Cabai Merah Keriting": "Red chilli, curly",
    "Cabai Rawit": "Bird's eye chilli",
    "Cabai Rawit Hijau": "Bird's eye chilli, green",
    "Cabai Rawit Merah": "Bird's eye chilli, red",
    "Minyak Goreng": "Cooking oil",
    "Minyak Goreng Curah": "Cooking oil, bulk",
    "Minyak Goreng Kemasan Bermerk 1": "Cooking oil, branded pack 1",
    "Minyak Goreng Kemasan Bermerk 2": "Cooking oil, branded pack 2",
    "Gula Pasir": "Granulated sugar",
    "Gula Pasir Kualitas Premium": "Granulated sugar, premium quality",
    "Gula Pasir Lokal": "Granulated sugar, local",
}


def pihps_label(commodity: str) -> str:
    """A commodity's English name, or BI's own for one new to the list."""
    return PIHPS_ENGLISH.get(commodity, commodity)


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
    labels = {c: pihps_label(c) for c in frame.columns}
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
        note="Group rows (e.g. Rice) are the average of their varieties.",
        mode=mode,
    )


# ---------------------------------------------------------------------------
# BPS inflation

INFLATION_KEY = "bps_inflation"
#: Rates in percent, so the tables report changes in points.
INFLATION_UNIT = "percent"
#: BPS publishes the rates to two decimals.
INFLATION_DECIMALS = 2
INFLATION_LABELS = {"yoy": "Year-on-year", "mtm": "Month-on-month"}
COMPONENT_LABELS = {
    "headline": "Headline",
    "core": "Core",
    "administered": "Administered prices",
    "volatile": "Volatile food",
}
REGION = "Region"
MONTH_FORMAT = "%b %Y"


def _inflation_chart(
    frame: pd.DataFrame,
    order: Sequence[str],
    selected: Sequence[str],
    labels: dict[str, str],
    *,
    key: str,
    title: str,
    note: str,
    since_year: int | None,
    palette: str,
    chart_title: str | None,
) -> Chart:
    chosen = [column for column in order if column in selected and column in frame.columns]
    shown = transform.since(frame[chosen], since_year)
    figure = figures.line_chart(
        shown,
        labels=labels,
        unit=INFLATION_UNIT,
        colours=theme.colour_map(list(order), palette),
        mode=LEVEL,
        palette=palette,
        title=chart_title,
        decimals=INFLATION_DECIMALS,
    )
    table = transform.latest_table(frame[chosen], "monthly", labels, INFLATION_UNIT)
    return Chart(
        key=key,
        title=title,
        unit=INFLATION_UNIT,
        figure=figure,
        table=table,
        frequency="monthly",
        note=note,
        decimals=INFLATION_DECIMALS,
    )


def inflation_chart(
    inflation: data.Inflation,
    *,
    measures: Sequence[str] = data.INFLATION_MEASURES,
    since_year: int | None = None,
    palette: str = "light",
    title: str | None = None,
) -> Chart:
    """Headline inflation, year-on-year and month-on-month on one axis."""
    return _inflation_chart(
        inflation.national,
        data.INFLATION_MEASURES,
        measures,
        INFLATION_LABELS,
        key="headline",
        title="Headline inflation",
        note="Consumer price inflation as BPS publishes it; the year-on-year rate starts in December 2009.",
        since_year=since_year,
        palette=palette,
        chart_title=title,
    )


def inflation_components_chart(
    inflation: data.Inflation,
    *,
    selected: Sequence[str] = data.INFLATION_COMPONENTS,
    since_year: int | None = None,
    palette: str = "light",
    title: str | None = None,
) -> Chart:
    """Bank Indonesia's disaggregation, month-on-month."""
    return _inflation_chart(
        inflation.components,
        data.INFLATION_COMPONENTS,
        selected,
        COMPONENT_LABELS,
        key="components",
        title="Inflation by component, month-on-month",
        note="Bank Indonesia's disaggregation of the consumer price index; a month blank at source breaks the line.",
        since_year=since_year,
        palette=palette,
        chart_title=title,
    )


def province_table(inflation: data.Inflation, *, since_year: int | None = None) -> pd.DataFrame:
    """Year-on-year inflation by region: one row per region, one column per month.

    Indonesia is pinned to the top and the provinces follow in order of their
    latest rate, hottest first; the months run newest first, so the latest
    sits beside the name without scrolling.
    """
    frame = transform.since(inflation.provinces, since_year)
    if frame.empty:
        return pd.DataFrame(columns=[REGION])
    frame = frame.sort_index(ascending=False)
    latest = frame.iloc[0]
    provinces = [c for c in frame.columns if c != data.NATIONAL_COLUMN]
    provinces.sort(key=lambda c: (-latest[c] if pd.notna(latest[c]) else float("inf"), c))
    order = [data.NATIONAL_COLUMN, *provinces] if data.NATIONAL_COLUMN in frame.columns else provinces
    table = frame[order].T
    table.columns = [month.strftime(MONTH_FORMAT) for month in table.columns]
    table.insert(0, REGION, [data.province_label(c) for c in table.index])
    return table.reset_index(drop=True)


def province_hotter_than_national(table: pd.DataFrame) -> pd.DataFrame:
    """True where a province's rate exceeds Indonesia's in the same month.

    Same shape as :func:`province_table`; the region column and Indonesia's own
    row are False.
    """
    months = [c for c in table.columns if c != REGION]
    mask = pd.DataFrame(False, index=table.index, columns=table.columns)
    national = table[table[REGION] == data.province_label(data.NATIONAL_COLUMN)]
    if national.empty or not months:
        return mask
    benchmark = national.iloc[0][months].astype(float)
    hotter = table[months].astype(float).gt(benchmark, axis=1)
    hotter.loc[national.index] = False
    mask[months] = hotter
    return mask


def province_panel(inflation: data.Inflation, *, palette: str = "light") -> Panel:
    """The latest month's year-on-year rate by region, ranked, for the export.

    The app shows the month-by-month table with the hot cells coloured; the
    offline file has no styled table, so it carries the ranking instead,
    with the provinces above Indonesia in the same red.
    """
    table = province_table(inflation)
    months = [c for c in table.columns if c != REGION]
    month = months[0] if months else ""
    hot = province_hotter_than_national(table)[month] if month else pd.Series(dtype=bool)
    values = table[month].astype(float) if month else pd.Series(dtype=float)
    national = table[REGION] == data.province_label(data.NATIONAL_COLUMN)
    colours = [
        theme.STATUS["stale"] if is_hot else (theme.CHROME[palette]["muted"] if is_national else theme.CATEGORICAL[palette][0])
        for is_hot, is_national in zip(hot, national)
    ]
    figure = figures.count_bar(
        list(table[REGION]),
        list(values),
        text=[transform.format_number(v, INFLATION_UNIT, INFLATION_DECIMALS) for v in values],
        hovertemplate="%{y}<br>%{x:.2f}% year-on-year<extra></extra>",
        colour=colours,
        empty="No province figures on file",
        palette=palette,
    )
    benchmark = float(values[national].iloc[0]) if national.any() and month else float("nan")
    shown = pd.DataFrame(
        {
            REGION: table[REGION],
            f"Year-on-year ({month})" if month else "Year-on-year": values.map(
                lambda v: transform.format_number(v, INFLATION_UNIT, INFLATION_DECIMALS)
            ),
            "vs Indonesia": values.map(lambda v: transform.format_change(v - benchmark, INFLATION_UNIT, INFLATION_DECIMALS)),
        }
    )
    if national.any():
        shown.loc[national, "vs Indonesia"] = ""
    return Panel(
        key="provinces",
        title=f"Year-on-year inflation by province, {month}" if month else "Year-on-year inflation by province",
        figure=figure,
        table=shown,
        note="Red: above Indonesia's rate in the same month.",
        unit=INFLATION_UNIT,
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
        # The day of the last scrape (each one finds lots new to the file):
        # the latest auction can lie days past it.
        scraped = bundle.lots["first_seen"].max() if not bundle.lots.empty else None
        return None if pd.isna(scraped) else scraped.normalize()
    if dataset.key == INFLATION_KEY:
        return bundle.inflation.latest
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
        elif dataset.key == INFLATION_KEY:
            charts = [
                inflation_chart(bundle.inflation, palette=palette),
                province_panel(bundle.inflation, palette=palette),
                inflation_components_chart(bundle.inflation, palette=palette),
            ]
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
    return Panel(
        f"lots_by_{spec.key}_{_slug(scope)}", _titled("Lots", spec, scope), figure, table,
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
    return Panel(
        f"price_by_{spec.key}_{_slug(scope)}",
        _titled("Listed price", spec, scope),
        figure,
        table,
        "",
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
    return Panel(
        f"weekly_{category}",
        "Lots in auction and lots sold each week" + (f", {scope}" if scope else ""),
        figure,
        table,
        "ibid marks a lot Terjual once its auction has been held",
        "lots",
    )
