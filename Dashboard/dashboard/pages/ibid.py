"""ibid vehicle auctions: how much went under the hammer, and what it went for.

Each category opens with the auctions ibid ran each week, then a control
block and two layers of breakdown.  The top layer is what the vehicle is
called; open one brand or model up and the layer below shows what its
condition and its age do to the price.  Only one layer is on screen at a
time, because showing every cut at once was the quickest way to make the page
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


def _segmented(container, label: str, specs, key: str, **kwargs) -> charts.Breakdown:
    """A breakdown picker, as one row of buttons rather than a column of dots."""
    labels = [spec.label for spec in specs]
    chosen = container.segmented_control(label, labels, default=labels[0], key=key, **kwargs)
    return specs[labels.index(chosen)] if chosen else specs[0]


def _category(lots, category: str) -> None:
    palette = ui.palette()
    ui.show_panel(charts.weekly_panel(lots, category, palette=palette), f"{KEY}:{category}:weekly")

    with st.container(border=True):
        naming, held = st.columns([3, 2], vertical_alignment="bottom")
        top = _segmented(naming, "Break down by", charts.TOP_BREAKDOWNS, f"{KEY}:{category}:top")
        held_only = held.toggle(
            "Completed auctions only",
            value=True,
            key=f"{KEY}:{category}:held",
            help=(
                "Leaves out lots whose auction had not been held when ibid was last read, whose price is an asking "
                "price rather than one the auction settled on. Everything below this block is scoped by it."
            ),
        )
        whole = charts.narrowed(lots, category, top, sold_only=held_only)
        within, layer = st.columns([3, 2], vertical_alignment="bottom")
        scope = within.selectbox(
            "Within",
            ["", *charts.drillable(whole, top)],
            format_func=lambda value: f"All {top.noun}" if not value else value,
            key=f"{KEY}:{category}:{top.key}:scope",
            help=(
                f"Open one up for the layer below it. Only {top.noun} with at least {charts.MIN_PRICED_LOTS} lots "
                "are offered, because a smaller one has nothing left to say once it is cut again."
            ),
        )
        second = _segmented(
            layer, "then by", charts.SECOND_BREAKDOWNS, f"{KEY}:{category}:second", disabled=not scope
        )

    subset = charts.narrowed(lots, category, top, scope, sold_only=held_only)
    spec = second if scope else top
    # The metrics answer for the same lots the charts draw, so opening one
    # model up moves all four of them to that model.
    every_lot = charts.narrowed(lots, category, top, scope, sold_only=False)
    first, other, third, fourth = st.columns(4)
    first.metric("Lots", f"{len(subset):,}")
    other.metric("Distinct plates", f"{subset['plate'].nunique():,}")
    third.metric(
        "Median listed price",
        f"Rp {subset['price_idr'].median() / 1e6:,.1f} mn" if not subset.empty else "–",
    )
    fourth.metric(
        "Auction held",
        f"{every_lot['sold'].mean():.0%}" if not every_lot.empty else "–",
        help="The share of lots in scope whose auction ibid had already run when it was last read.",
    )

    key = f"{KEY}:{category}:{top.key}:{spec.key}:{scope or 'all'}"
    ui.show_panel(charts.count_panel(subset, spec, scope=scope, palette=palette), f"{key}:lots")
    ui.show_panel(charts.price_panel(subset, spec, scope=scope, palette=palette), f"{key}:price")
