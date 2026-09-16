"""Bank Indonesia SPIP: e-money, cards, payment system indicators."""

from __future__ import annotations

from .. import ui


def render() -> None:
    ui.render_dataset("spip")
