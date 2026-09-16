"""Indonesian e-commerce GMV, from the Magpie IQ data pages.

Monthly gross merchandise value for the platforms that matter in Indonesia --
Shopee, Tokopedia, TikTok Shop -- plus the all-platform market total.

**These are one vendor's estimates, not reported platform figures.** Magpie IQ
derives them from continuous SKU-level tracking, and the pages mark the dataset
``isAccessibleForFree: false`` under their own licence, selling the exact
figures as a product. What this collector recovers is what they *plotted*, so
treat the series as an indicator of direction and relative scale, and check
``https://magpieiq.com/terms`` before republishing it anywhere.

The charts are server-rendered inline SVG, so no browser is needed:

* ``<polyline class="dp-line" points="x,y ...">`` carries the whole series.
* Two gridlines pair a pixel ``y`` with a dollar label, which gives an exact
  linear pixel-to-value map -- ``y=240`` is ``$0`` and ``y=185.5`` is ``$200M``
  on the Shopee page.
* Points are one month apart, anchored on the first x-axis label.

Two things in this markup will quietly corrupt the output if taken at face
value, and both are pinned by tests:

* **Read the polyline, not the circles.** The peak month's dot carries an extra
  class (``dp-dot dp-dot--peak``) and a larger radius, so matching
  ``class="dp-dot"`` exactly drops exactly one point and shifts every date by a
  month. That turned Shopee's real peak -- $419M in October 2024 -- into $404M
  in September 2025.
* **Anchor the months on the x-axis label, never on the JSON-LD.** Every page
  ships ``"temporalCoverage": "2023-07/2026-05"``, but Tokopedia's chart starts
  Jul '24 and TikTok Shop's Jun '24. On two of the four pages the metadata is a
  copy-paste default, and believing it puts every row a year out.

Accuracy is good enough to check against the pages' own prose, which is what
the tests do: the extracted Shopee peak is $419M against "about $419M in the
October 2024 sales season", and Tokopedia's latest month is $5.96M against
"$5.96M". Resolution is one decimal place of a coordinate -- about $0.4M on the
$200M-gridline pages and $40K on Tokopedia's.
"""

from __future__ import annotations

import datetime as dt
import html as html_module
import re
from dataclasses import dataclass

from .. import paths
from ..dates import MONTHS
from ..errors import SourceUnavailable
from ..http import fetch
from ..model import Obs

BASE = "https://magpieiq.com/data"
PREFIX = "ecommerce_gmv"
UNIT = "USD million"

#: Rounding for the stored figure.  The pages quote two decimals of a million
#: ("$5.96M"), which is also about the resolution the coordinates support, so
#: storing more would be false precision and storing less would lose the source's
#: own granularity.
DECIMALS = 2

_SUFFIX = {"": 1.0, "K": 1e3, "M": 1e6, "B": 1e9}
_CHART = re.compile(r'<svg viewBox="0 0 760 280".*?</svg>', re.S)
_GRIDLINE = re.compile(r'<line class="dp-grid" x1="[\d.]+" y1="([\d.]+)"')
_GRIDTEXT = re.compile(r'<text class="dp-gtxt"[^>]*>([^<]+)</text>')
_POLYLINE = re.compile(r'<polyline class="dp-line" points="([^"]+)"')
_PEAK = re.compile(r'class="dp-dot dp-dot--peak" cx="([\d.]+)" cy="([\d.]+)"')
_MONEY = re.compile(r"^\$([\d.]+)([KMB]?)$")
_AXIS_MONTH = re.compile(r"^([A-Za-z]{3})\s*'(\d{2})")
#: "Data through May 2026" -- the page's own statement of its last month, which
#: is an independent check on the date arithmetic.
_THROUGH = re.compile(r"Data through\s+([A-Za-z]+)\s+(\d{4})", re.I)


class ChartError(SourceUnavailable):
    """The chart is not shaped the way the parser expects."""


@dataclass(frozen=True, slots=True)
class Page:
    slug: str
    sub: str

    @property
    def url(self) -> str:
        return f"{BASE}/{self.slug}/"


PAGES = (
    Page("shopee-gmv-trend-indonesia-2026", "shopee"),
    Page("tokopedia-gmv-trend-indonesia-2026", "tokopedia"),
    Page("tiktok-shop-gmv-trend-indonesia-2026", "tiktok_shop"),
    Page("indonesia-ecommerce-market-size-2026", "total_market"),
)


def _month_name(name: str) -> int | None:
    return MONTHS.get(name.strip().lower().rstrip("."))


def add_months(start: dt.date, count: int) -> dt.date:
    total = (start.year * 12 + start.month - 1) + count
    return dt.date(total // 12, total % 12 + 1, 1)


def axis_scale(svg: str) -> tuple[float, float, float]:
    """``(pixel, value, value per pixel)`` from two labelled gridlines."""
    pixels = [float(y) for y in _GRIDLINE.findall(svg)]
    values = []
    for label in _GRIDTEXT.findall(svg):
        found = _MONEY.match(html_module.unescape(label).strip())
        if found:
            values.append(float(found.group(1)) * _SUFFIX[found.group(2)])
    if len(pixels) < 2 or len(values) < 2:
        raise ChartError("chart has fewer than two labelled gridlines")
    span = pixels[1] - pixels[0]
    if not span:
        raise ChartError("two gridlines share a pixel row")
    return pixels[0], values[0], (values[1] - values[0]) / span


def first_month(svg: str) -> dt.date:
    """The month of the leftmost point, from the first x-axis label."""
    for label in _GRIDTEXT.findall(svg):
        text = html_module.unescape(label).strip()
        if text.startswith("$"):
            continue
        found = _AXIS_MONTH.match(text)
        if found:
            month = _month_name(found.group(1))
            if month:
                return dt.date(2000 + int(found.group(2)), month, 1)
    raise ChartError("no month label on the x axis to anchor the series")


def parse(markup: str, *, sub: str) -> list[Obs]:
    """The monthly series one data page plots."""
    chart = _CHART.search(markup)
    if not chart:
        raise ChartError("page has no GMV chart")
    svg = chart.group(0)

    zero_pixel, zero_value, per_pixel = axis_scale(svg)
    points = _POLYLINE.search(svg)
    if not points:
        raise ChartError("chart has no data polyline")

    def value_at(pixel: float) -> float:
        return zero_value + (pixel - zero_pixel) * per_pixel

    start = first_month(svg)
    out: list[Obs] = []
    for index, pair in enumerate(points.group(1).split()):
        _, _, y = pair.partition(",")
        out.append(
            Obs(
                series_id=f"{PREFIX}.{sub}",
                ref_date=add_months(start, index),
                ref_period="M",
                value=round(value_at(float(y)) / 1e6, DECIMALS),
                unit=UNIT,
                notes={"source": "magpieiq", "shape": "svg polyline"},
            )
        )
    if not out:
        raise ChartError("chart polyline is empty")

    _check_last_month(markup, out)
    _check_peak(svg, out, value_at)
    return out


def _check_last_month(markup: str, observations: list[Obs]) -> None:
    """The page states its own last month; the arithmetic must land on it.

    This is what catches a layout change that shifts the whole series, which is
    otherwise invisible -- the numbers stay plausible and only the dates move.
    """
    stated = _THROUGH.search(html_module.unescape(re.sub(r"<[^>]+>", " ", markup)))
    if not stated:
        return
    month = _month_name(stated.group(1))
    if not month:
        return
    expected = dt.date(int(stated.group(2)), month, 1)
    if observations[-1].ref_date != expected:
        raise ChartError(
            f"the page says data through {expected:%B %Y} but the series ends "
            f"{observations[-1].ref_date:%B %Y}; the month anchor or the point "
            f"count is wrong"
        )


def _check_peak(svg: str, observations: list[Obs], value_at) -> None:
    """The highlighted dot must agree with the series' own maximum.

    If the polyline lost a point, the peak marker and the maximum diverge, so
    this catches the class-name trap rather than trusting a comment about it.
    """
    marker = _PEAK.search(svg)
    if not marker:
        return
    highlighted = round(value_at(float(marker.group(2))) / 1e6, DECIMALS)
    largest = max(obs.value for obs in observations)
    if abs(highlighted - largest) > max(0.5, abs(largest) * 0.005):
        raise ChartError(
            f"the highlighted peak is {highlighted} but the series maximum is "
            f"{largest}; a data point was probably missed"
        )


def collect(*, sess=None, since: dt.date | None = None, dry_run: bool = False, backups=None):
    from ..sinks import long_csv

    observations: list[Obs] = []
    failures: list[str] = []
    for page in PAGES:
        try:
            payload = fetch(page.url, sess=sess)
            observations.extend(parse(payload.text(), sub=page.sub))
        except SourceUnavailable as exc:
            # One page changing shape must not cost the other three.
            failures.append(f"{page.sub}: {exc}")

    if since:
        observations = [obs for obs in observations if obs.ref_date >= since]
    if not observations:
        raise SourceUnavailable(
            "no e-commerce GMV series parsed; " + ("; ".join(failures) or "all pages empty")
        )

    reports = [
        long_csv.upsert(
            paths.consumption_csv(PREFIX), observations, dry_run=dry_run, backups=backups
        )
    ]
    reports[0].warnings = [f"could not parse {f}" for f in failures]
    return reports
