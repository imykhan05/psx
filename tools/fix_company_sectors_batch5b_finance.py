import pandas as pd
from pathlib import Path

MASTER = Path("database/master/company_master.csv")
BACKUP = Path("database/master/company_master_before_batch5b_finance.csv")

df = pd.read_csv(MASTER)
df.to_csv(BACKUP, index=False)

SECTOR_MAP = {
    "BML": ("BANKS", "Commercial Bank"),
    "BOK": ("BANKS", "Commercial Bank"),
    "ESBL": ("BANKS", "Commercial Bank"),
    "ICIBL": ("BANKS", "Investment Bank"),
    "SBL": ("BANKS", "Commercial Bank"),
    "SCBPL": ("BANKS", "Commercial Bank"),
    "SIBL": ("FINANCE", "Investment Bank"),

    "CENI": ("INSURANCE", "General Insurance"),
    "EWIC": ("INSURANCE", "General Insurance"),
    "IGIL": ("INSURANCE", "Life Insurance"),
    "JGICL": ("INSURANCE", "General Insurance"),
    "TPLL": ("INSURANCE", "Life Insurance"),
    "UNIC": ("INSURANCE", "General Insurance"),
    "UVIC": ("INSURANCE", "General Insurance"),

    "BFMOD": ("MODARABA", "Modaraba"),
    "FEM": ("MODARABA", "Modaraba"),
    "FHAM": ("MODARABA", "Modaraba"),
    "FIMM": ("MODARABA", "Modaraba"),
    "OLPM": ("MODARABA", "Modaraba"),
    "SINDM": ("MODARABA", "Modaraba"),
    "UCAPM": ("MODARABA", "Modaraba"),

    "GRYL": ("LEASING", "Leasing"),
    "PGLC": ("LEASING", "Leasing"),

    "HIFA": ("MUTUAL FUND", "Investment Fund"),
    "JSGBETF": ("ETF", "Banking ETF"),
    "JSIL": ("ASSET MANAGEMENT", "Investment Management"),
    "ACIETF": ("ETF", "Consumer ETF"),
}

for symbol, (sector, industry) in SECTOR_MAP.items():
    mask = df["symbol"].astype(str).str.upper().eq(symbol)
    df.loc[mask, "sector"] = sector
    df.loc[mask, "industry"] = industry

df.to_csv(MASTER, index=False)

unknown_count = df[df["sector"].fillna("").str.upper().eq("UNKNOWN")].shape[0]
print("Batch 5B Finance applied")
print("Updated symbols:", len(SECTOR_MAP))
print("Remaining UNKNOWN:", unknown_count)
print("Backup:", BACKUP)