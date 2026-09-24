"""ibid vehicle auctions: how much went under the hammer, and what it went for.

Each category opens with the lots it put into auction week by week against the
ones it sold, then a filter bar and two layers of breakdown.  The top layer is
what the vehicle is called; open one brand or model up and the layer below
shows what its condition and its age do to the price.  Only one layer is on
screen at a time, because showing every cut at once was the quickest way to
make the page unreadable.
"""

from __future__ import annotations

import streamlit as st

from .. import catalogue, charts, ui

KEY = "ibid"
#: The two answers the auction filter takes; the first is what a page opens on.
HELD_ONLY, EVERYTHING = "Completed", "All"


def render() -> None:
    dataset = catalogue.BY_KEY[KEY]
    bundle = ui.bundle()
    lots = bundle.lots
    ui.page_header(dataset, charts.latest_observation(bundle, dataset))

    categories = list(charts.CATEGORY_LABEL)
    for tab, category in zip(st.tabs([charts.CATEGORY_LABEL[key] for key in categories]), categories):
        with tab:
            _category(lots, category)


def _breakdown(container, label: str, specs, key: str, **kwargs) -> charts.Breakdown:
    """One of the breakdowns, picked by its label."""
    labels = [spec.label for spec in specs]
    return specs[labels.index(ui.choice(container, label, labels, key, **kwargs))]


def _filters(lots, category: str) -> tuple[charts.Breakdown, str, charts.Breakdown, bool]:
    """The one bar that scopes everything below it, read left to right.

    Four cells of equal weight: what to break the lots down by, which one of
    them to open up, what to cut that one by, and which auctions count.  The
    last is read before the second, because which brands are worth opening
    depends on it.
    """
    with st.container(border=True):
        naming, within, layer, auctions = st.columns(4, vertical_alignment="bottom")
        top = _breakdown(naming, "Break down by", charts.TOP_BREAKDOWNS, f"{KEY}:{category}:top")
        held_only = (
            ui.choice(
                auctions,
                "Auctions",
                [HELD_ONLY, EVERYTHING],
                f"{KEY}:{category}:held",
                help=(
                    "Completed leaves out lots whose auction had not been held when ibid was last read, whose "
                    "price is an asking price rather than one the auction settled on. Everything below this bar "
                    "is scoped by it."
                ),
            )
            == HELD_ONLY
        )
        whole = charts.narrowed(lots, category, top, sold_only=held_only)
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
        second = _breakdown(
            layer, "then by", charts.SECOND_BREAKDOWNS, f"{KEY}:{category}:second", disabled=not scope
        )
    return top, scope, second, held_only


def _category(lots, category: str) -> None:
    palette = ui.palette()
    ui.show_panel(charts.weekly_panel(lots, category, palette=palette), f"{KEY}:{category}:weekly")

    top, scope, second, held_only = _filters(lots, category)
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
