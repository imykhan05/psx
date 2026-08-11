import pandas as pd
from pathlib import Path

MASTER = Path("database/master/company_master.csv")
OUT = Path("database/master/unknown_companies.csv")

df = pd.read_csv(MASTER)

unknown = df[df["sector"].fillna("").str.upper().eq("UNKNOWN")]

cols = ["symbol", "company", "sector", "industry"]
unknown[cols].sort_values("symbol").to_csv(OUT, index=False)

print(f"UNKNOWN companies: {len(unknown)}")
print(f"Saved: {OUT}")
print(unknown[cols].head(30).to_string(index=False))