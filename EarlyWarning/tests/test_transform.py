"""Transformations: per-day adjustment for flows, then log for every series."""

from __future__ import annotations

import calendar as _calendar
import math

import numpy as np


def _row(obs, series_id, date):
    return obs[(obs["series_id"] == series_id) & (obs["ref_date"] == date)].iloc[0]


def test_flow_is_per_day_then_log(obs):
    for date in ("2026-02-01", "2026-03-01"):
        row = _row(obs, "bi_card_transactions.atm_debit.value", date)
        days = _calendar.monthrange(int(date[:4]), int(date[5:7]))[1]
        assert row["days_in_month"] == days
        assert math.isclose(row["x_cal"], row["value"] / days)
        assert math.isclose(row["x"], math.log(row["value"] / days))


def test_stock_and_price_are_log_only(obs):
    stock = _row(obs, "bi_card_transactions.atm_debit.cards", "2026-02-01")
    assert stock["x_cal"] == stock["value"]
    assert math.isclose(stock["x"], math.log(stock["value"]))
    price = _row(obs, "pihps.traditional.01_beras", "2026-09-21")
    assert price["x_cal"] == price["value"]
    assert math.isclose(price["x"], math.log(price["value"]))


def test_twelve_flow_series_adjusted(result, obs):
    flows = result.inventory.index[result.inventory["calendar_adj"] == "per_day"]
    assert len(flows) == 12
    sub = obs[obs["series_id"].isin(flows) & obs["value"].notna()]
    assert np.allclose(sub["x_cal"], sub["value"] / sub["days_in_month"].astype(float))


def test_x_missing_exactly_where_value_missing(obs):
    assert (obs["x"].isna() == obs["value"].isna()).all()
