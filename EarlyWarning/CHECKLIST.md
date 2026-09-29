# Early Warning System — Progress Checklist

Tracks progress against [WORKPLAN.md](WORKPLAN.md).
Tick a box (`[x]`) when an item is done. Update the status table when a phase starts or ends.

**Status key:** ⬜ Not started · 🟡 In progress · ✅ Done · ⏸️ On hold · ❌ Dropped

## Status overview

| Phase | Target dates | Status | Checkpoint passed? | Notes |
|---|---|---|---|---|
| 0. Scoping & setup | 5 – 11 Oct 2026 | 🟡 | ⬜ | Started early (29 Sep). Scope docs in [Scope/](Scope/) |
| 1. Data foundation | 12 – 25 Oct 2026 | ⬜ | ⬜ | |
| 2. Profiling | 26 Oct – 8 Nov 2026 | ⬜ | ⬜ | |
| 3. Expected-value checks | 9 – 29 Nov 2026 | ⬜ | ⬜ | |
| 4. Anomaly & change detection | 16 Nov – 6 Dec 2026 | ⬜ | ⬜ | |
| 5. Early warning layer | 30 Nov – 20 Dec 2026 | ⬜ | ⬜ | |
| 6. Pilot & tuning | from 21 Dec 2026 | ⬜ | ⬜ | |
| 7. Cross-indicator (optional) | after v1 | ⬜ | ⬜ | |

---

## Phase 0 — Scoping & setup (week 1)

Documents: [SCOPE.md](Scope/SCOPE.md) · [indicator_inventory.csv](Scope/indicator_inventory.csv) · [DATA_SPEC.md](Scope/DATA_SPEC.md) · [KNOWN_EVENTS.md](Scope/KNOWN_EVENTS.md)

- [x] List all indicators: name, frequency, source, theme (66 series in the inventory)
- [x] Record history length per indicator (start, end, number of points, gaps)
- [x] Decide scope: monthly and weekly only; ibid, QRIS, OJK, short and quarterly series left out
- [x] Propose the "bad" direction for each indicator
- [ ] **You:** confirm the "bad" direction for each indicator (`bad_direction_status` → `confirmed`)
- [x] Draft 10 candidate known events, plus recurring and data events
- [ ] **You:** confirm, edit or add known events
- [ ] **You:** describe how analysts handle unusual values today
- [ ] **You:** identify end users and the tools they use for reports
- [x] Agree on the standard input format (long format: `series_id, ref_date, value, frequency, unit`)
- [ ] **You:** set up the code structure and environment under `EarlyWarning/`
- [ ] **◆ Checkpoint:** scope and known-event list agreed

## Phase 1 — Data foundation (weeks 2–3)

- [ ] Loader for `Dataset/Consumption/` CSVs (4 files, see [DATA_SPEC.md](Scope/DATA_SPEC.md))
- [ ] Loader for PIHPS food price Excel files (10 groups numbered 1–10 × traditional, modern, wholesale)
- [ ] Map PIHPS weeks to a common week convention (ISO weeks, Monday dates)
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
| 2026-09-29 | Scope is monthly and weekly datasets only | Keep v1 focused |
| 2026-09-29 | Leave out ibid, QRIS and OJK | Your decision |
| 2026-09-29 | Food prices: 10 groups (numbered 1–10) × 3 markets = 30 series; no sub-items | Your decision; keeps the list manageable |
| 2026-09-29 | Consumer survey: 12 headline series only | Brackets add detail, not new signals; 21 series stopped in 2019–2020 |
| 2026-09-29 | Leave out SEKI deposits and e-commerce GMV for now | Too little history (19–35 months) |
| 2026-09-29 | Leave out quarterly series (SEKI GDP, currency ratios) | Outside monthly/weekly scope |
| 2026-09-29 | Standard input format: `series_id, ref_date, value, frequency, unit` | Matches the existing consumption CSVs |

## Known events (test set)

See [KNOWN_EVENTS.md](Scope/KNOWN_EVENTS.md) (draft, to confirm).

## Open questions

- [x] Include quarterly indicators? **No** (see decision log)
- [x] Include ibid auction data? **No** (see decision log)
- [x] Which food price level: national only, or by region too? **National only**, which is all PIHPS provides here
- [ ] Which output format do analysts prefer?
- [ ] Should the 3 food markets roll up into one view per group, or stay separate?
- [ ] How often should the report run: monthly after the 15th, or weekly with the food prices?
