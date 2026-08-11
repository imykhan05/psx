from pathlib import Path
from datetime import datetime
import pandas as pd


REPORT_DIR = Path("reports/backtests")


def save_backtest_report(result_df: pd.DataFrame, summary_df: pd.DataFrame) -> dict:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    summary_path = REPORT_DIR / f"backtest_summary_{timestamp}.csv"
    trades_path = REPORT_DIR / f"backtest_trades_{timestamp}.csv"
    html_path = REPORT_DIR / f"backtest_report_{timestamp}.html"

    summary_df.to_csv(summary_path, index=False)
    result_df.to_csv(trades_path, index=False)

    html = build_html_report(summary_df, result_df)
    html_path.write_text(html, encoding="utf-8")

    return {
        "summary_csv": str(summary_path),
        "trades_csv": str(trades_path),
        "html_report": str(html_path),
    }


def build_html_report(summary_df: pd.DataFrame, result_df: pd.DataFrame) -> str:
    top_trades = result_df.sort_values(
        "future_return_3d",
        ascending=False
    ).head(25)

    worst_trades = result_df.sort_values(
        "future_return_3d",
        ascending=True
    ).head(25)

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>PSX AI Backtest Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background: #0f172a;
            color: #e5e7eb;
            padding: 30px;
        }}
        h1, h2 {{
            color: #38bdf8;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
            background: #111827;
        }}
        th {{
            background: #1e293b;
            color: #facc15;
            padding: 10px;
            border: 1px solid #334155;
        }}
        td {{
            padding: 8px;
            border: 1px solid #334155;
            text-align: center;
        }}
        .card {{
            background: #111827;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 25px;
            border: 1px solid #334155;
        }}
    </style>
</head>
<body>
    <h1>PSX AI Terminal - Backtest Report</h1>

    <div class="card">
        <h2>Backtest Summary</h2>
        {summary_df.to_html(index=False)}
    </div>

    <div class="card">
        <h2>Top Winning Trades</h2>
        {top_trades[["symbol", "date", "close", "change_pct", "volume", "future_return_1d", "future_return_3d"]].to_html(index=False)}
    </div>

    <div class="card">
        <h2>Worst Trades</h2>
        {worst_trades[["symbol", "date", "close", "change_pct", "volume", "future_return_1d", "future_return_3d"]].to_html(index=False)}
    </div>
</body>
</html>
"""