import pandas as pd
from pathlib import Path

MASTER = Path("database/master/company_master.csv")
BACKUP = Path("database/master/company_master_before_batch6b_finance_misc.csv")

df = pd.read_csv(MASTER)
df.to_csv(BACKUP, index=False)

SECTOR_MAP = {
    "AKDHL": ("HOSPITALITY", "Hospitality / Services"),
    "DCR": ("REIT", "Real Estate Investment Trust"),

    "FCIBL": ("FINANCE", "Credit / Investment"),
    "FCSC": ("SECURITIES", "Capital Securities"),
    "JSGCL": ("SECURITIES", "Brokerage / Capital"),

    "FECM": ("MODARABA", "Modaraba"),
    "FPJM": ("MODARABA", "Modaraba"),
    "FPRM": ("MODARABA", "Modaraba"),
    "FTSM": ("MODARABA", "Modaraba"),
    "WASL": ("MODARABA", "Mobility Modaraba"),

    "SEPL": ("PAPER & BOARD", "Security Paper"),
    "SLGL": ("LOGISTICS", "Secure Logistics"),
}

for symbol, (sector, industry) in SECTOR_MAP.items():
    mask = df["symbol"].astype(str).str.upper().eq(symbol)
    df.loc[mask, "sector"] = sector
    df.loc[mask, "industry"] = industry

df.to_csv(MASTER, index=False)

unknown_count = df[df["sector"].fillna("").str.upper().eq("UNKNOWN")].shape[0]
print("Batch 6B Finance/Misc applied")
print("Updated symbols:", len(SECTOR_MAP))
print("Remaining UNKNOWN:", unknown_count)
print("Backup:", BACKUP)