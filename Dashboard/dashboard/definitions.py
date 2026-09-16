"""Official definitions, quoted verbatim from the publishers.

Nothing here is paraphrased.  Each entry is the sentence or sentences the
publisher itself uses, in the language it publishes them in, with the
document they come from; where the publisher also issues an English text,
that is quoted too.  A series with no entry is listed on its chart as having
no official definition rather than being given one of our own.

Three registries, each optional per item:

* :data:`SERIES` -- by series id: what one line on a chart measures.  Several
  series can share one entry (every e-money series shares Bank Indonesia's
  definition of Uang Elektronik).
* :data:`GROUPS` -- by ``(dataset key, group key)``: the concept a whole chart
  measures, shown before the per-series entries.
* :data:`DATASETS` -- by dataset key: the publisher's own description of the
  publication, shown in the page header.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from .catalogue import Dataset, Group


@dataclass(frozen=True)
class Definition:
    """One verbatim quote and where it comes from."""

    #: The term as the publisher names it (e.g. "Uang Elektronik").
    term: str
    #: The publisher's own words, unchanged.
    text: str
    #: The document the quote is taken from, as its title reads.
    source: str
    url: str
    #: The publisher's own English wording, when it issues one; never ours.
    english: str = ""
    #: The document the English wording comes from, when it is a separate one.
    english_source: str = ""
    english_url: str = ""
    #: A factual pointer from the term to the table row, never a definition of our own.
    note: str = ""


@dataclass(frozen=True)
class Entry:
    """A definition as it appears under a chart, with the labels of the series it covers."""

    labels: tuple[str, ...]
    definition: Definition


SERIES: dict[str, tuple[Definition, ...]] = {}
GROUPS: dict[tuple[str, str], tuple[Definition, ...]] = {}
DATASETS: dict[str, tuple[Definition, ...]] = {}


def populated(dataset: Dataset) -> bool:
    """Whether the dataset has any entry at all.  A dataset with none has not
    been researched yet, which is not the same as its publisher defining
    nothing, so its page says nothing rather than "not found"."""
    if dataset.key in DATASETS:
        return True
    if any(key == dataset.key for key, _ in GROUPS):
        return True
    return any(series_id in SERIES for group in dataset.groups for series_id in group.series)


def for_dataset(dataset_key: str) -> tuple[Definition, ...]:
    return DATASETS.get(dataset_key, ())


def for_group(dataset_key: str, group: Group) -> list[Entry]:
    """The chart's definitions: the group's own first, then each distinct series
    definition once, with the labels of every series that shares it, in series order."""
    entries = [Entry((), definition) for definition in GROUPS.get((dataset_key, group.key), ())]
    shared: dict[Definition, list[str]] = {}
    for series_id in group.series:
        for definition in SERIES.get(series_id, ()):
            shared.setdefault(definition, []).append(group.label(series_id))
    entries.extend(Entry(tuple(labels), definition) for definition, labels in shared.items())
    return entries


def undefined(group: Group) -> list[str]:
    """Labels of the group's series that have no entry of their own."""
    return [group.label(series_id) for series_id in group.series if series_id not in SERIES]


def all_definitions() -> Iterator[Definition]:
    for registry in (SERIES, GROUPS, DATASETS):
        for definitions in registry.values():
            yield from definitions


# ---------------------------------------------------------------------------
# Bank Indonesia -- Survei Konsumen

_SK_METADATA = "Metadata: Indeks Keyakinan Konsumen (IKK), Bank Indonesia, 2026"
_SK_METADATA_URL = "https://www.bi.go.id/id/statistik/Metadata/Survei/Documents/1-Metadata-SK-2026.pdf"
_SK_METADATA_EN = "Metadata: Consumer Confidence Index (Consumer Survey), Bank Indonesia, March 2016"
_SK_METADATA_EN_URL = "https://www.bi.go.id/en/statistik/Metadata/Survei/Documents/1-Metadata-Consumer-Survey-2016.pdf"
_SK_REPORT = "Survei Konsumen, Agustus 2026 (Bank Indonesia)"
_SK_REPORT_URL = "https://www.bi.go.id/id/publikasi/laporan/Documents/SK-Agustus-2026.pdf"
_SK_REPORT_EN = "Consumer Survey, August 2026 (Bank Indonesia, English edition)"
_SK_REPORT_EN_URL = "https://www.bi.go.id/en/publikasi/laporan/Documents/Consumer-Expectation-Survey-August-2026.pdf"
_SK_REPORT_2019 = "Survei Konsumen, Desember 2019 (Bank Indonesia)"
_SK_REPORT_2019_URL = "https://www.bi.go.id/id/publikasi/laporan/Documents/SK%20Desember%202019.pdf"

SK_SURVEY = Definition(
    term="Survei Konsumen / Consumer Survey",
    text=(
        "Survei Konsumen merupakan survei bulanan yang bertujuan untuk mengetahui keyakinan konsumen "
        "mengenai kondisi ekonomi saat ini dan ekspektasi terhadap kondisi perekonomian pada 6 bulan mendatang."
    ),
    source="Bank Indonesia, Publikasi: Laporan Survei Konsumen",
    url="https://www.bi.go.id/id/publikasi/laporan/Default.aspx?id=survei-konsumen",
    english=(
        "The monthly Consumer Survey collects information on consumer confidence concerning current economic "
        "conditions based on consumption level and consumer expectations of economic conditions in the upcoming six months."
    ),
    english_source="Bank Indonesia, Publications: Consumer Survey",
    english_url="https://www.bi.go.id/en/publikasi/laporan/Default.aspx?id=survei-konsumen",
)

SK_METHOD = Definition(
    term="Metodologi / Methodology",
    text=(
        "Survei Konsumen merupakan survei bulanan yang dilaksanakan sejak Oktober 1999. Sejak Januari 2007, survei "
        "dilaksanakan terhadap kurang lebih 4.600 rumah tangga sebagai responden (stratified random sampling) di 18 kota: "
        "Jakarta, Bandung, Bodebek, Semarang, Surabaya, Medan, Makassar, Bandar Lampung, Palembang, Banjarmasin, Padang, "
        "Pontianak, Samarinda, Manado, Denpasar, Mataram, Pangkal Pinang, Ambon, dan Banten. Indeks per kota dihitung "
        "dengan metode balance score (net balance + 100) yang menunjukkan bahwa jika indeks di atas 100 berarti optimis "
        "dan di bawah 100 berarti pesimis."
    ),
    source=_SK_REPORT,
    url=_SK_REPORT_URL,
    english=(
        "The Consumer Survey has been conducted monthly since October 1999. Moreover, since January 2007, the survey has "
        "involved 4,600 households (stratified random sampling) in 18 cities, namely Jakarta, Bandung, Bodebek, Semarang, "
        "Surabaya, Medan, Makassar, Bandar Lampung, Palembang, Banjarmasin, Padang, Pontianak, Samarinda, Manado, Denpasar, "
        "Mataram, Pangkal Pinang, Ambon and Banten. The index per city is calculated using the balanced score method "
        "(net balance + 100) which indicates that a score of above 100 is considered optimistic and index of below 100 is pessimistic."
    ),
    english_source=_SK_REPORT_EN,
    english_url=_SK_REPORT_EN_URL,
)

SK_COVERAGE = Definition(
    term="Konsep, Definisi dan Cakupan Data (Survei Konsumen)",
    text=(
        "Survei Konsumen dilakukan terhadap sekitar 4.600 rumah tangga dengan tingkat pengeluaran rumah tangga minimal "
        "Rp1 juta per bulan yang dipilih secara acak (stratified random sampling) di 18 kota. Pertanyaan dalam kuesioner "
        "survei antara lain meliputi pertanyaan demografi mengenai karakteristik responden, pertanyaan inti, serta "
        "pertanyaan mengenai proporsi penggunaan penghasilan."
    ),
    source=_SK_METADATA,
    url=_SK_METADATA_URL,
)

SK_BALANCE_SCORE = Definition(
    term="Indeks saldo bersih / Balance score method",
    text=(
        "Menghitung masing-masing indeks komponen penyusun IKK dengan menggunakan metode indeks saldo bersih. Saldo bersih "
        "yaitu selisih antara persentase responden yang menjawab meningkat dengan persentase responden yang menjawab "
        "menurun. Indeks saldo bersih adalah angka saldo bersih ditambah 100.\n\n"
        "Angka indeks lebih dari 100 mengindikasikan respon optimis lebih banyak dibandingkan respon pesimis. Sebaliknya, "
        "angka indeks lebih kecil dari 100 mengindikasikan respon pesimis lebih banyak dibandingkan respon optimis."
    ),
    source=_SK_METADATA,
    url=_SK_METADATA_URL,
    english=(
        "Indexes on each city were captured by balance score method (net balance + 100). Net balance is a difference "
        "between percentages of respondent who answer \"increase\" with percentages of respondent who answer \"decrease\".\n\n"
        "An index above 100 shows that optimistic responses are more dominant than pessimistic ones. On the contrary, "
        "an index below 100 shows those pessimistic responses are more dominant than optimistic ones."
    ),
    english_source=_SK_METADATA_EN,
    english_url=_SK_METADATA_EN_URL,
)

SK_IKK = Definition(
    term="Indeks Keyakinan Konsumen (IKK) / Consumer Confidence Index (CCI)",
    text=(
        "Indeks Keyakinan Konsumen (IKK) merupakan indikator untuk mengetahui keyakinan konsumen mengenai kondisi ekonomi "
        "saat ini dan ekspektasi konsumen terhadap kondisi perekonomian ke depan. IKK dihasilkan dari Survei Konsumen yang "
        "merupakan survei rutin bulanan yang dilakukan oleh Bank Indonesia.\n\n"
        "IKK merupakan rata-rata dari Indeks Kondisi Ekonomi Saat Ini (IKE) dan Indeks Ekspektasi Konsumen (IEK).\n\n"
        "IKK pada level nasional merupakan hasil rata-rata dengan bobot tertentu pada tiap indeks kota yang termasuk dalam "
        "perhitungan nasional, yaitu Medan, Padang, Palembang, Pangkal Pinang, Bandar Lampung, Jakarta, Bandung, Serang, "
        "Semarang, Surabaya, Pontianak, Banjarmasin, Samarinda, Manado, Makassar, Ambon, Denpasar, dan Mataram."
    ),
    source=_SK_METADATA,
    url=_SK_METADATA_URL,
    english=(
        "Consumer Confidence Index (CCI) is a simplified average of Current Economy Condition Index (CECI) and "
        "Consumer Expectation Index (CEI)."
    ),
    english_source=_SK_METADATA_EN,
    english_url=_SK_METADATA_EN_URL,
)

SK_IKE = Definition(
    term="Indeks Kondisi Ekonomi Saat Ini (IKE) / Current Economic Condition Index (CECI)",
    text=(
        "IKE yang mengindikasikan persepsi konsumen terhadap kondisi ekonomi saat ini, merupakan rata-rata dari Indeks "
        "Penghasilan Saat Ini (IPSI), Indeks Ketersediaan Lapangan Kerja (IKLK), dan Indeks Pembelian Barang Tahan "
        "Lama/Durable Goods (IPDG)."
    ),
    source=_SK_METADATA,
    url=_SK_METADATA_URL,
    english=(
        "CECI covers their current income, timing for purchasing durable goods and employement availability, and those "
        "compared against situation on six months ago."
    ),
    english_source=_SK_METADATA_EN,
    english_url=_SK_METADATA_EN_URL,
)

SK_IEK = Definition(
    term="Indeks Ekspektasi Konsumen (IEK) / Consumer Expectation Index (CEI)",
    text=(
        "Sementara itu, IEK, yang mengindikasikan ekspektasi konsumen terhadap kondisi ekonomi ke depan, merupakan "
        "rata-rata dari Indeks Ekspektasi Penghasilan (IEP), Indeks Ekspektasi Ketersediaan Lapangan Kerja (IEKLK), "
        "dan Indeks Ekspektasi Kegiatan Usaha (IEKU)."
    ),
    source=_SK_METADATA,
    url=_SK_METADATA_URL,
    english=(
        "Meanwhile CEI include consumer confidence over consumer expectation for economic forcasting for the next 6 months "
        "compared to current condition, their expectation over income, business conditions in general and availability of employement."
    ),
    english_source=_SK_METADATA_EN,
    english_url=_SK_METADATA_EN_URL,
)

SK_COMPONENTS = Definition(
    term="Pertanyaan inti pembentuk indeks (IPSI, IKLK, IPDG, IEP, IEKLK, IEKU)",
    text=(
        "Pertanyaan inti pembentuk indeks merupakan pertanyaan tertutup dengan pilihan jawaban meningkat, tetap, dan "
        "menurun. Terdapat 6 pertanyaan inti sebagai komponen penyusun Indeks Keyakinan Konsumen, yaitu:\n"
        "▪ penghasilan saat ini dibandingkan 6 bulan yang lalu;\n"
        "▪ ketersediaan lapangan kerja di kota survei saat ini dibandingkan 6 bulan yang lalu;\n"
        "▪ pengeluaran untuk konsumsi barang tahan lama saat ini dibandingkan 6 bulan yang lalu;\n"
        "▪ perkiraan penghasilan pada 6 bulan yang akan datang dibandingkan saat ini;\n"
        "▪ perkiraan ketersediaan lapangan kerja di kota survei pada 6 bulan yang akan datang dibandingkan saat ini;\n"
        "▪ perkiraan kondisi kegiatan usaha di kota survei pada 6 bulan yang akan datang dibandingkan saat ini."
    ),
    source=_SK_METADATA,
    url=_SK_METADATA_URL,
    note=(
        "The six questions are listed in the order of the six component indices: Indeks Penghasilan Saat Ini (IPSI), "
        "Indeks Ketersediaan Lapangan Kerja (IKLK), Indeks Pembelian Barang Tahan Lama (IPDG), Indeks Ekspektasi "
        "Penghasilan (IEP), Indeks Ekspektasi Ketersediaan Lapangan Kerja (IEKLK) and Indeks Ekspektasi Kegiatan Usaha "
        "(IEKU); BI's data-series workbook names them in English Current Incomes Index, Job Availability Index, Purchase "
        "of Durable Goods Index, Incomes Expectation Index, Job Availability Expectation Index and Business Activities "
        "Expectation Index. BI publishes no separate definition of any one of them."
    ),
)

_SK_SHARE_NOTE = (
    "Bank Indonesia publishes no formal definition of this row of its table 'Perkembangan Proporsi Pengeluaran "
    "Responden' / 'Respondent Expenditure Proportion Development'; the quote is how its August 2026 report names the measure."
)

SK_SHARE_CONSUMPTION = Definition(
    term="Konsumsi / Consumption (proporsi pengeluaran responden)",
    text=(
        "Pada Agustus 2026, rata-rata proporsi pendapatan konsumen untuk konsumsi (average propensity to consume ratio) "
        "tercatat sebesar 74,2%, meningkat dibandingkan dengan proporsi pada bulan sebelumnya, yaitu sebesar 72,7%."
    ),
    source=_SK_REPORT,
    url=_SK_REPORT_URL,
    english="In August 2026, the average propensity to consume ratio was recorded at 74.2%, increasing from 72.7% in the previous period.",
    english_source=_SK_REPORT_EN,
    english_url=_SK_REPORT_EN_URL,
    note=_SK_SHARE_NOTE,
)

SK_SHARE_LOAN = Definition(
    term="Cicilan pinjaman / Loan Repayments (proporsi pengeluaran responden)",
    text=(
        "Sementara itu, proporsi pembayaran cicilan/utang (debt installment to income ratio) sebesar 10,0%, relatif "
        "stabil dibandingkan proporsi pada bulan sebelumnya sebesar 10,5%."
    ),
    source=_SK_REPORT,
    url=_SK_REPORT_URL,
    english="Meanwhile, the debt instalment-to-income ratio was recorded at 10.0%, relatively stable compared with 10.5% in the previous month.",
    english_source=_SK_REPORT_EN,
    english_url=_SK_REPORT_EN_URL,
    note=_SK_SHARE_NOTE,
)

SK_SHARE_SAVING = Definition(
    term="Tabungan / Savings (proporsi pengeluaran responden)",
    text=(
        "Lebih lanjut, proporsi pendapatan konsumen yang disimpan (saving to income ratio) sebesar 15,8%, lebih rendah "
        "dibandingkan proporsi pada bulan sebelumnya, yaitu sebesar 16,8% (Grafik 18)."
    ),
    source=_SK_REPORT,
    url=_SK_REPORT_URL,
    english="Furthermore, the savings-to-income ratio was recorded at 15.8%, down from 16.8% in the previous period (Graph 18).",
    english_source=_SK_REPORT_EN,
    english_url=_SK_REPORT_EN_URL,
    note=_SK_SHARE_NOTE,
)

SK_BRACKETS = Definition(
    term="Kelompok pengeluaran responden / Respondent Expenditure Level",
    text=(
        "Survei Konsumen dilakukan terhadap sekitar 4.600 rumah tangga dengan tingkat pengeluaran rumah tangga minimal "
        "Rp1 juta per bulan yang dipilih secara acak (stratified random sampling) di 18 kota.\n\n"
        "Selain itu juga dilengkapi dengan tabel indeks yang lebih detail berdasarkan kategori responden, yaitu tingkat "
        "pengeluaran, tingkat pendidikan, dan kelompok usia."
    ),
    source=_SK_METADATA,
    url=_SK_METADATA_URL,
    note=(
        "The brackets Rp 1-2 juta to > Rp 5 juta are the data-series workbook's 'Pengeluaran per bulan' / "
        "'Household Expenses' groups: monthly household expenditure, not income."
    ),
)

_SK_DISCONTINUED_NOTE = (
    "Bank Indonesia publishes no definition of this index beyond its label in the data-series workbook, which marks "
    "the rows 'Data diskontinu' / 'Data discontinued'. The quote is the general rule its reports state for all the "
    "survey's indices."
)

_SK_INDEX_RULE = (
    "Indeks per kota dihitung dengan metode balance score (net balance + 100) yang menunjukkan bahwa jika indeks di "
    "atas 100 berarti optimis dan di bawah 100 berarti pesimis."
)

SK_EXPECT_SAVING = Definition(
    term="Indeks perkiraan jumlah tabungan 6 bulan mendatang / Saving Expectation Index for the next 6 months",
    text=_SK_INDEX_RULE, source=_SK_REPORT_2019, url=_SK_REPORT_2019_URL, note=_SK_DISCONTINUED_NOTE,
)
SK_EXPECT_DEBT = Definition(
    term="Indeks perkiraan posisi pinjaman 6 bulan mendatang / Debt Expectation Index for the next 6 months",
    text=_SK_INDEX_RULE, source=_SK_REPORT_2019, url=_SK_REPORT_2019_URL, note=_SK_DISCONTINUED_NOTE,
)
SK_EXPECT_SPEND = Definition(
    term="Indeks perkiraan pengeluaran konsumsi 3 bulan mendatang / Consumption Expectation Index in the next 3 months",
    text=_SK_INDEX_RULE, source=_SK_REPORT_2019, url=_SK_REPORT_2019_URL, note=_SK_DISCONTINUED_NOTE,
)
SK_PRICE_EXPECTATIONS = Definition(
    term="Indeks Ekspektasi Harga pada 3, 6 dan 12 bulan yad / Price expectations index for the next 3, 6 and 12 months",
    text=_SK_INDEX_RULE,
    source=_SK_REPORT_2019,
    url=_SK_REPORT_2019_URL,
    english=(
        "Meanwhile, other information presented includes consumer expectation over prices for the next three months, six "
        "months, based on groups of commodities such as: foods materia; foods, beverages, ciggaretes and tobacco; housing, "
        "electricity, gas and fuel; clothing material; health; transportation, communication and financial services; "
        "education, recreation and sport."
    ),
    english_source=_SK_METADATA_EN,
    english_url=_SK_METADATA_EN_URL,
    note=_SK_DISCONTINUED_NOTE,
)


def _by_bracket(prefix: str, measure: Definition) -> dict[str, tuple[Definition, ...]]:
    """The all-respondent series shares the measure's definition; each bracket series adds the brackets'."""
    out = {prefix: (measure,)}
    for suffix in ("rp1_2juta", "rp2_3juta", "rp3_4juta", "rp4_5juta", "above_rp5juta"):
        out[f"{prefix}.{suffix}"] = (measure, SK_BRACKETS)
    return out


DATASETS["consumer_survey"] = (SK_SURVEY, SK_METHOD, SK_COVERAGE)
GROUPS[("consumer_survey", "confidence")] = (SK_BALANCE_SCORE,)
SERIES.update(
    {
        "bi_consumer_survey.ikk": (SK_IKK,),
        "bi_consumer_survey.ike": (SK_IKE,),
        "bi_consumer_survey.iek": (SK_IEK,),
        "bi_consumer_survey.ipsi": (SK_COMPONENTS,),
        "bi_consumer_survey.iklk": (SK_COMPONENTS,),
        "bi_consumer_survey.durable_goods_purchase": (SK_COMPONENTS,),
        "bi_consumer_survey.iep": (SK_COMPONENTS,),
        "bi_consumer_survey.ieklk": (SK_COMPONENTS,),
        "bi_consumer_survey.ieku": (SK_COMPONENTS,),
        "bi_consumer_survey.price_expectation_3m": (SK_PRICE_EXPECTATIONS,),
        "bi_consumer_survey.price_expectation_6m": (SK_PRICE_EXPECTATIONS,),
        "bi_consumer_survey.price_expectation_12m": (SK_PRICE_EXPECTATIONS,),
    }
)
SERIES.update(_by_bracket("bi_consumer_survey.expenditure_share.consumption", SK_SHARE_CONSUMPTION))
SERIES.update(_by_bracket("bi_consumer_survey.expenditure_share.loan_instalment", SK_SHARE_LOAN))
SERIES.update(_by_bracket("bi_consumer_survey.expenditure_share.saving", SK_SHARE_SAVING))
SERIES.update(_by_bracket("bi_consumer_survey.expectation.saving_6m", SK_EXPECT_SAVING))
SERIES.update(_by_bracket("bi_consumer_survey.expectation.debt_position_6m", SK_EXPECT_DEBT))
SERIES.update(_by_bracket("bi_consumer_survey.expectation.consumption_spend_3m", SK_EXPECT_SPEND))


# ---------------------------------------------------------------------------
# Bank Indonesia -- SPIP (payment system statistics)

_SPIP_META = "https://www.bi.go.id/id/statistik/Metadata/metadata-SPIP/Documents/"
_SPIP_META_EN = "https://www.bi.go.id/en/statistik/Metadata/metadata-SPIP/Documents/"
_M5E = "Metadata SPIP Tabel 5e: Uang Elektronik (Bank Indonesia, Januari 2022)"
_M5E_URL = _SPIP_META + "Tabel-5e.Uang-Elektronik_ID.pdf"
_M5E_EN = "PSFMI Metadata Table 5e: Electronic Money (Bank Indonesia)"
_M5E_EN_URL = _SPIP_META_EN + "Tabel-5e.Uang-Elektronik_EN.pdf"
_M5A = "Metadata SPIP Tabel 5a: ATM dan ATM+Debet (Bank Indonesia, Januari 2022)"
_M5A_URL = _SPIP_META + "Tabel-5a.ATM-dan-ATM+Debet_ID.pdf"
_M5A_EN = "PSFMI Metadata Table 5a: ATM and ATM+Debit (Bank Indonesia)"
_M5A_EN_URL = _SPIP_META_EN + "Tabel-5a.ATM-dan-ATM+Debet_EN.pdf"
_M5C = "Metadata SPIP Tabel 5c: Kartu Kredit (Bank Indonesia, Januari 2022)"
_M5C_URL = _SPIP_META + "Tabel-5c.Kartu-Kredit_ID.pdf"
_M5C_EN = "PSFMI Metadata Table 5c: Credit Cards (Bank Indonesia)"
_M5C_EN_URL = _SPIP_META_EN + "Tabel-5c.Kartu-Kredit_EN.pdf"
_M1 = "Metadata SPIP Tabel 1: Indikator Utama (Bank Indonesia, April 2023)"
_M1_URL = _SPIP_META + "Tabel-1.Indikator-Utama-ID.pdf"
_M1_EN = "PSFMI Metadata Table 1: Main Indicators (Bank Indonesia)"
_M1_EN_URL = _SPIP_META_EN + "Tabel-1.Indikator-Utama-EN.pdf"
_M2 = "Metadata SPIP Tabel 2: Media yang Digunakan Sebagai Alat Pembayaran oleh Bank dan Nonbank (Bank Indonesia, Juli 2021)"
_M2_URL = _SPIP_META + "Tabel-2_Media-yang-Digunakan-untuk-Alat-Pembayaran_ID.pdf"
_M2_EN = "PSFMI Metadata Table 2: Settlement Media used by Banks and Nonbanks (Bank Indonesia)"
_M2_EN_URL = _SPIP_META_EN + "Tabel-2_Media-yang-Digunakan-untuk-Alat-Pembayaran_EN.pdf"
_M3A = "Metadata SPIP Tabel 3a: Uang Kartal yang Diedarkan (Bank Indonesia, Juli 2021)"
_M3A_URL = _SPIP_META + "Tabel-3a_Uang-yang-Diedarkan-per-Pecahan-ID.pdf"
_M3A_EN = "PSFMI Metadata Table 3a: Currency in Circulation (Bank Indonesia)"
_M3A_EN_URL = _SPIP_META_EN + "Tabel-3a_Uang-yang-Diedarkan-per-Pecahan-EN.pdf"
_SEKI_MONEY = "Metadata SEKI: Uang Beredar dan Faktor-Faktor yang Mempengaruhinya (Bank Indonesia, Juni 2025)"
_SEKI_MONEY_URL = "https://www.bi.go.id/id/statistik/Metadata/SEKI/Documents/03_Uang-Beredar-dan-Faktor-Faktor-yang-Mempengaruhinya.pdf"
_SEKI_MONEY_EN = "SEKI Metadata: Broad Money and Its Affecting Factors (Bank Indonesia, August 2024)"
_SEKI_MONEY_EN_URL = "https://www.bi.go.id/en/statistik/Metadata/SEKI/Documents/Broad-Money-and-Its-Affecting-Factors-.pdf"
_PBI_UE = "Peraturan Bank Indonesia No. 20/6/PBI/2018 tentang Uang Elektronik, Pasal 1"
_PBI_UE_URL = "https://www.bi.go.id/id/publikasi/peraturan/Documents/PBI-200618.pdf"
_WEB_INSTRUMEN_EN = "Bank Indonesia, Retail Payment System: Instruments"
_WEB_INSTRUMEN_EN_URL = "https://www.bi.go.id/en/fungsi-utama/sistem-pembayaran/ritel/instrumen/default.aspx"
_T5E_XLS = "SPIP Tabel 5e. Uang Elektronik / Table 5e. Electronic Money, table notes"
_T5E_XLS_URL = "https://www.bi.go.id/id/statistik/ekonomi-keuangan/spip/Documents/TABEL_5e.xls"
_T2_XLS = "SPIP Tabel 2. Media yang Digunakan sebagai Alat Pembayaran, table footnote"
_T2_XLS_URL = "https://www.bi.go.id/id/statistik/ekonomi-keuangan/spip/Documents/TABEL_2.xls"

SPIP_ABOUT = Definition(
    term="Statistik Sistem Pembayaran dan Infrastruktur Pasar Keuangan (SPIP) / Payment System and Financial Market Infrastructure Statistics (PSFMI)",
    text=(
        "Dalam rangka menginformasikan perkembangan SP PUR di Indonesia maupun sebagai media komunikasi dan edukasi "
        "kepada stakeholder mengenai pelaksanaan tugas dan kebijakan SP PUR, BI menyusun Statistik Sistem Pembayaran dan "
        "Infrastruktur Pasar Keuangan Indonesia (SPIP). SPIP merupakan kumpulan indikator yang menggambarkan perkembangan "
        "berbagai indikator terkait SP PUR termasuk sistem dan infrastruktur pasar keuangan Indonesia. Cakupan SPIP meliputi "
        "indikator terkait pengedaran uang, sistem pembayaran, maupun sistem setelmen yang berlaku di Indonesia, yang dapat "
        "menggambarkan perkembangan instrumen maupun infrastruktur sistem pembayaran tunai - non tunai dan setelmen yang "
        "tersedia di Indonesia. Proses penyusunan SPIP mengacu pada data yang dikelola oleh BI juga bekerjasama dengan "
        "otoritas dan lembaga pendukung pasar keuangan di Indonesia lain seperti PT. Kliring Penjaminan Efek Indonesia, "
        "serta PT. Kustodian Sentral Efek Indonesia."
    ),
    source="Bank Indonesia, Pengantar: Statistik Sistem Pembayaran dan Infrastruktur Pasar Keuangan (SPIP)",
    url="https://www.bi.go.id/id/statistik/ekonomi-keuangan/spip/pengantar.aspx",
    english=(
        "Bank Indonesia compiles Payment System and Financial Market Infrastructure Statistics (PSFMI) to inform about "
        "the latest developments in Indonesia and as an effective communication and education media for stakeholders "
        "concerning relevant task implementation and policies in Payment System and Rupiah Currency Management (PS RCM). "
        "PSFMI statistics consists of indicators developed to represent the latest developments concerning the Payment "
        "System and Rupiah Currency Management, including financial market infrastructures and systems in Indonesia. The "
        "scope of PSFMI statistics covers currency in circulation, payment systems and settlement systems in Indonesia, "
        "which illustrate the development of cash and cashless payment systems and infrastructure as well as the "
        "availability of settlement services in Indonesia. PSFMI statistics are compiled referring to data managed by Bank "
        "Indonesia in conjunction with other relevant authorities and supporting institutions for the financial markets in "
        "Indonesia, including the Indonesia Stock Market Clearing House (KPEI) and Indonesian Central Securities Depository (KSEI)."
    ),
    english_source="Bank Indonesia, Introduction: Payment System and Financial Market Infrastructure Statistics (PSFMI)",
    english_url="https://www.bi.go.id/en/statistik/ekonomi-keuangan/spip/pengantar.aspx",
)

# -- E-money (SPIP table 5e, and the non-bank instrument count of table 2)

EM_UE = Definition(
    term="Uang Elektronik / Electronic money",
    text=(
        "Uang Elektronik (electronic money) adalah alat pembayaran yang memenuhi unsur-unsur sebagai berikut: • diterbitkan "
        "atas dasar nilai uang yang disetor terlebih dahulu kepada penerbit; • nilai uang disimpan secara elektronik dalam "
        "suatu media seperti server atau chip; dan • nilai uang elektronik yang dikelola oleh penerbit bukan merupakan "
        "simpanan sebagaimana dimaksud dalam undang-undang yang mengatur mengenai perbankan."
    ),
    source=_M5E,
    url=_M5E_URL,
    english=(
        "Electronic money is a payment instrument which meets the following requirements: a. Issued based on the value of "
        "money paid-up in advance to an issuer; b. The value of money is stored electronically in a server or chip; and "
        "c. The value of electronic money managed by an issuer does not constitute as a saving that is specified in Laws on banking."
    ),
    english_source=_M5E_EN,
    english_url=_M5E_EN_URL,
)

EM_TXN = Definition(
    term="Volume Transaksi / Nilai Transaksi (Uang Elektronik): table notes",
    text=(
        "- Sejak implementasi Laporan Bank Umum Terintegrasi (LBUT) di Januari 2022, terdapat perincian dimensi pelaporan. "
        "Transaksi tunai merupakan penjumlahan dari transaksi tarik dan setor tunai. Sementara transaksi belanja merupakan "
        "penjumlahan dari transaksi belanja dan pembayaran."
    ),
    source=_T5E_XLS,
    url=_T5E_XLS_URL,
    english=(
        "- Since the implementation of the Integrated Commercial Bank Report (LBUT) in January 2022, there are changes in "
        "granularity of the reporting dimensions. Cash transactions are the sum of cash withdrawal and deposit transactions. "
        "Meanwhile, shopping transactions are the sum of shopping and payment transactions."
    ),
    english_source=_T5E_XLS,
    english_url=_T5E_XLS_URL,
    note=(
        "No sentence in BI's metadata defines the table's aggregate 'Volume Transaksi' and 'Nilai Transaksi' rows themselves. "
        "The metadata defines their components (belanja, transfer antar uang elektronik, initial, reload/top up, tarik "
        "tunai, redeem), gives the units (thousand transactions; Rp billion) and states that the figures are accumulated "
        "over the reporting period."
    ),
)

EM_PURCHASE_VALUE = Definition(
    term="Nominal Transaksi Belanja Uang Elektronik / Value of Electronic Money purchase Transaction",
    text=(
        "Nominal Transaksi Belanja Uang Elektronik adalah nilai/nominal dari transaksi pembelanjaan yang dilakukan dengan "
        "menggunakan uang elektronik selama periode tertentu."
    ),
    source=_M5E, url=_M5E_URL,
    english="Value of Electronic Money purchase Transaction is the value of purchase transactions using Electronic Money in a certain period.",
    english_source=_M5E_EN, english_url=_M5E_EN_URL,
)

EM_PURCHASE_VOLUME = Definition(
    term="Volume Transaksi Belanja Uang Elektronik / Volume of Electronic Money purchase Transaction",
    text=(
        "Volume Transaksi Belanja Uang Elektronik adalah jumlah transaksi pembelanjaan yang dilakukan dengan menggunakan "
        "uang elektronik selama periode tertentu."
    ),
    source=_M5E, url=_M5E_URL,
    english="Volume of Electronic Money purchase Transaction is the number of purchase transactions using Electronic Money in a certain period.",
    english_source=_M5E_EN, english_url=_M5E_EN_URL,
)

EM_TOPUP_VALUE = Definition(
    term="Nilai Transaksi Reload/Top Up / Value of Reload/Top Up Transaction",
    text="Nilai Transaksi Reload/Top Up adalah nilai transaksi pengisian ulang dana pada uang elektronik selama periode laporan.",
    source=_M5E, url=_M5E_URL,
    english="Value of Reload/Top Up Transaction is the nominal transaction for reloading funds on electronic money in a certain period.",
    english_source=_M5E_EN, english_url=_M5E_EN_URL,
)

EM_TOPUP_VOLUME = Definition(
    term="Volume Transaksi Reload/Top Up / Volume of Reload/Top Up Transaction",
    text="Volume Transaksi Reload/Top Up adalah volume transaksi pengisian ulang dana pada uang elektronik selama periode laporan.",
    source=_M5E, url=_M5E_URL,
    english="Volume of Reload/Top Up Transaction is the amount of fund reload transactions in electronic money in a certain period.",
    english_source=_M5E_EN, english_url=_M5E_EN_URL,
)

EM_INSTRUMENTS = Definition(
    term="Jumlah Kartu/ Instrumen (Jumlah Uang Elektronik) / Number of Cards / Instruments",
    text=(
        "Jumlah Uang Elektronik adalah jumlah uang elektronik yang beredar di masyarakat pada periode tertentu.\n\n"
        "Data mengenai jumlah kartu/instrumen uang elektronik, jumlah kartu/instrumen registered, jumlah kartu/instrumen "
        "unregistered dan jumlah kartu/instrumen dalam rangka LKD adalah posisi jumlah kartu/instrumen beredar pada akhir "
        "periode laporan."
    ),
    source=_M5E, url=_M5E_URL,
    english="Number of Electronic Money is the number of Electronic Money circulating in public in a certain period.",
    english_source=_M5E_EN, english_url=_M5E_EN_URL,
)

EM_CHIP = Definition(
    term="Uang Elektronik Chip Based / Chip Based Electronic Money",
    text=(
        "Uang Elektronik Chip Based adalah jumlah uang elektronik yang menggunakan media penyimpanan data berbentuk chip "
        "sebagai media penyimpanan nilai uang elektronik pada akhir periode laporan."
    ),
    source=_M5E, url=_M5E_URL,
    english=(
        "Chip Based Electronic Money is electronic money that uses a microchip as the data storage media for storing the "
        "value of electronic money in a certain period."
    ),
    english_source=_M5E_EN, english_url=_M5E_EN_URL,
)

EM_SERVER = Definition(
    term="Uang Elektronik Server Based / Server Based Electronic Money",
    text=(
        "Uang Elektronik Server Based adalah jumlah uang elektronik yang menggunakan media penyimpanan data dalam bentuk "
        "server atau media komputer lainnya yang dikelola oleh penerbit sebagai media penyimpan nilai uang elektronik pada "
        "akhir periode laporan."
    ),
    source=_M5E, url=_M5E_URL,
    english=(
        "Server Based Electronic Money is electronic money that uses servers or computers managed by the issuer as data "
        "storage media for storing the value of electronic money in a certain period."
    ),
    english_source=_M5E_EN, english_url=_M5E_EN_URL,
)

EM_FLOAT = Definition(
    term="Dana Float / Float funds",
    text=(
        "17. Dana Float adalah seluruh Nilai Uang Elektronik yang berada pada Penerbit atas hasil penerbitan Uang Elektronik "
        "dan/atau Pengisian Ulang (Top Up) yang masih merupakan kewajiban Penerbit kepada Pengguna dan Penyedia Barang "
        "dan/atau Jasa."
    ),
    source=_PBI_UE, url=_PBI_UE_URL,
    english=(
        "Float funds of electronic money is the entire value of electronic money available at an Issuer based on the "
        "proceeds of electronic money issuance and/or Top Up as an Issuer's obligation to a User and Goods and/or Services Provider."
    ),
    english_source=_M5E_EN, english_url=_M5E_EN_URL,
)

EM_FLOAT_POSITION = Definition(
    term="Dana float: metode pencatatan / Float fund: recording method",
    text="Dana float adalah posisi dana float Uang Elektronik pada akhir periode laporan (akhir bulan).",
    source=_M1, url=_M1_URL,
    english="Float fund is the position of the electronic money float at the end of the reporting period (monthly).",
    english_source=_M1_EN, english_url=_M1_EN_URL,
)

EM_ISSUER = Definition(
    term="Penerbit / Issuer",
    text="Penerbit adalah Bank atau Lembaga Selain Bank yang menerbitkan uang elektronik.",
    source=_M5E, url=_M5E_URL,
    english="Issuer is a Bank or Non-Bank Financial Institution that issues electronic money.",
    english_source=_M5E_EN, english_url=_M5E_EN_URL,
    note=(
        "BI lists 'Dana Float Penerbit Uang Elektronik Bank' and 'Dana Float seluruh Penerbit Uang Elektronik Non Bank' "
        "as rows of the table without a definition of their own; the split is by the kind of issuer defined here."
    ),
)

EM_NONBANK_INSTRUMENTS = Definition(
    term="Instrumen Uang Elektronik yang Diterbitkan oleh Lembaga Selain Bank / Electronic Money Instrument issued by Non-banks",
    text=(
        "Instrumen Uang Elektronik berbasis kartu dan server yang diterbitkan oleh Lembaga Selain Bank adalah jumlah uang "
        "elektronik berbasis kartu dan server yang diterbitkan oleh penerbit Lembaga Selain Bank dan beredar di masyarakat "
        "pada periode tertentu.\n\n"
        "Jumlah Instrumen Uang Elektronik yang diterbitkan oleh Lembaga Selain Bank adalah posisi jumlah uang elektronik "
        "beredar pada akhir periode laporan (akhir bulan)."
    ),
    source=_M2, url=_M2_URL,
    english=(
        "Card and server-based electronic money issued by non-bank financial institution is the amount of card and "
        "server-based electronic money issued by non-bank financial institution in a certain period.\n\n"
        "Total amount of electronic money issued by nonbank financial institutions is the amount of electronic money at "
        "the end of the reporting period (end of month)."
    ),
    english_source=_M2_EN, english_url=_M2_EN_URL,
)

# -- Cards (SPIP tables 5a and 5c)

CARD_APMK = Definition(
    term="Alat Pembayaran dengan Menggunakan Kartu (APMK) / Card-Based Payment Instrument",
    text=(
        "Alat Pembayaran dengan Menggunakan Kartu (APMK) adalah alat pembayaran yang berupa kartu kredit, kartu Automated "
        "Teller Machine (ATM) dan/atau kartu debet."
    ),
    source=_M5C, url=_M5C_URL,
    english=(
        "A Card-Based Payment Instrument is a payment instrument in the form of a credit card, Automated Teller Machine "
        "(ATM) card and/or debit card."
    ),
    english_source=_M5C_EN, english_url=_M5C_EN_URL,
)

CARD_ATM = Definition(
    term="Kartu ATM / ATM card",
    text=(
        "Kartu ATM adalah Alat Pembayaran Menggunakan Kartu (APMK) yang dapat digunakan untuk melakukan penarikan tunai "
        "dan/atau pemindahan dana dimana kewajiban pemegang kartu dipenuhi seketika dengan mengurangi secara langsung "
        "simpanan pemegang kartu pada Bank atau Lembaga Selain Bank yang berwenang untuk menghimpun dana sesuai ketentuan "
        "perundang-undangan yang berlaku."
    ),
    source=_M5A, url=_M5A_URL,
    english=(
        "ATM cards are card-based payment instruments that may be used for cash withdrawals and/or fund transfers in which "
        "the obligations of the cardholder are settled in real-time through a direct debit of the cardholder's account at "
        "a bank or nonbank institution authorised to mobilise funds under prevailing laws and regulations."
    ),
    english_source=_WEB_INSTRUMEN_EN, english_url=_WEB_INSTRUMEN_EN_URL,
)

CARD_DEBIT = Definition(
    term="Kartu Debet / Debit card",
    text=(
        "Kartu Debet adalah APMK yang dapat digunakan untuk melakukan pembayaran atas kewajiban yang timbul dari suatu "
        "kegiatan ekonomi, termasuk transaksi pembelanjaan dimana kewajiban pemegang kartu dipenuhi seketika dengan "
        "mengurangi secara langsung simpanan pemegang kartu pada Bank atau Lembaga Selain Bank yang berwenang untuk "
        "menghimpun dana sesuai ketentuan perundang-undangan yang berlaku."
    ),
    source=_M5A, url=_M5A_URL,
    english=(
        "A Debit Card is a card-based payment instrument that may be used for payments of liabilities arising from economic "
        "activity, including shopping transactions, in which the obligation of the cardholder is settled in real-time "
        "through a direct debit of the cardholder's account at a bank or nonbank institution authorised to mobilise funds "
        "under prevailing laws and regulations."
    ),
    english_source=_WEB_INSTRUMEN_EN, english_url=_WEB_INSTRUMEN_EN_URL,
)

CARD_CREDIT = Definition(
    term="Kartu Kredit / Credit card",
    text=(
        "Kartu Kredit adalah APMK yang dapat digunakan untuk melakukan pembayaran atas kewajiban yang timbul dari suatu "
        "kegiatan ekonomi, termasuk transaksi pembelanjaan dan/atau untuk melakukan penarikan tunai, dimana kewajiban "
        "pembayaran pemegang kartu dipenuhi terlebih dahulu oleh acquirer atau penerbit, dan pemegang kartu berkewajiban "
        "untuk melakukan pembayaran pada waktu yang disepakati baik dengan pelunasan secara sekaligus (charge card) ataupun "
        "dengan pembayaran secara angsuran."
    ),
    source=_M5C, url=_M5C_URL,
    english=(
        "A credit card is a card-based payment instrument used for payments of obligations arising from economic activity, "
        "including shopping transactions and/or cash withdrawals, in which the payment obligation of the cardholder is "
        "settled in advance by the acquirer or issuer and the cardholder is required to execute payment at an agreed term "
        "in a lump sum (charge card) or instalments."
    ),
    english_source=_WEB_INSTRUMEN_EN, english_url=_WEB_INSTRUMEN_EN_URL,
)

CARD_ATM_COUNT = Definition(
    term="Jumlah Kartu ATM, Jumlah Kartu ATM+Debet / Number of ATM Cards, Number of ATM+Debit",
    text=(
        "Jumlah Kartu ATM adalah jumlah kartu ATM yang beredar di masyarakat pada periode tertentu.\n\n"
        "Jumlah Kartu ATM+Debet adalah jumlah kartu ATM yang berfungsi juga sebagai kartu Debet yang beredar di masyarakat "
        "pada periode tertentu.\n\n"
        "Data mengenai jumlah Kartu ATM, jumlah Kartu ATM+Debet adalah posisi jumlah instrumen Kartu ATM dan Kartu "
        "ATM+Debet beredar pada akhir periode laporan."
    ),
    source=_M5A, url=_M5A_URL,
    english=(
        "Number of ATM Cards is the amount of ATM cards circulating in the public at a certain period.\n\n"
        "Number of ATM+Debit is the amount of ATM cards which have function as debit cards circulating in the public at a "
        "certain period."
    ),
    english_source=_M5A_EN, english_url=_M5A_EN_URL,
    note="The dashboard series is the table's total row 'Jumlah Kartu/ Instrumen', which covers both kinds of card.",
)

CARD_CREDIT_COUNT = Definition(
    term="Jumlah Kartu Kredit / Number of Credit Cards",
    text=(
        "Jumlah Kartu Kredit adalah jumlah kartu kredit yang beredar di masyarakat pada periode tertentu.\n\n"
        "Data mengenai jumlah kartu kredit adalah posisi jumlah instrumen kartu kredit beredar pada akhir periode laporan."
    ),
    source=_M5C, url=_M5C_URL,
    english="Number of Credit Cards is the amount of Credit cards circulating in the public at a certain period.",
    english_source=_M5C_EN, english_url=_M5C_EN_URL,
)

_CARD_AGGREGATE_NOTE = (
    "BI's metadata defines these component transaction types and states that the figures are accumulated over the "
    "reporting period; it has no sentence defining the table's aggregate row that the dashboard shows."
)

CARD_ATM_VOLUME = Definition(
    term="Volume transaksi Kartu ATM/Debet: tunai, belanja, transfer / Volume of ATM/Debit transactions",
    text=(
        "Volume Tunai Kartu ATM/Debet adalah jumlah transaksi penarikan tunai yang dilakukan dengan menggunakan kartu ATM "
        "dan/atau kartu debet pada periode tertentu.\n\n"
        "Volume Belanja Kartu ATM/Debet adalah jumlah transaksi pembelanjaan yang dilakukan dengan menggunakan kartu debet "
        "pada periode tertentu.\n\n"
        "Volume Transfer Intrabank Kartu ATM/Debet adalah jumlah transfer dana antar rekening dalam 1 (satu) bank yang "
        "dilakukan dengan menggunakan kartu ATM dan/atau kartu debet pada periode tertentu.\n\n"
        "Volume Transfer Antarbank Kartu ATM/Debet adalah jumlah transfer dana antar rekening dalam bank yang berbeda "
        "(antarbank) yang dilakukan dengan menggunakan kartu ATM dan/atau kartu debet pada periode tertentu."
    ),
    source=_M5A, url=_M5A_URL,
    english=(
        "Volume of ATM/Debit cash transaction is the number of cash withdrawal transactions using ATM cards and/or debit "
        "cards in a certain period.\n\n"
        "Volume of ATM/Debit purchase transactions is the number of purchase transactions using debit cards in a certain period."
    ),
    english_source=_M5A_EN, english_url=_M5A_EN_URL,
    note=_CARD_AGGREGATE_NOTE,
)

CARD_ATM_VALUE = Definition(
    term="Nominal transaksi Kartu ATM/Debet: tunai, belanja / Value of ATM/Debit transactions",
    text=(
        "Nominal Tunai Kartu ATM/Debet adalah nilai/nominal dari transaksi penarikan tunai yang dilakukan dengan "
        "menggunakan kartu ATM dan/atau kartu debet pada periode tertentu.\n\n"
        "Nominal Belanja Kartu ATM/Debet adalah nilai/nominal dari transaksi pembelanjaan yang dilakukan dengan "
        "menggunakan kartu debet pada periode tertentu."
    ),
    source=_M5A, url=_M5A_URL,
    english=(
        "Value of ATM/Debit Cash transaction is the value of cash withdrawal transactions using ATM cards and/or debit "
        "cards in a certain period.\n\n"
        "Value of ATM/Debit purchase transactions is the value of purchase transactions using debit cards in a certain period."
    ),
    english_source=_M5A_EN, english_url=_M5A_EN_URL,
    note=_CARD_AGGREGATE_NOTE,
)

CARD_CREDIT_VOLUME = Definition(
    term="Volume transaksi Kartu Kredit: tunai, belanja / Volume of Credit Cards transactions",
    text=(
        "Volume Tunai Kartu Kredit adalah jumlah transaksi penarikan tunai yang dilakukan dengan menggunakan kartu kredit "
        "pada periode tertentu.\n\n"
        "Volume Belanja Kartu Kredit adalah jumlah transaksi pembelanjaan yang dilakukan dengan menggunakan kartu kredit "
        "pada periode tertentu."
    ),
    source=_M5C, url=_M5C_URL,
    english=(
        "Volume of Credit Cards cash transaction is the number of cash withdrawal transactions using Credit cards in a "
        "certain period.\n\n"
        "Volume of Credit cards purchase transactions is the number of purchase transactions using credit cards in a certain period."
    ),
    english_source=_M5C_EN, english_url=_M5C_EN_URL,
    note=_CARD_AGGREGATE_NOTE,
)

CARD_CREDIT_VALUE = Definition(
    term="Nilai transaksi Kartu Kredit: tunai, belanja / Value of Credit Cards transactions",
    text=(
        "Nilai Tunai Kartu Kredit adalah nilai/nominal dari transaksi penarikan tunai yang dilakukan dengan menggunakan "
        "kartu kredit pada periode tertentu.\n\n"
        "Nilai Belanja Kartu Kredit adalah nilai/nominal dari transaksi pembelanjaan yang dilakukan dengan menggunakan "
        "kartu kredit pada periode tertentu."
    ),
    source=_M5C, url=_M5C_URL,
    english=(
        "Value of Credit Cards cash transaction is the value of cash withdrawal transactions using credit cards in a "
        "certain period.\n\n"
        "Value of credit cards is the value of purchase transactions using credit cards in a certain period."
    ),
    english_source=_M5C_EN, english_url=_M5C_EN_URL,
    note=_CARD_AGGREGATE_NOTE,
)

# -- Currency and BI-RTGS (SPIP tables 1 and 2)

PS_MONEY_SUPPLY = Definition(
    term="Uang Beredar / Money Supply",
    text=(
        "Uang Beredar adalah kewajiban sistem moneter (Bank Sentral, Bank Umum, dan BPR) terhadap sektor swasta domestik "
        "(tidak termasuk pemerintah pusat dan bukan penduduk)."
    ),
    source=_M2, url=_M2_URL,
    english=(
        "Money Supply is a monetary system liability (central bank, commercial banks, and rural banks) on the domestic "
        "private sector (excluding the central government and non-residents)."
    ),
    english_source=_M2_EN, english_url=_M2_EN_URL,
)

PS_M1 = Definition(
    term="Uang Beredar dalam Arti Sempit (M1) / Narrow Money (M1)",
    text=(
        "Uang Beredar dalam Arti Sempit (M1) adalah kewajiban sistem moneter terhadap sektor swasta domestik yang meliputi "
        "uang kartal yang dipegang masyarakat dan uang giral (termasuk uang elektronik yang diterbitkan oleh Bank)."
    ),
    source=_M2, url=_M2_URL,
    english=(
        "Narrow Money (M1) is a monetary system liability on the domestic private sector in the form of Currency Outside "
        "Banks (COB) and demand deposits (denominated in Rupiah), including electronic money issued by Bank."
    ),
    english_source=_M2_EN, english_url=_M2_EN_URL,
)

PS_M1_FOOTNOTE = Definition(
    term="Uang Beredar dalam Arti Sempit (M1): catatan kaki tabel / table footnote",
    text=(
        "1) Sejak November 2021, tabungan rupiah yang dapat ditarik sewaktu-waktu direklasifikasi dari sebelumnya komponen "
        "uang kuasi, menjadi M1 karena sifatnya yang mudah digunakan untuk transaksi. Pengkunoan data reklasifikasi "
        "tersedia sejak Januari 2011."
    ),
    source=_T2_XLS, url=_T2_XLS_URL,
    english=(
        "1) Since November 2021, rupiah saving deposits that can be withdrawn at any time is reclassified from quasi money "
        "to narrow money, due to its highly liquid nature. Backdated data available since January 2011."
    ),
    english_source=_T2_XLS, english_url=_T2_XLS_URL,
)

PS_COB = Definition(
    term="Uang yang Diedarkan di Masyarakat / Currency in Circulation Outside Commercial and Rural Banks",
    text="Uang kartal yang berada di masyarakat juga disebut uang kartal yang berada di luar sistem perbankan.",
    source=_M1, url=_M1_URL,
    english="Currency held by resident sectors is also known as Currency Outside Banks (COB).",
    english_source=_M1_EN, english_url=_M1_EN_URL,
    note=(
        "The metadata of SPIP table 2 has no sentence for this row of its own; this is BI's nearest wording, from the "
        "metadata of table 1."
    ),
)

PS_CURRENCY = Definition(
    term="Uang kartal / Currency",
    text="Uang kartal/currency adalah uang kertas dan uang logam yang dikeluarkan oleh otoritas moneter sebagai alat pembayaran yang sah.",
    source=_SEKI_MONEY, url=_SEKI_MONEY_URL,
    english="Currency consists of notes and coins issued by Bank Indonesia as a legal tender.",
    english_source=_SEKI_MONEY_EN, english_url=_SEKI_MONEY_EN_URL,
)

PS_GIRO = Definition(
    term="Giro / Demand deposit",
    text=(
        "Giro adalah simpanan pada bank umum dalam rupiah milik pihak ketiga bukan bank, yang penarikannya dapat dilakukan "
        "setiap saat dengan menggunakan cek, surat perintah pembayaran lainnya, atau dengan cara pemindahbukuan."
    ),
    source=_M2, url=_M2_URL,
    english=(
        "A demand deposit is money deposited into a bank account denominated in Rupiah owned by a nonbank third party that "
        "can be withdrawn on-demand at any time using a cheque, other payment order or funds transfer."
    ),
    english_source=_M2_EN, english_url=_M2_EN_URL,
)

PS_RTGS = Definition(
    term="Sistem BI-RTGS / BI-RTGS system",
    text=(
        "Sistem Bank Indonesia Real Time Gross Settlement, yang selanjutnya disebut system BI-RTGS adalah suatu sistem "
        "transfer dana elektronik antar Bank dalam mata uang rupiah yang penyelesaiannya dilakukan per transaksi secara individual."
    ),
    source=_M1, url=_M1_URL,
    english=(
        "The Bank Indonesia – Real Time Gross Settlement (BI-RTGS) system is an interbank electronic funds transfer system "
        "denominated in rupiah with real-time settlement on an individual transaction basis."
    ),
    english_source=_M1_EN, english_url=_M1_EN_URL,
)

PS_RTGS_VALUE = Definition(
    term="Nilai Transaksi RTGS Agregat / Aggregate RTGS Transaction Value",
    text=(
        "Nilai Transaksi RTGS Agregat adalah jumlah nominal/nilai dari transaksi yang diproses dalam mata uang tertentu "
        "(Rupiah) di sistem BI-RTGS pada periode waktu tertentu.\n\n"
        "Data volume dan nilai transaksi RTGS merupakan akumulasi dari data transaksi harian selama periode bulanan."
    ),
    source=_M1, url=_M1_URL,
    english=(
        "Aggregate RTGS Transaction Value is the value of transactions processed in a specific currency (rupiah) via the "
        "BI-RTGS system in a certain period.\n\n"
        "RTGS transaction volume and value data represents the accumulated daily transaction data during the reporting month."
    ),
    english_source=_M1_EN, english_url=_M1_EN_URL,
)

PS_RTGS_VOLUME = Definition(
    term="Volume Transaksi RTGS Agregat / Aggregate RTGS Transaction Volume",
    text=(
        "Volume Transaksi RTGS Agregat adalah jumlah aktivitas transaksi yang diproses dalam sistem BI-RTGS pada periode "
        "waktu tertentu.\n\n"
        "Data volume dan nilai transaksi RTGS merupakan akumulasi dari data transaksi harian selama periode bulanan."
    ),
    source=_M1, url=_M1_URL,
    english=(
        "Aggregate RTGS Transaction Volume is total transaction activity (frequency) processed via the BI-RTGS system in a "
        "certain period.\n\n"
        "RTGS transaction volume and value data represents the accumulated daily transaction data during the reporting month."
    ),
    english_source=_M1_EN, english_url=_M1_EN_URL,
)

PS_UYD = Definition(
    term="Uang Kartal yang Diedarkan (UYD) / Currency in Circulation",
    text=(
        "Uang Kartal yang beredar di Masyarakat dan Perbankan (UYD) adalah uang kertas, uang logam, dan uang khusus yang "
        "dikeluarkan oleh otoritas moneter sebagai alat pembayaran yang sah. Perhitungan UYD diperoleh dari selisih antara "
        "posisi Rekening Pembuatan Uang dengan Posisi Rekening Kas di BI, Rekening Uang yang Dicabut dan Ditarik dari "
        "Peredaran, serta Rekening Uang dalam Penelitian."
    ),
    source=_M3A, url=_M3A_URL,
    english=(
        "Currency in Circulation is all the banknotes and coins as well as special money that has been issued by the "
        "monetary authority as legal tender. Currency in Circulation is calculated as the difference between the position "
        "of currency issued and the position of the cash account at Bank Indonesia, currency withdrawn from circulation as "
        "well as currency under investigation."
    ),
    english_source=_M3A_EN, english_url=_M3A_EN_URL,
)

PS_RATIO_GDP = Definition(
    term="Rasio UYD terhadap Produk Domestik Bruto (PDB) harga berlaku / Ratio of currency in circulation to GDP at current prices",
    text=(
        "Rasio UYD terhadap Produk Domestik Bruto (PDB) harga berlaku merupakan perbandingan antara posisi uang kartal yang "
        "diedarkan dengan nilai tambah barang dan jasa yang dihitung menggunakan harga pada tahun berjalan. Indikator ini "
        "mencerminkan peran uang kartal dalam perekonomian Indonesia."
    ),
    source=_M1, url=_M1_URL,
    english=(
        "The ratio of currency in circulation to gross domestic product (GDP) at current prices represents a comparison "
        "between the position of currency in circulation with value added of goods and services at current prices. This "
        "indicator reflects the role of currency in the Indonesian economy."
    ),
    english_source=_M1_EN, english_url=_M1_EN_URL,
)

PS_RATIO_HOUSEHOLD = Definition(
    term="Rasio UYD terhadap Konsumsi Rumah Tangga harga berlaku / Ratio of currency in circulation to household consumption at current prices",
    text=(
        "Rasio UYD terhadap Konsumsi Rumah Tangga harga berlaku merupakan perbandingan antara uang kartal yang diedarkan "
        "dengan pengeluaran konsumsi rumah tangga yang merupakan salah satu komponen PDB. Indikator ini mencerminkan peran "
        "uang kartal sebagai alat pembayaran pada sektor rumah tangga."
    ),
    source=_M1, url=_M1_URL,
    english=(
        "The ratio of currency in circulation to household consumption at current prices represents a comparison between "
        "currency in circulation and household consumption expenditure as a component of GDP. This indicator reflects the "
        "role of currency as a payment instrument in the household sector."
    ),
    english_source=_M1_EN, english_url=_M1_EN_URL,
)

DATASETS["spip"] = (SPIP_ABOUT,)
GROUPS.update(
    {
        ("spip", "emoney_value"): (EM_UE,),
        ("spip", "emoney_volume"): (EM_UE,),
        ("spip", "emoney_instruments"): (EM_UE,),
        ("spip", "emoney_float"): (EM_UE,),
        ("spip", "emoney_outstanding"): (EM_UE,),
        ("spip", "cards_value"): (CARD_APMK,),
        ("spip", "cards_volume"): (CARD_APMK,),
        ("spip", "cards_outstanding"): (CARD_APMK,),
        ("spip", "money"): (PS_MONEY_SUPPLY,),
        ("spip", "rtgs_value"): (PS_RTGS,),
        ("spip", "rtgs_volume"): (PS_RTGS,),
        ("spip", "cash_intensity"): (PS_UYD,),
    }
)
SERIES.update(
    {
        "bi_emoney.value": (EM_TXN,),
        "bi_emoney.value_purchase": (EM_PURCHASE_VALUE,),
        "bi_emoney.value_topup": (EM_TOPUP_VALUE,),
        "bi_emoney.volume": (EM_TXN,),
        "bi_emoney.volume_purchase": (EM_PURCHASE_VOLUME,),
        "bi_emoney.volume_topup": (EM_TOPUP_VOLUME,),
        "bi_emoney.instruments": (EM_INSTRUMENTS,),
        "bi_emoney.instruments_chip": (EM_CHIP,),
        "bi_emoney.instruments_server": (EM_SERVER,),
        "bi_emoney.float_funds": (EM_FLOAT, EM_FLOAT_POSITION),
        "bi_emoney.float_funds_bank": (EM_FLOAT, EM_ISSUER),
        "bi_emoney.float_funds_nonbank": (EM_FLOAT, EM_ISSUER),
        "bi_payment_system.emoney_instruments_outstanding": (EM_NONBANK_INSTRUMENTS,),
        "bi_card_transactions.atm_debit.value": (CARD_ATM, CARD_DEBIT, CARD_ATM_VALUE),
        "bi_card_transactions.atm_debit.volume": (CARD_ATM, CARD_DEBIT, CARD_ATM_VOLUME),
        "bi_card_transactions.atm_debit.cards": (CARD_ATM, CARD_DEBIT, CARD_ATM_COUNT),
        "bi_card_transactions.credit.value": (CARD_CREDIT, CARD_CREDIT_VALUE),
        "bi_card_transactions.credit.volume": (CARD_CREDIT, CARD_CREDIT_VOLUME),
        "bi_card_transactions.credit.cards": (CARD_CREDIT, CARD_CREDIT_COUNT),
        "bi_payment_system.currency_in_circulation": (PS_COB, PS_CURRENCY),
        "bi_payment_system.narrow_money": (PS_M1, PS_M1_FOOTNOTE),
        "bi_payment_system.demand_deposits_rupiah": (PS_GIRO,),
        "bi_payment_system.rtgs.value": (PS_RTGS_VALUE,),
        "bi_payment_system.rtgs.volume": (PS_RTGS_VOLUME,),
        "bi_payment_system.currency_to_gdp": (PS_RATIO_GDP,),
        "bi_payment_system.currency_to_household_consumption": (PS_RATIO_HOUSEHOLD,),
    }
)


# ---------------------------------------------------------------------------
# OJK -- Statistik Perbankan Indonesia (third-party funds)

_OJK_SPI = "Statistik Perbankan Indonesia, Juni 2025 (Otoritas Jasa Keuangan), Kata Pengantar / Foreword"
_OJK_SPI_URL = (
    "https://www.ojk.go.id/id/kanal/perbankan/data-dan-statistik/statistik-perbankan-indonesia/Documents/Pages/"
    "Statistik-Perbankan-Indonesia---Juni-2025/STATISTIK%20PERBANKAN%20INDONESIA%20%20-Juni%202025.pdf"
)
_UU_PERBANKAN = "Undang-Undang No. 10 Tahun 1998 tentang Perbankan, Pasal 1 (copy hosted by OJK)"
_UU_PERBANKAN_URL = "https://www.ojk.go.id/sustainable-finance/id/peraturan/undang-undang/Documents/UU_NO_10_1998%20Tentang%20Perbankan.PDF"

OJK_SPI = Definition(
    term="Statistik Perbankan Indonesia (SPI) / Indonesia Banking Statistics",
    text=(
        "Statistik Perbankan Indonesia (SPI) merupakan media publikasi yang menyajikan data mengenai perbankan Indonesia. "
        "SPI diterbitkan secara bulanan oleh Otoritas Jasa Keuangan untuk memberikan gambaran perkembangan perbankan di Indonesia."
    ),
    source=_OJK_SPI, url=_OJK_SPI_URL,
    english=(
        "The Indonesia Banking Statistic is a publication media that provides data of Indonesian Banking. The SPI is "
        "published monthly by Financial Services Authority to provide an overview of banking development in Indonesia."
    ),
)

OJK_PORTAL = Definition(
    term="Peralihan SPI ke Portal Data (Juli 2025)",
    text=(
        "Terhitung sejak publikasi data periode Juli 2025, penyajian Statistik Perbankan Indonesia (SPI) dialihkan "
        "sepenuhnya ke Portal Data Sektor Jasa Keuangan Terintegrasi (“Portal Data”) yang dapat diakses pada tautan "
        "https://data.ojk.go.id/SJKPublic\n\n"
        "Publikasi statistik dalam format PDF/Excel untuk periode sebelum Juli 2025 tetap dapat diakses dan diunduh pada halaman ini."
    ),
    source="Otoritas Jasa Keuangan, Statistik Perbankan Indonesia (publication page)",
    url="https://www.ojk.go.id/id/kanal/perbankan/data-dan-statistik/statistik-perbankan-indonesia/Default.aspx",
    note="This is why the collector, which reads the PDF and Excel releases, finds nothing after June 2025.",
)

_OJK_DPK_NOTE = (
    "OJK's SPI names 'Dana Pihak Ketiga' only by its abbreviation ('DPK : Dana Pihak Ketiga' / 'Third Party Funds') "
    "and by the rows of its table 1.28.a; the deposit types are defined in the Banking Law, quoted here. "
    "Undang-Undang No. 4 Tahun 2023, Pasal 14, re-enacts these definitions."
)

OJK_DPK = Definition(
    term="Dana Pihak Ketiga (DPK) / Third Party Funds: Simpanan",
    text=(
        "5. Simpanan adalah dana yang dipercayakan oleh masyarakat kepada bank berdasarkan perjanjian penyimpanan dana "
        "dalam bentuk giro, deposito, sertifikat deposito, tabungan dan atau bentuk lainnya yang dipersamakan dengan itu;"
    ),
    source=_UU_PERBANKAN, url=_UU_PERBANKAN_URL, note=_OJK_DPK_NOTE,
)
OJK_GIRO = Definition(
    term="Giro / Demand Deposits",
    text=(
        "6. Giro adalah simpanan yang penarikannya dapat dilakukan setiap saat dengan menggunakan cek, bilyet giro, "
        "sarana perintah pembayaran lainnya, atau dengan pemindahbukuan;"
    ),
    source=_UU_PERBANKAN, url=_UU_PERBANKAN_URL,
)
OJK_TABUNGAN = Definition(
    term="Tabungan / Saving Deposits",
    text=(
        "9. Tabungan adalah simpanan yang penarikannya hanya dapat dilakukan menurut Syarat tertentu yang disepakati, "
        "tetapi tidak dapat ditarik dengan cek, bilyet giro, dan atau alat lainnya yang dipersamakan dengan itu;"
    ),
    source=_UU_PERBANKAN, url=_UU_PERBANKAN_URL,
)
OJK_DEPOSITO = Definition(
    term="Deposito (Simpanan Berjangka) / Time Deposits",
    text=(
        "7. Deposito adalah simpanan yang penarikannya hanya dapat dilakukan pada waktu tertentu berdasarkan perjanjian "
        "Nasabah Penyimpan dengan bank;"
    ),
    source=_UU_PERBANKAN, url=_UU_PERBANKAN_URL,
    note="SPI's row is 'Simpanan Berjangka / Time Deposits'.",
)

DATASETS["ojk"] = (OJK_SPI, OJK_PORTAL)
SERIES.update(
    {
        "ojk_dpk.composition.giro": (OJK_GIRO,),
        "ojk_dpk.composition.tabungan": (OJK_TABUNGAN,),
        "ojk_dpk.composition.simpanan_berjangka": (OJK_DEPOSITO,),
        "ojk_dpk.composition.total": (OJK_DPK,),
    }
)

# ---------------------------------------------------------------------------
# ASPI QRIS (standard set by Bank Indonesia)

_PADG_QRIS = "Peraturan Anggota Dewan Gubernur No. 21/18/PADG/2019 tentang Implementasi Standar Nasional Quick Response Code untuk Pembayaran, Pasal 1"
_PADG_QRIS_URL = "https://www.bi.go.id/id/publikasi/peraturan/Documents/padg_211819.pdf"

QRIS_STANDARD = Definition(
    term="QRIS (Quick Response Code Indonesian Standard)",
    text=(
        "5. Standar Nasional QR Code Pembayaran (Quick Response Code Indonesian Standard) yang selanjutnya disebut QRIS "
        "adalah Standar QR Code Pembayaran yang ditetapkan oleh Bank Indonesia untuk digunakan dalam memfasilitasi "
        "transaksi pembayaran di Indonesia."
    ),
    source=_PADG_QRIS, url=_PADG_QRIS_URL,
)

QRIS_ABOUT = Definition(
    term="Pengantar QRIS (Bank Indonesia)",
    text=(
        "Quick Response Code Indonesian Standard (QRIS) atau biasa disingkat QRIS (dibaca “Kris”) merupakan standar QR "
        "Code Pembayaran yang ditetapkan oleh Bank Indonesia untuk digunakan dalam memfasilitasi transaksi pembayaran di "
        "Indonesia. QRIS dikembangkan oleh industri sistem pembayaran bersama dengan Bank Indonesia agar proses transaksi "
        "dengan QR Code dapat lebih cepat, mudah, murah, aman, dan andal (CEMUMUAH). Semua Penyedia Jasa Pembayaran (PJP) "
        "yang akan menggunakan QR Code Pembayaran wajib menerapkan QRIS."
    ),
    source="Bank Indonesia, Quick Response Code Indonesian Standard (QRIS): Pengantar",
    url="https://www.bi.go.id/id/fungsi-utama/sistem-pembayaran/ritel/kanal-layanan/QRIS/default.aspx",
)

QRIS_TXN = Definition(
    term="Transaksi QRIS",
    text="6. Transaksi QRIS adalah transaksi pembayaran yang difasilitasi dengan QR Code Pembayaran berdasarkan QRIS.",
    source=_PADG_QRIS, url=_PADG_QRIS_URL,
    note=(
        "Neither Bank Indonesia's regulation nor ASPI's statistics page defines the volume or the nominal value of QRIS "
        "transactions; ASPI's charts label them 'Volume Transaksi QRIS (Jutaan)' and 'Nominal/Nilai Transaksi QRIS (Triliun IDR)'."
    ),
)

QRIS_OFF_US = Definition(
    term="Transaksi off us (antar PJP) / on us (intra PJP)",
    text=(
        "Biaya transfer dengan QRIS TUNTAS ditetapkan sebesar Rp2.500/transaksi, namun untuk transaksi dengan nominal "
        "sampai dengan Rp100 ribu dikenakan biaya hanya sebesar Rp2.000/transaksi untuk mendukung inklusi. Biaya ini "
        "dikenakan untuk transaksi off us (antar Penyedia Jasa Pembayaran/PJP), sedangkan transaksi on us (intra PJP) "
        "tidak dikenakan biaya."
    ),
    source="Bank Indonesia, QRIS Tuntas (Tarik Tunai, Transfer, dan Setor Tunai)",
    url="https://www.bi.go.id/id/fungsi-utama/sistem-pembayaran/ritel/kanal-layanan/qris/qris-tuntas/default.aspx",
    note=(
        "No Bank Indonesia or ASPI document defines on-us and off-us QRIS transactions. This fee rule on BI's QRIS TUNTAS "
        "page is the nearest official wording: it glosses off us as 'antar Penyedia Jasa Pembayaran/PJP' and on us as "
        "'intra PJP'. ASPI's charts label the series 'Volume Off-Us' and 'Amount Off-Us'."
    ),
)

DATASETS["qris"] = (QRIS_STANDARD, QRIS_ABOUT)
SERIES.update(
    {
        "qris_transactions.value.total": (QRIS_TXN,),
        "qris_transactions.volume.total": (QRIS_TXN,),
        "qris_transactions.value.off_us": (QRIS_TXN, QRIS_OFF_US),
        "qris_transactions.volume.off_us": (QRIS_TXN, QRIS_OFF_US),
    }
)

# ---------------------------------------------------------------------------
# Bank Indonesia -- PIHPS (weekly food prices)

_PIHPS_FAQ = "Bank Indonesia, PIHPS Nasional: Penjelasan Indikator, Data dan Informasi (FAQ)"
_PIHPS_FAQ_URL = "https://www.bi.go.id/hargapangan/Informasi/FAQ"

PIHPS_ABOUT = Definition(
    term="Pusat Informasi Harga Pangan Strategis (PIHPS) Nasional",
    text=(
        "PIHPS Nasional adalah sistem informasi berbasis digital yang dikelola oleh Bank Indonesia sejak tahun 2016, dan "
        "berfungsi untuk menghimpun serta mendiseminasikan harga komoditas pangan strategis di seluruh provinsi di "
        "Indonesia. Adapun informasi harga yang disajikan mencakup komoditas pangan strategis seperti beras, telur ayam "
        "ras, daging ayam ras, daging sapi, cabai merah, cabai rawit, bawang merah, bawang putih, minyak goreng, dan gula "
        "pasir. Hingga tahun 2023, survei pemantauan harga PIHPS Nasional telah mencakup empat jenis pasar, yakni pasar "
        "tradisional, pasar modern, pedagang besar, dan produsen."
    ),
    source="Bank Indonesia, Siaran Pers No.25/174/DKom, 27 Juni 2023: Pusat Informasi Harga Pangan Strategis (PIHPS) Nasional Hadir di Website BI",
    url="https://www.bi.go.id/id/publikasi/ruang-media/news-release/Pages/sp_2517423.aspx",
)

PIHPS_PRICE = Definition(
    term="Konsep Harga (harga pasar, kota/kab, provinsi, nasional)",
    text=(
        "Harga pasar tradisional adalah rata-rata harga komoditi tertentu dari dua sampel pedagang\n\n"
        "Harga di kota/kab adalah rata-rata harga komoditi tertentu dari seluruh pasar yang disurvei\n\n"
        "Harga di provinsi adalah rata-rata harga komoditi tertentu dari seluruh kota/kab yang disurvei\n\n"
        "Harga nasional adalah rata-rata harga komoditi tertentu seluruh pedagang yang disurvei"
    ),
    source=_PIHPS_FAQ + ", D. Harga: Konsep Harga", url=_PIHPS_FAQ_URL,
    note="The dashboard's workbooks carry the national averages, weekly, for each market level.",
)

PIHPS_SURVEY = Definition(
    term="Survei Harga Pangan Harian: Pasar Tradisional",
    text=(
        "Pencacahan data dilakukan setiap hari kerja (Senin s.d. Jumat) pada pukul 09.00 s.d. 11.00 wib. Harga yang "
        "disurvei adalah harga eceran hasil transaksi yang terjadi antara penjual (pedagang eceran) dan pembeli "
        "(konsumen). Harga yang dilaporkan adalah harga dalam satuan standar yang telah ditetapkan oleh Bank Indonesia. "
        "Pelaporan disampaikan secara harian pada hari kerja (Senin s.d. Jumat) ke Bank Indonesia pada pukul 10.00 -12.00 "
        "wib, sehingga diharapkan seluruh data dapat dipublikasikan pada pukul 13.00 wib (dengan asumsi tidak terdapat "
        "kendala teknis di lapangan).\n\n"
        "Jumlah pedagang yang disurvei setiap pasar tradisional adalah 2 pedagang untuk setiap komoditi (2 data harga). "
        "Pemilihan pedagang bersifat tetap/panel untuk menjamin kontinuitas pencacahan, serta berlokasi tidak terlalu "
        "berdekatan antar satu pedagang dengan pedagang lainnya untuk mengantisipasi kecenderungan homogenitas harga."
    ),
    source=_PIHPS_FAQ + ", B. Metodologi Statistik", url=_PIHPS_FAQ_URL,
    note=(
        "BI publishes this methodology for the traditional-market survey only; no definition or methodology is "
        "published for the modern-market and wholesale (pedagang besar) levels."
    ),
)

PIHPS_COMMODITIES = Definition(
    term="Komoditi pangan strategis (10 komoditas)",
    text=(
        "Komoditas pangan yang disurvei dan disajikan di Pusat Informasi Harga Pangan Strategis adalah 10 komoditas pangan "
        "yang memiliki kontribusi signifikan dalam pembentukan angka inflasi (strategis), khususnya untuk inflasi volatile "
        "food, dengan rincian sebagai berikut:\n\n"
        "Beras: terdiri dari 6 kualitas beras berdasarkan level harga yaitu 2 jenis beras kualitas biasa/bawah, 2 jenis "
        "beras kualitas sedang, dan 2 jenis beras kualitas premium. Pemilihan jenis beras berdasarkan jenis yang paling "
        "banyak dikonsumsi masyarakat di kota/kabupaten lokasi sampel. Untuk harga beras kualitas biasa/bawah tidak "
        "termasuk beras raskin/rastra. Harga yang dilaporkan adalah harga per kg.\n\n"
        "Bawang merah: hanya mancakup 1 kualitas bawang merah yaitu lokal dengan kualitas sedang. Harga yang dilaporkan "
        "adalah harga per kg.\n\n"
        "Bawang putih: hanya 1 kualitas bawang putih yaitu bawang putih dalam bonggol kualitas sedang. Harga yang "
        "dilaporkan adalah harga per kg.\n\n"
        "Cabai merah: terdiri dari 2 kualitas, yaitu cabai merah besar dan cabai merah keriting kualitas segar. Harga yang "
        "dilaporkan adalah harga per kg.\n\n"
        "Cabai rawit: terdiri dari 2 kualitas, yaitu cabai rawit merah dan rawit hijau dengan kualitas segar. Harga yang "
        "dilaporkan adalah harga per kg.\n\n"
        "Daging sapi: terdiri dari 2 kualitas, yaitu daging sapi has luar dan has dalam dengan kualitas segar. Harga yang "
        "dilaporkan adalah harga per kg.\n\n"
        "Daging ayam ras: hanya 1 kualitas yaitu daging ayam ras tanpa jeroan dengan kualitas segar. Harga yang dilaporkan "
        "adalah harga per kg.\n\n"
        "Telur ayam ras: hanya 1 kualitas yaitu telur ayam kualitas segar. Harga yang dilaporkan adalah harga per kg.\n\n"
        "Gula pasir: teridiri dari 2 kualitas, yaitu kualitas lokal/curah warna kuning dan kualitas premium. Harga yang "
        "dilaporkan adalah harga per kg.\n\n"
        "Minyak goreng: terdiri dari 3 kualitas, yaitu 1 kualitas lokal/curah dan 2 kualitas kemasan isi ulang. Harga yang "
        "dilaporkan adalah harga per liter."
    ),
    source=_PIHPS_FAQ + ", A. Komoditi Pangan Strategis", url=_PIHPS_FAQ_URL,
)

DATASETS["pihps"] = (PIHPS_ABOUT, PIHPS_PRICE, PIHPS_SURVEY, PIHPS_COMMODITIES)

# ---------------------------------------------------------------------------
# Magpie IQ -- e-commerce GMV (a vendor's own definitions; the source language is English)

_MAGPIE_METHOD = "Magpie IQ Methodology: How We Measure Ecommerce Markets"
_MAGPIE_METHOD_URL = "https://magpieiq.com/methodology/"

GMV_METHOD = Definition(
    term="Sales Value (GMV)",
    text=(
        "Sales Value (GMV) = Final post-discount price × Units sold (Terjual)\n\n"
        "Price is held constant at the latest snapshot captured within the reporting period. This means that if a SKU was "
        "priced at Rp 85,000 at the time of capture and the platform's Terjual counter shows 1,200 units sold, GMV for "
        "that SKU is recorded as Rp 102,000,000 for the period. Units sold is sourced from the platform's cumulative "
        "\"terjual\" counter — the publicly visible sold count. Magpie IQ calculates the incremental change in this "
        "counter between snapshots to derive period-specific unit volume.\n\n"
        "This approach differs from platform-reported GMV. Platform-reported figures often include cancelled orders, "
        "returns, and pre-shipment adjustments that are not publicly visible at the product listing level. Magpie IQ's GMV "
        "is a floor estimate based on observable data — it is consistent and comparable across time and across platforms, "
        "but it is not a certified sales figure and should not be treated as one."
    ),
    source=_MAGPIE_METHOD + ", GMV calculation", url=_MAGPIE_METHOD_URL,
)

GMV_SHOPEE = Definition(
    term="Shopee Indonesia GMV",
    text=(
        "Total estimated Shopee Indonesia GMV, USD, all categories.\n\n"
        "Methodology. Total estimated Shopee Indonesia GMV by month, summed across all categories. Figures are estimates and may be revised."
    ),
    source="Magpie IQ, Shopee GMV Trend Indonesia 2026", url="https://magpieiq.com/data/shopee-gmv-trend-indonesia-2026/",
)
GMV_TIKTOK = Definition(
    term="TikTok Shop Indonesia GMV",
    text=(
        "Total estimated TikTok Shop Indonesia GMV, USD, all categories.\n\n"
        "Methodology. Total estimated TikTok Shop Indonesia GMV by month, summed across all categories. Figures are estimates and may be revised."
    ),
    source="Magpie IQ, TikTok Shop GMV Trend Indonesia 2026", url="https://magpieiq.com/data/tiktok-shop-gmv-trend-indonesia-2026/",
)
GMV_TOKOPEDIA = Definition(
    term="Tokopedia Indonesia GMV",
    text=(
        "Total estimated Tokopedia Indonesia GMV, USD (the classic marketplace, distinct from Tokopedia | Shop).\n\n"
        "Methodology. Total estimated Tokopedia Indonesia GMV by month, summed across all categories. Figures are estimates and may be revised."
    ),
    source="Magpie IQ, Tokopedia GMV Trend Indonesia 2026", url="https://magpieiq.com/data/tokopedia-gmv-trend-indonesia-2026/",
)
GMV_TOTAL = Definition(
    term="Indonesia e-commerce GMV, all platforms",
    text="Total estimated GMV across six marketplaces, USD. The October and December peaks are the 10.10 and year-end sales seasons.",
    source="Magpie IQ, Indonesia E-commerce Market Size & Growth 2024–2026",
    url="https://magpieiq.com/data/indonesia-ecommerce-market-size-2026/",
)
GMV_SCOPE = Definition(
    term="Platform expansion effects",
    text=(
        "When a new platform is added to Magpie IQ's coverage, total market GMV figures change. A 2021 market size figure "
        "based on Shopee and Lazada is not directly comparable to a 2025 figure based on five platforms. Magpie IQ reports "
        "always specify the platform scope."
    ),
    source=_MAGPIE_METHOD + ", Platform expansion effects", url=_MAGPIE_METHOD_URL,
)

DATASETS["ecommerce"] = (GMV_METHOD,)
SERIES.update(
    {
        "ecommerce_gmv.shopee": (GMV_SHOPEE,),
        "ecommerce_gmv.tiktok_shop": (GMV_TIKTOK,),
        "ecommerce_gmv.tokopedia": (GMV_TOKOPEDIA,),
        "ecommerce_gmv.total_market": (GMV_TOTAL, GMV_SCOPE),
    }
)

# ---------------------------------------------------------------------------
# ibid (Astra) vehicle auctions

IBID_TERMS = Definition(
    term="Ketentuan Umum IBID: Objek Lelang, Harga Terbentuk, kondisi objek lelang",
    text=(
        "Objek Lelang adalah berupa mobil, motor, alat berat, Scrap, Properti Tanah dan Bangunan, dan barang elektronik "
        "yang ditawarkan dalam lelang yang diselenggarakan oleh IBID melalui Platform IBID.\n\n"
        "Harga Terbentuk adalah harga penawaran tertinggi yang diajukan oleh Perserta Lelang yang telah disahkan sebagai "
        "pemenang Lelang oleh Pejabat Lelang.\n\n"
        "Objek Lelang dilelang oleh IBID dalam kondisi apa adanya (“as is”)."
    ),
    source="IBID (PT Balai Lelang Serasi), Ketentuan Umum, versi V15, 11 Agustus 2026",
    url="https://www.ibid.astra.co.id/prosedur/ketentuan-umum",
    note=(
        "ibid publishes no definition of the price shown on a lot card, of its vehicle grades (its terms only mention "
        "'grade hasil inspeksi Astra Car Valuation (ACV)' A and B) or of a lot. The only price it defines is the hammer "
        "price, Harga Terbentuk; the dashboard's prices are the ones shown on the lot cards, not confirmed hammer prices."
    ),
)

DATASETS["ibid"] = (IBID_TERMS,)


# ---------------------------------------------------------------------------
# Bank Indonesia -- SEKI (GDP by expenditure, republished from BPS; deposits by owner group)

_BI_PDB = "Metadata SEKI: Produk Domestik Bruto (PDB) (Bank Indonesia)"
_BI_PDB_URL = "https://www.bi.go.id/id/statistik/Metadata/SEKI/Documents/14_Produk-Domestik-Bruto.pdf"
_BI_PDB_EN = "SEKI Metadata: Gross Domestic Product (Bank Indonesia, July 2024)"
_BI_PDB_EN_URL = "https://www.bi.go.id/en/statistik/Metadata/SEKI/Documents/Gross-Domestic-Product.pdf"
_BI_DEP = "Metadata SEKI: Simpanan Masyarakat (Bank Indonesia, Juni 2025)"
_BI_DEP_URL = "https://www.bi.go.id/id/statistik/Metadata/SEKI/Documents/04_Simpanan-Masyarakat.pdf"
_BI_DEP_EN = "SEKI Metadata: Private Deposit on Commercial and Rural Banks (Bank Indonesia)"
_BI_DEP_EN_URL = "https://www.bi.go.id/en/statistik/Metadata/SEKI/Documents/Private-Deposit-.pdf"
_BI_NAB = "Metadata SEKI: Neraca Analitis Bank Umum dan BPR (Bank Indonesia)"
_BI_NAB_URL = "https://www.bi.go.id/id/statistik/Metadata/SEKI/Documents/02_Neraca-Analitis-Bank-Umum-dan-BPR.pdf"
_BI_NAB_EN = "SEKI Metadata: Analytical Balance Sheet of Commercial and Rural Banks (Bank Indonesia)"
_BI_NAB_EN_URL = "https://www.bi.go.id/en/statistik/Metadata/SEKI/Documents/Analytical-Balance-Sheet-of-Commercial-and-Rural-Banks-.pdf"
_LBUT = "Peraturan Anggota Dewan Gubernur No. 21/23/PADG/2019 tentang Laporan Bank Umum Terintegrasi, Lampiran II: Golongan Pihak Lawan"
_LBUT_URL = "https://www.bi.go.id/id/publikasi/peraturan/Pages/PADG_212319.aspx"
_BPS_LNPRT = "BPS, Neraca Lembaga Non Profit yang Melayani Rumahtangga Tahun 2011-2013 (Katalog 9506002), 2.3 Konsep dan Definisi"
_BPS_LNPRT_URL = "https://www.bps.go.id/id/publication/2024/10/31/44894a2bac8fc1804b37cd4b/neraca-lembaga-non-profit-yang-melayani-rumahtangga--2021-2023.html"


def _sirusa(number: int, title: str) -> tuple[str, str]:
    return (f"BPS, Sistem Informasi Rujukan Statistik (SIRUSA), indikator {number}: {title}", f"https://sirusa.bps.go.id/metadata/indikator/{number}")


SEKI_ABOUT = Definition(
    term="Statistik Ekonomi dan Keuangan Indonesia (SEKI) / Indonesian Economic and Financial Statistics",
    text=(
        "SEKI merupakan publikasi bulanan yang diterbitkan oleh Bank untuk memberikan informasi tentang data ekonomi dan "
        "keuangan Indonesia. Publikasi ini berguna bagi masyarakat untuk memahami perkembangan ekonomi dan keuangan "
        "Indonesia. Data dalam SEKI disusun dengan menggunakan data primer dari Bank Indonesia serta data sekunder dari "
        "lembaga lain seperti Kementerian Keuangan, Badan Pusat Statistik (BPS), dan Lembaga Penjamin Simpanan (LPS). "
        "Penyusunan data dalam SEKI telah menggunakan metodologi standar internasional sehingga dapat dibandingkan dengan "
        "data di negara lain. Publikasi SEKI mencakup empat sektor yaitu sektor moneter, sektor keuangan pemerintah, "
        "sektor riil, dan sektor eksternal. Data dalam SEKI disajikan dengan periodisasi yang disesuaikan dengan "
        "ketersediaan data dari masing-masing sektor."
    ),
    source="Bank Indonesia, Statistik Ekonomi dan Keuangan Indonesia (SEKI)",
    url="https://www.bi.go.id/id/statistik/ekonomi-keuangan/seki/Default.aspx",
    english=(
        "Indonesian Economic and Financial Statistics (SEKI) are published monthly by Bank Indonesia, presenting economic "
        "and financial data to help users understand economic and financial developments in Indonesia. Using primary data "
        "from Bank Indonesia and secondary data from other relevant institutions, including the Ministry of Finance, "
        "BPS-Statistics Indonesia, and Indonesia Deposit Insurance Corporation (LPS), SEKI data is compiled based on "
        "international standards and methodologies that enable cross-country data comparison. Covering four sectors, "
        "namely the monetary sector, government finance sector, real sector and external sector, the data samples apply "
        "periodisation that is adjusted to the data availability for each respective sector."
    ),
    english_source="Bank Indonesia, Indonesian Economic and Financial Statistics (SEKI)",
    english_url="https://www.bi.go.id/en/statistik/ekonomi-keuangan/seki/Default.aspx",
)

SEKI_PDB = Definition(
    term="Produk Domestik Bruto (PDB) / Gross Domestic Product (GDP)",
    text=(
        "PDB pada dasarnya merupakan jumlah nilai tambah yang dihasilkan oleh seluruh unit usaha dalam suatu negara "
        "tertentu, atau merupakan jumlah nilai barang dan jasa akhir yang dihasilkan oleh seluruh unit ekonomi.\n\n"
        "Pendekatan Pengeluaran: PDB adalah semua komponen permintaan akhir yang terdiri dari: (1) Pengeluaran Konsumsi "
        "Rumah Tangga (PK-RT), (2) Pengeluaran Konsumsi Lembaga Nonprofit yang Melayani Rumah Tangga (PK-LNPRT), (2) "
        "Pengeluaran Konsumsi Pemerintah (P-KP), (3) Pembentukan Modal Tetap Bruto (PMTB), (4) Perubahan Inventori, dan "
        "(5) Ekspor Neto (merupakan ekspor dikurangi impor).\n\n"
        "Selama ini, data PDB yang dipublikasikan oleh BPS menggunakan pendekatan produksi (lapangan usaha) dan pendekatan "
        "pengeluaran (penggunaan). Bank Indonesia tidak melakukan pengolahan lebih lanjut terhadap data PDB."
    ),
    source=_BI_PDB, url=_BI_PDB_URL,
    english=(
        "GDP is the amount of additional value produced by all business units in a particular country or the number of "
        "goods and services produced by all economic units. GDP is presented in current prices and constant prices.\n\n"
        "The Expenditure Approach: GDP by expenditure explains the final demand for goods and services produced in economic "
        "activities and exports and imports. The final demand consists of Household Final Consumption Expenditure (HFCE), "
        "Nonprofit Institutions Serving Households (NPISHs) Final Consumption Expenditure, General Government Final "
        "Consumption Expenditure (GGFCE), Gross Fixed Capital Formation (GFCF), Changes in Inventories (CI), and "
        "Exports-Imports of Goods and Services.\n\n"
        "Currently, GDP data published by Statistics Indonesia-BPS is calculated using the production approach and "
        "expenditure approach. Bank Indonesia does not reprocess the GDP data."
    ),
    english_source=_BI_PDB_EN, english_url=_BI_PDB_EN_URL,
)

SEKI_PRICE_BASIS = Definition(
    term="Atas dasar harga berlaku / harga konstan (current prices / constant prices)",
    text=(
        "PDB atas dasar harga berlaku menggambarkan nilai tambah barang dan jasa yang dihitung menggunakan harga pada "
        "tahun berjalan, sedangkan PDB atas dasar harga konstan menunjukkan nilai tambah barang dan jasa tersebut yang "
        "dihitung menggunakan harga yang berlaku pada satu tahun tertentu sebagai tahun dasar.\n\n"
        "PDB menurut harga berlaku digunakan untuk mengetahui kemampuan sumber daya ekonomi, pergeseran, dan struktur "
        "ekonomi suatu negara. Sementara itu, PDB atas dasar harga konstan digunakan untuk mengetahui pertumbuhan ekonomi "
        "secara riil dari tahun ke tahun atau pertumbuhan ekonomi yang tidak dipengaruhi oleh faktor harga."
    ),
    source=_BI_PDB, url=_BI_PDB_URL,
    english=(
        "GDP at current price is often referred to as nominal GDP, which is the value added of goods and services produced "
        "by a country in a period of time according to the prices prevailing at that time.\n\n"
        "Meanwhile, GDP at constant prices, often referred to as real GDP, is the value added of goods and services "
        "calculated using prices in a given year as the base year."
    ),
    english_source=_BI_PDB_EN, english_url=_BI_PDB_EN_URL,
)

SEKI_BASE_YEAR = Definition(
    term="Tahun dasar 2010 / Base year 2010",
    text=(
        "Sejak triwulan IV-2014, data PDB disajikan menggunakan tahun dasar 2010. Perubahan tahun dasar dari 2000 menjadi "
        "2010 dilakukan karena struktur perekonomian Indonesia dalam kurun waktu tersebut telah mengalami perubahan yang "
        "signifikan, meliputi perkembangan harga, cakupan komoditas produksi dan konsumsi serta jenis dan kualitas barang "
        "maupun jasa yang dihasilkan."
    ),
    source=_BI_PDB, url=_BI_PDB_URL,
    english=(
        "Since the fourth quarter of 2014, GDP data has been presented using 2010 as the base year. The base year was "
        "revised from 2000 to 2010 due to significant changes in Indonesia's economic structure during that period in "
        "terms of prices, the scope of production, commodities, and consumption, and the types and quality of goods and "
        "services produced."
    ),
    english_source=_BI_PDB_EN, english_url=_BI_PDB_EN_URL,
)

_s, _u = _sirusa(132284, "Produk Domestik Bruto Atas Dasar Harga Berlaku")
BPS_PDB_CURRENT = Definition(
    term="Produk Domestik Bruto Atas Dasar Harga Berlaku (BPS)",
    text=(
        "Jumlah penggunaan akhir barang dan jasa yang dihasilkan oleh berbagai kegiatan ekonomi untuk memenuhi pengeluaran "
        "konsumsi akhir, pembentukan modal, perubahan inventori, dan ekspor serta impor yang dihitung menurut harga yang "
        "berlaku pada saat PDB tersebut dihitung.\n\n"
        "Produk Domestik Bruto atas dasar harga berlaku jenis pengeluaran merupakan penambahan Pengeluaran Konsumsi Rumah "
        "Tangga (PKRT), Pengeluaran Konsumsi Lembaga Nonprofit yang melayani Rumah Tangga (PKLNPRT), Pengeluaran Konsumsi "
        "Pemerintah (PKP), Pembentukan Modal Tetap Bruto (PMTB), Perubahan Inventori (PI), dan Ekspor barang dan jasa yang "
        "kemudian dikurangi Impor barang dan jasa yang dihitung dengan menggunakan atas dasar harga berlaku."
    ),
    source=_s, url=_u,
)
_s, _u = _sirusa(132279, "Produk Domestik Bruto Atas Dasar Harga Konstan 2010")
BPS_PDB_CONSTANT = Definition(
    term="Produk Domestik Bruto Atas Dasar Harga Konstan 2010 (BPS)",
    text=(
        "Jumlah penggunaan akhir barang dan jasa yang dihasilkan oleh berbagai kegiatan ekonomi untuk memenuhi pengeluaran "
        "konsumsi akhir, pembentukan modal, perubahan inventori, dan ekspor serta impor yang dihitung menurut harga konstan "
        "(harga pada suatu tahun dasar yang ditetapkan).\n\n"
        "Produk Domestik Bruto atas dasar harga konstan jenis pengeluaran merupakan penambahan Pengeluaran Konsumsi Rumah "
        "Tangga (PKRT), Pengeluaran Konsumsi Lembaga Nonprofit yang melayani Rumah Tangga (PKLNPRT), Pengeluaran Konsumsi "
        "Pemerintah (PKP), Pembentukan Modal Tetap Bruto (PMTB), Perubahan Inventori (PI), dan Ekspor barang dan jasa yang "
        "kemudian dikurangi Impor barang dan jasa yang dihitung dengan menggunakan atas dasar harga konstan."
    ),
    source=_s, url=_u,
)
_s, _u = _sirusa(50661, "Pengeluaran Konsumsi Rumah Tangga")
BPS_PKRT = Definition(
    term="Pengeluaran Konsumsi Rumah Tangga (BPS)",
    text=(
        "Pengeluaran konsumsi rumah tangga adalah pengeluaran atas barang dan jasa oleh rumah tangga residen untuk tujuan "
        "konsumsi akhir, tidak termasuk pengeluaran rumah tangga untuk barang modal.\n\n"
        "Konsumsi rumah tangga = konsumsi makanan dan minuman, selain restoran + konsumsi pakaian, alas kaki, dan jasa "
        "perawatan + konsumsi perumahan dan perabot rumah tangga + konsumsi kesehatan dan pendidikan + konsumsi "
        "transportasi dan komunikasi + konsumsi restoran dan hotel + konsumsi lainnya"
    ),
    source=_s, url=_u,
)
_s, _u = _sirusa(132284, "Produk Domestik Bruto Atas Dasar Harga Berlaku")
SEKI_TOTAL_CONSUMPTION = Definition(
    term="Pengeluaran Konsumsi (total row) / Consumption Expenditures",
    text=(
        "PDB atas dasar harga berlaku menggambarkan nilai produk barang dan jasa yang digunakan sebagai konsumsi akhir "
        "oleh rumah tangga, Lembaga Non-profit yang melayani Rumah Tangga (LNPRT), dan pemerintah ditambah dengan investasi "
        "(pembentukan modal tetap bruto dan perubahan inventori), serta ekspor neto (ekspor dikurang impor) yang berlaku "
        "pada setiap tahun, PDB atas dasar harga berlaku dapat digunakan untuk melihat pergeseran dan struktur ekonomi "
        "suatu wilayah pada waktu tertentu."
    ),
    source=_s, url=_u,
    note=(
        "Neither Bank Indonesia nor BPS defines the table's 'Pengeluaran Konsumsi' / 'Consumption Expenditures' row "
        "itself. In BI's file it is the sum of the three rows indented beneath it: Rumah Tangga, Konsumsi LNPRT and Pemerintah."
    ),
)

SEKI_PKRT = Definition(
    term="Pengeluaran Konsumsi Rumah Tangga / Household Final Consumption Expenditure (HFCE)",
    text="Pengeluaran Konsumsi Rumah Tangga, pengeluaran atas barang dan jasa oleh rumah tangga untuk tujuan konsumsi.",
    source=_BI_PDB, url=_BI_PDB_URL,
    english=(
        "1. Household Final Consumption Expenditure (HFCE) cover all expenditures for goods and services consumption "
        "subtracted by net second-hand and waste goods selling carried out by the household in one year."
    ),
    english_source=_BI_PDB_EN, english_url=_BI_PDB_EN_URL,
)

BPS_LNPRT = Definition(
    term="Lembaga Non Profit yang Melayani Rumahtangga (LNPRT) (BPS)",
    text=(
        "Sehingga LNPRT adalah lembaga yang menyediakan barang dan jasa secara gratis atau pada harga yang tidak berarti "
        "secara ekonomi kepada anggotanya atau kelompok rumahtangga dan tidak dikontrol oleh pemerintah. Output LNPRT yang "
        "menyediakan jasa ke individu anggota atau rumahtangga dihitung sebagai pengeluaran konsumsi akhir LNPRT dan "
        "pengeluaran akhir aktual rumahtangga."
    ),
    source=_BPS_LNPRT, url=_BPS_LNPRT_URL,
    note=(
        "BPS's SIRUSA has no standalone entry for Pengeluaran Konsumsi LNPRT; this is the concept chapter of BPS's own "
        "LNPRT accounts publication (the file BPS serves from the 2021-2023 publication page is the 2011-2013 edition)."
    ),
)

SEKI_NPISH = Definition(
    term="Konsumsi LNPRT / NPISHs final consumption expenditure",
    text=(
        "2. Nonprofit Institutions Serving Households (NPISHs) final consumption equals the value of non-market output or "
        "production costs incurred minus the sale of goods/services in carrying out service activities for the community, "
        "members of the organization, or specific community groups."
    ),
    source=_BI_PDB_EN, url=_BI_PDB_EN_URL,
    note="Bank Indonesia's Indonesian metadata names this component but gives it no definition; this is its English metadata.",
)

SEKI_PKP = Definition(
    term="Pengeluaran Konsumsi Pemerintah / General Government Final Consumption Expenditure (GGFCE)",
    text=(
        "Pengeluaran Konsumsi Pemerintah, nilai seluruh jenis output pemerintah dikurangi nilai output untuk pembentukan "
        "modal sendiri dikurangi nilai penjualan barang/jasa (baik yang harganya signifikan dan tdk signifikan secara "
        "ekonomi) ditambah nilai barang/jasa yang dibeli dari produsen pasar untuk diberikan pada rumah tangga secara "
        "gratis atau dengan harga yang tidak signifikan secara ekonomi (social transfer in kind-purchased market production)."
    ),
    source=_BI_PDB, url=_BI_PDB_URL,
    english=(
        "3. General Government Final Consumption Expenditure (GGFCE) cover civil servants' spending, depreciation, and "
        "goods spending, either by central government or regional government, excluding the income from goods and "
        "services produced. This data uses the realization of State Budget (APBN) figures."
    ),
    english_source=_BI_PDB_EN, english_url=_BI_PDB_EN_URL,
)

SEKI_PMTB = Definition(
    term="Pembentukan Modal Tetap Domestik Bruto / Gross Fixed Capital Formation (GFCF)",
    text=(
        "Pembentukan Modal Tetap Domestik Bruto, pengeluaran unit produksi untuk menambah aset tetap dikurangi dengan "
        "pengurangan aset tetap bekas. Penambahan barang modal meliputi pengadaan, pembuatan, pembelian barang modal baru "
        "dari dalam negeri dan barang modal baru maupun bekas dari luar negeri (termasuk perbaikan besar, transfer atau "
        "barter barang modal). Pengurangan barang modal meliputi penjualan barang modal (termasuk barang modal yang "
        "ditransfer atau barter kepada pihak lain)."
    ),
    source=_BI_PDB, url=_BI_PDB_URL,
    english=(
        "4. Gross Fixed Capital Formation (GFCF) covers the production and purchase of new domestic capital goods, used "
        "goods, or new foreign capital goods. The method used is the flow of goods approach."
    ),
    english_source=_BI_PDB_EN, english_url=_BI_PDB_EN_URL,
)

# -- Deposits by owner group (SEKI table I.18)

SEKI_DEPOSITS = Definition(
    term="Simpanan Masyarakat / Private Deposits",
    text=(
        "Simpanan Masyarakat adalah simpanan milik pihak ketiga bukan bank umum dan Bank Perkreditan Rakyat/BPR (termasuk "
        "penghimpunan dana dengan prinsip syariah) baik dalam rupiah maupun valuta asing yang berbentuk giro, tabungan dan "
        "simpanan berjangka. BPR saat ini tidak diperbolehkan menerima simpanan giro dan kegiatan dalam valuta asing. "
        "Dalam publikasi ini, tidak termasuk simpanan milik Pemerintah Pusat dan Bukan Penduduk."
    ),
    source=_BI_DEP, url=_BI_DEP_URL,
    english=(
        "Private Deposits are deposits owned by non-commercial banks and rural bank third parties (including deposits with "
        "the sharia principle) in rupiah and foreign currency in the form of demand deposits, saving deposits, and time "
        "deposits. Rural banks are not allowed to accept demand deposits and manage deposits in foreign currency. In this "
        "publication, Private Deposits do not include deposits from the central government and non-residents."
    ),
    english_source=_BI_DEP_EN, english_url=_BI_DEP_EN_URL,
)

SEKI_OWNER_GROUPS = Definition(
    term="Golongan Pemilik / Group of Ownership",
    text=(
        "Golongan Pemilik terdiri dari:\n"
        "o Penduduk: orang, badan hukum, atau badan lainnya, yang berdomisili atau berencana berdomisili di Indonesia "
        "sekurang-kurangnya 1 (satu) tahun, termasuk perwakilan dan staf diplomatik Republik Indonesia di luar negeri atau "
        "yang mempunyai center economic of interest di Indonesia.\n"
        "o Bukan penduduk: orang, badan hukum, atau badan lainnya, yang tidak berdomisili di Indonesia, atau berencana "
        "berdomisili di Indonesia kurang dari 1 (satu) tahun, termasuk perwakilan dan staf diplomatik asing di Indonesia, "
        "atau yang tidak mempunyai center economic of interest di Indonesia. Bukan penduduk terdiri dari perorangan dan "
        "institusi.\n"
        "o Pemerintah Pusat: Seluruh instansi pemerintah baik kementerian, lembaga maupun badan di atas/setingkat "
        "kementerian yang anggaran keuangannya merupakan bagian dari Anggaran Pendapatan dan Belanja Negara (APBN) "
        "termasuk kantor wilayah/perwakilan/jawatan dan dinas-dinas vertikalnya di daerah-daerah."
    ),
    source=_BI_DEP, url=_BI_DEP_URL,
    note=(
        "Bank Indonesia's SEKI metadata defines 'Golongan Pemilik' only at this level; the individual rows of table I.18 "
        "(Perseorangan, Badan Usaha Bukan Keuangan Milik Swasta and Milik Negara, Lembaga Keuangan Lainnya, Pemerintah "
        "Daerah, Sektor Swasta Lainnya, Koperasi, Yayasan dan Badan Sosial) are not defined in any SEKI metadata. The "
        "entries below quote BI's reporting guidance for the banks' source report (LBUT), whose categories BI does not "
        "itself map onto the table's rows."
    ),
)

LBUT_PERORANGAN = Definition(
    term="Perorangan (Penduduk) / Individuals",
    text=(
        "i. Perorangan:\n"
        "a) Seluruh penduduk yang menetap dan tinggal di Indonesia.\n"
        "b) Warga Negara Asing (WNA) yang datang dan menetap di Indonesia yang ditunjukkan dengan kepemilikan KITAS (Kartu "
        "Izin Tinggal Terbatas) atau KITAS (Kartu Izin Tinggal Tetap).\n"
        "c) Warga Negara Indonesia (WNI) yang berada di luar negeri dalam rangka: ▪ Tugas-tugas diplomatik dan kenegaraan "
        "lainnya ▪ Pengobatan ▪ Perjalanan ke luar negeri lainnya, misalnya dalam rangka tour\n"
        "d) Karyawan yang bekerja pada kantor lembaga-lembaga internasional yang berada di Indonesia.\n"
        "e) Penduduk Indonesia yang bertempat tinggal di perbatasan wilayah RI dengan negara lain, yang karena "
        "pekerjaannya diharuskan untuk melintasi batas wilayah negara Indonesia secara harian dan rutin."
    ),
    source=_LBUT, url=_LBUT_URL,
)

LBUT_NONFINANCIAL_PRIVATE = Definition(
    term="Badan Usaha Bukan-Keuangan Milik Swasta / Perusahaan Non Finansial: Swasta Nasional, Swasta Pengendalian Asing",
    text=(
        "f) Perusahaan Non Finansial Perusahaan yang kegiatan utamanya adalah memproduksi barang atau jasa non finansial.\n\n"
        "Perusahaan non finansial yang dikendalikan oleh institusi domestik atau warga negara indonesia\n\n"
        "Perusahaan non finansial yang dikendalikan oleh institusi asing atau warga negara asing"
    ),
    source=_LBUT, url=_LBUT_URL,
    note="The second and third sentences are the guidance's entries for 'Swasta Nasional' and 'Swasta Pengendalian Asing'.",
)

LBUT_NONFINANCIAL_PUBLIC = Definition(
    term="Badan Usaha Bukan Keuangan Milik Negara / Perusahaan Non Finansial: Publik (BUMN, BUMD, BUM Desa)",
    text=(
        "f) Perusahaan Non Finansial Perusahaan yang kegiatan utamanya adalah memproduksi barang atau jasa non finansial.\n\n"
        "Perusahaan non finansial yang dikendalikan oleh pemerintah"
    ),
    source=_LBUT, url=_LBUT_URL,
    note="The second sentence is the guidance's entry for 'Publik', listed with the codes BUMN, BUMD and BUM Desa.",
)

SEKI_OTHER_FINANCIAL = Definition(
    term="Lembaga Keuangan Lainnya / Other Financial Corporations",
    text=(
        "Lembaga Keuangan Lainnya terdiri dari Lembaga Keuangan Non Bank (LKNB) antara lain Perusahaan Pembiayaan, "
        "Perusahaan Asuransi, Dana Pensiun, Pegadaian, dan Perusahaan Reksadana."
    ),
    source=_BI_NAB, url=_BI_NAB_URL,
    english=(
        "Other Financial Corporations comprise of non-bank financial institution, e.g. finance companies, insurance "
        "companies, pension funds, pawnshops, and mutual funds."
    ),
    english_source=_BI_NAB_EN, english_url=_BI_NAB_EN_URL,
)

LBUT_LOCAL_GOVERNMENT = Definition(
    term="Pemerintah Daerah / State and Local Governments",
    text=(
        "Instansi/lembaga pemerintah yang anggaran keuangannya diatur dalam Anggaran dan Pendapatan dan Belanja Daerah "
        "(APBD) termasuk kantor wilayah/perwakilan/jawatan dan dinas-dinas vertikalnya di daerah-daerah."
    ),
    source=_LBUT, url=_LBUT_URL,
)

LBUT_NONPROFIT = Definition(
    term="Yayasan, Badan Sosial, & Org. Kemasyarakatan / Lembaga Non Profit Melayani Rumah Tangga",
    text=(
        "h) Lembaga Non Profit Melayani Rumah Tangga Lembaga yang didirikan untuk melakukan usaha yang bersifat sosial "
        "dan tidak untuk mencari keuntungan."
    ),
    source=_LBUT, url=_LBUT_URL,
    note="BI does not state that the table's row equals this LBUT category; the correspondence is by name only.",
)

DATASETS["seki"] = (SEKI_ABOUT,)
GROUPS.update(
    {
        ("seki", "gdp_current"): (SEKI_PDB, SEKI_PRICE_BASIS),
        ("seki", "gdp_constant"): (SEKI_PDB, SEKI_PRICE_BASIS, SEKI_BASE_YEAR),
        ("seki", "deposits"): (SEKI_DEPOSITS, SEKI_OWNER_GROUPS),
    }
)
SERIES.update(
    {
        "bi_seki.gdp_expenditure_current.gdp": (BPS_PDB_CURRENT,),
        "bi_seki.gdp_expenditure_current.total_consumption": (SEKI_TOTAL_CONSUMPTION,),
        "bi_seki.gdp_expenditure_current.household_consumption": (BPS_PKRT, SEKI_PKRT),
        "bi_seki.gdp_expenditure_current.npish_consumption": (BPS_LNPRT, SEKI_NPISH),
        "bi_seki.gdp_expenditure_current.government_consumption": (SEKI_PKP,),
        "bi_seki.gdp_expenditure_current.gfcf": (SEKI_PMTB,),
        "bi_seki.gdp_expenditure_constant.gdp": (BPS_PDB_CONSTANT,),
        "bi_seki.gdp_expenditure_constant.total_consumption": (SEKI_TOTAL_CONSUMPTION,),
        "bi_seki.gdp_expenditure_constant.household_consumption": (BPS_PKRT, SEKI_PKRT),
        "bi_seki.gdp_expenditure_constant.government_consumption": (SEKI_PKP,),
        "bi_seki.deposits_by_owner.households": (LBUT_PERORANGAN,),
        "bi_seki.deposits_by_owner.private_nonfinancial_business": (LBUT_NONFINANCIAL_PRIVATE,),
        "bi_seki.deposits_by_owner.state_nonfinancial_business": (LBUT_NONFINANCIAL_PUBLIC,),
        "bi_seki.deposits_by_owner.other_financial_institutions": (SEKI_OTHER_FINANCIAL,),
        "bi_seki.deposits_by_owner.local_government": (LBUT_LOCAL_GOVERNMENT,),
        "bi_seki.deposits_by_owner.foundations_and_social_bodies": (LBUT_NONPROFIT,),
    }
)
