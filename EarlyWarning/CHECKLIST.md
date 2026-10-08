# Early Warning System — Progress Checklist

Tracks progress against [WORKPLAN.md](WORKPLAN.md).
Tick a box (`[x]`) when an item is done. Update the status table when a phase starts or ends.

**Status key:** ⬜ Not started · 🟡 In progress · ✅ Done · ⏸️ On hold · ❌ Dropped

## Status overview

| Phase | Target dates | Status | Checkpoint passed? | Notes |
|---|---|---|---|---|
| 0. Scoping & setup | 5 – 11 Oct 2026 | ⏸️ | ⬜ | Docs done in [Scope/](Scope/). Your checkpoint items deferred. |
| 1. Data foundation | 12 – 25 Oct 2026 | 🟡 | ⬜ | Started early (30 Sep). Specs in [DataFoundation/](DataFoundation/). You write the code. |
| 2. Profiling | 26 Oct – 8 Nov 2026 | 🟡 | ⬜ | Started early (8 Oct). Spec in [Profiling/](Profiling/). You write the code. |
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

Documents: [PHASE1_SPEC.md](DataFoundation/PHASE1_SPEC.md) · [DATA_QUALITY.md](DataFoundation/DATA_QUALITY.md) · [holiday_calendar.csv](DataFoundation/holiday_calendar.csv)

**Specs and decisions (Claude)**

- [x] Output tables defined: `observations` and `quality_report` (spec section 1)
- [x] Loader rules for the consumption CSVs and PIHPS (spec sections 2–3)
- [x] Week rule: ISO weeks with Monday dates, tested on real data (404 weeks, no empty weeks, 4 year-end clashes)
- [x] Quality flags and the masking approach (`data_issues.csv`) (spec section 5)
- [x] Confidence tag rule (spec section 6)
- [x] Revisions checked: latest 2 periods marked provisional; save a copy of each run from now on (spec section 7)
- [x] Transform per indicator (`log` or `level`) and seasonal period added to the inventory
- [x] Holiday and event table drafted, 2009–2027 (117 rows)
- [x] First data quality report, with 5 likely errors and 4 patterns to review
- [x] Acceptance checks listed (spec section 10)
- [x] Validation checks in detail: missing dates, duplicates, zeros and negatives, unit changes, structure ([VALIDATION_CALENDAR.md](DataFoundation/VALIDATION_CALENDAR.md), part A)
- [x] Calendar rules: ISO weeks with Monday `ref_date`, Sunday `week_ending`, 53-week years, weekly-to-monthly rule, holiday features (part B)
- [x] Transformation approach proposed and tested on the data: calendar adjustment, log or level, change measures, seasonal split, robust z with floors, breaks ([TRANSFORMS.md](DataFoundation/TRANSFORMS.md))
- [x] Inventory columns added: `series_kind`, `calendar_adj`, `holiday_adj`, `vol_tier`, `z_floor`

**Code: PIHPS + BI SPIP, 54 series ([README.md](README.md), `ews/`, outputs in `data/`)**

- [x] Loader for the PIHPS Excel files (10 groups numbered 1–10 × 3 markets), reusing the collectors' reader
- [x] Loader for the BI SPIP CSVs (card, e-money, payment system)
- [x] Validation checks: missing dates, duplicates, zeros and negatives, unit changes, structure (M1–M6, D1–D4, Z1, Z5, U1–U4, S1–S3, I1)
- [x] Readable validation log for review (`data/validation_log.txt`, plus `.csv`)
- [x] Calendar rules: ISO weeks with Monday `ref_date`, Sunday `week_ending`, 53-week years, days in month, week-to-month helper
- [x] Transformations: per-day adjustment for the 12 flow series, then log for all 54
- [x] `quality_report.csv`, and each step's output in `data/steps/`
- [x] `data_issues.csv` with the 5 suspects as `review`
- [x] 37 tests, passing on pandas 2.2 and 3.0; `Dataset/` checked untouched
- [x] Dropped (your decision): holiday features, change measures, robust z-scores, breaks

**Your part**

- [ ] Review `data/validation_log.txt`: 26 one-off spikes (U4) to confirm or dismiss
- [ ] Confirm or reject the suspects in `data_issues.csv`; switch confirmed errors to `mask`
- [ ] Loader for the consumer survey CSV (not in this code's scope)
- [ ] **◆ Checkpoint:** usable indicator list confirmed

## Phase 2 — Profiling (weeks 4–5)

Documents: [PHASE2_SPEC.md](Profiling/PHASE2_SPEC.md)

**Spec (Claude)**

- [x] Inputs, outputs and settings defined (spec sections 1–2): `components.csv`, `profile_cards.csv`, `profiles.md`
- [x] Preparation rules: breaks, short-gap interpolation, week 53 (section 3)
- [x] Robust STL settings, with the reason MSTL is not needed (section 4)
- [x] Seasonal and trend strength, robust and textbook versions, shape and stability (section 5)
- [x] Mann-Kendall and Sen's slope, full and rolling, and the `trend_now` label (section 6)
- [x] Baseline volatility: rolling MAD with floor, sticky share, observed tier, tail ratio (section 7)
- [x] Idul Fitri diagnostic (section 8)
- [x] Profile card columns, sentence rules and behaviour groups (sections 9–10)
- [x] Acceptance checks with expected values from a prototype run (section 11)
- [x] Checkpoint agenda (section 12)

**Code (you)**

- [ ] `breaks.csv` seeded from spec section 2
- [ ] Preparation: break cut, interpolation, week-53 handling
- [ ] Robust STL decomposition for each indicator (`components.csv`)
- [ ] Seasonal strength and trend strength scores (robust and textbook)
- [ ] Mann-Kendall test and Sen's slope (full and rolling windows), `trend_now`
- [ ] Baseline volatility (rolling MAD with floor), sticky share, observed tier, tail ratio
- [ ] Idul Fitri diagnostic
- [ ] Profile card per indicator (`profile_cards.csv`, `profiles.md`)
- [ ] Group indicators by behaviour (three axes: trend, season, noise; plus sticky)
- [ ] Tests for the acceptance checks (spec section 11)
- [ ] Review the profiles with an analyst (spec section 12)
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
| 2026-09-30 | Phase 0 checkpoint deferred; Phase 1 started | Your decision |
| 2026-09-30 | Phase 1 split: Claude writes the specs, you write the code | Your decision |
| 2026-09-30 | PIHPS dates mapped to ISO weeks (Monday date); keep the later non-missing reading on a clash | Tested on real data: regular 7-day spacing, no empty weeks |
| 2026-09-30 | Mask confirmed errors instead of deleting them; decisions kept in `data_issues.csv` | Keeps periods visible and every decision documented |
| 2026-09-30 | Latest 2 periods marked provisional | PIHPS and BI both revise recent values |
| 2026-09-30 | `log` transform for amounts, counts and prices; `level` for indices and shares | Tested: log removes the size effect for money and counts; indices move more when low, which is a real signal |
| 2026-09-30 | Flow series divided by days in month | Monthly changes of card flows correlate 0.6–0.7 with month length |
| 2026-09-30 | Weekly year-on-year = 52 weeks back; week 53 shares week 52's seasonal slot | Simple, always defined |
| 2026-09-30 | Weekly → monthly: a week belongs to the month containing its Thursday; monthly value is the mean | ISO rule; each week counted once |
| 2026-09-30 | Robust z-scores use a spread floor, set by volatility tier | Sticky rice prices gave 165 false extremes; 21 remain with the floor |
| 2026-10-01 | Phase 1 code covers PIHPS + BI SPIP (54 series); the consumer survey comes later | Your decision |
| 2026-10-01 | Only two transformations in v1: per-day (flows) and log (all series); no holiday features, change measures, z-scores or breaks | Your decision: keep v1 to what's needed |
| 2026-10-01 | Outputs in `EarlyWarning/data/`; `Dataset/` is read-only | Your decision; tested by hashing `Dataset/` before and after a run |
| 2026-10-01 | Suspected errors are flagged `review`, not masked | Your decision; switch to `mask` once confirmed |
| 2026-10-01 | SPIP freshness: month M is expected after the 15th of M+2 | Matches when BI publishes and when the collector runs (the 15th) |
| 2026-10-08 | Phase 2 split: Claude writes the spec with pseudocode only (no function signatures, no stubs, no tests); you write all the code | Your decision |
| 2026-10-08 | Phase 2 may use statsmodels (STL), scipy (MAD) and pymannkendall (Mann-Kendall, Sen's slope) | Your decision |
| 2026-10-08 | Plain robust STL; Idul Fitri is measured in the remainder, not modelled | Your decision; Phase 3 adds holiday regressors where the diagnostic says so |
| 2026-10-08 | No MSTL | Every series has one observation per week or month, so one seasonal cycle |
| 2026-10-08 | STL seasonal window 13; strengths use a robust spread (1.4826 × MAD, squared) | Prototype: the variance version is dominated by a few COVID-era months (ATM/debit value 0.18 vs 0.73 robust) |
| 2026-10-08 | Week 53 is left out of the STL input and re-inserted with week 52's seasonal value | Rule C9; keeps exactly 52 periods per cycle |
| 2026-10-08 | Trend is profiled on the seasonally adjusted series with the Hamed-Rao test, full and rolling 3-year windows; the card reports `trend_now` (steady, slowing, accelerating, faded, reversed) | 53 of 54 series are "increasing" in nominal terms, so the verdict alone is uninformative |
| 2026-10-08 | Behaviour groups on three axes (trend, season, noise) plus a sticky flag, rule-based | The one-label draft put 50 of 54 in "trending" |
| 2026-10-08 | E-money value and instrument series are profiled after their breaks (Jan 2019, Nov 2017), kept in `breaks.csv` | TRANSFORMS step 6 |

## Known events (test set)

See [KNOWN_EVENTS.md](Scope/KNOWN_EVENTS.md) (draft, to confirm).

## Open questions

- [x] Include quarterly indicators? **No** (see decision log)
- [x] Include ibid auction data? **No** (see decision log)
- [x] Which food price level: national only, or by region too? **National only**, which is all PIHPS provides here
- [ ] Which output format do analysts prefer?
- [ ] Should the 3 food markets roll up into one view per group, or stay separate?
- [ ] How often should the report run: monthly after the 15th, or weekly with the food prices?
