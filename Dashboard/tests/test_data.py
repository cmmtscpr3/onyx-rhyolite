"""The loaders, against the real dataset files."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from dashboard import catalogue, data

EXPECTED_SERIES = {
    "bi_card_transactions": 6,
    "bi_consumer_survey": 48,
    "bi_emoney": 12,
    "bi_payment_system": 8,
    "bi_seki": 19,
    "ecommerce_gmv": 4,
    "ojk_dpk": 4,
    "qris_transactions": 4,
}


def test_every_series_file_loads_with_its_series(series):
    counts = series.groupby("dataset")["series_id"].nunique().to_dict()
    assert counts == EXPECTED_SERIES
    assert series["value"].notna().all()
    assert series["ref_date"].dtype.kind == "M"


def test_frequency_is_read_or_inferred_per_series(series):
    frequency = series.groupby("series_id")["frequency"].first()
    assert frequency["bi_emoney.value"] == "monthly"
    assert frequency["bi_card_transactions.credit.value"] == "monthly"
    assert frequency["bi_payment_system.currency_in_circulation"] == "monthly"
    # Two quarterly ratios sit beside monthly stocks in the same file.
    assert frequency["bi_payment_system.currency_to_gdp"] == "quarterly"
    assert frequency["bi_payment_system.currency_to_household_consumption"] == "quarterly"
    # Files that carry the column keep it.
    assert frequency["bi_seki.gdp_expenditure_current.gdp"] == "quarterly"
    assert frequency["bi_seki.deposits_by_owner.total"] == "monthly"
    assert frequency["qris_transactions.value.total"] == "quarterly"
    assert (series["frequency"] != "").all()


@pytest.mark.parametrize(
    "dates, expected",
    [
        (["2026-01-01", "2026-01-08", "2026-01-15"], "weekly"),
        (["2026-01-01", "2026-02-01", "2026-03-01"], "monthly"),
        (["2025-03-01", "2025-06-01", "2025-09-01"], "quarterly"),
        (["2024-12-01", "2025-12-01"], "annual"),
        (["2022-12-01", "2023-12-01", "2024-04-01", "2024-05-01"], "irregular"),
        (["2026-01-01"], "irregular"),
    ],
)
def test_infer_frequency(dates, expected):
    assert data.infer_frequency([pd.Timestamp(d) for d in dates]) == expected


def test_every_catalogued_series_exists(series):
    ids = set(series["series_id"])
    for dataset in catalogue.DATASETS:
        for group in dataset.groups:
            missing = [sid for sid in group.series if sid not in ids]
            assert not missing, f"{dataset.key}/{group.key}: {missing}"
            assert set(group.default) <= set(group.series)
            assert set(group.labels) <= set(group.series)


def test_catalogue_covers_every_series_file(series):
    catalogued = {source for dataset in catalogue.DATASETS for source in dataset.sources}
    assert set(series["dataset"]) <= catalogued


def test_wide_keeps_the_requested_order(series):
    ids = ["bi_emoney.value_topup", "bi_emoney.value"]
    frame = data.wide(series, ids)
    assert list(frame.columns) == ids
    assert frame.index.is_monotonic_increasing and frame.index.is_unique
    assert frame.loc["2026-06-01", "bi_emoney.value"] == pytest.approx(337188.9, abs=0.1)


def test_spot_values(series):
    def value(series_id, date):
        row = series[(series["series_id"] == series_id) & (series["ref_date"] == date)]
        return float(row["value"].iloc[0])

    assert value("bi_consumer_survey.ikk", "2026-08-01") == pytest.approx(118.5)
    assert value("qris_transactions.volume.total", "2026-03-01") == pytest.approx(2118.0)
    assert value("bi_seki.deposits_by_owner.total", "2026-07-01") == pytest.approx(9666897.4, abs=0.1)


# ---------------------------------------------------------------------------
# PIHPS


def test_pihps_has_three_markets_of_31_commodities(pihps):
    counts = pihps.groupby("market")["commodity"].nunique()
    assert counts.to_dict() == {m: 31 for m in data.MARKETS}
    rows = data.pihps_commodities(pihps)
    assert len(rows) == 31
    assert (rows["level"] == 1).sum() == 10
    assert rows.iloc[0]["commodity"] == "Beras" and rows.iloc[0]["level"] == 1
    assert rows.iloc[1]["group"] == "Beras"


def test_pihps_weeks_are_unique_and_the_2023_overlap_is_dropped(pihps):
    assert not pihps.duplicated(["market", "commodity", "week"]).any()
    traditional_2024 = pihps[(pihps["market"] == "Traditional Market") & (pihps["week"].dt.year == 2024)]
    assert traditional_2024["week"].nunique() == 53
    assert pihps["week"].min() == pd.Timestamp("2019-01-01")
    assert pihps["week"].max() >= pd.Timestamp("2026-09-10")


def test_pihps_prices_are_numbers_and_dashes_are_missing(pihps):
    beras = pihps[(pihps["market"] == "Traditional Market") & (pihps["commodity"] == "Beras")]
    assert beras.set_index("week").loc["2026-09-10", "price"] == 16350
    assert pihps["price"].dtype.kind == "f"
    # Only a handful of cells are '-' in the source workbooks.
    assert 0 < pihps["price"].isna().sum() < 400


# ---------------------------------------------------------------------------
# ibid lots


def test_lots_parse_dates_plates_and_cities(lots):
    assert set(lots["category"]) == {"cars", "motorcycles"}
    assert lots.attrs["dropped_undated"] == 30
    assert lots.attrs["dropped_stray"] <= 5
    assert lots["auction_date"].min() >= pd.Timestamp("2026-07-01")
    cars = lots[lots["category"] == "cars"]
    assert 5500 <= len(cars) <= 5568
    assert cars["plate"].nunique() >= 4700
    assert (lots["city"] == "").mean() < 0.01
    assert "JAKARTA" in set(lots["city"]) and "JAKARTA B" not in set(lots["city"])
    assert lots["model_year"].isna().mean() < 0.01
    assert lots["price_idr"].notna().all()
    assert lots["sold"].dtype == bool


@pytest.mark.parametrize(
    "title, expected",
    [
        ("TOYOTA AVANZA 1.3 E MT (2019 - MT)", ("TOYOTA", "AVANZA")),
        ("TOYOTA AVANZA E 1.3 (2019 - MT)", ("TOYOTA", "AVANZA")),
        ("DAIHATSU GRAN MAX BV AC 1.3 (2021 - MT)", ("DAIHATSU", "GRAN MAX")),
        ("HONDA BEAT - 110 (2019 - AT)", ("HONDA", "BEAT")),
        ("HONDA SUPRA X - 125 (2019 - MT)", ("HONDA", "SUPRA")),
        ("MERCEDES-BENZ C-CLASS C 200 2.0 (2008 -…", ("MERCEDES-BENZ", "C-CLASS")),
        ("", ("", "")),
    ],
)
def test_parse_family(title, expected):
    assert data.parse_family(title) == expected


def test_parse_auction_date_and_city():
    assert data.parse_auction_date("18 Agt 2026") == dt.date(2026, 8, 18)
    assert data.parse_auction_date("15 Sep 2026") == dt.date(2026, 9, 15)
    assert data.parse_auction_date("Segera Dilelang") is None
    card = "Lot 1 Grade C HONDA HR-V E 1.5 (2018 - AT) 2018 | AT | DD1751XBH Rp 172.000.000 *Terdapat Biaya PMK41 (1,1%) 16 Sep 2026 MAKASSAR LIVE"
    assert data.parse_city(card) == "MAKASSAR"
    assert data.parse_city("… Rp 46.000.000 18 Jul 2026 JAKARTA B LIVE") == "JAKARTA"
    assert data.parse_city("… Rp 46.000.000 18 Jul 2026 JAKARTA FLASH") == "JAKARTA"
    assert data.parse_city("no date here") == ""


def test_fingerprint_changes_with_the_files(tmp_path, monkeypatch):
    (tmp_path / "a.csv").write_text("x")
    before = data.fingerprint([tmp_path])
    assert before.files == 1
    (tmp_path / "b.csv").write_text("y")
    after = data.fingerprint([tmp_path])
    assert after.files == 2 and after.digest != before.digest
