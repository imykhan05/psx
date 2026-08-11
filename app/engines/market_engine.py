"""
PSX AI Terminal Pro
Market Intelligence Engine v1.0
"""

from __future__ import annotations

import pandas as pd


class MarketEngine:

    def __init__(self, market_df: pd.DataFrame):
        self.df = market_df.copy()

    # -------------------------------------------------------
    # Basic Market Statistics
    # -------------------------------------------------------

    def total_stocks(self):
        return len(self.df)

    def advancing(self):
        return int((self.df["change_pct"] > 0).sum())

    def declining(self):
        return int((self.df["change_pct"] < 0).sum())

    def unchanged(self):
        return int((self.df["change_pct"] == 0).sum())

    # -------------------------------------------------------
    # Breadth
    # -------------------------------------------------------

    def advance_decline_ratio(self):

        dec = self.declining()

        if dec == 0:
            return 999

        return round(self.advancing() / dec, 2)

    # -------------------------------------------------------
    # Average Change
    # -------------------------------------------------------

    def average_change(self):

        return round(self.df["change_pct"].mean(), 2)

    # -------------------------------------------------------
    # Volume
    # -------------------------------------------------------

    def total_volume(self):

        return int(self.df["volume"].sum())

    # -------------------------------------------------------
    # Top Gainers
    # -------------------------------------------------------

    def top_gainers(self, n=10):

        return self.df.sort_values(
            "change_pct",
            ascending=False
        ).head(n)

    # -------------------------------------------------------
    # Top Losers
    # -------------------------------------------------------

    def top_losers(self, n=10):

        return self.df.sort_values(
            "change_pct"
        ).head(n)

    # -------------------------------------------------------
    # Highest Volume
    # -------------------------------------------------------

    def highest_volume(self, n=10):

        return self.df.sort_values(
            "volume",
            ascending=False
        ).head(n)

    # -------------------------------------------------------
    # Market Mood
    # -------------------------------------------------------

    def market_mood(self):

        ratio = self.advance_decline_ratio()

        avg = self.average_change()

        if ratio >= 2 and avg > 1:
            return "STRONG BULLISH"

        if ratio >= 1.2:
            return "BULLISH"

        if ratio <= 0.6:
            return "STRONG BEARISH"

        if ratio <= 0.9:
            return "BEARISH"

        return "SIDEWAYS"

    # -------------------------------------------------------
    # AI Market Score
    # -------------------------------------------------------

    def ai_market_score(self):

        score = 50

        ratio = self.advance_decline_ratio()

        avg = self.average_change()

        if ratio > 2:
            score += 20

        elif ratio > 1.5:
            score += 10

        elif ratio < 0.7:
            score -= 15

        elif ratio < 1:
            score -= 8

        if avg > 2:
            score += 20

        elif avg > 1:
            score += 10

        elif avg < -2:
            score -= 20

        elif avg < -1:
            score -= 10

        score = max(0, min(score, 100))

        return score

    # -------------------------------------------------------
    # Summary
    # -------------------------------------------------------

    def summary(self):

        return {

            "market_mood":
                self.market_mood(),

            "market_score":
                self.ai_market_score(),

            "total_stocks":
                self.total_stocks(),

            "advancing":
                self.advancing(),

            "declining":
                self.declining(),

            "unchanged":
                self.unchanged(),

            "advance_decline_ratio":
                self.advance_decline_ratio(),

            "average_change":
                self.average_change(),

            "total_volume":
                self.total_volume()

        }