import pandas as pd
from pathlib import Path

MASTER = Path("database/master/company_master.csv")
BACKUP = Path("database/master/company_master_before_batch6f_industrial.csv")

df = pd.read_csv(MASTER)
df.to_csv(BACKUP, index=False)

SECTOR_MAP = {
    "ARMG": ("ENGINEERING", "Industrial Manufacturing"),
    "BAPL": ("CHEMICAL", "Industrial Gases"),
    "DADX": ("CONSTRUCTION MATERIALS", "Pipes / Eternit"),
    "DIIL": ("ENGINEERING", "Industrial Manufacturing"),
    "DMC": ("INVESTMENT", "Holding / Corporation"),
    "DSIL": ("ENGINEERING", "Industrial Manufacturing"),
    "EMCO": ("ENGINEERING", "Industrial Manufacturing"),
    "GATI": ("CHEMICAL", "Polyester / Industrial"),
    "HUSI": ("TEXTILE", "Textile / Industrial"),
    "ICCI": ("ENGINEERING", "Industrial Manufacturing"),
    "IDYM": ("TEXTILE", "Dyeing / Textile"),
    "INKL": ("TEXTILE", "Knitwear / Textile"),
    "JVDC": ("PROPERTY", "Real Estate Development"),
    "JVDCPS": ("PROPERTY", "Preference Share"),
    "KHTC": ("TOBACCO", "Tobacco"),
    "KSBP": ("ENGINEERING", "Pumps / Engineering"),
    "LCI": ("CHEMICAL", "Diversified Chemicals"),
    "LEUL": ("LEATHER", "Leather Products"),
    "LOADS": ("AUTO PARTS", "Auto Parts"),
    "PAKL": ("LEATHER", "Leather Products"),
    "SASML": ("SUGAR", "Sugar Mills"),
    "SNAI": ("ENGINEERING", "Industrial Manufacturing"),
    "TCORP": ("HOLDING", "Holding Company"),
    "TCORPCPS": ("HOLDING", "Preference Share"),
    "TCORPR2": ("HOLDING", "Right Share"),
    "TPL": ("HOLDING", "Holding Company"),
    "WAVES": ("CONSUMER DURABLES", "Home Appliances"),
}

for symbol, (sector, industry) in SECTOR_MAP.items():
    mask = df["symbol"].astype(str).str.upper().eq(symbol)
    df.loc[mask, "sector"] = sector
    df.loc[mask, "industry"] = industry

df.to_csv(MASTER, index=False)

unknown_count = df[df["sector"].fillna("").str.upper().eq("UNKNOWN")].shape[0]
print("Batch 6F Industrial applied")
print("Updated symbols:", len(SECTOR_MAP))
print("Remaining UNKNOWN:", unknown_count)
print("Backup:", BACKUP)