"""ibid vehicle auctions: what sold, and what it went for.

One tab per category.  A single switch chooses how to cut the lots, and the
two charts under it answer the same question of that cut: how many, and at
what price.  Showing every cut at once was the quickest way to make the page
unreadable.
"""

from __future__ import annotations

import streamlit as st

from .. import catalogue, charts, ui

KEY = "ibid"


def render() -> None:
    dataset = catalogue.BY_KEY[KEY]
    bundle = ui.bundle()
    lots = bundle.lots
    ui.page_header(dataset, charts.latest_observation(bundle, dataset))

    categories = list(charts.CATEGORY_LABEL)
    for tab, category in zip(st.tabs([charts.CATEGORY_LABEL[key] for key in categories]), categories):
        with tab:
            _category(lots, category)

    st.caption(
        f"{lots.attrs.get('dropped_undated', 0)} lots without an auction date, "
        f"{lots.attrs.get('dropped_stray', 0)} with a stray pre-2025 date and "
        f"{lots.attrs.get('dropped_nonvehicle', 0)} that are not a single vehicle are left out."
    )


def _category(lots, category: str) -> None:
    left, right = st.columns([1, 3])
    sold_only = left.checkbox(
        "Sold lots only",
        value=True,
        key=f"{KEY}:{category}:sold",
        help="Everything on this tab is scoped by this switch. Unsold lots carry a listed price but found no buyer.",
    )
    labels = [spec.label for spec in charts.BREAKDOWNS]
    chosen = right.radio(
        "Break down by",
        labels,
        horizontal=True,
        key=f"{KEY}:{category}:breakdown",
        help="One cut at a time: the two charts below both answer for whichever one is chosen.",
    )
    spec = charts.BREAKDOWNS[labels.index(chosen)]

    subset = charts.lots_subset(lots, category, sold_only=sold_only)
    every_lot = charts.lots_subset(lots, category, sold_only=False)
    first, second, third, fourth = st.columns(4)
    first.metric("Lots", f"{len(subset):,}")
    second.metric("Distinct plates", f"{subset['plate'].nunique():,}")
    third.metric(
        "Median listed price",
        f"Rp {subset['price_idr'].median() / 1e6:,.1f} mn" if not subset.empty else "–",
    )
    fourth.metric("Sold share", f"{every_lot['sold'].mean():.0%}" if not every_lot.empty else "–")

    palette = ui.palette()
    key = f"{KEY}:{category}:{spec.key}"
    ui.show_panel(charts.count_panel(lots, category, spec, sold_only=sold_only, palette=palette), f"{key}:lots")
    ui.show_panel(charts.price_panel(lots, category, spec, sold_only=sold_only, palette=palette), f"{key}:price")
