"""Research probe for Phase 3: how well do simple one-step-ahead forecasts and intervals work here?

This is NOT the Phase 3 code. It is a quick, rough measurement behind the numbers quoted in
EXPECTED_VALUE_FORECASTING.md, kept so those numbers can be reproduced.

    pip install statsmodels                      # not in EarlyWarning/requirements.txt
    python -m ews.run --out /tmp/ews             # fresh Phase 1 output
    python Research/backtest_probe.py /tmp/ews/observations.csv

What it does, for each of the 54 series, on x = log(value) (flows per day first):

* rolling origin, expanding window, one step ahead, refit at every origin;
* test span: the last 60 months (monthly) or the last 156 weeks (weekly);
* point forecasts: naive, seasonal naive, seasonal-dummy regression on changes (with and without
  Idul Fitri regressors), ETS, Theta, STL + ETS (weekly), and the plain average of three of them;
* 95% intervals on the naive forecast and on the average: normal with the residual standard
  deviation, ETS's own, and conformal (the empirical quantile of past out-of-sample errors).

Missing periods are carried forward for fitting and never scored.
"""
from __future__ import annotations

import sys
import warnings
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
HOLIDAYS = HERE.parent / "DataFoundation" / "holiday_calendar.csv"
N_TEST = {"monthly": 60, "weekly": 156}
SEASON = {"monthly": 12, "weekly": 52}
MIN_CAL = 30          # past out-of-sample errors needed before a conformal interval is made
Z95 = 1.959964


def eid_dates() -> list[pd.Timestamp]:
    h = pd.read_csv(HOLIDAYS, parse_dates=["date"])
    return sorted(h.loc[h["event"] == "idul_fitri", "date"])


def eid_features(dates: pd.DatetimeIndex, freq: str) -> pd.DataFrame:
    """Idul Fitri regressors, known in advance for any date.

    Monthly: the share of the 14 days before Idul Fitri, and of the 7 days from it, that fall in
    the month (two columns). Weekly: one dummy per week relative to the Idul Fitri week, -4..+2.
    """
    eids = eid_dates()
    if freq == "monthly":
        out = pd.DataFrame(0.0, index=dates, columns=["eid_before", "eid_after"])
        for e in eids:
            for col, days in (("eid_before", pd.date_range(e - pd.Timedelta(days=14), periods=14)),
                              ("eid_after", pd.date_range(e, periods=7))):
                share = days.to_period("M").to_timestamp().value_counts() / len(days)
                for month, s in share.items():
                    if month in out.index:
                        out.loc[month, col] += s
        return out
    cols = [f"eid_w{k:+d}" for k in range(-4, 3)]
    out = pd.DataFrame(0.0, index=dates, columns=cols)
    for e in eids:
        week = e - pd.Timedelta(days=e.weekday())          # Monday of the Idul Fitri week
        for k in range(-4, 3):
            d = week + pd.Timedelta(weeks=k)
            if d in out.index:
                out.loc[d, f"eid_w{k:+d}"] = 1.0
    return out


def ols_change_forecast(y: np.ndarray, X: np.ndarray) -> float:
    """Regress the change in y on X (rows aligned with y, last row = the period to forecast)."""
    d = np.diff(y)
    Xd = X[1:-1]
    beta, *_ = np.linalg.lstsq(Xd, d, rcond=None)
    return y[-1] + float(X[-1] @ beta)


def backtest(args) -> pd.DataFrame:
    series_id, freq, dates, x = args
    from statsmodels.tsa.exponential_smoothing.ets import ETSModel
    from statsmodels.tsa.forecasting.stl import STLForecast
    from statsmodels.tsa.forecasting.theta import ThetaModel

    m = SEASON[freq]
    dates = pd.DatetimeIndex(dates)
    actual = np.asarray(x, dtype=float)
    filled = pd.Series(actual).ffill().bfill().to_numpy()
    n = len(filled)
    pos = dates.month.to_numpy() if freq == "monthly" else np.minimum(dates.isocalendar().week.to_numpy(), 52)
    seas = np.zeros((n, m))
    seas[np.arange(n), pos - 1] = 1.0                     # one dummy per month / ISO week
    eid = eid_features(dates, freq).to_numpy()
    X_seas = seas if freq == "monthly" else np.ones((n, 1))   # weekly: drift only (52 dummies overfit)
    X_eid = np.hstack([X_seas, eid])

    rows = []
    for t in range(n - N_TEST[freq], n):
        y = filled[:t]
        f = {"naive": y[-1], "seasonal_naive": y[-m]}
        f["dummies"] = ols_change_forecast(y, X_seas[: t + 1])
        f["dummies_eid"] = ols_change_forecast(y, X_eid[: t + 1])
        idx = pd.RangeIndex(t)
        ys = pd.Series(y, index=idx)
        ets_kw = dict(error="add", trend="add", damped_trend=True)
        lo = hi = np.nan
        try:
            if freq == "monthly":
                fit = ETSModel(ys, seasonal="add", seasonal_periods=m, **ets_kw).fit(disp=False)
            else:
                fit = ETSModel(ys, **ets_kw).fit(disp=False)
            pred = fit.get_prediction(start=t, end=t).summary_frame(alpha=0.05)
            f["ets"] = float(pred["mean"].iloc[0])
            lo, hi = float(pred["pi_lower"].iloc[0]), float(pred["pi_upper"].iloc[0])
        except Exception:
            f["ets"] = np.nan
        try:
            theta = ThetaModel(y, period=m, deseasonalize=(freq == "monthly"), method="additive").fit()
            f["theta"] = float(np.asarray(theta.forecast(1))[0])
        except Exception:
            f["theta"] = np.nan
        if freq == "weekly":
            try:
                stl = STLForecast(ys, ETSModel, model_kwargs=ets_kw, period=m, robust=True).fit(
                    fit_kwargs=dict(disp=False))
                f["stl_ets"] = float(np.asarray(stl.forecast(1))[0])
            except Exception:
                f["stl_ets"] = np.nan
        third = f["dummies_eid"] if freq == "monthly" else f["naive"]
        f["average"] = np.nanmean([f["ets"], f["theta"], third])
        # in-sample one-step naive residual spread, as a textbook interval would use
        f["naive_sd"] = float(np.std(np.diff(y), ddof=1))
        rows.append(dict(series_id=series_id, frequency=freq, ref_date=dates[t], actual=actual[t],
                         ets_lo=lo, ets_hi=hi, **f))
    out = pd.DataFrame(rows)

    # Conformal: the 95% quantile of the absolute out-of-sample errors seen so far (expanding).
    for model in ("naive", "average"):
        err = (out["actual"] - out[model]).abs().to_numpy()
        q = np.full(len(out), np.nan)
        for i in range(MIN_CAL, len(out)):
            past = err[:i][~np.isnan(err[:i])]
            if len(past) >= MIN_CAL:
                k = min(int(np.ceil(0.95 * (len(past) + 1))), len(past))
                q[i] = np.sort(past)[k - 1]
        out[f"{model}_conf_q"] = q
    return out


def group_of(series_id: str, inv: pd.DataFrame) -> str:
    row = inv.loc[series_id]
    if row["frequency"] == "weekly":
        return f"food prices, {row['vol_tier']} volatility"
    return f"monthly {row['series_kind']}s" + (" (holiday-sensitive)" if row["holiday_adj"] == "yes" and row["series_kind"] == "stock" else "")


def main(path: str) -> None:
    obs = pd.read_csv(path, parse_dates=["ref_date"], low_memory=False)
    inv = pd.read_csv(HERE.parent / "Scope" / "indicator_inventory.csv").set_index("series_id")
    jobs = [(sid, g["frequency"].iloc[0], g["ref_date"].to_numpy(), g["x"].to_numpy())
            for sid, g in obs.sort_values("ref_date").groupby("series_id")]
    with Pool() as pool:
        bt = pd.concat(pool.map(backtest, jobs), ignore_index=True)
    bt = bt[bt["actual"].notna()].copy()
    bt["group"] = [group_of(s, inv) for s in bt["series_id"]]
    out_dir = Path(path).parent
    bt.to_csv(out_dir / "backtest_probe.csv", index=False)

    models = ["naive", "seasonal_naive", "dummies", "dummies_eid", "ets", "theta", "stl_ets", "average"]
    pd.set_option("display.width", 200, "display.max_columns", 30)

    print("\n== Point forecasts: mean absolute error, in % (log points x 100), median over the series ==")
    mae = bt.assign(**{mo: (bt["actual"] - bt[mo]).abs() * 100 for mo in models}).groupby(
        ["group", "series_id"])[models].mean()
    print(mae.groupby("group").median().round(2).to_string())
    print("\n== The same, relative to naive (below 1 = better than naive), median over the series ==")
    rel = mae.div(mae["naive"], axis=0)
    print(rel.groupby("group").median().round(2).to_string())
    print("\n== Number of series each model wins ==")
    print(mae.drop(columns="average").idxmin(axis=1).groupby(level="group").value_counts().unstack(fill_value=0).to_string())
    print("\n== Series where the average beats the best single model picked on the FIRST half of the test span ==")
    half = bt.groupby("series_id")["ref_date"].transform(lambda d: d.rank(method="first") <= len(d) / 2)
    singles = [mo for mo in models if mo != "average"]
    abs_err = bt.assign(**{mo: (bt["actual"] - bt[mo]).abs() for mo in models})
    first = abs_err[half].groupby("series_id")[singles].mean().idxmin(axis=1)
    second = abs_err[~half].groupby("series_id")[models].mean()
    picked = pd.Series({s: second.loc[s, first[s]] for s in second.index})
    oracle = second[singles].min(axis=1)
    print(f"  average beats or ties the picked model in {(second['average'] <= picked).sum()} of {len(picked)} series")
    print(f"  picked model is still the best single model in the second half in {(picked <= oracle + 1e-12).sum()} of {len(picked)}")
    print(f"  median error, second half, relative to naive: picked {np.median(picked / second['naive']):.2f}, "
          f"average {np.median(second['average'] / second['naive']):.2f}")

    print("\n== 95% intervals: share of actual values inside (target 0.95), and median width in % ==")
    iv = {
        "naive +/- 1.96 sd": (bt["naive"] - Z95 * bt["naive_sd"], bt["naive"] + Z95 * bt["naive_sd"]),
        "ETS own interval": (bt["ets_lo"], bt["ets_hi"]),
        "naive, conformal": (bt["naive"] - bt["naive_conf_q"], bt["naive"] + bt["naive_conf_q"]),
        "average, conformal": (bt["average"] - bt["average_conf_q"], bt["average"] + bt["average_conf_q"]),
    }
    has_conf = bt["naive_conf_q"].notna()            # compare every interval on the same periods
    rows = []
    for name, (lo, hi) in iv.items():
        d = bt[has_conf].assign(inside=((bt["actual"] >= lo) & (bt["actual"] <= hi))[has_conf],
                                width=((hi - lo) * 100)[has_conf])
        g = d.groupby("group").agg(coverage=("inside", "mean"), width=("width", "median"))
        g["interval"] = name
        rows.append(g.reset_index())
    table = pd.concat(rows).pivot(index="group", columns="interval", values=["coverage", "width"]).round(2)
    print(table.to_string())

    print("\n== If nothing unusual is happening: expected flags from 95% bands alone ==")
    for freq, k in bt.groupby("frequency")["series_id"].nunique().items():
        per_year = 52 if freq == "weekly" else 12
        print(f"  {freq}: {k} series x 5% = {k * 0.05:.1f} per period, about {k * 0.05 * per_year:.0f} per year")


if __name__ == "__main__":
    main(sys.argv[1])
