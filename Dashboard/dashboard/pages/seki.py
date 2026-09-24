"""Bank Indonesia SEKI, as two pages in the side panel: GDP by expenditure
(a price-basis switch) and deposits by owner."""

from __future__ import annotations

from .. import catalogue, charts, ui

KEY = "seki"
BASES = ("gdp_current", "gdp_constant")


def _header():
    dataset = catalogue.BY_KEY[KEY]
    bundle = ui.bundle()
    ui.page_header(dataset, charts.latest_observation(bundle, dataset))
    return dataset, bundle


def render_gdp() -> None:
    dataset, bundle = _header()
    groups = [catalogue.group(KEY, key) for key in BASES]
    switch = ui.Switch("Price basis", tuple(group.title for group in groups))
    ui.render_switched(bundle, dataset, groups, switch, key=f"{KEY}:gdp")


def render_deposits() -> None:
    dataset, bundle = _header()
    ui.render_group(bundle, dataset, catalogue.group(KEY, "deposits"), title="")
