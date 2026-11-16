"""Indonesia fuel prices from the World Bank Global Fuel Prices Database (Dec 2015 - Apr 2025).

Source: World Bank, Global Fuel Prices Database (E. Akcura), free Excel download:
        https://datacatalog.worldbank.org/search/dataset/0066829/global-fuel-prices-database
Indonesia: official Pertamina monthly price announcements, Province of DKI Jakarta.
Usage:  python build_indonesia_fuel.py <path to Global_Fuel_Prices_Database.xlsx>
Output: indonesia_fuel_prices.csv (long format, one row per fuel per month)
"""
import sys, datetime
import pandas as pd

SRC = sys.argv[1]
# sheet (local currency) -> its USD sheet; Indonesian rows are matched by name
SHEETS = {"Regular Gasoline (below RON 95)": "Reg Gasoline (below RON 95) USD",
          "Premium Gasoline RON95 or above": "Premium Gasoline RON95or ab USD",
          "Diesel": "Diesel USD",
          "Kerosene": "Kerosene USD"}
FUELS = {   # row-label start -> (fuel_id, product, category, subsidised)
    "Indonesia (Pertalite": ("gasoline_ron90_pertalite", "Pertalite (RON 90)", "gasoline", True),
    "Indonesia (Pertamax fuel RON at least 92": ("gasoline_ron92_pertamax", "Pertamax (RON 92)", "gasoline", False),
    "Indonesia (Pertamax fuel RON 98": ("gasoline_ron98_pertamax_turbo", "Pertamax Turbo (RON 98)", "gasoline", False),
    "Indonesia (Pertamax green": ("gasoline_ron95_pertamax_green", "Pertamax Green (RON 95)", "gasoline", False),
    "Indonesia (Dexlit": ("diesel_dexlite", "Dexlite (CN 51)", "diesel", False),
    "Indonesia (Pertamina Dex": ("diesel_pertamina_dex", "Pertamina Dex (CN 53)", "diesel", False),
    "Indonesia (non-subsidized Kerosene": ("kerosene_nonsubsidised", "Kerosene, non-subsidised (depot)", "kerosene", False),
}

def indonesia_rows(sheet):
    raw = pd.read_excel(SRC, sheet_name=sheet, header=None)
    date_cols = [c for c in raw.columns if isinstance(raw.iloc[0, c], datetime.datetime)]
    out = []
    for _, row in raw.iloc[1:].iterrows():
        label = str(row.iloc[0]).strip()
        key = next((k for k in FUELS if label.startswith(k)), None)
        if key is None:
            continue
        s = pd.Series(pd.to_numeric(row[date_cols], errors="coerce").to_numpy(),
                      index=pd.to_datetime([raw.iloc[0, c] for c in date_cols]).to_period("M").to_timestamp())
        # headers use the 3rd of the month in 2017-2023; all dates are set to the 1st (monthly data)
        out.append((key, label, s))
    return out

frames = []
for lcu_sheet, usd_sheet in SHEETS.items():
    usd = {k: s for k, _, s in indonesia_rows(usd_sheet)}
    for key, label, s in indonesia_rows(lcu_sheet):
        fuel_id, product, category, subsidised = FUELS[key]
        frames.append(pd.DataFrame({
            "date": s.index.strftime("%Y-%m-%d"), "fuel_id": fuel_id, "product": product, "category": category,
            "subsidised": subsidised, "price_idr_per_litre": s.to_numpy(),
            "price_usd_per_litre": usd[key].reindex(s.index).to_numpy() if key in usd else None,
            "source_label": label}))
df = pd.concat(frames).dropna(subset=["price_idr_per_litre"]).sort_values(["fuel_id", "date"])
df["price_usd_per_litre"] = df["price_usd_per_litre"].astype(float).round(4)
df.to_csv("indonesia_fuel_prices.csv", index=False)
print(df.groupby("fuel_id").agg(start=("date", "min"), end=("date", "max"), months=("date", "size"),
                                min_idr=("price_idr_per_litre", "min"), max_idr=("price_idr_per_litre", "max")).to_string())
