import pandas as pd
from pathlib import Path

MASTER = Path("database/master/company_master.csv")
BACKUP = Path("database/master/company_master_before_batch6d_food_auto_misc.csv")

df = pd.read_csv(MASTER)
df.to_csv(BACKUP, index=False)

SECTOR_MAP = {
    "FCEPL": ("FOOD", "Dairy / Food"),
    "GDL": ("FOOD", "Dairy"),
    "HRPL": ("FOOD", "Rice / Food"),

    "HCAR": ("AUTOMOBILE", "Passenger Cars"),
    "HTL": ("OIL & GAS", "Lubricants"),

    "FCL": ("CABLES", "Electric Cables"),
    "PCAL": ("CABLES", "Electric Cables"),

    "FRCL": ("CERAMICS", "Ceramics"),
    "KCL": ("CERAMICS", "Ceramics"),

    "FTMM": ("ENGINEERING", "Manufacturing"),
    "GFIL": ("TEXTILE", "Fabrics / Textile"),
    "TREET": ("HOLDING", "Diversified Holding"),

    "GCWL": ("CHEMICAL", "Industrial Chemicals"),
    "NICL": ("CHEMICAL", "Industrial Chemicals"),
}

for symbol, (sector, industry) in SECTOR_MAP.items():
    mask = df["symbol"].astype(str).str.upper().eq(symbol)
    df.loc[mask, "sector"] = sector
    df.loc[mask, "industry"] = industry

df.to_csv(MASTER, index=False)

unknown_count = df[df["sector"].fillna("").str.upper().eq("UNKNOWN")].shape[0]
print("Batch 6D Food/Auto/Misc applied")
print("Updated symbols:", len(SECTOR_MAP))
print("Remaining UNKNOWN:", unknown_count)
print("Backup:", BACKUP)