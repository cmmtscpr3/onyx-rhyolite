"""Indonesia Indicators tracker -- Streamlit entrypoint.

    streamlit run Dashboard/app.py

Pages are bucketed by publisher and dataset; see ``dashboard/catalogue.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="Indonesia Indicators", page_icon="📈", layout="wide")

from dashboard import ui  # noqa: E402
from dashboard.pages import consumer_survey, ecommerce, ibid, ojk, overview, pihps, qris, seki, spip  # noqa: E402

PAGES = {
    "Overview": [st.Page(overview.render, title="Overview", icon=":material/home:", default=True)],
    "Inflation": [st.Page(pihps.render, title="PIHPS · Weekly food prices", icon=":material/rice_bowl:", url_path="pihps")]
    "Consumption": [
        st.Page(spip.render, title="SPIP · Payment system statistics", icon=":material/credit_card:", url_path="spip"),
        st.Page(seki.render, title="SEKI · Economic & financial statistics", icon=":material/account_balance:", url_path="seki"),
        st.Page(consumer_survey.render, title="Survei Konsumen · Consumer survey", icon=":material/groups:", url_path="consumer-survey"),
        st.Page(ojk.render, title="SPI · Third-party funds (DPK)", icon=":material/savings:", url_path="ojk"),
        st.Page(qris.render, title="ASPI · QRIS transactions", icon=":material/qr_code:", url_path="qris"),
        st.Page(ecommerce.render, title="Magpie IQ · E-commerce GMV", icon=":material/shopping_cart:", url_path="ecommerce"),
        st.Page(ibid.render, title="ibid · Vehicle auctions", icon=":material/directions_car:", url_path="ibid"),
    ],
}

ui.sidebar()
st.navigation(PAGES).run()
