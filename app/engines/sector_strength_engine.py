import pandas as pd


class SectorStrengthEngine:

    def __init__(self, sector_summary: pd.DataFrame):
        self.summary = sector_summary.copy()

    def sector_score(self, sector: str) -> int:

        if self.summary.empty:
            return 50

        sector = str(sector).upper()

        row = self.summary[
            self.summary["sector"].str.upper() == sector
        ]

        if row.empty:
            return 50

        score = float(row.iloc[0]["sector_score"])

        return int(max(min(score, 100), 0))

    def sector_rank(self, sector: str):

        if self.summary.empty:
            return None

        ranked = self.summary.sort_values(
            "sector_score",
            ascending=False
        ).reset_index(drop=True)

        ranked["rank"] = ranked.index + 1

        row = ranked[
            ranked["sector"].str.upper() == sector.upper()
        ]

        if row.empty:
            return None

        return int(row.iloc[0]["rank"])

    def attach_sector_strength(self, df: pd.DataFrame):

        result = df.copy()

        scores = []

        ranks = []

        for _, row in result.iterrows():

            sector = row.get("sector", "UNKNOWN")

            scores.append(
                self.sector_score(sector)
            )

            ranks.append(
                self.sector_rank(sector)
            )

        result["sector_strength_score"] = scores

        result["sector_rank"] = ranks

        return result


def sector_label(score):

    if score >= 85:
        return "VERY STRONG"

    if score >= 70:
        return "STRONG"

    if score >= 55:
        return "GOOD"

    if score >= 40:
        return "WEAK"

    return "VERY WEAK"