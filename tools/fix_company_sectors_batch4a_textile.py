import pandas as pd
from pathlib import Path

MASTER = Path("database/master/company_master.csv")
BACKUP = Path("database/master/company_master_before_batch4a_textile.csv")

df = pd.read_csv(MASTER)
df.to_csv(BACKUP, index=False)

SECTOR_MAP = {
    "AATM": ("TEXTILE", "Textile Mills"),
    "ADMM": ("TEXTILE", "Denim / Textile"),
    "AMTEX": ("TEXTILE", "Textile Mills"),
    "ANL": ("TEXTILE", "Textile / Apparel"),
    "ANLNV": ("TEXTILE", "Textile / Preference Share"),
    "ANTM": ("TEXTILE", "Textile Mills"),
    "ARCTM": ("TEXTILE", "Textile Mills"),
    "ARUJ": ("TEXTILE", "Textile Mills"),
    "ASHT": ("TEXTILE", "Textile Mills"),
    "ASTM": ("TEXTILE", "Textile Mills"),
    "CCM": ("TEXTILE", "Cotton / Textile"),
    "DINT": ("TEXTILE", "Textile Mills"),
    "ELCM": ("TEXTILE", "Cotton / Textile"),
    "ELSM": ("TEXTILE", "Spinning"),
    "FASM": ("TEXTILE", "Spinning"),
    "GADT": ("TEXTILE", "Textile Mills"),
    "GSPM": ("TEXTILE", "Spinning"),
    "HIRAT": ("TEXTILE", "Textile Mills"),
    "IDRT": ("TEXTILE", "Textile Mills"),
    "IDSM": ("TEXTILE", "Spinning"),
    "JATM": ("TEXTILE", "Textile Mills"),
    "JKSM": ("TEXTILE", "Spinning"),
    "JUBS": ("TEXTILE", "Spinning"),
    "KML": ("TEXTILE", "Textile Mills"),
    "KOHTM": ("TEXTILE", "Textile Mills"),
    "KOIL": ("TEXTILE", "Textile / Industrial"),
    "KOSM": ("TEXTILE", "Spinning"),
    "MQTM": ("TEXTILE", "Textile Mills"),
    "NAGC": ("TEXTILE", "Cotton / Textile"),
    "NCL": ("TEXTILE", "Textile Mills"),
    "NCML": ("TEXTILE", "Cotton / Textile"),
    "PRWM": ("TEXTILE", "Weaving"),
    "QUET": ("TEXTILE", "Textile Mills"),
    "REDCO": ("TEXTILE", "Textile Mills"),
    "REWM": ("TEXTILE", "Weaving"),
    "RUBY": ("TEXTILE", "Textile Mills"),
    "RUPL": ("TEXTILE", "Polyester / Textile"),
    "SAIF": ("TEXTILE", "Textile Mills"),
    "SHCM": ("TEXTILE", "Cotton / Textile"),
    "SHDT": ("TEXTILE", "Textile Mills"),
    "SLYT": ("TEXTILE", "Textile Mills"),
    "SSML": ("TEXTILE", "Spinning"),
    "STJT": ("TEXTILE", "Textile Mills"),
    "STML": ("TEXTILE", "Textile Mills"),
    "SURC": ("TEXTILE", "Cotton / Textile"),
    "SUTM": ("TEXTILE", "Textile Mills"),
    "TATM": ("TEXTILE", "Textile Mills"),
    "YOUW": ("TEXTILE", "Weaving"),
    "ZTL": ("TEXTILE", "Textile Mills"),
}

for symbol, (sector, industry) in SECTOR_MAP.items():
    mask = df["symbol"].astype(str).str.upper().eq(symbol)
    df.loc[mask, "sector"] = sector
    df.loc[mask, "industry"] = industry

df.to_csv(MASTER, index=False)

unknown_count = df[df["sector"].fillna("").str.upper().eq("UNKNOWN")].shape[0]
print("Batch 4A Textile applied")
print("Updated symbols:", len(SECTOR_MAP))
print("Remaining UNKNOWN:", unknown_count)
print("Backup:", BACKUP)