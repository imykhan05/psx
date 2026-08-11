from pathlib import Path
import pandas as pd

SECTOR_MAP_PATH = Path("rules/sector_map.csv")


class SectorEngine:
    def __init__(self, market_df: pd.DataFrame, sector_map_path: Path = SECTOR_MAP_PATH):
        self.df = market_df.copy()
        self.sector_map_path = sector_map_path
        self.sector_map = self.load_sector_map()

    def load_sector_map(self) -> pd.DataFrame:
        if not self.sector_map_path.exists():
            raise FileNotFoundError(f"Sector map not found: {self.sector_map_path}")

        sector_map = pd.read_csv(self.sector_map_path)
        sector_map["symbol"] = sector_map["symbol"].astype(str).str.strip().str.upper()
        sector_map["sector"] = sector_map["sector"].astype(str).str.strip().str.upper()
        return sector_map

    def attach_sectors(self) -> pd.DataFrame:
        df = self.df.copy()
        df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()

        if "sector" in df.columns:
            df["sector"] = df["sector"].fillna("UNKNOWN")
            return df

        df = df.merge(self.sector_map, on="symbol", how="left")

        if "sector_x" in df.columns and "sector_y" in df.columns:
            df["sector"] = df["sector_y"].fillna(df["sector_x"])
            df = df.drop(columns=["sector_x", "sector_y"], errors="ignore")
        elif "sector_y" in df.columns:
            df["sector"] = df["sector_y"]
            df = df.drop(columns=["sector_y"], errors="ignore")
        elif "sector_x" in df.columns:
            df["sector"] = df["sector_x"]
            df = df.drop(columns=["sector_x"], errors="ignore")

        if "sector" not in df.columns:
            df["sector"] = "UNKNOWN"

        df["sector"] = df["sector"].fillna("UNKNOWN")
        return df

    def sector_summary(self) -> pd.DataFrame:
        df = self.attach_sectors()

        if "ai_score" not in df.columns:
            df["ai_score"] = 0

        summary = (
            df.groupby("sector")
            .agg(
                stocks=("symbol", "count"),
                advancing=("change_pct", lambda x: int((x > 0).sum())),
                declining=("change_pct", lambda x: int((x < 0).sum())),
                avg_change=("change_pct", "mean"),
                total_volume=("volume", "sum"),
                avg_ai_score=("ai_score", "mean"),
                max_ai_score=("ai_score", "max"),
            )
            .reset_index()
        )

        summary["advance_ratio"] = summary["advancing"] / summary["declining"].replace(0, 1)
        summary["avg_change"] = summary["avg_change"].round(2)
        summary["avg_ai_score"] = summary["avg_ai_score"].round(2)
        summary["sector_score"] = summary.apply(self.calculate_sector_score, axis=1)

        return summary.sort_values(
            ["sector_score", "avg_ai_score", "total_volume"],
            ascending=False
        )

    def calculate_sector_score(self, row) -> int:
        score = 50

        if row["advance_ratio"] >= 2:
            score += 15
        elif row["advance_ratio"] >= 1.2:
            score += 8
        elif row["advance_ratio"] < 0.7:
            score -= 12

        if row["avg_change"] >= 2:
            score += 15
        elif row["avg_change"] >= 1:
            score += 8
        elif row["avg_change"] <= -1:
            score -= 10

        if row["avg_ai_score"] >= 70:
            score += 15
        elif row["avg_ai_score"] >= 60:
            score += 8

        if row["stocks"] < 3:
            score -= 5

        return int(max(min(score, 100), 0))

    def top_sectors(self, n: int = 10) -> pd.DataFrame:
        return self.sector_summary().head(n)

    def sector_for_stock(self, symbol: str) -> str:
        symbol = str(symbol).strip().upper()
        matched = self.sector_map[self.sector_map["symbol"] == symbol]
        if matched.empty:
            return "UNKNOWN"
        return matched.iloc[0]["sector"]