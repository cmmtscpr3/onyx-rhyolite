# Phase 1 — Data Foundation Spec

What the Phase 1 code should do. You write the code; this doc sets the rules, the expected outputs and the
checks that prove it works.

Related files:

- [DATA_QUALITY.md](DATA_QUALITY.md): data problems found so far, and what to do about each
- [holiday_calendar.csv](holiday_calendar.csv): holiday and event table
- [../Scope/indicator_inventory.csv](../Scope/indicator_inventory.csv): the 66 series, now with `transform` and `seasonal_period`
- [../Scope/DATA_SPEC.md](../Scope/DATA_SPEC.md): source file layouts

---

## 1. What Phase 1 produces

Two tables. The code should rebuild both from `Dataset/` each run, so they never need editing by hand.

### 1a. `observations`: the clean data (one row per series per period)

| Column | Type | Notes |
|---|---|---|
| `series_id` | text | From the inventory |
| `ref_date` | date | Monthly: 1st of the month. Weekly: Monday of the week (see section 4). |
| `value` | number or empty | The cleaned value. Empty if missing or masked. |
| `raw_value` | number or empty | The value as read from the source, before masking |
| `frequency` | text | `weekly` or `monthly` |
| `unit` | text | From the inventory |
| `source_date` | date | The original date in the source. Differs from `ref_date` for PIHPS. |
| `quality_flag` | text | `ok`, `missing`, `masked_error`, `holiday_artifact`, `provisional` or `review` (see section 5) |
| `is_provisional` | yes/no | `yes` for the latest period while the source may still revise it |

### 1b. `quality_report`: one row per series

| Column | Notes |
|---|---|
| `series_id` | |
| `start`, `end` | First and last `ref_date` with a value |
| `n_expected` | Number of periods between start and end |
| `n_values` | Periods with a value |
| `n_missing` | Periods with no value, including masked ones |
| `pct_missing` | `n_missing / n_expected` |
| `n_flagged` | Count per flag type |
| `longest_gap` | Longest run of missing periods |
| `last_update_lag` | Periods between `end` and the expected latest period (see section 7) |
| `confidence` | `high`, `medium` or `low` (rule in section 6) |
| `notes` | Anything unusual |

**Storage:** CSV is fine, and so is Parquet if you prefer. Put the outputs outside `Dataset/`, so they never mix with the collected data.

## 2. Loading the consumption CSVs

Sources: `bi_consumer_survey.csv`, `bi_card_transactions.csv`, `bi_emoney.csv` and `bi_payment_system.csv`.

1. Read each file and keep only the rows whose `series_id` is in the inventory.
2. Parse `ref_date` as a date. Check it is the 1st of a month; otherwise raise an error.
3. Parse `value` as a number. If that fails, stop with an error naming the row.
4. Take `frequency` from the inventory, not the file (3 of the 4 files have no `frequency` column).
5. Check the file's `unit` matches the inventory's `unit`. A mismatch means the source changed, so stop.
6. Add a row for every missing month between start and end, with an empty value and `quality_flag = missing`.

## 3. Loading PIHPS food prices

Source: `Dataset/Food Prices/PIHPS/<Market>/Tabel Harga Berdasarkan Daerah <year>.xlsx`, for 3 markets and years 2019–2026.

1. Read sheet 1 of each file. Row 1 is the header.
2. **Header:** columns 3 onwards are week dates in the form `dd/ mm/ yyyy` (with spaces). Remove the spaces, then parse as day/month/year.
3. **Group rows:** column 1 holds the row number. Group rows use letters (the source's own style); sub-item rows use digits. Keep only the group rows. There are 10 per file, always in the same order.
4. **Map the groups to numbers 1–10** by their order, and check the name in column 2 matches the table below. If a name doesn't match, stop, because the source layout changed.

   | No | Name in file | series_id part |
   |---|---|---|
   | 1 | Beras | `01_beras` |
   | 2 | Daging Ayam | `02_daging_ayam` |
   | 3 | Daging Sapi | `03_daging_sapi` |
   | 4 | Telur Ayam | `04_telur_ayam` |
   | 5 | Bawang Merah | `05_bawang_merah` |
   | 6 | Bawang Putih | `06_bawang_putih` |
   | 7 | Cabai Merah | `07_cabai_merah` |
   | 8 | Cabai Rawit | `08_cabai_rawit` |
   | 9 | Minyak Goreng | `09_minyak_goreng` |
   | 10 | Gula Pasir | `10_gula_pasir` |

5. **Values:** strip spaces and remove the thousands commas (`15,750` → `15750`). A value of `-` or an empty cell means missing.
6. **Series id:** `pihps.<market>.<No>_<name>`, where market is `traditional`, `modern` or `wholesale`.
7. **Duplicate dates across files:** the Traditional Market 2023 file repeats the 2024 weeks. Today, all 530 repeated cells agree. Rule: if the same date appears in two files, the values must match. If they don't, keep the value from the file whose year matches the date, and log a warning.
8. Map the dates to weeks (section 4).

## 4. Week rule for PIHPS

**Problem:** PIHPS weeks start on the weekday of 1 January, which changes every year (Tue, Wed, Fri, Mon, Mon, Mon, Wed, Thu for 2019–2026). At year end, dates can be only 1–3 days apart.

**Rule:** map every PIHPS date to its **ISO week** (Monday–Sunday), and use the **Monday** as `ref_date`. Keep the original date in `source_date`.

- **If two dates land in the same ISO week**, keep the **later date that has a value**. If both are missing, the week is missing.
- **Tested on the real data** (Modern Market, 2019–2026): 408 dates become 404 ISO weeks, with no empty weeks and 4 clashes, all at year end:

  | ISO week (Monday) | Dates that clash | Keep |
  |---|---|---|
  | 30 Dec 2019 | 31 Dec 2019, 1 Jan 2020 | 1 Jan 2020, or 31 Dec 2019 where 1 Jan is missing (Traditional) |
  | 28 Dec 2020 | 30 Dec 2020, 1 Jan 2021 | Same rule |
  | 30 Dec 2024 | 30 Dec 2024, 1 Jan 2025 | 1 Jan 2025 |
  | 29 Dec 2025 | 31 Dec 2025, 1 Jan 2026 | 1 Jan 2026 |

- **Check after mapping:** consecutive `ref_date` values must be exactly 7 days apart, with missing weeks filled with empty rows. Stop if not.
- **53-week years:** ISO years 2020 and 2026 have a week 53. Section 8 explains how Phase 2 should handle them.

## 5. Quality flags and masking

Each observation gets exactly one `quality_flag`:

| Flag | Meaning | `value` column | Set by |
|---|---|---|---|
| `ok` | Normal | Same as `raw_value` | Default |
| `missing` | No value in the source | Empty | Loader |
| `masked_error` | A confirmed data error | Empty | `data_issues.csv` (see below) |
| `holiday_artifact` | A real reading, but distorted by a holiday (few markets reporting) | Empty | `data_issues.csv` |
| `review` | Looks odd but is not yet confirmed as an error | Same as `raw_value` | `data_issues.csv` |
| `provisional` | Latest period, which may still be revised | Same as `raw_value` | Loader (section 7) |

**`data_issues.csv`** is a small hand-kept list with the columns `series_id, ref_date, action, reason`, where `action` is `mask`, `holiday_artifact` or `review`:

- Keep it next to the code and check it into git, so every masking decision is written down.
- Start it from the table in [DATA_QUALITY.md, section 3](DATA_QUALITY.md#3-suspected-data-errors), once you've confirmed the rows.
- `series_id` may use `*` for "all series in this group", for example `pihps.traditional.*`.

**Why mask rather than delete?** Later models need to know that a period exists and has no usable value.

## 6. Confidence tag per series

| Tag | Rule |
|---|---|
| `high` | At least 3 full seasonal cycles (36 months or 156 weeks), `pct_missing` under 5%, and no gap longer than 3 periods |
| `medium` | At least 2 full cycles (24 months or 104 weeks), and `pct_missing` under 15% |
| `low` | Anything else |

Today every in-scope series should come out `high`, except possibly the 3 spending share series (their Apr–Jul 2020 gap is 4 months long, which makes them `medium`).

## 7. Revisions and the provisional flag

**What we saw (see DATA_QUALITY.md, section 4):**

- PIHPS revises the **latest 1–2 weeks** on the next run. Up to 29 cells changed per run, usually by 0.1–0.5%, but up to 2.5%.
- BI revised `currency_in_circulation` and `narrow_money` for the last 2 months (the latest by -0.58%).

**Rules:**

- Set `is_provisional = yes` and `quality_flag = provisional` for:
  - PIHPS: the latest **2** weeks
  - BI monthly series: the latest **2** months
- Phase 3 and later: an alert on a provisional value should say so ("based on provisional data").
- **First-reported values:** don't rebuild them in Phase 1. The backups only go back to Sep 2026, which is too short to be useful. Instead, from now on, save a copy of `observations` after each run (for example, `observations_<run date>.csv`). This builds a vintage history for honest backtests later.

**Expected latest period** (for `last_update_lag`):

- PIHPS: the week of the most recent Saturday run.
- BI payment series: about 2 months before today.
- Consumer survey: about 1 month before today.

## 8. Transforms (applied after loading, not stored in `observations`)

> The full approach (7 steps, with evidence) is in [TRANSFORMS.md](TRANSFORMS.md). The detailed validation checks and calendar rules are in [VALIDATION_CALENDAR.md](VALIDATION_CALENDAR.md). This section is the short version.

Every series has a `transform` in the inventory:

| Transform | Used for | Why |
|---|---|---|
| `log` | Prices, IDR amounts, transaction counts and volumes, instruments and cards in circulation | These grow in percentages, so log makes changes comparable over time |
| `level` | Survey indices (around 100) and percentage shares | Already on a stable scale. Log adds nothing. |

**`seasonal_period`** is 12 for monthly series and 52 for weekly series.

- In ISO years with a week 53, Phase 2 can either merge week 53 into week 52 (the simplest option) or use STL with period 52.18. **Suggested:** merge, and note it.

**Watch out for "sticky" prices:** the traditional and wholesale rice prices often don't change from one week to the next. The robust spread (MAD) of their weekly changes is close to **zero**, so any tiny change looks extreme. Phase 2 and later checks need a **floor on the spread**. For example, use the larger of the MAD and 0.5% of the level, or compare against a 4-week change instead.

## 9. Holiday table

[holiday_calendar.csv](holiday_calendar.csv) columns:

| Column | Notes |
|---|---|
| `event` | For example, `idul_fitri` |
| `event_type` | `religious`, `national`, `shock` or `policy` |
| `date` | Main date |
| `end_date` | For events that last more than one day (for example, shocks) |
| `window_before_days`, `window_after_days` | Suggested effect window around the date |
| `affects` | Themes likely to react |
| `verified` | `no` until checked against the official government holiday decree (SKB) |
| `notes` | |

- **Covers:** 2009–2027 for Idul Fitri, Ramadan start, Idul Adha and Lunar New Year. Christmas and New Year are listed for each year too. The shocks are COVID and the Delta wave.
- **Loader use:** turn the table into per-period features, for example "days of Ramadan in this month" or "Idul Fitri falls in this ISO week or the next 2". Phase 2–3 models use these.
- **To do:** check the dates against the official SKB lists before relying on them. The 2027 dates are estimates.

## 10. Acceptance checks

The Phase 1 code is done when all of these pass:

| # | Check | Expected today (data as of 30 Sep 2026) |
|---|---|---|
| 1 | Series in `observations` | 66 (30 weekly, 36 monthly) |
| 2 | Duplicate `series_id` + `ref_date` | 0 |
| 3 | Weekly spacing | Always 7 days |
| 4 | Monthly spacing | Always 1 month |
| 5 | PIHPS weeks per series | 404 (Jan 2019 – Sep 2026) |
| 6 | PIHPS missing weeks, before masking | Traditional 5, Modern 1, Wholesale 1 |
| 7 | Spending share series missing months | 4 each (Apr–Jul 2020) |
| 8 | Unit per series matches the inventory | All 66 |
| 9 | Values ≤ 0 | 0 |
| 10 | Every `data_issues.csv` row matches a real observation | All |
| 11 | Latest `ref_date`: PIHPS | Week of 21 Sep 2026 (source date 24 Sep 2026) |
| 12 | Latest `ref_date`: card and e-money | Jul 2026 |
| 13 | Latest `ref_date`: payment system | Aug 2026 for currency in circulation and RTGS value/volume; Jul 2026 for the other 3 |
| 14 | Latest `ref_date`: consumer survey | Aug 2026 |
| 15 | Re-running on the same inputs gives identical outputs | Yes |

Tip: turn these into automated tests. The existing `Collectors/tests/` show the pattern already used in this repo.
