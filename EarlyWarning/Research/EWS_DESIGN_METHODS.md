# Research 1 — How early warning systems are designed

What established early warning systems do, which of their methods fit this project, and what that means for
Phases 3–6 of [the work plan](../WORKPLAN.md). The forecasting side is in
[EXPECTED_VALUE_FORECASTING.md](EXPECTED_VALUE_FORECASTING.md).

> **Status (20 Nov 2026): research notes, nothing here is decided.** Section 8 lists the changes I'd suggest to
> the plan. Section 9 says which sources I re-read for this note and which I cite from memory.

---

## 1. The short version

1. **Our system is a surveillance system, not a crisis predictor.** That decides which literature applies
   (section 2). The closest relatives are the food-price monitors of WFP and FAO and the outbreak detection
   systems of public health agencies. Both are built exactly like our plan: expected value → gap → score →
   threshold.
2. **Every mature system has the same five parts** (section 4): a baseline that says what is normal, a
   standardised gap from it, a threshold, a rule for persistence, and a human who reviews the alert.
   The parts differ far less between systems than the care taken over the baseline.
3. **The baseline must not learn from past anomalies.** Public health systems down-weight past outbreaks when
   they fit the baseline. Without this, COVID and the 2022 cooking oil crisis widen our bands for years and
   hide the next event (section 5).
4. **Set thresholds from an alert budget, not from "95%".** With 66 indicators, 95% bands give about 3 false
   flags every run even when nothing is happening (section 6).
5. **Ten known events are too few to tune on.** They can show a detector is not broken. They cannot rank two
   good detectors. Injected synthetic anomalies have to carry the tuning (section 7).
6. **"Early" has a ceiling set by publication lag.** Food prices arrive within a week; BI payment data arrives
   2–3 months late. The weekly food series are the only truly early part of the system.

## 2. Two families of early warning system

| | **A. Event prediction** | **B. Surveillance** (ours) |
|---|---|---|
| Question | "Will a defined crisis happen in the next N months?" | "Is this new value unusual, given what we expected?" |
| Needs | A dated list of past crises (dozens) | A model of normal behaviour |
| Method | Supervised: signals approach, logit, machine learning | Unsupervised: forecast, residual, control chart |
| Judged by | Hits and false alarms against the crisis list | Alert rate, hits on known events, time to detect |
| Examples | Currency and banking crisis models (IMF, ECB) | WFP ALPS, FAO IFPA, disease outbreak detection, factory process control |

We have 10 candidate events across 66 series, not dozens of crises, and the goals in the work plan (Q1, Q2)
are about expected values. So we are in family B. We still borrow two ideas from family A: how to **choose a
threshold from the costs of the two kinds of error**, and how to **weight indicators by their track record**
(section 6).

## 3. Reference systems, and what to borrow from each

| System | How it works | What we borrow | What doesn't fit |
|---|---|---|---|
| **WFP ALPS** (Alert for Price Spikes) | For each market and commodity, regress the monthly price on a time trend and 12 month dummies. Indicator = (price − expected price) ÷ standard deviation of the residuals. Four bands: normal, stress, alert, crisis. Also run on forecast prices. | The whole shape of Q2 for food prices. Named bands instead of a bare number. Running the same indicator on a **forecast** to warn before the value arrives. | A straight-line trend and fixed month dummies. Idul Fitri moves, and our prices have level shifts. No protection against past spikes inflating the spread. |
| **FAO IFPA** (indicator of food price anomalies, SDG 2.c.1) | Two growth rates per month: over 3 months and over 12 months. Each is compared with the mean and standard deviation **of the same calendar month in earlier years**. Combined 40% quarterly, 60% annual. Bands: under 0.5 normal, 0.5–1 moderately high, 1 or more abnormally high. | Combining a short and a long horizon in one score, which is our Q1 + Q2. Same-month comparison as the seasonal control. Its minimum-history rule (5 years, at most 3 missing months in a row). | The 1 standard deviation threshold is deliberately sensitive (about 1 month in 6 is "abnormal"). That is too many alerts across 66 series. Same-month statistics break around Idul Fitri. |
| **IFPRI excessive food price variability** | Flags days when a price return is above a high quantile (95%) of its estimated distribution. A period counts as "excessive volatility" only when such days are more frequent than chance allows. | Our volatility-regime detector: count exceedances in a window and test the count, instead of alerting on each one. | Built for daily futures prices. |
| **Farrington algorithm** (UK outbreak detection; improved by Noufaily et al. 2013) | Every week, for every disease: fit a regression to the same weeks (± 3) of the last 5 years, **down-weight past outbreaks**, compute an upper prediction bound, and report an exceedance score = (observed − expected) ÷ (bound − expected). | Closest match to our problem: many series, checked routinely, by few analysts. Borrow the reference window of "same period ± a few, over past years", the down-weighting, and the exceedance score as a ranking. The 2013 revision exists because the original gave **too many alarms**; it cut them by down-weighting less aggressively and by better thresholds. | Count data (cases). Ours are log prices and amounts, so we use ordinary rather than Poisson-type regression. |
| **EARS C1–C3** (US CDC) | Mean and standard deviation of a short recent baseline (7 days). C2 and C3 skip the 2 most recent days (a **guard band**) so an outbreak that has just started doesn't raise its own baseline. | The guard band. Our Hampel test already uses a trailing window; adding a 1–2 period gap would stop a slow build-up from hiding itself. | No seasonality at all. Only a fallback for short series. |
| **Signals approach** (Kaminsky, Lizondo, Reinhart 1998) and its loss-function versions (Alessi & Detken 2011) | Each indicator signals when it crosses a percentile threshold. The threshold is chosen per indicator to minimise the noise-to-signal ratio. Indicators are combined into a composite, weighted by the inverse of that ratio. Later work picks the threshold by minimising a loss that weights missed crises against false alarms. | Per-indicator thresholds expressed as percentiles of the indicator's own history. Weighting signals by how reliable each has been. Stating the miss/false-alarm trade-off as an explicit number. | Needs a crisis list to compute the ratio. With 10 events ours would be noise. |
| **Statistical process control** (Shewhart, CUSUM, EWMA charts) | Monitor the **residuals** of a model, not the raw series. Shewhart catches big single moves; CUSUM and EWMA catch small sustained shifts. Charts are designed by average run length: how long until a false alarm, how long until a real shift is caught. | Already in Phase 4. Borrow the design method: choose chart settings from a target false-alarm interval, and report the expected detection delay for a shift of a given size. | Classic charts assume independent, normal residuals. Ours are heavy-tailed, so limits should come from the backtest, not from tables. |
| **Official seasonal adjustment** (X-13ARIMA-SEATS, TRAMO) | Regression with ARIMA errors, including **moving-holiday regressors** and automatic outlier detection with three named types: additive outlier (one-off spike), level shift, temporary change (spike that decays). BPS has published a Ramadan adjustment of GDP on this basis. | The outlier vocabulary for our plain-language reasons: "spike", "shift", "spike that is fading". The moving-holiday regressor design (see the forecasting note, section 5). | It revises history when new data arrives. An EWS must judge each point once, with the data of the day. |
| **UN multi-hazard EWS checklist** (WMO/UNDRR 2018) | Four elements: risk knowledge; monitoring and forecasting; warning dissemination; response capability. A system fails if any one is missing. | A reminder that Phases 3–4 only cover the second element. The open Phase 0 items (who reads it, what they do today, what they do with an alert) are the other three. | — |

## 4. The common design, mapped to our phases

Every surveillance system above follows the same chain. The table shows the choices at each link.

| Link | The design question | Common answers | Our phase |
|---|---|---|---|
| 1. **Baseline** | What did we expect? | Same period in past years (IFPA, Farrington); trend + seasonal regression (ALPS); forecast model (process control) | 3 |
| 2. **Gap** | How far is the value from that? | Actual − expected, in log units | 3 |
| 3. **Scale** | Is that gap big *for this series, now*? | Divide by a robust spread with a floor; or take the rank of the gap among past gaps | 3 |
| 4. **Kind of change** | Spike, shift, trend change or volatility change? | One detector per kind, all reading the same gaps | 4 |
| 5. **Threshold** | When does a score become an alert? | Fixed bands (ALPS, IFPA); alert budget; cost-weighted loss | 5 |
| 6. **Persistence** | Is one period enough? | 2 of the last 3; cumulative sums; count of exceedances in a window | 5 |
| 7. **Corroboration** | Do related series agree? | Same commodity in 3 markets; same theme | 5 / 7 |
| 8. **Explanation** | Why was it flagged? | Named band + direction + size in % + which check fired | 5 |
| 9. **Review and feedback** | Was it useful? | Analyst marks each alert; thresholds re-tuned on a schedule | 6 |

Two lessons hold across all of them:

- **Most false alarms come from link 1, not link 5.** A baseline that misses a known pattern (a moving holiday,
  a 31-day month, a reporting change) produces alerts no threshold can fix without also hiding real events.
  This is the same finding as our Phase 1 work on calendar effects.
- **Keep the kinds of change apart.** A level shift judged by a spike detector fires once and then looks
  normal. Judged by a year-on-year check, it fires for 12 months. Neither is wrong, but the watchlist should
  say "shifted in March, still at the new level" once, not 12 separate alerts.

## 5. Keeping the baseline clean

The most transferable technical idea in this research. Three practices, in order of effort:

| Practice | From | In our terms |
|---|---|---|
| **Robust statistics** | General | Median and MAD instead of mean and standard deviation; robust STL. Already our direction. |
| **Guard band** | EARS | The baseline window ends 1–2 periods before the point being judged. |
| **Down-weight or mask past anomalies** | Farrington | Periods the system flagged (and an analyst confirmed), plus the known events, get low or zero weight when models and spreads are re-estimated. Our `data_issues.csv` already does this for data errors; the same mechanism can serve for real events, with a different action name (for example `exclude_from_baseline`). The value stays visible; it just stops teaching the model what "normal" is. |

A related rule: **after a confirmed level shift, reset the baseline** (the `breaks` table from
[TRANSFORMS.md](../DataFoundation/TRANSFORMS.md), step 6, which v1 dropped). Without it, year-on-year checks
echo every shift for a year, and again in reverse a year later when the shifted value becomes the comparison base.

## 6. Thresholds: alert budgets, not confidence levels

**The arithmetic.** A 95% band is wrong 5% of the time by design.

| | Series | False flags per run at 95% | Per year |
|---|---|---|---|
| Weekly food prices | 30 | 1.5 | about 78 |
| Monthly indicators | 36 | 1.8 | about 22 |

And that is for one check. Q1, Q2 and four detectors per series multiply it. Three ways to handle this, from
simplest to most formal:

1. **Alert budget (recommended start).** Ask the analysts how many items they can review per run (say 5).
   Rank all series by score and set the amber/red lines so the backtest produces that many on average.
   This is the "target alert rate" already in Phase 5; the point here is to make it the *primary* rule.
2. **False discovery rate.** Turn each score into a p-value (the forecasting note, section 7, shows a simple
   way), then apply the Benjamini–Hochberg rule across the series in each run. It adapts by itself: few alerts
   in quiet periods, many when a real shock moves many series.
3. **Cost-weighted loss** (Alessi & Detken). Choose the threshold that minimises
   `θ × miss rate + (1 − θ) × false alarm rate`, where θ says how much worse a miss is than a false alarm.
   Useful mainly as a question for the end users: "is a missed event 2× or 10× as bad as a wasted review?"

**Count related series once.** The three markets of one commodity report the same underlying price. For
volatile goods they move together week by week (red chili, traditional vs wholesale: correlation 0.58); for
sticky ones they adjust at different times (rice: 0.13). Either way, rice rising in all three is one event,
and it is also stronger evidence than rice rising in one. So corroboration should raise the
*rank* of a single watchlist line, not add lines. This answers the open question in
[SCOPE.md](../Scope/SCOPE.md) on rolling up the markets: keep the 30 series for detection, show 10 lines.

**Named bands.** ALPS and IFPA both publish 3–4 named levels, not a z-score. Our traffic lights do the same.
The research adds one caution: their cut-offs (0.5 and 1 standard deviation for IFPA) are far looser than
anything we could afford across 66 series, so we should copy the idea and not the numbers.

## 7. How to evaluate an early warning system

| Measure | Meaning | Note for us |
|---|---|---|
| **Hit rate** | Share of known events flagged | See the caution below |
| **Time to detect** | Periods from event start to first flag | Count from when the data was *published*, not the period it refers to |
| **Alert rate** | Alerts per run | The quantity the analysts actually feel |
| **Precision** | Share of alerts that were useful | Only measurable in the pilot, from analyst feedback |
| **Unexplained episodes** | Flags with no known cause | Each is a missing event or a false alarm; the Hampel notebook already lists them |
| **Average run length** | Periods between false alarms on quiet data | Standard for CUSUM and EWMA design |

**Caution: 10 events is a very small test set.** If a detector catches 8 of 10, the 95% confidence interval for
its true hit rate is about 44% to 97%. A detector that catches 7 is not measurably worse. So:

- Use the known events as a **sanity check** ("does it catch COVID and the cooking oil crisis?"), and to find
  wrong event dates.
- Use **injected anomalies** for tuning and for comparing detectors: add spikes, steps, ramps and volatility
  bursts of known size (in units of each series' own spread) to quiet stretches of real data, at random dates,
  hundreds of times. This gives detection probability and delay as a function of size, with tight error bars.
  It is how the Farrington revision and most process-control designs were evaluated.
- Do not tune on the same events you report results on. With 10 events, any tuning will overfit them.

**Judge the system as it will run.** Three things make a backtest look better than live use:

| Trap | Why | Fix |
|---|---|---|
| Revised data | The backtest sees final values; the live system sees first releases | Mark the result as optimistic; start archiving first-reported values now (already decided in Phase 1) so the pilot can measure the difference |
| Centred windows | Using future data around a point | Trailing windows only. The Hampel notebook found the same. |
| Models fitted on the full history | Seasonal patterns and spreads learned from data after the test date | Rolling-origin backtest: refit using only data before each date |

## 8. Suggested changes to the plan

None of these adds a new model. They change how existing items are done.

| # | Suggestion | Where | Why |
|---|---|---|---|
| 1 | Add an "exclude from baseline" list for confirmed real events, using the `data_issues.csv` mechanism | Phase 3 | Section 5: stops COVID and policy shocks widening the bands |
| 2 | Bring back the `breaks` table for confirmed level shifts | Phase 3 | Section 5: stops year-on-year echoes |
| 3 | Make the alert budget the primary threshold rule; ask analysts for the number | Phase 5 (ask now) | Section 6 |
| 4 | One watchlist line per commodity, ranked higher when markets agree | Phase 5 | Section 6 |
| 5 | Build the synthetic-anomaly injector early and share it between Phases 3 and 4 | Phase 3–4 | Section 7: the known events can't carry the tuning |
| 6 | Report time to detect from the publication date | Phase 4 | Section 1, point 6 |
| 7 | Add a guard band of 1–2 periods to trailing baselines | Phase 4 | Section 3 (EARS) |
| 8 | Close the open Phase 0 items on users and current process before Phase 5 | Phase 0 | Section 3 (UN checklist): detection without a response path is not a warning system |

**Later, not v1:** `Dataset/BPS-Inflation/` now holds official inflation. Once it has a loader, weekly PIHPS
prices could be tested as an early read on monthly volatile-food inflation. That would give the system a
*target* to be early about, which moves part of it into family A. It is a Phase 7 question.

## 9. Sources

Re-read for this note:

- FAO, *SDG indicator 2.c.1 metadata* (updated 29 Jul 2024): IFPA formulas, the 0.4 weight, the 0.5 and 1
  thresholds, the 5-year rule. https://unstats.un.org/sdgs/metadata/files/Metadata-02-0C-01.pdf
- WFP, *ALPS: calculation and use of the Alert for Price Spikes indicator* (technical guidance note, April 2014;
  VAM resource page updated Oct 2025): trend + monthly dummies by least squares, four bands, use on forecasts.
  https://vamresources.manuals.wfp.org/docs/alps-calculation-and-use-of-the-alert-for-price-spikes-indicator
- Noufaily et al. (2013), "An improved algorithm for outbreak detection in multiple surveillance systems",
  *Statistics in Medicine* 32(7). Summary and the R implementation notes:
  https://surveillance.r-forge.r-project.org/pkgdown/reference/farringtonFlexible.html
- Kaminsky, Lizondo & Reinhart (1998), "Leading indicators of currency crises", *IMF Staff Papers* 45(1).
  https://econpapers.repec.org/RePEc:pal:imfstp:v:45:y:1998:i:1:p:1-48 (read through secondary summaries)
- WMO/UNDRR (2018), *Multi-hazard early warning systems: a checklist*.
  https://globalplatform.undrr.org/2022/sites/default/files/2022-02/Multi-hazard%20Early%20Warning%20Systems-%20A%20Checklist.pdf
- BPS (2019), *Seasonal adjustment of Ramadan effect in GDP by expenditures*.
  https://www.bps.go.id/en/publication/2019/12/23/9d9299d3e823e5996d4823a2/penyesuaian-musiman-dengan-efek-ramadhan-pada-pdb-pengeluaran.html

Cited from memory, not re-read (check before quoting them elsewhere):

- The exact ALPS band cut-offs. I recall under 0.25 normal, 0.25–1 stress, 1–2 alert, 2 or more crisis, but I
  could not open the guidance note PDF to confirm.
- Baquedano (2015), "Developing an indicator of price anomalies as an early warning tool", FAO.
- Martins-Filho, Yao & Torero, IFPRI excessive food price variability early warning system.
- Farrington et al. (1996), "A statistical algorithm for the early detection of outbreaks of infectious
  disease", *JRSS A*; Hutwagner et al. (2003) on EARS C1–C3. The "± 3 weeks, 5 years" window and the 2-day
  guard band are the usual defaults.
- Alessi & Detken (2011), "Quasi real time early warning indicators for costly asset price boom/bust cycles",
  *European Journal of Political Economy*.
- Chen & Liu (1993), "Joint estimation of model parameters and outlier effects in time series", *JASA*
  (the outlier types); Alwan & Roberts (1988) on control charts for model residuals.
