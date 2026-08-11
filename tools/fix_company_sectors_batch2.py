import pandas as pd
from pathlib import Path

MASTER = Path("database/master/company_master.csv")
BACKUP = Path("database/master/company_master_before_batch2.csv")

df = pd.read_csv(MASTER)
df.to_csv(BACKUP, index=False)

SECTOR_MAP = {
    "ASLCPS": ("STEEL", "Steel / Preference Share"),
    "ASLPS": ("STEEL", "Steel / Preference Share"),
    "BECO": ("STEEL", "Steel Products"),
    "CSAP": ("STEEL", "Steel Pipe / Engineering"),
    "DBCI": ("CEMENT", "Cement Manufacturing"),
    "DCL": ("CEMENT", "Cement Manufacturing"),
    "DNCC": ("CEMENT", "Cement Manufacturing"),
    "DSL": ("STEEL", "Steel Products"),
    "FECTC": ("CEMENT", "Cement Manufacturing"),
    "FLYNG": ("CEMENT", "Cement Manufacturing"),
    "GWLC": ("CEMENT", "Cement Manufacturing"),
    "ICL": ("CHEMICAL", "Industrial Chemicals"),
    "ITTEFAQ": ("STEEL", "Steel / Iron"),
    "MSCL": ("STEEL", "Steel Products"),
    "MUGHALC": ("STEEL", "Steel / Preference Share"),
    "SARC": ("CHEMICAL", "Industrial Chemicals"),
}

for symbol, (sector, industry) in SECTOR_MAP.items():
    mask = df["symbol"].astype(str).str.upper().eq(symbol)
    df.loc[mask, "sector"] = sector
    df.loc[mask, "industry"] = industry

df.to_csv(MASTER, index=False)

unknown_count = df[df["sector"].fillna("").str.upper().eq("UNKNOWN")].shape[0]
print("Batch 2 applied")
print("Updated symbols:", len(SECTOR_MAP))
print("Remaining UNKNOWN:", unknown_count)
print("Backup:", BACKUP)