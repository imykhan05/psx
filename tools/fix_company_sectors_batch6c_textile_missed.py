import pandas as pd
from pathlib import Path

MASTER = Path("database/master/company_master.csv")
BACKUP = Path("database/master/company_master_before_batch6c_textile_missed.csv")

df = pd.read_csv(MASTER)
df.to_csv(BACKUP, index=False)

SECTOR_MAP = {
    "AHTM": ("TEXTILE", "Textile Mills"),
    "AKGL": ("TEXTILE", "Textile Mills"),
    "BNWM": ("TEXTILE", "Woollen / Textile"),
    "CFL": ("TEXTILE", "Fibres / Textile"),
    "CHBL": ("TEXTILE", "Textile Mills"),
    "CLCPS": ("TEXTILE", "Textile / Preference Share"),
    "CRTM": ("TEXTILE", "Textile Mills"),
    "CTM": ("TEXTILE", "Textile Mills"),
    "FIL": ("TEXTILE", "Textile / Manufacturing"),
    "FML": ("TEXTILE", "Towel / Textile"),
    "FSWL": ("TEXTILE", "Sports Textile"),
    "FZCM": ("TEXTILE", "Cloth / Textile"),
    "IBFL": ("TEXTILE", "Fibres / Textile"),
    "MEHT": ("TEXTILE", "Textile Mills"),
    "PASL": ("TEXTILE", "Textile / Holding"),
    "PRET": ("TEXTILE", "Textile Mills"),
    "SERT": ("TEXTILE", "Textile Mills"),
    "SZTM": ("TEXTILE", "Textile Mills"),
    "ZAHID": ("TEXTILE", "Textile Mills"),
}

for symbol, (sector, industry) in SECTOR_MAP.items():
    mask = df["symbol"].astype(str).str.upper().eq(symbol)
    df.loc[mask, "sector"] = sector
    df.loc[mask, "industry"] = industry

df.to_csv(MASTER, index=False)

unknown_count = df[df["sector"].fillna("").str.upper().eq("UNKNOWN")].shape[0]
print("Batch 6C Textile missed applied")
print("Updated symbols:", len(SECTOR_MAP))
print("Remaining UNKNOWN:", unknown_count)
print("Backup:", BACKUP)