import pandas as pd
from pathlib import Path

MASTER = Path("database/master/company_master.csv")
BACKUP = Path("database/master/company_master_before_batch6g_funds_food.csv")

df = pd.read_csv(MASTER)
df.to_csv(BACKUP, index=False)

SECTOR_MAP = {
    "LSEFSL": ("FINANCE", "Financial Services"),
    "MCBIM": ("ASSET MANAGEMENT", "Investment Management"),
    "OLPL": ("FINANCE", "Financial Services"),
    "SPAC1": ("INVESTMENT", "SPAC / Investment"),

    "MIIETF": ("ETF", "Islamic ETF"),
    "MZNPETF": ("ETF", "Pakistan ETF"),
    "NITGETF": ("ETF", "Pakistan ETF"),

    "LPGL": ("FOOD", "Gelatin / Food Ingredients"),
    "MFFL": ("FOOD", "Fruit Products"),
    "OTSU": ("PHARMACEUTICAL", "Pharmaceuticals"),
    "UBDL": ("FOOD", "Food Brands"),
    "UDPL": ("FOOD", "Food Distribution"),

    "MACFL": ("PACKAGING", "Packaging Films"),
    "NSRM": ("TEXTILE", "Silk / Textile"),
    "OML": ("TEXTILE", "Textile Mills"),
    "ORM": ("RENTAL SERVICES", "Equipment Rental"),
}

for symbol, (sector, industry) in SECTOR_MAP.items():
    mask = df["symbol"].astype(str).str.upper().eq(symbol)
    df.loc[mask, "sector"] = sector
    df.loc[mask, "industry"] = industry

df.to_csv(MASTER, index=False)

unknown_count = df[df["sector"].fillna("").str.upper().eq("UNKNOWN")].shape[0]
print("Batch 6G Funds/Food applied")
print("Updated symbols:", len(SECTOR_MAP))
print("Remaining UNKNOWN:", unknown_count)
print("Backup:", BACKUP)