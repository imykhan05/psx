import argparse
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------
# WINDOWS CONSOLE UTF-8 SAFETY
# Prevents UnicodeEncodeError for status icons and Unicode table text.
# ---------------------------------------------------------
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(
        encoding="utf-8",
        errors="replace",
    )

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(
        encoding="utf-8",
        errors="replace",
    )

from app.core.parser import read_psx_file
from app.core.sqlite_database import update_sqlite_database, sqlite_summary
from app.core.indicators import add_indicators
from app.core.history_engine_v2 import prepare_history_v2, history_v2_summary
from app.core.historical_backfill_engine import run_historical_backfill
from app.core.daily_import_engine import import_latest_daily_file
from app.core.daily_data_manager_v2 import run_daily_data_manager_v2

from app.engines.feature_builder_v3 import build_features_v3
from app.engines.ai_engine_v5 import apply_ai_engine_v5
from app.engines.institutional_v5_calibrator import apply_institutional_v5_calibration
from app.engines.signal_consensus_engine import apply_signal_consensus
from app.engines.recommendation_engine import build_recommendations
from app.engines.market_engine import MarketEngine
from app.engines.sector_engine import SectorEngine
from app.engines.decision_engine_v2 import apply_decision_engine_v2
from app.engines.trade_validation_engine import apply_trade_validation
from app.engines.entry_timing_engine import apply_entry_timing
from app.engines.risk_management_engine_v2 import apply_risk_management_v2
from app.engines.portfolio_engine_v5 import build_portfolio_plan_v5
from app.engines.market_breadth_engine_v1 import (
    run_market_breadth_engine_v1,
)
from app.engines.smart_money_tracker_v2 import (
    run_smart_money_tracker_v2,
)
from app.engines.opportunity_ranking_engine_v1 import (
    run_opportunity_ranking_engine_v1,
)
from app.engines.trade_lifecycle_engine_v1 import (
    apply_trade_lifecycle_engine_v1,
)
from app.engines.exit_intelligence_engine_v1 import (
    apply_exit_intelligence_engine_v1,
)
from app.engines.live_portfolio_monitor_v1 import (
    run_live_portfolio_monitor_v1,
)
from app.engines.equity_curve_engine_v1 import (
    run_equity_curve_engine_v1,
)
from app.engines.portfolio_analytics_pro_v1 import (
    run_portfolio_analytics_pro_v1,
)
from app.engines.trade_journal_pro_v1 import (
    run_trade_journal_pro_v1,
)
from app.engines.strategy_analytics_engine_v1 import (
    run_strategy_analytics_engine_v1,
)
from app.engines.strategy_optimizer_self_learning_v2 import (
    run_strategy_optimizer_self_learning_v2,
)
from app.engines.institutional_alert_center_v1 import (
    run_institutional_alert_center_v1,
)
from app.engines.ai_institutional_assistant_v1 import (
    run_ai_institutional_assistant_v1,
)
from app.engines.ai_command_center_v1 import (
    run_ai_command_center_v1,
)
from app.engines.order_execution_simulator_v1 import (
    execute_buy_order_v1,
    execute_sell_order_v1,
    list_pending_orders_v1,
)
from app.engines.reporting_engine_v3 import generate_reports_v2
from app.engines.performance_dashboard_v3 import (
    run_performance_dashboard_v3,
)

from app.engines.backtesting.signal_tracker_v1 import record_signals_v1
from app.engines.backtesting.backtest_engine_v1 import run_backtest_v1
from app.engines.backtesting.performance_analyzer_v1 import (
    run_performance_analyzer_v1,
)
from app.engines.backtesting.learning_engine_v1 import (
    run_learning_engine_v1,
)

from app.engines.feature_debug_engine import (
    debug_feature_snapshot,
    debug_feature_quality,
    debug_top_symbols,
)

from app.engines.long_term.fundamental_loader import (
    merge_fundamentals,
    fundamentals_summary,
)
from app.engines.long_term.long_term_engine import LongTermEngine

from app.master_data.master_builder_v2 import build_company_master_v2
from app.master_data.company_master import CompanyMaster
from app.master_data.master_sync import sync_master_everywhere
from app.master_data.master_merger import merge_master_metadata

from app.company_directory.sector_mapper import (
    SectorMapper,
    build_directory_from_scan,
)

from app.psx_intelligence.psx_company_enricher import (
    PSXCompanyEnricher,
    build_psx_company_database_from_scan,
    enrich_with_psx_company_data,
)

from config import CAPITAL_DEFAULT, MAX_PRICE_DEFAULT


def clean_duplicate_columns(df):
    if df is None:
        return df

    if hasattr(df, "columns"):
        return df.loc[:, ~df.columns.duplicated()].copy()

    return df


def print_table(title, df, columns, rows=15):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)

    if df is None or df.empty:
        print("No records found.")
    else:
        df = clean_duplicate_columns(df)
        available = [column for column in columns if column in df.columns]

        if available:
            print(df[available].head(rows).to_string(index=False))
        else:
            print("No requested columns found.")

    print("=" * 80)
    print()


def print_dict(title, data):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)

    if not data:
        print("No data found.")
    else:
        for key, value in data.items():
            if key != "trades":
                print(f"{key:30}: {value}")

    print("=" * 80)
    print()





FRESHNESS_ENGINE_VERSION = "freshness_firewall_v1"


def normalize_trading_date(value):
    if value is None:
        return None

    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")

    text = str(value).strip()

    if not text or text.upper() in {
        "NONE", "NAN", "NULL", "UNKNOWN", "UNKNOWN_TRADING_DATE"
    }:
        return None

    for date_format in (
        "%d%b%Y", "%Y-%m-%d", "%Y%m%d", "%d-%m-%Y", "%d/%m/%Y"
    ):
        parsed = pd.to_datetime(
            text,
            format=date_format,
            errors="coerce",
        )
        if pd.notna(parsed):
            return parsed.strftime("%Y-%m-%d")

    parsed = pd.to_datetime(text, errors="coerce")

    if pd.isna(parsed):
        return None

    return parsed.strftime("%Y-%m-%d")


def latest_dataframe_date(df, date_column="date"):
    if (
        df is None
        or not hasattr(df, "columns")
        or df.empty
        or date_column not in df.columns
    ):
        return None

    dates = (
        df[date_column]
        .dropna()
        .apply(normalize_trading_date)
        .dropna()
    )

    if dates.empty:
        return None

    return max(dates.tolist())


def filename_date_from_summary(daily_data_summary):
    if not isinstance(daily_data_summary, dict):
        return None

    parse_summary = daily_data_summary.get("parse_summary", {}) or {}

    for value in [
        parse_summary.get("filename_trading_date_iso"),
        daily_data_summary.get("latest_trading_date_iso"),
        parse_summary.get("filename_trading_date"),
        daily_data_summary.get("latest_trading_date"),
    ]:
        normalized = normalize_trading_date(value)
        if normalized:
            return normalized

    return None


def parser_date_from_summary(daily_data_summary):
    if not isinstance(daily_data_summary, dict):
        return None

    parse_summary = daily_data_summary.get("parse_summary", {}) or {}

    for value in [
        parse_summary.get("latest_trading_date_iso"),
        daily_data_summary.get("latest_trading_date_iso"),
        parse_summary.get("latest_trading_date"),
        daily_data_summary.get("latest_trading_date"),
    ]:
        normalized = normalize_trading_date(value)
        if normalized:
            return normalized

    return None


def detect_sqlite_latest_date(database_path="database/psx_terminal.db"):
    """
    Detect SQLite's true latest market date.

    PSX dates are commonly stored as DDMMMYYYY text, for example 10JUL2026.
    SQL MAX(date) is unsafe for this format because it compares text
    alphabetically. This implementation reads distinct date values, parses
    them in Python, and selects the real chronological maximum.
    """
    path = Path(database_path)

    if not path.exists() or path.stat().st_size == 0:
        return {
            "status": "failed",
            "database": str(path),
            "table": None,
            "date_column": None,
            "latest_date_iso": None,
            "reason": "SQLite database file is missing or empty",
        }

    preferred_date_columns = (
        "date",
        "trading_date",
        "trade_date",
        "market_date",
        "date_parsed",
    )

    try:
        connection = sqlite3.connect(str(path))

        tables = [
            row[0]
            for row in connection.execute(
                '''
                SELECT name
                FROM sqlite_master
                WHERE type='table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                '''
            ).fetchall()
        ]

        candidates = []

        for table in tables:
            safe_table = table.replace('"', '""')

            columns = [
                row[1]
                for row in connection.execute(
                    f'PRAGMA table_info("{safe_table}")'
                ).fetchall()
            ]

            lower_map = {
                str(column).lower(): column
                for column in columns
            }

            actual_column = None

            for preferred in preferred_date_columns:
                if preferred in lower_map:
                    actual_column = lower_map[preferred]
                    break

            if not actual_column:
                continue

            safe_column = actual_column.replace('"', '""')

            query = (
                f'SELECT DISTINCT "{safe_column}" '
                f'FROM "{safe_table}" '
                f'WHERE "{safe_column}" IS NOT NULL '
                f'AND TRIM(CAST("{safe_column}" AS TEXT)) != ""'
            )

            rows = connection.execute(query).fetchall()

            parsed_values = []

            for row in rows:
                raw_value = row[0] if row else None
                normalized = normalize_trading_date(raw_value)

                if normalized:
                    parsed_values.append(
                        {
                            "raw_value": raw_value,
                            "latest_date_iso": normalized,
                        }
                    )

            if not parsed_values:
                continue

            latest_for_table = max(
                parsed_values,
                key=lambda item: item["latest_date_iso"],
            )

            candidates.append(
                {
                    "table": table,
                    "date_column": actual_column,
                    "raw_value": latest_for_table["raw_value"],
                    "latest_date_iso": latest_for_table["latest_date_iso"],
                    "distinct_dates_checked": len(parsed_values),
                }
            )

        connection.close()

        if not candidates:
            return {
                "status": "failed",
                "database": str(path),
                "table": None,
                "date_column": None,
                "latest_date_iso": None,
                "reason": "No valid market-date values found in SQLite",
            }

        latest = max(
            candidates,
            key=lambda item: item["latest_date_iso"],
        )

        return {
            "status": "success",
            "database": str(path),
            "table": latest["table"],
            "date_column": latest["date_column"],
            "raw_value": latest["raw_value"],
            "latest_date_iso": latest["latest_date_iso"],
            "distinct_dates_checked": latest["distinct_dates_checked"],
            "candidate_tables_checked": len(candidates),
            "reason": (
                "SQLite latest trading date resolved by chronological parsing"
            ),
        }

    except Exception as exc:
        return {
            "status": "failed",
            "database": str(path),
            "table": None,
            "date_column": None,
            "latest_date_iso": None,
            "reason": f"SQLite latest-date check failed: {exc}",
        }


def run_freshness_firewall(
    daily_data_summary,
    today_df,
    final_df=None,
    sqlite_database="database/psx_terminal.db",
    stage="SOURCE",
):
    filename_date = filename_date_from_summary(daily_data_summary)
    parser_date = parser_date_from_summary(daily_data_summary)
    snapshot_date = latest_dataframe_date(today_df)
    final_date = (
        latest_dataframe_date(final_df)
        if final_df is not None
        else None
    )

    sqlite_check = detect_sqlite_latest_date(sqlite_database)
    sqlite_date = sqlite_check.get("latest_date_iso")

    source_mode = str(
        daily_data_summary.get("source_mode", "")
    ).strip()

    if source_mode == "manual_file_override":
        filename_date = filename_date or snapshot_date
        parser_date = parser_date or snapshot_date

    dates = {
        "filename_date_iso": filename_date,
        "parser_date_iso": parser_date,
        "snapshot_date_iso": snapshot_date,
        "sqlite_latest_date_iso": sqlite_date,
    }

    if final_df is not None:
        dates["final_dataframe_date_iso"] = final_date

    errors = []

    for label, value in dates.items():
        if not value:
            errors.append(f"{label} could not be resolved")

    resolved_values = [
        value for value in dates.values() if value
    ]
    unique_dates = sorted(set(resolved_values))

    if len(unique_dates) > 1:
        errors.append(
            "Trading-date mismatch detected: "
            + ", ".join(
                f"{key}={value}"
                for key, value in dates.items()
            )
        )

    if sqlite_check.get("status") != "success":
        errors.append(
            sqlite_check.get(
                "reason",
                "SQLite freshness check failed",
            )
        )

    parse_summary = daily_data_summary.get("parse_summary", {}) or {}

    if parse_summary.get("filename_date_matches_snapshot") is False:
        errors.append(
            "Daily filename date does not match parsed snapshot date"
        )

    verified = len(errors) == 0

    return {
        "engine_version": FRESHNESS_ENGINE_VERSION,
        "stage": stage,
        "status": "VERIFIED" if verified else "BLOCKED",
        "freshness_verified": verified,
        "source_mode": source_mode,
        **dates,
        "resolved_trading_date_iso": (
            unique_dates[0]
            if len(unique_dates) == 1
            else None
        ),
        "sqlite_check": sqlite_check,
        "errors": errors,
        "reason": (
            "All trading dates match"
            if verified
            else "Freshness verification failed"
        ),
    }


def enforce_freshness_firewall(freshness_summary):
    if freshness_summary.get("freshness_verified", False):
        return

    errors = freshness_summary.get("errors", [])
    detail = (
        " | ".join(str(error) for error in errors)
        if errors
        else "Unknown freshness failure"
    )

    raise ValueError(
        "FRESHNESS FIREWALL BLOCKED SCANNER: " + detail
    )


def clean_resolved_metadata_warnings(df):
    """
    Remove stale metadata warnings after Company Master metadata has been merged.
    """
    if df is None or not hasattr(df, "columns") or df.empty:
        return df

    result = clean_duplicate_columns(df.copy())

    warning_columns = [
        "validation_warnings",
        "entry_timing_warning",
        "risk_management_warnings",
        "consensus_warnings",
        "decision_reason",
        "institutional_v5_reason",
        "position_reason",
    ]

    for column in warning_columns:
        if column not in result.columns:
            continue

        for index, row in result.iterrows():
            sector = str(row.get("sector", "")).strip().upper()
            industry = str(row.get("industry", "")).strip().upper()

            sector_valid = sector not in {
                "",
                "UNKNOWN",
                "NAN",
                "NONE",
                "NULL",
            }

            industry_valid = industry not in {
                "",
                "UNKNOWN",
                "NAN",
                "NONE",
                "NULL",
            }

            if not (sector_valid or industry_valid):
                continue

            value = row.get(column, "")

            if value is None:
                continue

            parts = [
                part.strip()
                for part in str(value).split("|")
                if part.strip()
            ]

            cleaned_parts = [
                part
                for part in parts
                if "sector metadata missing" not in part.lower()
            ]

            result.at[index, column] = " | ".join(cleaned_parts)

    return clean_duplicate_columns(result)


def align_final_recommendations_with_portfolio(final_df, portfolio):
    """
    Make the final recommendation table consistent with Portfolio Engine V5.

    Rules:
    - Selected portfolio stocks receive portfolio capital, quantity, entry,
      stop-loss, targets and holding instructions.
    - WATCH/AVOID/NO TRADE stocks always receive zero capital and zero quantity.
    - BUY stocks not selected by Portfolio V5 remain zero-allocation candidates.
    """
    if final_df is None or not hasattr(final_df, "columns") or final_df.empty:
        return final_df

    result = clean_duplicate_columns(final_df.copy())

    required_defaults = {
        "recommended_capital": 0.0,
        "quantity": 0,
        "holding_days": "No trade",
        "portfolio_selected": False,
        "portfolio_rank": 0,
        "portfolio_investment": 0.0,
        "portfolio_quantity": 0,
        "portfolio_position_status": "",
    }

    for column, default in required_defaults.items():
        if column not in result.columns:
            result[column] = default

    # Force stable dtypes before row-level assignments.
    # Pandas 3.x / Python 3.14 raises an error when assigning a float
    # into an int64 column, so monetary columns must be float first.
    result["recommended_capital"] = pd.to_numeric(
        result["recommended_capital"],
        errors="coerce",
    ).fillna(0).astype(float)

    result["portfolio_investment"] = pd.to_numeric(
        result["portfolio_investment"],
        errors="coerce",
    ).fillna(0).astype(float)

    result["quantity"] = pd.to_numeric(
        result["quantity"],
        errors="coerce",
    ).fillna(0).astype(int)

    result["portfolio_quantity"] = pd.to_numeric(
        result["portfolio_quantity"],
        errors="coerce",
    ).fillna(0).astype(int)

    result["portfolio_rank"] = pd.to_numeric(
        result["portfolio_rank"],
        errors="coerce",
    ).fillna(0).astype(int)

    result["portfolio_selected"] = (
        result["portfolio_selected"]
        .fillna(False)
        .astype(bool)
    )

    result["holding_days"] = (
        result["holding_days"]
        .fillna("No trade")
        .astype(str)
    )

    result["portfolio_position_status"] = (
        result["portfolio_position_status"]
        .fillna("")
        .astype(str)
    )

    selected_map = {}

    if portfolio and isinstance(portfolio, dict):
        trades = portfolio.get("trades")

        if trades is not None and hasattr(trades, "iterrows") and not trades.empty:
            trades = clean_duplicate_columns(trades)

            for _, trade in trades.iterrows():
                symbol = str(trade.get("symbol", "")).strip().upper()

                if symbol:
                    selected_map[symbol] = trade

    for index, row in result.iterrows():
        symbol = str(row.get("symbol", "")).strip().upper()
        decision = str(row.get("final_decision", "")).strip().upper()
        consensus_decision = str(
            row.get("consensus_decision", "")
        ).strip().upper()
        risk_permission = str(
            row.get("risk_permission", "")
        ).strip().upper()

        blocked = (
            decision in {"AVOID", "WATCH", "NO TRADE", "BLOCKED"}
            or consensus_decision in {"AVOID", "WATCH", "NO TRADE", "BLOCKED"}
            or risk_permission == "NO TRADE"
        )

        if symbol in selected_map:
            trade = selected_map[symbol]

            result.at[index, "portfolio_selected"] = True
            result.at[index, "portfolio_rank"] = int(
                trade.get("rank", 0) or 0
            )
            result.at[index, "portfolio_investment"] = float(
                trade.get("investment", 0) or 0
            )
            result.at[index, "portfolio_quantity"] = int(
                trade.get("quantity", 0) or 0
            )
            result.at[index, "portfolio_position_status"] = str(
                trade.get("position_status", "")
            )

            result.at[index, "recommended_capital"] = float(
                trade.get("investment", 0) or 0
            )
            result.at[index, "quantity"] = int(
                trade.get("quantity", 0) or 0
            )

            for target_column, trade_column in [
                ("suggested_entry_price", "suggested_entry_price"),
                ("adjusted_entry_price", "adjusted_entry_price"),
                ("entry_low", "entry_low"),
                ("entry_high", "entry_high"),
                ("stop_loss", "stop_loss"),
                ("target_1", "target_1"),
                ("target_2", "target_2"),
            ]:
                if trade_column in trade.index:
                    result.at[index, target_column] = trade.get(
                        trade_column,
                        result.at[index, target_column]
                        if target_column in result.columns
                        else 0,
                    )

            position_status = str(
                trade.get("position_status", "")
            ).strip().upper()

            if position_status == "READY TO BUY":
                result.at[index, "holding_days"] = "1-4 days"
            elif position_status in {
                "CONTROLLED / SMALL ENTRY",
                "CONTROLLED FALLBACK POSITION",
            }:
                result.at[index, "holding_days"] = "1-3 days"
            elif position_status == "WAIT ENTRY LEVEL":
                result.at[index, "holding_days"] = "Wait for entry"
            else:
                result.at[index, "holding_days"] = "1-4 days"

        else:
            result.at[index, "portfolio_selected"] = False
            result.at[index, "portfolio_rank"] = 0
            result.at[index, "portfolio_investment"] = 0.0
            result.at[index, "portfolio_quantity"] = 0
            result.at[index, "portfolio_position_status"] = ""

            # Portfolio V5 is the final authority for deployable capital.
            result.at[index, "recommended_capital"] = 0.0
            result.at[index, "quantity"] = 0

            if blocked:
                result.at[index, "holding_days"] = "No trade"
            elif decision in {"BUY", "STRONG BUY"}:
                result.at[index, "holding_days"] = "Not selected by portfolio"
            else:
                result.at[index, "holding_days"] = "No trade"

    result["recommended_capital"] = (
        pd.to_numeric(
            result["recommended_capital"],
            errors="coerce",
        )
        .fillna(0)
        .round(2)
    )

    result["quantity"] = (
        pd.to_numeric(
            result["quantity"],
            errors="coerce",
        )
        .fillna(0)
        .astype(int)
    )

    return clean_duplicate_columns(result)


def apply_consensus_master_decision(final_df):
    """
    Convert detailed consensus decisions into the standard decisions expected
    by Portfolio Engine V5 and Reporting Engine V2.

    Raw pre-consensus decisions are preserved for debugging.
    """
    if final_df is None or final_df.empty:
        return final_df

    result = clean_duplicate_columns(final_df.copy())

    columns_to_preserve = [
        "final_decision",
        "final_score",
        "decision_reason",
        "entry_timing_action",
        "risk_level",
        "position_risk_factor",
    ]

    for column in columns_to_preserve:
        raw_column = f"{column}_before_consensus"

        if column in result.columns and raw_column not in result.columns:
            result[raw_column] = result[column]

    decision_map = {
        "STRONG BUY": "STRONG BUY",
        "BUY": "BUY",
        "BUY SMALL": "BUY",
        "ACCUMULATE": "BUY",
        "BUY ON DIP": "BUY",
        "BUY ABOVE BREAKOUT": "BUY",
        "WAIT FOR PULLBACK": "WATCH",
        "WATCH": "WATCH",
        "AVOID": "AVOID",
    }

    if "consensus_decision" in result.columns:
        mapped_decisions = (
            result["consensus_decision"]
            .astype(str)
            .str.upper()
            .str.strip()
            .map(decision_map)
        )

        fallback_decision = result.get("final_decision", "WATCH")

        result["final_decision"] = mapped_decisions.fillna(
            fallback_decision
        )

        result["verdict"] = result["consensus_decision"]

    if "consensus_score" in result.columns:
        result["final_score"] = result["consensus_score"]
        result["ai_score"] = result["consensus_score"]

    if "consensus_confidence" in result.columns:
        result["confidence"] = result["consensus_confidence"]
        result["confidence_v3"] = result["consensus_confidence"]

    if "consensus_entry_action" in result.columns:
        result["entry_timing_action"] = result["consensus_entry_action"]

    if "consensus_risk_level" in result.columns:
        risk_map = {
            "LOW": "LOW",
            "MEDIUM": "MEDIUM",
            "HIGH": "HIGH",
            "VERY HIGH": "HIGH",
            "BLOCKED": "HIGH",
        }

        result["risk_level"] = (
            result["consensus_risk_level"]
            .astype(str)
            .str.upper()
            .str.strip()
            .map(risk_map)
            .fillna("MEDIUM")
        )

    if "consensus_position_factor" in result.columns:
        result["position_risk_factor"] = result[
            "consensus_position_factor"
        ]

    if "consensus_reason" in result.columns:
        result["decision_reason"] = result["consensus_reason"]

        if "consensus_warnings" in result.columns:
            warning_mask = (
                result["consensus_warnings"]
                .fillna("")
                .astype(str)
                .str.strip()
                .ne("")
            )

            result.loc[warning_mask, "decision_reason"] = (
                result.loc[warning_mask, "decision_reason"].fillna("")
                + " || Warnings: "
                + result.loc[warning_mask, "consensus_warnings"].fillna("")
            )

    if "consensus_confidence" in result.columns:
        result["buy_probability"] = (
            result.get("buy_probability", result["consensus_confidence"])
            * 0.55
            + result["consensus_confidence"] * 0.45
        ).clip(0, 100).round(2)

        result["sell_probability"] = (
            100 - result["buy_probability"]
        ).clip(0, 100).round(2)

    result["model_version"] = "AI_V5_SIGNAL_CONSENSUS_V1"
    result["ai_engine_version"] = "signal_consensus_engine_v1_master"

    result = clean_duplicate_columns(result)

    return result


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--file",
        default=None,
        help=(
            "Optional manual PSX daily file. When omitted, Daily Data Manager V2 "
            "automatically uses the latest file from database/historical_files."
        ),
    )

    parser.add_argument(
        "--historical-folder",
        default="database/historical_files",
        help="Root folder containing yearly PSX historical-file folders.",
    )

    parser.add_argument(
        "--force-import",
        action="store_true",
        help="Force SQLite import even when the latest file appears duplicated.",
    )

    parser.add_argument(
        "--capital",
        type=int,
        default=CAPITAL_DEFAULT,
    )

    parser.add_argument(
        "--max-price",
        type=float,
        default=MAX_PRICE_DEFAULT,
    )

    parser.add_argument(
        "--backfill",
        action="store_true",
    )

    parser.add_argument(
        "--daily-import",
        action="store_true",
    )

    parser.add_argument(
        "--terminal",
        action="store_true",
        help="Launch the PSX Institutional Trading Terminal desktop GUI and exit.",
    )

    parser.add_argument(
        "--skip-news",
        action="store_true",
        help=(
            "Skip the News Sentiment Engine step entirely. It is optional; the "
            "core scan runs fine without it."
        ),
    )

    parser.add_argument(
        "--refresh-news",
        action="store_true",
        help=(
            "Load the transformer model and refresh news sentiment inline during "
            "this scan (slow, needs feedparser/transformers). By default the scan "
            "only READS the sentiment cache written by tools/refresh_sentiment.py "
            "on its own schedule — keeping the ~500MB model off the scan path."
        ),
    )

    parser.add_argument(
        "--publish",
        action="store_true",
        help=(
            "After the scan completes, git-commit the small output files "
            "(daily_signal.json, sentiment_cache.json, top_buys.csv, "
            "full_market_scan.csv) and push to origin — this triggers the "
            "Render auto-deploy. Intended for the scheduled daily run. "
            "See docs/DEPLOYMENT.md."
        ),
    )

    # ---------------------------------------------------------
    # ORDER EXECUTION SIMULATOR V1 — MANUAL COMMAND MODE
    # These options do not run automatically during a normal scan.
    # ---------------------------------------------------------
    parser.add_argument(
        "--order-list",
        action="store_true",
        help="List current READY TO BUY pending orders and exit.",
    )

    parser.add_argument(
        "--execute-buy",
        action="store_true",
        help="Execute a confirmed pending BUY order and exit.",
    )

    parser.add_argument(
        "--execute-sell",
        action="store_true",
        help="Execute a partial or full SELL order and exit.",
    )

    parser.add_argument(
        "--symbol",
        default=None,
        help="Symbol for manual order execution, for example LOTCHEM.",
    )

    parser.add_argument(
        "--price",
        type=float,
        default=None,
        help="Actual broker execution price.",
    )

    parser.add_argument(
        "--quantity",
        type=int,
        default=None,
        help=(
            "Actual BUY quantity or SELL quantity. "
            "For full SELL, omit --quantity."
        ),
    )

    parser.add_argument(
        "--execution-date",
        default=None,
        help="Execution date in YYYY-MM-DD format. Defaults to today.",
    )

    parser.add_argument(
        "--broker-reference",
        default="",
        help="Optional broker order/reference number.",
    )

    parser.add_argument(
        "--execution-notes",
        default="",
        help="Optional notes for the manual trade execution.",
    )

    parser.add_argument(
        "--commission",
        type=float,
        default=0.0,
        help="Optional broker commission/charges.",
    )

    args = parser.parse_args()

    # ---------------------------------------------------------
    # INSTITUTIONAL TRADING TERMINAL V1 — EARLY GUI MODE
    # The terminal launches as a separate desktop application and reads
    # all existing scanner reports without changing normal scanner behavior.
    # ---------------------------------------------------------
    if args.terminal:
        terminal_file = Path("institutional_terminal_v1.py")

        if not terminal_file.exists():
            raise FileNotFoundError(
                "Institutional terminal file not found: "
                f"{terminal_file.resolve()}"
            )

        terminal_environment = os.environ.copy()
        terminal_environment["PYTHONUTF8"] = "1"
        terminal_environment["PYTHONIOENCODING"] = "utf-8"

        completed = subprocess.run(
            [
                sys.executable,
                str(terminal_file),
                "--project-root",
                str(Path.cwd()),
            ],
            check=False,
            env=terminal_environment,
        )

        raise SystemExit(completed.returncode)

    # ---------------------------------------------------------
    # ORDER EXECUTION SIMULATOR V1 — EARLY EXIT COMMANDS
    # Manual execution is intentionally separated from scanner analysis.
    # ---------------------------------------------------------
    order_command_count = sum(
        [
            bool(args.order_list),
            bool(args.execute_buy),
            bool(args.execute_sell),
        ]
    )

    if order_command_count > 1:
        raise ValueError(
            "Use only one order command at a time: "
            "--order-list, --execute-buy, or --execute-sell."
        )

    if args.order_list:
        pending_orders = list_pending_orders_v1(
            portfolio_folder="database/portfolio",
            reports_latest_folder="reports/latest",
        )

        print_table(
            "ORDER EXECUTION SIMULATOR V1 — PENDING ORDERS",
            pending_orders,
            [
                "symbol",
                "company",
                "sector",
                "portfolio_quantity",
                "adjusted_entry_price",
                "suggested_entry_price",
                "stop_loss",
                "target_1",
                "target_2",
                "execution_status",
            ],
            rows=50,
        )

        print("Order Execution Simulator V1 working ✅")
        return

    if args.execute_buy:
        if not args.symbol:
            raise ValueError(
                "--symbol is required with --execute-buy."
            )

        if args.price is None:
            raise ValueError(
                "--price is required with --execute-buy."
            )

        if args.quantity is None:
            raise ValueError(
                "--quantity is required with --execute-buy."
            )

        order_execution_summary = execute_buy_order_v1(
            symbol=args.symbol,
            actual_entry_price=args.price,
            actual_quantity=args.quantity,
            entry_date=args.execution_date,
            broker_reference=args.broker_reference,
            notes=args.execution_notes,
            commission=args.commission,
            portfolio_folder="database/portfolio",
            reports_latest_folder="reports/latest",
        )

        print_dict(
            "ORDER EXECUTION SIMULATOR V1 — BUY EXECUTED",
            order_execution_summary,
        )

        print("Order Execution Simulator V1 working ✅")
        print(
            "Run the normal scanner command now to refresh "
            "Trade Lifecycle, Live Portfolio Monitor and Dashboard V3."
        )
        return

    if args.execute_sell:
        if not args.symbol:
            raise ValueError(
                "--symbol is required with --execute-sell."
            )

        if args.price is None:
            raise ValueError(
                "--price is required with --execute-sell."
            )

        order_execution_summary = execute_sell_order_v1(
            symbol=args.symbol,
            exit_price=args.price,
            exit_quantity=args.quantity,
            exit_date=args.execution_date,
            broker_reference=args.broker_reference,
            notes=args.execution_notes,
            commission=args.commission,
            portfolio_folder="database/portfolio",
            reports_latest_folder="reports/latest",
        )

        print_dict(
            "ORDER EXECUTION SIMULATOR V1 — SELL EXECUTED",
            order_execution_summary,
        )

        print("Order Execution Simulator V1 working ✅")
        print(
            "Run the normal scanner command now to refresh "
            "Trade Lifecycle, Live Portfolio Monitor and Dashboard V3."
        )
        return

    if args.backfill:
        backfill_summary = run_historical_backfill()

        print_dict(
            "HISTORICAL BACKFILL SUMMARY",
            backfill_summary,
        )

    if args.daily_import:
        daily_import_summary = import_latest_daily_file()

        print_dict(
            "DAILY IMPORT SUMMARY",
            daily_import_summary,
        )

    # ---------------------------------------------------------
    # DAILY DATA MANAGER V2 — MASTER DATA SOURCE
    # ---------------------------------------------------------
    if args.file:
        if args.file.lower().endswith(".csv"):
            manual_df = pd.read_csv(args.file)
        else:
            manual_df = read_psx_file(args.file)

        manual_df = clean_duplicate_columns(manual_df)

        if manual_df is None or manual_df.empty:
            raise ValueError(f"No records found in manual file: {args.file}")

        if "date" not in manual_df.columns:
            raise ValueError(
                "Required 'date' column is missing from manual source data."
            )

        from app.core.latest_trading_data_engine import get_latest_trading_snapshot

        today_df, daily_data_summary = get_latest_trading_snapshot(
            manual_df,
            date_column="date",
        )
        daily_data_summary["source_mode"] = "manual_file_override"
        daily_data_summary["source_file"] = args.file

    else:
        today_df, daily_data_summary = run_daily_data_manager_v2(
            historical_folder=args.historical_folder,
            import_to_sqlite=True,
            force_import=args.force_import,
        )
        daily_data_summary["source_mode"] = "daily_data_manager_v2"

    today_df = clean_duplicate_columns(today_df)

    if today_df is None or today_df.empty:
        reason = daily_data_summary.get(
            "reason",
            "Daily Data Manager V2 could not resolve the latest trading file.",
        )
        raise ValueError(reason)

    if "date" not in today_df.columns:
        raise ValueError(
            "Daily Data Manager returned data without the required 'date' column."
        )

    latest_date = today_df["date"].iloc[0]

    # ---------------------------------------------------------
    # FRESHNESS FIREWALL V1 — SOURCE STAGE
    # ---------------------------------------------------------
    source_freshness_summary = run_freshness_firewall(
        daily_data_summary=daily_data_summary,
        today_df=today_df,
        final_df=None,
        sqlite_database="database/psx_terminal.db",
        stage="SOURCE",
    )

    print_dict(
        "FRESHNESS FIREWALL V1 — SOURCE",
        source_freshness_summary,
    )

    enforce_freshness_firewall(
        source_freshness_summary
    )

    print_dict(
        "DAILY DATA MANAGER V2 SUMMARY",
        daily_data_summary,
    )

    print(f"Source mode              : {daily_data_summary.get('source_mode')}")
    print(f"Historical folder        : {args.historical_folder}")
    print(f"Latest source file       : {daily_data_summary.get('latest_file', args.file)}")
    print(f"Latest source filename   : {daily_data_summary.get('latest_filename')}")
    print(f"Latest trading date      : {latest_date}")
    print(f"Latest snapshot records  : {len(today_df)}")
    print(
        "Duplicate import skipped: "
        f"{daily_data_summary.get('duplicate_import_skipped', False)}"
    )
    print()

    # ---------------------------------------------------------
    # SQLITE + COMPLETE HISTORICAL DATA
    # ---------------------------------------------------------
    history = update_sqlite_database(today_df)
    history = prepare_history_v2(history)
    history = add_indicators(history)
    history = clean_duplicate_columns(history)

    # ---------------------------------------------------------
    # FEATURE BUILDER
    # ---------------------------------------------------------
    features = build_features_v3(
        history,
        latest_date,
    )
    features = clean_duplicate_columns(features)

    if features is None or features.empty:
        raise ValueError(
            f"Feature Builder returned no records for {latest_date}."
        )

    # ---------------------------------------------------------
    # COMPANY INTELLIGENCE
    # ---------------------------------------------------------
    build_psx_company_database_from_scan(features)

    features = enrich_with_psx_company_data(features)
    features = clean_duplicate_columns(features)

    build_directory_from_scan(features)

    # ---------------------------------------------------------
    # MARKET ENGINE
    # ---------------------------------------------------------
    market = MarketEngine(features)
    market_summary = market.summary()

    # ---------------------------------------------------------
    # AI ENGINE V5
    # ---------------------------------------------------------
    ai_result = apply_ai_engine_v5(
        features,
        max_price=args.max_price,
        market_summary=market_summary,
    )
    ai_result = clean_duplicate_columns(ai_result)

    # ---------------------------------------------------------
    # RECOMMENDATION + DECISION PIPELINE
    # ---------------------------------------------------------
    final = build_recommendations(
        ai_result,
        capital=args.capital,
    )
    final = clean_duplicate_columns(final)

    final = apply_decision_engine_v2(
        final,
        market_summary,
    )
    final = clean_duplicate_columns(final)

    final = apply_trade_validation(final)
    final = clean_duplicate_columns(final)

    final = apply_entry_timing(final)
    final = clean_duplicate_columns(final)

    final = apply_risk_management_v2(final)
    final = clean_duplicate_columns(final)

    # ---------------------------------------------------------
    # INSTITUTIONAL V5 CALIBRATION
    # ---------------------------------------------------------
    final = apply_institutional_v5_calibration(
        final,
        market_summary=market_summary,
        remove_blocked_from_final=False,
    )
    final = clean_duplicate_columns(final)

    # ---------------------------------------------------------
    # SIGNAL CONSENSUS ENGINE V1
    # ---------------------------------------------------------
    final = apply_signal_consensus(
        final,
        market_summary=market_summary,
    )
    final = clean_duplicate_columns(final)

    # Make consensus the master decision used by portfolio/reporting.
    final = apply_consensus_master_decision(final)
    final = clean_duplicate_columns(final)

    # Ensure report always carries resolved trading date.
    if "date" not in final.columns:
        final["date"] = latest_date
    else:
        final["date"] = final["date"].fillna(latest_date)

    # ---------------------------------------------------------
    # DEBUG OUTPUT
    # ---------------------------------------------------------
    debug_feature_quality(features)

    debug_feature_snapshot(
        features,
        title="FEATURE BUILDER V3 OUTPUT",
        rows=10,
    )

    debug_feature_snapshot(
        ai_result,
        title="AI ENGINE V5 RAW OUTPUT BEFORE CALIBRATION",
        rows=10,
    )

    debug_feature_snapshot(
        final,
        title="SIGNAL CONSENSUS ENGINE V1 MASTER OUTPUT",
        rows=10,
    )

    debug_top_symbols(final)

    # ---------------------------------------------------------
    # LONG-TERM ENGINE
    # ---------------------------------------------------------
    long_term_input = merge_fundamentals(features)
    long_term_input = clean_duplicate_columns(long_term_input)

    long_term_engine = LongTermEngine()

    long_term_result = long_term_engine.apply(
        long_term_input,
        capital=args.capital,
    )
    long_term_result = clean_duplicate_columns(long_term_result)

    if (
        long_term_result is not None
        and not long_term_result.empty
        and "date" not in long_term_result.columns
    ):
        long_term_result["date"] = latest_date

    # ---------------------------------------------------------
    # COMPANY MASTER
    # ---------------------------------------------------------
    company_master = build_company_master_v2(
        features_df=features,
        final_df=final,
        long_term_df=long_term_result,
    )

    sync_summary = sync_master_everywhere()

    final = merge_master_metadata(final)
    final = clean_duplicate_columns(final)

    long_term_result = merge_master_metadata(long_term_result)
    long_term_result = clean_duplicate_columns(long_term_result)

    if "date" not in final.columns:
        final["date"] = latest_date
    else:
        final["date"] = final["date"].fillna(latest_date)

    # ---------------------------------------------------------
    # FRESHNESS FIREWALL V1 — FINAL STAGE
    # ---------------------------------------------------------
    final_freshness_summary = run_freshness_firewall(
        daily_data_summary=daily_data_summary,
        today_df=today_df,
        final_df=final,
        sqlite_database="database/psx_terminal.db",
        stage="FINAL",
    )

    print_dict(
        "FRESHNESS FIREWALL V1 — FINAL",
        final_freshness_summary,
    )

    enforce_freshness_firewall(
        final_freshness_summary
    )

    # ---------------------------------------------------------
    # PORTFOLIO ENGINE V5
    # Runs after Company Master sync and metadata merge so that
    # sector/industry fields are consistent in portfolio output.
    # ---------------------------------------------------------
    portfolio = build_portfolio_plan_v5(
        final,
        capital=args.capital,
        max_positions=5,
        min_positions_bullish=2,
        min_position_value=3000,
        max_position_pct=0.28,
        max_sector_positions=2,
        base_exposure_pct=0.70,
        max_portfolio_risk_pct=2.50,
        per_trade_risk_pct=0.80,
    )

    if portfolio and "trades" in portfolio:
        portfolio["trades"] = clean_duplicate_columns(
            portfolio["trades"]
        )

    # ---------------------------------------------------------
    # FINAL RECOMMENDATION ALIGNMENT
    # Portfolio V5 is the final authority for deployable capital.
    # ---------------------------------------------------------
    final = align_final_recommendations_with_portfolio(
        final,
        portfolio,
    )
    final = clean_resolved_metadata_warnings(final)
    final = clean_duplicate_columns(final)

    # ---------------------------------------------------------
    # MARKET BREADTH ENGINE V1
    # Runs after final AI and portfolio alignment so breadth reflects
    # the same finalized decision state used by downstream engines.
    # ---------------------------------------------------------
    market_breadth_summary = run_market_breadth_engine_v1(
        market_df=final,
        trading_date=normalize_trading_date(latest_date),
        output_folder="reports/market_breadth",
    )

    # ---------------------------------------------------------
    # SMART MONEY TRACKER V2
    # Uses finalized AI output plus Market Breadth context to detect
    # accumulation, distribution, hidden buying and retail-trap risk.
    # ---------------------------------------------------------
    smart_money_summary = run_smart_money_tracker_v2(
        market_df=final,
        market_breadth_summary=market_breadth_summary,
        trading_date=normalize_trading_date(latest_date),
        output_folder="reports/smart_money",
    )

    # ---------------------------------------------------------
    # OPPORTUNITY RANKING ENGINE V1
    # Ranks finalized BUY and WATCH candidates using market breadth,
    # smart-money context, risk, validation and entry readiness.
    # ---------------------------------------------------------
    opportunity_ranking_summary = run_opportunity_ranking_engine_v1(
        market_df=final,
        market_breadth_summary=market_breadth_summary,
        smart_money_summary=smart_money_summary,
        portfolio_df=portfolio,
        trading_date=normalize_trading_date(latest_date),
        max_price=float(args.max_price),
        output_folder="reports/opportunity_ranking",
    )

    # ---------------------------------------------------------
    # TRADE LIFECYCLE ENGINE V1
    # 1) Saves portfolio-selected candidates as READY TO BUY.
    # 2) Updates actual OPEN positions from latest market prices.
    # 3) Enriches final recommendations with real holding state.
    # Must run before Exit Intelligence so BUY/HOLD/EXIT decisions
    # are based on actual positions instead of recommendation quantity.
    # ---------------------------------------------------------
    final, trade_lifecycle_summary = apply_trade_lifecycle_engine_v1(
        recommendations_df=final,
        market_df=final,
        data_folder="database/portfolio",
    )
    final = clean_duplicate_columns(final)

    # ---------------------------------------------------------
    # EXIT INTELLIGENCE ENGINE V1
    # Runs after portfolio alignment so selected positions use
    # actual portfolio quantity, investment, entry, stop and targets.
    # ---------------------------------------------------------
    final = apply_exit_intelligence_engine_v1(
        final,
        partial_profit_pct=40.0,
        final_profit_pct=100.0,
        breakeven_trigger_pct=3.0,
        trail_trigger_pct=5.0,
        emergency_loss_pct=-8.0,
        max_holding_days=5,
        minimum_confidence=55.0,
        add_more_min_confidence=82.0,
        add_more_max_profit_pct=2.5,
        add_more_max_rsi=72.0,
        weak_rsi_level=45.0,
        overbought_rsi_level=82.0,
    )
    final = clean_duplicate_columns(final)

    # ---------------------------------------------------------
    # LIVE PORTFOLIO MONITOR V1
    # Runs after Trade Lifecycle and Exit Intelligence.
    # It updates only actual open positions stored in
    # database/portfolio/open_positions.csv.
    # READY TO BUY recommendations are not converted into fake positions.
    # ---------------------------------------------------------
    live_portfolio_summary = run_live_portfolio_monitor_v1(
        latest_market_df=final,
        lifecycle_folder="database/portfolio",
        reports_latest_folder="reports/latest",
        output_folder="reports/live_portfolio",
    )

    # ---------------------------------------------------------
    # EQUITY CURVE ENGINE V1
    # Runs after Live Portfolio Monitor so current market values,
    # realized P/L and unrealized P/L are already updated.
    # Uses the verified trading date, not the scanner run date.
    # ---------------------------------------------------------
    equity_curve_summary = run_equity_curve_engine_v1(
        starting_capital=float(args.capital),
        snapshot_date=normalize_trading_date(latest_date),
        portfolio_folder="database/portfolio",
        reports_folder="reports/performance",
    )

    # ---------------------------------------------------------
    # PORTFOLIO ANALYTICS PRO V1
    # Runs after Equity Curve so exposure, concentration, risk,
    # diversification and rebalancing use the latest portfolio state.
    # ---------------------------------------------------------
    portfolio_analytics_summary = run_portfolio_analytics_pro_v1(
        starting_capital=float(args.capital),
        portfolio_folder="database/portfolio",
        reports_folder="reports/portfolio_analytics",
        latest_reports_folder="reports/latest",
    )

    # ---------------------------------------------------------
    # TRADE JOURNAL PRO V1
    # Runs after live portfolio, equity curve and portfolio analytics.
    # Uses actual executions plus current AI recommendation context.
    # ---------------------------------------------------------
    trade_journal_summary = run_trade_journal_pro_v1(
        starting_capital=float(args.capital),
        recommendation_df=final,
        portfolio_folder="database/portfolio",
        reports_folder="reports/trade_journal",
        latest_reports_folder="reports/latest",
    )

    # ---------------------------------------------------------
    # STRATEGY ANALYTICS ENGINE V1
    # Runs after Trade Journal Pro so each detected strategy is measured
    # using actual open/closed trade performance.
    # ---------------------------------------------------------
    strategy_analytics_summary = run_strategy_analytics_engine_v1(
        starting_capital=float(args.capital),
        journal_df=None,
        trade_journal_folder="reports/trade_journal",
        reports_folder="reports/strategy_analytics",
    )

    # ---------------------------------------------------------
    # STRATEGY OPTIMIZER & SELF-LEARNING ENGINE V2
    # Runs after Strategy Analytics. Weight changes are sample-safe and
    # advisory; tiny samples remain in LEARNING mode.
    # ---------------------------------------------------------
    strategy_optimizer_summary = run_strategy_optimizer_self_learning_v2(
        starting_capital=float(args.capital),
        strategy_folder="reports/strategy_analytics",
        journal_folder="reports/trade_journal",
        output_folder="database/strategy_learning",
        report_folder="reports/strategy_optimizer",
        minimum_closed_trades=10,
        strong_sample_trades=25,
        disable_sample_trades=30,
        maximum_weight_change=0.15,
    )

    # ---------------------------------------------------------
    # INSTITUTIONAL ALERT CENTER V1
    # ---------------------------------------------------------
    institutional_alert_summary = run_institutional_alert_center_v1(
        market_df=final,
        portfolio_risk_pct=float(
            portfolio_analytics_summary.get("portfolio_risk_pct", 0.0)
        ) if isinstance(portfolio_analytics_summary, dict) else 0.0,
        portfolio_health_score=float(
            portfolio_analytics_summary.get("portfolio_health_score", 0.0)
        ) if isinstance(portfolio_analytics_summary, dict) else 0.0,
        trading_date=normalize_trading_date(latest_date),
        portfolio_folder="database/portfolio",
        reports_latest_folder="reports/latest",
        strategy_optimizer_folder="reports/strategy_optimizer",
        output_folder="reports/alerts",
    )

    # ---------------------------------------------------------
    # AI INSTITUTIONAL ASSISTANT V1
    # ---------------------------------------------------------
    ai_assistant_summary = run_ai_institutional_assistant_v1(
        market_df=final,
        market_summary=market_summary,
        portfolio_summary=portfolio_analytics_summary,
        lifecycle_summary=trade_lifecycle_summary,
        alert_summary=institutional_alert_summary,
        strategy_summary=strategy_analytics_summary,
        optimizer_summary=strategy_optimizer_summary,
        starting_capital=float(args.capital),
        trading_date=normalize_trading_date(latest_date),
        reports_folder="reports/ai_assistant",
        alerts_folder="reports/alerts",
        portfolio_folder="database/portfolio",
        optimizer_folder="reports/strategy_optimizer",
    )

    # ---------------------------------------------------------
    # AI COMMAND CENTER V1
    # Unified single-screen institutional decision output.
    # ---------------------------------------------------------
    ai_command_center_summary = run_ai_command_center_v1(
        market_df=final,
        market_summary=market_summary,
        portfolio_summary=portfolio_analytics_summary,
        lifecycle_summary=trade_lifecycle_summary,
        alert_summary=institutional_alert_summary,
        assistant_summary=ai_assistant_summary,
        strategy_summary=strategy_analytics_summary,
        optimizer_summary=strategy_optimizer_summary,
        starting_capital=float(args.capital),
        trading_date=normalize_trading_date(latest_date),
        output_folder="reports/command_center",
        portfolio_folder="database/portfolio",
        alerts_folder="reports/alerts",
        assistant_folder="reports/ai_assistant",
        strategy_folder="reports/strategy_analytics",
        optimizer_folder="reports/strategy_optimizer",
    )

    # ---------------------------------------------------------
    # BACKTESTING + SELF-LEARNING PIPELINE V1
    # 1) Save today's selected portfolio signals.
    # 2) Evaluate older signals against historical OHLC data.
    # 3) Generate performance reports.
    # 4) Generate learning recommendations when enough data exists.
    # ---------------------------------------------------------
    resolved_source_file = daily_data_summary.get(
        "latest_file",
        args.file,
    ) or args.file or ""

    signal_tracker_summary = record_signals_v1(
        portfolio=portfolio,
        signal_date=latest_date,
        source_file=str(resolved_source_file),
        final_df=final,
        history_file="database/backtesting/signal_history.csv",
        save_only_selected=True,
    )

    backtest_summary = run_backtest_v1(
        signal_history_file="database/backtesting/signal_history.csv",
        historical_prices_file="database/psx_history_clean.csv",
        max_holding_days=5,
        target_priority=False,
        close_open_signals_after_max_days=True,
    )

    performance_summary = run_performance_analyzer_v1(
        signal_history_file="database/backtesting/signal_history.csv",
        report_folder="reports/backtests",
        min_closed_signals_for_rating=10,
    )

    learning_summary = run_learning_engine_v1(
        signal_history_file="database/backtesting/signal_history.csv",
        learning_folder="database/backtesting/learning",
        report_folder="reports/backtests",
        minimum_closed_signals=10,
        minimum_group_signals=3,
        maximum_adjustment=10.0,
    )

    # ---------------------------------------------------------
    # SUMMARIES
    # ---------------------------------------------------------
    psx_intelligence_summary = PSXCompanyEnricher().summary()
    directory_summary = SectorMapper().summary()
    master_summary = CompanyMaster().summary()

    sqlite_summary_data = sqlite_summary()
    history_summary_data = history_v2_summary(history)

    sector_summary = SectorEngine(final).sector_summary()
    sector_summary = clean_duplicate_columns(sector_summary)

    # ---------------------------------------------------------
    # REPORTING ENGINE V3
    # ---------------------------------------------------------
    report_summary = generate_reports_v2(
        portfolio=portfolio,
        final_df=final,
        long_term_df=long_term_result,
        sector_df=sector_summary,
        market_summary=market_summary,
        sqlite_summary_data=sqlite_summary_data,
        history_summary_data=history_summary_data,
        output_root="reports",
    )

    # ---------------------------------------------------------
    # PERFORMANCE DASHBOARD V3
    # Runs after Reporting, Alert Center, AI Assistant and Command Center
    # so the terminal can visualize the complete institutional state.
    # ---------------------------------------------------------
    dashboard_summary = run_performance_dashboard_v3(
        reports_root="reports",
        latest_folder="reports/latest",
        lifecycle_folder="database/portfolio",
        output_folder="reports/dashboard",
        dashboard_filename="dashboard_v3.html",
        latest_dashboard_filename="latest_dashboard_v3.html",
        trading_date=normalize_trading_date(latest_date),
        starting_capital=float(args.capital),
        auto_refresh_seconds=0,
    )

    # ---------------------------------------------------------
    # NEWS SENTIMENT ENGINE V1 (optional, non-blocking)
    # Independent information signal. The ~500MB transformer model is kept OFF
    # this scan path by default: the standalone refresher
    # (tools/refresh_sentiment.py) runs the model on its own schedule and writes
    # the cache, and the normal scan only READS that cache and reports how fresh
    # it is. Pass --refresh-news to force an inline model refresh instead.
    # Any failure here is caught and logged; the core scan always continues.
    # ---------------------------------------------------------
    if not args.skip_news:
        try:
            from app.engines.news_sentiment_engine_v1 import (
                run_news_sentiment_engine,
                read_cached_sentiment,
                sentiment_summary,
            )

            if args.refresh_news:
                # Explicit opt-in: load the model and refresh inline (slow).
                news_payload = run_news_sentiment_engine()
                print_dict(
                    "NEWS SENTIMENT ENGINE V1 SUMMARY (inline refresh)",
                    sentiment_summary(news_payload),
                )
            else:
                # Default: read the cache the scheduled refresher produced.
                cached = read_cached_sentiment()
                if cached is None:
                    print(
                        "[NEWS SENTIMENT] no cache yet — run "
                        "'python tools/refresh_sentiment.py' (or pass "
                        "--refresh-news) to populate it."
                    )
                else:
                    from datetime import datetime, timezone

                    summary = sentiment_summary(cached)
                    generated_at = cached.get("generated_at")
                    age_hours = None
                    try:
                        gen = datetime.fromisoformat(str(generated_at))
                        if gen.tzinfo is None:
                            gen = gen.replace(tzinfo=timezone.utc)
                        age_hours = (
                            datetime.now(timezone.utc) - gen
                        ).total_seconds() / 3600.0
                    except (TypeError, ValueError):
                        pass
                    summary["cache_age_hours"] = (
                        round(age_hours, 1) if age_hours is not None else "unknown"
                    )
                    summary["stale"] = (
                        age_hours is not None and age_hours > 12
                    )
                    print_dict(
                        "NEWS SENTIMENT (cached — from scheduled refresher)",
                        summary,
                    )
        except Exception as exc:
            print(
                "[NEWS SENTIMENT] skipped (non-fatal): "
                f"{type(exc).__name__}: {exc}"
            )

    # ---------------------------------------------------------
    # DAILY MARKET SIGNAL ENGINE (Phase 2 #2)
    # Combines the rule-scoring output (breadth + BUY/WATCH distribution) with
    # the news sentiment tilt into one BULLISH/BEARISH/NEUTRAL verdict. Runs
    # after the news step so the sentiment cache is fresh. Non-blocking.
    # ---------------------------------------------------------
    try:
        from app.engines.daily_signal_engine import run_daily_signal_engine

        daily_signal = run_daily_signal_engine()
        print_dict(
            "DAILY MARKET SIGNAL",
            {
                "verdict": daily_signal.get("verdict"),
                "confidence": daily_signal.get("confidence"),
                "date": daily_signal.get("date"),
                "top_opportunities": ", ".join(
                    daily_signal.get("top_opportunities", [])
                ),
                "reason_1": (daily_signal.get("reasons") or [""])[0],
            },
        )
    except Exception as exc:
        print(
            "[DAILY SIGNAL] skipped (non-fatal): "
            f"{type(exc).__name__}: {exc}"
        )

    # ---------------------------------------------------------
    # SCREENER ENGINE V1 (Phase: click-and-go screeners)
    # Turns the scan output + price history into named stock lists
    # (upper-lock, MA50/MA200, volume spikes, accumulation, rule-picks).
    # Reads full_market_scan.csv (written above) + SQLite daily_prices.
    # Non-blocking: any failure is logged and the scan still completes.
    # ---------------------------------------------------------
    try:
        from app.engines.screener_engine_v1 import run_screener_engine

        screener_payload = run_screener_engine()
        print_dict(
            "SCREENER ENGINE V1",
            {
                "as_of": screener_payload.get("as_of_date"),
                "universe": screener_payload.get("universe"),
                "screeners": len(screener_payload.get("screeners", {})),
            },
        )
    except Exception as exc:
        print(
            "[SCREENERS] skipped (non-fatal): "
            f"{type(exc).__name__}: {exc}"
        )

    # ---------------------------------------------------------
    # SECTOR ROTATION ENGINE V1 — where money has flowed, by sector
    # ---------------------------------------------------------
    try:
        from app.engines.sector_rotation_engine_v1 import run_sector_rotation

        sector_rot = run_sector_rotation()
        print(f"[SECTOR ROTATION] {sector_rot.get('sector_count')} sectors ranked.")
    except Exception as exc:
        print(
            "[SECTOR ROTATION] skipped (non-fatal): "
            f"{type(exc).__name__}: {exc}"
        )

    # ---------------------------------------------------------
    # MORNING BRIEFING ENGINE V1 — pre-market multi-timeframe summary
    # Reads all_stocks.json (screener, above) + daily_signal + sentiment.
    # Non-blocking. Also regenerated by the 9 AM job with fresh news.
    # ---------------------------------------------------------
    try:
        from app.engines.morning_briefing_engine_v1 import run_morning_briefing

        run_morning_briefing()
        print("[BRIEFING] morning_briefing.json updated.")
    except Exception as exc:
        print(
            "[BRIEFING] skipped (non-fatal): "
            f"{type(exc).__name__}: {exc}"
        )

    # ---------------------------------------------------------
    # HIGHLIGHTS ENGINE V1 — "Today's Highlights" digest
    # Aggregates screeners + sectors + signal + news into one watch-list.
    # ---------------------------------------------------------
    try:
        from app.engines.highlights_engine_v1 import run_highlights_engine

        hl = run_highlights_engine()
        print(f"[HIGHLIGHTS] {len(hl.get('highlights', []))} groups.")
    except Exception as exc:
        print(
            "[HIGHLIGHTS] skipped (non-fatal): "
            f"{type(exc).__name__}: {exc}"
        )

    # ---------------------------------------------------------
    # SEASONALITY ENGINE V1 — day-of-week / month-of-year patterns
    # ---------------------------------------------------------
    try:
        from app.engines.seasonality_engine_v1 import run_seasonality_engine

        run_seasonality_engine()
        print("[SEASONALITY] seasonality.json updated.")
    except Exception as exc:
        print(
            "[SEASONALITY] skipped (non-fatal): "
            f"{type(exc).__name__}: {exc}"
        )

    # ---------------------------------------------------------
    # MODEL ENGINE V1 — walk-forward-validated cross-sectional ranking
    # (the honest "real model": small OOS edge; see docs/EDGE_VALIDATION.md)
    # ---------------------------------------------------------
    try:
        from app.engines.model_engine_v1 import run_model_engine

        mp = run_model_engine()
        print(f"[MODEL] {mp.get('universe')} stocks ranked.")
    except Exception as exc:
        print(
            "[MODEL] skipped (non-fatal): "
            f"{type(exc).__name__}: {exc}"
        )

    # ---------------------------------------------------------
    # SYSTEM SUMMARIES
    # ---------------------------------------------------------
    print_dict(
        "SQLITE DATABASE SUMMARY",
        sqlite_summary_data,
    )

    print_dict(
        "HISTORY ENGINE V2 SUMMARY",
        history_summary_data,
    )

    print_dict(
        "FUNDAMENTALS SUMMARY",
        fundamentals_summary(),
    )

    print_dict(
        "PSX INTELLIGENCE SUMMARY",
        psx_intelligence_summary,
    )

    print_dict(
        "COMPANY DIRECTORY SUMMARY",
        directory_summary,
    )

    print_dict(
        "PSX MARKET SUMMARY",
        market_summary,
    )

    print_dict(
        "AI MASTER DATABASE SUMMARY",
        master_summary,
    )

    print_dict(
        "MASTER SYNC SUMMARY",
        sync_summary,
    )

    print_dict(
        "REPORTING ENGINE V3 SUMMARY",
        report_summary,
    )

    print_dict(
        "PERFORMANCE DASHBOARD V3 SUMMARY",
        dashboard_summary,
    )

    print_dict(
        "FRESHNESS FIREWALL V1 — SOURCE SUMMARY",
        source_freshness_summary,
    )

    print_dict(
        "FRESHNESS FIREWALL V1 — FINAL SUMMARY",
        final_freshness_summary,
    )

    print_dict(
        "MARKET BREADTH ENGINE V1 SUMMARY",
        market_breadth_summary,
    )

    print_dict(
        "SMART MONEY TRACKER V2 SUMMARY",
        smart_money_summary,
    )

    print_dict(
        "OPPORTUNITY RANKING ENGINE V1 SUMMARY",
        opportunity_ranking_summary,
    )

    print_dict(
        "TRADE LIFECYCLE ENGINE V1 SUMMARY",
        trade_lifecycle_summary,
    )

    print_dict(
        "LIVE PORTFOLIO MONITOR V1 SUMMARY",
        live_portfolio_summary,
    )

    print_dict(
        "EQUITY CURVE ENGINE V1 SUMMARY",
        equity_curve_summary,
    )

    print_dict(
        "PORTFOLIO ANALYTICS PRO V1 SUMMARY",
        portfolio_analytics_summary,
    )

    print_dict(
        "TRADE JOURNAL PRO V1 SUMMARY",
        trade_journal_summary,
    )

    print_dict(
        "STRATEGY ANALYTICS ENGINE V1 SUMMARY",
        strategy_analytics_summary,
    )

    print_dict(
        "STRATEGY OPTIMIZER & SELF-LEARNING ENGINE V2 SUMMARY",
        strategy_optimizer_summary,
    )

    print_dict(
        "INSTITUTIONAL ALERT CENTER V1 SUMMARY",
        institutional_alert_summary,
    )

    print_dict(
        "AI INSTITUTIONAL ASSISTANT V1 SUMMARY",
        ai_assistant_summary,
    )

    print_dict(
        "AI COMMAND CENTER V1 SUMMARY",
        ai_command_center_summary,
    )

    print_dict(
        "SIGNAL TRACKER V1 SUMMARY",
        signal_tracker_summary,
    )

    print_dict(
        "BACKTEST ENGINE V1 SUMMARY",
        backtest_summary,
    )

    print_dict(
        "PERFORMANCE ANALYZER V1 SUMMARY",
        performance_summary,
    )

    print_dict(
        "LEARNING ENGINE V1 SUMMARY",
        learning_summary,
    )

    # ---------------------------------------------------------
    # EQUITY CURVE STATUS
    # ---------------------------------------------------------
    equity_history_path = Path(
        equity_curve_summary.get(
            "equity_history_csv",
            "database/portfolio/equity_history.csv",
        )
    )

    if (
        equity_history_path.exists()
        and equity_history_path.stat().st_size > 0
    ):
        try:
            equity_history_view = pd.read_csv(
                equity_history_path
            )
            equity_history_view = clean_duplicate_columns(
                equity_history_view
            )
        except (
            pd.errors.EmptyDataError,
            pd.errors.ParserError,
            UnicodeDecodeError,
        ):
            equity_history_view = pd.DataFrame()
    else:
        equity_history_view = pd.DataFrame()

    print_table(
        "EQUITY CURVE ENGINE V1 STATUS",
        equity_history_view,
        [
            "date",
            "starting_capital",
            "cash_balance",
            "invested_capital",
            "open_market_value",
            "realized_profit_loss",
            "unrealized_profit_loss",
            "gross_profit_loss",
            "total_equity",
            "daily_return_pct",
            "cumulative_return_pct",
            "peak_equity",
            "drawdown_amount",
            "drawdown_pct",
            "active_positions",
            "closed_positions",
            "last_updated_at",
        ],
        rows=30,
    )

    # ---------------------------------------------------------
    # PORTFOLIO ANALYTICS PRO V1 STATUS
    # ---------------------------------------------------------
    portfolio_analytics_path = Path(
        portfolio_analytics_summary.get(
            "portfolio_analytics_csv",
            "reports/portfolio_analytics/portfolio_analytics.csv",
        )
    )

    sector_exposure_path = Path(
        portfolio_analytics_summary.get(
            "sector_exposure_csv",
            "reports/portfolio_analytics/sector_exposure.csv",
        )
    )

    rebalancing_path = Path(
        portfolio_analytics_summary.get(
            "rebalancing_suggestions_csv",
            "reports/portfolio_analytics/rebalancing_suggestions.csv",
        )
    )

    def read_optional_report(path):
        if (
            path.exists()
            and path.stat().st_size > 0
        ):
            try:
                frame = pd.read_csv(path)
                return clean_duplicate_columns(frame)
            except (
                pd.errors.EmptyDataError,
                pd.errors.ParserError,
                UnicodeDecodeError,
            ):
                return pd.DataFrame()

        return pd.DataFrame()

    portfolio_analytics_view = read_optional_report(
        portfolio_analytics_path
    )

    sector_exposure_view = read_optional_report(
        sector_exposure_path
    )

    rebalancing_view = read_optional_report(
        rebalancing_path
    )

    print_table(
        "PORTFOLIO ANALYTICS PRO V1 — POSITION ANALYTICS",
        portfolio_analytics_view,
        [
            "symbol",
            "company",
            "sector",
            "position_status",
            "entry_date",
            "quantity",
            "entry_price",
            "current_price",
            "cost_value",
            "market_value",
            "position_weight_pct",
            "unrealized_profit_loss",
            "unrealized_profit_loss_pct",
            "stop_loss",
            "target_1",
            "target_2",
            "risk_amount",
            "risk_pct_of_capital",
            "risk_reward_t1",
            "risk_reward_t2",
            "concentration_status",
            "risk_status",
            "holding_days",
        ],
        rows=25,
    )

    print_table(
        "PORTFOLIO ANALYTICS PRO V1 — SECTOR EXPOSURE",
        sector_exposure_view,
        [
            "sector",
            "positions",
            "cost_value",
            "market_value",
            "sector_exposure_pct",
            "unrealized_profit_loss",
            "risk_amount",
            "average_position_weight_pct",
            "sector_concentration_status",
        ],
        rows=25,
    )

    print_table(
        "PORTFOLIO ANALYTICS PRO V1 — REBALANCING SUGGESTIONS",
        rebalancing_view,
        [
            "priority",
            "category",
            "symbol_or_sector",
            "issue",
            "suggested_action",
            "severity",
        ],
        rows=25,
    )

    # ---------------------------------------------------------
    # TRADE JOURNAL PRO V1 STATUS
    # ---------------------------------------------------------
    trade_journal_path = Path(
        trade_journal_summary.get(
            "journal_csv",
            "reports/trade_journal/trade_journal.csv",
        )
    )

    trade_review_path = Path(
        trade_journal_summary.get(
            "review_queue_csv",
            "reports/trade_journal/trade_review_queue.csv",
        )
    )

    trade_journal_view = read_optional_report(
        trade_journal_path
    )

    trade_review_view = read_optional_report(
        trade_review_path
    )

    print_table(
        "TRADE JOURNAL PRO V1 — JOURNAL",
        trade_journal_view,
        [
            "trade_id",
            "symbol",
            "company",
            "sector",
            "strategy",
            "entry_date",
            "exit_date",
            "entry_price",
            "exit_price",
            "original_quantity",
            "remaining_quantity",
            "realized_profit_loss",
            "unrealized_profit_loss",
            "total_profit_loss",
            "return_pct",
            "holding_days",
            "trade_status",
            "trade_result",
            "why_bought",
            "why_sold",
            "mistake_flag",
            "mistake_notes",
            "lesson_learned",
            "manual_review_status",
        ],
        rows=30,
    )

    print_table(
        "TRADE JOURNAL PRO V1 — REVIEW QUEUE",
        trade_review_view,
        [
            "review_priority",
            "trade_id",
            "symbol",
            "company",
            "strategy",
            "trade_status",
            "trade_result",
            "realized_profit_loss",
            "return_pct",
            "mistake_flag",
            "mistake_notes",
            "lesson_learned",
            "manual_review_status",
            "review_action",
        ],
        rows=30,
    )

    # ---------------------------------------------------------
    # STRATEGY ANALYTICS ENGINE V1 STATUS
    # ---------------------------------------------------------
    strategy_analytics_path = Path(
        strategy_analytics_summary.get(
            "strategy_analytics_csv",
            "reports/strategy_analytics/strategy_analytics.csv",
        )
    )

    strategy_leaderboard_path = Path(
        strategy_analytics_summary.get(
            "leaderboard_csv",
            "reports/strategy_analytics/strategy_leaderboard.csv",
        )
    )

    strategy_analytics_view = read_optional_report(
        strategy_analytics_path
    )

    strategy_leaderboard_view = read_optional_report(
        strategy_leaderboard_path
    )

    print_table(
        "STRATEGY ANALYTICS ENGINE V1 — PERFORMANCE",
        strategy_analytics_view,
        [
            "strategy",
            "total_trades",
            "open_trades",
            "closed_trades",
            "winning_trades",
            "losing_trades",
            "win_rate_pct",
            "gross_profit",
            "gross_loss",
            "net_profit_loss",
            "profit_factor",
            "expectancy",
            "average_return_pct",
            "average_holding_days",
            "sharpe_ratio",
            "maximum_drawdown_pct",
            "recovery_factor",
            "best_trade_symbol",
            "best_trade_profit_loss",
            "worst_trade_symbol",
            "worst_trade_profit_loss",
            "strategy_score",
            "status",
            "recommendation",
        ],
        rows=30,
    )

    print_table(
        "STRATEGY ANALYTICS ENGINE V1 — LEADERBOARD",
        strategy_leaderboard_view,
        [
            "rank",
            "strategy",
            "strategy_score",
            "status",
            "closed_trades",
            "win_rate_pct",
            "profit_factor",
            "expectancy",
            "net_profit_loss",
            "sharpe_ratio",
            "maximum_drawdown_pct",
            "recovery_factor",
            "average_return_pct",
            "recommendation",
        ],
        rows=30,
    )

    # ---------------------------------------------------------
    # STRATEGY OPTIMIZER & SELF-LEARNING ENGINE V2 STATUS
    # ---------------------------------------------------------
    strategy_optimizer_path = Path(
        strategy_optimizer_summary.get(
            "optimizer_output_csv",
            "reports/strategy_optimizer/strategy_optimizer_output.csv",
        )
    )

    strategy_actions_path = Path(
        strategy_optimizer_summary.get(
            "strategy_actions_csv",
            "reports/strategy_optimizer/strategy_actions_v2.csv",
        )
    )

    strategy_optimizer_view = read_optional_report(
        strategy_optimizer_path
    )

    strategy_actions_view = read_optional_report(
        strategy_actions_path
    )

    print_table(
        "STRATEGY OPTIMIZER & SELF-LEARNING V2 — WEIGHT DECISIONS",
        strategy_optimizer_view,
        [
            "strategy",
            "closed_trades",
            "sample_confidence_pct",
            "operating_status",
            "base_strategy_score",
            "optimizer_quality_score",
            "win_rate_pct",
            "profit_factor",
            "expectancy",
            "sharpe_ratio",
            "maximum_drawdown_pct",
            "recent_30d_trades",
            "recent_30d_win_rate_pct",
            "current_weight",
            "suggested_weight",
            "weight_change_pct",
            "recommended_action",
            "automatic_disable_allowed",
            "optimizer_reason",
        ],
        rows=30,
    )

    print_table(
        "STRATEGY OPTIMIZER & SELF-LEARNING V2 — ACTIONS",
        strategy_actions_view,
        [
            "priority",
            "strategy",
            "operating_status",
            "closed_trades",
            "optimizer_quality_score",
            "recommended_action",
            "suggested_weight",
            "automatic_disable_allowed",
            "operational_instruction",
            "optimizer_reason",
        ],
        rows=30,
    )

    # ---------------------------------------------------------
    # INSTITUTIONAL ALERT CENTER V1 STATUS
    # ---------------------------------------------------------
    institutional_alerts_view = read_optional_report(
        Path(institutional_alert_summary.get(
            "live_alerts_csv", "reports/alerts/live_alerts.csv"
        ))
    )
    critical_alerts_view = read_optional_report(
        Path(institutional_alert_summary.get(
            "critical_alerts_csv", "reports/alerts/critical_alerts.csv"
        ))
    )

    print_table(
        "INSTITUTIONAL ALERT CENTER V1 — LIVE ALERTS",
        institutional_alerts_view,
        [
            "priority", "severity", "alert_category", "alert_type",
            "symbol", "title", "message", "recommended_action",
            "current_price", "reference_price", "confidence", "source_engine",
        ],
        rows=50,
    )

    print_table(
        "INSTITUTIONAL ALERT CENTER V1 — CRITICAL ALERTS",
        critical_alerts_view,
        [
            "priority", "severity", "alert_type", "symbol", "title",
            "message", "recommended_action", "confidence", "source_engine",
        ],
        rows=30,
    )

    # ---------------------------------------------------------
    # AI COMMAND CENTER V1 STATUS
    # ---------------------------------------------------------
    ai_command_actions_path = Path(
        ai_command_center_summary.get(
            "actions_csv",
            "reports/command_center/ai_command_center_actions.csv",
        )
    )

    ai_command_actions_view = read_optional_report(
        ai_command_actions_path
    )

    print_table(
        "AI COMMAND CENTER V1 — PRIORITY ACTIONS",
        ai_command_actions_view,
        [
            "rank",
            "priority",
            "category",
            "symbol",
            "action",
            "reason",
            "confidence",
            "severity",
            "source",
        ],
        rows=40,
    )

    # ---------------------------------------------------------
    # MARKET BREADTH ENGINE V1 STATUS
    # ---------------------------------------------------------
    market_breadth_summary_view = read_optional_report(
        Path(
            market_breadth_summary.get(
                "summary_csv",
                "reports/market_breadth/market_breadth_summary.csv",
            )
        )
    )

    market_breadth_sector_view = read_optional_report(
        Path(
            market_breadth_summary.get(
                "sector_csv",
                "reports/market_breadth/market_breadth_by_sector.csv",
            )
        )
    )

    print_table(
        "MARKET BREADTH ENGINE V1 — MARKET HEALTH",
        market_breadth_summary_view,
        [
            "trading_date",
            "total_symbols",
            "advancing",
            "declining",
            "unchanged",
            "advance_pct",
            "advance_decline_ratio",
            "average_change_pct",
            "up_volume_pct",
            "momentum_positive_pct",
            "ai_buy_count",
            "ai_buy_pct",
            "institutional_strength_pct",
            "upper_cap_count",
            "lower_cap_count",
            "bullish_sectors",
            "weak_sectors",
            "breadth_score",
            "breadth_label",
            "market_health_score",
            "market_health_label",
            "upper_cap_probability",
            "market_participation_status",
        ],
        rows=5,
    )

    print_table(
        "MARKET BREADTH ENGINE V1 — SECTOR BREADTH",
        market_breadth_sector_view,
        [
            "sector",
            "stocks",
            "advancing",
            "declining",
            "advance_pct",
            "average_change_pct",
            "total_volume",
            "up_volume_pct",
            "trend_positive_pct",
            "ai_strength_pct",
            "sector_breadth_score",
            "sector_breadth_label",
        ],
        rows=30,
    )

    # ---------------------------------------------------------
    # SMART MONEY TRACKER V2 STATUS
    # ---------------------------------------------------------
    smart_money_stocks_view = read_optional_report(
        Path(
            smart_money_summary.get(
                "stocks_csv",
                "reports/smart_money/smart_money_stocks.csv",
            )
        )
    )

    smart_money_sectors_view = read_optional_report(
        Path(
            smart_money_summary.get(
                "sectors_csv",
                "reports/smart_money/smart_money_by_sector.csv",
            )
        )
    )

    print_table(
        "SMART MONEY TRACKER V2 — TOP STOCKS",
        smart_money_stocks_view,
        [
            "rank",
            "symbol",
            "company",
            "sector",
            "close",
            "change_pct",
            "volume",
            "volume_ratio",
            "accumulation_score",
            "hidden_accumulation_score",
            "distribution_pressure",
            "breakout_quality_score",
            "breakout_quality",
            "retail_trap_score",
            "retail_trap_risk",
            "smart_money_score_v2",
            "smart_money_label",
            "recommended_action",
            "smart_money_reason",
        ],
        rows=30,
    )

    print_table(
        "SMART MONEY TRACKER V2 — SECTOR FLOW",
        smart_money_sectors_view,
        [
            "sector",
            "stocks",
            "average_smart_money_score",
            "average_accumulation_score",
            "average_distribution_pressure",
            "institutional_buying_count",
            "operator_accumulation_count",
            "hidden_accumulation_count",
            "distribution_count",
            "retail_trap_count",
            "sector_smart_money_label",
        ],
        rows=30,
    )

    # ---------------------------------------------------------
    # OPPORTUNITY RANKING ENGINE V1 STATUS
    # ---------------------------------------------------------
    opportunity_ranking_view = read_optional_report(
        Path(
            opportunity_ranking_summary.get(
                "ranked_csv",
                "reports/opportunity_ranking/opportunity_ranking.csv",
            )
        )
    )

    opportunity_categories_view = read_optional_report(
        Path(
            opportunity_ranking_summary.get(
                "categories_csv",
                "reports/opportunity_ranking/opportunity_categories.csv",
            )
        )
    )

    print_table(
        "OPPORTUNITY RANKING ENGINE V1 — TOP OPPORTUNITIES",
        opportunity_ranking_view,
        [
            "overall_rank",
            "symbol",
            "company",
            "sector",
            "close",
            "final_decision",
            "buy_probability",
            "smart_money_score",
            "trade_validation_score",
            "risk_permission",
            "risk_status",
            "entry_timing_action",
            "reward_risk_ratio",
            "opportunity_score",
            "opportunity_grade",
            "execution_bucket",
            "opportunity_type",
            "eligible_for_trade",
            "ranking_reason",
        ],
        rows=30,
    )

    print_table(
        "OPPORTUNITY RANKING ENGINE V1 — CATEGORY WINNERS",
        opportunity_categories_view,
        [
            "category",
            "symbol",
            "company",
            "sector",
            "opportunity_score",
            "buy_probability",
            "smart_money_score",
            "risk_score",
            "execution_bucket",
            "reason",
        ],
        rows=20,
    )

    # ---------------------------------------------------------
    # SECTOR TABLE
    # ---------------------------------------------------------
    print_table(
        "PSX SECTOR SUMMARY",
        sector_summary,
        [
            "sector",
            "stocks",
            "advancing",
            "declining",
            "avg_change",
            "total_volume",
            "avg_ai_score",
            "sector_score",
        ],
        rows=20,
    )

    # ---------------------------------------------------------
    # ENGINE STATUS
    # ---------------------------------------------------------
    print("Parser working ✅")
    print("SQLite Database working ✅")
    print("Historical Backfill Engine ready ✅")
    print("Daily Import Engine ready ✅")
    print("Latest Trading Data Engine V2 working ✅")
    print("Daily Data Manager V2 working ✅")
    print("History Engine V2 working ✅")
    print("Indicators calculated ✅")
    print("PSX Intelligence working ✅")
    print("Company Directory working ✅")
    print("Feature Builder V3 working ✅")
    print("AI Engine V5 raw working ✅")
    print("Institutional V5 Calibrator working ✅")
    print("Signal Consensus Engine V1 working ✅")
    print("Consensus Master Decision working ✅")
    print("Institutional Smart Money Engine working ✅")
    print("Decision Engine V2 working ✅")
    print("Trade Validation Engine working ✅")
    print("Entry Timing Engine working ✅")
    print("Risk Management Engine V2 working ✅")
    print("Feature Debug Engine working ✅")
    print("Portfolio Engine V5 Institutional working ✅")
    print("Market Breadth Engine V1 working ✅")
    print("Smart Money Tracker V2 working ✅")
    print("Opportunity Ranking Engine V1 working ✅")
    print("Trade Lifecycle Engine V1 working ✅")
    print("Exit Intelligence Engine V1 working ✅")
    print("Live Portfolio Monitor V1 working ✅")
    print("Equity Curve Engine V1 working ✅")
    print("Portfolio Analytics Pro V1 working ✅")
    print("Trade Journal Pro V1 working ✅")
    print("Strategy Analytics Engine V1 working ✅")
    print("Strategy Optimizer & Self-Learning Engine V2 working ✅")
    print("Institutional Alert Center V1 working ✅")
    print("AI Institutional Assistant V1 working ✅")
    print("AI Command Center V1 working ✅")
    print("Order Execution Simulator V1 manual mode ready ✅")
    print("Freshness Firewall V1 verified ✅")
    print("Signal Tracker V1 working ✅")
    print("Backtest Engine V1 working ✅")
    print("Performance Analyzer V1 working ✅")
    print("Learning Engine V1 working ✅")
    print("Reporting Engine V3 working ✅")
    print("Performance Dashboard V3 working ✅")
    print("Long-Term AI Engine working ✅")
    print("AI Master Database working ✅")

    print()
    print(f"Resolved trading date: {latest_date}")
    print(
        "Freshness status: "
        f"{final_freshness_summary.get('status')}"
    )
    print(
        "Verified trading date: "
        f"{final_freshness_summary.get('resolved_trading_date_iso')}"
    )
    print(f"Latest source file: {daily_data_summary.get('latest_file', args.file)}")
    print(f"Latest snapshot records: {len(today_df)}")
    print(f"Total history records: {len(history)}")
    print(f"Master records: {len(company_master)}")
    print(f"Report folder: {report_summary.get('folder')}")
    print(f"Latest folder: {report_summary.get('latest_folder')}")
    print(f"Latest summary: {report_summary.get('latest_summary_md')}")
    print(f"Latest top buys: {report_summary.get('latest_top_buys_csv')}")
    print(
        "Performance dashboard: "
        f"{dashboard_summary.get('dashboard', 'reports/dashboard/dashboard.html')}"
    )
    print(
        "Latest dashboard: "
        f"{dashboard_summary.get('latest_dashboard', 'reports/latest_dashboard_v3.html')}"
    )
    print(
        "Dashboard output folder: "
        f"{dashboard_summary.get('output_folder', 'reports/dashboard')}"
    )
    print(
        "Live portfolio positions: "
        f"{live_portfolio_summary.get('live_positions_csv', 'reports/live_portfolio/live_positions.csv')}"
    )
    print(
        "Live portfolio summary: "
        f"{live_portfolio_summary.get('portfolio_summary_csv', 'reports/live_portfolio/live_portfolio_summary.csv')}"
    )
    print(
        "Live open positions: "
        f"{live_portfolio_summary.get('open_positions_csv', 'database/portfolio/open_positions.csv')}"
    )
    print(
        "Live closed positions: "
        f"{live_portfolio_summary.get('closed_positions_csv', 'database/portfolio/closed_positions.csv')}"
    )
    print(
        "Order execution log: "
        "database/portfolio/execution_log.csv"
    )
    print(
        "Equity history: "
        f"{equity_curve_summary.get('equity_history_csv', 'database/portfolio/equity_history.csv')}"
    )
    print(
        "Daily equity curve: "
        f"{equity_curve_summary.get('daily_equity_curve_csv', 'reports/performance/daily_equity_curve.csv')}"
    )
    print(
        "Monthly returns: "
        f"{equity_curve_summary.get('monthly_returns_csv', 'reports/performance/monthly_returns.csv')}"
    )
    print(
        "Drawdown history: "
        f"{equity_curve_summary.get('drawdown_history_csv', 'reports/performance/drawdown_history.csv')}"
    )
    print(
        "Portfolio analytics: "
        f"{portfolio_analytics_summary.get('portfolio_analytics_csv', 'reports/portfolio_analytics/portfolio_analytics.csv')}"
    )
    print(
        "Sector exposure: "
        f"{portfolio_analytics_summary.get('sector_exposure_csv', 'reports/portfolio_analytics/sector_exposure.csv')}"
    )
    print(
        "Position risk contribution: "
        f"{portfolio_analytics_summary.get('position_risk_csv', 'reports/portfolio_analytics/position_risk_contribution.csv')}"
    )
    print(
        "Rebalancing suggestions: "
        f"{portfolio_analytics_summary.get('rebalancing_suggestions_csv', 'reports/portfolio_analytics/rebalancing_suggestions.csv')}"
    )
    print(
        "Portfolio analytics summary: "
        f"{portfolio_analytics_summary.get('summary_csv', 'reports/portfolio_analytics/portfolio_analytics_summary.csv')}"
    )
    print(
        "Trade journal: "
        f"{trade_journal_summary.get('journal_csv', 'reports/trade_journal/trade_journal.csv')}"
    )
    print(
        "Monthly trade journal: "
        f"{trade_journal_summary.get('monthly_summary_csv', 'reports/trade_journal/monthly_trade_journal.csv')}"
    )
    print(
        "Trade review queue: "
        f"{trade_journal_summary.get('review_queue_csv', 'reports/trade_journal/trade_review_queue.csv')}"
    )
    print(
        "Trade journal summary: "
        f"{trade_journal_summary.get('summary_csv', 'reports/trade_journal/trade_journal_summary.csv')}"
    )
    print(
        "Strategy analytics: "
        f"{strategy_analytics_summary.get('strategy_analytics_csv', 'reports/strategy_analytics/strategy_analytics.csv')}"
    )
    print(
        "Strategy leaderboard: "
        f"{strategy_analytics_summary.get('leaderboard_csv', 'reports/strategy_analytics/strategy_leaderboard.csv')}"
    )
    print(
        "Strategy monthly performance: "
        f"{strategy_analytics_summary.get('strategy_monthly_csv', 'reports/strategy_analytics/strategy_monthly.csv')}"
    )
    print(
        "Strategy equity: "
        f"{strategy_analytics_summary.get('strategy_equity_csv', 'reports/strategy_analytics/strategy_equity.csv')}"
    )
    print(
        "Strategy summary: "
        f"{strategy_analytics_summary.get('summary_csv', 'reports/strategy_analytics/strategy_summary.csv')}"
    )
    print(
        "Strategy optimizer output: "
        f"{strategy_optimizer_summary.get('optimizer_output_csv', 'reports/strategy_optimizer/strategy_optimizer_output.csv')}"
    )
    print(
        "Strategy weights V2: "
        f"{strategy_optimizer_summary.get('strategy_weights_csv', 'database/strategy_learning/strategy_weights_v2.csv')}"
    )
    print(
        "Strategy actions V2: "
        f"{strategy_optimizer_summary.get('strategy_actions_csv', 'reports/strategy_optimizer/strategy_actions_v2.csv')}"
    )
    print(
        "Strategy learning summary: "
        f"{strategy_optimizer_summary.get('learning_summary_csv', 'reports/strategy_optimizer/strategy_learning_summary.csv')}"
    )
    print(
        "Latest strategy weights JSON: "
        f"{strategy_optimizer_summary.get('latest_weights_json', 'database/strategy_learning/latest_strategy_weights.json')}"
    )
    print(
        "Live institutional alerts: "
        f"{institutional_alert_summary.get('live_alerts_csv', 'reports/alerts/live_alerts.csv')}"
    )
    print(
        "Critical institutional alerts: "
        f"{institutional_alert_summary.get('critical_alerts_csv', 'reports/alerts/critical_alerts.csv')}"
    )
    print(
        "Institutional alert summary: "
        f"{institutional_alert_summary.get('alert_summary_csv', 'reports/alerts/alert_summary.csv')}"
    )
    print(
        "Institutional alert history: "
        f"{institutional_alert_summary.get('alert_history_csv', 'reports/alerts/alert_history.csv')}"
    )
    print(
        "AI assistant report: "
        f"{ai_assistant_summary.get('assistant_report_csv', 'reports/ai_assistant/ai_institutional_assistant.csv')}"
    )
    print(
        "AI assistant actions: "
        f"{ai_assistant_summary.get('assistant_actions_csv', 'reports/ai_assistant/ai_institutional_actions.csv')}"
    )
    print(
        "AI assistant summary: "
        f"{ai_assistant_summary.get('assistant_summary_csv', 'reports/ai_assistant/ai_institutional_assistant_summary.csv')}"
    )
    print(
        "AI assistant brief: "
        f"{ai_assistant_summary.get('assistant_brief_md', 'reports/ai_assistant/ai_institutional_brief.md')}"
    )
    print(
        "AI command center snapshot: "
        f"{ai_command_center_summary.get('snapshot_csv', 'reports/command_center/ai_command_center_snapshot.csv')}"
    )
    print(
        "AI command center actions: "
        f"{ai_command_center_summary.get('actions_csv', 'reports/command_center/ai_command_center_actions.csv')}"
    )
    print(
        "AI command center summary: "
        f"{ai_command_center_summary.get('summary_csv', 'reports/command_center/ai_command_center_summary.csv')}"
    )
    print(
        "AI command center HTML: "
        f"{ai_command_center_summary.get('command_center_html', 'reports/command_center/ai_command_center.html')}"
    )
    print(
        "AI command center brief: "
        f"{ai_command_center_summary.get('command_center_md', 'reports/command_center/ai_command_center.md')}"
    )
    print(
        "Market breadth summary: "
        f"{market_breadth_summary.get('summary_csv', 'reports/market_breadth/market_breadth_summary.csv')}"
    )
    print(
        "Market breadth by sector: "
        f"{market_breadth_summary.get('sector_csv', 'reports/market_breadth/market_breadth_by_sector.csv')}"
    )
    print(
        "Market breadth HTML: "
        f"{market_breadth_summary.get('html', 'reports/market_breadth/market_breadth.html')}"
    )
    print(
        "Smart money summary: "
        f"{smart_money_summary.get('summary_csv', 'reports/smart_money/smart_money_summary.csv')}"
    )
    print(
        "Smart money stocks: "
        f"{smart_money_summary.get('stocks_csv', 'reports/smart_money/smart_money_stocks.csv')}"
    )
    print(
        "Smart money sectors: "
        f"{smart_money_summary.get('sectors_csv', 'reports/smart_money/smart_money_by_sector.csv')}"
    )
    print(
        "Smart money HTML: "
        f"{smart_money_summary.get('html', 'reports/smart_money/smart_money_tracker.html')}"
    )
    print(
        "Opportunity ranking: "
        f"{opportunity_ranking_summary.get('ranked_csv', 'reports/opportunity_ranking/opportunity_ranking.csv')}"
    )
    print(
        "Opportunity categories: "
        f"{opportunity_ranking_summary.get('categories_csv', 'reports/opportunity_ranking/opportunity_categories.csv')}"
    )
    print(
        "Top opportunities today: "
        f"{opportunity_ranking_summary.get('top_today_csv', 'reports/opportunity_ranking/top_opportunities_today.csv')}"
    )
    print(
        "Opportunity ranking HTML: "
        f"{opportunity_ranking_summary.get('html', 'reports/opportunity_ranking/opportunity_ranking.html')}"
    )
    print(
        "Manual order commands: "
        "python main.py --order-list | --execute-buy | --execute-sell"
    )
    print(
        "Signal history: "
        f"{signal_tracker_summary.get('history_file', 'database/backtesting/signal_history.csv')}"
    )
    print("Backtest reports: reports/backtests")
    print("Learning data: database/backtesting/learning")
    lifecycle_dashboard = trade_lifecycle_summary.get(
        "dashboard",
        {},
    )
    print(
        "Pending entries: "
        f"{lifecycle_dashboard.get('pending_entries', 0)}"
    )
    print(
        "Open positions: "
        f"{lifecycle_dashboard.get('open_positions', 0)}"
    )
    print(
        "Closed positions: "
        f"{lifecycle_dashboard.get('closed_positions', 0)}"
    )
    print(
        "Pending entries file: "
        f"{lifecycle_dashboard.get('pending_entries_file', 'database/portfolio/pending_entries.csv')}"
    )
    print(
        "Open positions file: "
        f"{lifecycle_dashboard.get('open_positions_file', 'database/portfolio/open_positions.csv')}"
    )
    print(
        "Closed positions file: "
        f"{lifecycle_dashboard.get('closed_positions_file', 'database/portfolio/closed_positions.csv')}"
    )
    print()

    # ---------------------------------------------------------
    # PORTFOLIO PLAN
    # ---------------------------------------------------------
    print_dict(
        "PORTFOLIO PLAN V5 INSTITUTIONAL + SIGNAL CONSENSUS",
        portfolio,
    )

    print_table(
        "PORTFOLIO TRADES V5 INSTITUTIONAL + SIGNAL CONSENSUS",
        portfolio.get("trades") if portfolio else None,
        [
            "rank",
            "symbol",
            "company",
            "sector",
            "industry",
            "final_decision",
            "final_score",
            "consensus_score",
            "consensus_confidence",
            "consensus_decision",
            "consensus_entry_action",
            "consensus_risk_level",
            "consensus_position_factor",
            "consensus_bullish_votes",
            "consensus_neutral_votes",
            "consensus_bearish_votes",
            "consensus_agreement_pct",
            "buy_probability",
            "portfolio_rank_score",
            "position_quality_index",
            "institutional_portfolio_score",
            "portfolio_fallback_candidate",
            "smart_money_score",
            "accumulation_score",
            "trade_validation_score",
            "entry_timing_score",
            "entry_timing_action",
            "risk_management_score",
            "risk_permission",
            "risk_status",
            "allocation_weight",
            "allocation_factor",
            "allocation",
            "quantity",
            "investment",
            "suggested_entry_price",
            "adjusted_entry_price",
            "entry_low",
            "entry_high",
            "stop_loss",
            "target_1",
            "target_2",
            "risk_per_share",
            "max_loss",
            "expected_profit_t1",
            "expected_profit_t2",
            "risk_reward_t1",
            "risk_pct_of_capital",
            "position_pct_of_capital",
            "position_status",
            "exit_plan",
            "position_reason",
        ],
        rows=10,
    )

    # ---------------------------------------------------------
    # SIGNAL CONSENSUS TABLE
    # ---------------------------------------------------------
    print_table(
        "SIGNAL CONSENSUS ENGINE V1 TOP PICKS",
        final,
        [
            "symbol",
            "company",
            "sector",
            "industry",
            "date",
            "close",
            "change_pct",
            "volume",
            "value_traded",
            "consensus_score",
            "consensus_confidence",
            "consensus_decision",
            "consensus_entry_action",
            "consensus_risk_level",
            "consensus_position_factor",
            "consensus_bullish_votes",
            "consensus_neutral_votes",
            "consensus_bearish_votes",
            "consensus_agreement_pct",
            "consensus_hard_block",
            "consensus_reason",
            "consensus_warnings",
            "final_decision",
            "final_score",
            "buy_probability",
            "smart_money_score",
            "trade_validation_score",
            "entry_timing_action",
            "risk_permission",
            "risk_status",
        ],
        rows=25,
    )

    # ---------------------------------------------------------
    # INSTITUTIONAL V5 PICKS
    # ---------------------------------------------------------
    print_table(
        "INSTITUTIONAL V5 TOP PICKS",
        final,
        [
            "symbol",
            "company",
            "sector",
            "industry",
            "date",
            "close",
            "change_pct",
            "volume",
            "value_traded",
            "institutional_v5_score",
            "institutional_v5_verdict",
            "institutional_v5_final_decision",
            "institutional_v5_win_probability",
            "institutional_v5_loss_probability",
            "institutional_v5_confidence",
            "institutional_v5_confidence_label",
            "institutional_v5_risk_grade",
            "institutional_v5_security_block",
            "institutional_v5_security_block_reason",
            "smart_money_score",
            "accumulation_score",
            "trade_validation_score",
            "entry_timing_score",
            "entry_timing_action_before_consensus",
            "risk_management_score",
            "risk_permission",
            "risk_status",
            "institutional_v5_reason",
        ],
        rows=25,
    )

    # ---------------------------------------------------------
    # SMART MONEY PICKS
    # ---------------------------------------------------------
    print_table(
        "INSTITUTIONAL SMART MONEY TOP PICKS",
        final,
        [
            "symbol",
            "company",
            "sector",
            "close",
            "change_pct",
            "volume",
            "volume_ratio_20",
            "value_traded",
            "smart_money_score",
            "accumulation_score",
            "distribution_score",
            "delivery_strength",
            "institutional_signal",
            "institutional_buy_probability",
            "institutional_sell_probability",
            "wyckoff_phase",
            "price_volume_divergence",
            "breakout_confirmation",
            "false_breakout_detection",
            "hidden_buying",
            "hidden_selling",
            "volume_climax",
            "dry_volume",
            "institutional_reasons",
            "institutional_warnings",
        ],
        rows=20,
    )

    # ---------------------------------------------------------
    # RISK PICKS
    # ---------------------------------------------------------
    print_table(
        "RISK MANAGEMENT TOP PICKS",
        final,
        [
            "symbol",
            "company",
            "sector",
            "close",
            "change_pct",
            "rsi",
            "final_score",
            "final_decision",
            "consensus_decision",
            "consensus_risk_level",
            "buy_probability",
            "smart_money_score",
            "institutional_signal",
            "trade_validation_score",
            "entry_timing_score",
            "entry_timing_action",
            "risk_management_score",
            "risk_permission",
            "risk_status",
            "risk_action",
            "position_risk_factor",
            "adjusted_entry_price",
            "risk_reward_t1",
            "stop_distance_pct",
            "risk_management_warnings",
        ],
        rows=20,
    )

    # ---------------------------------------------------------
    # ENTRY TIMING PICKS
    # ---------------------------------------------------------
    print_table(
        "ENTRY TIMING TOP PICKS",
        final,
        [
            "symbol",
            "company",
            "sector",
            "close",
            "change_pct",
            "rsi",
            "final_score",
            "final_decision",
            "consensus_decision",
            "consensus_entry_action",
            "buy_probability",
            "smart_money_score",
            "institutional_signal",
            "trade_validation_score",
            "trade_validation_status",
            "entry_timing_score",
            "entry_timing_action",
            "entry_timing_action_before_consensus",
            "entry_timing_status",
            "suggested_entry_type",
            "suggested_entry_price",
            "entry_low",
            "entry_high",
            "stop_loss",
            "target_1",
            "target_2",
            "entry_timing_warning",
        ],
        rows=20,
    )

    # ---------------------------------------------------------
    # TRADE VALIDATION PICKS
    # ---------------------------------------------------------
    print_table(
        "TRADE VALIDATION TOP PICKS",
        final,
        [
            "symbol",
            "company",
            "sector",
            "close",
            "final_score",
            "final_decision",
            "consensus_decision",
            "consensus_confidence",
            "buy_probability",
            "sell_probability",
            "smart_money_score",
            "institutional_signal",
            "trade_validation_score",
            "trade_validation_status",
            "trade_action",
            "risk_reward_t1",
            "entry_low",
            "entry_high",
            "stop_loss",
            "target_1",
            "target_2",
            "validation_warnings",
        ],
        rows=20,
    )

    # ---------------------------------------------------------
    # LONG-TERM PICKS
    # ---------------------------------------------------------
    print_table(
        "LONG TERM INVESTMENT PICKS",
        long_term_result,
        [
            "symbol",
            "company",
            "close",
            "long_term_score",
            "long_term_confidence",
            "long_term_verdict",
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
            "long_term_reason",
            "long_term_risk",
        ],
        rows=20,
    )

    # ---------------------------------------------------------
    # TRADE LIFECYCLE STATUS
    # ---------------------------------------------------------
    lifecycle_view = final.copy()

    if (
        lifecycle_view is not None
        and not lifecycle_view.empty
        and "lifecycle_status" in lifecycle_view.columns
    ):
        lifecycle_view = lifecycle_view[
            lifecycle_view["lifecycle_status"]
            .fillna("")
            .astype(str)
            .str.upper()
            .ne("NO POSITION")
        ].copy()

    print_table(
        "TRADE LIFECYCLE ENGINE V1 STATUS",
        lifecycle_view,
        [
            "symbol",
            "company",
            "sector",
            "date",
            "close",
            "portfolio_selected",
            "portfolio_position_status",
            "lifecycle_status",
            "trade_id",
            "actual_entry_price",
            "actual_quantity",
            "open_quantity",
            "remaining_quantity",
            "average_cost",
            "current_stop_loss",
            "highest_price_since_entry",
            "lowest_price_since_entry",
            "realized_profit_loss",
            "unrealized_profit_loss",
            "unrealized_profit_loss_pct",
            "holding_days_numeric",
            "partial_profit_booked",
        ],
        rows=25,
    )

    # ---------------------------------------------------------
    # LIVE PORTFOLIO MONITOR V1
    # ---------------------------------------------------------
    live_positions_path = Path(
        live_portfolio_summary.get(
            "live_positions_csv",
            "reports/live_portfolio/live_positions.csv",
        )
    )

    if (
        live_positions_path.exists()
        and live_positions_path.stat().st_size > 0
    ):
        try:
            live_positions_view = pd.read_csv(
                live_positions_path
            )
            live_positions_view = clean_duplicate_columns(
                live_positions_view
            )
        except (
            pd.errors.EmptyDataError,
            pd.errors.ParserError,
            UnicodeDecodeError,
        ):
            live_positions_view = pd.DataFrame()
    else:
        live_positions_view = pd.DataFrame()

    print_table(
        "LIVE PORTFOLIO MONITOR V1 STATUS",
        live_positions_view,
        [
            "trade_id",
            "symbol",
            "company",
            "sector",
            "entry_date",
            "actual_entry_price",
            "average_cost",
            "original_quantity",
            "remaining_quantity",
            "current_price",
            "market_value",
            "cost_value",
            "initial_stop_loss",
            "current_stop_loss",
            "target_1",
            "target_2",
            "target_1_hit",
            "target_2_hit",
            "highest_price_since_entry",
            "lowest_price_since_entry",
            "realized_profit_loss",
            "unrealized_profit_loss",
            "unrealized_profit_loss_pct",
            "total_profit_loss",
            "risk_amount_to_stop",
            "profit_lock_pct",
            "holding_days",
            "position_status",
            "position_event",
            "recommended_action",
            "last_market_date",
            "last_updated_at",
        ],
        rows=25,
    )

    # ---------------------------------------------------------
    # EXIT INTELLIGENCE
    # ---------------------------------------------------------
    exit_view = final.copy()

    if (
        exit_view is not None
        and not exit_view.empty
        and "portfolio_selected" in exit_view.columns
    ):
        selected_exit_view = exit_view[
            exit_view["portfolio_selected"].fillna(False).astype(bool)
        ].copy()

        if not selected_exit_view.empty:
            exit_view = selected_exit_view

    print_table(
        "EXIT INTELLIGENCE ENGINE V1",
        exit_view,
        [
            "symbol",
            "company",
            "sector",
            "date",
            "close",
            "portfolio_selected",
            "portfolio_quantity",
            "portfolio_position_status",
            "lifecycle_status",
            "trade_id",
            "actual_entry_price",
            "actual_quantity",
            "open_quantity",
            "remaining_quantity",
            "adjusted_entry_price",
            "stop_loss",
            "target_1",
            "target_2",
            "exit_action",
            "exit_reason",
            "exit_risk_level",
            "exit_current_price",
            "exit_entry_price",
            "exit_profit_loss_pct",
            "exit_original_stop_loss",
            "exit_suggested_stop_loss",
            "exit_trailing_stop",
            "exit_profit_lock_pct",
            "exit_target_status",
            "exit_confidence",
            "exit_engine_version",
        ],
        rows=25,
    )

    # ---------------------------------------------------------
    # FINAL RECOMMENDATIONS
    # ---------------------------------------------------------
    print_table(
        "FINAL SHORT TERM TRADE RECOMMENDATIONS",
        final,
        [
            "symbol",
            "company",
            "sector",
            "industry",
            "date",
            "close",
            "change_pct",
            "volume",
            "consensus_score",
            "consensus_confidence",
            "consensus_decision",
            "consensus_entry_action",
            "consensus_risk_level",
            "consensus_position_factor",
            "consensus_agreement_pct",
            "base_ai_score",
            "ai_score",
            "final_probability",
            "confidence",
            "ai_engine_version",
            "adaptive_ai_score",
            "adaptive_verdict",
            "buy_probability",
            "sell_probability",
            "trend_score_v4",
            "trend_score_v5",
            "trend_label_v5",
            "momentum_score_v4",
            "volume_score_v4",
            "liquidity_score_v4",
            "risk_score_v4",
            "market_score_v4",
            "sector_score_v4",
            "smart_money_score",
            "accumulation_score",
            "distribution_score",
            "institutional_signal",
            "institutional_buy_probability",
            "institutional_sell_probability",
            "wyckoff_phase",
            "trade_validation_score",
            "trade_validation_status",
            "trade_action",
            "entry_timing_score",
            "entry_timing_action",
            "entry_timing_status",
            "suggested_entry_type",
            "suggested_entry_price",
            "risk_management_score",
            "risk_permission",
            "risk_status",
            "risk_action",
            "position_risk_factor",
            "adjusted_entry_price",
            "risk_reward_t1",
            "model_version",
            "confidence_v3",
            "confidence_label",
            "market_strength_score",
            "sector_strength_score",
            "sector_rank",
            "sector_score",
            "market_score",
            "market_mood",
            "final_score",
            "verdict",
            "risk_level",
            "final_decision",
            "decision_reason",
            "portfolio_selected",
            "portfolio_rank",
            "portfolio_investment",
            "portfolio_quantity",
            "portfolio_position_status",
            "lifecycle_status",
            "trade_id",
            "actual_entry_price",
            "actual_quantity",
            "open_quantity",
            "remaining_quantity",
            "average_cost",
            "current_stop_loss",
            "highest_price_since_entry",
            "lowest_price_since_entry",
            "realized_profit_loss",
            "unrealized_profit_loss",
            "unrealized_profit_loss_pct",
            "holding_days_numeric",
            "partial_profit_booked",
            "recommended_capital",
            "quantity",
            "entry_low",
            "entry_high",
            "stop_loss",
            "target_1",
            "target_2",
            "holding_days",
            "exit_action",
            "exit_reason",
            "exit_risk_level",
            "exit_suggested_action",
            "exit_current_price",
            "exit_entry_price",
            "exit_profit_loss_pct",
            "exit_original_stop_loss",
            "exit_suggested_stop_loss",
            "exit_trailing_stop",
            "exit_profit_lock_pct",
            "exit_target_status",
            "exit_confidence",
            "exit_engine_version",
        ],
        rows=25,
    )

    # ---------------------------------------------------------
    # GIT-COMMIT-ON-REFRESH (Deploy Priority 1, item 2)
    # With --publish, commit + push the small output files so the deployed
    # Render API picks up fresh data. Best-effort: a publish failure never
    # fails the scan (the reports are already written locally either way).
    # ---------------------------------------------------------
    if getattr(args, "publish", False):
        try:
            from tools.publish_outputs import publish as publish_outputs

            publish_outputs(push=True)
        except Exception as exc:
            print(
                "[PUBLISH] skipped (non-fatal): "
                f"{type(exc).__name__}: {exc}"
            )


if __name__ == "__main__":
    main()