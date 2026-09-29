# Early Warning System — Work Plan

A plan to build an early warning system (EWS) that tracks our monthly and weekly
indicators, finds trend, seasonality, volatility and anomalies, and points
analysts to the indicators that need attention.

Progress is tracked in [CHECKLIST.md](CHECKLIST.md).

---

## 1. Goals

The system should answer two questions for every new data point:

- **Q1 — Short-term:** Is this value what we expected, given the last period?
- **Q2 — Long-term:** Is this value expected, given a year ago or the last few months?

It should also:

- Show the trend, seasonality and volatility of each indicator.
- Detect anomalies: spikes, level shifts, trend changes and volatility changes.
- Turn all signals into a short, ranked watchlist with a plain-language reason for each flag.

## 2. Assumptions

- **Team:** you and Claude as the core team, with an analyst joining at a few checkpoints.
- **Pace:** part-time, about 1–2 working sessions per week.
- **Scale:** 10–50 indicators to start. Hundreds of indicators add about 1–2 weeks to Phases 1 and 5.
- **Data size:** under 1,000 points per indicator, so we use classic statistical methods, not ML or deep learning.
- **History:** monthly series need 3+ years and weekly series 2+ years for reliable seasonality. Shorter series get simpler checks and a "low confidence" tag.
- **Tools:** Python with pandas, statsmodels and a changepoint library (for example, ruptures).
- **Start date:** week 1 starts **Mon 5 Oct 2026**. Dates shift if the start moves.

## 3. What already exists in this repo

These give Phase 1 a head start. We still need to check each one.

- **`Collectors/`** already collects data on weekly, monthly and quarterly schedules (GitHub Actions).
- **`Dataset/Consumption/`** is mostly in a shared long format (`series_id, geo_id, geo_name, ref_date, value, unit`).
- **`Dataset/Food Prices/PIHPS/`** holds food prices by region for traditional markets, modern markets and wholesale, as yearly Excel files.
- **`Dashboard/`** is an existing app. It could host the EWS output.

Things to watch for:

- **Short histories:** some series start in 2023 (e-commerce GMV) or 2025 (`bi_seki`).
- **Quarterly data:** QRIS is quarterly, which is outside our monthly/weekly scope. We need to decide whether to include it.
- **Different format:** the ibid car and motor files are auction listings, not time series. They would need to be turned into an indicator first (for example, median price or sell-through rate per week).
- **Moving holidays:** Ramadan and Idul Fitri move about 11 days earlier each year. They drive food prices and consumption, so the holiday calendar is critical.

## 4. Workplan map

```
 Phase 0        Phase 1          Phase 2          Phase 3
 Scoping   ──►  Data         ──► Profiling    ──► Expected-value
 & setup        foundation       (trend, season)  checks (Q1 & Q2)
                                                        │
                                                        ▼
 Phase 7        Phase 6          Phase 5          Phase 4
 Cross-     ◄── Pilot &      ◄── Early warning ◄── Anomaly &
 indicator      tuning           layer + output   change detection
 (optional)
```

## 5. Timeline

```
Week:              1   2   3   4   5   6   7   8   9   10  11  12  13+
Phase 0 Scoping    ███
Phase 1 Data           ███████
Phase 2 Profiling              ███████
Phase 3 Q1 & Q2                        ███████████
Phase 4 Anomaly                                ███████████
Phase 5 EWS layer                                      ███████████
Phase 6 Pilot                                                  ███████►
Phase 7 Cross-ind.                                                     ►
Checkpoints        ◆       ◆       ◆           ◆       ◆       ◆
```

| Phase | Weeks | Dates (target) | Checkpoint |
|---|---|---|---|
| 0. Scoping & setup | 1 | 5 – 11 Oct 2026 | Scope agreed |
| 1. Data foundation | 2–3 | 12 – 25 Oct 2026 | Usable indicators confirmed |
| 2. Profiling | 4–5 | 26 Oct – 8 Nov 2026 | Profiles match analyst knowledge |
| 3. Expected-value checks | 6–8 | 9 – 29 Nov 2026 | Forecasts and intervals good enough |
| 4. Anomaly & change detection | 7–9 | 16 Nov – 6 Dec 2026 | Detectors chosen |
| 5. Early warning layer | 9–11 | 30 Nov – 20 Dec 2026 | Analyst demo |
| 6. Pilot & tuning | 12+ | from 21 Dec 2026 (4–8 weeks) | Go-live decision |
| 7. Cross-indicator | after v1 | TBD | — |

Phases 3 and 4 overlap on purpose, because they share the same forecasts and residuals.
Expect a slower pace over the year-end holidays during the pilot.

## 6. Phase details

### Phase 0 — Scoping & setup (week 1)

**Goal:** agree on what we build and for whom.

- Indicator inventory: name, frequency, source, owner, history length, and which direction is "bad".
- How analysts handle unusual values today.
- 5–10 known past events the system should catch. These are our test set.
- End users, and the tools they already use for reports.
- Repo structure, environment and input data format.

**Deliverable:** scope notes, the indicator inventory and the code skeleton.

### Phase 1 — Data foundation (weeks 2–3)

**Goal:** clean, aligned, trusted data. This is where most false alarms get prevented.

- Build a loader that turns every source into one long format (`series_id, ref_date, value, frequency, unit`).
- Add validation checks: missing dates, duplicates, zeros and negatives, sudden unit changes.
- Set calendar rules: week-ending day, ISO weeks and 53-week years.
- Build a holiday and event table: Ramadan, Idul Fitri, Christmas, New Year, Lunar New Year, and shocks like COVID.
- Pick a transform per indicator: level, log or % change.
- Decide how to handle revisions. The `Dataset/Backup/` snapshots may let us rebuild the first-reported values.
- Write a data quality report per indicator.

**Deliverable:** a clean dataset, the data quality report and the holiday table.

### Phase 2 — Profiling (weeks 4–5)

**Goal:** understand each indicator before predicting it.

- Robust STL decomposition (use MSTL where there are several seasonal patterns).
- Seasonal strength and trend strength scores.
- Mann-Kendall test and Sen's slope, on full and rolling windows.
- Baseline volatility (rolling MAD).
- A profile card per indicator, and groups of indicators by behaviour.

**Deliverable:** profile cards and behaviour groups.

### Phase 3 — Expected-value checks, Q1 & Q2 (weeks 6–8)

**Goal:** say whether each new value is expected.

- **Q1:** one-step-ahead forecasts (naive, seasonal naive, ETS, Theta). Pick the best per indicator by backtest.
- Prediction intervals: simple first, then conformal.
- **Q2:** YoY change vs its history, same-period percentile rank, and a recent-window baseline (3 or 6 months).
- Surprise scores for every indicator and period.
- A rolling-origin backtest framework that later phases reuse.

**Deliverable:** surprise scores, a model choice per indicator and a backtest report.

### Phase 4 — Anomaly & change detection (weeks 7–9)

**Goal:** catch the different kinds of "something changed".

- Point outliers: robust z-score on the STL remainder, and a Hampel filter.
- Level shifts: CUSUM and EWMA control charts.
- Changepoints: PELT, and Bayesian online changepoint detection if needed.
- Volatility regime: current rolling MAD vs its history.
- Test against the known events and against synthetic anomalies we inject.

**Deliverable:** the final detector set and a hit/miss report.

### Phase 5 — Early warning layer & output (weeks 9–11)

**Goal:** a short, clear list for analysts.

- Combined score. Start simple: count how many signals agree.
- Traffic lights (green, amber, red) with persistence rules.
- Direction rules per indicator.
- A plain-language reason for every flag.
- Thresholds set by target alert rate, using the backtest.
- Output: a watchlist, drill-down charts, and "new or cleared since last period". This could be added to `Dashboard/`.

**Deliverable:** a working EWS report run on historical data.

### Phase 6 — Pilot & tuning (week 12+, 4–8 weeks)

**Goal:** prove it works on live data.

- Run each period alongside the current analyst process.
- Collect "useful" or "noise" feedback on each alert.
- Tune thresholds per indicator.
- Automate the runs (for example, after each collector workflow), refit on a schedule and log every run.
- Handover docs: how to add an indicator and how to read the report.

**Deliverable:** a production-ready v1 and a tuning log.

### Phase 7 — Cross-indicator view (optional, after v1)

- Aggregate weekly indicators to monthly, then use cross-correlation to find leading indicators.
- Theme-level scores, for example food prices, payments and savings.
- Keep only links that make business sense and hold over time.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Data is messier than expected | Buffer in Phase 1. Exclude bad indicators rather than delay everything. |
| Too many alerts | Persistence rules, target alert rate and analyst feedback |
| Few known events to test against | Inject synthetic spikes and shifts |
| Moving holidays cause false alarms | Holiday table built in Phase 1 and used by every model |
| Scope creep into complex models | Stay simple until the pilot shows a real gap |
| Analysts don't trust the output | Plain-language reasons and early analyst checkpoints |

## 8. Ways of working

- **Every phase ends with a checkpoint.** We review the results together and decide to continue, adjust or cut scope.
- **Keep the checklist current.** Tick items in [CHECKLIST.md](CHECKLIST.md) as they finish, and log decisions in its decision log.
- **Shift dates, not quality.** If a phase slips, move the later dates and note why in the checklist.
