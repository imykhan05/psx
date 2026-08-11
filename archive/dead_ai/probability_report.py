from pathlib import Path
from datetime import datetime
import pandas as pd


REPORT_DIR = Path("reports/ai_learning")


def save_probability_report(probability_df: pd.DataFrame) -> dict:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    csv_path = REPORT_DIR / f"probability_report_{timestamp}.csv"
    html_path = REPORT_DIR / f"probability_report_{timestamp}.html"

    probability_df.to_csv(csv_path, index=False)

    html = build_html_report(probability_df)
    html_path.write_text(html, encoding="utf-8")

    return {
        "probability_csv": str(csv_path),
        "probability_html": str(html_path)
    }


def build_html_report(probability_df: pd.DataFrame) -> str:
    top = probability_df.head(20)

    best_feature = top.iloc[0].to_dict() if not top.empty else {}

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>PSX AI Probability Report</title>
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
        .grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 25px;
        }}
        .card {{
            background: #111827;
            border: 1px solid #334155;
            padding: 20px;
            border-radius: 12px;
        }}
        .metric {{
            font-size: 28px;
            font-weight: bold;
            color: #22c55e;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: #111827;
            margin-top: 20px;
        }}
        th {{
            background: #1e293b;
            color: #facc15;
            padding: 10px;
        }}
        td {{
            padding: 9px;
            border: 1px solid #334155;
            text-align: center;
        }}
    </style>
</head>
<body>

    <h1>PSX AI Terminal - Probability Report</h1>

    <div class="grid">
        <div class="card">
            <h2>Best Feature</h2>
            <div class="metric">{best_feature.get("feature", "N/A")}</div>
        </div>

        <div class="card">
            <h2>Profit Probability</h2>
            <div class="metric">{best_feature.get("profit_probability", 0)}%</div>
        </div>

        <div class="card">
            <h2>Target Probability</h2>
            <div class="metric">{best_feature.get("target_probability", 0)}%</div>
        </div>

        <div class="card">
            <h2>Expected Value</h2>
            <div class="metric">{best_feature.get("expected_value", 0)}%</div>
        </div>
    </div>

    <div class="card">
        <h2>Probability Ranking</h2>
        {top.to_html(index=False)}
    </div>

</body>
</html>
"""