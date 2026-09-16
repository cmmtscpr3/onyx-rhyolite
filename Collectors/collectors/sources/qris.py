"""QRIS payment statistics, from the charts ASPI publishes.

QRIS is the national QR payment standard, and ASPI (Asosiasi Sistem Pembayaran
Indonesia) is the only publisher of these figures: Bank Indonesia has no QRIS
table at all, which is worth stating because it looks like it should.  Every
one of the 34 tables in BI's SPIP family was checked — 5a/5c are cards, 5e is
electronic money, 9a–9c are RTGS, 10a–b are clearing — and none is QRIS.  So
there is no reachable fallback for this series.

**ASPI blocks datacentre traffic.**  `aspi-indonesia.or.id` sits behind
Cloudflare and answers *every* path with a 403 "Sorry, you have been blocked" —
including `/robots.txt` and `/wp-json/`. It is a WAF/IP block, not a challenge
a browser can solve: a real Chromium with an `id-ID` locale and a desktop user
agent gets the same page, and because a re-terminating egress proxy owns the
outbound TLS handshake, changing browser engines cannot change the fingerprint
Cloudflare sees. The live path here is therefore **unverified against the real
page**, and is written for a runner that is not blocked.

So this collector has two front doors and one parser:

* ``--html PATH`` (or ``QRIS_HTML``) parses a page saved from a browser, with
  no network at all. That is the route that works from a blocked runner, and it
  is the one the tests exercise.
* Otherwise Playwright loads the page and, because chart data often arrives by
  XHR rather than in the HTML, every JSON response is captured as well and
  offered to the parser.

The parser handles the two shapes WordPress chart pages actually use: a data
table in the markup, and a chart config embedded in a script. Both are tried;
whichever yields observations wins. Nothing parsed means nothing written — an
empty scrape must never silently blank a dataset.
"""

from __future__ import annotations

import datetime as dt
import html as html_module
import json
import os
import re
from pathlib import Path

from .. import paths
from ..dates import MONTHS, clean_label, month_start, normalise_unit, parse_year
from ..errors import SourceUnavailable
from ..model import Obs

URL = "https://aspi-indonesia.or.id/statistik-qris/"
PREFIX = "qris_transactions"

#: Label fragments ASPI and the Indonesian payments press use, mapped onto
#: stable series suffixes so the ids do not move when a chart title is reworded.
SERIES_ALIASES: tuple[tuple[str, str, str], ...] = (
    # (matched in a folded label, series suffix, unit when the label omits one)
    ("jumlah pengguna", "users", "count"),
    ("pengguna", "users", "count"),
    ("user", "users", "count"),
    ("jumlah merchant", "merchants", "count"),
    ("merchant", "merchants", "count"),
    ("nilai transaksi", "value", "IDR million"),
    ("nominal", "value", "IDR million"),
    ("volume transaksi", "volume", "count"),
    ("jumlah transaksi", "volume", "count"),
    ("volume", "volume", "count"),
    ("transaksi", "volume", "count"),
)

#: A unit written into a label, e.g. "Nominal Transaksi (Rp Miliar)".
_UNIT_IN_LABEL = re.compile(r"\(([^)]{1,30})\)")

_MONTH_YEAR = re.compile(
    r"^\s*([A-Za-z]{3,12})[\s\-/]+(\d{4})\s*$",
)
_YEAR_MONTH = re.compile(r"^\s*(\d{4})[\-/](\d{1,2})\s*$")
_TAG = re.compile(r"<[^>]+>")


def _fold(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().casefold()


def series_for(label: str) -> tuple[str, str] | None:
    """``('Nominal Transaksi (Rp Miliar)')`` -> ``('value', 'IDR billion')``.

    ``None`` when a label is not one of the QRIS measures, so a stray column is
    skipped rather than guessed at.
    """
    folded = _fold(label)
    if not folded:
        return None
    for needle, suffix, default_unit in SERIES_ALIASES:
        if needle in folded:
            written = _UNIT_IN_LABEL.search(str(label))
            unit = normalise_unit(written.group(1), default_unit) if written else default_unit
            return suffix, unit
    return None


def parse_period(text: object) -> dt.date | None:
    """A month from the labels these charts use: ``Jan 2026``, ``2026-01``, ``Januari 2026``."""
    label = clean_label(text)
    if not label:
        return None
    match = _YEAR_MONTH.match(label)
    if match:
        year, month = int(match.group(1)), int(match.group(2))
        return month_start(year, month) if 1 <= month <= 12 else None
    match = _MONTH_YEAR.match(label)
    if match:
        month = MONTHS.get(match.group(1).lower().rstrip("."))
        if month:
            return month_start(int(match.group(2)), month)
    year = parse_year(label)
    if year is not None and re.fullmatch(r"\s*\d{4}\s*", label):
        return None  # a bare year is not a month; annual points are not wanted here
    return None


def to_number(text: object) -> float | None:
    """A figure from a chart label or table cell, in either separator style."""
    if text is None:
        return None
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        return None if text != text else float(text)
    raw = str(text).strip().replace(" ", " ")
    raw = re.sub(r"(?i)\b(rp|idr)\b", "", raw).strip()
    raw = re.sub(r"[^\d,.\-]", "", raw)
    if not raw or raw in {"-", "--"}:
        return None
    # Whichever of "." and "," comes last is the decimal separator.  With only
    # one of them present it is a thousands separator when every group after
    # the first is exactly three digits -- which is how an Indonesian-language
    # page writes 1.234.567, and lets 12.5 stay a decimal.
    if "," in raw and "." in raw:
        raw = (
            raw.replace(".", "").replace(",", ".")
            if raw.rfind(",") > raw.rfind(".")
            else raw.replace(",", "")
        )
    elif "," in raw or "." in raw:
        separator = "," if "," in raw else "."
        groups = raw.split(separator)
        if len(groups) > 1 and all(len(group) == 3 for group in groups[1:]):
            raw = raw.replace(separator, "")
        elif separator == ",":
            raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


# ------------------------------------------------------------------ table shape
def _tables(markup: str) -> list[list[list[str]]]:
    out = []
    for table in re.findall(r"<table[^>]*>(.*?)</table>", markup, re.S | re.I):
        rows = []
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S | re.I):
            cells = [
                html_module.unescape(_TAG.sub(" ", cell)).strip()
                for cell in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S | re.I)
            ]
            if cells:
                rows.append(cells)
        if len(rows) > 1:
            out.append(rows)
    return out


def parse_tables(markup: str) -> list[Obs]:
    """Observations from any table whose first column is a month."""
    out: list[Obs] = []
    for rows in _tables(markup):
        header, *body = rows
        measures = {
            index: series_for(name)
            for index, name in enumerate(header)
            if index and series_for(name)
        }
        if not measures:
            continue
        for row in body:
            period = parse_period(row[0] if row else None)
            if period is None:
                continue
            for index, found in measures.items():
                if index >= len(row):
                    continue
                value = to_number(row[index])
                if value is None:
                    continue
                suffix, unit = found
                out.append(
                    Obs(
                        series_id=f"{PREFIX}.{suffix}",
                        ref_date=period,
                        ref_period="M",
                        value=value,
                        unit=unit,
                        notes={"shape": "table", "label": header[index]},
                    )
                )
    return out


# ------------------------------------------------------------------ chart shape
#: A chart config is only worth parsing if it names its points and its axis, so
#: a candidate brace must have one of these nearby.  Without the pre-filter the
#: scan is quadratic in the script's length -- every ``{`` in a bundle gets a
#: full balanced read -- which is minutes on a large inline script.
_CHART_MARKERS = ("series", "datasets", "categories", "labels")
_MARKER_WINDOW = 4_000
_MAX_CANDIDATES = 400
_MAX_OBJECT = 400_000
#: Inline chart configs are small.  Anything this size is a bundle, not a config.
_MAX_SCRIPT = 2_000_000


def _json_objects(text: str) -> list[dict]:
    """Balanced ``{...}`` blocks that parse as JSON and look like chart configs."""
    found: list[dict] = []
    tried = 0
    for match in re.finditer(r"\{", text):
        start = match.start()
        window = text[start : start + _MARKER_WINDOW]
        if not any(marker in window for marker in _CHART_MARKERS):
            continue
        tried += 1
        if tried > _MAX_CANDIDATES:
            break
        depth = 0
        for end in range(start, min(len(text), start + _MAX_OBJECT)):
            char = text[end]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(text[start : end + 1])
                    except ValueError:
                        pass
                    else:
                        if isinstance(parsed, dict):
                            found.append(parsed)
                    break
        if len(found) > 50:
            break
    return found


def _categories(config: dict) -> list[str]:
    for path in (("xAxis", "categories"), ("labels",), ("xaxis", "categories")):
        node = config
        for key in path:
            node = node.get(key) if isinstance(node, dict) else None
            if node is None:
                break
        if isinstance(node, list) and node:
            return [str(item) for item in node]
    data = config.get("data")
    if isinstance(data, dict):
        return _categories(data)
    return []


def _series(config: dict) -> list[dict]:
    for key in ("series", "datasets"):
        node = config.get(key)
        if isinstance(node, list) and node:
            return [item for item in node if isinstance(item, dict)]
    data = config.get("data")
    if isinstance(data, dict):
        return _series(data)
    return []


def parse_charts(markup: str) -> list[Obs]:
    """Observations from an embedded Highcharts / Chart.js / ApexCharts config."""
    out: list[Obs] = []
    for script in re.findall(r"<script[^>]*>(.*?)</script>", markup, re.S | re.I):
        if len(script) > _MAX_SCRIPT:
            continue
        for config in _json_objects(script):
            categories = _categories(config)
            series = _series(config)
            if not categories or not series:
                continue
            for entry in series:
                found = series_for(entry.get("name") or entry.get("label") or "")
                if not found:
                    continue
                suffix, unit = found
                points = entry.get("data")
                if not isinstance(points, list):
                    continue
                for label, point in zip(categories, points):
                    period = parse_period(label)
                    value = to_number(point) if not isinstance(point, (int, float)) else float(point)
                    if period is None or value is None:
                        continue
                    out.append(
                        Obs(
                            series_id=f"{PREFIX}.{suffix}",
                            ref_date=period,
                            ref_period="M",
                            value=value,
                            unit=unit,
                            notes={"shape": "chart", "label": entry.get("name") or ""},
                        )
                    )
    return out


def parse(markup: str, *, extra_json: list[str] | None = None) -> list[Obs]:
    """Every observation the page yields, from whichever shape carries them."""
    found = parse_tables(markup) + parse_charts(markup)
    for payload in extra_json or []:
        found.extend(parse_charts(f"<script>{payload}</script>"))
    # One reading per series per month; the table and the chart of the same
    # numbers would otherwise both land.
    seen: dict[tuple[str, dt.date], Obs] = {}
    for obs in found:
        seen.setdefault((obs.series_id, obs.ref_date), obs)
    return list(seen.values())


# ------------------------------------------------------------------- fetching
def read_saved(path: Path | str) -> list[Obs]:
    """Parse a page saved from a browser.  No network, and fully testable."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return parse(text)


def fetch_live(*, url: str = URL, timeout: int = 60000) -> list[Obs]:
    """Load the page in a browser, capturing XHR JSON as well as the markup."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SourceUnavailable(
            "playwright is not installed; pip install -r Collectors/requirements.txt"
        ) from exc
    from .ibid import chromium_path

    captured: list[str] = []
    with sync_playwright() as p:
        options = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
        executable = chromium_path()
        if executable:
            options["executable_path"] = executable
        browser = p.chromium.launch(**options)
        try:
            page = browser.new_context(locale="id-ID").new_page()

            def remember(response):
                kind = (response.headers or {}).get("content-type", "")
                if "json" in kind.lower():
                    try:
                        captured.append(response.text())
                    except Exception:  # noqa: BLE001 - a body we cannot read is not fatal
                        pass

            page.on("response", remember)
            page.goto(url, wait_until="networkidle", timeout=timeout)
            page.wait_for_timeout(4000)
            markup = page.content()
        finally:
            browser.close()

    if "you have been blocked" in markup.lower() or "attention required" in markup.lower():
        raise SourceUnavailable(
            f"{url} answered a Cloudflare block page. ASPI blocks datacentre "
            f"addresses; run this from an unblocked network, or save the page in a "
            f"browser and pass it with --html."
        )
    return parse(markup, extra_json=captured)


def collect(
    *,
    sess=None,
    since: dt.date | None = None,
    dry_run: bool = False,
    backups=None,
    html: str | None = None,
):
    """Parse a saved page when given one, else load the live page in a browser."""
    from ..sinks import long_csv

    saved = html or os.environ.get("QRIS_HTML")
    observations = read_saved(saved) if saved else fetch_live()
    if since:
        observations = [obs for obs in observations if obs.ref_date >= since]
    if not observations:
        raise SourceUnavailable(
            f"no QRIS series found in {'the saved page' if saved else URL}; "
            f"leaving {paths.consumption_csv(PREFIX).name} untouched"
        )
    return [
        long_csv.upsert(
            paths.consumption_csv(PREFIX), observations, dry_run=dry_run, backups=backups
        )
    ]
