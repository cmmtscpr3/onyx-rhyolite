# Early Warning System — Progress Checklist

Tracks progress against [WORKPLAN.md](WORKPLAN.md).
Tick a box (`[x]`) when an item is done. Update the status table when a phase starts or ends.

**Status key:** ⬜ Not started · 🟡 In progress · ✅ Done · ⏸️ On hold · ❌ Dropped

## Status overview

| Phase | Target dates | Status | Checkpoint passed? | Notes |
|---|---|---|---|---|
| 0. Scoping & setup | 5 – 11 Oct 2026 | ⬜ | ⬜ | |
| 1. Data foundation | 12 – 25 Oct 2026 | ⬜ | ⬜ | |
| 2. Profiling | 26 Oct – 8 Nov 2026 | ⬜ | ⬜ | |
| 3. Expected-value checks | 9 – 29 Nov 2026 | ⬜ | ⬜ | |
| 4. Anomaly & change detection | 16 Nov – 6 Dec 2026 | ⬜ | ⬜ | |
| 5. Early warning layer | 30 Nov – 20 Dec 2026 | ⬜ | ⬜ | |
| 6. Pilot & tuning | from 21 Dec 2026 | ⬜ | ⬜ | |
| 7. Cross-indicator (optional) | after v1 | ⬜ | ⬜ | |

---

## Phase 0 — Scoping & setup (week 1)

- [ ] List all indicators: name, frequency, source, owner, and which direction is "bad"
- [ ] Record history length per indicator (start date, number of points)
- [ ] Decide scope: include quarterly series (QRIS)? Include ibid auction data?
- [ ] Describe how analysts handle unusual values today
- [ ] List 5–10 known past events the system should catch
- [ ] Identify end users and the tools they use for reports
- [ ] Agree on the standard input format (long format: `series_id, ref_date, value, frequency, unit`)
- [ ] Set up the code structure and environment under `EarlyWarning/`
- [ ] **◆ Checkpoint:** scope and known-event list agreed

## Phase 1 — Data foundation (weeks 2–3)

- [ ] Loader for `Dataset/Consumption/` CSVs
- [ ] Loader for PIHPS food price Excel files (traditional, modern, wholesale)
- [ ] (If in scope) Turn ibid listings into weekly indicators
- [ ] Validation checks: missing dates, duplicates, zeros and negatives, unit changes
- [ ] Calendar rules: week-ending day, ISO weeks, 53-week years
- [ ] Holiday and event table: Ramadan, Idul Fitri, Christmas, New Year, Lunar New Year, COVID
- [ ] Choose a transform per indicator (level, log or % change)
- [ ] Decide how to handle revisions (check whether `Dataset/Backup/` snapshots help)
- [ ] Data quality report per indicator
- [ ] Tag low-confidence indicators (short history)
- [ ] **◆ Checkpoint:** usable indicator list confirmed

## Phase 2 — Profiling (weeks 4–5)

- [ ] Robust STL (or MSTL) decomposition for each indicator
- [ ] Seasonal strength and trend strength scores
- [ ] Mann-Kendall test and Sen's slope (full and rolling windows)
- [ ] Baseline volatility (rolling MAD)
- [ ] Profile card per indicator
- [ ] Group indicators by behaviour (seasonal, trending, noisy, stable)
- [ ] Review the profiles with an analyst
- [ ] **◆ Checkpoint:** profiles match analyst knowledge

## Phase 3 — Expected-value checks, Q1 & Q2 (weeks 6–8)

- [ ] Rolling-origin backtest framework
- [ ] Q1 forecasts: naive and seasonal naive baselines
- [ ] Q1 forecasts: ETS
- [ ] Q1 forecasts: Theta
- [ ] Pick the best model per indicator by backtest error
- [ ] Prediction intervals (simple)
- [ ] Prediction intervals (conformal)
- [ ] Interval coverage check (for example, about 95% of actual values inside a 95% band)
- [ ] Q2: YoY change vs its own history
- [ ] Q2: same-period percentile rank
- [ ] Q2: recent-window baseline (3 or 6 months)
- [ ] Surprise score for every indicator and period
- [ ] **◆ Checkpoint:** forecasts and intervals good enough

## Phase 4 — Anomaly & change detection (weeks 7–9)

- [ ] Point outliers: robust z-score on the STL remainder
- [ ] Point outliers: Hampel filter
- [ ] Level shifts: CUSUM
- [ ] Level shifts: EWMA control chart
- [ ] Changepoints: PELT
- [ ] (If needed) Bayesian online changepoint detection
- [ ] Volatility regime detector
- [ ] Synthetic anomaly test set (injected spikes and shifts)
- [ ] Hit/miss report on known events: caught, missed, how early
- [ ] Drop detectors that are too noisy
- [ ] **◆ Checkpoint:** final detector set chosen

## Phase 5 — Early warning layer & output (weeks 9–11)

- [ ] Combined score design (start simple: count of signals that agree)
- [ ] Traffic-light levels (green, amber, red)
- [ ] Persistence rules (for example, 2 of the last 3 periods outside the band)
- [ ] Direction rules per indicator
- [ ] Plain-language reason for each flag
- [ ] Thresholds set by target alert rate, using the backtest
- [ ] Watchlist view ranked by score
- [ ] Drill-down charts per indicator
- [ ] "New or cleared since last period" view
- [ ] Decide the output home (`Dashboard/`, HTML report or Excel)
- [ ] Analyst demo
- [ ] **◆ Checkpoint:** analysts find it useful and clear

## Phase 6 — Pilot & tuning (week 12+)

- [ ] Run each period alongside the current process
- [ ] Alert feedback capture ("useful" or "noise")
- [ ] Tune thresholds per indicator (record changes in the tuning log)
- [ ] Automate runs after the collector workflows
- [ ] Scheduled model refits
- [ ] Run logging
- [ ] Handover docs: adding an indicator, reading the report
- [ ] **◆ Checkpoint:** go-live decision

## Phase 7 — Cross-indicator view (optional)

- [ ] Aggregate weekly indicators to monthly
- [ ] Cross-correlation to find leading indicators
- [ ] Sense-check leading indicators with analysts
- [ ] Theme-level scores (food prices, payments, savings and others)

---

## Decision log

Record key choices so we remember why things are the way they are.

| Date | Decision | Reason |
|---|---|---|
| | | |

## Known events (test set)

Fill this in during Phase 0.

| Event | Date(s) | Indicators affected | Expected signal |
|---|---|---|---|
| | | | |

## Open questions

- [ ] Include quarterly indicators?
- [ ] Include ibid auction data, and if so, what indicator?
- [ ] Which output format do analysts prefer?
- [ ] Which food price level: national only, or by region too?
