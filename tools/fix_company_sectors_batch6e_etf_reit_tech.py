import pandas as pd
from pathlib import Path

MASTER = Path("database/master/company_master.csv")
BACKUP = Path("database/master/company_master_before_batch6e_etf_reit_tech.csv")

df = pd.read_csv(MASTER)
df.to_csv(BACKUP, index=False)

SECTOR_MAP = {
    "HMB": ("BANKS", "Commercial Bank"),

    "HBLTETF": ("ETF", "Treasury ETF"),
    "HGFA": ("MUTUAL FUND", "Growth Fund"),
    "NBPGETF": ("ETF", "Pakistan Growth ETF"),
    "UBLPETF": ("ETF", "Pakistan ETF"),

    "GRR": ("PROPERTY", "Real Estate / Residency"),
    "IREIT": ("REIT", "Real Estate Investment Trust"),
    "JSRR": ("REIT", "Rental REIT"),
    "SRR": ("PROPERTY", "Real Estate / Residency"),

    "HUMNL": ("MEDIA", "TV Network / Media"),
    "MDTL": ("MEDIA", "Media"),

    "ITANZ": ("TECHNOLOGY", "IT Services"),
    "STL": ("TECHNOLOGY", "Telecom / IT Services"),

    "CLVL": ("LOGISTICS", "Logistics"),
    "IMAGE": ("TEXTILE", "Fashion / Apparel"),
    "AGLNCPS": ("FERTILIZER", "Preference Share"),
}

for symbol, (sector, industry) in SECTOR_MAP.items():
    mask = df["symbol"].astype(str).str.upper().eq(symbol)
    df.loc[mask, "sector"] = sector
    df.loc[mask, "industry"] = industry

df.to_csv(MASTER, index=False)

unknown_count = df[df["sector"].fillna("").str.upper().eq("UNKNOWN")].shape[0]
print("Batch 6E ETF/REIT/Tech applied")
print("Updated symbols:", len(SECTOR_MAP))
print("Remaining UNKNOWN:", unknown_count)
print("Backup:", BACKUP)