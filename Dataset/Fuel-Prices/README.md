# Indonesia fuel prices

`indonesia_fuel_prices.csv`: monthly retail fuel prices in Indonesia, Dec 2015 to Apr 2025, extracted from the
World Bank **Global Fuel Prices Database** (free download:
https://datacatalog.worldbank.org/search/dataset/0066829/global-fuel-prices-database).

Prices are Pertamina's official monthly price announcements for the **Province of DKI Jakarta**, as collected by
the database author (https://www.pertamina.com/id/news-room/announcement).

## Columns

| column | meaning |
|---|---|
| `date` | month (1st of the month) |
| `fuel_id` | short id, see below |
| `product` | Pertamina product name |
| `category` | gasoline, diesel or kerosene |
| `subsidised` | True for government-set subsidised fuel (Pertalite) |
| `price_idr_per_litre` | price in rupiah per litre |
| `price_usd_per_litre` | price in USD per litre, as converted in the source (blank where the source has none) |
| `source_label` | the row label in the source workbook |

## Fuels

| fuel_id | product | months |
|---|---|---|
| `gasoline_ron90_pertalite` | Pertalite (RON 90), subsidised | Mar 2016 - Dec 2024 |
| `gasoline_ron92_pertamax` | Pertamax (RON 92) | Dec 2015 - Apr 2025 |
| `gasoline_ron95_pertamax_green` | Pertamax Green (RON 95) | Sep 2023 - Apr 2025 |
| `gasoline_ron98_pertamax_turbo` | Pertamax Turbo (RON 98) | Dec 2015 - Apr 2025 |
| `diesel_dexlite` | Dexlite (cetane 51) | Aug 2016 - Apr 2025 |
| `diesel_pertamina_dex` | Pertamina Dex (cetane 53) | Dec 2015 - Apr 2025 |
| `kerosene_nonsubsidised` | Kerosene, non-subsidised (depot) | Mar 2018 - Dec 2023 |

## Notes

- **Subsidised diesel (Solar / Biosolar) is not in the source database.** Only the non-subsidised diesels are.
- No months are missing inside each fuel's range.
- The source workbook dates most 2017-2023 columns on the 3rd of the month; all dates are set to the 1st here.
- USD prices are missing for April 2025 (all fuels) and for Pertamax Green (no USD row in the source).
- Rebuild with: `python build_indonesia_fuel.py <path to Global_Fuel_Prices_Database.xlsx>`
