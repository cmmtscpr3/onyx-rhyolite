"""ibid vehicle auctions: weekly median listed price and lot counts."""

from __future__ import annotations

import streamlit as st

from .. import catalogue, charts, ui

KEY = "ibid"


def render() -> None:
    dataset = catalogue.BY_KEY[KEY]
    bundle = ui.bundle()
    lots = bundle.lots
    ui.page_header(dataset, charts.latest_observation(bundle, dataset))

    left, middle, right = st.columns([1, 2, 1])
    category = left.radio(
        "Category", list(charts.CATEGORY_LABEL), format_func=charts.CATEGORY_LABEL.get, horizontal=True, key=f"{KEY}:category"
    )
    models = charts.top_models(lots, category)
    model = middle.selectbox(
        "Model",
        options=[None, *models],
        format_func=lambda m: "All models" if m is None else m,
        key=f"{KEY}:model:{category}",
    )
    sold_only = right.checkbox("Sold lots only", value=True, key=f"{KEY}:sold")

    subset = charts.lots_subset(lots, category, model, sold_only)
    a, b, c, d = st.columns(4)
    a.metric("Lots", f"{len(subset):,}")
    b.metric("Distinct plates", f"{subset['plate'].nunique():,}")
    c.metric("Median listed price", f"Rp {subset['price_idr'].median() / 1e6:,.1f} mn" if not subset.empty else "–")
    all_lots = charts.lots_subset(lots, category, model, sold_only=False)
    d.metric("Sold share", f"{all_lots['sold'].mean():.0%}" if not all_lots.empty else "–")

    for chart in charts.lots_charts(lots, category=category, model=model, sold_only=sold_only, palette=ui.palette()):
        st.markdown(f"#### {chart.title}")
        ui.show_chart(chart, f"{KEY}:{chart.key}:{model or 'all'}:{sold_only}")
    st.caption(
        f"{lots.attrs.get('dropped_undated', 0)} lots without an auction date and "
        f"{lots.attrs.get('dropped_stray', 0)} with a stray pre-2025 date are left out."
    )
