"""
Seasonality Engine v1 — day-of-week and month-of-year patterns on PSX.

From the full price history: the average return by weekday (Mon-Fri) and by
calendar month, across all stocks and all years, with sample sizes and % of
periods positive.

HONEST: these are historical AVERAGES with tiny effect sizes and no guarantee
they repeat. A "good" month on average still has plenty of bad ones. It is
context, not a trading rule.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "database" / "psx_terminal.db"
OUT_PATH = PROJECT_ROOT / "reports" / "latest" / "seasonality.json"

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MIN_PRICE = 2.0


def _load() -> pd.DataFrame:
    con = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query("SELECT date_parsed, symbol, close FROM daily_prices", con)
    finally:
        con.close()
    df["date_parsed"] = pd.to_datetime(df["date_parsed"], format="ISO8601", errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["date_parsed", "close"])
    df = df[df["close"] >= MIN_PRICE].sort_values(["symbol", "date_parsed"])
    # skip debt paper (PIB/Sukuk 'P0...', TFCs)
    sym = df["symbol"].astype(str)
    return df[~(sym.str.match(r"^P\d") | sym.str.contains("TFC", na=False))]


def build_seasonality() -> dict:
    df = _load()
    df["ret1"] = df.groupby("symbol")["close"].transform(lambda s: s / s.shift(1) - 1) * 100.0

    # weekday effect (from daily returns)
    df["wd"] = df["date_parsed"].dt.dayofweek
    weekday = []
    for i, name in enumerate(WEEKDAYS):
        r = df.loc[df["wd"] == i, "ret1"].dropna()
        if len(r):
            weekday.append({"day": name, "avg_return": round(float(r.mean()), 3),
                            "pct_positive": round(float((r > 0).mean() * 100), 1),
                            "n": int(len(r))})

    # month effect (from actual monthly returns per stock)
    df["ym"] = df["date_parsed"].dt.to_period("M")
    m = df.groupby(["symbol", "ym"])["close"].agg(["first", "last"])
    m["ret"] = (m["last"] / m["first"] - 1.0) * 100.0
    m["month"] = m.index.get_level_values("ym").month
    month = []
    for i in range(1, 13):
        r = m.loc[m["month"] == i, "ret"].dropna()
        if len(r):
            month.append({"month": MONTHS[i - 1], "avg_return": round(float(r.mean()), 2),
                          "pct_positive": round(float((r > 0).mean() * 100), 1),
                          "n": int(len(r))})

    def _best(lst, key="avg_return"):
        return max(lst, key=lambda x: x[key]) if lst else None

    def _worst(lst, key="avg_return"):
        return min(lst, key=lambda x: x[key]) if lst else None

    return {
        "engine_version": "seasonality_engine_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "history_from": str(df["date_parsed"].min().date()),
        "history_to": str(df["date_parsed"].max().date()),
        "weekday": weekday,
        "month": month,
        "best_weekday": _best(weekday),
        "worst_weekday": _worst(weekday),
        "best_month": _best(month),
        "worst_month": _worst(month),
        "note": ("Historical averages across all stocks/years. Effect sizes are "
                 "small and NOT a guarantee — a 'good' month still has many bad "
                 "days. Context, not a trading rule."),
    }


def run_seasonality_engine() -> dict:
    payload = build_seasonality()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


if __name__ == "__main__":
    p = run_seasonality_engine()
    print(f"history {p['history_from']} -> {p['history_to']}")
    print("weekday avg daily return %:")
    for w in p["weekday"]:
        print(f"  {w['day']:10} {w['avg_return']:+.3f}%  (+ve {w['pct_positive']}%)")
    print("month avg monthly return %:")
    for mo in p["month"]:
        print(f"  {mo['month']:4} {mo['avg_return']:+.2f}%  (+ve {mo['pct_positive']}%)")
