import pandas as pd
from pathlib import Path

MASTER = Path("database/master/company_master.csv")
BACKUP = Path("database/master/company_master_before_batch6h_remaining_normal.csv")

df = pd.read_csv(MASTER)
df.to_csv(BACKUP, index=False)

SECTOR_MAP = {
    "ARPAK": ("MISCELLANEOUS", "Trading / Services"),
    "BRRG": ("SECURITY SERVICES", "Security Services"),
    "GAMON": ("CONSTRUCTION", "Construction"),
    "GOC": ("CONSUMER GOODS", "Sports / Consumer Goods"),
    "HAEL": ("MISCELLANEOUS", "Trading / Enterprise"),
    "HAFL": ("MISCELLANEOUS", "Trading / Manufacturing"),
    "IML": ("MISCELLANEOUS", "Industrial / Trading"),
    "JDMT": ("TEXTILE", "Textile Mills"),

    "JSMFETF": ("ETF", "Momentum ETF"),
    "JSML": ("SUGAR", "Sugar Mills"),
    "KSTM": ("TEXTILE", "Textile Mills"),
    "MWMP": ("MEDIA", "Cinema / Entertainment"),

    "QTECH": ("TECHNOLOGY", "Data / IT Services"),
    "SGF": ("AUTO PARTS", "Tyres / Footwear"),
    "SLM": ("AUTO PARTS", "Tyres"),
    "SMCPL": ("CONSTRUCTION MATERIALS", "Ready Mix Concrete"),
    "SML": ("SUGAR", "Sugar / Food"),
    "SPL": ("CHEMICAL", "Peroxide / Chemicals"),
    "STCL": ("CERAMICS", "Tiles / Ceramics"),
    "STPL": ("PACKAGING", "Tin Plate / Packaging"),
    "STYLERS": ("TEXTILE", "Apparel / Textile"),
    "TELE": ("TELECOM", "Telecom Services"),
    "TOWL": ("TEXTILE", "Towels / Textile"),
    "TPLT": ("TECHNOLOGY", "Tracking / IoT"),
    "TSBL": ("SECURITIES", "Brokerage"),
    "TSMF": ("MUTUAL FUND", "Mutual Fund"),
    "UDLI": ("FOOD", "Food Distribution"),
    "WAHN": ("CHEMICAL", "Explosives / Chemicals"),
    "WAVESAPP": ("CONSUMER DURABLES", "Home Appliances"),
    "WTL": ("TELECOM", "Telecom Services"),
    "ZAL": ("TECHNOLOGY", "Digital Marketplace"),
    "ZIL": ("CONSUMER GOODS", "Personal Care"),
    "ZUMA": ("MISCELLANEOUS", "Resources / Trading"),
}

for symbol, (sector, industry) in SECTOR_MAP.items():
    mask = df["symbol"].astype(str).str.upper().eq(symbol)
    df.loc[mask, "sector"] = sector
    df.loc[mask, "industry"] = industry

df.to_csv(MASTER, index=False)

unknown_count = df[df["sector"].fillna("").str.upper().eq("UNKNOWN")].shape[0]
print("Batch 6H Remaining Normal applied")
print("Updated symbols:", len(SECTOR_MAP))
print("Remaining UNKNOWN:", unknown_count)
print("Backup:", BACKUP)