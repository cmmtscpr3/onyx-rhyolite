"""The buckets: which series belong to which dataset, and how to label them.

One entry per dataset.  Adding a new dataset to the tracker is one ``Dataset``
here plus, for anything that is not a long series CSV, a loader in ``data.py``
and a page in ``pages/``.

Series ids are the ones the collectors write; labels are what the reader sees.
A group is one chart: series that share a unit, in the order their colours
are assigned.  That order is fixed so that deselecting a series never repaints
the others.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Group:
    """One chart: series of one unit, in fixed colour order."""

    key: str
    title: str
    unit: str
    series: tuple[str, ...]
    labels: dict[str, str] = field(default_factory=dict)
    #: The series shown before the reader touches the multiselect.  Empty
    #: means all of them.
    default: tuple[str, ...] = ()
    #: A sub-heading the page groups charts under (e.g. "E-money").
    heading: str = ""
    note: str = ""
    #: Draw markers as well as lines -- for quarterly or irregular series,
    #: where a bare line hides how few observations there are.
    markers: bool = False

    def label(self, series_id: str) -> str:
        return self.labels.get(series_id, series_id)

    @property
    def shown(self) -> tuple[str, ...]:
        return self.default or self.series


@dataclass(frozen=True)
class Annotation:
    """A dated note drawn on every chart of a dataset (a series break)."""

    date: str
    text: str


@dataclass(frozen=True)
class Dataset:
    """One page of the tracker."""

    key: str
    title: str
    short: str
    publisher: str
    section: str
    source_url: str
    cadence: str
    #: The file stems under ``Dataset/Consumption`` this page draws on, or
    #: the folder names for the two datasets that are not long CSVs.
    sources: tuple[str, ...]
    collector: str
    #: Days after the latest observation at which the dataset counts as
    #: late; twice that is stale.  ``None`` for datasets with no schedule.
    late_after_days: int | None
    notes: tuple[str, ...] = ()
    groups: tuple[Group, ...] = ()
    annotations: tuple[Annotation, ...] = ()
    #: A status the freshness table shows regardless of dates.
    forced_status: str = ""

    @property
    def headings(self) -> list[str]:
        seen: list[str] = []
        for group in self.groups:
            if group.heading not in seen:
                seen.append(group.heading)
        return seen


SECTIONS: tuple[str, ...] = ("Overview", "Food prices", "Bank Indonesia", "OJK", "Other sources")

NATIONAL_NOTE = "National figures only; the collectors store no regional breakdown."

# ---------------------------------------------------------------------------
# Bank Indonesia -- SPIP (payment system statistics)

EMONEY = (
    Group(
        key="emoney_value",
        heading="E-money",
        title="Transaction value",
        unit="IDR billion",
        series=("bi_emoney.value", "bi_emoney.value_purchase", "bi_emoney.value_topup"),
        labels={
            "bi_emoney.value": "All transactions",
            "bi_emoney.value_purchase": "Purchases",
            "bi_emoney.value_topup": "Top-ups",
        },
        note="Purchases and top-ups do not add up to the total; the remainder (about a fifth) is transfers and other transaction types BI does not break out here.",
    ),
    Group(
        key="emoney_volume",
        heading="E-money",
        title="Transaction volume",
        unit="thousand transactions",
        series=("bi_emoney.volume", "bi_emoney.volume_purchase", "bi_emoney.volume_topup"),
        labels={
            "bi_emoney.volume": "All transactions",
            "bi_emoney.volume_purchase": "Purchases",
            "bi_emoney.volume_topup": "Top-ups",
        },
    ),
    Group(
        key="emoney_instruments",
        heading="E-money",
        title="Instruments outstanding",
        unit="million units",
        series=("bi_emoney.instruments", "bi_emoney.instruments_chip", "bi_emoney.instruments_server"),
        labels={
            "bi_emoney.instruments": "All instruments",
            "bi_emoney.instruments_chip": "Chip-based",
            "bi_emoney.instruments_server": "Server-based",
        },
    ),
    Group(
        key="emoney_float",
        heading="E-money",
        title="Float funds",
        unit="IDR billion",
        series=("bi_emoney.float_funds", "bi_emoney.float_funds_bank", "bi_emoney.float_funds_nonbank"),
        labels={
            "bi_emoney.float_funds": "All issuers",
            "bi_emoney.float_funds_bank": "Bank issuers",
            "bi_emoney.float_funds_nonbank": "Non-bank issuers",
        },
    ),
    Group(
        key="emoney_outstanding",
        heading="E-money",
        title="Instruments issued by non-banks (SPIP table 2)",
        unit="million instruments",
        series=("bi_payment_system.emoney_instruments_outstanding",),
        labels={"bi_payment_system.emoney_instruments_outstanding": "E-money instruments issued by non-banks (table 2)"},
        note="SPIP table 2's row is 'Instrumen Uang Elektronik yang Diterbitkan oleh Lembaga Selain Bank': instruments issued by non-bank institutions only, which is why it runs below the all-issuer count of table 5e.",
    ),
)

CARDS = (
    Group(
        key="cards_value",
        heading="Cards",
        title="Transaction value",
        unit="IDR billion",
        series=("bi_card_transactions.atm_debit.value", "bi_card_transactions.credit.value"),
        labels={
            "bi_card_transactions.atm_debit.value": "ATM and debit cards",
            "bi_card_transactions.credit.value": "Credit cards",
        },
    ),
    Group(
        key="cards_volume",
        heading="Cards",
        title="Transaction volume",
        unit="thousand transactions",
        series=("bi_card_transactions.atm_debit.volume", "bi_card_transactions.credit.volume"),
        labels={
            "bi_card_transactions.atm_debit.volume": "ATM and debit cards",
            "bi_card_transactions.credit.volume": "Credit cards",
        },
    ),
    Group(
        key="cards_outstanding",
        heading="Cards",
        title="Cards outstanding",
        unit="million units",
        series=("bi_card_transactions.atm_debit.cards", "bi_card_transactions.credit.cards"),
        labels={
            "bi_card_transactions.atm_debit.cards": "ATM and debit cards",
            "bi_card_transactions.credit.cards": "Credit cards",
        },
    ),
)

PAYMENT_SYSTEM = (
    Group(
        key="money",
        heading="Currency and BI-RTGS",
        title="Currency and narrow money",
        unit="IDR billion",
        series=(
            "bi_payment_system.currency_in_circulation",
            "bi_payment_system.narrow_money",
            "bi_payment_system.demand_deposits_rupiah",
        ),
        labels={
            "bi_payment_system.currency_in_circulation": "Currency in circulation",
            "bi_payment_system.narrow_money": "Narrow money (M1)",
            "bi_payment_system.demand_deposits_rupiah": "Rupiah demand deposits",
        },
        note="M1 is not the sum of the other two lines: since November 2021 BI counts rupiah savings deposits withdrawable at any time in M1 (backdated to January 2011), and the table does not list them.",
    ),
    Group(
        key="rtgs_value",
        heading="Currency and BI-RTGS",
        title="BI-RTGS settlement value",
        unit="IDR billion",
        series=("bi_payment_system.rtgs.value",),
        labels={"bi_payment_system.rtgs.value": "RTGS value"},
    ),
    Group(
        key="rtgs_volume",
        heading="Currency and BI-RTGS",
        title="BI-RTGS settlement volume",
        unit="thousand transactions",
        series=("bi_payment_system.rtgs.volume",),
        labels={"bi_payment_system.rtgs.volume": "RTGS volume"},
    ),
    Group(
        key="cash_intensity",
        heading="Currency and BI-RTGS",
        title="Cash intensity (quarterly)",
        unit="percent",
        series=(
            "bi_payment_system.currency_to_gdp",
            "bi_payment_system.currency_to_household_consumption",
        ),
        labels={
            "bi_payment_system.currency_to_gdp": "Currency to GDP",
            "bi_payment_system.currency_to_household_consumption": "Currency to household consumption",
        },
        markers=True,
        note="Quarterly ratios, dated to the quarter's final month.",
    ),
)

# ---------------------------------------------------------------------------
# Bank Indonesia -- SEKI

GDP_LABELS = {
    "gdp": "GDP",
    "total_consumption": "Total consumption",
    "household_consumption": "Household consumption",
    "npish_consumption": "NPISH consumption",
    "government_consumption": "Government consumption",
    "gfcf": "Gross fixed capital formation",
}

SEKI = (
    Group(
        key="gdp_current",
        heading="National accounts: GDP by expenditure",
        title="Current prices",
        unit="IDR billion",
        series=tuple(f"bi_seki.gdp_expenditure_current.{k}" for k in GDP_LABELS),
        labels={f"bi_seki.gdp_expenditure_current.{k}": v for k, v in GDP_LABELS.items()},
        default=(
            "bi_seki.gdp_expenditure_current.household_consumption",
            "bi_seki.gdp_expenditure_current.gdp",
        ),
        markers=True,
        note="BPS quarterly national accounts as republished in SEKI tables VII.3 and VII.4; quarters are dated to their first month.",
    ),
    Group(
        key="gdp_constant",
        heading="National accounts: GDP by expenditure",
        title="Constant prices",
        unit="IDR billion",
        series=tuple(
            f"bi_seki.gdp_expenditure_constant.{k}"
            for k in ("gdp", "total_consumption", "household_consumption", "government_consumption")
        ),
        labels={
            f"bi_seki.gdp_expenditure_constant.{k}": GDP_LABELS[k]
            for k in ("gdp", "total_consumption", "household_consumption", "government_consumption")
        },
        default=(
            "bi_seki.gdp_expenditure_constant.household_consumption",
            "bi_seki.gdp_expenditure_constant.gdp",
        ),
        markers=True,
    ),
    Group(
        key="deposits",
        heading="Bank deposits by owner group",
        title="Deposits by owner",
        unit="IDR billion",
        series=(
            "bi_seki.deposits_by_owner.households",
            "bi_seki.deposits_by_owner.private_nonfinancial_business",
            "bi_seki.deposits_by_owner.state_nonfinancial_business",
            "bi_seki.deposits_by_owner.other_financial_institutions",
            "bi_seki.deposits_by_owner.local_government",
            "bi_seki.deposits_by_owner.cooperatives",
            "bi_seki.deposits_by_owner.foundations_and_social_bodies",
            "bi_seki.deposits_by_owner.other_private_sector",
            "bi_seki.deposits_by_owner.total",
        ),
        labels={
            "bi_seki.deposits_by_owner.households": "Households (perseorangan)",
            "bi_seki.deposits_by_owner.private_nonfinancial_business": "Private non-financial business",
            "bi_seki.deposits_by_owner.state_nonfinancial_business": "State non-financial business",
            "bi_seki.deposits_by_owner.other_financial_institutions": "Other financial institutions",
            "bi_seki.deposits_by_owner.local_government": "Local government",
            "bi_seki.deposits_by_owner.cooperatives": "Cooperatives",
            "bi_seki.deposits_by_owner.foundations_and_social_bodies": "Foundations and social bodies",
            "bi_seki.deposits_by_owner.other_private_sector": "Other private sector (includes households)",
            "bi_seki.deposits_by_owner.total": "All owners",
        },
        default=(
            "bi_seki.deposits_by_owner.households",
            "bi_seki.deposits_by_owner.private_nonfinancial_business",
            "bi_seki.deposits_by_owner.state_nonfinancial_business",
        ),
        note="Households, cooperatives and foundations are sub-groups of 'other private sector', so those lines must not be added together. Monthly from January 2025 (SEKI table I.18).",
    ),
)

# ---------------------------------------------------------------------------
# Bank Indonesia -- Survei Konsumen

EXPENDITURE_GROUPS = {
    "": "All respondents",
    "rp1_2juta": "Rp 1-2 mn a month",
    "rp2_3juta": "Rp 2.1-3 mn a month",
    "rp3_4juta": "Rp 3.1-4 mn a month",
    "rp4_5juta": "Rp 4.1-5 mn a month",
    "above_rp5juta": "Above Rp 5 mn a month",
}


def _by_expenditure_group(prefix: str) -> tuple[tuple[str, ...], dict[str, str]]:
    """The all-respondent series plus one per monthly household expenditure bracket."""
    ids = tuple(f"{prefix}.{suffix}" if suffix else prefix for suffix in EXPENDITURE_GROUPS)
    labels = {sid: label for sid, label in zip(ids, EXPENDITURE_GROUPS.values())}
    return ids, labels


_SHARE_CONS, _SHARE_CONS_L = _by_expenditure_group("bi_consumer_survey.expenditure_share.consumption")
_SHARE_LOAN, _SHARE_LOAN_L = _by_expenditure_group("bi_consumer_survey.expenditure_share.loan_instalment")
_SHARE_SAVE, _SHARE_SAVE_L = _by_expenditure_group("bi_consumer_survey.expenditure_share.saving")
_EXP_SAVE, _EXP_SAVE_L = _by_expenditure_group("bi_consumer_survey.expectation.saving_6m")
_EXP_DEBT, _EXP_DEBT_L = _by_expenditure_group("bi_consumer_survey.expectation.debt_position_6m")
_EXP_SPEND, _EXP_SPEND_L = _by_expenditure_group("bi_consumer_survey.expectation.consumption_spend_3m")

CONSUMER_SURVEY = (
    Group(
        key="confidence",
        heading="Confidence indices",
        title="Consumer confidence and its components",
        unit="index",
        series=(
            "bi_consumer_survey.ikk",
            "bi_consumer_survey.ike",
            "bi_consumer_survey.iek",
            "bi_consumer_survey.ipsi",
            "bi_consumer_survey.iklk",
            "bi_consumer_survey.durable_goods_purchase",
            "bi_consumer_survey.iep",
            "bi_consumer_survey.ieklk",
            "bi_consumer_survey.ieku",
        ),
        labels={
            "bi_consumer_survey.ikk": "Consumer Confidence Index (IKK)",
            "bi_consumer_survey.ike": "Current economic conditions (IKE)",
            "bi_consumer_survey.iek": "Consumer expectations (IEK)",
            "bi_consumer_survey.ipsi": "Current income (IPSI)",
            "bi_consumer_survey.iklk": "Job availability (IKLK)",
            "bi_consumer_survey.durable_goods_purchase": "Durable goods purchases (IPDG)",
            "bi_consumer_survey.iep": "Income expectations (IEP)",
            "bi_consumer_survey.ieklk": "Job availability expectations (IEKLK)",
            "bi_consumer_survey.ieku": "Business activity expectations (IEKU)",
        },
        default=("bi_consumer_survey.ikk", "bi_consumer_survey.ike", "bi_consumer_survey.iek"),
        note="Diffusion indices: 100 is neutral, above 100 optimistic. IKK is the average of IKE and IEK; each of those averages three components.",
    ),
    Group(
        key="share_consumption",
        heading="Household budget shares by monthly expenditure group",
        title="Share of income spent on consumption",
        unit="percent",
        series=_SHARE_CONS,
        labels=_SHARE_CONS_L,
    ),
    Group(
        key="share_loan_instalment",
        heading="Household budget shares by monthly expenditure group",
        title="Share of income going to loan instalments",
        unit="percent",
        series=_SHARE_LOAN,
        labels=_SHARE_LOAN_L,
    ),
    Group(
        key="share_saving",
        heading="Household budget shares by monthly expenditure group",
        title="Share of income saved",
        unit="percent",
        series=_SHARE_SAVE,
        labels=_SHARE_SAVE_L,
    ),
    Group(
        key="expectation_saving",
        heading="Discontinued series",
        title="Expected savings in six months",
        unit="index",
        series=_EXP_SAVE,
        labels=_EXP_SAVE_L,
        note="Last published for March 2020.",
    ),
    Group(
        key="expectation_debt",
        heading="Discontinued series",
        title="Expected debt position in six months",
        unit="index",
        series=_EXP_DEBT,
        labels=_EXP_DEBT_L,
        note="Last published for March 2020.",
    ),
    Group(
        key="expectation_spend",
        heading="Discontinued series",
        title="Expected consumption spending in three months",
        unit="index",
        series=_EXP_SPEND,
        labels=_EXP_SPEND_L,
        note="Last published for March 2020.",
    ),
    Group(
        key="price_expectations",
        heading="Discontinued series",
        title="Price expectations",
        unit="index",
        series=(
            "bi_consumer_survey.price_expectation_3m",
            "bi_consumer_survey.price_expectation_6m",
            "bi_consumer_survey.price_expectation_12m",
        ),
        labels={
            "bi_consumer_survey.price_expectation_3m": "Prices in 3 months",
            "bi_consumer_survey.price_expectation_6m": "Prices in 6 months",
            "bi_consumer_survey.price_expectation_12m": "Prices in 12 months",
        },
        note="Last published for December 2019 (3 and 6 months) and March 2020 (12 months).",
    ),
)

# ---------------------------------------------------------------------------
# OJK, ASPI, Magpie IQ

OJK = (
    Group(
        key="dpk",
        title="Third-party funds by deposit type",
        unit="IDR billion",
        series=(
            "ojk_dpk.composition.giro",
            "ojk_dpk.composition.tabungan",
            "ojk_dpk.composition.simpanan_berjangka",
            "ojk_dpk.composition.total",
        ),
        labels={
            "ojk_dpk.composition.giro": "Demand deposits (giro)",
            "ojk_dpk.composition.tabungan": "Savings deposits (tabungan)",
            "ojk_dpk.composition.simpanan_berjangka": "Time deposits (simpanan berjangka)",
            "ojk_dpk.composition.total": "All third-party funds",
        },
        markers=True,
    ),
)

QRIS = (
    Group(
        key="qris_value",
        title="Transaction value",
        unit="IDR trillion",
        series=("qris_transactions.value.total", "qris_transactions.value.off_us"),
        labels={
            "qris_transactions.value.total": "All QRIS transactions",
            "qris_transactions.value.off_us": "Off-us (payer and merchant at different providers)",
        },
        markers=True,
    ),
    Group(
        key="qris_volume",
        title="Transaction volume",
        unit="million transactions",
        series=("qris_transactions.volume.total", "qris_transactions.volume.off_us"),
        labels={
            "qris_transactions.volume.total": "All QRIS transactions",
            "qris_transactions.volume.off_us": "Off-us (payer and merchant at different providers)",
        },
        markers=True,
    ),
)

ECOMMERCE = (
    Group(
        key="gmv",
        title="Gross merchandise value by platform",
        unit="USD million",
        series=(
            "ecommerce_gmv.shopee",
            "ecommerce_gmv.tiktok_shop",
            "ecommerce_gmv.tokopedia",
            "ecommerce_gmv.total_market",
        ),
        labels={
            "ecommerce_gmv.shopee": "Shopee",
            "ecommerce_gmv.tiktok_shop": "TikTok Shop",
            "ecommerce_gmv.tokopedia": "Tokopedia",
            "ecommerce_gmv.total_market": "Total market (all platforms)",
        },
    ),
)

# ---------------------------------------------------------------------------
# The datasets, in sidebar order

DATASETS: tuple[Dataset, ...] = (
    Dataset(
        key="pihps",
        title="PIHPS: weekly food prices",
        short="PIHPS",
        publisher="Bank Indonesia (Pusat Informasi Harga Pangan Strategis)",
        section="Food prices",
        source_url="https://www.bi.go.id/hargapangan",
        cadence="weekly",
        sources=("Food Prices/PIHPS",),
        collector="pihps",
        late_after_days=21,
        notes=(
            "Weekly national average prices for 31 commodities (10 groups, 21 varieties) at three market levels: traditional markets, modern markets and wholesalers.",
            "Prices are rupiah per kilogram, or per litre for cooking oil, as PIHPS publishes them. Group rows are the average of their varieties.",
            NATIONAL_NOTE,
        ),
    ),
    Dataset(
        key="spip",
        title="SPIP: payment system statistics",
        short="BI SPIP",
        publisher="Bank Indonesia (Statistik Sistem Pembayaran dan Infrastruktur Pasar Keuangan)",
        section="Bank Indonesia",
        source_url="https://www.bi.go.id/id/statistik/ekonomi-keuangan/spip/",
        cadence="monthly",
        sources=("bi_emoney", "bi_card_transactions", "bi_payment_system"),
        collector="bi_spip",
        late_after_days=95,
        notes=(
            "Monthly, published with a lag of one to two months. E-money is SPIP table 5e (plus the instrument count of table 2), cards tables 5a and 5c, currency and BI-RTGS tables 1 and 2.",
            "BI revises recent months; the collectors overwrite revised values, so the latest months can move between runs.",
        ),
        groups=EMONEY + CARDS + PAYMENT_SYSTEM,
    ),
    Dataset(
        key="seki",
        title="SEKI: economic and financial statistics",
        short="BI SEKI",
        publisher="Bank Indonesia (Statistik Ekonomi dan Keuangan Indonesia)",
        section="Bank Indonesia",
        source_url="https://www.bi.go.id/id/statistik/ekonomi-keuangan/seki/",
        cadence="monthly and quarterly",
        sources=("bi_seki",),
        collector="bi_seki",
        late_after_days=95,
        notes=(
            "GDP by expenditure is BPS's quarterly national accounts republished by BI (tables VII.3 and VII.4), so it is the official series, not an independent one.",
            "Deposits by owner group (table I.18) start in January 2025.",
        ),
        groups=SEKI,
    ),
    Dataset(
        key="consumer_survey",
        title="Survei Konsumen: consumer survey",
        short="BI Survei Konsumen",
        publisher="Bank Indonesia",
        section="Bank Indonesia",
        source_url="https://www.bi.go.id/id/publikasi/laporan/Pages/Survei-Konsumen.aspx",
        cadence="monthly",
        sources=("bi_consumer_survey",),
        collector="bi_consumer_survey",
        late_after_days=60,
        notes=(
            "About 4,600 households in 18 cities; urban only, so rural and informal households are under-represented.",
            "Budget shares are what respondents report doing with their income; the confidence indices are what they expect.",
        ),
        groups=CONSUMER_SURVEY,
    ),
    Dataset(
        key="ojk",
        title="SPI: third-party funds (DPK)",
        short="OJK SPI",
        publisher="Otoritas Jasa Keuangan (Statistik Perbankan Indonesia)",
        section="OJK",
        source_url="https://www.ojk.go.id/id/kanal/perbankan/data-dan-statistik/statistik-perbankan-indonesia/",
        cadence="monthly (irregular on file)",
        sources=("ojk_dpk",),
        collector="ojk_dpk",
        late_after_days=95,
        forced_status="stale",
        notes=(
            "From the July 2025 data period OJK publishes SPI only through its Portal Data (data.ojk.go.id/SJKPublic); the PDF and Excel releases the collector reads end with June 2025, and it picks new ones up automatically if they reappear.",
            "Only nine release months are on file, so the lines join observations that are months apart.",
            "For a current reading of deposits by owner, use the SEKI page.",
        ),
        groups=OJK,
    ),
    Dataset(
        key="qris",
        title="QRIS transactions",
        short="ASPI QRIS",
        publisher="Asosiasi Sistem Pembayaran Indonesia",
        section="Other sources",
        source_url="https://aspi-indonesia.or.id/statistik-qris/",
        cadence="quarterly",
        sources=("qris_transactions",),
        collector="qris",
        late_after_days=None,
        forced_status="manual",
        notes=(
            "Transcribed by hand from a published QRIS chart: 13 quarters from 2023 Q1 to 2026 Q1, each dated to the quarter's final month. There is no scraper behind it, so it only extends when the next chart is transcribed.",
            "ASPI blocks datacentre addresses, and BI publishes no QRIS table, so no automated source exists yet.",
        ),
        groups=QRIS,
    ),
    Dataset(
        key="ecommerce",
        title="E-commerce GMV",
        short="Magpie IQ",
        publisher="Magpie IQ (vendor estimates)",
        section="Other sources",
        source_url="https://magpieiq.com/data/shopee-gmv-trend-indonesia-2026/",
        cadence="monthly",
        sources=("ecommerce_gmv",),
        collector="magpieiq",
        late_after_days=95,
        notes=(
            "One vendor's estimates from SKU-level tracking, read off the published chart to about USD 0.4 million; not reported platform figures.",
            "The total-market series rebases in April 2025: the share it attributes to platforms other than the three shown jumps from about 10% to about 30% in one month. Compare it across that date with care.",
            "Magpie IQ's terms mark the data as not free to republish; check them before sharing this page outside the project.",
        ),
        groups=ECOMMERCE,
        annotations=(Annotation("2025-04-01", "Total market rebased"),),
    ),
    Dataset(
        key="ibid",
        title="ibid vehicle auctions",
        short="ibid",
        publisher="ibid (Astra) auction listings",
        section="Other sources",
        source_url="https://www.ibid.astra.co.id/cari-lelang/mobil-bekas",
        cadence="on demand",
        sources=("ibid_car_data", "ibid_motor_data"),
        collector="ibid",
        late_after_days=None,
        forced_status="manual",
        notes=(
            "Every lot the scraper has seen, cars and motorcycles, with the price shown on its card. That is the listed price, not a confirmed hammer price.",
            "Rows are lots, not vehicles: about a third of plates appear in more than one lot (relisted after an auction), usually at the same price.",
            "Two scrapes so far (17 August and 15 September 2026) covering auctions from mid July 2026. The scrape is opt-in and slow, so it runs by hand.",
        ),
    ),
)

BY_KEY: dict[str, Dataset] = {dataset.key: dataset for dataset in DATASETS}


def datasets_in(section: str) -> list[Dataset]:
    return [dataset for dataset in DATASETS if dataset.section == section]


def group(dataset_key: str, group_key: str) -> Group:
    for candidate in BY_KEY[dataset_key].groups:
        if candidate.key == group_key:
            return candidate
    raise KeyError(f"{dataset_key} has no group {group_key!r}")
