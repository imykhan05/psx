import pandas as pd
from pathlib import Path

MASTER = Path("database/master/company_master.csv")
BACKUP = Path("database/master/company_master_before_batch5a_auto.csv")

df = pd.read_csv(MASTER)
df.to_csv(BACKUP, index=False)

SECTOR_MAP = {
    "AGIL": ("AUTO PARTS", "Auto Parts"),
    "AGTL": ("AUTOMOBILE", "Agricultural Tractors"),
    "ATBA": ("AUTO PARTS", "Batteries"),
    "BCL": ("ENGINEERING", "Foundry / Casting"),
    "BELA": ("AUTOMOBILE", "Automotive"),
    "BWHL": ("AUTO PARTS", "Auto Wheels"),
    "DFML": ("AUTOMOBILE", "Motor Vehicles"),
    "DWAE": ("AUTO PARTS", "Auto Engineering"),
    "GTYR": ("AUTO PARTS", "Tyres"),
    "HINO": ("AUTOMOBILE", "Commercial Vehicles"),
    "MTL": ("AUTOMOBILE", "Agricultural Tractors"),
    "TBL": ("AUTO PARTS", "Batteries"),

    "ARPL": ("CHEMICAL", "Specialty Chemicals"),
    "BERG": ("CHEMICAL", "Paints"),
    "BIFO": ("CHEMICAL", "Industrial Chemicals"),
    "BUXL": ("CHEMICAL", "Paints"),

    "BFBIO": ("PHARMACEUTICAL", "Biotechnology"),
    "LIVEN": ("PHARMACEUTICAL", "Pharmaceuticals"),

    "BGL": ("GLASS & CERAMICS", "Glass Manufacturing"),
    "GHGL": ("GLASS & CERAMICS", "Glass Manufacturing"),
    "GVGL": ("GLASS & CERAMICS", "Glass Manufacturing"),
    "TGL": ("GLASS & CERAMICS", "Glass Manufacturing"),
}

for symbol, (sector, industry) in SECTOR_MAP.items():
    mask = df["symbol"].astype(str).str.upper().eq(symbol)
    df.loc[mask, "sector"] = sector
    df.loc[mask, "industry"] = industry

df.to_csv(MASTER, index=False)

unknown_count = df[df["sector"].fillna("").str.upper().eq("UNKNOWN")].shape[0]
print("Batch 5A Auto/Pharma applied")
print("Updated symbols:", len(SECTOR_MAP))
print("Remaining UNKNOWN:", unknown_count)
print("Backup:", BACKUP)