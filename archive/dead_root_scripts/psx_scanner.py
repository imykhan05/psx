import argparse
import os
import zipfile
from datetime import datetime
import pandas as pd

FUTURE_MONTHS = [
    "-JAN", "-FEB", "-MAR", "-APR", "-MAY", "-JUN",
    "-JUL", "-AUG", "-SEP", "-OCT", "-NOV", "-DEC"
]

DB_PATH = "data/database/psx_history.csv"


def read_psx_file(file_path):
    with zipfile.ZipFile(file_path) as z:
        filename = z.namelist()[0]
        df = pd.read_csv(
            z.open(filename),
            sep="|",
            header=None,
            names=[
                "date", "symbol", "code", "company",
                "open", "high", "low", "close",
                "volume", "prev_close",
                "x1", "x2", "x3"
            ],
        )

    df = df[["date", "symbol", "code", "company", "open", "high", "low", "close", "volume", "prev_close"]]
    df["symbol"] = df["symbol"].astype(str).str.strip()
    df["company"] = df["company"].astype(str).str.strip()

    for month in FUTURE_MONTHS:
        df = df[~df["symbol"].str.contains(month, na=False)]

    for col in ["open", "high", "low", "close", "volume", "prev_close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["symbol", "close", "volume", "prev_close"])
    df = df[(df["close"] > 0) & (df["prev_close"] > 0) & (df["volume"] > 0)]

    df["date_parsed"] = pd.to_datetime(df["date"], format="%d%b%Y", errors="coerce")
    df = df.dropna(subset=["date_parsed"])

    df["change"] = df["close"] - df["prev_close"]
    df["change_pct"] = (df["change"] / df["prev_close"]) * 100

    range_value = (df["high"] - df["low"]).replace(0, 0.01)
    df["close_position"] = ((df["close"] - df["low"]) / range_value) * 100

    return df


def update_database(today_df):
    os.makedirs("data/database", exist_ok=True)

    if os.path.exists(DB_PATH):
        old = pd.read_csv(DB_PATH)
        old["date_parsed"] = pd.to_datetime(old["date_parsed"], errors="coerce")
        combined = pd.concat([old, today_df], ignore_index=True)
    else:
        combined = today_df.copy()

    combined = combined.drop_duplicates(subset=["date", "symbol"], keep="last")
    combined = combined.sort_values(["symbol", "date_parsed"])
    combined.to_csv(DB_PATH, index=False)

    return combined


def add_indicators(history):
    history = history.sort_values(["symbol", "date_parsed"]).copy()

    history["ema20"] = history.groupby("symbol")["close"].transform(lambda x: x.ewm(span=20, adjust=False).mean())
    history["ema50"] = history.groupby("symbol")["close"].transform(lambda x: x.ewm(span=50, adjust=False).mean())
    history["vol_avg20"] = history.groupby("symbol")["volume"].transform(lambda x: x.rolling(20).mean())

    delta = history.groupby("symbol")["close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.groupby(history["symbol"]).transform(lambda x: x.rolling(14).mean())
    avg_loss = loss.groupby(history["symbol"]).transform(lambda x: x.rolling(14).mean())

    rs = avg_gain / avg_loss.replace(0, 0.01)
    history["rsi14"] = 100 - (100 / (1 + rs))

    return history


def score_stock(row):
    price = row["close"]
    volume = row["volume"]
    change_pct = row["change_pct"]
    close_position = row["close_position"]
    company = str(row["company"]).upper()

    momentum = 0
    if 2 <= change_pct <= 10:
        momentum = min(change_pct * 3, 30)
    elif change_pct > 10:
        momentum = 22
    elif 0 < change_pct < 2:
        momentum = 8

    volume_score = min(volume / 250000 * 20, 20)

    close_score = 20 if close_position >= 85 else 15 if close_position >= 70 else 8 if close_position >= 50 else 0

    liquidity = 15 if volume >= 1_000_000 else 12 if volume >= 500_000 else 8 if volume >= 200_000 else 4 if volume >= 50_000 else 0

    indicator_score = 0
    if pd.notna(row.get("ema20")) and price > row["ema20"]:
        indicator_score += 5
    if pd.notna(row.get("ema50")) and price > row["ema50"]:
        indicator_score += 5
    if pd.notna(row.get("rsi14")):
        if 45 <= row["rsi14"] <= 70:
            indicator_score += 8
        elif row["rsi14"] < 35:
            indicator_score += 5
    if pd.notna(row.get("vol_avg20")) and row["vol_avg20"] > 0 and volume > row["vol_avg20"] * 2:
        indicator_score += 7

    risk_penalty = 0
    risk_notes = []

    if "WINDING" in company:
        risk_penalty += 35
        risk_notes.append("WINDING-UP")
    if "NON-COMPLIANT" in company:
        risk_penalty += 25
        risk_notes.append("NON-COMPLIANT")
    if change_pct > 12:
        risk_penalty += 12
        risk_notes.append("Extended")
    if price < 5:
        risk_penalty += 8
        risk_notes.append("Low Price")
    if volume < 50_000:
        risk_penalty += 10
        risk_notes.append("Low Liquidity")

    score = round(max(min(momentum + volume_score + close_score + liquidity + indicator_score - risk_penalty, 100), 0), 2)

    verdict = "BUY/WATCH" if score >= 80 else "WATCH" if score >= 65 else "AVOID"

    return pd.Series({
        "score": score,
        "verdict": verdict,
        "entry_low": round(price * 0.985, 2),
        "entry_high": round(price * 1.01, 2),
        "stop_loss": round(price * 0.95, 2),
        "target_1": round(price * 1.08, 2),
        "target_2": round(price * 1.14, 2),
        "risk_note": ", ".join(risk_notes) if risk_notes else "Normal"
    })


def badge(verdict):
    if verdict == "BUY/WATCH":
        return '<span class="badge buy">BUY/WATCH</span>'
    if verdict == "WATCH":
        return '<span class="badge watch">WATCH</span>'
    return '<span class="badge avoid">AVOID</span>'


def make_rows(df):
    rows = ""
    for i, r in enumerate(df.itertuples(), 1):
        rsi = "" if pd.isna(getattr(r, "rsi14", None)) else f"{r.rsi14:.1f}"
        ema20 = "" if pd.isna(getattr(r, "ema20", None)) else f"{r.ema20:.2f}"
        rows += f"""
        <tr>
            <td>{i}</td>
            <td><b>{r.symbol}</b></td>
            <td>{r.company}</td>
            <td>{r.close:.2f}</td>
            <td class="{'green' if r.change_pct >= 0 else 'red'}">{r.change_pct:.2f}%</td>
            <td>{int(r.volume):,}</td>
            <td>{rsi}</td>
            <td>{ema20}</td>
            <td><b>{r.score:.2f}</b></td>
            <td>{badge(r.verdict)}</td>
            <td>{r.entry_low} - {r.entry_high}</td>
            <td>{r.stop_loss}</td>
            <td>{r.target_1}</td>
            <td>{r.target_2}</td>
            <td>{r.risk_note}</td>
        </tr>
        """
    return rows


def build_html_report(result, history, capital, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    scan_date = str(result.iloc[0]["date"])
    now = datetime.now().strftime("%H%M")
    html_path = os.path.join(output_dir, f"psx_dashboard_{scan_date}_{now}.html")
    csv_path = os.path.join(output_dir, f"psx_scan_{scan_date}_{now}.csv")

    result.to_csv(csv_path, index=False)

    top20 = result.head(20)
    buy = result[result["score"] >= 80].head(10)
    watch = result[(result["score"] >= 65) & (result["score"] < 80)].head(10)
    avoid = result[result["score"] < 40].head(10)
    best = result.iloc[0]
    total_days = history["date"].nunique()

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>PSX AI Scanner Pro</title>
<style>
body {{
    margin:0;
    font-family:Segoe UI, Arial, sans-serif;
    background:#eef3f8;
    color:#1f2937;
}}
.header {{
    background:linear-gradient(135deg,#002b5c,#005bbb);
    color:white;
    padding:28px 40px;
}}
.header h1 {{margin:0;font-size:32px;}}
.header p {{margin:8px 0 0;opacity:.9;}}
.container {{padding:25px 40px;}}
.cards {{
    display:grid;
    grid-template-columns:repeat(5,1fr);
    gap:16px;
    margin-bottom:24px;
}}
.card {{
    background:white;
    border-radius:16px;
    padding:18px;
    box-shadow:0 8px 22px rgba(0,0,0,.08);
    border-left:6px solid #005bbb;
}}
.label {{color:#6b7280;font-size:13px;}}
.value {{font-size:25px;font-weight:800;margin-top:8px;}}
.best {{
    background:white;
    border-radius:18px;
    padding:24px;
    margin-bottom:24px;
    box-shadow:0 8px 22px rgba(0,0,0,.08);
    border-top:6px solid #16a34a;
}}
.best h2 {{margin-top:0;color:#002b5c;}}
.grid {{
    display:grid;
    grid-template-columns:repeat(4,1fr);
    gap:14px;
}}
.metric {{
    background:#f8fafc;
    padding:14px;
    border-radius:12px;
}}
.metric span {{display:block;color:#6b7280;font-size:13px;}}
.metric b {{font-size:20px;}}
.section {{
    background:white;
    border-radius:18px;
    padding:22px;
    margin-bottom:24px;
    box-shadow:0 8px 22px rgba(0,0,0,.08);
}}
.section h2 {{margin-top:0;color:#002b5c;}}
table {{
    width:100%;
    border-collapse:collapse;
    font-size:13px;
}}
th {{
    background:#002b5c;
    color:white;
    padding:10px;
    text-align:left;
    position:sticky;
    top:0;
}}
td {{
    padding:9px;
    border-bottom:1px solid #e5e7eb;
}}
tr:hover {{background:#f1f5f9;}}
.badge {{
    padding:6px 10px;
    border-radius:20px;
    color:white;
    font-size:11px;
    font-weight:700;
}}
.buy {{background:#16a34a;}}
.watch {{background:#f59e0b;}}
.avoid {{background:#dc2626;}}
.green {{color:#16a34a;font-weight:800;}}
.red {{color:#dc2626;font-weight:800;}}
.footer {{
    text-align:center;
    color:#6b7280;
    padding:25px;
}}
</style>
</head>
<body>

<div class="header">
    <h1>PSX AI Scanner Pro</h1>
    <p>Historical database enabled | Date: {scan_date} | Capital: {capital:,} PKR</p>
</div>

<div class="container">

<div class="cards">
    <div class="card"><div class="label">Stocks Scanned</div><div class="value">{len(result)}</div></div>
    <div class="card"><div class="label">Database Days</div><div class="value">{total_days}</div></div>
    <div class="card"><div class="label">BUY/WATCH</div><div class="value">{len(result[result["score"] >= 80])}</div></div>
    <div class="card"><div class="label">WATCH</div><div class="value">{len(result[(result["score"] >= 65) & (result["score"] < 80)])}</div></div>
    <div class="card"><div class="label">Best Score</div><div class="value">{best["score"]}/100</div></div>
</div>

<div class="best">
    <h2>⭐ Best Stock If Taking Only One Trade</h2>
    <h1>{best["symbol"]} - {best["company"]}</h1>
    <div class="grid">
        <div class="metric"><span>Close</span><b>{best["close"]}</b></div>
        <div class="metric"><span>Score</span><b>{best["score"]}/100</b></div>
        <div class="metric"><span>RSI 14</span><b>{'' if pd.isna(best.get('rsi14')) else round(best.get('rsi14'),1)}</b></div>
        <div class="metric"><span>Entry Zone</span><b>{best["entry_low"]} - {best["entry_high"]}</b></div>
        <div class="metric"><span>Stop Loss</span><b>{best["stop_loss"]}</b></div>
        <div class="metric"><span>Target 1</span><b>{best["target_1"]}</b></div>
        <div class="metric"><span>Target 2</span><b>{best["target_2"]}</b></div>
        <div class="metric"><span>Risk</span><b>{best["risk_note"]}</b></div>
    </div>
</div>

<div class="section">
<h2>🏆 Top 20 Ranked Stocks</h2>
<table>
<tr>
<th>#</th><th>Symbol</th><th>Company</th><th>Close</th><th>Change</th><th>Volume</th><th>RSI</th><th>EMA20</th><th>Score</th><th>Verdict</th><th>Entry</th><th>SL</th><th>T1</th><th>T2</th><th>Risk</th>
</tr>
{make_rows(top20)}
</table>
</div>

<div class="section">
<h2>🟢 BUY/WATCH Stocks</h2>
<table>
<tr>
<th>#</th><th>Symbol</th><th>Company</th><th>Close</th><th>Change</th><th>Volume</th><th>RSI</th><th>EMA20</th><th>Score</th><th>Verdict</th><th>Entry</th><th>SL</th><th>T1</th><th>T2</th><th>Risk</th>
</tr>
{make_rows(buy)}
</table>
</div>

<div class="section">
<h2>🟡 WATCH Stocks</h2>
<table>
<tr>
<th>#</th><th>Symbol</th><th>Company</th><th>Close</th><th>Change</th><th>Volume</th><th>RSI</th><th>EMA20</th><th>Score</th><th>Verdict</th><th>Entry</th><th>SL</th><th>T1</th><th>T2</th><th>Risk</th>
</tr>
{make_rows(watch)}
</table>
</div>

<div class="section">
<h2>🔴 AVOID / Weak Stocks</h2>
<table>
<tr>
<th>#</th><th>Symbol</th><th>Company</th><th>Close</th><th>Change</th><th>Volume</th><th>RSI</th><th>EMA20</th><th>Score</th><th>Verdict</th><th>Entry</th><th>SL</th><th>T1</th><th>T2</th><th>Risk</th>
</tr>
{make_rows(avoid)}
</table>
</div>

</div>
<div class="footer">PSX AI Scanner Pro — Decision support only, not guaranteed profit.</div>
</body>
</html>
"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    return csv_path, html_path


def run_scan(file_path, capital, max_price, output_dir):
    today_df = read_psx_file(file_path)
    history = update_database(today_df)
    history = add_indicators(history)

    latest_date = today_df["date"].iloc[0]
    latest = history[history["date"] == latest_date].copy()
    latest = latest[latest["close"] <= max_price].copy()

    scores = latest.apply(score_stock, axis=1)
    result = pd.concat([latest, scores], axis=1)
    result = result.sort_values(["score", "volume"], ascending=False)

    csv_path, html_path = build_html_report(result, history, capital, output_dir)

    print("\nScan complete.")
    print("Database updated:", DB_PATH)
    print("CSV:", csv_path)
    print("HTML Dashboard:", html_path)
    print("\nOpen this file in browser:")
    print(os.path.abspath(html_path))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--capital", type=int, default=50000)
    parser.add_argument("--max-price", type=float, default=500)
    parser.add_argument("--output", default="reports")

    args = parser.parse_args()
    run_scan(args.file, args.capital, args.max_price, args.output)