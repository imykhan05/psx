import pandas as pd
from pathlib import Path

MASTER = Path("database/master/company_master.csv")
BACKUP = Path("database/master/company_master_before_batch1.csv")

df = pd.read_csv(MASTER)
df.to_csv(BACKUP, index=False)

SECTOR_MAP = {
    "ATIL": ("INSURANCE", "General Insurance"),
    "AMBL": ("MICROFINANCE", "Microfinance Bank"),
    "ASIC": ("INSURANCE", "General Insurance"),
    "CSIL": ("FINANCE", "Investment / Finance"),
    "DEL": ("INSURANCE", "Life Insurance"),
    "EFUG": ("INSURANCE", "General Insurance"),
    "EFUL": ("INSURANCE", "Life Insurance"),
    "IGIHL": ("INSURANCE", "Insurance Holding"),
    "JLICL": ("INSURANCE", "Life Insurance"),
    "PAKRI": ("INSURANCE", "Reinsurance"),
    "PIL": ("INSURANCE", "General Insurance"),
    "PKGI": ("INSURANCE", "General Insurance"),
    "RICL": ("INSURANCE", "General Insurance"),
    "SHNI": ("INSURANCE", "General Insurance"),
    "TPLI": ("INSURANCE", "General Insurance"),
}

for symbol, (sector, industry) in SECTOR_MAP.items():
    mask = df["symbol"].astype(str).str.upper().eq(symbol)
    df.loc[mask, "sector"] = sector
    df.loc[mask, "industry"] = industry

df.to_csv(MASTER, index=False)

unknown_count = df[df["sector"].fillna("").str.upper().eq("UNKNOWN")].shape[0]
print("Batch 1 applied")
print("Updated symbols:", len(SECTOR_MAP))
print("Remaining UNKNOWN:", unknown_count)
print("Backup:", BACKUP)