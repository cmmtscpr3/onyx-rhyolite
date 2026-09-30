# Validation Checks and Calendar Rules

Detailed rules for two Phase 1 items. They extend [PHASE1_SPEC.md](PHASE1_SPEC.md), sections 2–5.
You write the code; this doc says exactly what it should check and how dates work.

---

## Part A — Validation checks

**When they run:** after loading, before anything else uses the data.

**Severity levels:**

| Level | What the code does |
|---|---|
| **STOP** | Raise an error and write nothing. The data or the source layout is broken. |
| **WARN** | Keep going, but log it and add a note to `quality_report`. |
| **INFO** | Record it in `quality_report` only. |

### A1. Missing dates

| ID | Check | Applies to | Severity | Action |
|---|---|---|---|---|
| M1 | Every period between a series' first and last date exists | All | INFO | Add an empty row with `quality_flag = missing` (never drop the period) |
| M2 | Missing run longer than 3 periods | All | WARN | Note it in `quality_report` (today: only the spending shares, Apr–Jul 2020) |
| M3 | More than 5% of periods missing | All | WARN | Lowers `confidence` (see spec section 6) |
| M4 | The latest period is older than expected (stale feed) | All | WARN | Expected latest: PIHPS, the most recent Saturday run week; survey, 1 month back; BI payment series, 2 months back |
| M5 | Every series in the inventory appears in the loaded data | All | STOP | A missing series means a source changed or a filter is wrong |
| M6 | Every loaded series is in the inventory | All | WARN | New series in a source. Ignore them, but log. |

### A2. Duplicates

| ID | Check | Applies to | Severity | Action |
|---|---|---|---|---|
| D1 | Same `series_id` + `source_date` appears twice with the **same** value | All | INFO | Keep one (today: 530 cells from the Traditional Market 2023 file) |
| D2 | Same `series_id` + `source_date` appears twice with **different** values | All | WARN | Keep the value from the file whose year matches the date; log both values |
| D3 | Two source dates map to the same ISO week | PIHPS | INFO | Keep the later date that has a value (calendar rule C4); today there are 4 cases, all at year end |
| D4 | No duplicate `series_id` + `ref_date` remains in `observations` | All | STOP | Final guard |

### A3. Zeros and negatives

| ID | Check | Applies to | Severity | Action |
|---|---|---|---|---|
| Z1 | Value ≤ 0 in a `log` series | Series with `transform = log` | STOP | Log of zero or a negative is undefined. Today: none. |
| Z2 | Value ≤ 0 in a `level` series | Indices and shares | WARN | Possible but suspicious (indices sit around 50–150, shares between 0 and 100) |
| Z3 | Value out of its natural range | Shares | WARN | Shares must be 0–100 |
| Z4 | Value out of its natural range | Survey indices | WARN | Must be 0–200 (the BI indices are built on a 0–200 scale) |
| Z5 | Value is not a number after cleaning | All | STOP | For example, a text note left in a cell |

### A4. Unit changes

Sources rarely announce unit changes, so check both the label and the size of the numbers.

| ID | Check | Applies to | Severity | Action |
|---|---|---|---|---|
| U1 | The `unit` label in the source differs from the inventory | Consumption CSVs | STOP | The source changed its unit. Update the inventory on purpose, then re-run. |
| U2 | The PIHPS header still reads `Komoditas (Rp)` | PIHPS | STOP | Prices are in rupiah |
| U3 | **Scale jump:** a single-period change of about ×10, ×100, ×1000 (or ÷) that **stays** for 3+ periods | Series with `transform = log` | WARN | A likely unit switch (for example, million → billion). The rule: \|Δlog\| is within 0.3 of log(10), log(100) or log(1000), and the level doesn't come back. |
| U4 | **One-off spike:** a big move that comes straight back the next period | All | WARN | A likely typo or data error. List it for `data_issues.csv`, but don't mask it automatically. The rule: robust z-score of Δ above 8, **and** the next Δ has the opposite sign with a similar size. The robust z uses a spread floor (see [TRANSFORMS.md](TRANSFORMS.md), step 5), so sticky prices don't trigger it. |

Today U3 finds nothing. U4 finds the 5 cases listed in [DATA_QUALITY.md](DATA_QUALITY.md), section 3a.

### A5. Structure checks (source layout)

| ID | Check | Severity |
|---|---|---|
| S1 | PIHPS has exactly 10 group rows, in the order and with the names in spec section 3 | STOP |
| S2 | Every PIHPS header date parses | STOP |
| S3 | Monthly `ref_date` is always the 1st of the month | STOP |

### Output of the checks

A `validation_log` table (or CSV) with one row per finding:

`run_time, check_id, severity, series_id, ref_date, message`

The quality report counts WARN findings per series.

---

## Part B — Calendar rules

### B1. Monthly series

| Rule | Detail |
|---|---|
| C1. Date label | `ref_date` = the 1st of the month (already true in the source) |
| C2. Days in month | Store `days_in_month` (28–31). Flow series use it in [TRANSFORMS.md](TRANSFORMS.md), step 1. |

### B2. Weekly series (PIHPS)

| Rule | Detail |
|---|---|
| C3. Week system | **ISO weeks: Monday to Sunday.** Each week gets an ISO year and week number (for example, `2026-W39`). |
| C4. Date label (week start) | `ref_date` = the **Monday** of the ISO week. The original PIHPS date goes in `source_date`. If two PIHPS dates fall in one ISO week, keep the later one that has a value. |
| C5. Week-ending day | Also store `week_ending` = the **Sunday** of the same week (`ref_date` + 6 days). Use it for display ("week ending 27 Sep 2026"), not as a key. |
| C6. Why Monday and not the PIHPS weekday | The PIHPS weekday changes every year (Tue, Wed, Fri, Mon, Mon, Mon, Wed, Thu for 2019–2026). ISO weeks give regular 7-day steps. Tested: 404 weeks, no gaps. |

**Why keep both dates?** `ref_date` (Monday) is the key that joins tables. `week_ending` (Sunday) is the friendlier label, because a price collected during the week is "known" by its end.

### B3. 53-week years

- ISO years usually have 52 weeks, but some have 53: of the years in range, **2020 and 2026**. The next one is 2032.
- Week 53 exists only in those years.

| Use | Rule |
|---|---|
| C7. Storing data | Keep week 53 as a normal row. Never drop it. |
| C8. Year-on-year change | Compare with the value **52 weeks earlier** (364 days back, always a Monday). Simple and always defined. After a 53-week year, the "same week" drifts by one week, which is fine for weekly food prices. |
| C9. Seasonal models (Phase 2) | Use season length 52. For the seasonal pattern, treat week 53 as week 52 (they share one seasonal slot). |
| C10. Same-week-of-year comparisons (Q2 percentile) | Compare by ISO week number. Week 53 is compared with the week 52 values of other years. |

### B4. Weekly → monthly (for cross-frequency views)

| Rule | Detail |
|---|---|
| C11. Which month a week belongs to | **The month that contains the week's Thursday.** This is the ISO rule. Each week belongs to exactly one month, and each month has 4 or 5 weeks. |
| C12. Monthly value | The **mean** of that month's weekly prices (ignoring missing weeks). Mark it missing if fewer than 3 weeks have values. |

### B5. Holidays and events on the calendar

From [holiday_calendar.csv](holiday_calendar.csv), build **features per period**. You don't need to adjust the data itself:

| Feature | Weekly (per ISO week) | Monthly |
|---|---|---|
| `fitri_pre` | 1 if Idul Fitri is 1–4 weeks after this week | Number of days in the month that fall in the 28 days before Idul Fitri |
| `fitri_week` | 1 if Idul Fitri falls in this week | 1 if Idul Fitri falls in this month |
| `fitri_post` | 1 if Idul Fitri was 1–2 weeks before this week | Days in the month within 14 days after Idul Fitri |
| `ramadan_days` | Days of Ramadan in this week (0–7) | Days of Ramadan in this month (0–30) |
| `adha_pre` | 1 if Idul Adha is 1–2 weeks after this week | Days in the month within 14 days before Idul Adha |
| `lny`, `christmas`, `new_year` | 1 if the holiday falls in this week | 1 if it falls in this month |
| `covid_shock` | 1 during the shock windows | 1 during the shock windows |

**Why this matters:** Idul Fitri moves about 11 days earlier each year, so a fixed "month of year" seasonal pattern can't capture it. The first test on traditional market prices shows the effect is real:

| Group | Average weekly change in the 4 weeks before Idul Fitri | Other weeks |
|---|---|---|
| 2 Chicken | +0.77% | -0.10% |
| 3 Beef | +0.73% | +0.03% |
| 5 Shallot | +1.60% | -0.26% |
