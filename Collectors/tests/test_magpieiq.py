"""The Magpie IQ e-commerce GMV parser, against recorded chart markup."""

from __future__ import annotations

import datetime as dt

import pytest

from collectors.sources import magpieiq
from collectors.sources.magpieiq import ChartError


def _series(fixtures, name, sub):
    return magpieiq.parse((fixtures / f"magpieiq_{name}.html").read_text(), sub=sub)


def test_shopee_matches_the_figures_the_page_states_in_prose(fixtures):
    """Two independent anchors, so this is exact rather than eyeballed.

    The page says Shopee "peaked at about $419M in the October 2024 sales
    season" and "runs around $264M a month in 2026".
    """
    rows = _series(fixtures, "shopee", "shopee")
    assert len(rows) == 35
    assert rows[0].ref_date == dt.date(2023, 7, 1)
    assert rows[-1].ref_date == dt.date(2026, 5, 1)

    by_date = {obs.ref_date: obs.value for obs in rows}
    assert by_date[dt.date(2024, 10, 1)] == pytest.approx(419.0, abs=0.5)
    assert by_date[dt.date(2026, 5, 1)] == pytest.approx(264.0, abs=0.5)
    assert max(by_date.values()) == by_date[dt.date(2024, 10, 1)]


def test_tokopedia_matches_its_stated_figures(fixtures):
    """The page quotes "$64.1M" and "$5.96M"."""
    rows = _series(fixtures, "tokopedia", "tokopedia")
    by_date = {obs.ref_date: obs.value for obs in rows}
    assert max(by_date.values()) == pytest.approx(64.1, abs=0.2)
    assert by_date[dt.date(2026, 5, 1)] == pytest.approx(5.96, abs=0.1)


def test_the_month_anchor_comes_from_the_axis_not_the_json_ld(fixtures):
    """Every page ships temporalCoverage 2023-07/2026-05. Two of them lie.

    Tokopedia's chart starts Jul '24 and TikTok Shop's Jun '24, so trusting the
    metadata would put every row of those two a year out.
    """
    for name, sub, start, count in (
        ("tokopedia", "tokopedia", dt.date(2024, 7, 1), 23),
        ("tiktok_shop", "tiktok_shop", dt.date(2024, 6, 1), 24),
    ):
        markup = (fixtures / f"magpieiq_{name}.html").read_text()
        assert '"temporalCoverage": "2023-07/2026-05"' in markup
        rows = magpieiq.parse(markup, sub=sub)
        assert (rows[0].ref_date, len(rows)) == (start, count)
        assert rows[-1].ref_date == dt.date(2026, 5, 1)


@pytest.mark.parametrize(
    "name,sub", [("shopee", "shopee"), ("tokopedia", "tokopedia"), ("tiktok_shop", "tiktok_shop")]
)
def test_every_page_is_monthly_national_and_contiguous(fixtures, name, sub):
    rows = _series(fixtures, name, sub)
    assert [obs.ref_period for obs in rows] == ["M"] * len(rows)
    assert {obs.geo_id for obs in rows} == {"0000"}
    assert {obs.unit for obs in rows} == {"USD million"}
    assert {obs.series_id for obs in rows} == {f"ecommerce_gmv.{sub}"}
    for earlier, later in zip(rows, rows[1:]):
        assert magpieiq.add_months(earlier.ref_date, 1) == later.ref_date


@pytest.mark.parametrize(
    "name,sub", [("shopee", "shopee"), ("tokopedia", "tokopedia"), ("tiktok_shop", "tiktok_shop")]
)
def test_the_peak_marker_agrees_with_the_series_maximum(fixtures, name, sub):
    """The check that catches the dropped-point trap.

    The peak month's dot carries `dp-dot dp-dot--peak`, so a parser matching
    `class="dp-dot"` exactly loses it and shifts every date. Then the marker and
    the maximum disagree, and parse() raises instead of storing wrong dates.
    """
    rows = _series(fixtures, name, sub)  # would raise if they diverged
    assert rows


def test_a_dropped_point_is_caught_rather_than_stored(fixtures):
    """Simulate the trap: remove the peak from the polyline and re-parse.

    The series then ends a month early, which the stated last month catches
    first -- either guard is a pass, the point is that it never stores silently.
    """
    markup = (fixtures / "magpieiq_shopee.html").read_text()
    points = magpieiq._POLYLINE.search(markup).group(1).split()
    peak = magpieiq._PEAK.search(markup)
    without = " ".join(p for p in points if not p.startswith(peak.group(1) + ","))
    assert len(without.split()) == len(points) - 1
    broken = markup.replace(" ".join(points), without)
    with pytest.raises(ChartError, match="data through|peak"):
        magpieiq.parse(broken, sub="shopee")


def test_the_peak_guard_catches_a_dropped_point_on_its_own(fixtures):
    """Isolate it: drop the peak and move the anchor so the dates still line up.

    With the last-month check satisfied, only the disagreement between the
    highlighted dot and the series maximum is left to notice the loss.
    """
    markup = (fixtures / "magpieiq_shopee.html").read_text()
    points = magpieiq._POLYLINE.search(markup).group(1).split()
    peak = magpieiq._PEAK.search(markup)
    without = " ".join(p for p in points if not p.startswith(peak.group(1) + ","))
    broken = markup.replace(" ".join(points), without).replace("Jul &#x27;23", "Aug &#x27;23")
    with pytest.raises(ChartError, match="peak"):
        magpieiq.parse(broken, sub="shopee")


def test_a_shifted_anchor_is_caught_by_the_pages_own_last_month(fixtures):
    """The page states 'Data through May 2026'; the arithmetic must land there."""
    markup = (fixtures / "magpieiq_shopee.html").read_text()
    shifted = markup.replace("Jul &#x27;23", "Jul &#x27;22")
    with pytest.raises(ChartError, match="data through"):
        magpieiq.parse(shifted, sub="shopee")


def test_each_page_carries_its_own_y_scale(fixtures):
    """Shopee steps $200M per gridline, Tokopedia $20M, TikTok Shop $10M.

    The scale is negative because SVG y grows downward while value grows up.
    """
    scales = {}
    for name in ("shopee", "tokopedia", "tiktok_shop"):
        markup = (fixtures / f"magpieiq_{name}.html").read_text()
        svg = magpieiq._CHART.search(markup).group(0)
        _, _, per_pixel = magpieiq.axis_scale(svg)
        scales[name] = round(abs(per_pixel) * 54.5 / 1e6)
    assert scales == {"shopee": 200, "tokopedia": 20, "tiktok_shop": 10}


def test_a_page_with_no_chart_is_reported_not_written():
    with pytest.raises(ChartError, match="no GMV chart"):
        magpieiq.parse("<html><body><p>Maintenance</p></body></html>", sub="shopee")


def test_values_are_stored_in_millions_to_two_decimals(fixtures):
    """The pages quote "$5.96M", which is also about the coordinate resolution."""
    rows = _series(fixtures, "tokopedia", "tokopedia")
    assert all(obs.value == round(obs.value, 2) for obs in rows)
    assert magpieiq.UNIT == "USD million"
