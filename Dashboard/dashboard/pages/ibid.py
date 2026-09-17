"""ibid vehicle auctions: what sold, what it went for, and how the weekly market moved.

One tab per category, each answering three questions in order: which brands and
models came up, what they went for, and how the week-by-week market moved.
"""

from __future__ import annotations

import streamlit as st

from .. import catalogue, charts, transform, ui

KEY = "ibid"
#: Lots are aggregated into auction weeks, so changes are week on week.
FREQUENCY = "weekly"


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
    sold_only = st.checkbox(
        "Sold lots only",
        value=True,
        key=f"{KEY}:{category}:sold",
        help="Everything on this tab is scoped by this switch. Unsold lots carry a listed price but found no buyer.",
    )
    subset = charts.lots_subset(lots, category, sold_only=sold_only)
    every_lot = charts.lots_subset(lots, category, sold_only=False)
    palette = ui.palette()

    first, second, third, fourth = st.columns(4)
    first.metric("Lots", f"{len(subset):,}")
    second.metric("Distinct plates", f"{subset['plate'].nunique():,}")
    third.metric(
        "Median listed price",
        f"Rp {subset['price_idr'].median() / 1e6:,.1f} mn" if not subset.empty else "–",
    )
    fourth.metric("Sold share", f"{every_lot['sold'].mean():.0%}" if not every_lot.empty else "–")

    ui.show_panel(charts.brand_panel(lots, category, sold_only=sold_only, palette=palette), f"{KEY}:{category}:brands")
    ui.show_panel(charts.model_panel(lots, category, sold_only=sold_only, palette=palette), f"{KEY}:{category}:models")
    ui.show_panel(charts.price_panel(lots, category, sold_only=sold_only, palette=palette), f"{KEY}:{category}:prices")

    st.subheader("Week by week")
    left, right = st.columns([2, 3])
    models = charts.top_models(lots, category)
    model = left.selectbox(
        "Model",
        options=[None, *models],
        format_func=lambda name: "All models" if name is None else name,
        key=f"{KEY}:{category}:model",
    )
    mode = right.radio(
        "Show as",
        transform.show_as_options(FREQUENCY),
        horizontal=True,
        key=f"{KEY}:{category}:mode",
        help=transform.show_as_help(FREQUENCY),
    )
    for chart in charts.lots_charts(
        lots, category=category, model=model, sold_only=sold_only, mode=mode, palette=palette
    ):
        st.markdown(f"#### {chart.title}")
        ui.show_chart(chart, f"{KEY}:{category}:{chart.key}:{model or 'all'}:{sold_only}")
