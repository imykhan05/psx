from pathlib import Path
from datetime import datetime
import pandas as pd


REPORT_DIR = Path("reports/ai_learning")


def save_learning_report(learning_df: pd.DataFrame, rule_analysis: dict, weight_changes: dict) -> dict:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    csv_path = REPORT_DIR / f"ai_learning_{timestamp}.csv"
    html_path = REPORT_DIR / f"ai_learning_report_{timestamp}.html"

    learning_df.to_csv(csv_path, index=False)

    html = build_html_report(learning_df, rule_analysis, weight_changes)
    html_path.write_text(html, encoding="utf-8")

    return {
        "learning_csv": str(csv_path),
        "learning_html": str(html_path)
    }


def build_html_report(learning_df: pd.DataFrame, rule_analysis: dict, weight_changes: dict) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>PSX AI Learning Report</title>
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
            background: #111827;
            margin-bottom: 30px;
        }}
        th {{
            background: #1e293b;
            color: #facc15;
            padding: 10px;
        }}
        td {{
            padding: 8px;
            border: 1px solid #334155;
            text-align: center;
        }}
        .card {{
            background: #111827;
            border: 1px solid #334155;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 25px;
        }}
        .good {{ color: #22c55e; }}
        .bad {{ color: #ef4444; }}
        .neutral {{ color: #facc15; }}
    </style>
</head>
<body>
    <h1>PSX AI Terminal - Learning Report</h1>

    <div class="card">
        <h2>Feature Learning Summary</h2>
        {learning_df.to_html(index=False)}
    </div>

    <div class="card">
        <h2>Strong Features</h2>
        <p class="good">{rule_analysis.get("strong_features", [])}</p>
    </div>

    <div class="card">
        <h2>Weak Features</h2>
        <p class="bad">{rule_analysis.get("weak_features", [])}</p>
    </div>

    <div class="card">
        <h2>Suggested Weight Changes</h2>
        <pre>{weight_changes}</pre>
    </div>
</body>
</html>
"""