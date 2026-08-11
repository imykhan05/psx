import pandas as pd
from pathlib import Path

MASTER = Path("database/master/company_master.csv")
BACKUP = Path("database/master/company_master_before_batch6a_packaging.csv")

df = pd.read_csv(MASTER)
df.to_csv(BACKUP, index=False)

SECTOR_MAP = {
    "BPL": ("OIL & GAS", "LPG Marketing"),
    "CNERGY": ("REFINERY", "Oil Refinery"),

    "CPPL": ("PACKAGING", "Paper / Packaging"),
    "ECOP": ("PACKAGING", "Plastic Packaging"),
    "IPAK": ("PACKAGING", "Packaging"),
    "TRIPF": ("PACKAGING", "Packaging Films"),

    "DYNO": ("CHEMICAL", "Industrial Chemicals"),
    "NRSL": ("CHEMICAL", "Resins / Chemicals"),
    "EPCLPS": ("CHEMICAL", "Polymer / Preference Share"),

    "ENGROH": ("HOLDING", "Holding Company"),
    "PIAHCLA": ("HOLDING", "Holding Company"),

    "DLL": ("INVESTMENT", "Holding / Investment"),
    "FCEL": ("FINANCE", "Equity / Finance"),
    "FDPL": ("PROPERTY", "Property / Real Estate"),
    "FNEL": ("FINANCE", "Equity / Finance"),
}

for symbol, (sector, industry) in SECTOR_MAP.items():
    mask = df["symbol"].astype(str).str.upper().eq(symbol)
    df.loc[mask, "sector"] = sector
    df.loc[mask, "industry"] = industry

df.to_csv(MASTER, index=False)

unknown_count = df[df["sector"].fillna("").str.upper().eq("UNKNOWN")].shape[0]
print("Batch 6A Packaging/Holding applied")
print("Updated symbols:", len(SECTOR_MAP))
print("Remaining UNKNOWN:", unknown_count)
print("Backup:", BACKUP)