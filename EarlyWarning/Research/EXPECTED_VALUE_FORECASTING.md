# Research 2 — Expected-value checks and forecasting

Methods for Phase 3 of [the work plan](../WORKPLAN.md) (Q1 and Q2), what the forecasting literature says about
them, and what a first test on our own 54 series shows. The system-design side is in
[EWS_DESIGN_METHODS.md](EWS_DESIGN_METHODS.md).

> **Status (20 Nov 2026): research notes, nothing here is decided.** The numbers in section 3 come from
> [backtest_probe.py](backtest_probe.py), a rough probe and not the Phase 3 code. It covers the 54 series the
> Phase 1 code produces (the consumer survey has no loader yet), with data to 9 Nov 2026 (weekly) and
> Jul–Aug 2026 (monthly).

---

## 1. The short version

1. **For most of our series, the best one-step forecast is very close to "the same as last period".**
   ETS and Theta beat that by 0–15%, and for some series they are clearly worse. Seasonal naive is 5 to 14
   times worse. So the choice of forecast model matters much less than the plan assumes.
2. **The width of the band matters much more, and ours would be too wide.** Bands built from each series'
   full history covered 97–98% of recent values instead of 95%, because old shocks and data breaks inflate
   them. Bands built from the last 2–3 years hit 95–96% and were **up to half as wide**. A band twice too wide
   misses events.
3. **Idul Fitri regressors work where the effect is big, and hurt elsewhere.** Against naive, they cut the error for
   currency in circulation by 39% and for narrow money by 38%. They did nothing for most food prices and made e-money
   worse. Add them per series, on evidence, not by theme.
4. **Turn the gap into a rank, not a z-score.** "This gap is larger than 99% of the gaps we saw in the last two
   years" needs no assumption about bell curves. Our changes have 6 times more extreme values than a bell
   curve predicts.
5. **Q2 needs more care than Q1.** Same-period comparisons have only 7–14 past values, and year-on-year
   checks echo every past shock a year later.
6. **So Phase 3 can be simpler and shorter than planned:** fewer models, more effort on the band, the clean
   baseline and the backtest.

## 2. What an expected-value check is made of

| Part | Question | Example |
|---|---|---|
| **Expectation** | What value did we expect? | Forecast for this week: Rp 15,800 |
| **Gap** | How far off is the actual value? | +2.1% |
| **Scale** | How big are gaps normally, for this series, lately? | Typical gap: 0.4% |
| **Score** | How unusual is this gap? | Larger than 99% of recent gaps |
| **Band** | The same thing, drawn on a chart | Expected range: Rp 15,650 – 15,950 |

Q1 and Q2 differ only in the first part:

| | Expectation built from | Catches | Blind to |
|---|---|---|---|
| **Q1** (short-term) | The last few periods | Sudden moves | Slow drifts: each step looks normal |
| **Q2** (long-term) | A year ago, the same season in past years, the last few months | Drifts and levels that are unusual for the season | Moves that are normal for the season but sudden |

## 3. What our data says

Rolling-origin test: for each series and each period in the last 3 years (weekly) or 5 years (monthly), fit on
everything before it, forecast one step, compare. All errors are in %, on the log scale.

### 3a. Point forecasts

Mean absolute error of "same as last period" (naive), and every other method **relative to it**
(below 1 = better than naive). Median across the series in each group.

| Group | Series | Naive error | Seasonal naive | ETS | Theta | Month dummies | + Idul Fitri | Average of 3 |
|---|---|---|---|---|---|---|---|---|
| Food, low volatility (rice, beef, oil, sugar) | 12 | 0.31% | 13.9 | 1.02 | 1.05 | — | 1.10 | 0.99 |
| Food, mid (chicken, eggs) | 6 | 0.93% | 4.9 | 1.00 | 1.01 | — | 1.00 | 0.99 |
| Food, high (shallot, garlic, chili) | 12 | 2.91% | 5.3 | **0.93** | 1.00 | — | 1.01 | 0.96 |
| Monthly flows (card, e-money, RTGS) | 12 | 5.69% | 5.0 | 0.89 | **0.85** | 0.94 | 1.02 | 0.87 |
| Money stocks (currency, M1, demand deposits) | 3 | 2.67% | 4.9 | 0.80 | 0.87 | 0.77 | **0.62** | 0.65 |
| Other stocks (cards, e-money float and instruments) | 9 | 2.69% | 7.1 | 1.26 | 1.26 | 1.42 | 1.40 | 1.30 |

"Month dummies" predicts the monthly change from the average change of that calendar month. "+ Idul Fitri"
adds the regressors in section 5 (for food: a weekly version with no month dummies). "Average of 3" is the
plain mean of ETS, Theta and one more (the Idul Fitri model for monthly, naive for weekly).

What this shows:

- **Naive is the best single method for 19 of the 54 series**, ETS for 16, the Idul Fitri model for 9, Theta
  for 7. No method wins broadly.
- **Seasonal naive is not a usable benchmark here.** These series trend and wander; last year's level is far
  from this year's. It stays useful as a *Q2 comparison*, not as a Q1 forecast.
- **Why ETS helps volatile food prices a little:** their weekly changes carry over (correlation of one week's
  change with the next: 0.27). A price that rose last week tends to rise again. For the other food groups that
  correlation is about zero, so nothing beats naive.
- **Why models help monthly flows:** monthly changes partly reverse (correlation −0.22) and have a seasonal
  pattern, both of which naive ignores.
- **Why models hurt "other stocks":** these series have steps and reporting changes. A model fitted across a
  step learns a pattern that isn't there. E-money top-up volume is the extreme case (naive 10% error, every
  model about 19%).
- **STL + ETS on weekly data did badly** (3 to 6 times the naive error with default settings). With 7 years of
  data, the "seasonal" pattern for each week is mostly last year's shocks. A smoother seasonal setting would do
  better, but the weekly food series show little fixed seasonality to model in the first place.
- **Picking the best model per series versus averaging: a tie.** I picked each series' best model on the first
  half of the test span and scored it on the second half. The pick was still the best in 35 of 54 series, and
  its median error was 1.00 of naive against 0.98 for the average. Neither rule is worth much over naive.

### 3b. Bands

95% bands around the naive forecast, built two ways. Coverage is the share of actual values that fell inside
(target 95%). Width is the full width of the band.

| Group | Full history, ±1.96 standard deviations | | Last 2 years (weekly) or 3 years (monthly), 95th percentile of past gaps | |
|---|---|---|---|---|
| | Coverage | Width | Coverage | Width |
| Food, low volatility | 98% | 4.6% | 95% | **2.4%** |
| Food, mid | 98% | 9.0% | 95% | 6.5% |
| Food, high | 97% | 17.9% | 95% | 17.1% |
| Monthly flows | 98% | 51% | 95% | **32%** |
| Money stocks | 97% | 16% | 96% | 15% |
| Other stocks | 98% | 33% | 95% | **16%** |

- Full-history bands are too wide everywhere, and 1.5 to 2 times too wide for three of the six groups. A ±25%
  band on a monthly flow can't flag anything short of a collapse.
- ETS's own formula bands behaved the same way (98% coverage on most groups) and went the other way on money
  stocks (93%).
- The causes are visible in the data: past data errors (the 30× jump in e-money volume in 2013), reporting
  breaks, and COVID. This is the "keep the baseline clean" point from the design note, measured.

### 3c. Shape of the gaps

| Fact | Value | Consequence |
|---|---|---|
| Changes beyond 3 standard deviations | 1.7% of periods, weekly and monthly (a bell curve gives 0.27%) | Fixed "3 sigma" rules fire 6× more often than their label says. Use ranks or robust scales. |
| Size of this week's change vs last week's | Correlation 0.38 | Volatility comes in clusters. The scale should follow recent conditions. |
| Low-volatility food: weeks with exactly zero change | Typically 37%, up to 59% | Sticky prices. The spread floor from [TRANSFORMS.md](../DataFoundation/TRANSFORMS.md) is needed. |
| Low-volatility food: noisiest year vs calmest year | About 10× the spread | One fixed spread per series is wrong for both years. |

## 4. Point forecasts: the menu

| Method | What it is | Fit for our data |
|---|---|---|
| **Naive** | Last value | The benchmark to beat, and the default for food prices and unstable stocks |
| **Seasonal naive** | Value one year ago | Q2 comparison only |
| **ETS** (exponential smoothing) | Weighted average of the past, with trend and season | Monthly flows; volatile food (non-seasonal form). Cannot take regressors, so no holidays. |
| **Theta** | A simple trend + smoothing combination that won the M3 forecasting competition | Monthly flows. Similar to ETS in practice. |
| **Regression with ARIMA errors** (also called dynamic regression; what X-13 uses) | Regression on calendar and holiday variables, with a time-series model for what is left | **The only classic method that handles moving holidays.** Use for the money stocks and any series where section 5's test passes. |
| **Dynamic harmonic regression** | The same, with sine and cosine waves for the season | Hyndman's recommendation for weekly data when there are regressors |
| **STL + a non-seasonal model** | Remove the season, forecast the rest | Hyndman's recommendation for weekly data when the season changes over time. Weak here (3a). Still the right tool for Phase 2 profiling. |
| **Structural / state-space models** | Trend, season and regressors as separate moving parts | Same abilities as regression with ARIMA errors, with built-in handling of gaps. An option, not needed for v1. |
| **Simple average of 2–3 methods** | Mean of the forecasts | Robust: never the best, never bad. A sound default where no method clearly wins. |
| **Machine learning; pre-trained "foundation" models** | — | Not for v1. Under 1,000 points per series, and the large competitions back this up (below). Could be a challenger in the pilot. |

**What the forecasting competitions found** (M3, M4: thousands of real series, most of them short like ours):
simple statistical methods and averages of them were hard to beat; pure machine-learning entries in M4 scored
below a plain average of three exponential-smoothing variants; Theta and that average were beaten by only 17 of
49 entries. Our own test agrees with the spirit of this and goes further: at one step ahead on these series,
even ETS and Theta add little.

**Why "expected value" still needs a model at all, if naive is so good:** for the flows and money stocks the
gain is real (11–38%), and a smaller typical gap means a tighter band and earlier detection. For the rest, use
naive and spend the effort on the band.

## 5. Moving holidays

Idul Fitri moves about 11 days earlier each year. In 2012–2026 it fell in each of the months March to August
only 2 or 3 times. A model that learns "what June usually looks like" therefore mixes Idul Fitri years with
ordinary ones, and gets both wrong. Decomposition methods (STL) and ETS have the same problem.

**The standard fix** (used in official seasonal adjustment, including BPS's Ramadan adjustment of GDP) is a
regressor that says how much of the holiday window falls in each period:

| Frequency | Regressor | Used in the probe |
|---|---|---|
| Monthly | Share of the 14 days before Idul Fitri that fall in the month; share of the 7 days from Idul Fitri that fall in the month | Yes |
| Weekly | One dummy for each week from 4 weeks before to 2 weeks after | Yes |

The dates come from [holiday_calendar.csv](../DataFoundation/holiday_calendar.csv) and are known years ahead,
so they can be used in a real forecast.

**Result, per series** (error relative to the same model without the regressors):

| Series | Without | With | Verdict |
|---|---|---|---|
| Currency in circulation | 2.33% | 1.87% | **Use** |
| Narrow money (M1) | 1.20% | 1.04% | **Use** |
| ATM/debit transaction value | 4.59% | 4.09% | **Use** |
| RTGS volume; ATM/debit volume | 8.79%; 3.39% | 8.39%; 3.24% | Small gain |
| Demand deposits; credit card flows | — | slightly worse | No |
| E-money flows; RTGS value | — | 4–30% worse | **No** |
| Food: red chili, beef | — | 6% and 2% better than naive | Small gain |
| Food: chicken, shallot, eggs, bird's-eye chili | — | no change | No |
| Food: rice, garlic, cooking oil, sugar | — | 8–23% worse | **No** |

So the `holiday_adj = yes` settings in the inventory (all flows; chicken, beef and shallot) are **not confirmed
by this test**. Two cautions before changing them: the probe's regressors are crude (a different window, or a
Ramadan-long ramp, may fit food better), and with only 8 Idul Fitri in the weekly data a 7-dummy model is
easy to overfit. Pooling the three markets of a commodity to estimate one shared effect would help.

**Where no regressor is used, still label the period.** A flag in an Idul Fitri window should say so in its
reason, as the Hampel notebook already does with "recurring" events.

## 6. The scale and the band

| Option | How | Verdict for us |
|---|---|---|
| Formula bands from the model | ETS or ARIMA formula, assumes bell-curve errors with a fixed spread | Too wide here (3b), and wrong in the tails (3c). Don't rely on them. |
| **Empirical bands from past forecast errors** (this is "split conformal prediction" in its simplest form) | Band = forecast ± the 95th percentile of the absolute out-of-sample errors in a calibration window | **Recommended.** It needs no assumptions and got 95–96% in the test. The window is the main setting. |
| **Scaled version** | First divide each error by a local spread (rolling MAD with the floor), then take the percentile | Recommended where volatility clusters (food). Bands widen in turbulent stretches and narrow in calm ones. |
| Adaptive conformal methods (ACI, EnbPI, conformal PID) | Adjust the band continuously so long-run coverage stays at 95% even when the data's behaviour changes | **Use with care.** They are built to *absorb* changes in behaviour. That is the opposite of an alarm: after a few misses the band widens until the misses stop. Fine for the drill-down chart; not for the alert rule. |

**Choices that matter more than the method:**

- **Window.** Long enough to estimate a 95th percentile (100+ weekly points, 36+ monthly), short enough to
  follow the present. The test used 104 weeks and 36 months. Seasonal series may need errors compared within
  the same season; test it.
- **Clean calibration set.** Leave out masked errors, confirmed events and anything in the "exclude from
  baseline" list (design note, section 5). Add a guard band of 1–2 periods.
- **Out-of-sample errors only.** In-sample residuals are too small and give bands that are too narrow.
- **Asymmetry.** Use separate upper and lower percentiles where rises and falls differ (food prices spike up
  and ease down), and because `bad_direction` makes one side matter more.

## 7. The surprise score

A score that means the same thing for every series, and that the Phase 5 thresholds can use directly:

`p = (1 + number of calibration gaps at least as large as today's gap) ÷ (1 + number of calibration gaps)`

- p = 0.01 reads as "a gap this large happened in about 1% of comparable past periods".
- It is the same calculation as the empirical band (today's value is outside the 95% band exactly when
  p < 0.05), so chart and score can never disagree.
- It is a valid p-value under mild conditions (Bates et al. 2023), which is what the false-discovery-rate rule
  in the design note needs.
- Its resolution is limited by the window: with 104 calibration points the smallest possible p is about 0.01.
  To rank the extreme cases, keep the scaled gap (gap ÷ local spread) next to it.
- Keep the **sign** and apply `bad_direction` afterwards, so one score serves "bad", "good" and "both".

## 8. Q2 checks

| Check | How | Problem | Fix |
|---|---|---|---|
| **Year-on-year change vs its own history** | Rank today's YoY change among past YoY changes | **Echo:** a shock in March 2025 makes March 2026 look unusual in the other direction. **Idul Fitri:** shifts between months. **Overlap:** consecutive YoY values share 11 of 12 months, so history holds fewer independent values than it seems. | Skip or label comparisons whose base period was itself flagged or lies across a break. Use the Idul Fitri-adjusted series where section 5 says "use". |
| **Same-period percentile** | Rank today's value (or its growth) among the same month or week in past years | **Too few values.** 14 past Julys: the most extreme possible rank is 1 in 15, about 7%, so it can never reach a 5% line. For weekly data, 7 values: 12.5%. | Pool neighbouring periods, as the Farrington outbreak algorithm does: the same week ± 3 over 7 years gives 49 values. Work on detrended data or on growth rates, never on raw levels of a trending series. |
| **Recent-window baseline** | Today vs the median of the last 13 weeks or 6 months | Slow to react to a real shift; fine by design | Add a guard band. This check is the one that catches slow drifts. |
| **Short + long growth combined** (FAO's food price anomaly indicator) | 3-month and 12-month growth, each standardised against the same month in past years, weighted 40/60 | Same small-sample and Idul Fitri problems | A good template for the *combined* Q2 score, with the fixes above and our own thresholds |
| **Trend + month dummies** (WFP's ALPS) | Regress on a line and 12 month dummies; score the residual | Straight-line trend; breaks; shocks widen its spread | Shows Q2 can be a model-based expectation too: a deliberately *slow* forecast (trend + season, no memory of recent values) is the natural partner to Q1's fast one |

A design point follows from the last row: **Q1 and Q2 can be the same machinery with two different
expectations**, a fast one and a slow one, both scored as in section 7. That is less code than a separate set of
Q2 statistics, and it makes the two answers comparable.

## 9. Backtest design

The plan's rolling-origin framework is the right one. Details that the research and the probe add:

| Topic | Recommendation |
|---|---|
| **Scheme** | Expanding window, one step ahead, refit at each origin (or every few origins for speed: the full probe took 20 minutes on 4 cores, nearly all of it refitting ETS weekly) |
| **Horizon** | One step, but defined by **publication**: when month M arrives (around the 15th of M+2), the forecast may use data to M−1 only. If two months arrive together, judge them in order. |
| **Point accuracy** | Mean absolute error on the log scale (reads as %). Always report it relative to naive; this is the idea behind the MASE measure. Avoid MAPE. |
| **Bands** | Coverage (target 95%) **and** width, together. Coverage alone rewards wide bands. The interval score (Winkler score) combines both in one number. |
| **By regime** | Report coverage separately for calm and turbulent stretches, and for Idul Fitri windows. An average of 95% can hide 99% and 80%. |
| **What to exclude from scoring** | Missing and masked periods. Keep known events **in** the scoring but report them separately: they are where the bands *should* fail. |
| **Revisions** | The latest 2 periods are provisional and the backtest uses final values, so its results are a little optimistic. Note it; measure it in the pilot from the archived first releases. |
| **Synthetic anomalies** | Inject a jump of k × the local spread at random dates and record how often the score crosses the line, for k = 2, 3, 4, 6. This turns "the band is 2.4% wide" into "a 3% jump in rice is caught 9 times in 10". |

## 10. A simpler shape for Phase 3

| Plan item | Suggestion | Reason |
|---|---|---|
| Naive and seasonal naive baselines | Keep naive as the Q1 benchmark. Move seasonal naive to Q2. | 3a |
| ETS, Theta, pick the best by backtest | Build naive, ETS and one regression model with Idul Fitri terms. Assign by rule: naive unless a model beats it by a clear margin (say 10%) in the backtest; else the model, or the average of two. | 3a: gains are small and uneven; a margin stops noise from choosing |
| Prediction intervals, simple then conformal | Go straight to empirical bands from out-of-sample errors, with a recent, cleaned window and local scaling. | 3b, section 6 |
| Coverage check | Add width, and coverage by regime. | Section 9 |
| Q2: YoY, percentile rank, recent window | Build them as a slow expectation scored like Q1, with pooled neighbouring periods and echo handling. | Section 8 |
| Surprise score | The p-value of section 7, signed, plus the scaled gap. | Section 7 |
| — (new) | A list of periods excluded from calibration, and the `breaks` table. | 3b; design note section 5 |
| — (new) | Re-test `holiday_adj` per series before using it. | Section 5 |

**Tools.** `statsmodels` covers everything above and is what the probe used: `ETSModel`, `ThetaModel`,
`STLForecast`, and `SARIMAX` or `UnobservedComponents` for regression with holiday terms. It is slow when
refitting thousands of times. Nixtla's `statsforecast` is built for exactly that (fast ETS and Theta, a
rolling-origin function, conformal bands); I have not tested it here. `ruptures` remains the choice for
Phase 4 changepoints. The empirical bands and the p-value need only numpy.

## 11. Limits of the probe

- 54 series; the 12 consumer survey series are not covered.
- Final (revised) values, not first releases.
- Default model settings, no tuning. STL + ETS and the weekly Idul Fitri dummies in particular could be done
  better.
- The test span (2021/2023 onwards) is calmer than the full history. That is part of the finding in 3b, but it
  also means coverage in a future crisis will be lower than 95%, as it should be.
- Nothing was excluded from fitting: known data errors and events are in the training data, as they would be
  in a naive first build.

## 12. Sources

Re-read for this note:

- Hyndman & Athanasopoulos, *Forecasting: Principles and Practice* (3rd ed.), section 13.1 "Weekly, daily and
  sub-daily data": STL + non-seasonal model, or dynamic harmonic regression; "The best way to deal with moving
  holiday effects is to include dummy variables in the model", which ETS cannot do. https://otexts.com/fpp3/weekly.html
- FAO, *SDG indicator 2.c.1 metadata* (2024). https://unstats.un.org/sdgs/metadata/files/Metadata-02-0C-01.pdf
- Bates, Candès, Lei, Romano & Sesia (2023), "Testing for outliers with conformal p-values", *Annals of
  Statistics* 51(1). https://arxiv.org/abs/2104.08279
- Angelopoulos, Candès & Tibshirani (2023), "Conformal PID control for time series prediction", NeurIPS.
  https://arxiv.org/abs/2307.16895 (also summarises ACI and its tendency to widen without limit after misses)
- Zaffran et al. (2022), "Adaptive conformal predictions for time series". https://arxiv.org/abs/2202.07282
- M4 competition summaries: https://blogs.sas.com/content/forecasting/2020/01/08/m4-forecasting-competition-results-and-commentary
- BPS (2019), *Seasonal adjustment of Ramadan effect in GDP by expenditures*.
  https://www.bps.go.id/en/publication/2019/12/23/9d9299d3e823e5996d4823a2/penyesuaian-musiman-dengan-efek-ramadhan-pada-pdb-pengeluaran.html

Cited from memory, not re-read:

- Makridakis, Spiliotis & Assimakopoulos (2020), "The M4 Competition", *International Journal of Forecasting*;
  Assimakopoulos & Nikolopoulos (2000) on the Theta method.
- Hyndman & Koehler (2006), "Another look at measures of forecast accuracy" (MASE); Gneiting & Raftery (2007),
  "Strictly proper scoring rules" (interval score); Tashman (2000) on rolling-origin evaluation.
- Gibbs & Candès (2021), "Adaptive conformal inference under distribution shift"; Xu & Xie (2021), "Conformal
  prediction interval for dynamic time-series" (EnbPI).
- Bell & Hillmer (1983) on moving-holiday regressors in seasonal adjustment.
- WFP ALPS technical guidance note (2014).
