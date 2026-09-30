# Data Quality Report (first pass)

A manual check of the 66 in-scope series, with data as of **30 Sep 2026**.
The Phase 1 code should produce this report automatically in future (see [PHASE1_SPEC.md](PHASE1_SPEC.md), section 1b).

## 1. Summary

| Check | Result |
|---|---|
| Series checked | 66 (30 weekly, 36 monthly) |
| Duplicate readings (same series and date) | None in the consumption CSVs. PIHPS: 530 repeated cells in the Traditional Market 2023 file, all identical to the 2024 file. |
| Values that are not numbers | None |
| Zero or negative values | None |
| Unit changes within a series | None |
| Missing periods | PIHPS: 5 weeks in traditional markets, 1 week in modern and wholesale. Survey spending shares: Apr–Jul 2020. |
| Suspected data errors | 5 likely errors, plus 4 patterns to review (section 3) |
| Revisions | PIHPS revises the latest 1–2 weeks; BI revised 2 money series (section 4) |

**Overall:** the data is in good shape. The main work for Phase 1 is:

1. Map the PIHPS weeks to ISO weeks.
2. Mask a handful of clear errors.
3. Flag the latest periods as provisional.

## 2. Missing data

| Series | Missing | Likely reason |
|---|---|---|
| All 10 traditional-market food groups | 1 Jan 2020, 1 Jan 2021 | New Year |
| All 10 traditional-market food groups | 14 May 2021, 2 May 2022 | Idul Fitri |
| All 30 food series | 28 Feb 2022 | Unknown. Check the PIHPS website. |
| Survey spending shares (consumption, saving, loan instalments) | Apr–Jul 2020 (4 months) | Survey disruption during COVID |

All missing periods are short (1 week or 4 months), so Phase 2 can fill them or skip them. No imputation happens in Phase 1.

## 3. Suspected data errors

**How these were found:** for each series, the period-to-period change (on the log scale) was compared with its normal spread (a robust z-score using the median and MAD). Moves more than 8× the normal spread were listed. Most of them are **real events** (section 3c). The ones below look like **errors**, usually because the value jumps and then comes straight back.

### 3a. Likely errors → propose `mask`

| # | Series | Date(s) | What happens | Proposed action |
|---|---|---|---|---|
| 1 | `bi_card_transactions.atm_debit.cards` | Nov 2011 | Falls about 85% for one month, then fully recovers in Dec 2011 | mask |
| 2 | `bi_emoney.volume` and `bi_emoney.volume_topup` | Sep 2013 | Jumps about 30× for one month, then back in Oct 2013 | mask |
| 3 | `pihps.modern.10_gula_pasir` (sugar) | Week of 3 Jun 2024 | Almost doubles for one week, then back | mask |
| 4 | `pihps.modern.01_beras` (rice) | Weeks of 5 Feb and 12 Feb 2025 | Rises about 18%, then falls back | mask (check the PIHPS website first) |
| 5 | `pihps.traditional.*` (many groups) | Week of 5 Feb 2019 (Lunar New Year) | Most groups dip for one week, then recover | `holiday_artifact` |

### 3b. Patterns to review → propose `review`

| # | Series | Date(s) | What happens | Question |
|---|---|---|---|---|
| 6 | E-money instruments (total, chip, server) and `bi_payment_system.emoney_instruments_outstanding` | Dec 2013 – Mar 2014, Dec 2015, Nov – Dec 2017 | Big up and down jumps, repeated across related series | Changes in how issuers report? Nov 2017 matches the cashless toll road push, so it may be real. |
| 7 | `bi_emoney.value`, `bi_emoney.value_topup` | Jan 2019 | Value jumps about 4.5× and stays higher. Top-ups jump about 11×, then swing again in May–Jun 2019. | A lasting level shift. Probably new issuers counted. Treat as a **structural break**, not an error. |
| 8 | `bi_emoney.float_funds_bank` | Dec 2021 – Apr 2022 | Large swings up and down | Reporting change or a real flow? |
| 9 | `bi_emoney.float_funds_nonbank` | May 2015 – Aug 2016 | Large swings | Early days of non-bank e-money, when the series was small. May be real but noisy. |

### 3c. Big moves that look real (keep, and use as test events)

| Series | Date(s) | Event |
|---|---|---|
| All consumer sentiment indices | Apr 2020 | COVID and large-scale social restrictions (PSBB) |
| All consumer sentiment indices | Jul 2021 | Delta wave (PPKM Darurat) |
| Cooking oil (group 9), modern and wholesale | Late Jan 2022 (down), late Mar 2022 (up) | Price cap introduced, then removed |
| Garlic (group 6), all markets | Mar – May 2019, Feb 2020 | Import disruptions |
| `bi_card_transactions.credit.cards` | Jun 2026 | Down 3.8% in a month. Recent, so worth watching. |

These match [KNOWN_EVENTS.md](../Scope/KNOWN_EVENTS.md) well. That's a good sign for Phase 4.

### 3d. Sticky prices (a method issue, not a data error)

- The traditional and wholesale **rice** prices often stay the same for weeks, so their typical weekly change is almost zero.
- As a result, the robust z-score check flagged 165–184 "extreme" moves that are really small (0.4–2%).
- **Action for Phase 2+:** use a floor on the spread, as described in [PHASE1_SPEC.md, section 8](PHASE1_SPEC.md#8-transforms-applied-after-loading-not-stored-in-observations). Don't mask these values.

## 4. Revisions

Compared the backup snapshots in `Dataset/Backup/` with the current files.

**PIHPS 2026 workbooks:**

| Market | Run of 19 Sep → now | Run of 26 Sep → now |
|---|---|---|
| Traditional | 29 cells changed | 7 cells changed |
| Modern | 19 cells changed | 22 cells changed |
| Wholesale | 17 cells changed | 2 cells changed |

- The changes are always in the **latest 1–2 weeks**.
- They are mostly 0.1–0.5%, with the largest about 2.5% (modern premium rice, 17,750 → 18,200).

**BI monthly (run of 29 Sep → now):**

| Series | Month | Change |
|---|---|---|
| `currency_in_circulation` | Jun 2026 | -0.001% |
| `currency_in_circulation` | Jul 2026 | -0.58% |
| `narrow_money` | Jun 2026 | -0.0001% |

Card and e-money data had no revisions, only a new month (Jul 2026).

**Conclusion:** treat the latest 2 periods as **provisional** (see [PHASE1_SPEC.md, section 7](PHASE1_SPEC.md#7-revisions-and-the-provisional-flag)).

## 5. Freshness (latest data in the repo)

| Source | Latest period | Lag vs today (30 Sep 2026) |
|---|---|---|
| PIHPS food prices | Week of 24 Sep 2026 | Under 1 week |
| Consumer survey | Aug 2026 | 1 month |
| Currency in circulation, RTGS | Aug 2026 | 1 month |
| Card, e-money, demand deposits, narrow money, e-money outstanding | Jul 2026 | 2 months |

## 6. Next steps

- [ ] Confirm or reject each row in section 3, then create `data_issues.csv` from it (format in [PHASE1_SPEC.md, section 5](PHASE1_SPEC.md#5-quality-flags-and-masking)).
- [ ] Check 28 Feb 2022, and the modern-market rice readings of Feb 2025, on the PIHPS website.
- [ ] Check the holiday dates against the official SKB lists.
