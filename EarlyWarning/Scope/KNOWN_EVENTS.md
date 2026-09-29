# Known Events — test set (DRAFT)

Past events the early warning system should catch. We use them in Phases 3–4 to check whether the system
flags the right things, and how early.

> **This is a draft from general knowledge.** Every row is marked `candidate`.
> Please confirm, fix dates, remove rows or add events you know about. When a row is confirmed, change its status to `confirmed`.

## 1. One-off events

| # | Event | Date(s) | Indicators expected to react | Expected signal | Status |
|---|---|---|---|---|---|
| 1 | Toll roads go fully cashless | 31 Oct 2017 | E-money instruments (chip), e-money volume and value | Level shift up | candidate |
| 2 | Garlic price spike (import delays) | Apr – May 2019 | Food group 6 (garlic), all markets | Spike up | candidate |
| 3 | COVID-19: first cases, then large-scale social restrictions (PSBB) | Mar – Jun 2020 | Consumer sentiment (all 9 indices), card and e-money transactions, RTGS | Sharp drop, then a slow recovery. Level shift and higher volatility. | candidate |
| 4 | Bird's-eye chili price spike | Jan – Mar 2021 | Food group 8, all markets | Spike up | candidate |
| 5 | Cooking oil crisis: price caps, then export ban | Nov 2021 – Jun 2022 (export ban 28 Apr – 23 May 2022) | Food group 9, all markets | Trend up, then level shifts as policy changed | candidate |
| 6 | VAT rise from 10% to 11% | 1 Apr 2022 | Food prices (broad), consumer sentiment | Small level shift | candidate |
| 7 | Egg price spike | Aug 2022 | Food group 4, all markets | Spike up | candidate |
| 8 | Fuel (BBM) price rise | 3 Sep 2022 | Consumer sentiment (IKK, IEK), food prices (transport cost pass-through) | Drop in sentiment; prices move up | candidate |
| 9 | Rice price surge (El Niño, low harvest) | Aug 2023 – Mar 2024 (peak around Feb 2024) | Food group 1, all markets | Trend up, record highs | candidate |
| 10 | General election | 14 Feb 2024 | Consumer sentiment, currency in circulation | Possible short-term moves | candidate |

## 2. Recurring events (seasonal, should NOT raise alarms on their own)

The system should learn these as normal seasonal patterns. If one of them is **much larger or smaller than
usual**, that is worth a flag.

| Event | Dates 2019–2026 | Indicators expected to react | Expected pattern |
|---|---|---|---|
| Ramadan and Idul Fitri | Idul Fitri: 5 Jun 2019, 24 May 2020, 13 May 2021, 2 May 2022, 22 Apr 2023, 10 Apr 2024, 31 Mar 2025, 20 Mar 2026 | Food prices (especially groups 2, 3, 4, 5, 7, 8), currency in circulation, card and e-money transactions | Prices and cash demand rise in the weeks before, then ease after. **The dates move about 11 days earlier each year**, so a fixed-month seasonal model will miss them. |
| Idul Adha | 11 Aug 2019, 31 Jul 2020, 20 Jul 2021, 10 Jul 2022, 29 Jun 2023, 17 Jun 2024, 6 Jun 2025, 27 May 2026 | Food group 3 (beef) | Price rise in the weeks before |
| Christmas and New Year | Every Dec – Jan | Food prices, card and e-money transactions, currency in circulation | Seasonal rise in December |
| Rainy season | Around Nov – Mar | Food groups 5, 7, 8 (shallot, chili) | Supply issues, prices tend to rise |
| Harvest season | Around Mar – May | Food group 1 (rice) | Prices tend to ease |

The exact holiday dates will go into the holiday table in Phase 1. Check them against the official government holiday list.

## 3. Data events (not real-world changes)

These look like anomalies but come from how the data is collected. The system should **not** flag them.

| Date | What | Indicators |
|---|---|---|
| 1 Jan 2020, 1 Jan 2021, 14 May 2021, 2 May 2022 | Missing week | Traditional market food prices |
| 28 Feb 2022 | Missing week | All food prices |
| Apr – Jul 2020 | No survey data | Consumer survey spending shares |
| Every year end | PIHPS week dates change weekday; weeks 1–3 days apart | All food prices |

## 4. How we will use this list

1. In Phase 4, run the detectors over history and check which of the confirmed events are flagged, and how early.
2. **Target:** most one-off events flagged within 1–2 periods of the start.
3. Recurring events should stay green unless they are unusually large.
