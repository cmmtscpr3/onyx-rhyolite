# Phase 0 — Scope

What the first version (v1) of the early warning system covers, and why.
Part of [the work plan](../WORKPLAN.md). Progress is tracked in [the checklist](../CHECKLIST.md).

## 1. Goal (recap)

For each indicator, and each new data point, tell analysts:

- **Q1:** Is this value what we expected, given the last period?
- **Q2:** Is this value expected, given a year ago or the last few months?
- Whether the trend, seasonal pattern or volatility has changed.
- Which indicators to watch now, and why.

## 2. What is in scope

**66 indicators: 30 weekly and 36 monthly.** The full list, with dates and counts, is in
[indicator_inventory.csv](indicator_inventory.csv).

| Theme | Source | Series | Frequency | History |
|---|---|---|---|---|
| Food prices | PIHPS (`Dataset/Food Prices/PIHPS/`) | 10 commodity groups × 3 markets = **30** | weekly | Jan 2019 → Sep 2026 (about 400 weeks) |
| Consumer sentiment | `bi_consumer_survey.csv` | 9 headline indices | monthly | Jan 2012 → Aug 2026 |
| Household spending share | `bi_consumer_survey.csv` | 3 headline shares (consumption, saving, loan instalments) | monthly | Jan 2012 → Aug 2026 |
| Card payments | `bi_card_transactions.csv` | 6 (ATM/debit and credit × cards, value, volume) | monthly | Jan 2009 → Jun 2026 |
| E-money | `bi_emoney.csv` | 12 | monthly | 2009 or 2013 → Jun 2026 |
| Money & payments | `bi_payment_system.csv` | 6 | monthly | Jan 2012 → Jul 2026 |

**The 10 food groups** (numbered 1–10, used in the series ids):

| No | Group | Indonesian name |
|---|---|---|
| 1 | Rice | Beras |
| 2 | Chicken | Daging Ayam |
| 3 | Beef | Daging Sapi |
| 4 | Chicken eggs | Telur Ayam |
| 5 | Shallot | Bawang Merah |
| 6 | Garlic | Bawang Putih |
| 7 | Red chili | Cabai Merah |
| 8 | Bird's-eye chili | Cabai Rawit |
| 9 | Cooking oil | Minyak Goreng |
| 10 | Sugar | Gula Pasir |

Each group is tracked in 3 markets: **traditional**, **modern** and **wholesale**.
Series ids look like `pihps.traditional.01_beras`.

## 3. What is out of scope, and why

| Left out | Reason | Revisit when |
|---|---|---|
| ibid car and motor auctions | Your decision. They are listings, not time series. | After v1, if wanted |
| QRIS transactions | Your decision. The data is quarterly and collected by hand. | After v1 |
| OJK deposits (`ojk_dpk.csv`) | Your decision | After v1 |
| SEKI deposits by owner | Only 19 months of history (from Jan 2025) | About 2027, once there are 2–3 years |
| SEKI GDP by expenditure | Quarterly | Not planned (outside monthly/weekly scope) |
| E-commerce GMV | Short history (23–35 months) | About 2027 |
| Currency-to-GDP and currency-to-consumption ratios | Quarterly | Not planned |
| 21 consumer survey series that stopped in 2019–2020 | No new data | Not planned |
| Consumer survey income-bracket splits | Your decision: headlines only | After v1, if needed for drill-down |
| PIHPS sub-items (for example, rice quality grades) | Your decision: groups only | After v1, if needed for drill-down |

## 4. Key facts found while scoping

- **All 66 series have long enough history** for seasonality: the weekly series have 7+ years and the monthly series 14+ years.
- **Food prices have a few empty weeks:**
  - 1 week in all markets: 28 Feb 2022.
  - 4 more in traditional markets: 1 Jan 2020, 1 Jan 2021, 14 May 2021 and 2 May 2022.
  - 14 May 2021 and 2 May 2022 fall on Idul Fitri, so holidays affect data collection as well as prices.
- **The food price week does not fall on the same weekday every year.** It follows the weekday of 1 January (2025 on Wednesday, 2026 on Thursday). This also creates short 1–3 day steps at each year end. Phase 1 must fix this.
- **The consumer survey spending shares have no data for Apr–Jul 2020**, during COVID.
- **BI revises past values**, so we should keep first-reported values where we can.

Details for Phase 1 are in [DATA_SPEC.md](DATA_SPEC.md).

## 5. Direction: which way is "bad"?

Each indicator has a **proposed** bad direction in the inventory (`bad_direction` column). All are marked `to_confirm`.

| Theme | Proposed bad direction |
|---|---|
| Food prices | Up (price rises) |
| Consumer sentiment | Down |
| Spending share | Saving share down, loan instalment share up, consumption share both ways |
| Card payments, e-money activity, RTGS | Down (less activity) |
| E-money float, currency in circulation, demand deposits, narrow money | Both ways (unusual in either direction) |

"Both" means the system flags big moves in either direction.

## 6. Still to do (your part)

- [ ] **Confirm the bad direction** for each indicator in the inventory, and change `to_confirm` to `confirmed`.
- [ ] **Review the known events** in [KNOWN_EVENTS.md](KNOWN_EVENTS.md). Confirm, edit or add events.
- [ ] **End users:** who will read the EWS output, and what tools do they use today (Excel, dashboard, email)?
- [ ] **Current process:** how do analysts spot and handle unusual values today?
- [ ] **Code environment:** set up by you.

## 7. Open questions

- Should the three markets roll up to one "food price" view per group, or stay separate?
- Should big food price moves in markets be compared with each other? For example, is wholesale moving before traditional?
- How often should the monthly report run: once a month after the 15th (when the BI data lands), or every week with the food prices?
