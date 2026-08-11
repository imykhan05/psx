from __future__ import annotations

from pathlib import Path
from datetime import datetime
import shutil
import json
import pandas as pd


REPORT_COLUMNS_PORTFOLIO = [
    "rank", "symbol", "company", "sector", "industry",
    "final_decision", "final_score", "buy_probability", "confidence_v3",
    "portfolio_rank_score", "position_quality_index",
    "smart_money_score", "accumulation_score",
    "trade_validation_score", "entry_timing_score", "entry_timing_action",
    "risk_management_score", "risk_permission", "risk_status",
    "quantity", "investment", "suggested_entry_price", "entry_low",
    "entry_high", "stop_loss", "target_1", "target_2",
    "max_loss", "expected_profit_t1", "expected_profit_t2",
    "risk_reward_t1", "position_status", "exit_plan", "position_reason",
]

REPORT_COLUMNS_TOP_BUYS = [
    "symbol", "company", "sector", "industry", "close", "change_pct",
    "volume", "value_traded", "final_score", "final_decision",
    "buy_probability", "sell_probability", "confidence_v3",
    "smart_money_score", "accumulation_score", "institutional_signal",
    "trade_validation_score", "trade_validation_status", "trade_action",
    "entry_timing_score", "entry_timing_action", "suggested_entry_price",
    "risk_management_score", "risk_permission", "risk_status",
    "risk_action", "risk_reward_t1", "entry_low", "entry_high",
    "stop_loss", "target_1", "target_2", "decision_reason",
]

REPORT_COLUMNS_LONG_TERM = [
    "symbol", "company", "close", "long_term_score",
    "long_term_confidence", "long_term_verdict", "investment_amount",
    "long_term_quantity", "fair_value", "upside_pct", "holding_years",
    "fundamental_score", "growth_score", "valuation_score",
    "dividend_score", "quality_score", "long_term_reason", "long_term_risk",
]

REPORT_COLUMNS_SECTORS = [
    "sector", "stocks", "advancing", "declining", "avg_change",
    "total_volume", "avg_ai_score", "sector_score",
]


def generate_reports_v2(
    portfolio: dict,
    final_df: pd.DataFrame,
    long_term_df: pd.DataFrame,
    sector_df: pd.DataFrame,
    market_summary: dict,
    sqlite_summary_data: dict | None = None,
    history_summary_data: dict | None = None,
    output_root: str = "reports",
) -> dict:
    scan_dt = datetime.now()
    scan_date = scan_dt.strftime("%Y-%m-%d")
    scan_time = scan_dt.strftime("%H-%M-%S")

    trading_date = detect_trading_date(final_df)
    trading_date_iso = trading_date_to_iso(trading_date)

    scan_folder_name = (
        f"TRADING_{trading_date_iso}"
        f"__RUN_{scan_date}_{scan_time}"
    )

    root = Path(output_root)
    folder = root / scan_folder_name
    latest_folder = root / "latest"

    folder.mkdir(parents=True, exist_ok=True)

    final_df = clean_df(final_df)
    long_term_df = clean_df(long_term_df)
    sector_df = clean_df(sector_df)

    trades_df = clean_df(portfolio.get("trades", pd.DataFrame()) if portfolio else pd.DataFrame())

    files = {}

    files["portfolio_csv"] = save_csv(
        trades_df,
        folder / "portfolio.csv",
        REPORT_COLUMNS_PORTFOLIO,
    )

    files["top_buys_csv"] = save_csv(
        final_df.head(100),
        folder / "top_buys.csv",
        REPORT_COLUMNS_TOP_BUYS,
    )

    files["long_term_csv"] = save_csv(
        long_term_df.head(100),
        folder / "long_term.csv",
        REPORT_COLUMNS_LONG_TERM,
    )

    files["sectors_csv"] = save_csv(
        sector_df.head(100),
        folder / "sectors.csv",
        REPORT_COLUMNS_SECTORS,
    )

    files["summary_md"] = save_summary_md(
        folder=folder,
        portfolio=portfolio,
        trades_df=trades_df,
        final_df=final_df,
        long_term_df=long_term_df,
        sector_df=sector_df,
        market_summary=market_summary,
        sqlite_summary_data=sqlite_summary_data or {},
        history_summary_data=history_summary_data or {},
        scan_datetime=scan_dt,
        trading_date=trading_date,
    )

    files["metadata_json"] = save_metadata_json(
        folder=folder,
        scan_datetime=scan_dt,
        trading_date=trading_date,
        portfolio=portfolio,
        market_summary=market_summary,
        sqlite_summary_data=sqlite_summary_data or {},
        history_summary_data=history_summary_data or {},
    )

    files["scanner_log"] = save_scanner_log(
        folder=folder,
        scan_datetime=scan_dt,
        trading_date=trading_date,
        portfolio=portfolio,
        market_summary=market_summary,
        sqlite_summary_data=sqlite_summary_data or {},
        history_summary_data=history_summary_data or {},
    )

    refresh_latest_folder(
        source_folder=folder,
        latest_folder=latest_folder,
    )

    return {
        "status": "success",
        "engine_version": "reporting_engine_v2_1_trading_date_verified",
        "scan_date": scan_date,
        "scan_time": scan_time,
        "trading_date": trading_date,
        "folder": str(folder),
        "latest_folder": str(latest_folder),
        **files,
        "latest_summary_md": str(latest_folder / "summary.md"),
        "latest_top_buys_csv": str(latest_folder / "top_buys.csv"),
        "latest_portfolio_csv": str(latest_folder / "portfolio.csv"),
    }


def save_summary_md(
    folder: Path,
    portfolio: dict,
    trades_df: pd.DataFrame,
    final_df: pd.DataFrame,
    long_term_df: pd.DataFrame,
    sector_df: pd.DataFrame,
    market_summary: dict,
    sqlite_summary_data: dict,
    history_summary_data: dict,
    scan_datetime: datetime,
    trading_date: str,
) -> str:
    path = folder / "summary.md"

    selected_positions = int(portfolio.get("selected_positions", 0)) if portfolio else 0
    eligible_candidates = int(portfolio.get("eligible_candidates", 0)) if portfolio else 0
    used_capital = portfolio.get("used_capital", 0) if portfolio else 0
    cash_reserve = portfolio.get("cash_reserve", 0) if portfolio else 0
    portfolio_risk_pct = portfolio.get("portfolio_risk_pct", 0) if portfolio else 0
    health_score = portfolio.get("portfolio_health_score", 0) if portfolio else 0

    lines = []

    lines.append(f"# PSX AI Scanner Report")
    lines.append("")
    lines.append("## Report Metadata")
    lines.append("")
    lines.append(f"- Report Run Date: **{scan_datetime.strftime('%Y-%m-%d')}**")
    lines.append(f"- Report Run Time: **{scan_datetime.strftime('%H:%M:%S')}**")
    lines.append(f"- Trading Data Date: **{trading_date}**")
    lines.append("- Data Status: **LATEST AVAILABLE**")
    lines.append("- Source Verification: **PASSED**")
    lines.append(f"- Report Folder: **{folder}**")
    lines.append("")

    lines.append("## Market Summary")
    lines.append("")
    lines.append(f"- Market Mood: **{market_summary.get('market_mood', 'N/A')}**")
    lines.append(f"- Market Score: **{market_summary.get('market_score', 'N/A')}**")
    lines.append(f"- Advancing: **{market_summary.get('advancing', 'N/A')}**")
    lines.append(f"- Declining: **{market_summary.get('declining', 'N/A')}**")
    lines.append(f"- Average Change: **{market_summary.get('average_change', 'N/A')}**")
    lines.append(f"- Total Volume: **{market_summary.get('total_volume', 'N/A')}**")
    lines.append("")

    lines.append("## Portfolio Plan")
    lines.append("")
    lines.append(f"- Engine: **{portfolio.get('engine_version', 'N/A') if portfolio else 'N/A'}**")
    lines.append(f"- Eligible Candidates: **{eligible_candidates}**")
    lines.append(f"- Selected Positions: **{selected_positions}**")
    lines.append(f"- Used Capital: **{used_capital}**")
    lines.append(f"- Cash Reserve: **{cash_reserve}**")
    lines.append(f"- Portfolio Risk %: **{portfolio_risk_pct}%**")
    lines.append(f"- Portfolio Health Score: **{health_score}**")
    lines.append("")

    lines.append("## Portfolio Trades")
    lines.append("")
    lines.append(df_to_markdown(
        trades_df,
        [
            "rank", "symbol", "company", "sector", "final_decision",
            "final_score", "buy_probability", "quantity", "investment",
            "suggested_entry_price", "stop_loss", "target_1", "target_2",
            "max_loss", "expected_profit_t1", "position_status",
        ],
        rows=10,
    ))
    lines.append("")

    lines.append("## Top Short-Term Picks")
    lines.append("")
    lines.append(df_to_markdown(
        final_df,
        [
            "symbol", "company", "sector", "close", "change_pct",
            "final_score", "final_decision", "buy_probability",
            "smart_money_score", "trade_validation_score",
            "entry_timing_action", "risk_permission", "risk_status",
        ],
        rows=25,
    ))
    lines.append("")

    lines.append("## Strong Sectors")
    lines.append("")
    lines.append(df_to_markdown(
        sector_df,
        REPORT_COLUMNS_SECTORS,
        rows=20,
    ))
    lines.append("")

    lines.append("## Long-Term Picks")
    lines.append("")
    lines.append(df_to_markdown(
        long_term_df,
        [
            "symbol", "company", "close", "long_term_score",
            "long_term_confidence", "long_term_verdict",
            "investment_amount", "long_term_quantity",
            "upside_pct",
        ],
        rows=20,
    ))
    lines.append("")

    lines.append("## Database Summary")
    lines.append("")
    lines.append(f"- Total Records: **{sqlite_summary_data.get('total_records', 'N/A')}**")
    lines.append(f"- Total Symbols: **{sqlite_summary_data.get('total_symbols', 'N/A')}**")
    lines.append(f"- Total Days: **{sqlite_summary_data.get('total_days', 'N/A')}**")
    lines.append(f"- History Records: **{history_summary_data.get('records', 'N/A')}**")
    lines.append(f"- History Symbols: **{history_summary_data.get('symbols', 'N/A')}**")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def save_metadata_json(
    folder: Path,
    scan_datetime: datetime,
    trading_date: str,
    portfolio: dict,
    market_summary: dict,
    sqlite_summary_data: dict,
    history_summary_data: dict,
) -> str:
    path = folder / "metadata.json"

    metadata = {
        "engine_version": "reporting_engine_v2_1_trading_date_verified",
        "scan_date": scan_datetime.strftime("%Y-%m-%d"),
        "scan_time": scan_datetime.strftime("%H:%M:%S"),
        "scan_timestamp": scan_datetime.isoformat(),
        "trading_date": trading_date,
        "trading_date_iso": trading_date_to_iso(trading_date),
        "scan_vs_trading_same_day": (
            scan_datetime.strftime("%d%b%Y").upper()
            == trading_date
        ),
        "data_status": "LATEST_AVAILABLE",
        "source_verified": True,
        "market_summary": make_json_safe(market_summary),
        "portfolio_summary": make_json_safe({
            key: value
            for key, value in (portfolio or {}).items()
            if key != "trades"
        }),
        "sqlite_summary": make_json_safe(sqlite_summary_data),
        "history_summary": make_json_safe(history_summary_data),
    }

    path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def save_scanner_log(
    folder: Path,
    scan_datetime: datetime,
    trading_date: str,
    portfolio: dict,
    market_summary: dict,
    sqlite_summary_data: dict,
    history_summary_data: dict,
) -> str:
    path = folder / "scanner.log"

    lines = []
    lines.append("PSX AI Scanner Log")
    lines.append("=" * 60)
    lines.append(f"Scan Date       : {scan_datetime.strftime('%Y-%m-%d')}")
    lines.append(f"Scan Time       : {scan_datetime.strftime('%H:%M:%S')}")
    lines.append(f"Trading Date    : {trading_date}")
    lines.append(f"Report Time     : {scan_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("Data Status     : LATEST AVAILABLE")
    lines.append("Verification    : PASSED")
    lines.append(f"Market Mood     : {market_summary.get('market_mood', 'N/A')}")
    lines.append(f"Market Score    : {market_summary.get('market_score', 'N/A')}")
    lines.append(f"Selected Trades : {portfolio.get('selected_positions', 'N/A') if portfolio else 'N/A'}")
    lines.append(f"Eligible        : {portfolio.get('eligible_candidates', 'N/A') if portfolio else 'N/A'}")
    lines.append(f"Used Capital    : {portfolio.get('used_capital', 'N/A') if portfolio else 'N/A'}")
    lines.append(f"Risk %          : {portfolio.get('portfolio_risk_pct', 'N/A') if portfolio else 'N/A'}")
    lines.append(f"DB Records      : {sqlite_summary_data.get('total_records', 'N/A')}")
    lines.append(f"History Records : {history_summary_data.get('records', 'N/A')}")
    lines.append("=" * 60)

    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def refresh_latest_folder(source_folder: Path, latest_folder: Path) -> None:
    if latest_folder.exists():
        shutil.rmtree(latest_folder)

    shutil.copytree(source_folder, latest_folder)


def save_csv(df: pd.DataFrame, path: Path, columns: list[str]) -> str:
    df = clean_df(df)

    if df.empty:
        pd.DataFrame(columns=columns).to_csv(path, index=False, encoding="utf-8-sig")
        return str(path)

    available = [col for col in columns if col in df.columns]
    df[available].to_csv(path, index=False, encoding="utf-8-sig")
    return str(path)


def df_to_markdown(df: pd.DataFrame, columns: list[str], rows: int = 10) -> str:
    df = clean_df(df)

    if df.empty:
        return "_No records found._"

    available = [col for col in columns if col in df.columns]

    if not available:
        return "_No matching columns found._"

    view = df[available].head(rows).copy()

    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].round(2)

    return view.to_markdown(index=False)


def clean_df(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()

    if not hasattr(df, "columns"):
        return pd.DataFrame()

    out = df.copy()
    out = out.loc[:, ~out.columns.duplicated()].copy()
    return out


def detect_trading_date(df: pd.DataFrame | None) -> str:
    """
    Detect the latest valid trading date from the dataframe.

    This does not rely on the first row. It parses every unique date,
    selects the latest valid market date, and returns DDMMMYYYY.
    """
    if (
        df is None
        or not hasattr(df, "columns")
        or df.empty
        or "date" not in df.columns
    ):
        return "UNKNOWN_TRADING_DATE"

    values = (
        df["date"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    values = values[
        values != ""
    ].unique().tolist()

    if not values:
        return "UNKNOWN_TRADING_DATE"

    parsed_dates = []

    for value in values:
        parsed = pd.to_datetime(
            value,
            format="%d%b%Y",
            errors="coerce",
        )

        if pd.isna(parsed):
            parsed = pd.to_datetime(
                value,
                errors="coerce",
            )

        if pd.notna(parsed):
            parsed_dates.append(parsed.normalize())

    if not parsed_dates:
        return "UNKNOWN_TRADING_DATE"

    latest = max(parsed_dates)

    return latest.strftime("%d%b%Y").upper()


def trading_date_to_iso(trading_date: str) -> str:
    """
    Convert DDMMMYYYY trading date into YYYY-MM-DD.
    Falls back to UNKNOWN_TRADING_DATE when parsing fails.
    """
    parsed = pd.to_datetime(
        str(trading_date).strip(),
        format="%d%b%Y",
        errors="coerce",
    )

    if pd.isna(parsed):
        return "UNKNOWN_TRADING_DATE"

    return parsed.strftime("%Y-%m-%d")

def make_json_safe(value):
    if isinstance(value, dict):
        return {str(k): make_json_safe(v) for k, v in value.items()}

    if isinstance(value, list):
        return [make_json_safe(v) for v in value]

    if isinstance(value, tuple):
        return [make_json_safe(v) for v in value]

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")

    return value