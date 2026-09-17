"""The offline HTML: every chart at its default selection, one file, no network.

Plotly.js is inlined once (about 3.6 MB) and each figure is written as a div
plus a small script, so the file opens from disk with nothing else present.
The same page is also what gets published as an artifact; ``standalone=False``
leaves out the document skeleton for that.
"""

from __future__ import annotations

import datetime as dt
import html
import subprocess
from typing import Sequence

import pandas as pd
import plotly.io as pio
from plotly.offline import get_plotlyjs

from . import catalogue, charts, definitions, transform
from .catalogue import Dataset, Group
from .theme import CHROME, STATUS

WIB = dt.timezone(dt.timedelta(hours=7))

PLOTLY_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
}

STATUS_TEXT = {"fresh": "Fresh", "late": "Late", "stale": "Stale", "manual": "Manual", "no data": "No data"}


def data_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=charts.data.paths.REPO_ROOT,
            timeout=10,
        )
        return out.stdout.strip()
    except Exception:  # pragma: no cover - not a git checkout
        return ""


def plotlyjs() -> str:
    """The Plotly library, with the one literal U+FFFD it contains escaped.

    Plotly's minified source has a regex literal matching the replacement
    character (``/\ufffd/g``).  Written as the ``\\uFFFD`` escape it is the
    same JavaScript, and the file no longer carries a character that some
    hosts reject as a sign of a broken paste.
    """
    return get_plotlyjs().replace("\ufffd", "\\uFFFD")


def _css() -> str:
    c = CHROME["light"]
    return f"""
:root {{
  color-scheme: light;
  --page: {c['page']};
  --surface: {c['surface']};
  --ink: {c['primary']};
  --ink-2: {c['secondary']};
  --muted: {c['muted']};
  --grid: {c['grid']};
  --axis: {c['axis']};
  --border: {c['border']};
  --accent: #2a78d6;
}}
body {{ margin: 0; background: var(--page); color: var(--ink); font: 14px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }}
.wrap {{ max-width: 1180px; margin: 0 auto; padding-block: 24px 48px; padding-inline: 16px; }}
header.top h1 {{ font-size: 26px; margin: 0 0 4px; letter-spacing: -0.01em; }}
header.top .meta {{ color: var(--ink-2); margin: 0; }}
nav.toc {{ display: flex; flex-wrap: wrap; gap: 8px 16px; margin: 20px 0 8px; padding: 12px 0; border-top: 1px solid var(--grid); border-bottom: 1px solid var(--grid); position: sticky; top: env(safe-area-inset-top, 0px); background: var(--page); z-index: 2; }}
nav.toc a {{ color: var(--ink-2); text-decoration: none; font-size: 13px; }}
nav.toc a:hover, nav.toc a:focus {{ color: var(--accent); text-decoration: underline; }}
nav.toc .sec {{ color: var(--muted); font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; }}
section.dataset {{ padding-top: 36px; scroll-margin-top: 72px; }}
section.dataset h2 {{ font-size: 21px; margin: 0 0 4px; }}
section.dataset h3.subhead {{ font-size: 17px; margin: 28px 0 0; color: var(--ink-2); }}
section.dataset h2 .eyebrow {{ display: block; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); font-weight: 600; margin-bottom: 4px; }}
.source {{ color: var(--ink-2); margin: 0 0 12px; }}
.source a {{ color: var(--accent); }}
.notes {{ margin: 8px 0 16px; padding: 10px 14px; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; color: var(--ink-2); }}
.notes summary {{ cursor: pointer; color: var(--ink); }}
.notes ul {{ margin: 8px 0 0; padding-left: 18px; }}
.notes p.term {{ margin: 10px 0 2px; }}
.notes blockquote {{ margin: 4px 0; padding: 2px 0 2px 12px; border-left: 3px solid var(--grid); color: var(--ink); }}
.notes p.src {{ margin: 0 0 4px; font-size: 12px; }}
.chart {{ background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 12px 8px 4px; margin: 16px 0 0; }}
.chart h3 {{ font-size: 15px; margin: 0 8px 4px; }}
.chart .unit {{ color: var(--muted); font-size: 12px; margin: 0 8px 8px; }}
.chart .note {{ color: var(--ink-2); font-size: 12px; margin: 4px 8px 8px; }}
.tablewrap {{ overflow-x: auto; }}
table.latest {{ border-collapse: collapse; width: 100%; font-size: 13px; margin: 8px 0 4px; }}
table.latest th, table.latest td {{ text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--grid); white-space: nowrap; }}
table.latest th {{ color: var(--muted); font-weight: 600; font-size: 11px; letter-spacing: 0.04em; text-transform: uppercase; }}
table.latest td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
table.latest th.num {{ text-align: right; }}
.status {{ display: inline-flex; align-items: center; gap: 6px; }}
.status i {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}
footer {{ color: var(--muted); font-size: 12px; margin-top: 40px; border-top: 1px solid var(--grid); padding-top: 12px; }}
@media (max-width: 640px) {{ header.top h1 {{ font-size: 22px; }} section.dataset {{ padding-top: 28px; }} }}
"""


def _latest_table_html(table: pd.DataFrame, unit: str) -> str:
    if table.empty:
        return ""
    head = (
        "<tr><th>Series</th><th>Latest</th>"
        f"<th class=num>Value ({html.escape(unit)})</th><th class=num>vs previous</th><th class=num>vs year earlier</th></tr>"
    )
    rows = []
    for row in table.itertuples(index=False):
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(row.Series))}</td>"
            f"<td>{row.Latest:%d %b %Y}</td>"
            f"<td class=num>{html.escape(transform.format_number(row.Value, unit))}</td>"
            f"<td class=num>{html.escape(transform.format_change(row._3, unit))}</td>"
            f"<td class=num>{html.escape(transform.format_change(row._4, unit))}</td>"
            "</tr>"
        )
    return f'<div class=tablewrap><table class=latest><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div>'


def _plain_table_html(table: pd.DataFrame) -> str:
    """A table that arrives ready to print, as the ibid panels do."""
    if table.empty:
        return ""
    head = "".join(f"<th{' class=num' if i else ''}>{html.escape(str(name))}</th>" for i, name in enumerate(table.columns))
    rows = []
    for row in table.itertuples(index=False):
        cells = "".join(
            f"<td{' class=num' if i else ''}>{html.escape(str(value))}</td>" for i, value in enumerate(row)
        )
        rows.append(f"<tr>{cells}</tr>")
    return f'<div class=tablewrap><table class=latest><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def _freshness_html(bundle: charts.Bundle, now: dt.date) -> str:
    table = charts.freshness_table(bundle, now)
    head = "<tr><th>Dataset</th><th>Publisher</th><th>Cadence</th><th>Latest observation</th><th class=num>Age (days)</th><th>Status</th></tr>"
    rows = []
    for row in table.itertuples(index=False):
        status = str(row.Status)
        latest = f"{row._4:%d %b %Y}" if row._4 is not None else "–"
        age = "" if row._5 is None or pd.isna(row._5) else f"{int(row._5)}"
        rows.append(
            "<tr>"
            f'<td><a href="#{row.key}">{html.escape(row.Dataset)}</a></td>'
            f"<td>{html.escape(row.Publisher)}</td><td>{html.escape(row.Cadence)}</td>"
            f"<td>{latest}</td><td class=num>{age}</td>"
            f'<td><span class=status><i style="background:{STATUS.get(status, STATUS["no data"])}"></i>{STATUS_TEXT.get(status, status)}</span></td>'
            "</tr>"
        )
    return f'<div class=tablewrap><table class=latest><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div>'


def _lines(text: str) -> str:
    return "<br>".join(html.escape(line) for line in text.splitlines())


def _definition_html(labels: Sequence[str], definition: definitions.Definition) -> str:
    who = f"<b>{html.escape(', '.join(labels))}</b> · " if labels else ""
    out = [f'<p class="term">{who}<i>{html.escape(definition.term)}</i></p>', f"<blockquote>{_lines(definition.text)}</blockquote>"]
    if definition.english:
        out.append(f'<blockquote lang="en">{_lines(definition.english)}</blockquote>')
    if definition.note:
        out.append(f"<p>{html.escape(definition.note)}</p>")
    source = f'Source: <a href="{html.escape(definition.url)}" rel="noopener">{html.escape(definition.source)}</a>'
    if definition.english_url:
        source += f' · English text: <a href="{html.escape(definition.english_url)}" rel="noopener">{html.escape(definition.english_source)}</a>'
    out.append(f'<p class="src">{source}</p>')
    return "".join(out)


def _definitions_html(dataset: Dataset, group: Group) -> str:
    if not definitions.populated(dataset):
        return ""
    entries = definitions.for_group(dataset.key, group)
    missing = definitions.undefined(group)
    if not entries and not missing:
        return ""
    body = "".join(_definition_html(entry.labels, entry.definition) for entry in entries)
    if missing:
        qualifier = "separate " if entries else ""
        body += f'<p class="note">No {qualifier}official definition found for: {html.escape(", ".join(missing))}.</p>'
    return f'<details class="notes"><summary>Official definitions</summary>{body}</details>'


def build_offline_html(bundle: charts.Bundle, *, now: dt.datetime | None = None, standalone: bool = True) -> bytes:
    built = (now or dt.datetime.now(dt.timezone.utc)).astimezone(WIB)
    commit = data_commit()
    parts: list[str] = []
    parts.append("<title>Indonesia Indicators</title>")
    parts.append(f"<style>{_css()}</style>")
    parts.append(f"<script>{plotlyjs()}</script>")
    parts.append('<div class="wrap">')
    meta = f"Built {built:%d %b %Y %H:%M} WIB"
    if commit:
        meta += f" · data commit {commit}"
    meta += f" · {bundle.fingerprint.files} data files, last changed {bundle.fingerprint.newest.astimezone(WIB):%d %b %Y}"
    parts.append(f'<header class="top"><h1>Indonesia Indicators</h1><p class="meta">{html.escape(meta)}</p></header>')

    toc = ['<a href="#overview">Overview</a>']
    for section in catalogue.SECTIONS[1:]:
        datasets = catalogue.datasets_in(section)
        if not datasets:
            continue
        toc.append(f'<span class="sec">{html.escape(section)}</span>')
        toc.extend(f'<a href="#{d.key}">{html.escape(d.short)}</a>' for d in datasets)
    parts.append(f'<nav class="toc">{"".join(toc)}</nav>')

    parts.append('<section class="dataset" id="overview"><h2>Freshness</h2>')
    parts.append(
        '<p class="source">Fresh: within the dataset\'s normal publication lag. Late: past it. '
        "Stale: more than twice past it, or the source has stopped publishing. Manual: no schedule, updated by hand.</p>"
    )
    parts.append(_freshness_html(bundle, built.date()))
    parts.append("</section>")

    for dataset, chart_list in charts.default_charts(bundle, palette="light"):
        latest = charts.latest_observation(bundle, dataset)
        when = f"latest observation {latest:%d %b %Y}" if latest is not None else "no observations on file"
        parts.append(f'<section class="dataset" id="{dataset.key}">')
        parts.append(
            f'<h2><span class="eyebrow">{html.escape(dataset.section)}</span>{html.escape(dataset.title)}</h2>'
        )
        parts.append(
            f'<p class="source">{html.escape(dataset.publisher)} · {html.escape(dataset.cadence)} · {when} · '
            f'<a href="{html.escape(dataset.source_url)}" rel="noopener">source</a></p>'
        )
        if dataset.notes:
            items = "".join(f"<li>{html.escape(note)}</li>" for note in dataset.notes)
            parts.append(f'<details class="notes"><summary>About this data</summary><ul>{items}</ul></details>')
        described = definitions.for_dataset(dataset.key)
        if described:
            body = "".join(_definition_html((), definition) for definition in described)
            parts.append(f'<details class="notes"><summary>Official description</summary>{body}</details>')
        heading_shown = ""
        for chart in chart_list:
            if chart.heading and chart.heading != heading_shown:
                parts.append(f'<h3 class="subhead">{html.escape(chart.heading)}</h3>')
                heading_shown = chart.heading
            figure_html = pio.to_html(
                chart.figure, include_plotlyjs=False, full_html=False, config=PLOTLY_CONFIG, div_id=f"fig-{dataset.key}-{_slug(chart.key)}"
            )
            parts.append('<div class="chart">')
            parts.append(f"<h3>{html.escape(chart.title)}</h3>")
            parts.append(f'<p class="unit">{html.escape(chart.unit)}</p>')
            parts.append(figure_html)
            if isinstance(chart, charts.Panel):
                parts.append(_plain_table_html(chart.table))
            else:
                parts.append(_latest_table_html(chart.table, chart.unit))
            if chart.note:
                parts.append(f'<p class="note">{html.escape(chart.note)}</p>')
            group = next((candidate for candidate in dataset.groups if candidate.key == chart.key), None)
            if group is not None:
                parts.append(_definitions_html(dataset, group))
            parts.append("</div>")
        parts.append("</section>")

    parts.append(
        "<footer>Series ids and files are those the collectors write under Dataset/. "
        "Discontinued consumer-survey series are omitted from this export; the Streamlit app shows them.</footer>"
    )
    parts.append("</div>")
    body = "\n".join(parts)
    if not standalone:
        return body.encode("utf-8")
    document = (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        f"{body}\n</head>\n<body></body>\n</html>\n"
    )
    # <title>, <style> and the library belong in <head>; the content in <body>.
    head_end = document.index('<div class="wrap">')
    head, rest = document[:head_end], document[head_end:]
    rest = rest.replace("\n</head>\n<body></body>\n</html>\n", "")
    return (head + "</head>\n<body>\n" + rest + "\n</body>\n</html>\n").encode("utf-8")


def _slug(text: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in text).strip("-").lower()
