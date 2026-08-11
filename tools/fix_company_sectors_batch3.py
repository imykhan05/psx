import pandas as pd
from pathlib import Path

MASTER = Path("database/master/company_master.csv")
BACKUP = Path("database/master/company_master_before_batch3.csv")

df = pd.read_csv(MASTER)
df.to_csv(BACKUP, index=False)

SECTOR_MAP = {
    "ALTN": ("POWER", "Independent Power Producer"),
    "GEMBCEM": ("POWER", "Clean Energy"),
    "GEMMEL": ("POWER", "Energy / Power"),
    "KOHE": ("POWER", "Independent Power Producer"),
    "KOHP": ("POWER", "Independent Power Producer"),
    "LPL": ("POWER", "Independent Power Producer"),
    "PKGP": ("POWER", "Independent Power Producer"),
    "SEL": ("POWER", "Energy / Power"),
    "TSPL": ("POWER", "Independent Power Producer"),

    "NRL": ("REFINERY", "Oil Refinery"),
    "PRL": ("REFINERY", "Oil Refinery"),

    "OBOY": ("OIL & GAS", "Oil / Energy"),
    "POML": ("OIL & GAS", "Oil Marketing / Energy"),
    "SPSL": ("OIL & GAS", "Petroleum / Energy"),
    "SSOM": ("OIL & GAS", "Oil / Energy"),
    "WAFI": ("OIL & GAS", "Oil Marketing / Energy"),

    "POWERPS": ("CEMENT", "Cement / Preference Share"),
}

for symbol, (sector, industry) in SECTOR_MAP.items():
    mask = df["symbol"].astype(str).str.upper().eq(symbol)
    df.loc[mask, "sector"] = sector
    df.loc[mask, "industry"] = industry

df.to_csv(MASTER, index=False)

unknown_count = df[df["sector"].fillna("").str.upper().eq("UNKNOWN")].shape[0]
print("Batch 3 applied")
print("Updated symbols:", len(SECTOR_MAP))
print("Remaining UNKNOWN:", unknown_count)
print("Backup:", BACKUP)