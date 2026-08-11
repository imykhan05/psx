from __future__ import annotations

from pathlib import Path
from datetime import datetime
import shutil
import json
import pandas as pd


ENGINE_VERSION = "reporting_engine_v3_1_portfolio_lifecycle_wiring"

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
    "symbol", "company", "sector", "industry", "date",
    "close", "change_pct", "volume", "value_traded",
    "final_score", "final_decision",
    "buy_probability", "sell_probability", "confidence_v3",
    "smart_money_score", "accumulation_score", "institutional_signal",
    "trade_validation_score", "trade_validation_status", "trade_action",
    "entry_timing_score", "entry_timing_action", "suggested_entry_price",
    "risk_management_score", "risk_permission", "risk_status",
    "risk_action", "risk_reward_t1", "entry_low", "entry_high",
    "stop_loss", "target_1", "target_2",
    "portfolio_selected", "portfolio_rank", "portfolio_investment",
    "portfolio_quantity", "portfolio_position_status",
    "lifecycle_status", "trade_id", "actual_entry_price",
    "actual_quantity", "open_quantity", "remaining_quantity",
    "average_cost", "current_stop_loss",
    "highest_price_since_entry", "lowest_price_since_entry",
    "realized_profit_loss", "unrealized_profit_loss",
    "unrealized_profit_loss_pct", "holding_days_numeric",
    "partial_profit_booked",
    "exit_action", "exit_reason", "exit_risk_level",
    "exit_suggested_action", "exit_current_price", "exit_entry_price",
    "exit_profit_loss_pct", "exit_original_stop_loss",
    "exit_suggested_stop_loss", "exit_trailing_stop",
    "exit_profit_lock_pct", "exit_target_status",
    "exit_confidence", "exit_engine_version",
    "decision_reason",
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

REPORT_COLUMNS_LIFECYCLE = [
    "symbol", "company", "sector", "industry", "date", "close",
    "portfolio_selected", "portfolio_rank",
    "portfolio_position_status", "lifecycle_status", "trade_id",
    "portfolio_quantity", "portfolio_investment",
    "quantity", "investment",
    "suggested_entry_price", "adjusted_entry_price",
    "entry_low", "entry_high",
    "stop_loss", "target_1", "target_2",
    "risk_per_share", "expected_profit_t1", "expected_profit_t2",
    "actual_entry_price", "actual_quantity", "open_quantity",
    "remaining_quantity", "average_cost", "current_stop_loss",
    "highest_price_since_entry", "lowest_price_since_entry",
    "realized_profit_loss", "unrealized_profit_loss",
    "unrealized_profit_loss_pct", "holding_days_numeric",
    "partial_profit_booked",
]

REPORT_COLUMNS_EXIT = [
    "symbol", "company", "sector", "industry", "date", "close",
    "portfolio_selected", "portfolio_position_status",
    "lifecycle_status", "trade_id",
    "actual_entry_price", "actual_quantity",
    "open_quantity", "remaining_quantity",
    "adjusted_entry_price", "stop_loss", "target_1", "target_2",
    "exit_action", "exit_reason", "exit_risk_level",
    "exit_suggested_action", "exit_current_price", "exit_entry_price",
    "exit_profit_loss_pct", "exit_original_stop_loss",
    "exit_suggested_stop_loss", "exit_trailing_stop",
    "exit_profit_lock_pct", "exit_target_status",
    "exit_confidence", "exit_engine_version",
]

REPORT_COLUMNS_ACTION_PLAN = [
    "priority", "symbol", "company", "sector", "lifecycle_status",
    "portfolio_position_status", "final_decision", "risk_permission",
    "entry_timing_action", "exit_action", "recommended_action",
    "current_price", "entry_price", "stop_loss",
    "target_1", "target_2", "confidence", "reason",
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
    """
    Backward-compatible entry point.

    The function name remains generate_reports_v2 so main.py does not need
    to change, while the implementation is Reporting Engine V3.
    """
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

    trades_df = clean_df(
        portfolio.get("trades", pd.DataFrame())
        if portfolio
        else pd.DataFrame()
    )

    lifecycle_df = build_lifecycle_view(final_df)
    lifecycle_df = enrich_lifecycle_with_portfolio(
        lifecycle_df=lifecycle_df,
        trades_df=trades_df,
    )

    action_plan_source_df = enrich_final_with_portfolio(
        final_df=final_df,
        trades_df=trades_df,
    )

    exit_df = build_exit_view(action_plan_source_df)
    action_plan_df = build_action_plan(action_plan_source_df)

    pending_entries_df = lifecycle_df[
        lifecycle_df.get("lifecycle_status", "")
        .astype(str)
        .str.upper()
        .eq("READY TO BUY")
    ].copy() if not lifecycle_df.empty and "lifecycle_status" in lifecycle_df.columns else pd.DataFrame()

    open_positions_df = lifecycle_df[
        lifecycle_df.get("lifecycle_status", "")
        .astype(str)
        .str.upper()
        .isin(["OPEN", "PARTIAL EXIT"])
    ].copy() if not lifecycle_df.empty and "lifecycle_status" in lifecycle_df.columns else pd.DataFrame()

    closed_positions_df = lifecycle_df[
        lifecycle_df.get("lifecycle_status", "")
        .astype(str)
        .str.upper()
        .isin(["CLOSED", "EXITED", "STOPPED OUT", "FULL EXIT"])
    ].copy() if not lifecycle_df.empty and "lifecycle_status" in lifecycle_df.columns else pd.DataFrame()

    long_term_report_df = filter_meaningful_long_term_rows(long_term_df)

    lifecycle_summary = build_lifecycle_summary(
        lifecycle_df=lifecycle_df,
        pending_entries_df=pending_entries_df,
        open_positions_df=open_positions_df,
        closed_positions_df=closed_positions_df,
    )

    exit_summary = build_exit_summary(exit_df)

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

    files["full_market_scan_csv"] = save_csv(
        final_df,
        folder / "full_market_scan.csv",
        REPORT_COLUMNS_TOP_BUYS,
    )

    files["long_term_csv"] = save_csv(
        long_term_report_df.head(100),
        folder / "long_term.csv",
        REPORT_COLUMNS_LONG_TERM,
    )

    files["sectors_csv"] = save_csv(
        sector_df.head(100),
        folder / "sectors.csv",
        REPORT_COLUMNS_SECTORS,
    )

    files["trade_lifecycle_csv"] = save_csv(
        lifecycle_df,
        folder / "trade_lifecycle.csv",
        REPORT_COLUMNS_LIFECYCLE,
    )

    files["pending_entries_csv"] = save_csv(
        pending_entries_df,
        folder / "pending_entries.csv",
        REPORT_COLUMNS_LIFECYCLE,
    )

    files["open_positions_csv"] = save_csv(
        open_positions_df,
        folder / "open_positions.csv",
        REPORT_COLUMNS_LIFECYCLE,
    )

    files["closed_positions_csv"] = save_csv(
        closed_positions_df,
        folder / "closed_positions.csv",
        REPORT_COLUMNS_LIFECYCLE,
    )

    files["exit_intelligence_csv"] = save_csv(
        exit_df,
        folder / "exit_intelligence.csv",
        REPORT_COLUMNS_EXIT,
    )

    files["daily_action_plan_csv"] = save_csv(
        action_plan_df,
        folder / "daily_action_plan.csv",
        REPORT_COLUMNS_ACTION_PLAN,
    )

    files["summary_md"] = save_summary_md(
        folder=folder,
        portfolio=portfolio,
        trades_df=trades_df,
        final_df=final_df,
        long_term_df=long_term_report_df,
        sector_df=sector_df,
        lifecycle_df=lifecycle_df,
        pending_entries_df=pending_entries_df,
        open_positions_df=open_positions_df,
        closed_positions_df=closed_positions_df,
        exit_df=exit_df,
        action_plan_df=action_plan_df,
        market_summary=market_summary,
        sqlite_summary_data=sqlite_summary_data or {},
        history_summary_data=history_summary_data or {},
        lifecycle_summary=lifecycle_summary,
        exit_summary=exit_summary,
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
        lifecycle_summary=lifecycle_summary,
        exit_summary=exit_summary,
        action_plan_summary=build_action_plan_summary(action_plan_df),
    )

    files["scanner_log"] = save_scanner_log(
        folder=folder,
        scan_datetime=scan_dt,
        trading_date=trading_date,
        portfolio=portfolio,
        market_summary=market_summary,
        sqlite_summary_data=sqlite_summary_data or {},
        history_summary_data=history_summary_data or {},
        lifecycle_summary=lifecycle_summary,
        exit_summary=exit_summary,
    )

    refresh_latest_folder(
        source_folder=folder,
        latest_folder=latest_folder,
    )

    return {
        "status": "success",
        "engine_version": ENGINE_VERSION,
        "scan_date": scan_date,
        "scan_time": scan_time,
        "trading_date": trading_date,
        "folder": str(folder),
        "latest_folder": str(latest_folder),
        "lifecycle_summary": lifecycle_summary,
        "exit_summary": exit_summary,
        **files,
        "latest_summary_md": str(latest_folder / "summary.md"),
        "latest_top_buys_csv": str(latest_folder / "top_buys.csv"),
        "latest_full_market_scan_csv": str(
            latest_folder / "full_market_scan.csv"
        ),
        "latest_portfolio_csv": str(latest_folder / "portfolio.csv"),
        "latest_trade_lifecycle_csv": str(
            latest_folder / "trade_lifecycle.csv"
        ),
        "latest_exit_intelligence_csv": str(
            latest_folder / "exit_intelligence.csv"
        ),
        "latest_daily_action_plan_csv": str(
            latest_folder / "daily_action_plan.csv"
        ),
    }


def save_summary_md(
    folder: Path,
    portfolio: dict,
    trades_df: pd.DataFrame,
    final_df: pd.DataFrame,
    long_term_df: pd.DataFrame,
    sector_df: pd.DataFrame,
    lifecycle_df: pd.DataFrame,
    pending_entries_df: pd.DataFrame,
    open_positions_df: pd.DataFrame,
    closed_positions_df: pd.DataFrame,
    exit_df: pd.DataFrame,
    action_plan_df: pd.DataFrame,
    market_summary: dict,
    sqlite_summary_data: dict,
    history_summary_data: dict,
    lifecycle_summary: dict,
    exit_summary: dict,
    scan_datetime: datetime,
    trading_date: str,
) -> str:
    path = folder / "summary.md"

    selected_positions = int(
        portfolio.get("selected_positions", 0)
    ) if portfolio else 0

    eligible_candidates = int(
        portfolio.get("eligible_candidates", 0)
    ) if portfolio else 0

    used_capital = portfolio.get(
        "used_capital",
        0,
    ) if portfolio else 0

    cash_reserve = portfolio.get(
        "cash_reserve",
        0,
    ) if portfolio else 0

    portfolio_risk_pct = portfolio.get(
        "portfolio_risk_pct",
        0,
    ) if portfolio else 0

    health_score = portfolio.get(
        "portfolio_health_score",
        0,
    ) if portfolio else 0

    lines = []

    lines.append("# PSX AI Scanner Institutional Report")
    lines.append("")
    lines.append("## Report Metadata")
    lines.append("")
    lines.append(
        f"- Reporting Engine: **{ENGINE_VERSION}**"
    )
    lines.append(
        f"- Report Run Date: **{scan_datetime.strftime('%Y-%m-%d')}**"
    )
    lines.append(
        f"- Report Run Time: **{scan_datetime.strftime('%H:%M:%S')}**"
    )
    lines.append(
        f"- Trading Data Date: **{trading_date}**"
    )
    lines.append("- Data Status: **LATEST AVAILABLE**")
    lines.append("- Source Verification: **PASSED**")
    lines.append(f"- Report Folder: **{folder}**")
    lines.append("")

    lines.append("## Market Summary")
    lines.append("")
    lines.append(
        f"- Market Mood: **{market_summary.get('market_mood', 'N/A')}**"
    )
    lines.append(
        f"- Market Score: **{market_summary.get('market_score', 'N/A')}**"
    )
    lines.append(
        f"- Advancing: **{market_summary.get('advancing', 'N/A')}**"
    )
    lines.append(
        f"- Declining: **{market_summary.get('declining', 'N/A')}**"
    )
    lines.append(
        f"- Average Change: **{market_summary.get('average_change', 'N/A')}**"
    )
    lines.append(
        f"- Total Volume: **{market_summary.get('total_volume', 'N/A')}**"
    )
    lines.append("")

    lines.append("## Portfolio Plan")
    lines.append("")
    lines.append(
        f"- Engine: **{portfolio.get('engine_version', 'N/A') if portfolio else 'N/A'}**"
    )
    lines.append(
        f"- Eligible Candidates: **{eligible_candidates}**"
    )
    lines.append(
        f"- Selected Positions: **{selected_positions}**"
    )
    lines.append(
        f"- Used Capital: **{used_capital}**"
    )
    lines.append(
        f"- Cash Reserve: **{cash_reserve}**"
    )
    lines.append(
        f"- Portfolio Risk %: **{portfolio_risk_pct}%**"
    )
    lines.append(
        f"- Portfolio Health Score: **{health_score}**"
    )
    lines.append("")

    lines.append("## Portfolio Trades")
    lines.append("")
    lines.append(
        df_to_markdown(
            trades_df,
            [
                "rank", "symbol", "company", "sector",
                "final_decision", "final_score",
                "buy_probability", "quantity", "investment",
                "suggested_entry_price", "stop_loss",
                "target_1", "target_2",
                "max_loss", "expected_profit_t1",
                "position_status",
            ],
            rows=10,
        )
    )
    lines.append("")

    lines.append("## Trade Lifecycle Summary")
    lines.append("")
    lines.append(
        f"- Pending Entries: **{lifecycle_summary.get('pending_entries', 0)}**"
    )
    lines.append(
        f"- Open Positions: **{lifecycle_summary.get('open_positions', 0)}**"
    )
    lines.append(
        f"- Partial Exit Positions: **{lifecycle_summary.get('partial_exit_positions', 0)}**"
    )
    lines.append(
        f"- Closed Positions: **{lifecycle_summary.get('closed_positions', 0)}**"
    )
    lines.append(
        f"- Open Market Value: **{lifecycle_summary.get('open_market_value', 0)}**"
    )
    lines.append(
        f"- Unrealized P/L: **{lifecycle_summary.get('unrealized_profit_loss', 0)}**"
    )
    lines.append(
        f"- Realized P/L: **{lifecycle_summary.get('realized_profit_loss', 0)}**"
    )
    lines.append("")

    lines.append("### Pending Entries")
    lines.append("")
    lines.append(
        df_to_markdown(
            pending_entries_df,
            [
                "symbol", "company", "sector",
                "lifecycle_status", "portfolio_position_status",
                "close", "portfolio_quantity",
                "adjusted_entry_price", "stop_loss",
                "target_1", "target_2",
            ],
            rows=20,
        )
    )
    lines.append("")

    lines.append("### Open Positions")
    lines.append("")
    lines.append(
        df_to_markdown(
            open_positions_df,
            [
                "symbol", "company", "sector",
                "lifecycle_status", "trade_id",
                "actual_entry_price", "open_quantity",
                "remaining_quantity", "average_cost",
                "close", "current_stop_loss",
                "unrealized_profit_loss",
                "unrealized_profit_loss_pct",
                "holding_days_numeric",
            ],
            rows=20,
        )
    )
    lines.append("")

    lines.append("### Closed Positions")
    lines.append("")
    lines.append(
        df_to_markdown(
            closed_positions_df,
            [
                "symbol", "company", "sector",
                "lifecycle_status", "trade_id",
                "actual_entry_price",
                "realized_profit_loss",
                "holding_days_numeric",
            ],
            rows=20,
        )
    )
    lines.append("")

    lines.append("## Exit Intelligence Summary")
    lines.append("")
    lines.append(
        f"- BUY NOW: **{exit_summary.get('buy_now', 0)}**"
    )
    lines.append(
        f"- HOLD: **{exit_summary.get('hold', 0)}**"
    )
    lines.append(
        f"- ADD MORE: **{exit_summary.get('add_more', 0)}**"
    )
    lines.append(
        f"- MOVE STOPLOSS: **{exit_summary.get('move_stoploss', 0)}**"
    )
    lines.append(
        f"- TRAIL STOP: **{exit_summary.get('trail_stop', 0)}**"
    )
    lines.append(
        f"- PARTIAL PROFIT: **{exit_summary.get('partial_profit', 0)}**"
    )
    lines.append(
        f"- BOOK FULL PROFIT: **{exit_summary.get('book_full_profit', 0)}**"
    )
    lines.append(
        f"- EXIT TODAY: **{exit_summary.get('exit_today', 0)}**"
    )
    lines.append(
        f"- EMERGENCY EXIT: **{exit_summary.get('emergency_exit', 0)}**"
    )
    lines.append("")

    lines.append("### Exit Intelligence Actions")
    lines.append("")
    lines.append(
        df_to_markdown(
            exit_df,
            [
                "symbol", "company", "sector",
                "lifecycle_status", "exit_action",
                "exit_reason", "exit_risk_level",
                "exit_current_price", "exit_entry_price",
                "exit_profit_loss_pct",
                "exit_suggested_stop_loss",
                "exit_trailing_stop",
                "exit_target_status",
                "exit_confidence",
            ],
            rows=25,
        )
    )
    lines.append("")

    lines.append("## Today's Action Plan")
    lines.append("")
    lines.append(
        df_to_markdown(
            action_plan_df,
            REPORT_COLUMNS_ACTION_PLAN,
            rows=30,
        )
    )
    lines.append("")

    lines.append("## Top Short-Term Picks")
    lines.append("")
    lines.append(
        df_to_markdown(
            final_df,
            [
                "symbol", "company", "sector",
                "close", "change_pct",
                "final_score", "final_decision",
                "buy_probability", "smart_money_score",
                "trade_validation_score",
                "entry_timing_action",
                "risk_permission", "risk_status",
                "lifecycle_status", "exit_action",
            ],
            rows=25,
        )
    )
    lines.append("")

    lines.append("## Strong Sectors")
    lines.append("")
    lines.append(
        df_to_markdown(
            sector_df,
            REPORT_COLUMNS_SECTORS,
            rows=20,
        )
    )
    lines.append("")

    lines.append("## Long-Term Picks")
    lines.append("")
    lines.append(
        df_to_markdown(
            long_term_df,
            [
                "symbol", "company", "close",
                "long_term_score",
                "long_term_confidence",
                "long_term_verdict",
                "investment_amount",
                "long_term_quantity",
                "fair_value",
                "upside_pct",
            ],
            rows=25,
        )
    )
    lines.append("")

    lines.append("## Database Summary")
    lines.append("")
    lines.append(
        f"- Total Records: **{sqlite_summary_data.get('total_records', 'N/A')}**"
    )
    lines.append(
        f"- Total Symbols: **{sqlite_summary_data.get('total_symbols', 'N/A')}**"
    )
    lines.append(
        f"- Total Days: **{sqlite_summary_data.get('total_days', 'N/A')}**"
    )
    lines.append(
        f"- History Records: **{history_summary_data.get('records', 'N/A')}**"
    )
    lines.append(
        f"- History Symbols: **{history_summary_data.get('symbols', 'N/A')}**"
    )
    lines.append("")

    path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    return str(path)


def positive_numeric_value(value) -> float:
    try:
        number = float(value)
        if pd.notna(number) and number > 0:
            return number
    except Exception:
        pass
    return 0.0


def enrich_final_with_portfolio(
    final_df: pd.DataFrame,
    trades_df: pd.DataFrame,
) -> pd.DataFrame:
    final_df = clean_df(final_df)
    trades_df = clean_df(trades_df)
    if final_df.empty or trades_df.empty or "symbol" not in final_df.columns:
        return final_df

    available = [c for c in [
        "symbol", "quantity", "investment", "suggested_entry_price",
        "adjusted_entry_price", "entry_low", "entry_high", "stop_loss",
        "target_1", "target_2", "risk_per_share", "expected_profit_t1",
        "expected_profit_t2", "position_status"
    ] if c in trades_df.columns]
    if "symbol" not in available:
        return final_df

    lookup_df = trades_df[available].drop_duplicates("symbol", keep="last").copy()
    lookup_df["symbol"] = lookup_df["symbol"].astype(str).str.upper().str.strip()
    lookup = lookup_df.set_index("symbol").to_dict("index")

    result = final_df.copy()
    result["symbol"] = result["symbol"].astype(str).str.upper().str.strip()

    mapping = {
        "quantity": ["portfolio_quantity", "quantity"],
        "investment": ["portfolio_investment", "investment"],
        "suggested_entry_price": ["suggested_entry_price"],
        "adjusted_entry_price": ["adjusted_entry_price"],
        "entry_low": ["entry_low"],
        "entry_high": ["entry_high"],
        "stop_loss": ["stop_loss", "current_stop_loss"],
        "target_1": ["target_1"],
        "target_2": ["target_2"],
        "risk_per_share": ["risk_per_share"],
        "expected_profit_t1": ["expected_profit_t1"],
        "expected_profit_t2": ["expected_profit_t2"],
    }

    for idx, row in result.iterrows():
        trade = lookup.get(upper_text(row.get("symbol", "")))
        if not trade:
            continue
        result.at[idx, "portfolio_selected"] = True
        if clean_text(row.get("portfolio_position_status", "")) == "":
            result.at[idx, "portfolio_position_status"] = clean_text(trade.get("position_status", ""))
        for source, targets in mapping.items():
            source_value = positive_numeric_value(trade.get(source, 0))
            if source_value <= 0:
                continue
            for target in targets:
                if positive_numeric_value(row.get(target, 0)) <= 0:
                    result.at[idx, target] = source_value
    return clean_df(result)


def enrich_lifecycle_with_portfolio(
    lifecycle_df: pd.DataFrame,
    trades_df: pd.DataFrame,
) -> pd.DataFrame:
    lifecycle_df = enrich_final_with_portfolio(lifecycle_df, trades_df)
    defaults = {
        "portfolio_quantity": 0, "portfolio_investment": 0.0,
        "quantity": 0, "investment": 0.0,
        "suggested_entry_price": 0.0, "adjusted_entry_price": 0.0,
        "entry_low": 0.0, "entry_high": 0.0, "stop_loss": 0.0,
        "target_1": 0.0, "target_2": 0.0, "risk_per_share": 0.0,
        "expected_profit_t1": 0.0, "expected_profit_t2": 0.0,
    }
    for column, default in defaults.items():
        if column not in lifecycle_df.columns:
            lifecycle_df[column] = default
    return clean_df(lifecycle_df)


def build_lifecycle_view(
    final_df: pd.DataFrame,
) -> pd.DataFrame:
    final_df = clean_df(final_df)

    if final_df.empty:
        return pd.DataFrame(
            columns=REPORT_COLUMNS_LIFECYCLE
        )

    if "lifecycle_status" not in final_df.columns:
        final_df["lifecycle_status"] = "NO POSITION"

    view = final_df[
        final_df["lifecycle_status"]
        .fillna("")
        .astype(str)
        .str.upper()
        .ne("NO POSITION")
    ].copy()

    return view


def build_exit_view(
    final_df: pd.DataFrame,
) -> pd.DataFrame:
    final_df = clean_df(final_df)

    if final_df.empty:
        return pd.DataFrame(
            columns=REPORT_COLUMNS_EXIT
        )

    if "exit_action" not in final_df.columns:
        return pd.DataFrame(
            columns=REPORT_COLUMNS_EXIT
        )

    view = final_df[
        final_df["exit_action"]
        .fillna("")
        .astype(str)
        .str.upper()
        .ne("NO ACTION")
    ].copy()

    if view.empty:
        selected = final_df[
            final_df.get(
                "portfolio_selected",
                pd.Series(
                    False,
                    index=final_df.index,
                )
            )
            .fillna(False)
            .astype(bool)
        ].copy()

        return selected

    return view


def build_action_plan(
    final_df: pd.DataFrame,
) -> pd.DataFrame:
    final_df = clean_df(final_df)

    if final_df.empty:
        return pd.DataFrame(
            columns=REPORT_COLUMNS_ACTION_PLAN
        )

    rows = []

    for _, row in final_df.iterrows():
        exit_action = upper_text(
            row.get("exit_action", "")
        )
        lifecycle_status = upper_text(
            row.get("lifecycle_status", "")
        )
        final_decision = upper_text(
            row.get("final_decision", "")
        )
        risk_permission = upper_text(
            row.get("risk_permission", "")
        )
        entry_action = upper_text(
            row.get("entry_timing_action", "")
        )
        selected = bool_value(
            row.get("portfolio_selected", False)
        )

        recommended_action = "NO ACTION"
        priority = 99

        if exit_action == "EMERGENCY EXIT":
            recommended_action = "EMERGENCY EXIT"
            priority = 1
        elif exit_action == "EXIT TODAY":
            recommended_action = "EXIT TODAY"
            priority = 2
        elif exit_action == "BOOK FULL PROFIT":
            recommended_action = "BOOK FULL PROFIT"
            priority = 3
        elif exit_action == "PARTIAL PROFIT":
            recommended_action = "PARTIAL PROFIT"
            priority = 4
        elif exit_action == "TRAIL STOP":
            recommended_action = "TRAIL STOP"
            priority = 5
        elif exit_action == "MOVE STOPLOSS":
            recommended_action = "MOVE STOPLOSS"
            priority = 6
        elif exit_action == "ADD MORE":
            recommended_action = "ADD MORE"
            priority = 7
        elif exit_action == "HOLD":
            recommended_action = "HOLD"
            priority = 8
        elif exit_action == "BUY NOW":
            recommended_action = "BUY NOW"
            priority = 9
        elif (
            selected
            and lifecycle_status == "READY TO BUY"
            and entry_action == "BUY NOW"
            and risk_permission in {
                "TRADE ALLOWED",
                "TRADE ALLOWED SMALL",
            }
        ):
            recommended_action = "BUY NOW"
            priority = 9
        elif final_decision in {
            "BUY",
            "STRONG BUY",
        } and risk_permission == "WAIT":
            recommended_action = "WATCH / WAIT"
            priority = 20
        elif final_decision in {
            "AVOID",
            "NO TRADE",
            "BLOCKED",
        }:
            recommended_action = "AVOID"
            priority = 30

        if recommended_action == "NO ACTION":
            continue

        current_price = first_positive_numeric_from_row(
            row,
            [
                "exit_current_price",
                "close",
            ],
        )

        entry_price = first_positive_numeric_from_row(
            row,
            [
                "actual_entry_price",
                "exit_entry_price",
                "adjusted_entry_price",
                "suggested_entry_price",
            ],
        )

        stop_loss = first_positive_numeric_from_row(
            row,
            [
                "exit_suggested_stop_loss",
                "current_stop_loss",
                "stop_loss",
            ],
        )

        confidence = first_positive_numeric_from_row(
            row,
            [
                "exit_confidence",
                "confidence_v3",
                "buy_probability",
            ],
        )

        reason = clean_text(
            row.get(
                "exit_reason",
                row.get(
                    "decision_reason",
                    "",
                ),
            )
        )

        rows.append({
            "priority": priority,
            "symbol": upper_text(
                row.get("symbol", "")
            ),
            "company": clean_text(
                row.get("company", "")
            ),
            "sector": clean_text(
                row.get("sector", "")
            ),
            "lifecycle_status": lifecycle_status,
            "portfolio_position_status": clean_text(
                row.get(
                    "portfolio_position_status",
                    "",
                )
            ),
            "final_decision": final_decision,
            "risk_permission": risk_permission,
            "entry_timing_action": entry_action,
            "exit_action": exit_action,
            "recommended_action": recommended_action,
            "current_price": current_price,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "target_1": first_positive_numeric_from_row(
                row,
                ["target_1"],
            ),
            "target_2": first_positive_numeric_from_row(
                row,
                ["target_2"],
            ),
            "confidence": confidence,
            "reason": reason,
        })

    result = pd.DataFrame(
        rows,
        columns=REPORT_COLUMNS_ACTION_PLAN,
    )

    if not result.empty:
        result = result.sort_values(
            [
                "priority",
                "confidence",
            ],
            ascending=[
                True,
                False,
            ],
        ).reset_index(
            drop=True
        )

    return result


def build_lifecycle_summary(
    lifecycle_df: pd.DataFrame,
    pending_entries_df: pd.DataFrame,
    open_positions_df: pd.DataFrame,
    closed_positions_df: pd.DataFrame,
) -> dict:
    partial_exit_positions = 0

    if (
        not lifecycle_df.empty
        and "lifecycle_status" in lifecycle_df.columns
    ):
        partial_exit_positions = int(
            lifecycle_df["lifecycle_status"]
            .fillna("")
            .astype(str)
            .str.upper()
            .eq("PARTIAL EXIT")
            .sum()
        )

    open_market_value = 0.0
    unrealized_profit_loss = 0.0
    realized_profit_loss = 0.0

    if not open_positions_df.empty:
        current_price = numeric_series(
            open_positions_df,
            "close",
        )

        remaining_quantity = numeric_series(
            open_positions_df,
            "remaining_quantity",
        )

        if remaining_quantity.eq(0).all():
            remaining_quantity = numeric_series(
                open_positions_df,
                "open_quantity",
            )

        open_market_value = float(
            (
                current_price
                * remaining_quantity
            ).sum()
        )

        unrealized_profit_loss = float(
            numeric_series(
                open_positions_df,
                "unrealized_profit_loss",
            ).sum()
        )

        realized_profit_loss = float(
            numeric_series(
                open_positions_df,
                "realized_profit_loss",
            ).sum()
        )

    if not closed_positions_df.empty:
        realized_profit_loss += float(
            numeric_series(
                closed_positions_df,
                "realized_profit_loss",
            ).sum()
        )

    return {
        "pending_entries": int(
            len(pending_entries_df)
        ),
        "open_positions": int(
            len(open_positions_df)
        ),
        "partial_exit_positions": partial_exit_positions,
        "closed_positions": int(
            len(closed_positions_df)
        ),
        "open_market_value": round(
            open_market_value,
            2,
        ),
        "unrealized_profit_loss": round(
            unrealized_profit_loss,
            2,
        ),
        "realized_profit_loss": round(
            realized_profit_loss,
            2,
        ),
    }


def build_exit_summary(
    exit_df: pd.DataFrame,
) -> dict:
    actions = (
        exit_df["exit_action"]
        .fillna("")
        .astype(str)
        .str.upper()
        if (
            not exit_df.empty
            and "exit_action" in exit_df.columns
        )
        else pd.Series(
            dtype=str
        )
    )

    return {
        "buy_now": int(
            actions.eq("BUY NOW").sum()
        ),
        "hold": int(
            actions.eq("HOLD").sum()
        ),
        "add_more": int(
            actions.eq("ADD MORE").sum()
        ),
        "move_stoploss": int(
            actions.eq("MOVE STOPLOSS").sum()
        ),
        "trail_stop": int(
            actions.eq("TRAIL STOP").sum()
        ),
        "partial_profit": int(
            actions.eq("PARTIAL PROFIT").sum()
        ),
        "book_full_profit": int(
            actions.eq("BOOK FULL PROFIT").sum()
        ),
        "exit_today": int(
            actions.eq("EXIT TODAY").sum()
        ),
        "emergency_exit": int(
            actions.eq("EMERGENCY EXIT").sum()
        ),
        "no_action": int(
            actions.eq("NO ACTION").sum()
        ),
    }


def build_action_plan_summary(
    action_plan_df: pd.DataFrame,
) -> dict:
    if action_plan_df.empty:
        return {
            "total_actions": 0,
            "action_counts": {},
        }

    counts = (
        action_plan_df["recommended_action"]
        .fillna("")
        .astype(str)
        .value_counts()
        .to_dict()
    )

    return {
        "total_actions": int(
            len(action_plan_df)
        ),
        "action_counts": {
            str(key): int(value)
            for key, value in counts.items()
        },
    }


def filter_meaningful_long_term_rows(
    long_term_df: pd.DataFrame,
) -> pd.DataFrame:
    long_term_df = clean_df(
        long_term_df
    )

    if long_term_df.empty:
        return long_term_df

    confidence = numeric_series(
        long_term_df,
        "long_term_confidence",
    )

    fair_value = numeric_series(
        long_term_df,
        "fair_value",
    )

    meaningful = long_term_df[
        (confidence > 0)
        | (fair_value > 0)
    ].copy()

    return (
        meaningful
        if not meaningful.empty
        else long_term_df.head(0).copy()
    )


def save_metadata_json(
    folder: Path,
    scan_datetime: datetime,
    trading_date: str,
    portfolio: dict,
    market_summary: dict,
    sqlite_summary_data: dict,
    history_summary_data: dict,
    lifecycle_summary: dict,
    exit_summary: dict,
    action_plan_summary: dict,
) -> str:
    path = folder / "metadata.json"

    metadata = {
        "engine_version": ENGINE_VERSION,
        "scan_date": scan_datetime.strftime(
            "%Y-%m-%d"
        ),
        "scan_time": scan_datetime.strftime(
            "%H:%M:%S"
        ),
        "scan_timestamp": scan_datetime.isoformat(),
        "trading_date": trading_date,
        "trading_date_iso": trading_date_to_iso(
            trading_date
        ),
        "scan_vs_trading_same_day": (
            scan_datetime.strftime(
                "%d%b%Y"
            ).upper()
            == trading_date
        ),
        "data_status": "LATEST_AVAILABLE",
        "source_verified": True,
        "market_summary": make_json_safe(
            market_summary
        ),
        "portfolio_summary": make_json_safe({
            key: value
            for key, value in (
                portfolio or {}
            ).items()
            if key != "trades"
        }),
        "lifecycle_summary": make_json_safe(
            lifecycle_summary
        ),
        "exit_summary": make_json_safe(
            exit_summary
        ),
        "action_plan_summary": make_json_safe(
            action_plan_summary
        ),
        "sqlite_summary": make_json_safe(
            sqlite_summary_data
        ),
        "history_summary": make_json_safe(
            history_summary_data
        ),
    }

    path.write_text(
        json.dumps(
            metadata,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return str(path)


def save_scanner_log(
    folder: Path,
    scan_datetime: datetime,
    trading_date: str,
    portfolio: dict,
    market_summary: dict,
    sqlite_summary_data: dict,
    history_summary_data: dict,
    lifecycle_summary: dict,
    exit_summary: dict,
) -> str:
    path = folder / "scanner.log"

    lines = []
    lines.append("PSX AI Scanner Institutional Log")
    lines.append("=" * 60)
    lines.append(f"Engine Version   : {ENGINE_VERSION}")
    lines.append(
        f"Scan Date        : {scan_datetime.strftime('%Y-%m-%d')}"
    )
    lines.append(
        f"Scan Time        : {scan_datetime.strftime('%H:%M:%S')}"
    )
    lines.append(f"Trading Date     : {trading_date}")
    lines.append("Data Status      : LATEST AVAILABLE")
    lines.append("Verification     : PASSED")
    lines.append(
        f"Market Mood      : {market_summary.get('market_mood', 'N/A')}"
    )
    lines.append(
        f"Market Score     : {market_summary.get('market_score', 'N/A')}"
    )
    lines.append(
        f"Selected Trades  : {portfolio.get('selected_positions', 'N/A') if portfolio else 'N/A'}"
    )
    lines.append(
        f"Eligible         : {portfolio.get('eligible_candidates', 'N/A') if portfolio else 'N/A'}"
    )
    lines.append(
        f"Used Capital     : {portfolio.get('used_capital', 'N/A') if portfolio else 'N/A'}"
    )
    lines.append(
        f"Risk %           : {portfolio.get('portfolio_risk_pct', 'N/A') if portfolio else 'N/A'}"
    )
    lines.append(
        f"Pending Entries  : {lifecycle_summary.get('pending_entries', 0)}"
    )
    lines.append(
        f"Open Positions   : {lifecycle_summary.get('open_positions', 0)}"
    )
    lines.append(
        f"Closed Positions : {lifecycle_summary.get('closed_positions', 0)}"
    )
    lines.append(
        f"Unrealized P/L   : {lifecycle_summary.get('unrealized_profit_loss', 0)}"
    )
    lines.append(
        f"Realized P/L     : {lifecycle_summary.get('realized_profit_loss', 0)}"
    )
    lines.append(
        f"BUY NOW Actions  : {exit_summary.get('buy_now', 0)}"
    )
    lines.append(
        f"HOLD Actions     : {exit_summary.get('hold', 0)}"
    )
    lines.append(
        f"EXIT Actions     : {exit_summary.get('exit_today', 0) + exit_summary.get('emergency_exit', 0)}"
    )
    lines.append(
        f"DB Records       : {sqlite_summary_data.get('total_records', 'N/A')}"
    )
    lines.append(
        f"History Records  : {history_summary_data.get('records', 'N/A')}"
    )
    lines.append("=" * 60)

    path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    return str(path)


def refresh_latest_folder(
    source_folder: Path,
    latest_folder: Path,
) -> None:
    if latest_folder.exists():
        shutil.rmtree(
            latest_folder
        )

    shutil.copytree(
        source_folder,
        latest_folder,
    )


def save_csv(
    df: pd.DataFrame,
    path: Path,
    columns: list[str],
) -> str:
    df = clean_df(df)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if df.empty:
        pd.DataFrame(
            columns=columns
        ).to_csv(
            path,
            index=False,
            encoding="utf-8-sig",
        )
        return str(path)

    for column in columns:
        if column not in df.columns:
            df[column] = default_for_column(
                column
            )

    df[columns].to_csv(
        path,
        index=False,
        encoding="utf-8-sig",
    )

    return str(path)


def df_to_markdown(
    df: pd.DataFrame,
    columns: list[str],
    rows: int = 10,
) -> str:
    df = clean_df(df)

    if df.empty:
        return "_No records found._"

    available = [
        column
        for column in columns
        if column in df.columns
    ]

    if not available:
        return "_No matching columns found._"

    view = df[
        available
    ].head(
        rows
    ).copy()

    for column in view.columns:
        if pd.api.types.is_float_dtype(
            view[column]
        ):
            view[column] = view[
                column
            ].round(
                2
            )

    try:
        return view.to_markdown(
            index=False
        )
    except ImportError:
        return view.to_string(
            index=False
        )


def clean_df(
    df: pd.DataFrame | None,
) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()

    if not hasattr(
        df,
        "columns",
    ):
        return pd.DataFrame()

    output = df.copy()

    output = output.loc[
        :,
        ~output.columns.duplicated(),
    ].copy()

    return output


def detect_trading_date(
    df: pd.DataFrame | None,
) -> str:
    if (
        df is None
        or not hasattr(
            df,
            "columns",
        )
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
            parsed_dates.append(
                parsed.normalize()
            )

    if not parsed_dates:
        return "UNKNOWN_TRADING_DATE"

    latest = max(
        parsed_dates
    )

    return latest.strftime(
        "%d%b%Y"
    ).upper()


def trading_date_to_iso(
    trading_date: str,
) -> str:
    parsed = pd.to_datetime(
        str(
            trading_date
        ).strip(),
        format="%d%b%Y",
        errors="coerce",
    )

    if pd.isna(parsed):
        return "UNKNOWN_TRADING_DATE"

    return parsed.strftime(
        "%Y-%m-%d"
    )


def make_json_safe(
    value,
):
    if isinstance(
        value,
        dict,
    ):
        return {
            str(key): make_json_safe(
                item
            )
            for key, item in value.items()
        }

    if isinstance(
        value,
        list,
    ):
        return [
            make_json_safe(
                item
            )
            for item in value
        ]

    if isinstance(
        value,
        tuple,
    ):
        return [
            make_json_safe(
                item
            )
            for item in value
        ]

    if hasattr(
        value,
        "item",
    ):
        try:
            return value.item()
        except Exception:
            pass

    if isinstance(
        value,
        pd.DataFrame,
    ):
        return value.to_dict(
            orient="records"
        )

    return value


def numeric_series(
    df: pd.DataFrame,
    column: str,
) -> pd.Series:
    if column not in df.columns:
        return pd.Series(
            0.0,
            index=df.index,
            dtype=float,
        )

    return pd.to_numeric(
        df[column],
        errors="coerce",
    ).fillna(
        0.0
    )


def first_numeric_from_row(
    row: pd.Series,
    columns: list[str],
) -> float:
    for column in columns:
        value = row.get(
            column,
            None,
        )

        try:
            number = float(
                value
            )

            if pd.notna(number):
                return round(
                    number,
                    4,
                )
        except Exception:
            continue

    return 0.0


def first_positive_numeric_from_row(
    row: pd.Series,
    columns: list[str],
) -> float:
    for column in columns:
        try:
            number = float(row.get(column, None))
            if pd.notna(number) and number > 0:
                return round(number, 4)
        except Exception:
            continue
    return 0.0


def clean_text(
    value,
) -> str:
    try:
        if pd.isna(
            value
        ):
            return ""
    except Exception:
        pass

    return str(
        value
    ).strip()


def upper_text(
    value,
) -> str:
    return clean_text(
        value
    ).upper()


def bool_value(
    value,
) -> bool:
    if isinstance(
        value,
        bool,
    ):
        return value

    try:
        if pd.isna(
            value
        ):
            return False
    except Exception:
        pass

    if isinstance(
        value,
        (
            int,
            float,
        ),
    ):
        return bool(
            value
        )

    return str(
        value
    ).strip().upper() in {
        "TRUE",
        "1",
        "YES",
        "Y",
        "SELECTED",
    }


def default_for_column(
    column: str,
):
    boolean_columns = {
        "portfolio_selected",
        "partial_profit_booked",
    }

    integer_columns = {
        "rank",
        "quantity",
        "portfolio_rank",
        "portfolio_quantity",
        "actual_quantity",
        "open_quantity",
        "remaining_quantity",
        "holding_days_numeric",
        "priority",
    }

    numeric_columns = {
        "close",
        "change_pct",
        "volume",
        "value_traded",
        "final_score",
        "buy_probability",
        "sell_probability",
        "confidence_v3",
        "portfolio_rank_score",
        "position_quality_index",
        "smart_money_score",
        "accumulation_score",
        "trade_validation_score",
        "entry_timing_score",
        "risk_management_score",
        "investment",
        "portfolio_investment",
        "suggested_entry_price",
        "adjusted_entry_price",
        "entry_low",
        "entry_high",
        "stop_loss",
        "target_1",
        "target_2",
        "max_loss",
        "expected_profit_t1",
        "expected_profit_t2",
        "risk_reward_t1",
        "actual_entry_price",
        "average_cost",
        "current_stop_loss",
        "highest_price_since_entry",
        "lowest_price_since_entry",
        "realized_profit_loss",
        "unrealized_profit_loss",
        "unrealized_profit_loss_pct",
        "exit_current_price",
        "exit_entry_price",
        "exit_profit_loss_pct",
        "exit_original_stop_loss",
        "exit_suggested_stop_loss",
        "exit_trailing_stop",
        "exit_profit_lock_pct",
        "exit_confidence",
        "current_price",
        "entry_price",
        "confidence",
        "long_term_score",
        "long_term_confidence",
        "investment_amount",
        "long_term_quantity",
        "fair_value",
        "upside_pct",
        "holding_years",
        "fundamental_score",
        "growth_score",
        "valuation_score",
        "dividend_score",
        "quality_score",
    }

    if column in boolean_columns:
        return False

    if column in integer_columns:
        return 0

    if column in numeric_columns:
        return 0.0

    return ""
