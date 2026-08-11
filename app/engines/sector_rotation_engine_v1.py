"""
Sector Rotation Engine v1 — where money has been flowing, by sector.

Your "big players rotate from one group to the next" idea, at the sector level.
It is DESCRIPTIVE (fact): it shows where money HAS flowed (returns + volume +
breadth per sector), and flags sectors whose short-term pace is accelerating vs
fading. It does NOT predict where money will go next (sector momentum is subject
to the same anti-predictive caveat as single-stock momentum — see
docs/EDGE_VALIDATION.md).

Reuses the screener engine's merged frame (per-stock sector + multi-timeframe
returns + sustained volume + MA flags), so no extra data load.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from app.engines.screener_engine_v1 import _merged_frame

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = PROJECT_ROOT / "reports" / "latest" / "sector_rotation.json"

WEEKS_PER_MONTH = 4.3
ACCEL = 0.5  # pct/week threshold to call a sector accelerating / fading


def _num(v, d=2):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return round(float(v), d)


def build_sector_rotation(df: pd.DataFrame | None = None) -> dict:
    if df is None:
        df = _merged_frame()
    d = df.copy()
    d["sector"] = d["sector"].fillna("").replace("", "UNCLASSIFIED")
    for c in ("change_pct", "ret_1w", "ret_1m", "ret_200d", "rvol5", "value_traded",
              "above_ma50", "above_ma200"):
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce")

    total_value = float(d["value_traded"].sum()) if "value_traded" in d else 0.0
    as_of = d["as_of"].dropna().max() if "as_of" in d else None

    rows = []
    for sector, g in d.groupby("sector"):
        n = int(len(g))
        if n < 2:
            continue
        ret_1w = float(g["ret_1w"].median()) if g["ret_1w"].notna().any() else np.nan
        ret_1m = float(g["ret_1m"].median()) if g["ret_1m"].notna().any() else np.nan
        # weekly pace now vs the average weekly pace over the last month
        month_pace = (ret_1m / WEEKS_PER_MONTH) if not np.isnan(ret_1m) else np.nan
        if not np.isnan(ret_1w) and not np.isnan(month_pace):
            trend = ("accelerating" if ret_1w > month_pace + ACCEL
                     else "fading" if ret_1w < month_pace - ACCEL else "steady")
        else:
            trend = "n/a"

        top = (g.sort_values("rvol5", ascending=False, na_position="last")
               .head(3)[["symbol", "change_pct", "ret_1w", "rvol5"]])
        top_stocks = [
            {"symbol": r["symbol"], "change_pct": _num(r["change_pct"]),
             "ret_1w": _num(r["ret_1w"]), "rvol5": _num(r["rvol5"])}
            for _, r in top.iterrows()
        ]

        rows.append({
            "sector": sector,
            "n": n,
            "ret_1d": _num(g["change_pct"].median()),
            "ret_1w": _num(ret_1w),
            "ret_1m": _num(ret_1m),
            "ret_200d": _num(g["ret_200d"].median()),
            "pct_up_today": _num((g["change_pct"] > 0).mean() * 100, 1),
            "pct_above_ma50": _num(g["above_ma50"].mean() * 100, 1) if "above_ma50" in g else None,
            "avg_rvol": _num(g["rvol5"].median()),
            "value_share_pct": _num((float(g["value_traded"].sum()) / total_value * 100)
                                    if total_value else None, 1),
            "trend": trend,
            "top_stocks": top_stocks,
        })

    # rank by this week's return (recent leaders first)
    rows.sort(key=lambda r: (r["ret_1w"] is None, -(r["ret_1w"] or -1e9)))
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    return {
        "engine_version": "sector_rotation_engine_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of_date": as_of,
        "sector_count": len(rows),
        "note": ("Where money HAS flowed, by sector (returns + volume + breadth). "
                 "'accelerating' = this week's pace is above the last month's average "
                 "pace (with rising volume = stronger inflow); 'fading' = the reverse. "
                 "Descriptive, not a forecast — sector momentum does not reliably "
                 "predict next-week returns on PSX."),
        "leaders": rows[:6],
        "laggards": rows[-6:][::-1] if len(rows) > 6 else [],
        "sectors": rows,
    }


def run_sector_rotation() -> dict:
    payload = build_sector_rotation()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


if __name__ == "__main__":
    p = run_sector_rotation()
    print(f"as_of {p['as_of_date']} | {p['sector_count']} sectors")
    print(f"{'sector':22} {'n':>3} {'1w%':>7} {'1m%':>7} {'vol':>5} {'trend':>12}")
    for r in p["sectors"][:15]:
        print(f"{r['sector'][:22]:22} {r['n']:>3} {str(r['ret_1w']):>7} "
              f"{str(r['ret_1m']):>7} {str(r['avg_rvol']):>5} {r['trend']:>12}")
