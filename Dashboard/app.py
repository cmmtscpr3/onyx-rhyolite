"""Indonesia Indicators tracker -- Streamlit entrypoint.

    streamlit run Dashboard/app.py

Pages are bucketed by publisher and dataset; see ``dashboard/catalogue.py``.
"""

from __future__ import annotations

import contextlib
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="Indonesia Indicators", page_icon="📈", layout="wide")

#: The repository's own packages.  Streamlit Community Cloud pulls each new
#: commit into the running app without restarting it: the datasets are read
#: afresh, since their cache is keyed on the files, but Python keeps every
#: module it has already imported -- so new data turned up under old code,
#: which is how a change to the food names stayed invisible behind a fresh
#: week of prices.  This file is re-read on every run, so it checks.
OWN_CODE = {"dashboard": ROOT / "dashboard", "collectors": ROOT.parent / "Collectors" / "collectors"}


@st.cache_resource
def _code_in_memory() -> dict:
    """Process-wide, so it outlives the reruns that re-execute this file."""
    return {"newest": None, "lock": threading.Lock()}


@contextlib.contextmanager
def _current_own_code():
    """Import inside this to get the code on disk, not the code first loaded.

    When any source file is newer than the code in memory, every module of
    both packages is forgotten and imported again, together, so a new page
    never meets an old helper.  Modules loaded but never recorded -- by a copy
    of this file that predates the check -- count as stale.
    """
    newest = max(
        (path.stat().st_mtime for folder in OWN_CODE.values() for path in folder.rglob("*.py")),
        default=0.0,
    )
    state = _code_in_memory()
    with state["lock"]:
        loaded = [name for name in list(sys.modules) if name.split(".")[0] in OWN_CODE]
        if loaded and (state["newest"] is None or state["newest"] < newest):
            for name in loaded:
                sys.modules.pop(name, None)
        yield
        state["newest"] = newest


with _current_own_code():
    from dashboard import ui  # noqa: E402
    from dashboard.pages import consumer_survey, ecommerce, ibid, ojk, overview, pihps, qris, seki, spip  # noqa: E402

PAGES = {
    "Overview": [st.Page(overview.render, title="Overview", icon=":material/home:", default=True)],
    "Inflation": [st.Page(pihps.render, title="PIHPS · Weekly food prices", icon=":material/rice_bowl:", url_path="pihps")],
    "Consumption": [
        st.Page(consumer_survey.render, title="Survei Konsumen · Consumer survey", icon=":material/groups:", url_path="consumer-survey"),
        st.Page(spip.render, title="SPIP · Payment system statistics", icon=":material/credit_card:", url_path="spip"),
        st.Page(seki.render_gdp, title="SEKI - GDP by Expenditure", icon=":material/account_balance:", url_path="seki-gdp"),
        st.Page(seki.render_deposits, title="SEKI - Bank Deposits", icon=":material/account_balance_wallet:", url_path="seki-deposits"),
        st.Page(ojk.render, title="SPI · Third-party funds (DPK)", icon=":material/savings:", url_path="ojk"),
        st.Page(qris.render, title="ASPI · QRIS transactions", icon=":material/qr_code:", url_path="qris"),
        st.Page(ecommerce.render, title="Magpie IQ · E-commerce GMV", icon=":material/shopping_cart:", url_path="ecommerce"),
        st.Page(ibid.render, title="ibid · Vehicle auctions", icon=":material/directions_car:", url_path="ibid"),
    ],
}

ui.sidebar()
st.navigation(PAGES).run()
