"""Validation checks: missing dates, duplicates, zeros and negatives, unit changes, structure."""

from __future__ import annotations

import datetime as dt

import pandas as pd

from ews import validate
from ews.findings import STOP, WARN, Findings


def _ids(findings, check_id, severity=None):
    return {(f.series_id, f.ref_date) for f in findings if f.check_id == check_id and (severity is None or f.severity == severity)}


def test_scope_is_54_series(result):
    inv = result.inventory
    assert len(inv) == 54
    assert inv["frequency"].value_counts().to_dict() == {"weekly": 30, "monthly": 24}
    assert set(result.observations["series_id"]) == set(inv.index)


def test_real_data_passes_without_stop(result):
    assert not result.findings.has_stop


def test_no_duplicate_periods(obs):
    assert not obs.duplicated(["series_id", "ref_date"]).any()


def test_repeated_2024_weeks_in_2023_file_are_identical(findings):
    d1 = [f for f in findings if f.check_id == "D1"]
    assert len(d1) == 10  # one per traditional-market series
    assert not [f for f in findings if f.check_id == "D2"]


def test_known_missing_weeks(obs):
    missing = obs[obs["quality_flag"] == "missing"]
    by_market = missing.groupby(missing["series_id"].str.split(".").str[1])["ref_date"].apply(
        lambda s: sorted(set(s.dt.strftime("%Y-%m-%d")))
    )
    assert by_market["traditional"] == ["2021-05-10", "2022-02-28", "2022-05-02"]
    assert by_market["modern"] == ["2022-02-28"]
    assert by_market["wholesale"] == ["2022-02-28"]
    assert not missing["series_id"].str.startswith("bi_").any()


def test_no_zero_or_negative_values(obs):
    assert not (obs["raw_value"] <= 0).any()


def test_units_match_inventory(findings):
    assert not _ids(findings, "U1")
    assert not _ids(findings, "U2")


def test_quarterly_ratios_left_out_quietly(findings):
    m6 = [f for f in findings if f.check_id == "M6"]
    assert {f.series_id for f in m6} == {
        "bi_payment_system.currency_to_gdp",
        "bi_payment_system.currency_to_household_consumption",
    }
    assert all(f.severity != WARN for f in m6)


def test_one_off_spikes_flagged(findings):
    spikes = _ids(findings, "U4", WARN)
    assert ("bi_card_transactions.atm_debit.cards", "2011-11-01") in spikes
    assert ("bi_emoney.volume", "2013-09-01") in spikes
    assert ("pihps.modern.10_gula_pasir", "2024-06-03") in spikes


def test_latest_periods(obs):
    latest = obs[obs["value"].notna()].groupby("series_id")["ref_date"].max()
    assert (latest[latest.index.str.startswith("pihps.")] >= pd.Timestamp(2026, 9, 21)).all()
    card_emoney = latest[latest.index.str.startswith(("bi_card", "bi_emoney"))]
    assert (card_emoney >= pd.Timestamp(2026, 7, 1)).all()
    assert latest["bi_payment_system.currency_in_circulation"] >= pd.Timestamp(2026, 8, 1)


def test_no_stale_feeds_as_of_test_date(findings):
    assert not _ids(findings, "M4")


def test_expected_latest():
    # PIHPS: the Saturday run fills the week it falls in.
    assert validate.expected_latest("weekly", dt.date(2026, 9, 30)) == pd.Timestamp(2026, 9, 21)
    assert validate.expected_latest("weekly", dt.date(2026, 9, 26)) == pd.Timestamp(2026, 9, 21)
    # SPIP: month M arrives around the 15th of M+2.
    assert validate.expected_latest("monthly", dt.date(2026, 10, 1)) == pd.Timestamp(2026, 7, 1)
    assert validate.expected_latest("monthly", dt.date(2026, 10, 20)) == pd.Timestamp(2026, 8, 1)


def test_data_issues_flag_but_do_not_mask(obs):
    flagged = obs[obs["quality_flag"] == "review"]
    assert ("bi_card_transactions.atm_debit.cards", pd.Timestamp(2011, 11, 1)) in set(
        zip(flagged["series_id"], flagged["ref_date"])
    )
    assert flagged["value"].notna().all()  # review keeps the value
    assert (obs["quality_flag"] != "masked_error").all()


def test_latest_two_periods_provisional(obs):
    assert (obs.groupby("series_id")["is_provisional"].sum() == 2).all()


def test_quality_report(result):
    report = result.quality
    assert len(report) == 54
    assert set(report["confidence"]) == {"high"}


# --- synthetic cases -------------------------------------------------------

def _aligned(values, start="2020-01-01", freq="MS", frequency="monthly"):
    dates = pd.date_range(start, periods=len(values), freq=freq)
    return pd.DataFrame({
        "series_id": "test.series", "frequency": frequency, "unit": "IDR billion", "ref_date": dates,
        "week_ending": pd.NaT, "iso_year": pd.NA, "iso_week": pd.NA, "days_in_month": 30,
        "source_date": dates, "source_file": "x", "raw_text": [str(v) for v in values], "raw_value": values,
    })


def test_z1_stops_on_zero_or_negative():
    findings = Findings()
    validate.check_aligned(_aligned([10.0, 11.0, -1.0, 12.0] * 5), findings, dt.date(2021, 12, 1))
    assert any(f.check_id == "Z1" and f.severity == STOP for f in findings.items)


def test_m2_m3_long_gap():
    findings = Findings()
    values = [10.0] * 10 + [float("nan")] * 5 + [10.0] * 10
    validate.check_aligned(_aligned(values), findings, dt.date(2022, 3, 1))
    assert any(f.check_id == "M2" for f in findings.items)
    assert any(f.check_id == "M3" for f in findings.items)


def test_u3_unit_switch_that_stays():
    findings = Findings()
    values = [100.0 + i for i in range(20)] + [100_000.0 + i for i in range(10)]
    validate.check_aligned(_aligned(values), findings, dt.date(2022, 9, 1))
    assert any(f.check_id == "U3" and "x1,000" in f.message for f in findings.items)
    assert not any(f.check_id == "U4" for f in findings.items)  # it stays, so not a spike


def test_d4_duplicate_period_stops():
    findings = Findings()
    frame = _aligned([10.0] * 15)
    frame = pd.concat([frame, frame.iloc[[3]]], ignore_index=True)
    validate.check_aligned(frame, findings, dt.date(2021, 6, 1))
    assert any(f.check_id == "D4" and f.severity == STOP for f in findings.items)
