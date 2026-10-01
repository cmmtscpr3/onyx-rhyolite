# Early Warning System

The plan is in [WORKPLAN.md](WORKPLAN.md), progress in [CHECKLIST.md](CHECKLIST.md), the scope in [Scope/](Scope/)
and the Phase 1 design in [DataFoundation/](DataFoundation/).

This folder also holds the **Phase 1 code** (`ews/`), which turns the collected data into clean, validated,
log-transformed datasets in `data/`.

## Scope of the code

**54 series:**

| Source | Series | Frequency |
|---|---|---|
| PIHPS food prices: 10 groups (numbered 1–10) × traditional, modern, wholesale | 30 | weekly |
| BI SPIP: `bi_card_transactions` (6), `bi_emoney` (12), `bi_payment_system` (6) | 24 | monthly |

`Dataset/` is **only read**. Nothing in this code writes there, and a test checks that.

## Install, run, test

```bash
pip install -r EarlyWarning/requirements.txt   # pandas, numpy, openpyxl, pytest

cd EarlyWarning
python -m ews.run                       # writes to EarlyWarning/data/
python -m ews.run --today 2026-09-30    # check freshness as of another date
python -m ews.run --out /tmp/ews        # write somewhere else
pytest                                  # 37 tests, about 25 seconds, offline against the real Dataset/
```

The run takes about 5 seconds. It exits with code 1 if any check returns STOP.

## The pipeline

```
 Dataset/ ──► inventory.py ──► load.py ──► calendar.py ──► validate.py ──► transform.py ──► data/
              (54 series)      01_loaded   02_calendar     03_validated    04_transformed
```

| Module | What it does | Output |
|---|---|---|
| `inventory.py` | Picks the 54 series and their settings from `Scope/indicator_inventory.csv` | (in memory) |
| `load.py` | Reads the files exactly as they are: PIHPS group rows (reusing the collectors' workbook reader) and the 3 SPIP CSVs | `data/steps/01_loaded.csv` |
| `validate.py`, pass 1 | Checks file structure, units, numbers and coverage, and resolves duplicate dates | (findings) |
| `calendar.py` | Fixes the dates: weekly → Monday of the ISO week, plus the Sunday week-ending date; fills gaps with empty rows; adds days in month | `data/steps/02_calendar.csv` |
| `validate.py`, pass 2 | Checks missing periods, zeros and negatives, unit switches and one-off spikes; applies `data_issues.csv`; marks provisional periods | `data/steps/03_validated.csv` |
| `transform.py` | Per-day adjustment for flows, then log for every series | `data/steps/04_transformed.csv` = `data/observations.csv` |

## Outputs (`data/`)

| File | One row per | Use |
|---|---|---|
| `observations.csv` | series × period | **The dataset for the early warning system** |
| `quality_report.csv` | series | Health check: coverage, gaps, flags, confidence |
| `validation_log.txt` | finding | **Readable log to review after each run** |
| `validation_log.csv` | finding | The same findings, for filtering in Excel |
| `steps/*.csv` | — | Each step's output, to see exactly what changed |

**`observations.csv` columns:**

| Column | Meaning |
|---|---|
| `series_id`, `frequency`, `unit` | From the inventory |
| `ref_date` | The period: Monday of the ISO week (weekly) or the 1st of the month (monthly) |
| `week_ending` | Sunday of that week (weekly only) |
| `iso_year`, `iso_week` | ISO week number (weekly only). 2020 and 2026 have a week 53. |
| `days_in_month` | 28–31 (monthly only) |
| `source_date`, `source_file` | Where the value came from. For PIHPS, `source_date` is the original column date. |
| `raw_value` | The value as read |
| `value` | The cleaned value (blank if missing or masked) |
| `quality_flag` | `ok`, `missing`, `review`, `masked_error` or `provisional` |
| `is_provisional` | `True` for the latest 2 periods, which the sources often revise |
| `x_cal` | `value ÷ days_in_month` for flows; `value` for stocks and prices |
| `x` | `ln(x_cal)`, the transformed value |

## Why these two transformations

| Transformation | Applies to | Why |
|---|---|---|
| **Per day** (`value ÷ days in month`) | The 12 flow series (card, e-money and RTGS transaction value and volume) | Flows are monthly totals. A 31-day month carries about 10% more activity than February for no economic reason. Monthly changes in card flows move with month length (correlation 0.6–0.7); stocks don't. |
| **Log** | All 54 series | The series grow in percentage terms. After log, a change of 0.05 means about 5% in any series and any year, so prices, IDR amounts and counts share one scale. |

## Validation checks

**Severity:** STOP means no data files are written; WARN means logged for review; INFO means recorded only.

| Check | Question | Severity |
|---|---|---|
| M1 | Is every week or month present? Gaps become empty rows flagged `missing`. | INFO |
| M2 | Is any gap longer than 3 periods? | WARN |
| M3 | Is more than 5% of the series missing? | WARN |
| M4 | Is the latest value as recent as expected? (PIHPS: last Saturday's run; SPIP: month M arrives around the 15th of M+2.) | WARN |
| M5 | Is every inventory series in the files? | STOP |
| M6 | Are there series in the files we don't track? The 2 quarterly ratios are known and listed as INFO. | WARN |
| D1 | Is a date repeated with the same value? (The 2023 traditional file repeats 2024.) | INFO |
| D2 | Is a date repeated with different values? | WARN |
| D3 | Do two PIHPS dates fall in one ISO week? The later date with a price is kept. | INFO |
| D4 | Is any duplicate left after alignment? | STOP |
| Z1 | Is any value zero or negative? (Log needs positive values.) | STOP |
| Z5 | Is any value not a number? | STOP |
| U1 | Does the SPIP unit label match the inventory? | STOP |
| U2 | Is the PIHPS header still "Komoditas (Rp)"? | STOP |
| U3 | Is there a step of about ×10, ×100 or ×1000 that stays (a hidden unit change)? | WARN |
| U4 | Is there a big move that comes straight back (a likely typo)? | WARN |
| S1 | Are the 10 PIHPS groups all there, with the expected names? | STOP |
| S2 | Is every PIHPS week header a date? | STOP |
| S3 | Is every monthly date the 1st of the month? | STOP |
| I1 | Does every `data_issues.csv` row match an observation? | WARN |

## `data_issues.csv`

Your list of suspected or confirmed data errors: `series_id, ref_date, action, reason`.

- `action = review` flags the value but keeps it. `action = mask` blanks `value` (`raw_value` keeps the original).
- `series_id` may end in `*` for a group (for example, `pihps.traditional.*`).
- Weekly dates snap to the Monday of their week.

It ships with the 5 suspects from [DataFoundation/DATA_QUALITY.md](DataFoundation/DATA_QUALITY.md) as `review`. Change a row to `mask` once you've confirmed it's an error. The U4 lines in `validation_log.txt` are candidates to add.
