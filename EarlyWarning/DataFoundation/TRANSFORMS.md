# Transformation Approach

How to turn the clean data (`observations` from Phase 1) into the inputs the early warning checks use.
Each step says **what** to do, **why**, and the **evidence** from our data.
Per-series settings are in [../Scope/indicator_inventory.csv](../Scope/indicator_inventory.csv) (new columns listed in section 3).

---

## 1. Overview: 7 steps, in order

```
 clean value (Phase 1)
   │
   ├─ 1. Calendar adjust ── flows: value per day
   ├─ 2. Scale ──────────── log  or  level
   ├─ 3. Change measures ── short, medium, long (YoY), gap to recent baseline
   ├─ 4. Seasonal split ─── STL (+ holiday features) → trend, seasonal, remainder     [Phase 2]
   ├─ 5. Standardise ────── robust z-score with a spread floor                       [Phase 3–4]
   ├─ 6. Breaks ─────────── known level shifts handled explicitly
   └─ 7. Align frequency ── weekly → monthly, for cross-indicator views              [Phase 7]
```

Phase 1 builds steps 1–3 and 6. Steps 4, 5 and 7 are specified here so the choices fit together, but they belong to later phases.

**Rule:** never overwrite `value`. Each step adds new columns (or a new table), so any result can be traced back to the raw number.

## 2. The steps

### Step 1 — Calendar adjustment (flows only)

**What:** for **flow** series (totals over the month, such as transaction value or volume), divide by the days in the month:

`value_per_day = value / days_in_month`

Leave stocks (levels at month end), prices, indices and shares unchanged.

**Why:** a 31-day month has about 10% more transactions than February for no economic reason. Without this step, every February looks like a drop.

**Evidence:** the correlation between the monthly change and the change in days-in-month:

| Series type | Correlation | Needs adjustment? |
|---|---|---|
| Card transaction value and volume | 0.60 – 0.72 | **Yes** |
| RTGS value and volume | 0.34 – 0.43 | **Yes** |
| E-money purchase value and volume | 0.29 – 0.38 | **Yes** |
| Stocks (cards, float, M1, currency) | about 0 (−0.13 to 0.16) | No |
| Survey indices and shares | about 0 | No |

**Later upgrade (optional):** use **working days** (weekdays minus public holidays and collective leave days) instead of calendar days. This needs a full public holiday list, which our holiday table doesn't have yet.

### Step 2 — Scale: log or level

**What:**

- **`log`** for everything measured in money, counts or prices. After this, a change of 0.05 ≈ 5%.
- **`level`** (no change) for survey indices and percentage shares.

**Why:** money and count series grow in percentage terms, so a 100-unit move means much more in 2012 than in 2026. Log puts all periods on the same footing. Indices and shares already sit on a fixed scale.

**Evidence:** the correlation between the size of a series and the size of its changes. A good scale shows **no** link.

| Series type | Raw level | After log | Pick |
|---|---|---|---|
| E-money value and volume | +0.41 to +0.69 | −0.28 to +0.09 | **log** |
| Card value and volume | +0.28 to +0.42 | −0.10 to +0.01 | **log** |
| Money and payment stocks | +0.29 to +0.44 | −0.23 to +0.07 | **log** |
| Volatile food prices (shallot, garlic, chili) | +0.26 to +0.36 | −0.01 to +0.19 | **log** |
| Stable food prices (rice, beef, sugar, eggs) | about 0 | about 0 | **log** (for consistency; no harm) |
| Survey indices | −0.17 to −0.46 | worse (−0.31 to −0.62) | **level** |
| Spending shares | −0.16 to +0.25 | similar | **level** |

The survey indices move more when they are **low**, as in crises. That is a real signal, not a scale problem, so log would hide it.

**Sign note:** all `log` series are strictly positive today (check Z1 in [VALIDATION_CALENDAR.md](VALIDATION_CALENDAR.md)).

### Step 3 — Change measures (the core inputs for Q1 and Q2)

Computed on the step-2 series, which we call `x`:

| Measure | Weekly (food prices) | Monthly | Answers | Unit |
|---|---|---|---|---|
| **Short change** | `x[t] − x[t−1]` (week on week) | `x[t] − x[t−1]` (month on month) | Q1: "vs last period" | log: ×100 ≈ %; level: points |
| **Medium change** | `x[t] − x[t−4]` (4 weeks) | `x[t] − x[t−3]` (3 months) | Smooths noise and sticky prices | same |
| **Long change (YoY)** | `x[t] − x[t−52]` (calendar rule C8) | `x[t] − x[t−12]` | Q2: "vs a year ago" | same |
| **Gap to recent baseline** | `x[t] − median(x[t−13 … t−1])` (last 13 weeks) | `x[t] − median(x[t−6 … t−1])` (last 6 months) | Q2: "vs the last few months" | same |

**Rules:**

- If any input is missing (or masked), the result is missing. Never fill with zero.
- **YoY on its own removes most fixed seasonality** (same month vs same month). That is why it is the backbone of Q2, even before Phase 2's seasonal models.
- **Idul Fitri warning:** YoY compares Mar 2026 with Mar 2025, but Idul Fitri moved from 31 Mar to 20 Mar. Month-on-month and YoY changes around Idul Fitri months must be read with the holiday features (step 4).

**Evidence that the medium window helps:** rice in traditional markets often doesn't change for weeks. Its 4-week change has a clear spread (2.0%) where the weekly change is mostly zero.

### Step 4 — Seasonal split (Phase 2)

**What:** robust **STL** on the step-2 series, which splits it into **trend + seasonal + remainder**. Use season length 12 (monthly) or 52 (weekly). Add the holiday features from calendar rule B5 as regressors where the inventory says `holiday_adj = yes`.

**How strong is the seasonality?** This is the share of the monthly-change spread explained by month of year. For reference, about 6% is what pure noise would give.

| Series | Seasonal share | Treatment |
|---|---|---|
| Card value and volume | 48 – 63% | Full seasonal model |
| Narrow money (M1) | 61% | Full seasonal model |
| Currency in circulation | 42% | Full seasonal model + Idul Fitri features |
| RTGS | 25 – 33% | Seasonal model |
| Demand deposits, loan instalment share | 23 – 24% | Seasonal model |
| E-money purchase value and volume | 20 – 21% | Seasonal model |
| Survey indices | 8 – 12% | **Weak.** A simple model is enough (Phase 2 confirms). |
| E-money stocks (float, instruments) | 3 – 14% | Weak |

**Holiday features:** where they matter (`holiday_adj = yes` in the inventory):

- All monthly flows, currency in circulation, narrow money and demand deposits
- Food groups 2 (chicken), 3 (beef) and 5 (shallot), in all 3 markets

These react to Idul Fitri (see [VALIDATION_CALENDAR.md, B5](VALIDATION_CALENDAR.md#b5-holidays-and-events-on-the-calendar)).

### Step 5 — Standardise (Phase 3–4)

**What:** turn each change or remainder into a **robust z-score**:

`z = (change − median) / spread`, where `spread = max(1.4826 × MAD, floor)`

(MAD = median absolute deviation.)

**Why the floor?** Sticky prices have a MAD close to zero, so tiny moves get huge z-scores. The first check flagged 165–184 false "extremes" in rice.

**Proposed floors:**

| Series | Floor on weekly change | Floor on monthly change |
|---|---|---|
| Food prices, low volatility | 0.5% | — |
| Food prices, mid volatility | 1.0% | — |
| Food prices, high volatility | 2.0% | — |
| Monthly `log` series | — | 0.5% |
| Survey indices | — | 1.0 point |
| Spending shares | — | 0.2 points |

**Volatility tiers for food** (`vol_tier` column), from the spread of the 4-week change in traditional markets:

| Tier | Groups | 4-week spread |
|---|---|---|
| low | 1 Rice, 3 Beef, 9 Cooking oil, 10 Sugar | 1.2 – 3.1% |
| mid | 2 Chicken, 4 Eggs | 4.8 – 6.0% |
| high | 5 Shallot, 6 Garlic, 7 Red chili, 8 Bird's-eye chili | 8.8 – 20.5% |

The tiers matter for alert thresholds too. A 10% weekly move is an event for rice but a normal week for chili.

**Tested with these floors** (weekly change, full history 2019–2026, about 400 weeks): the number of weeks with |z| > 4 per series is:

| Market | 1 Rice | 2 Chicken | 3 Beef | 4 Eggs | 5 Shallot | 6 Garlic | 7 Red chili | 8 Bird's-eye chili | 9 Cooking oil | 10 Sugar |
|---|---|---|---|---|---|---|---|---|---|---|
| Traditional | 21 | 11 | 21 | 20 | 7 | 15 | 3 | 6 | 24 | 18 |
| Modern | 17 | 9 | 17 | 12 | 3 | 8 | 3 | 7 | 32 | 19 |
| Wholesale | 1 | 2 | 10 | 9 | 2 | 13 | 2 | 2 | 15 | 12 |

That is 0–8% of weeks. Many of these are real events (the cooking oil caps in 2022, the garlic spikes in 2019–2020) or the errors in [DATA_QUALITY.md](DATA_QUALITY.md). Phase 4 tunes the final thresholds, using persistence rules and the target alert rate.

**Window:** compute the median and MAD over a **rolling window** (the last 3 years, excluding the current point), so the baseline adapts slowly and a new shock doesn't hide itself.

### Step 6 — Structural breaks

**What:** keep a short list of known **level shifts** (a `breaks` table: `series_id, date, reason`). For each break:

- Change measures that span the break (for example, YoY in the 12 months after it) get `quality_flag = review`.
- Baselines and models use only data **after** the break, or add a step dummy (Phase 2).

**Starting list** (to confirm):

| Series | Date | Reason |
|---|---|---|
| `bi_emoney.value`, `bi_emoney.value_topup` | Jan 2019 | Value jumps about 4.5× and stays: likely a change in reporting coverage |
| E-money instruments and `emoney_instruments_outstanding` | Nov 2017 | Cashless toll roads (real, but a step) |
| Cooking oil (group 9) | 1 Feb 2022, 16 Mar 2022 | Price cap on, then off (real, policy-driven) |

### Step 7 — Frequency alignment (Phase 7)

To compare weekly food prices with monthly series, convert weekly to monthly using calendar rules C11–C12: the month containing the Thursday, the mean of the weeks, and at least 3 weeks with values. Then apply steps 2–5 to the monthly version. Never go the other way: don't split monthly data into weeks.

## 3. New inventory columns

These are added to [indicator_inventory.csv](../Scope/indicator_inventory.csv):

| Column | Values | Meaning |
|---|---|---|
| `series_kind` | `price`, `flow`, `stock`, `index`, `share` | Drives steps 1 and 2 |
| `calendar_adj` | `per_day`, `none` | Step 1 |
| `transform` | `log`, `level` | Step 2 (already there) |
| `seasonal_period` | `52`, `12` | Steps 3–4 (already there) |
| `holiday_adj` | `yes`, `no` | Step 4 |
| `vol_tier` | `low`, `mid`, `high` (food only) | Step 5 floors |
| `z_floor` | number | Step 5 spread floor, in the unit of the short change (log × 100 = %, or points) |

## 4. Output tables (suggested)

| Table | One row per | Columns |
|---|---|---|
| `features` | series × period | `series_id, ref_date, x` (after steps 1–2), `chg_short, chg_medium, chg_yoy, gap_baseline`, holiday features, `quality_flag` |
| `breaks` | break | `series_id, date, reason` |

`features` is what Phases 2–4 read. They never go back to the raw files.

## 5. Checks for the transformation code

| # | Check |
|---|---|
| T1 | `x` exists for every row where `value` exists |
| T2 | Flow series: `x = log(value / days_in_month)`. Spot-check 3 rows by hand. |
| T3 | `chg_yoy` for monthly series is missing for the first 12 months of each series. For weekly, the first 52 weeks. |
| T4 | No change measure is computed across a missing or masked value |
| T5 | Recomputing on the same input gives identical output |
| T6 | Sticky-price check: after the floor, rice in traditional markets has about 20 weeks with \|z\| > 4 in the full history (it had 165 before the floor). Tested with full-history median and MAD; the rolling window may differ slightly. |
