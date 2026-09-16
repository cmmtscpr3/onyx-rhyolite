"""ASPI QRIS: quarterly value and volume, transcribed from a chart."""

from __future__ import annotations

from .. import ui


def render() -> None:
    ui.render_dataset("qris")
