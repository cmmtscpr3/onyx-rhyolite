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
