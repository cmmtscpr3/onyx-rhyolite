# Phase 2 — Profiling Spec

What the Phase 2 code should do: understand each of the 54 series before anything tries to predict it.
You write the code; this document gives the algorithms as pseudocode, the settings, the outputs and the checks
that prove it works. There are no function signatures here on purpose: the structure of the code is yours.

Related files:

- [../WORKPLAN.md](../WORKPLAN.md), section 6, Phase 2: the goal and the deliverables
- [../DataFoundation/PHASE1_SPEC.md](../DataFoundation/PHASE1_SPEC.md): the input table this phase reads
- [../DataFoundation/TRANSFORMS.md](../DataFoundation/TRANSFORMS.md): steps 3 to 5 (change measures, STL, robust z) are picked up here
- [../DataFoundation/VALIDATION_CALENDAR.md](../DataFoundation/VALIDATION_CALENDAR.md): rules C9 and C10 (week 53), B5 (holiday windows)
- [../Scope/indicator_inventory.csv](../Scope/indicator_inventory.csv): `seasonal_period`, `holiday_adj`, `vol_tier`, `z_floor`
- [../DataFoundation/holiday_calendar.csv](../DataFoundation/holiday_calendar.csv): the Idul Fitri dates and windows

**How the numbers in this document were obtained.** A throwaway prototype of exactly this pseudocode was run once
on `data/observations.csv` (data as of 30 Sep 2026) to fill the "expected today" columns and to check that the
steps fit together. The prototype is not part of the repo. Where a number comes from it, the text says "prototype".

---

## 1. What Phase 2 produces

Three files under `data/profiles/`. The code rebuilds all three from `data/observations.csv` on every run; it never
reads `Dataset/` and never re-runs Phase 1.

### 1a. `components.csv`: one row per series per period

| Column | Meaning |
|---|---|
| `series_id`, `ref_date`, `frequency` | Copied from `observations` |
| `x` | The Phase 1 log value (empty where missing or masked) |
| `x_filled` | `x` with short gaps linearly interpolated (section 3). Only used as STL input. |
| `was_filled` | `True` where `x` was empty and `x_filled` is interpolated |
| `trend`, `seasonal`, `remainder` | The STL components (section 4). `remainder` is empty where `was_filled` is `True`. |
| `robust_weight` | STL's robustness weight, 0 to 1. Low means STL treated the point as an outlier. |
| `d1` | Short change `x[t] − x[t−1]`. Empty if either side is empty. Never filled. |
| `vol_roll` | Rolling robust spread of `d1`, floored (section 7) |
| `roll_trend`, `roll_slope_yr` | Rolling-window Mann-Kendall verdict and Sen's slope, % per year (section 6) |
| `in_fitri_window` | `True` if the period overlaps an Idul Fitri window (section 8) |

### 1b. `profile_cards.csv`: one row per series

The full column list is in section 9. Groups of columns: identity and coverage; seasonality; trend; volatility;
Idul Fitri; behaviour labels; a one-sentence `summary`.

### 1c. `profiles.md`: the readable version of the cards

One short block per series, grouped by theme, for the analyst checkpoint. Section 9 gives the sentence rules.

## 2. Inputs and settings

**Inputs**

| File | Used for |
|---|---|
| `data/observations.csv` | `x` per series and period, `quality_flag`, `iso_year`, `iso_week`, `is_provisional` |
| `Scope/indicator_inventory.csv` | `seasonal_period` (52 or 12), `z_floor` (spread floor, %), `vol_tier` and `holiday_adj` (to compare against) |
| `DataFoundation/holiday_calendar.csv` | Rows with `event = idul_fitri`: `date`, `window_before_days`, `window_after_days` |
| `breaks.csv` (new, hand-kept, next to `data_issues.csv`) | `series_id, date, reason`. Profiling starts after the latest break. Seed it from TRANSFORMS.md step 6 (table below). |

**Starting `breaks.csv`** (from [TRANSFORMS.md](../DataFoundation/TRANSFORMS.md), step 6; the cooking oil price caps are events, not breaks, so they are left out):

| series_id | date | reason |
|---|---|---|
| `bi_emoney.value`, `bi_emoney.value_topup` | 2019-01-01 | value jumps about 4.5× and stays: reporting coverage change |
| `bi_emoney.instruments`, `bi_emoney.instruments_chip`, `bi_emoney.instruments_server`, `bi_payment_system.emoney_instruments_outstanding` | 2017-11-01 | cashless toll roads: real, but a permanent step |

**Settings** (keep them in one place, with these defaults):

| Setting | Default | Why |
|---|---|---|
| `P` seasonal period | 52 weekly, 12 monthly (inventory) | One value per week or month, so one seasonal cycle. No MSTL needed: nothing in scope has two cycles. |
| STL `seasonal` window | 13 | Odd, ≥ 7. Lets the seasonal shape drift over about a decade, not year to year. Prototype: 7 inflates the robust seasonal strength (the pattern absorbs noise); a periodic pattern under-fits the monthly series (e-money purchases 0.62 → 0.28). 13 sits in between. |
| STL `robust` | on | Down-weights COVID months, price-cap weeks and typos so they land in the remainder, not in the trend |
| STL `trend` window | statsmodels default | Smallest odd integer above `1.5 × P / (1 − 1.5 / seasonal)`: 93 weeks, 21 months |
| `max_fill` | 3 periods | Longest gap the interpolation may bridge. Today the longest gap is 1 week. A longer one must stop the run. |
| `W` rolling window | 3 years: 156 weeks, 36 months | Same horizon for rolling trend and rolling volatility |
| `alpha` | 0.05 | Significance level for Mann-Kendall |
| `min_history` | `3 × P` | Below this, only the volatility step runs and the card says `confidence = low`. All 54 series pass today (shortest: `bi_emoney.value` after its break, 91 months). |
| Spread floor | `z_floor / 100` from the inventory | Sticky prices (TRANSFORMS step 5) |
| Volatility tier cut-offs | `low < 4% ≤ mid < 8% ≤ high` on the robust spread of the 4-week change (3-month for monthly) | Section 7 |

Everything is computed on `x` (log scale). A difference of 0.01 in `x` is about 1%, and the document quotes such
values as percentages.

## 3. Per-series preparation

```
for each series in observations, ordered by ref_date:
    P = seasonal_period from the inventory
    if the series has rows in breaks.csv:
        keep only periods on or after the latest break date; note "profiled from <date>" on the card
    y = x
    missing = (y is empty)                        # covers quality_flag 'missing' and 'masked_error'
    y_filled = y with interior gaps of length <= max_fill linearly interpolated
    if any gap is longer than max_fill: stop with an error naming the series and the gap
    was_filled = missing

    weekly only (rule C9): mark rows with iso_week == 53 (2020 and 2026 today)
        remove them from the STL input, so the input has exactly 52 periods per cycle
        after STL, put them back:
            seasonal = the seasonal value of week 52 of the same ISO year
            trend    = linear interpolation between the neighbouring weeks
            remainder = y − trend − seasonal

    if number of rows < min_history: skip sections 4 to 6 and 8; run section 7 only; confidence = low
```

Provisional values (the latest 2 periods) are used like any other value; the card records `n_provisional` so a
reader knows the tail may still move.

## 4. Step A — Robust STL

```
result = statsmodels STL(y_filled without week-53 rows, period=P, seasonal=13, robust=True).fit()
trend, seasonal, remainder, robust_weight = result.trend, result.seasonal, result.resid, result.weights
re-insert the week-53 rows (section 3)
remainder[was_filled] = empty                   # an interpolated point has no real remainder
check: at every row with a real value and not week 53, |y − (trend + seasonal + remainder)| < 1e-9
```

**Why not MSTL:** MSTL is for several seasonal periods at once (for example, daily data with weekly and yearly
cycles). Each series here has one observation per week or per month, so one cycle. The work plan's "use MSTL where
there are several seasonal patterns" applies to nothing in scope; say so in the code comment and move on.

**Prototype:** runs for all 54 series; the recomposition check holds everywhere; 15 to 90 points per series get a
robustness weight under 0.5 (most in modern-market beef, sugar and cooking oil, whose prices step rather than drift).

## 5. Step B — Seasonal strength and shape

Two strength scores, both in `[0, 1]`, after Wang, Smith and Hyndman (also Hyndman and Athanasopoulos, *FPP3*,
section 4.3):

```
F_T = max(0, 1 − spread(remainder) / spread(trend + remainder))        # trend strength
F_S = max(0, 1 − spread(remainder) / spread(seasonal + remainder))     # seasonal strength
computed on rows where remainder is not empty
```

Compute each **twice**, with two definitions of `spread`:

| Variant | `spread` | Column | Use |
|---|---|---|---|
| Textbook | variance | `F_T_var`, `F_S_var` | Reported for comparison with the literature |
| **Robust** | `(1.4826 × MAD)²` | `F_T`, `F_S` | **Used for the labels and the sentences** |

**Why the robust one.** The variance of the remainder is dominated by a handful of huge months (COVID, the 2022
cooking-oil caps, the data errors still flagged `review`). Prototype: with the variance version the ATM/debit value
series scores `F_S_var = 0.18` although it peaks every December; the robust version gives 0.73. The correlation
between the two across the 54 series is only 0.32, so the choice matters.

**Caveat, sticky prices.** A sticky series has a tiny remainder, so even a 3% seasonal swing looks "strong"
(traditional rice: `F_S = 0.60` with a peak-to-trough swing of 2.8%). Always read `F_S` together with the amplitude,
and let the labels in section 10 require both.

Seasonal shape:

```
amplitude = max(seasonal) − min(seasonal)                 # ×100 ≈ % peak to trough
slot      = month (1–12) for monthly; ISO week (1–52, week 53 counted as 52, rule C10) for weekly
mean seasonal value per slot → peak_slot = slot with the highest mean, trough_slot = lowest
stability: F_S (robust) on the first half of the rows and on the second half;
           flag 'seasonality_changed' if the two differ by more than 0.2
```

**Expected today (prototype, robust `F_S`, amplitude, peak → trough):**

| Series | `F_S` | Amplitude | Peak → trough | Reads as |
|---|---|---|---|---|
| `bi_payment_system.currency_in_circulation` | 0.84 | 12.8% | Dec → Feb | Strong, year-end cash demand |
| `bi_payment_system.narrow_money` | 0.78 | 6.6% | Dec → Feb | Strong |
| `bi_card_transactions.atm_debit.value` | 0.73 | 10.2% | Dec → Jan | Strong |
| `bi_emoney.value` (from 2019) | 0.68 | 41.8% | May → Jun | Strong but the halves disagree (0.91 vs 0.28): read with care |
| `pihps.traditional.02_daging_ayam` (chicken) | 0.68 | 23.9% | week 1 → week 36 | Strong |
| `pihps.traditional.04_telur_ayam` (eggs) | 0.70 | 16.7% | week 52 → week 41 | Strong |
| `pihps.traditional.05_bawang_merah` (shallot) | 0.58 | 54.2% | week 24 → week 40 | Some, large swing |
| `pihps.traditional.08_cabai_rawit` (bird's-eye chili) | 0.66 | 75.4% | week 50 → week 44 | Strong, huge swing |
| `pihps.traditional.07_cabai_merah` (red chili) | 0.29 | 53.5% | week 50 → week 34 | Weak: the spikes are weather, not calendar |
| `pihps.traditional.01_beras` (rice) | 0.60 | 2.8% | week 30 → week 48 | Sticky-price artefact: small swing |
| `bi_emoney.instruments_server` | 0.18 | 8.0% | — | None |

16 of 54 series have halves that differ by more than 0.2 (for example `bi_card_transactions.credit.cards` 0.66 →
0.09). These go on the checkpoint list: their seasonal pattern is not stable, so Phase 3 should weight recent years.

## 6. Step C — Trend: Mann-Kendall and Sen's slope

**Input:** the seasonally adjusted series `sa = y_filled − seasonal` (week-53 rows left out). Not the trend
component: it is smoothed, so a test on it would find a "significant" trend in almost anything.

**Full window**

```
result = pymannkendall.hamed_rao_modification_test(sa, alpha=alpha)   # corrects for autocorrelation
mk_trend = result.trend                 # 'increasing', 'decreasing' or 'no trend'
mk_p     = result.p
slope_yr = result.slope × P × 100       # Sen's slope per period → % per year on the log scale
cross-check = pymannkendall.seasonal_test(y_filled, period=P, alpha=alpha).trend
mk_agree = (cross-check == mk_trend)    # prototype: disagree for 1 of 54 (bi_payment_system.rtgs.volume)
```

**Rolling window** (feeds the Phase 4 trend-change detector and the `trend_now` label):

```
for every period t from W−1 to the end, step 1:
    window = the W periods ending at t, minus week-53 rows
    if more than 10% of the window was filled: roll_trend[t] = empty; continue
    if the window has no variation (all ties, the test cannot compute): roll_trend[t] = 'no trend', roll_slope_yr[t] = 0
    else: r = hamed_rao_modification_test(sa[window], alpha); roll_trend[t] = r.trend; roll_slope_yr[t] = r.slope × P × 100
card: roll_trend_now = roll_trend at the last period, roll_slope_now = roll_slope_yr at the last period,
      share_significant = share of windows with a verdict other than 'no trend',
      last_direction_change = the last ref_date where roll_trend differs from the period before (empty if never)
```

**`trend_now`: how the recent 3 years compare with the full history.** This is the field analysts will read, because
the full-window verdict alone says almost nothing: 53 of 54 series are "increasing" (they are nominal prices and
money amounts, so they grow with inflation and the economy).

```
a = |slope_yr|
if roll_trend_now == 'no trend' and mk_trend != 'no trend':            trend_now = 'faded'
elif roll_trend_now != 'no trend' and sign(roll_slope_now) != sign(slope_yr): trend_now = 'reversed'
elif |roll_slope_now − slope_yr| < 0.5 × max(a, 1):                     trend_now = 'steady'
elif |roll_slope_now| > a:                                               trend_now = 'accelerating'
else:                                                                    trend_now = 'slowing'
```

**Expected today (prototype):** steady 21, slowing 11, faded 11, accelerating 8, reversed 3.

| `trend_now` | Series (prototype) |
|---|---|
| reversed | `bi_card_transactions.atm_debit.volume` (+9.2%/yr full, −6.4%/yr recent), `bi_payment_system.rtgs.volume`, `pihps.modern.07_cabai_merah` |
| faded | `bi_card_transactions.atm_debit.value`; garlic (group 6) in all 3 markets; red chili traditional and wholesale; bird's-eye chili in all 3 markets; `pihps.modern.03_daging_sapi`; `pihps.wholesale.04_telur_ayam` |
| accelerating | chicken (group 2) and shallot (group 5) in all 3 markets (shallot about +11%/yr recently vs +5% full); `bi_card_transactions.credit.volume`; `bi_payment_system.rtgs.value` |
| slowing | the e-money float and instrument series (growth of 24–55%/yr over the full history, 10–19% recently), `bi_card_transactions.atm_debit.cards`, eggs modern and traditional, cooking oil modern, sugar wholesale |

Full-window slopes for reference: food 1.8–8.5% per year; card series 2–12%; payment system 6–12%; e-money 24–55%.

**Runtime note.** The rolling test with step 1 is the slow part: about 55 seconds for all 54 series in the
prototype (the weekly series have about 250 windows of 156 points each). Acceptable; if it ever matters, step 4
for weekly series loses little.

## 7. Step D — Baseline volatility

```
d1[t] = y[t] − y[t−1]                                   # empty if either is empty; never use y_filled here
floor = z_floor / 100                                   # inventory; 0.5% for every series without a tier
for every t:
    spread[t] = 1.4826 × MAD(d1 over the W periods ending at t−1, ignoring empties; needs at least P values)
    vol_roll[t] = max(spread[t], floor)
card:
    vol_baseline = median(vol_roll over the whole (post-break) history)
    vol_recent   = median(vol_roll over the last W periods)
    vol_current  = vol_roll at the last period
    vol_ratio    = vol_current / vol_baseline
    remainder_mad = 1.4826 × MAD(remainder)              # the STL view of noise
    sticky_share  = share of periods with d1 == 0 exactly
    d4 = y[t] − y[t−4] weekly, y[t] − y[t−3] monthly
    spread_4 = 1.4826 × MAD(d4)                          # the measure TRANSFORMS used for the food tiers
    observed_tier = low if spread_4 < 4%, mid if < 8%, else high
    tail_ratio = 95th percentile of |d1| / (1.4826 × MAD(d1))   # "calm with rare big jumps" shows as a high value
```

Rules carried over from TRANSFORMS.md step 5: the window excludes the current point, so a new shock does not hide
itself; the floor stops sticky prices from producing huge z-scores later.

**Expected today (prototype):**

- `vol_baseline` sits exactly on the floor (0.5%) for 12 series: rice, cooking oil and sugar in all 3 markets,
  traditional and wholesale beef, `bi_card_transactions.credit.cards`, `bi_emoney.instruments_chip`.
- `sticky_share`: rice 0.49–0.58, sugar 0.37–0.46, cooking oil 0.22–0.38, traditional beef 0.14, everything else
  under 0.10. Nine series are above 0.2.
- `vol_ratio` under 0.5 for 8 e-money series (0.25–0.43): their volatility fell as the series matured, so the
  full-history baseline overstates "normal" for them. That is why `vol_recent` is also on the card.
- `observed_tier` agrees with the inventory's `vol_tier` for 22 of the 30 food series. The disagreements:
  garlic (group 6) is `high` in the inventory but 2.7–4.5% here (`low` or `mid`); modern chicken, modern eggs,
  traditional eggs and modern red chili come out one tier lower than listed. Garlic is the interesting one: it is
  calm most weeks with rare, very large spikes (2019, 2020), which a MAD does not see. That is what `tail_ratio`
  is for. The prototype did not compute `tail_ratio`; expect garlic to rank highest among the food series.
- Decision for the checkpoint: re-derive `vol_tier` and `z_floor` in the inventory from this output.

## 8. Step E — Idul Fitri diagnostic

Plain STL cannot follow a holiday that moves about 11 days earlier each year, so its effect ends up in the
remainder. This step measures how much, per series, so Phase 3 knows where a holiday regressor is needed. It does
not adjust anything.

```
windows = for each holiday_calendar row with event == 'idul_fitri':
              [date − window_before_days, date + window_after_days]        # 14 days before, 7 after
in_fitri_window[t] = the period overlaps any window
                     weekly: the period is Monday..Sunday; monthly: the whole calendar month
r_in  = remainder where in_fitri_window and not empty
r_out = remainder where not in_fitri_window and not empty
fitri_mean  = mean(r_in)                                   # ×100 ≈ % above (+) or below (−) the seasonal norm
fitri_ratio = (1.4826 × MAD(r_in)) / (1.4826 × MAD(r_out))  # > 1 means noisier around the holiday
holiday_sensitive = fitri_ratio > 1.5 or |fitri_mean| > remainder_mad
card: fitri_mean, fitri_ratio, holiday_sensitive, holiday_adj (inventory), fitri_agrees = (holiday_sensitive == (holiday_adj == 'yes'))
```

**Expected today (prototype):** 19 series flagged; the flag agrees with the inventory's `holiday_adj` for only 25
of 54. The disagreements are the finding, not a bug. They go to the checkpoint:

| Direction | Series | Numbers |
|---|---|---|
| Flagged, inventory says yes | ATM/debit value and volume (ratio 5.9, 4.1), currency in circulation (ratio 4.5, +3.8%), narrow money, RTGS value, RTGS volume (−9.2%: fewer working days), traditional beef (ratio 2.0) | Clear |
| Flagged, inventory says **no** | cooking oil in all 3 markets (+2.6 to +3.3%), sugar in all 3 (+1.3 to +1.9%), rice in all 3 (+0.5 to +1.0%, ratio 1.2–1.8), traditional eggs (−1.7%), traditional and wholesale garlic, `bi_emoney.float_funds_bank` | Plausible: staples rise before Lebaran. The inventory list was a first guess. |
| **Not** flagged, inventory says yes | chicken in all 3 markets (−0.5 to −2.0%), shallot in all 3, modern and wholesale beef, credit card value and volume, the 6 e-money flows, demand deposits | Chicken and shallot rise in the 4 weeks before and fall after (VALIDATION_CALENDAR B5); a window that starts 14 days before the holiday averages the two out. Try `window_before_days = 28` for weekly food series and see if they flip. |

So one tuning knob is already known: the weekly pre-window. Keep it a setting.

## 9. Step F — The profile card and the sentences

**`profile_cards.csv` columns**

| Group | Columns |
|---|---|
| Identity | `series_id, frequency, theme, series_kind, profiled_from (break date or first date), n_periods, n_missing, n_provisional, confidence` |
| Seasonality | `F_S, F_T, F_S_var, F_T_var, amplitude_pct, peak_slot, trough_slot, F_S_first_half, F_S_second_half, seasonality_changed` |
| Trend | `mk_trend, mk_p, slope_yr, mk_agree, roll_trend_now, roll_slope_now, share_significant, last_direction_change, trend_now` |
| Volatility | `vol_baseline, vol_recent, vol_current, vol_ratio, remainder_mad, sticky_share, spread_4, observed_tier, vol_tier (inventory), tail_ratio, n_low_weight` |
| Idul Fitri | `fitri_mean, fitri_ratio, holiday_sensitive, holiday_adj (inventory), fitri_agrees` |
| Labels | `trend_axis, season_axis, noise_axis, sticky, behaviour` (section 10) |
| Text | `summary` |

Percentages are stored as percentages (×100), rounded to 1 decimal; strengths to 2 decimals.

**Sentence rules for `summary` and `profiles.md`** (one clause per axis, joined into one or two sentences):

```
seasonal clause:
    strong: "Strong seasonality (F_S): peaks in <peak>, lowest in <trough>, swing about <amplitude>%."
    some:   "Some seasonality (F_S): peaks in <peak>, swing about <amplitude>%."
    none:   "No clear seasonal pattern."
    + " The pattern has changed over time." if seasonality_changed
trend clause:
    flat:   "No clear long-run trend."
    else:   "Rising|Falling about <slope_yr>% a year over the full history"
            + {steady: "; the last 3 years look the same.",
               accelerating: "; faster recently (<roll_slope_now>%/yr).",
               slowing: "; slower recently (<roll_slope_now>%/yr).",
               faded: "; no significant trend in the last 3 years.",
               reversed: "; the last 3 years go the other way (<roll_slope_now>%/yr)."}
noise clause:
    "<Low|Mid|High> volatility: a typical period moves about <vol_baseline>%"
    + ", <vol_ratio × 100>% of normal right now" if vol_ratio < 0.67 or > 1.5
    + "; price unchanged in <sticky_share>% of weeks" if sticky
    + "; calm with rare large jumps" if tail_ratio is high (threshold to set once measured)
holiday clause:
    "Reacts to Idul Fitri (<fitri_mean>% vs its seasonal norm)." if holiday_sensitive
slot names: monthly → month name; weekly → "week <n> (around <first Monday of that ISO week in the latest year>)"
```

Example (traditional chicken, from the prototype numbers): *Strong seasonality (0.68): peaks in week 1 (around
early January), lowest in week 36, swing about 24%. Rising about 2.2% a year over the full history; faster
recently (4.6%/yr). Mid volatility: a typical week moves about 2.2%.*

`profiles.md` is the same text per series under a heading, grouped by theme, with the 10 to 12 key numbers in a
small table under each heading, so the analyst can scan it in one sitting.

## 10. Step G — Behaviour groups

Rule-based, on three axes, because the first draft ("seasonal / trending / noisy / stable") put 50 of 54 series
in "trending" and told the analyst nothing.

```
trend_axis:  'flat'   if mk_trend == 'no trend' or |slope_yr| < 2
             'strong' if |slope_yr| >= 10
             'growth' otherwise
season_axis: 'strong' if F_S >= 0.6 and amplitude >= 5%
             'some'   if F_S >= 0.3 and amplitude >= 2%
             'none'   otherwise
noise_axis:  observed_tier                      # low / mid / high
sticky:      sticky_share >= 0.2
behaviour = "trend:<trend_axis>+season:<season_axis>+noise:<noise_axis>" + ("+sticky" if sticky)
```

**Expected today (prototype):**

| | season: none | some | strong | total |
|---|---|---|---|---|
| trend: flat | 0 | 3 | 0 | 3 |
| trend: growth | 2 | 12 | 22 | 36 |
| trend: strong | 2 | 10 | 3 | 15 |
| total | 4 | 25 | 25 | 54 |

Noise: low 21, mid 18, high 15. Sticky: 9 (rice, sugar, cooking oil × 3 markets).

What the groups are for: Phase 3 picks a forecasting baseline per group (season:strong → seasonal naive or ETS with
seasonality; season:none → naive or drift; sticky → compare 4-week changes, not weekly ones; noise:high → wider
bands and persistence rules). The thresholds (2, 10, 0.3, 0.6, 2%, 5%, 0.2) are starting points to confirm at the
checkpoint; keep them in the settings table.

## 11. Acceptance checks

The Phase 2 code is done when all of these pass. "Expected today" is data as of 30 Sep 2026.

| # | Check | Expected today |
|---|---|---|
| 1 | Cards in `profile_cards.csv` | 54 (30 weekly, 24 monthly) |
| 2 | Rows in `components.csv` | 16,151 with the seeded `breaks.csv` (16,635 without) |
| 3 | Recomposition: `x = trend + seasonal + remainder` at every row with a value, outside week 53 | Within 1e-9 |
| 4 | `remainder` empty exactly where `was_filled` or `x` is empty | Yes |
| 5 | `d1` empty across every missing or masked period, on both sides | Yes (50 missing + 0 masked rows today) |
| 6 | Week-53 rows present in `components.csv` with a seasonal value equal to the same year's week 52 | 2020 and 2026, 30 weekly series |
| 7 | Robust `F_S` for `bi_payment_system.currency_in_circulation` | about 0.84 (peak December, trough February) |
| 8 | Robust `F_S` for `bi_card_transactions.atm_debit.value`; textbook `F_S_var` | about 0.73; about 0.18 |
| 9 | `mk_trend` | 'increasing' for 53 series; 'no trend' for `bi_payment_system.rtgs.volume` |
| 10 | `trend_now` counts | steady 21, slowing 11, faded 11, accelerating 8, reversed 3 |
| 11 | `sticky_share` for `pihps.traditional.01_beras` | about 0.58 |
| 12 | `vol_baseline` on the floor (0.5%) | 12 series (section 7) |
| 13 | `holiday_sensitive` count | 19; agrees with the inventory for 25 |
| 14 | Behaviour table | As in section 10 |
| 15 | Synthetic: a sine of period P plus 1% noise | robust `F_S` ≥ 0.95, `mk_trend` = 'no trend' |
| 16 | Synthetic: a straight line plus 1% noise | `F_T` ≥ 0.95, `mk_trend` = 'increasing', slope within 5% of the true slope |
| 17 | Synthetic: white noise | `F_S` ≤ 0.4, `mk_trend` = 'no trend' |
| 18 | Re-running on the same inputs gives identical files | Yes |
| 19 | `Dataset/` untouched (hash before and after, as in `tests/test_pipeline.py`) | Yes |
| 20 | Run time for all 54 series | Under 2 minutes |

Checks 7 to 13 should be tested with a tolerance (±0.05 on strengths, ±1 on counts): STL, interpolation and
window edges can shift them slightly between implementations. If a number is far off, the first things to compare
are the `seasonal` window (13), the robust spread (`1.4826 × MAD`, squared for the strengths) and whether the test
ran on `y − seasonal` rather than on `trend`.

Synthetic checks 15 to 17 were run in the prototype with 120 monthly points: sine `F_S = 1.00`, line `F_T = 1.00`
with the slope recovered exactly, noise `F_S_var = 0.33`.

## 12. Analyst checkpoint: what to put on the table

The checkpoint question is "do the profiles match what analysts know?". Print these from the outputs:

1. **Seasonal peaks and troughs for the 10 food groups × 3 markets**, as a 10 × 3 grid of "peak week → trough
   week". Ask: is chicken really highest at New Year and lowest around week 36? Are eggs highest at year end? Does
   shallot peak mid-year (week 24)?
2. **The `trend_now` lists** from section 6. Ask about the reversals (ATM/debit volume falling for 3 years, RTGS
   volume) and the faded trends (garlic, chili).
3. **The Idul Fitri disagreements** from section 8, with the proposed wider pre-window for weekly series.
4. **The volatility tier mismatches** from section 7, and whether to update `vol_tier` and `z_floor` in the inventory.
5. **The 16 series whose seasonal pattern changed between halves.**
6. The one-line summaries for all 54, in `profiles.md`.

Decisions to record in the checklist's decision log: the thresholds in section 10, the holiday window, the tier
update, and which series get `confidence = medium` because of unstable seasonality.

## 13. Suggested code layout (not binding)

One new entry point next to the Phase 1 one, reading `data/observations.csv`, writing to `data/profiles/`:

| Part | Does |
|---|---|
| settings | The table in section 2, in one place |
| prepare | Section 3: break cut, interpolation, week-53 handling |
| decompose | Section 4 |
| strength | Section 5 |
| trend | Section 6, full and rolling |
| volatility | Section 7 |
| holiday | Section 8 |
| cards | Sections 9 and 10, including the sentences |
| run | Loops over the series, writes the three files, prints a 4-line summary like `ews.run` does |

Tests follow the Phase 1 pattern: a session fixture that runs the whole thing once against the real data, then one
small test per acceptance check. New dependencies go in `requirements.txt`: `statsmodels` (STL), `scipy`
(`median_abs_deviation` with `scale='normal'` gives the `1.4826 × MAD` directly), `pymannkendall` (the tests and
Sen's slope).
