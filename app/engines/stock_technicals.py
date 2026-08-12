"""
Per-stock technical panel — computed on demand for one symbol from the price
history (SQLite daily_prices). Used to enrich the /stock lookup with the full
picture: returns across timeframes, 52-week position, drawdown, RSI, ATR/
volatility, gap, streak, and distance from the moving averages.

All FACTS (measurements of the past). No prediction.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "database" / "psx_terminal.db"


def _r(v, d=2):
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return None
    return round(float(v), d)


def _ret(close: pd.Series, n: int):
    if len(close) <= n or close.iloc[-1 - n] == 0:
        return None
    return (close.iloc[-1] / close.iloc[-1 - n] - 1.0) * 100.0


def compute_technicals(symbol: str) -> dict:
    con = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(
            "SELECT date_parsed, open, high, low, close, volume "
            "FROM daily_prices WHERE symbol = ? ORDER BY date_parsed",
            con, params=[symbol.strip().upper()],
        )
    finally:
        con.close()
    if df.empty:
        return {}

    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["close"])
    if len(df) < 2:
        return {}

    close, high, low, vol = df["close"], df["high"], df["low"], df["volume"]
    last = close.iloc[-1]

    # 52-week window
    win = df.tail(252)
    hi52, lo52 = win["high"].max(), win["low"].min()

    # max drawdown over the last year (peak-to-trough)
    c1y = win["close"]
    dd = (c1y / c1y.cummax() - 1.0).min() * 100.0 if len(c1y) else None

    # RSI(14), SMA-based
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = (100 - 100 / (1 + rs)).iloc[-1] if len(close) > 14 else None

    # ATR(14) and volatility
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().iloc[-1] if len(tr) > 14 else None
    vol20 = (close.pct_change().rolling(20).std().iloc[-1] * 100.0) if len(close) > 20 else None

    # gap today (open vs prev close)
    gap = ((df["open"].iloc[-1] - prev_close.iloc[-1]) / prev_close.iloc[-1] * 100.0
           if prev_close.iloc[-1] else None)

    # up/down streak
    sign = np.sign(close.diff().fillna(0).values)
    streak = 0
    if len(sign):
        s = sign[-1]
        for v in sign[::-1]:
            if v == s and v != 0:
                streak += 1
            else:
                break
        streak = int(streak * (1 if s > 0 else -1))

    ma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else None
    ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None
    avg_vol20 = vol.rolling(20).mean().iloc[-1] if len(vol) >= 20 else None

    return {
        "history_days": int(len(df)),
        "ret_1w": _r(_ret(close, 5)),
        "ret_1m": _r(_ret(close, 21)),
        "ret_3m": _r(_ret(close, 63)),
        "ret_6m": _r(_ret(close, 126)),
        "ret_1y": _r(_ret(close, 252)),
        "high_52w": _r(hi52),
        "low_52w": _r(lo52),
        "pct_from_52w_high": _r((last / hi52 - 1) * 100 if hi52 else None),
        "pct_from_52w_low": _r((last / lo52 - 1) * 100 if lo52 else None),
        "max_drawdown_1y": _r(dd),
        "rsi14": _r(rsi, 1),
        "atr14": _r(atr),
        "atr_pct": _r((atr / last * 100) if atr and last else None),
        "volatility_20d": _r(vol20),
        "gap_today": _r(gap),
        "streak_days": streak,
        "ma50": _r(ma50),
        "ma200": _r(ma200),
        "pct_from_ma50": _r((last / ma50 - 1) * 100 if ma50 else None),
        "pct_from_ma200": _r((last / ma200 - 1) * 100 if ma200 else None),
        "rvol": _r((vol.iloc[-1] / avg_vol20) if avg_vol20 else None),
    }
