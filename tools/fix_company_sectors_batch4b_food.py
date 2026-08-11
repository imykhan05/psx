import pandas as pd
from pathlib import Path

MASTER = Path("database/master/company_master.csv")
BACKUP = Path("database/master/company_master_before_batch4b_food.csv")

df = pd.read_csv(MASTER)
df.to_csv(BACKUP, index=False)

SECTOR_MAP = {
    "ADAMS": ("SUGAR", "Sugar Mills"),
    "AGSML": ("SUGAR", "Sugar Mills"),
    "ALNRS": ("SUGAR", "Sugar Mills"),
    "ANSM": ("SUGAR", "Sugar Mills"),
    "CHAS": ("SUGAR", "Sugar Mills"),
    "DWSM": ("SUGAR", "Sugar Mills"),
    "FRSM": ("SUGAR", "Sugar Mills"),
    "HABSM": ("SUGAR", "Sugar Mills"),
    "HWQS": ("SUGAR", "Sugar Mills"),
    "MIRKS": ("SUGAR", "Sugar Mills"),
    "MRNS": ("SUGAR", "Sugar Mills"),
    "NONS": ("SUGAR", "Sugar Mills"),
    "SANSM": ("SUGAR", "Sugar Mills"),
    "SHJS": ("SUGAR", "Sugar Mills"),
    "SHSML": ("SUGAR", "Sugar Mills"),
    "SKRS": ("SUGAR", "Sugar Mills"),

    "BBFL": ("FOOD", "Poultry / Food"),
    "BFAGRO": ("AGRICULTURE", "Dairy / Agro"),
    "BNL": ("FOOD", "Food Processing"),
    "DAAG": ("AGRICULTURE", "Agro"),
    "FFL": ("FOOD", "Dairy / Food"),
    "MFL": ("FOOD", "Rice / Food"),
    "NATF": ("FOOD", "Packaged Foods"),
    "QUICE": ("FOOD", "Food Processing"),
    "WAHDAT": ("FOOD", "Poultry"),

    "BAFS": ("AGRICULTURE", "Seed / Agriculture"),
    "GEMPAPL": ("PACKAGING", "Agro Packaging"),

    # Verify later
    "FANM": ("MODARABA", "Modaraba"),
}

for symbol, (sector, industry) in SECTOR_MAP.items():
    mask = df["symbol"].astype(str).str.upper().eq(symbol)
    df.loc[mask, "sector"] = sector
    df.loc[mask, "industry"] = industry

df.to_csv(MASTER, index=False)

unknown_count = df[df["sector"].fillna("").str.upper().eq("UNKNOWN")].shape[0]
print("Batch 4B Food/Sugar applied")
print("Updated symbols:", len(SECTOR_MAP))
print("Remaining UNKNOWN:", unknown_count)
print("Backup:", BACKUP)