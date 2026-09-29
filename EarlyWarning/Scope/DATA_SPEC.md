# Data Spec — standard input format

The format every indicator should be converted into in Phase 1, and the data quirks the loader needs to handle.
See [SCOPE.md](SCOPE.md) for which series are in scope.

## 1. Standard format (long format)

One row per indicator per period.

| Column | Type | Example | Notes |
|---|---|---|---|
| `series_id` | text | `pihps.traditional.01_beras` | Must match the id in [indicator_inventory.csv](indicator_inventory.csv) |
| `ref_date` | date (YYYY-MM-DD) | `2026-09-24` | Monthly: first day of the month. Weekly: see section 3. |
| `value` | number | `16350` | No thousands separators. Empty means missing. |
| `frequency` | text | `weekly` or `monthly` | |
| `unit` | text | `IDR per kg` | |

This matches the format the consumption CSVs already use (`series_id, geo_id, geo_name, ref_date, value, unit`).
We drop `geo_id` and `geo_name`, because every in-scope series is national, and add `frequency`.

**Rules:**

- One value per `series_id` + `ref_date`. No duplicates.
- A missing period is kept as a row with an empty `value`, not dropped, so gaps stay visible.
- Values are stored as reported. Transforms such as log or % change happen later, not in this file.

## 2. Consumption CSVs (`Dataset/Consumption/`)

Already close to the standard format.

- `ref_date` is already the first day of the month.
- `bi_card_transactions.csv`, `bi_emoney.csv` and `bi_payment_system.csv` have **no `frequency` column**. Add `monthly`.
- `bi_payment_system.csv` also holds 2 quarterly ratio series. They are out of scope, so filter them out.
- `bi_consumer_survey.csv`: keep only the 12 headline series listed in the inventory. Leave out the income-bracket splits (ids with `.rp1_2juta`, `.above_rp5juta` and similar) and the discontinued series.
- The spending share series have **no data for Apr–Jul 2020**. Keep these as missing rows.

## 3. PIHPS food prices (`Dataset/Food Prices/PIHPS/<Market>/`)

These need the most work.

**Layout:**

- There is one Excel file per market per year (2019–2026). Each file has one sheet.
- Row 1 is the header: `No`, `Komoditas (Rp)`, then one column per week, with dates written like `24/ 09/ 2026` (day/month/year, with spaces).
- The rows form a two-level list: 10 group rows, each followed by its sub-item rows. The source numbers the groups with letters, not digits. **The loader should map the groups to numbers 1–10** (see the table in [SCOPE.md](SCOPE.md)) and skip the sub-item rows.
- Prices are text with comma thousands separators (`15,750`). Strip the commas before converting to numbers.
- `-` means the market did not report. Treat it as missing.
- The data is national averages only, even though the file name says "Berdasarkan Daerah" (by region).
- The 2019–2025 files store text as shared strings. The 2026 file stores it inline. Most Excel readers handle both.

**Duplicates:** the Traditional Market 2023 file covers two years and repeats the 2024 weeks. Keep only one value per week.

**Week dates (important):**

- The PIHPS week starts on the weekday of 1 January, or the next Monday if 1 January is a weekend. So the weekday changes every year:

  | Year | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
  |---|---|---|---|---|---|---|---|---|
  | Weekday | Tue | Wed | Fri | Mon | Mon | Mon | Wed | Thu |

- At each year end, the last week of one year and the first week of the next can be only 1–3 days apart.
- **Proposed fix for Phase 1:** map every PIHPS column to an ISO week, using the Monday of that week as `ref_date`. If two columns fall in the same ISO week, keep the later one. Treat 53-week years explicitly. This gives regular weekly spacing, which the models need.

**Known missing weeks:**

| Date | Markets | Likely reason |
|---|---|---|
| 1 Jan 2020 | Traditional | New Year |
| 1 Jan 2021 | Traditional | New Year |
| 14 May 2021 | Traditional | Idul Fitri |
| 28 Feb 2022 | All 3 | Unknown |
| 2 May 2022 | Traditional | Idul Fitri |

**Units:** IDR per kg for all groups except cooking oil, which is IDR per litre. Confirm this against the PIHPS website.

## 4. Revisions

- BI revises past values, and the collectors re-read the last few periods on each run.
- `Dataset/Backup/<timestamp>/` keeps each file as it was before a run changed it. From these we may be able to rebuild **first-reported values**.
- Phase 1 should decide whether to keep a `first_reported_value` column. It makes backtests more honest.

## 5. Update timing

These are the times the collectors run (from `Collectors/README.md`):

| Data | Collector runs | Latest data in the repo (as of 29 Sep 2026) |
|---|---|---|
| PIHPS food prices | Every Saturday, 09:00 WIB | Week of 24 Sep 2026 |
| BI card, e-money, payment system | 15th of each month, 10:00 WIB | Jun 2026 (Jul 2026 for some) |
| BI consumer survey | 15th of each month, 10:00 WIB | Aug 2026 |

The BI payment data lags by about 2–3 months. Keep this in mind for how "early" the warnings on those series can be.
