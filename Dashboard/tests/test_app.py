"""The Streamlit app itself, run headless through Streamlit's test harness."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["overview", "pihps", "spip", "seki", "consumer_survey", "ojk", "qris", "ecommerce", "ibid"]


def _page_script(page_name, root):
    import sys

    sys.path.insert(0, root)
    import importlib

    module = importlib.import_module(f"dashboard.pages.{page_name}")
    module.render()


def test_entrypoint_runs_without_exceptions():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=300)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert at.title[0].value == "Indonesia Indicators"


@pytest.mark.parametrize("page", PAGES)
def test_each_page_renders(page):
    at = AppTest.from_function(_page_script, kwargs={"page_name": page, "root": str(ROOT)}, default_timeout=300)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert at.title, "every page has a title"
    if page != "overview":
        assert at.dataframe, "every dataset page shows a latest-values table"
