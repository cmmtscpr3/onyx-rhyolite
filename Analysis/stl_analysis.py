"""STL decomposition of the PIHPS food prices, and how much of each series is seasonal.

One question: for each of the 93 ``(market, commodity)`` price series, how much of
the variation is seasonal and how much is trend?  The answer is an STL
decomposition plus the two strength measures of Wang, Smith & Hyndman (2006), and
for the series where the seasonality survives a significance test, a plot of the
components and of the autocorrelation.

Five decisions shape everything downstream, and each is a judgement rather than a
default worth taking on trust.  Two of them go against the obvious choice, and the
measurements behind those are recorded beside the constants below.

**The weekly prices are aggregated to calendar months first.**  PIHPS re-anchors its
weekly grid to 1 January every year, so the survey weekday jumps annually -- Tue,
Wed, Fri, Mon, Mon, Mon, Wed, Thu across 2019-2026 -- and a year carries 52 *or* 53
observations.  Over the 406 survey dates there are 400 seven-day gaps plus 1/2/3/2/1
day stubs at the year boundaries.  A weekly STL at ``period=52`` would therefore
carry a phase error that grows through the sample, because a year is 52.18 weeks and
"week 12" is a different calendar date every year.  Monthly aggregation removes that,
and removes the missing data too: the 217 dashed cells are whole survey weeks (all 31
commodities dashed on the same date), always interior, and never more than two in a
month, so requiring three real weeks per month leaves a complete panel and **nothing
is ever interpolated**.  Interpolation would have manufactured smoothness and
inflated both strengths.

**The decomposition runs on logs.**  STL is additive only, and food prices under
inflation have seasonal amplitude that scales with the level.  On ``log(price)`` the
additive decomposition is multiplicative on the price scale and the seasonal
component reads as an approximate proportional deviation.

**The seasonal pattern is held constant.**  Not the statsmodels default of a degree-1
window of 7, which with only 7.67 cycles spans almost a whole monthly sub-series and
fits noise as seasonality.  Holding it constant drops the bootstrap null mean of F_S
from about 0.40 to about 0.15 and clears the over-fitting spike out of the remainder's
autocorrelation at lag 12.  See ``SEASONAL``.

**Outlier down-weighting is off.**  Robust STL leaves down-weighted outliers at full
size in the remainder, which is the denominator of both strength measures, so it
deflates them mechanically rather than statistically.  See ``ROBUST``.

**Significance is bootstrapped, not thresholded.**  STL recovers a non-zero seasonal
component even from pure noise, so the seasonal strength is biased upward and no
fixed cut-off can support the word "significant".  The null distribution is built by
resampling each series' own remainder in blocks, which is the only part of this
module that costs real time.

Everything this cannot see is written down in ``Analysis/README.md`` -- above all that
Idul Fitri is lunar and drifts two and a half months across this sample, which STL
cannot represent.  Read that before reading the numbers.

    pip install -r Analysis/requirements.txt
    python Analysis/stl_analysis.py --self-test     # validate the statistics
    python Analysis/stl_analysis.py                 # the full run
    python Analysis/stl_analysis.py --sensitivity   # how much the parameters matter
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no display in CI or over SSH; figures go straight to PNG

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from statsmodels.graphics.tsaplots import plot_acf  # noqa: E402
from statsmodels.tsa.seasonal import STL  # noqa: E402

ANALYSIS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = ANALYSIS_ROOT.parent

# The dashboard's loader already knows this dataset's quirks -- text prices with
# thousands commas, '-' for a week a market did not report, and the Traditional
# Market 2023 workbook that duplicates all of 2024 -- so it is reused rather than
# re-implemented.  ``dashboard/__init__.py`` is a bare docstring and ``data.py``
# imports only pandas and the collectors' readers, so this pulls in no Streamlit.
if str(REPO_ROOT / "Dashboard") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "Dashboard"))

from dashboard.data import fingerprint, load_pihps  # noqa: E402

# ---------------------------------------------------------------------------
# Parameters

#: Calendar-month seasonality.  See the module docstring for why not weekly.
PERIOD = 12

#: The seasonal LOESS window and its degree, which together set how fast the seasonal
#: shape may evolve from year to year -- and so how much variance is allowed to land in
#: the seasonal component rather than the remainder.  This is the most consequential
#: choice in the module.
#:
#: A window wider than a monthly sub-series (7-8 points here) at degree 0 makes the
#: seasonal pattern *constant*: it is R's ``stl(s.window = "periodic")``, which
#: statsmodels has no keyword for.  That is the default, against the statsmodels
#: default of ``seasonal=7`` at degree 1, on three pieces of evidence measured on this
#: data.  With only 7.67 cycles a degree-1 window of 7 spans almost the whole
#: sub-series and fits noise as seasonality:
#:
#: * the bootstrap null mean of F_S falls from about 0.40 to about 0.15, so most of
#:   what the flexible window called seasonal was what STL invents from noise;
#: * the remainder's autocorrelation at lag 12 falls from -0.49 to -0.00 for Daging
#:   Ayam Ras Segar -- a large negative spike there is the signature of an over-fitted
#:   seasonal component, and the constant fit removes it;
#: * power rises where there is real signal: Bawang Merah Ukuran Sedang goes from
#:   p = 0.023 to p = 0.003.
#:
#: F_S is *lower* under the constant fit, and that lower number is the honest one.
SEASONAL = 25
SEASONAL_DEG = 0

#: Bisquare outlier down-weighting, **off by default**, which is not the obvious
#: choice and is the one parameter here worth arguing about.
#:
#: Robust STL down-weights outliers when it *fits* the trend and seasonal components,
#: but those outliers stay at full size in the remainder -- and both strength measures
#: are variance ratios whose denominator is dominated by the remainder.  The two are
#: therefore mismatched: turning robustness on inflates Var(R) while barely moving
#: Var(S), so it mechanically deflates the statistic being measured.  Beras Kualitas
#: Medium I is the clean demonstration: sd(S) is 0.0061 robust against 0.0070 not,
#: essentially unchanged, while sd(R) doubles from 0.0099 to 0.0194, and F_S falls
#: from 0.42 to 0.05 on nothing but that.
#:
#: The genuine cost of leaving it off is that a one-off spike can bend the 23-month
#: trend window.  ``--robust`` turns it on and ``--sensitivity`` reports both, because
#: for a series whose spikes are irregular rather than annual the robust reading is
#: the fairer one.
ROBUST = False

#: Surrogate series per bootstrap.  The smallest p-value this can report is
#: ``1 / (N_BOOT + 1)``.
N_BOOT = 499

#: Moving-block length for the remainder bootstrap.  Long enough to carry the
#: remainder's short-run autocorrelation, and deliberately not a multiple of 12 --
#: blocks of exactly a year could reassemble annual structure by accident.
BLOCK = PERIOD + 1

#: Real survey weeks a calendar month needs before its mean is trusted.  At three,
#: the only month dropped across all 93 series is September 2026 (2 weeks on file).
MIN_WEEKS = 3

#: False discovery rate for the Benjamini-Hochberg step, and so the rule that
#: decides which series get plotted.
ALPHA = 0.05

#: Hyndman & Athanasopoulos' rule of thumb for "strong" seasonality (FPP3 sec. 4.3).
#: Reported beside the p-value because it is a convention, not a test.
FPP3_STRONG = 0.64

#: Lags on the ACF panels: two full years.  With 92 observations, estimates beyond
#: roughly lag 23 (n/4) are unreliable whatever the plot suggests.
ACF_LAGS = 24

#: Idul Fitri in Indonesia, 2019-2026.  Lunar, so it moves about 11 days earlier each
#: Gregorian year -- 5 June 2019 to 20 March 2026, right through this sample.  Used
#: only to measure how much repeating festival structure STL had to discard; see
#: ``idul_fitri_r2``.
IDUL_FITRI: tuple[str, ...] = (
    "2019-06-05", "2020-05-24", "2021-05-13", "2022-05-02",
    "2023-04-22", "2024-04-10", "2025-03-31", "2026-03-20",
)

#: Where results land.  Gitignored: a re-run rewrites every file.
OUTPUTS = ANALYSIS_ROOT / "outputs"


@dataclass(frozen=True)
class Strength:
    """How much of a series the trend and the seasonal component account for."""

    trend: float
    seasonal: float


# ---------------------------------------------------------------------------
# Weekly prices to a monthly panel

def monthly_panel(pihps: pd.DataFrame, *, min_weeks: int = MIN_WEEKS) -> pd.DataFrame:
    """Mean price per calendar month, from the survey weeks that reported.

    Returns the tidy frame ``market, commodity, level, group, order, month, price,
    weeks``.  A month with fewer than ``min_weeks`` real observations is dropped
    rather than filled, so the result carries no NaN and no interpolated value.
    """
    frame = pihps.dropna(subset=["price"]).copy()
    frame["month"] = frame["week"].dt.to_period("M").dt.to_timestamp()
    keys = ["market", "commodity", "level", "group", "order", "month"]
    monthly = frame.groupby(keys, as_index=False).agg(price=("price", "mean"), weeks=("price", "size"))
    monthly = monthly[monthly["weeks"] >= min_weeks]
    return monthly.sort_values(["market", "order", "month"]).reset_index(drop=True)


def log_series(monthly: pd.DataFrame) -> pd.Series:
    """One series' monthly log price, on a month-start index STL can read."""
    series = monthly.set_index("month")["price"].sort_index()
    series.index = pd.DatetimeIndex(series.index, freq="MS")
    if (series <= 0).any():
        raise ValueError("a price is zero or negative, so it cannot be logged")
    return np.log(series)


# ---------------------------------------------------------------------------
# Decomposition and strengths

def fit_stl(y: pd.Series, *, seasonal: int = SEASONAL, seasonal_deg: int = SEASONAL_DEG,
            robust: bool = ROBUST):
    """STL with the parameters this analysis declares, and a reconciliation check.

    ``trend`` and ``low_pass`` are left at the statsmodels defaults, derived from
    ``period`` and ``seasonal``.  The assertion is free and catches a mis-specified
    call immediately.
    """
    result = STL(y, period=PERIOD, seasonal=seasonal, seasonal_deg=seasonal_deg, robust=robust).fit()
    rebuilt = result.trend + result.seasonal + result.resid
    assert np.abs(np.asarray(y) - np.asarray(rebuilt)).max() < 1e-9, "STL components do not sum to the series"
    return result


def trend_window(seasonal: int = SEASONAL) -> int:
    """The trend window statsmodels derives from ``period`` and ``seasonal``.

    Recorded in the results rather than restated as a constant, because it is a
    derived quantity: the smallest odd integer above ``1.5 * period / (1 - 1.5 /
    seasonal)``, which is 23 months for the defaults here.
    """
    return int(STL(np.zeros(3 * PERIOD), period=PERIOD, seasonal=seasonal).config["trend"])


def _strength(remainder_var: float, combined_var: float) -> float:
    """``max(0, 1 - Var(R) / Var(component + R))``, guarded against a flat series."""
    if not np.isfinite(combined_var) or combined_var <= 0:
        return 0.0
    return float(max(0.0, 1.0 - remainder_var / combined_var))


def strengths(result) -> Strength:
    """Trend and seasonal strength, per Wang, Smith & Hyndman (2006) / FPP3 sec. 4.3.

    The denominators are ``Var(T + R)`` and ``Var(S + R)`` -- the components are
    correlated, so the variance does not decompose additively and ``Var(T) + Var(R)``
    is the wrong denominator.  ``Var(S) / Var(observed)``, the other common mistake,
    is a different and larger quantity.  Because the fit is on logs, both are
    strengths of proportional variation.
    """
    remainder = np.asarray(result.resid, dtype=float)
    trend = np.asarray(result.trend, dtype=float)
    seasonal = np.asarray(result.seasonal, dtype=float)
    remainder_var = float(remainder.var(ddof=1))
    return Strength(
        trend=_strength(remainder_var, float((trend + remainder).var(ddof=1))),
        seasonal=_strength(remainder_var, float((seasonal + remainder).var(ddof=1))),
    )


# ---------------------------------------------------------------------------
# Significance

def moving_block(remainder: np.ndarray, *, block: int, rng: np.random.Generator) -> np.ndarray:
    """Resample a remainder in overlapping blocks, preserving its short-run structure.

    Drawing whole blocks keeps the autocorrelation within a block while destroying
    the phase alignment between blocks, which is exactly the structure a seasonality
    test needs to remove.
    """
    n = remainder.size
    starts = rng.integers(0, n - block + 1, size=int(np.ceil(n / block)))
    return np.concatenate([remainder[start:start + block] for start in starts])[:n]


def seasonal_pvalue(
    y: pd.Series,
    result,
    observed: float,
    *,
    n_boot: int = N_BOOT,
    block: int = BLOCK,
    rng: np.random.Generator,
    **stl_kw,
) -> float:
    """Monte Carlo p-value for "this series has no seasonality".

    Surrogates are ``trend + moving_block(remainder)``: the fitted trend is kept, the
    seasonal component is dropped, and the remainder is resampled.  Each surrogate is
    decomposed with identical parameters, which is what makes the comparison fair --
    the null distribution then carries the same upward bias STL gives the observed
    statistic.

    The ``+1`` on both sides is the standard Monte Carlo correction (Phipson & Smyth,
    2010): it keeps the p-value valid and stops it ever reporting exactly zero.
    """
    baseline = np.asarray(result.trend, dtype=float)
    remainder = np.asarray(result.resid, dtype=float)
    atleast = 0
    for _ in range(n_boot):
        surrogate = pd.Series(baseline + moving_block(remainder, block=block, rng=rng), index=y.index)
        if strengths(fit_stl(surrogate, **stl_kw)).seasonal >= observed:
            atleast += 1
    return (1.0 + atleast) / (n_boot + 1.0)


def trend_pvalue(
    y: pd.Series,
    result,
    observed: float,
    *,
    n_boot: int = N_BOOT,
    block: int = BLOCK,
    rng: np.random.Generator,
    **stl_kw,
) -> float:
    """The same test for "this series has no trend", with the trend flattened to its mean.

    Reported, but read it with care: food prices are near-I(1), carrying a stochastic
    trend by construction, so this comes back significant for very nearly every
    series.  That is a property of prices, not a discovery about any one commodity,
    which is why the plotting rule keys on seasonality alone.
    """
    baseline = float(np.asarray(result.trend, dtype=float).mean()) + np.asarray(result.seasonal, dtype=float)
    remainder = np.asarray(result.resid, dtype=float)
    atleast = 0
    for _ in range(n_boot):
        surrogate = pd.Series(baseline + moving_block(remainder, block=block, rng=rng), index=y.index)
        if strengths(fit_stl(surrogate, **stl_kw)).trend >= observed:
            atleast += 1
    return (1.0 + atleast) / (n_boot + 1.0)


def benjamini_hochberg(pvalues: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg q-values, controlling the false discovery rate.

    Ninety-three tests would otherwise produce a handful of discoveries by chance.
    BH assumes independence or positive regression dependence; these series share
    national shocks, so the dependence is positive and BH is generally held to
    survive it.  Benjamini-Yekutieli would hold under arbitrary dependence at a cost
    in power -- see the README.
    """
    pvalues = np.asarray(pvalues, dtype=float)
    n = pvalues.size
    order = np.argsort(pvalues)
    scaled = pvalues[order] * n / np.arange(1, n + 1)
    stepped = np.minimum.accumulate(scaled[::-1])[::-1]
    qvalues = np.empty(n, dtype=float)
    qvalues[order] = np.clip(stepped, 0.0, 1.0)
    return qvalues


def idul_fitri_r2(remainder: pd.Series) -> float:
    """How much of the remainder two Idul Fitri dummies explain.

    A diagnostic, not a correction.  STL places seasonality at a fixed calendar
    position, but Indonesia's largest food-demand spike is lunar and moves from June
    to March across this sample, so genuine repeating festival demand is discarded as
    noise.  A large value here means the decomposition is mis-specified for that
    series and its seasonal strength is understated.
    """
    festival = {pd.Period(day, freq="M") for day in IDUL_FITRI}
    months = remainder.index.to_period("M")
    design = np.column_stack([
        np.ones(remainder.size),
        np.fromiter((month in festival for month in months), dtype=float, count=remainder.size),
        np.fromiter((month + 1 in festival for month in months), dtype=float, count=remainder.size),
    ])
    values = np.asarray(remainder, dtype=float)
    coefficients, *_ = np.linalg.lstsq(design, values, rcond=None)
    residual_ss = float(((values - design @ coefficients) ** 2).sum())
    total_ss = float(((values - values.mean()) ** 2).sum())
    return 0.0 if total_ss <= 0 else float(max(0.0, 1.0 - residual_ss / total_ss))


# ---------------------------------------------------------------------------
# Figures

def _slug(text: str) -> str:
    return "-".join(str(text).split()).replace("/", "-")


def plot_components(y: pd.Series, result, *, title: str, subtitle: str, path: Path) -> None:
    """The four STL panels: observed, trend, seasonal, remainder."""
    panels = (
        ("Observed (log IDR)", y),
        ("Trend", result.trend),
        ("Seasonal", result.seasonal),
        ("Remainder", result.resid),
    )
    figure, axes = plt.subplots(4, 1, figsize=(10, 9), sharex=True)
    for axis, (label, values) in zip(axes, panels):
        axis.plot(y.index, np.asarray(values), linewidth=1.1, color="#1f4e79")
        axis.set_ylabel(label, fontsize=9)
        axis.grid(alpha=0.25, linewidth=0.5)
    axes[3].axhline(0.0, color="#999999", linewidth=0.8)
    axes[2].axhline(0.0, color="#999999", linewidth=0.8)
    figure.suptitle(title, fontsize=12, y=0.98)
    axes[0].set_title(subtitle, fontsize=9, color="#555555", loc="left")
    figure.tight_layout(rect=(0, 0, 1, 0.97))
    figure.savefig(path, dpi=130)
    plt.close(figure)


def plot_acf_panels(y: pd.Series, result, *, title: str, path: Path) -> None:
    """Three ACFs, because one of the raw series on its own would mislead.

    The level ACF of a near-I(1) price decays slowly whatever else is true, so it is
    read as a diagnostic of nonstationarity and nothing more.  Seasonality shows up
    in the differenced series, as spikes at lags 12 and 24.  The remainder ACF says
    whether STL took the seasonal structure out: spikes left at 12 or 24 mean the
    seasonal window is too rigid, or the Idul Fitri drift is leaking.

    Bartlett's widening bands suit the first two panels, where the null is not white
    noise.  For the remainder, white noise *is* the hypothesis under test, so the
    flat +/- 1.96/sqrt(n) band is the right one.
    """
    differenced = y.diff().dropna()
    panels = (
        ("Log level -- slow decay is the I(1) signature, not evidence of seasonality", y, True),
        ("First difference -- annual seasonality appears here, at lags 12 and 24", differenced, True),
        ("STL remainder -- spikes at 12 or 24 mean seasonality was left behind", result.resid, False),
    )
    figure, axes = plt.subplots(3, 1, figsize=(10, 9))
    for axis, (label, values, bartlett) in zip(axes, panels):
        # title=None, or statsmodels stamps its own "Autocorrelation" over the label.
        plot_acf(np.asarray(values), ax=axis, lags=ACF_LAGS, bartlett_confint=bartlett,
                 alpha=0.05, title=None)
        axis.set_title(label, fontsize=9, loc="left", color="#555555")
        axis.set_xlabel("lag (months)", fontsize=8)
        axis.set_ylim(-1.05, 1.05)
        axis.grid(alpha=0.25, linewidth=0.5)
    figure.suptitle(title, fontsize=12, y=0.99)
    figure.tight_layout(rect=(0, 0, 1, 0.97))
    figure.savefig(path, dpi=130)
    plt.close(figure)


# ---------------------------------------------------------------------------
# The run

def _series_seed(y: pd.Series) -> int:
    """A generator seed derived from the series' own values, not its position."""
    return int.from_bytes(hashlib.sha256(np.asarray(y, dtype=float).tobytes()).digest()[:8], "big")


def analyse(
    monthly: pd.DataFrame,
    *,
    seasonal: int = SEASONAL,
    seasonal_deg: int = SEASONAL_DEG,
    robust: bool = ROBUST,
    n_boot: int = N_BOOT,
    seed: int = 20260917,
    progress: bool = True,
) -> pd.DataFrame:
    """Decompose every series, score it, and bootstrap its seasonality.

    Each series seeds its own generator from its own values, so a run is reproducible,
    adding or dropping a series changes no other series' p-value, and two series
    carrying identical data get an identical verdict.  That last point is not
    fastidiousness: ten of the group rows are the only variety in their group and so
    are byte-identical to it, and seeding by position gave the same series two
    different q-values, one side of the threshold each.
    """
    stl_kw = {"seasonal": seasonal, "seasonal_deg": seasonal_deg, "robust": robust}
    rows: list[dict] = []
    groups = list(monthly.groupby(["market", "commodity"], sort=False))
    for index, ((market, commodity), part) in enumerate(groups, start=1):
        y = log_series(part)
        result = fit_stl(y, **stl_kw)
        score = strengths(result)
        rng = np.random.default_rng([seed, _series_seed(y)])
        p_seasonal = seasonal_pvalue(y, result, score.seasonal, n_boot=n_boot, rng=rng, **stl_kw)
        p_trend = trend_pvalue(y, result, score.trend, n_boot=n_boot, rng=rng, **stl_kw)
        rows.append({
            "market": market,
            "commodity": str(commodity).strip(),
            "level": int(part["level"].iloc[0]),
            "group": part["group"].iloc[0],
            "n_months": int(y.size),
            "first_month": y.index.min().date().isoformat(),
            "last_month": y.index.max().date().isoformat(),
            "f_trend": round(score.trend, 4),
            "f_seasonal": round(score.seasonal, 4),
            "p_seasonal": round(p_seasonal, 5),
            "p_trend": round(p_trend, 5),
            "idul_fitri_r2": round(idul_fitri_r2(result.resid), 4),
            "strong_fpp3": bool(score.seasonal >= FPP3_STRONG),
        })
        if progress:
            print(
                f"  [{index:2d}/{len(groups)}] {market:<18} {str(commodity).strip():<32} "
                f"F_S={score.seasonal:.3f} F_T={score.trend:.3f} p={p_seasonal:.4f}",
                file=sys.stderr,
            )
    frame = pd.DataFrame(rows)
    frame["q_seasonal"] = benjamini_hochberg(frame["p_seasonal"].to_numpy()).round(5)
    frame["q_trend"] = benjamini_hochberg(frame["p_trend"].to_numpy()).round(5)
    return frame.sort_values("f_seasonal", ascending=False).reset_index(drop=True)


def sensitivity(monthly: pd.DataFrame) -> pd.DataFrame:
    """Seasonal strength under four defensible parameter choices, per series.

    Given that the Idul Fitri drift is absorbed by a short seasonal window and thrown
    away by a long one, the spread across these settings is a headline result rather
    than a footnote: where it is wide, the answer depends on the parameter and should
    be reported as a range.
    """
    settings = {
        "constant (default)": {"seasonal": 25, "seasonal_deg": 0, "robust": False},
        "evolving, seasonal=13": {"seasonal": 13, "seasonal_deg": 1, "robust": False},
        "evolving, seasonal=7": {"seasonal": 7, "seasonal_deg": 1, "robust": False},
        "constant, robust": {"seasonal": 25, "seasonal_deg": 0, "robust": True},
    }
    rows: list[dict] = []
    for (market, commodity), part in monthly.groupby(["market", "commodity"], sort=False):
        y = log_series(part)
        row = {"market": market, "commodity": str(commodity).strip()}
        for label, kw in settings.items():
            row[label] = round(strengths(fit_stl(y, **kw)).seasonal, 4)
        row["spread"] = round(max(row[label] for label in settings) - min(row[label] for label in settings), 4)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("spread", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Self test

def self_test() -> None:
    """Check the statistics against series whose answers are known in advance.

    This is what validates the strength formulas and the bootstrap: a seasonal series
    must score high and test significant, noise must not, and a p-value on pure noise
    must not be systematically small.
    """
    rng = np.random.default_rng(7)
    index = pd.date_range("2019-01-01", periods=92, freq="MS")
    months = np.arange(92)

    seasonal_series = pd.Series(
        9.5 + 0.004 * months + 0.15 * np.sin(2 * np.pi * months / 12) + rng.normal(0, 0.01, 92), index=index
    )
    noise_series = pd.Series(9.5 + rng.normal(0, 0.05, 92), index=index)
    trend_only = pd.Series(9.5 + 0.01 * months + rng.normal(0, 0.005, 92), index=index)

    checks: list[tuple[str, bool, str]] = []

    result = fit_stl(seasonal_series)
    score = strengths(result)
    p_seasonal = seasonal_pvalue(seasonal_series, result, score.seasonal, n_boot=99,
                                 rng=np.random.default_rng(1))
    checks.append(("seasonal series: F_S high", score.seasonal > 0.9, f"F_S={score.seasonal:.3f}"))
    checks.append(("seasonal series: significant", p_seasonal <= 0.05, f"p={p_seasonal:.4f}"))

    result = fit_stl(noise_series)
    score = strengths(result)
    p_noise = seasonal_pvalue(noise_series, result, score.seasonal, n_boot=99, rng=np.random.default_rng(2))
    checks.append(("white noise: F_S low", score.seasonal < 0.5, f"F_S={score.seasonal:.3f}"))
    checks.append(("white noise: not significant", p_noise > 0.05, f"p={p_noise:.4f}"))

    result = fit_stl(trend_only)
    score = strengths(result)
    checks.append(("trend only: F_T near 1", score.trend > 0.95, f"F_T={score.trend:.3f}"))
    checks.append(("trend only: F_S low", score.seasonal < 0.6, f"F_S={score.seasonal:.3f}"))

    # A block bootstrap must preserve length and draw only from the input.
    remainder = np.asarray(fit_stl(seasonal_series).resid, dtype=float)
    drawn = moving_block(remainder, block=BLOCK, rng=np.random.default_rng(3))
    checks.append(("bootstrap keeps length", drawn.size == remainder.size, f"{drawn.size} of {remainder.size}"))
    checks.append(("bootstrap draws from input", set(drawn).issubset(set(remainder)), "subset"))

    # BH must leave a single p-value alone and must never shrink one, and must
    # reproduce the worked example in Benjamini & Hochberg (1995), table 1, where
    # four of the fifteen hypotheses are rejected at a false discovery rate of 0.05.
    single = benjamini_hochberg(np.array([0.03]))
    many = np.array([0.001, 0.01, 0.2, 0.5])
    published = np.array([0.0001, 0.0004, 0.0019, 0.0095, 0.0201, 0.0278, 0.0298, 0.0344,
                          0.0459, 0.3240, 0.4262, 0.5719, 0.6528, 0.7590, 1.0000])
    rejected = int((benjamini_hochberg(published) <= 0.05).sum())
    checks.append(("BH of one p-value is itself", np.isclose(single[0], 0.03), f"{single[0]:.3f}"))
    checks.append(("BH never lowers a p-value", bool((benjamini_hochberg(many) >= many).all()), "monotone"))
    checks.append(("BH matches Benjamini & Hochberg 1995", rejected == 4, f"{rejected} of 15 rejected"))

    # The Idul Fitri diagnostic must find a spike it was given, and not one it was not.
    festival_months = {pd.Period(day, freq="M") for day in IDUL_FITRI}
    spike = pd.Series(
        [0.3 if month in festival_months else 0.0 for month in index.to_period("M")], index=index
    ) + rng.normal(0, 0.01, 92)
    checks.append(("Idul Fitri: finds a planted spike", idul_fitri_r2(spike) > 0.8, f"R2={idul_fitri_r2(spike):.3f}"))
    flat = pd.Series(rng.normal(0, 0.05, 92), index=index)
    checks.append(("Idul Fitri: quiet on noise", idul_fitri_r2(flat) < 0.3, f"R2={idul_fitri_r2(flat):.3f}"))

    width = max(len(name) for name, _, _ in checks)
    failed = 0
    for name, passed, detail in checks:
        print(f"  {'PASS' if passed else 'FAIL'}  {name:<{width}}  {detail}")
        failed += not passed
    print(f"\n{len(checks) - failed}/{len(checks)} checks passed")
    if failed:
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# CLI

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--market", action="append", help="limit to a market; repeatable")
    parser.add_argument("--level", type=int, choices=(1, 2), help="1 for group rows, 2 for varieties")
    parser.add_argument("--seasonal", type=int, default=SEASONAL,
                        help=f"seasonal LOESS window (default {SEASONAL}, a constant seasonal pattern)")
    parser.add_argument("--seasonal-deg", type=int, choices=(0, 1), default=SEASONAL_DEG,
                        help=f"0 holds the seasonal pattern constant, 1 lets it evolve (default {SEASONAL_DEG})")
    parser.add_argument("--robust", action="store_true", help="bisquare outlier weighting; see ROBUST and README")
    parser.add_argument("--n-boot", type=int, default=N_BOOT, help=f"bootstrap surrogates (default {N_BOOT})")
    parser.add_argument("--alpha", type=float, default=ALPHA, help=f"false discovery rate (default {ALPHA})")
    parser.add_argument("--complete-years", action="store_true", help="trim to 2019-2025, seven whole cycles")
    parser.add_argument("--sensitivity", action="store_true", help="parameter spread only; no bootstrap, no figures")
    parser.add_argument("--self-test", action="store_true", help="validate the statistics and exit")
    parser.add_argument("--outdir", type=Path, default=OUTPUTS, help=f"where results land (default {OUTPUTS})")
    args = parser.parse_args(argv)

    if args.self_test:
        self_test()
        return 0

    args.outdir.mkdir(parents=True, exist_ok=True)
    print("Loading PIHPS workbooks...", file=sys.stderr)
    pihps = load_pihps()
    monthly = monthly_panel(pihps)
    if args.market:
        monthly = monthly[monthly["market"].isin(args.market)]
    if args.level:
        monthly = monthly[monthly["level"] == args.level]
    if args.complete_years:
        monthly = monthly[monthly["month"] < "2026-01-01"]
    if monthly.empty:
        raise SystemExit("no series selected")

    series_count = monthly.groupby(["market", "commodity"]).ngroups
    months = monthly["month"]
    print(
        f"{series_count} series, {months.nunique()} months "
        f"({months.min():%Y-%m} to {months.max():%Y-%m}), no interpolated values",
        file=sys.stderr,
    )

    if args.sensitivity:
        spread = sensitivity(monthly)
        path = args.outdir / "stl_sensitivity.csv"
        spread.to_csv(path, index=False)
        print("\nSeasonal strength under four parameter choices -- widest spread first\n")
        print(spread.head(15).to_string(index=False))
        print(f"\nmedian spread {spread['spread'].median():.3f}, widest {spread['spread'].max():.3f}")
        print(f"\nWrote {path}")
        return 0

    results = analyse(monthly, seasonal=args.seasonal, seasonal_deg=args.seasonal_deg,
                      robust=args.robust, n_boot=args.n_boot)
    # BH rejects at q <= alpha, not q < alpha.  With a p-value floor of 1/(B+1) the
    # q-values tie at the boundary often enough that the difference decides series.
    results["selected"] = results["q_seasonal"] <= args.alpha

    # The parameters and the data fingerprint ride along so a results file is
    # self-describing and a re-run against changed data is detectable.  The trend
    # window is whatever statsmodels derived from period and seasonal, not a
    # constant, so it is read back off a fitted model rather than restated here.
    results["period"] = PERIOD
    results["seasonal_window"] = args.seasonal
    results["seasonal_deg"] = args.seasonal_deg
    results["trend_window"] = trend_window(args.seasonal)
    results["robust"] = args.robust
    results["n_boot"] = args.n_boot
    results["data_fingerprint"] = fingerprint().digest

    path = args.outdir / "stl_strength.csv"
    results.to_csv(path, index=False)

    figures = args.outdir / "figures"
    figures.mkdir(exist_ok=True)
    for _, row in results[results["selected"]].iterrows():
        part = monthly[(monthly["market"] == row["market"]) & (monthly["commodity"].str.strip() == row["commodity"])]
        y = log_series(part)
        result = fit_stl(y, seasonal=args.seasonal, seasonal_deg=args.seasonal_deg, robust=args.robust)
        stem = f"{_slug(row['market'])}__{_slug(row['commodity'])}"
        title = f"{row['commodity']} -- {row['market']}"
        subtitle = (
            f"F_S={row['f_seasonal']:.3f}  F_T={row['f_trend']:.3f}  "
            f"q={row['q_seasonal']:.4f}  Idul Fitri R2 of remainder={row['idul_fitri_r2']:.3f}"
        )
        plot_components(y, result, title=title, subtitle=subtitle, path=figures / f"{stem}__stl.png")
        plot_acf_panels(y, result, title=f"{title} -- autocorrelation", path=figures / f"{stem}__acf.png")

    shown = ["market", "commodity", "level", "f_seasonal", "q_seasonal", "f_trend", "q_trend",
             "idul_fitri_r2", "strong_fpp3", "selected"]
    print("\n" + results[shown].to_string(index=False))
    print(
        f"\n{int(results['selected'].sum())} of {len(results)} series significant at FDR {args.alpha}; "
        f"{int(results['strong_fpp3'].sum())} pass the FPP3 rule of thumb (F_S >= {FPP3_STRONG})"
    )
    print(f"Wrote {path} and {2 * int(results['selected'].sum())} figures to {figures}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
