# Analysis

STL decomposition of the PIHPS food prices, and how much of each series is seasonal.
For each of the 93 `(market, commodity)` series it reports a trend strength and a
seasonal strength, tests the seasonality against a bootstrapped null, and plots the
components and the autocorrelation for the series that survive the test.

```bash
pip install -r Analysis/requirements.txt
python Analysis/stl_analysis.py --self-test     # validate the statistics (seconds)
python Analysis/stl_analysis.py                 # the full run (~3 minutes)
python Analysis/stl_analysis.py --n-boot 1999   # the same, with stable p-values (~9 min)
python Analysis/stl_analysis.py --sensitivity   # how much the parameters matter (~6s)
```

Results land in `Analysis/outputs/`, which is gitignored because a re-run rewrites
every file: `stl_strength.csv` for all 93 series, and two PNGs per selected series.

**Read the traps below before reading the numbers.** Several of them change what the
numbers mean, and one of them changed a default.

## What it does

1. **Weekly prices become monthly means.** PIHPS re-anchors its weekly grid to 1
   January every year, so the survey weekday jumps annually — Tue, Wed, Fri, Mon,
   Mon, Mon, Wed, Thu across 2019–2026 — and a year carries 52 *or* 53 observations.
   Across the 406 survey dates there are 400 seven-day gaps plus 1/2/3/2/1-day stubs
   at the year boundaries. A weekly STL at `period=52` would carry a phase error that
   grows through the sample, because a year is 52.18 weeks and "week 12" is a
   different calendar date every year. Monthly aggregation removes that.

   It also removes the missing data. The 217 dashed cells (0.57%) are whole survey
   weeks — all 31 commodities dashed on the same date — always interior, and never
   more than two in one month. Requiring three real weeks per month therefore leaves a
   complete panel: 92 months, January 2019 to August 2026, for every one of the 93
   series, with **nothing interpolated anywhere**. September 2026 is the only month
   dropped, having just two survey weeks on file.

2. **Logs.** STL is additive only, and food prices under inflation have seasonal
   amplitude that scales with the level. On `log(price)` the additive decomposition is
   multiplicative on the price scale and the seasonal component reads as an
   approximate proportional deviation.

3. **STL**, at `period=12`, with the parameters in the table below.

4. **Strengths**, after Wang, Smith & Hyndman (2006) and Hyndman & Athanasopoulos
   *FPP3* §4.3:

   ```
   F_T = max(0, 1 - Var(R) / Var(T + R))
   F_S = max(0, 1 - Var(R) / Var(S + R))
   ```

   Both in [0, 1]. The denominators are `Var(T + R)` and `Var(S + R)`, not
   `Var(T) + Var(R)`: STL's components are correlated and the variance does not
   decompose additively. `Var(S) / Var(observed)`, the other common mistake, is a
   different and larger quantity.

5. **Significance by bootstrap.** 499 surrogate series per commodity, each
   `trend + moving_block(remainder)` — the fitted trend kept, the seasonal dropped,
   the remainder resampled in blocks of 13 months so its short-run autocorrelation
   survives while its phase alignment does not. Each surrogate is decomposed with
   identical parameters, so the null distribution carries the same upward bias STL
   gives the observed statistic. The p-value is `(1 + #{F_S* >= F_S}) / (B + 1)`, the
   standard Monte Carlo correction (Phipson & Smyth 2010), then Benjamini–Hochberg
   across all 93 series. A series is plotted when `q_seasonal <= 0.05`.

6. **Figures** for the selected series: the four STL panels, and three ACFs.

## Parameters

| Parameter | Value | Why |
|---|---|---|
| `period` | 12 | Calendar-month seasonality. |
| `seasonal`, `seasonal_deg` | 25, 0 | A **constant** seasonal pattern: a window wider than a monthly sub-series at degree 0. See trap 3 — this is not the statsmodels default and the reason matters. |
| `trend` | 21 (derived) | The statsmodels default, the smallest odd integer above `1.5 × period / (1 − 1.5 / seasonal)`. |
| `low_pass` | 13 (derived) | The statsmodels default, the smallest odd integer above `period`. |
| `robust` | **off** | See trap 4. |
| `n_boot` | 499 | Floors the p-value at `1 / (B + 1)`. Raise it when a verdict sits near the threshold — see trap 5. |
| `block` | 13 | Not a multiple of 12: blocks of exactly a year could reassemble annual structure by accident. |

`seasonal="periodic"` does **not** exist in statsmodels — that is R's `stl()`. A
constant seasonal pattern is a wide window at `seasonal_deg=0`, which is what the
defaults above do. `--seasonal` and `--seasonal-deg` override them, and
`--sensitivity` compares four settings side by side.

## What the run found

At the defaults, with `--n-boot 1999`:

* **10 of 93 series are significant at FDR 0.05**, and they are two commodities seen
  independently in all three markets and at both hierarchy levels: **Bawang Merah**
  (shallots, `F_S` ≈ 0.50, `p` = 0.0005–0.002) and **Daging Sapi** (beef, `F_S` ≈ 0.40,
  `p` = 0.0005–0.004). Agreement across three separately-collected market tiers is the
  strongest evidence available here that these are real and not fitting artefacts.
* Shallots swing roughly +16% in June to −18% in September against trend, a ~34
  percentage point annual cycle — an ordinary harvest pattern.
* **Nothing passes the FPP3 rule of thumb** (`F_S >= 0.64`) while ten pass the
  bootstrap test. The convention and the test disagree completely on this data, which
  is trap 1 in practice.
* **`q_trend <= 0.05` for 100% of series**, which is trap 7 in practice: it is a
  property of prices, not a finding about any commodity.
* The median `F_S` across all 93 series is 0.23 and the median `F_T` is 0.95.
* Rice, cooking oil and sugar — the administered commodities — do not clear the bar.
  Read trap 12 before concluding they have no seasonality.
* Chilli does not clear it either, despite a visible average annual swing, because its
  year-to-year variation is large enough to swamp the repeating part.

## Traps and assumptions

Ordered by how much they can change your conclusions.

**1. A bare strength threshold cannot support the word "significant".** STL recovers
a non-zero seasonal component from anything, including noise. In the self-test a pure
white-noise series scores **F_S = 0.11** under these defaults — and **F_S = 0.37**
under the statsmodels default seasonal window, which is more than half way to the FPP3
rule of thumb for "strong" seasonality (0.64). That rule is a useful convention for
ranking series, and `strong_fpp3` reports it, but it is not a test and should not be
read as one. This is the whole reason the bootstrap exists, and the fact that the
threshold's meaning moves with a parameter is the whole reason not to trust it.

**2. Idul Fitri is lunar and drifts straight through the sample.** Indonesia's largest
food-demand spike moved from 5 June 2019 to about 20 March 2026 — roughly 11 days
earlier each Gregorian year, two and a half months of drift across the sample. The
festival month runs June, May, May, May, April, April, March, March. STL places
seasonality at a *fixed* calendar position, so this effect is smeared across four
months and real repeating structure is discarded as noise.

Worse, it interacts with the seasonal window: a short window lets STL track the drift
as evolving seasonality and inflates `F_S`; a long window treats it as noise and
deflates it. The `idul_fitri_r2` column measures the damage directly, regressing each
remainder on two festival dummies.

**And it catches something.** For beef it comes back at **0.11 to 0.20** — the highest
in the dataset by a wide margin — meaning up to a fifth of the beef remainder is
festival demand that the decomposition had no way to represent. Beef is exactly where
you would expect it: demand spikes at Idul Fitri and Idul Adha, both lunar. So beef's
seasonal strength here is understated, and the amount is roughly known.

Note that under the flexible seasonal window this diagnostic reads only 0.05, because
the flexible fit absorbs the drifting festival effect into "evolving seasonality" and
hides it from the remainder. The constant fit is what makes the trap visible. The
proper correction is to regress out a festival regressor before decomposing, or to
work in lunar time; neither is done here.

**3. The seasonal window is a modelling decision, and the statsmodels default
over-fits this data.** The window and its degree set how fast the seasonal shape may
evolve. With 7.67 cycles, each monthly sub-series holds 7–8 points, so the statsmodels
default — a degree-1 window of 7 — spans almost the whole sub-series and fits noise as
seasonality. Three measurements on this data say so:

* the bootstrap null mean of `F_S` falls from about **0.40 to about 0.15** when the
  seasonal pattern is held constant, so most of what the flexible window called
  seasonal was what STL invents from noise;
* the remainder's autocorrelation at lag 12 falls from **−0.49 to −0.00** for Daging
  Ayam Ras Segar. A large negative spike there is the signature of an over-fitted
  seasonal component, not of leftover seasonality;
* power rises where there is real signal: Bawang Merah Ukuran Sedang goes from
  `p = 0.023` to `p = 0.003`.

So the default here is a constant seasonal pattern. `F_S` comes out *lower* — 0.617
against 0.274 for Daging Ayam Ras Segar — and the lower number is the honest one. The
cost is that genuine slow evolution in the seasonal shape is now assumed away;
`--seasonal 7 --seasonal-deg 1` restores the flexible fit and trap 13 is how you tell
which is better specified for a given series.

**4. Outlier down-weighting mechanically deflates the thing being measured.** Robust
STL down-weights outliers when it *fits* trend and seasonal, but leaves them at full
size in the remainder — and both strengths are variance ratios whose denominator the
remainder dominates. So `robust=True` inflates `Var(R)` while barely moving `Var(S)`.
Beras Kualitas Medium I is the clean demonstration: `sd(S)` is 0.0061 robust against
0.0070 not, essentially unchanged, while `sd(R)` doubles from 0.0099 to 0.0194, and
`F_S` falls from 0.42 to 0.05 on nothing else. That is why robustness is off by
default here, against the usual advice.

The genuine cost of leaving it off is that a one-off spike can bend the 23-month trend
window, and for a commodity whose spikes are irregular rather than annual the robust
reading is the fairer one. `--robust` turns it on; `--sensitivity` reports both.

**5. The verdict can sit on the FDR boundary, and then the bootstrap's own noise
decides it.** A Monte Carlo p-value is itself a random variable, and Benjamini–Hochberg
compares the k-th smallest against `k × alpha / n` — so when p-values cluster rather
than separate, jitter flips series across the line. Two measurements of how much this
matters here:

* Under the *flexible* seasonal window this was severe. Two runs differing only in how
  the bootstrap was seeded returned **8 significant series and 0** — the same data, the
  same parameters, opposite conclusions. That instability was itself a symptom of the
  over-fitting in trap 3: a null mean of 0.40 leaves no separation to work with.
* Under the current defaults it is mild. `--n-boot 499` selects 8 series and
  `--n-boot 1999` selects 10, disagreeing only on the two marginal beef rows, while
  every shallot series is selected either way.

So: treat a series near the threshold as unresolved, not as significant. When the best
`q_seasonal` is close to `alpha`, re-run at `--n-boot 1999` — and if the answer moves,
that *is* the answer at this sample size.

**6. The parameters move the answer a lot.** Across the four settings `--sensitivity`
compares, the spread in `F_S` is wide for many series. Where it is wide the honest
report is a range, not a number.

**7. `F_T` is close to vacuous for price series.** Food prices are near-I(1): they
carry a stochastic trend by construction. `F_T` measures whether the trend *component*
dominates the remainder — it is not a test for the presence of a deterministic trend.
It comes back above 0.9 for most series here and `q_trend` is significant for very
nearly all of them. That is a property of prices, not a discovery about any commodity,
which is why the plotting rule keys on seasonality alone.

**8. Selection and multiplicity.** Plotting the series that score highest on `F_S`,
chosen by a test on `F_S`, is a winner's curse: the plotted series have upward-biased
strength estimates. BH controls the false discovery rate but not that bias. BH also
assumes independence or positive regression dependence; these series share national
shocks, so the dependence is positive and BH is generally held to survive it. For a
guarantee under arbitrary dependence, Benjamini–Yekutieli is the conservative
alternative, at a cost in power.

**9. The panel is not 93 independent series.** Three overlapping kinds of duplication.
(a) The 10 group rows are near-duplicates of the 21 varieties beneath them — and where
a group has a single variety they are byte-identical, so the same data appears twice.
Note the group rows are *not* the arithmetic mean of their varieties; PIHPS weights
them somehow, so they cannot be reconstructed. (b) The three markets are three
measurements of largely the same underlying commodity. (c) All series share national
macro shocks. The effective sample size is well below 93, findings arrive in
correlated clusters, and the FDR calculation is where this bites. The `level` and
`group` columns exist so you can re-run on a non-overlapping subset: `--level 2`
drops the group rows, `--market` picks one market.

**10. Prices are nominal.** There is no CPI deflator anywhere in this repository, so
`F_T` partly measures general inflation rather than relative food-price movement, and
the seasonal amplitude is measured against a rising nominal base. Deflating would
lower `F_T` materially and leave `F_S` roughly intact.

**11. Structural breaks, which the trend LOESS smooths straight through.** The sample
contains at least COVID-19 disruption (2020), the cooking-oil crisis and its HET price
cap (late 2021–2022), the global food and fuel shock and the domestic fuel-subsidy cut
(2022), and the El Niño rice surge with Bulog SPHP intervention (2023–24). A level
shift is not a trend; LOESS bends through it and spills the difference into the
remainder, depressing both strengths near the break.

**12. Administered prices truncate seasonality.** Minyak Goreng Curah sat under a
price ceiling; Beras and Gula Pasir have government reference prices and Bulog
intervention. A capped price cannot express its seasonal peak, so a low `F_S` for
these may mean effective policy rather than absent seasonality. Do not read them the
way you read shallots.

**13. Check the remainder ACF before trusting a seasonal strength.** Panel 3 of the
ACF figure is a specification test, not decoration. A spike at lag 12 or 24 means
seasonality was left behind; a large *negative* spike at lag 12 — which several series
here show — means the opposite, that `seasonal=7` is flexible enough to over-fit the
seasonal component and push compensating negative correlation into the remainder.
Compare against the `constant seasonal` column of `--sensitivity` when this appears.

**14. The ACF of the level series says almost nothing.** It decays slowly for any
near-I(1) series whatever else is true, which is why the figure carries three panels
and not one: the level as a nonstationarity diagnostic, the first difference where
annual seasonality actually shows as spikes at lags 12 and 24, and the remainder as
the specification check. Bartlett's widening bands suit the first two, where the null
is not white noise; the remainder panel uses the flat ±1.96/√n band, because white
noise *is* the hypothesis under test there. With 92 observations, estimates beyond
about lag 23 (n/4) are unreliable however clean the plot looks.

**15. End effects and the unbalanced final year.** LOESS has higher variance at both
ends, so the first and last few trend points are the least reliable — which is where
you will want to look. The sample also ends in August 2026, so months January to
August have 8 observations and September to December only 7, and the seasonal estimate
is slightly better determined for the first two thirds of the year. `--complete-years`
trims to 2019–2025, exactly seven cycles, as the robustness check.

**16. Monthly means hide weekly structure and add a mild calendar artefact.** Months
carry 4 or 5 survey weeks (56 and 36 of them respectively), so a monthly mean averages
a varying number of draws — a mild heteroskedasticity, analogous to a trading-day
effect. Any genuine sub-monthly dynamics, such as a two-week pre-festival run-up, is
averaged away.

**17. Seven and two-thirds cycles is not many.** The seasonal component is estimated
from 7–8 observations per calendar month. The strength estimates carry real sampling
uncertainty; the bootstrap addresses only "is it non-zero", not the precision of
`F_S`, and STL's own uncertainty is not quantified at all.

**18. What STL does and does not assume.** It does *not* require stationarity or
normality — neither holds here. It *does* assume a known, integer, fixed seasonal
period; additive components, which the log transform turns into a multiplicative
assumption on the price scale; and a smooth trend. The strength ratios additionally
assume the remainder variance is a meaningful scale, which under traps 4 and 16 it
only roughly is.

**19. PIHPS revises.** The collectors' own notes record that published prices get
revised, so this is not a vintage-stable dataset and re-running next month can move
past numbers. The `data_fingerprint` column records which snapshot produced a result.

## Verification

`--self-test` runs 13 checks in a few seconds and is what actually validates the
statistics: a synthetic seasonal series must score high and test significant, white
noise must not, a trend-only series must give `F_T ≈ 1`, the block bootstrap must
preserve length and draw only from its input, the Idul Fitri diagnostic must find a
planted spike and stay quiet on noise, and the Benjamini–Hochberg implementation must
reproduce the worked example in Benjamini & Hochberg (1995) — four of fifteen
hypotheses rejected at a false discovery rate of 0.05.

Beyond that, every STL fit asserts that its components sum back to the series, so a
mis-specified call fails immediately rather than quietly.

## Output columns

`stl_strength.csv`, one row per series, sorted by `f_seasonal` descending.

| Column | Meaning |
|---|---|
| `market`, `commodity`, `level`, `group` | Which series. `level` is 1 for a group row, 2 for a variety. |
| `n_months`, `first_month`, `last_month` | Coverage after aggregation. |
| `f_trend`, `f_seasonal` | The two strengths, in [0, 1]. |
| `p_seasonal`, `q_seasonal` | Bootstrap p-value and its BH-adjusted q-value. |
| `p_trend`, `q_trend` | The same for the trend. Read trap 7 first. |
| `idul_fitri_r2` | Share of the remainder two festival dummies explain. Trap 2. |
| `strong_fpp3` | `f_seasonal >= 0.64`, the FPP3 rule of thumb. A convention, not a test. |
| `selected` | `q_seasonal <= 0.05`; these are the series that got figures. |
| `period`, `seasonal_window`, `seasonal_deg`, `trend_window`, `robust`, `n_boot` | The parameters that produced the row. |
| `data_fingerprint` | Hash of the dataset files, from the dashboard's own `fingerprint()`. |
