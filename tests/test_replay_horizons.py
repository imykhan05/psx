"""
Measurement-integrity tests for the multi-horizon analyzer (ROADMAP.md F1.2).

If forward-return or fill computation is wrong, every win-rate is wrong. These
lock the arithmetic against a hand-computed synthetic case.
"""

import pandas as pd

from app.engines.backtesting.replay_horizon_analyzer_v1 import _add_forward_columns


def _synthetic() -> pd.DataFrame:
    d = pd.DataFrame(
        {
            "symbol": ["X"] * 11,
            "date": [f"{i:02d}JAN2020" for i in range(1, 12)],
            "close": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
            "low": [10, 9, 8, 13, 14, 15, 16, 17, 18, 19, 20],
        }
    )
    d["dp"] = pd.to_datetime(d["date"], format="%d%b%Y", errors="coerce")
    return d.sort_values(["symbol", "dp"]).reset_index(drop=True)


def test_forward_close_horizons():
    r = _add_forward_columns(_synthetic())
    assert r.loc[0, "fwd_close_3"] == 13
    assert r.loc[0, "fwd_close_5"] == 15
    assert r.loc[0, "fwd_close_10"] == 20


def test_forward_min_low_excludes_current_and_looks_forward():
    r = _add_forward_columns(_synthetic())
    # min of lows on days 1..10 after day 0 = min(9,8,13,...,20) = 8
    assert r.loc[0, "fwd_min_low_10"] == 8


def test_no_future_data_is_nan():
    r = _add_forward_columns(_synthetic())
    assert pd.isna(r.loc[10, "fwd_close_3"])  # last row has no forward rows


def test_forward_return_direction():
    r = _add_forward_columns(_synthetic())
    signal_close = r.loc[0, "close"]
    ret_5 = (r.loc[0, "fwd_close_5"] - signal_close) / signal_close * 100
    assert round(ret_5, 2) == 50.0  # 10 -> 15
