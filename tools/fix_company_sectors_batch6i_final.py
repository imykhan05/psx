import pandas as pd
from pathlib import Path

MASTER = Path("database/master/company_master.csv")
BACKUP = Path("database/master/company_master_before_batch6i_final.csv")

df = pd.read_csv(MASTER)
df.to_csv(BACKUP, index=False)

SECTOR_MAP = {
    "PABC": ("ALUMINIUM", "Aluminium Cans"),
    "PAKD": ("TELECOM", "Data Communication"),
    "PAKOXY": ("CHEMICAL", "Industrial Gases"),
    "PAKQATAR": ("INSURANCE", "Life Insurance"),
    "PASM": ("TEXTILE", "Spinning"),
    "PIM": ("MODARABA", "Islamic Modaraba"),
    "PPP": ("PAPER & BOARD", "Paper Products"),
    "PPVC": ("CHEMICAL", "PVC / Chemicals"),
    "PQGTL": ("INSURANCE", "General Insurance"),
    "PSX": ("FINANCE", "Stock Exchange"),
    "PSYL": ("CHEMICAL", "Synthetic Chemicals"),
    "PTL": ("AUTO PARTS", "Tyres"),

    "P01GHS100627": ("GOVT SECURITIES", "1 Year GHS"),
    "P01GHS130527": ("GOVT SECURITIES", "1 Year GHS"),
    "P01GHS150427": ("GOVT SECURITIES", "1 Year GHS"),
    "P01GHS200527": ("GOVT SECURITIES", "1 Year GHS"),
    "P01GHS230627": ("GOVT SECURITIES", "1 Year GHS"),
    "P01GHS290427": ("GOVT SECURITIES", "1 Year GHS"),
    "P01GIS101226": ("GOVT SECURITIES", "1 Year GIS"),
    "P01GIS200826": ("GOVT SECURITIES", "1 Year GIS"),
    "P01GIS210127": ("GOVT SECURITIES", "1 Year GIS"),
    "P01GIS290926": ("GOVT SECURITIES", "1 Year GIS"),
    "P03FRR180629": ("GOVT SECURITIES", "3 Year Fixed Rate"),
    "P03FRR300528": ("GOVT SECURITIES", "3 Year Fixed Rate"),
    "P05FRR211029": ("GOVT SECURITIES", "5 Year Fixed Rate"),
    "P05FRR240129": ("GOVT SECURITIES", "5 Year Fixed Rate"),
}

for symbol, (sector, industry) in SECTOR_MAP.items():
    mask = df["symbol"].astype(str).str.upper().eq(symbol)
    df.loc[mask, "sector"] = sector
    df.loc[mask, "industry"] = industry

df.to_csv(MASTER, index=False)

unknown_count = df[df["sector"].fillna("").str.upper().eq("UNKNOWN")].shape[0]
print("Batch 6I Final applied")
print("Updated symbols:", len(SECTOR_MAP))
print("Remaining UNKNOWN:", unknown_count)
print("Backup:", BACKUP)