from __future__ import annotations

from pathlib import Path
from datetime import datetime
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


def generate_reports_v1(
    portfolio: dict,
    final_df: pd.DataFrame,
    long_term_df: pd.DataFrame,
    sector_df: pd.DataFrame,
    market_summary: dict,
    sqlite_summary_data: dict | None = None,
    history_summary_data: dict | None = None,
    output_root: str = "reports",
) -> dict:
    report_date = detect_report_date(final_df)
    folder = Path(output_root) / report_date
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
        final_df.head(50),
        folder / "top_buys.csv",
        REPORT_COLUMNS_TOP_BUYS,
    )

    files["long_term_csv"] = save_csv(
        long_term_df.head(50),
        folder / "long_term.csv",
        REPORT_COLUMNS_LONG_TERM,
    )

    files["sectors_csv"] = save_csv(
        sector_df.head(50),
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
        report_date=report_date,
    )

    return {
        "status": "success",
        "engine_version": "reporting_engine_v1",
        "report_date": report_date,
        "folder": str(folder),
        **files,
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
    report_date: str,
) -> str:
    path = folder / "summary.md"

    selected_positions = int(portfolio.get("selected_positions", 0)) if portfolio else 0
    eligible_candidates = int(portfolio.get("eligible_candidates", 0)) if portfolio else 0
    used_capital = portfolio.get("used_capital", 0) if portfolio else 0
    cash_reserve = portfolio.get("cash_reserve", 0) if portfolio else 0
    portfolio_risk_pct = portfolio.get("portfolio_risk_pct", 0) if portfolio else 0
    health_score = portfolio.get("portfolio_health_score", 0) if portfolio else 0

    lines = []

    lines.append(f"# PSX AI Scanner Report — {report_date}")
    lines.append("")
    lines.append("## Market Summary")
    lines.append("")
    lines.append(f"- Market Mood: **{market_summary.get('market_mood', 'N/A')}**")
    lines.append(f"- Market Score: **{market_summary.get('market_score', 'N/A')}**")
    lines.append(f"- Advancing: **{market_summary.get('advancing', 'N/A')}**")
    lines.append(f"- Declining: **{market_summary.get('declining', 'N/A')}**")
    lines.append(f"- Average Change: **{market_summary.get('average_change', 'N/A')}**")
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
        rows=20,
    ))
    lines.append("")

    lines.append("## Strong Sectors")
    lines.append("")
    lines.append(df_to_markdown(
        sector_df,
        REPORT_COLUMNS_SECTORS,
        rows=15,
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
        rows=15,
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


def detect_report_date(df: pd.DataFrame | None) -> str:
    if df is not None and hasattr(df, "columns") and "date" in df.columns and not df.empty:
        value = str(df["date"].iloc[0]).strip()
        if value:
            safe = value.replace("/", "-").replace("\\", "-").replace(":", "-")
            return safe

    return datetime.now().strftime("%Y-%m-%d")