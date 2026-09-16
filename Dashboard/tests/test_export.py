"""The offline HTML: one file, every dataset, Plotly inlined once."""

from __future__ import annotations

import datetime as dt

import pytest

from dashboard import catalogue, charts, data, export


@pytest.fixture(scope="session")
def html(series, pihps, lots):
    bundle = charts.Bundle(series=series, pihps=pihps, lots=lots, fingerprint=data.fingerprint())
    return export.build_offline_html(bundle, now=dt.datetime(2026, 9, 16, 3, 0, tzinfo=dt.timezone.utc)).decode("utf-8")


def test_export_has_every_dataset_section_and_one_plotly(html):
    for dataset in catalogue.DATASETS:
        assert f'id="{dataset.key}"' in html, dataset.key
    assert html.count("<title>Indonesia Indicators</title>") == 1
    assert html.count("Plotly.newPlot") >= 20
    assert html.count("plotly.js v") == 1  # the library banner, inlined once
    assert "<!doctype html>" in html[:30]
    assert html.index("</head>") < html.index("<body>") < html.index('<div class="wrap">')
    assert 'src="http' not in html  # nothing fetched from a network


def test_export_size_is_reasonable(html):
    size = len(html.encode("utf-8"))
    assert 3_000_000 < size < 12_000_000, size


def test_export_fragment_has_no_skeleton(series, pihps, lots):
    bundle = charts.Bundle(series=series, pihps=pihps, lots=lots, fingerprint=data.fingerprint())
    fragment = export.build_offline_html(bundle, standalone=False).decode("utf-8")
    assert fragment.startswith("<title>")
    assert "<html" not in fragment and "<body" not in fragment


def test_export_marks_the_sub_headings(html):
    expected = [heading for dataset in catalogue.DATASETS for heading in dataset.headings if heading and heading != "Discontinued series"]
    assert html.count('<h3 class="subhead">') == len(expected)
    for heading in ("E-money", "Cards", "Currency and BI-RTGS", "Confidence indices"):
        assert f'<h3 class="subhead">{heading}</h3>' in html, heading
