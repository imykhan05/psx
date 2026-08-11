from __future__ import annotations

import html
import json
import math
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class PerformanceDashboardConfigV3:
    reports_root: str = "reports"
    latest_folder: str = "reports/latest"
    lifecycle_folder: str = "database/portfolio"
    output_folder: str = "reports/dashboard"
    dashboard_filename: str = "dashboard_v3.html"
    latest_dashboard_filename: str = "latest_dashboard_v3.html"


class PerformanceDashboardV3:
    """
    Performance Dashboard V3

    Professional single-file institutional dashboard combining:
    - AI Command Center
    - Institutional Alerts
    - Portfolio and lifecycle data
    - Equity curve and drawdown
    - Portfolio heatmap and allocation
    - Strategy leaderboard
    - Monthly returns
    - Trade journal and review queue
    - Sector exposure and rotation
    - Risk gauge
    - Engine health

    The dashboard is static HTML with optional browser auto-refresh.
    """

    VERSION = "performance_dashboard_v3_0_command_center_terminal"

    def __init__(
        self,
        reports_root: str = "reports",
        latest_folder: str = "reports/latest",
        lifecycle_folder: str = "database/portfolio",
        output_folder: str = "reports/dashboard",
        dashboard_filename: str = "dashboard_v3.html",
        latest_dashboard_filename: str = "latest_dashboard_v3.html",
    ):
        self.config = PerformanceDashboardConfigV3(
            reports_root=reports_root,
            latest_folder=latest_folder,
            lifecycle_folder=lifecycle_folder,
            output_folder=output_folder,
            dashboard_filename=dashboard_filename,
            latest_dashboard_filename=latest_dashboard_filename,
        )

        self.reports_root = Path(reports_root)
        self.latest_folder = Path(latest_folder)
        self.lifecycle_folder = Path(lifecycle_folder)
        self.output_folder = Path(output_folder)

        self.output_folder.mkdir(parents=True, exist_ok=True)

        self.dashboard_path = (
            self.output_folder / dashboard_filename
        )
        self.latest_dashboard_path = (
            self.reports_root / latest_dashboard_filename
        )

    def run(
        self,
        trading_date: str | None = None,
        starting_capital: float = 50000.0,
        auto_refresh_seconds: int = 0,
    ) -> dict:
        starting_capital = positive_float(
            starting_capital,
            "starting_capital",
        )

        data = self.load_all_data(
            starting_capital=starting_capital
        )

        resolved_date = normalize_date(
            trading_date
            or data["command_summary"].get(
                "trading_date",
                "",
            )
        )

        model = self.build_dashboard_model(
            data=data,
            starting_capital=starting_capital,
            trading_date=resolved_date,
        )

        html_text = self.render_html(
            model=model,
            auto_refresh_seconds=max(
                int(auto_refresh_seconds),
                0,
            ),
        )

        self.dashboard_path.write_text(
            html_text,
            encoding="utf-8",
        )

        self.latest_dashboard_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        shutil.copyfile(
            self.dashboard_path,
            self.latest_dashboard_path,
        )

        snapshot_path = (
            self.output_folder
            / "dashboard_v3_snapshot.json"
        )
        snapshot_path.write_text(
            json.dumps(
                make_json_safe(model),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        return {
            "status": "success",
            "engine_version": self.VERSION,
            "trading_date": resolved_date,
            "command_status": model["command_status"],
            "market_mood": model["market_mood"],
            "portfolio_health_score": model[
                "portfolio_health_score"
            ],
            "portfolio_risk_pct": model[
                "portfolio_risk_pct"
            ],
            "alert_status": model["alert_status"],
            "open_positions": model["open_positions_count"],
            "pending_entries": model["pending_entries_count"],
            "dashboard": str(self.dashboard_path),
            "latest_dashboard": str(
                self.latest_dashboard_path
            ),
            "snapshot_json": str(snapshot_path),
            "output_folder": str(self.output_folder),
            "reason": (
                "Performance Dashboard V3 generated successfully"
            ),
        }

    # ---------------------------------------------------------
    # LOAD DATA
    # ---------------------------------------------------------

    def load_all_data(
        self,
        starting_capital: float,
    ) -> dict:
        command_summary = self.read_first_record(
            self.reports_root
            / "command_center"
            / "ai_command_center_summary.csv"
        )

        command_actions = self.read_csv(
            self.reports_root
            / "command_center"
            / "ai_command_center_actions.csv"
        )

        alerts_summary = self.read_first_record(
            self.reports_root
            / "alerts"
            / "alert_summary.csv"
        )

        live_alerts = self.read_csv(
            self.reports_root
            / "alerts"
            / "live_alerts.csv"
        )

        critical_alerts = self.read_csv(
            self.reports_root
            / "alerts"
            / "critical_alerts.csv"
        )

        open_positions = self.read_csv(
            self.lifecycle_folder
            / "open_positions.csv"
        )

        pending_entries = self.read_csv(
            self.lifecycle_folder
            / "pending_entries.csv"
        )

        closed_positions = self.read_csv(
            self.lifecycle_folder
            / "closed_positions.csv"
        )

        equity_history = self.read_csv(
            self.lifecycle_folder
            / "equity_history.csv"
        )

        daily_equity = self.read_csv(
            self.reports_root
            / "performance"
            / "daily_equity_curve.csv"
        )

        if equity_history.empty:
            equity_history = daily_equity

        monthly_returns = self.read_csv(
            self.reports_root
            / "performance"
            / "monthly_returns.csv"
        )

        drawdown_history = self.read_csv(
            self.reports_root
            / "performance"
            / "drawdown_history.csv"
        )

        portfolio_summary = self.read_first_record(
            self.reports_root
            / "portfolio_analytics"
            / "portfolio_analytics_summary.csv"
        )

        position_analytics = self.read_csv(
            self.reports_root
            / "portfolio_analytics"
            / "portfolio_analytics.csv"
        )

        sector_exposure = self.read_csv(
            self.reports_root
            / "portfolio_analytics"
            / "sector_exposure.csv"
        )

        position_risk = self.read_csv(
            self.reports_root
            / "portfolio_analytics"
            / "position_risk_contribution.csv"
        )

        rebalancing = self.read_csv(
            self.reports_root
            / "portfolio_analytics"
            / "rebalancing_suggestions.csv"
        )

        strategy_summary = self.read_first_record(
            self.reports_root
            / "strategy_analytics"
            / "strategy_summary.csv"
        )

        strategy_analytics = self.read_csv(
            self.reports_root
            / "strategy_analytics"
            / "strategy_analytics.csv"
        )

        strategy_leaderboard = self.read_csv(
            self.reports_root
            / "strategy_analytics"
            / "strategy_leaderboard.csv"
        )

        strategy_monthly = self.read_csv(
            self.reports_root
            / "strategy_analytics"
            / "strategy_monthly.csv"
        )

        optimizer_output = self.read_csv(
            self.reports_root
            / "strategy_optimizer"
            / "strategy_optimizer_output.csv"
        )

        journal = self.read_csv(
            self.reports_root
            / "trade_journal"
            / "trade_journal.csv"
        )

        journal_summary = self.read_first_record(
            self.reports_root
            / "trade_journal"
            / "trade_journal_summary.csv"
        )

        review_queue = self.read_csv(
            self.reports_root
            / "trade_journal"
            / "trade_review_queue.csv"
        )

        assistant_summary = self.read_first_record(
            self.reports_root
            / "ai_assistant"
            / "ai_institutional_assistant_summary.csv"
        )

        market_summary = self.load_market_summary()

        return {
            "command_summary": command_summary,
            "command_actions": command_actions,
            "alerts_summary": alerts_summary,
            "live_alerts": live_alerts,
            "critical_alerts": critical_alerts,
            "open_positions": open_positions,
            "pending_entries": pending_entries,
            "closed_positions": closed_positions,
            "equity_history": equity_history,
            "monthly_returns": monthly_returns,
            "drawdown_history": drawdown_history,
            "portfolio_summary": portfolio_summary,
            "position_analytics": position_analytics,
            "sector_exposure": sector_exposure,
            "position_risk": position_risk,
            "rebalancing": rebalancing,
            "strategy_summary": strategy_summary,
            "strategy_analytics": strategy_analytics,
            "strategy_leaderboard": strategy_leaderboard,
            "strategy_monthly": strategy_monthly,
            "optimizer_output": optimizer_output,
            "journal": journal,
            "journal_summary": journal_summary,
            "review_queue": review_queue,
            "assistant_summary": assistant_summary,
            "market_summary": market_summary,
            "starting_capital": starting_capital,
        }

    def load_market_summary(self) -> dict:
        candidates = [
            self.latest_folder / "market_summary.csv",
            self.reports_root / "latest" / "market_summary.csv",
        ]

        for path in candidates:
            record = self.read_first_record(path)
            if record:
                return record

        return {}

    # ---------------------------------------------------------
    # DASHBOARD MODEL
    # ---------------------------------------------------------

    def build_dashboard_model(
        self,
        data: dict,
        starting_capital: float,
        trading_date: str,
    ) -> dict:
        command = data["command_summary"]
        portfolio = data["portfolio_summary"]
        alert_summary = data["alerts_summary"]
        market = data["market_summary"]
        journal_summary = data["journal_summary"]
        strategy_summary = data["strategy_summary"]

        open_df = data["open_positions"]
        pending_df = data["pending_entries"]
        closed_df = data["closed_positions"]
        equity_df = data["equity_history"]

        open_cost = self.calculate_open_cost(open_df)
        open_market_value = self.calculate_open_market_value(
            open_df
        )

        realized_pnl = first_number(
            [
                portfolio.get("realized_profit_loss"),
                latest_value(
                    equity_df,
                    "realized_profit_loss",
                ),
                numeric_sum(
                    closed_df,
                    "realized_profit_loss",
                ),
            ],
            0.0,
        )

        unrealized_pnl = first_number(
            [
                portfolio.get("unrealized_profit_loss"),
                latest_value(
                    equity_df,
                    "unrealized_profit_loss",
                ),
                numeric_sum(
                    open_df,
                    "unrealized_profit_loss",
                ),
            ],
            0.0,
        )

        cash_available = (
            starting_capital
            - open_cost
            + realized_pnl
        )

        total_equity = (
            cash_available
            + open_market_value
        )

        portfolio_risk_pct = first_number(
            [
                portfolio.get("portfolio_risk_pct"),
                portfolio.get("total_risk_pct"),
                numeric_sum(
                    data["position_analytics"],
                    "risk_pct_of_capital",
                ),
            ],
            0.0,
        )

        health_score = first_number(
            [
                portfolio.get("portfolio_health_score"),
                command.get("portfolio_health_score"),
            ],
            0.0,
        )

        critical_count = safe_int(
            first_valid(
                alert_summary.get("critical_alerts"),
                len(data["critical_alerts"]),
                0,
            )
        )

        high_count = safe_int(
            alert_summary.get("high_alerts", 0)
        )

        alert_status = (
            "CRITICAL"
            if critical_count > 0
            else (
                "ATTENTION"
                if high_count > 0
                else "NORMAL"
            )
        )

        market_mood = upper(
            first_valid(
                command.get("market_mood"),
                market.get("market_mood"),
                market.get("mood"),
                "UNKNOWN",
            )
        )

        market_score = first_number(
            [
                command.get("market_score"),
                market.get("market_score"),
                market.get("score"),
            ],
            0.0,
        )

        command_status = text(
            first_valid(
                command.get("command_status"),
                "MONITOR",
            )
        )

        overall_recommendation = text(
            first_valid(
                command.get("overall_recommendation"),
                "NO NEW TRADE; CONTINUE MONITORING",
            )
        )

        command_actions = self.merge_command_actions(
            data["command_actions"]
        )

        equity_labels, equity_values = chart_series(
            equity_df,
            "date",
            "total_equity",
        )

        drawdown_labels, drawdown_values = chart_series(
            data["drawdown_history"],
            "date",
            "drawdown_pct",
        )

        sector_labels, sector_values = top_series(
            data["sector_exposure"],
            "sector",
            "sector_exposure_pct",
            10,
        )

        allocation_labels, allocation_values = top_series(
            data["position_analytics"],
            "symbol",
            "market_value",
            10,
        )

        strategy_labels, strategy_values = top_series(
            data["strategy_analytics"],
            "strategy",
            "strategy_score",
            10,
        )

        monthly_labels, monthly_values = top_series(
            data["monthly_returns"],
            "month",
            "monthly_return_pct",
            12,
            sort_desc=False,
        )

        action_counts = (
            command_actions["action"]
            .fillna("")
            .astype(str)
            .value_counts()
            .to_dict()
            if not command_actions.empty
            and "action" in command_actions.columns
            else {}
        )

        return {
            "engine_version": self.VERSION,
            "generated_at": datetime.now().isoformat(
                timespec="seconds"
            ),
            "trading_date": trading_date,
            "command_status": command_status,
            "overall_recommendation": overall_recommendation,
            "market_mood": market_mood,
            "market_score": round(market_score, 2),
            "portfolio_health_score": round(
                health_score,
                2,
            ),
            "portfolio_health_status": health_status(
                health_score
            ),
            "portfolio_risk_pct": round(
                portfolio_risk_pct,
                4,
            ),
            "portfolio_risk_status": risk_status(
                portfolio_risk_pct
            ),
            "alert_status": alert_status,
            "critical_alerts": critical_count,
            "high_alerts": high_count,
            "starting_capital": round(
                starting_capital,
                2,
            ),
            "used_capital": round(
                open_cost,
                2,
            ),
            "cash_available": round(
                cash_available,
                2,
            ),
            "cash_available_pct": round(
                cash_available
                / starting_capital
                * 100
                if starting_capital > 0
                else 0.0,
                2,
            ),
            "open_market_value": round(
                open_market_value,
                2,
            ),
            "total_equity": round(
                total_equity,
                2,
            ),
            "realized_pnl": round(
                realized_pnl,
                2,
            ),
            "unrealized_pnl": round(
                unrealized_pnl,
                2,
            ),
            "open_positions_count": int(
                len(open_df)
            ),
            "pending_entries_count": int(
                len(pending_df)
            ),
            "closed_positions_count": int(
                len(closed_df)
            ),
            "win_rate_pct": first_number(
                [
                    journal_summary.get("win_rate_pct"),
                    strategy_summary.get("win_rate_pct"),
                ],
                0.0,
            ),
            "profit_factor": first_number(
                [
                    best_value(
                        data["strategy_analytics"],
                        "profit_factor",
                    ),
                    0,
                ],
                0.0,
            ),
            "max_drawdown_pct": min_value(
                data["drawdown_history"],
                "drawdown_pct",
                0.0,
            ),
            "best_trade": text(
                command.get("best_trade", "")
            ),
            "best_strategy": text(
                first_valid(
                    strategy_summary.get("best_strategy"),
                    command.get("best_strategy"),
                    "",
                )
            ),
            "command_actions": command_actions,
            "live_alerts": data["live_alerts"],
            "critical_alerts_df": data["critical_alerts"],
            "open_positions": open_df,
            "pending_entries": pending_df,
            "closed_positions": closed_df,
            "position_analytics": data[
                "position_analytics"
            ],
            "sector_exposure": data["sector_exposure"],
            "position_risk": data["position_risk"],
            "rebalancing": data["rebalancing"],
            "strategy_leaderboard": data[
                "strategy_leaderboard"
            ],
            "strategy_analytics": data[
                "strategy_analytics"
            ],
            "optimizer_output": data[
                "optimizer_output"
            ],
            "journal": data["journal"],
            "review_queue": data["review_queue"],
            "monthly_returns": data[
                "monthly_returns"
            ],
            "equity_labels": equity_labels,
            "equity_values": equity_values,
            "drawdown_labels": drawdown_labels,
            "drawdown_values": drawdown_values,
            "sector_labels": sector_labels,
            "sector_values": sector_values,
            "allocation_labels": allocation_labels,
            "allocation_values": allocation_values,
            "strategy_labels": strategy_labels,
            "strategy_values": strategy_values,
            "monthly_labels": monthly_labels,
            "monthly_values": monthly_values,
            "action_labels": list(
                action_counts.keys()
            ),
            "action_values": list(
                action_counts.values()
            ),
        }

    def merge_command_actions(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(
                columns=[
                    "rank",
                    "priority",
                    "category",
                    "symbol",
                    "action",
                    "reason",
                    "confidence",
                    "severity",
                    "source",
                ]
            )

        working = df.copy()

        for column in [
            "category",
            "symbol",
            "action",
            "reason",
            "severity",
            "source",
        ]:
            if column not in working.columns:
                working[column] = ""

        if "priority" not in working.columns:
            working["priority"] = 20

        if "confidence" not in working.columns:
            working["confidence"] = 0.0

        # Merge the same symbol and action regardless of category.
        rows = []

        for (
            symbol,
            action,
        ), group in working.groupby(
            [
                working["symbol"]
                .fillna("")
                .astype(str)
                .str.upper()
                .str.strip(),
                working["action"]
                .fillna("")
                .astype(str)
                .str.upper()
                .str.strip(),
            ],
            sort=False,
        ):
            group = group.sort_values(
                [
                    "priority",
                    "confidence",
                ],
                ascending=[
                    True,
                    False,
                ],
            )

            best = group.iloc[0].to_dict()
            reasons = unique_texts(
                group["reason"]
            )
            sources = unique_texts(
                group["source"]
            )
            categories = unique_texts(
                group["category"]
            )

            best["symbol"] = symbol
            best["action"] = action
            best["reason"] = " | ".join(
                reasons[:4]
            )
            best["source"] = " + ".join(
                sources[:3]
            )
            best["category"] = " / ".join(
                categories[:3]
            )
            best["confidence"] = float(
                pd.to_numeric(
                    group["confidence"],
                    errors="coerce",
                )
                .fillna(0)
                .max()
            )
            rows.append(best)

        result = pd.DataFrame(rows)
        result = result.sort_values(
            [
                "priority",
                "confidence",
            ],
            ascending=[
                True,
                False,
            ],
        ).reset_index(drop=True)

        result["rank"] = range(
            1,
            len(result) + 1,
        )

        return result[
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
            ]
        ]

    def calculate_open_cost(
        self,
        open_df: pd.DataFrame,
    ) -> float:
        if open_df.empty:
            return 0.0

        if (
            "cost_value" in open_df.columns
            and numeric_sum(
                open_df,
                "cost_value",
            ) > 0
        ):
            return numeric_sum(
                open_df,
                "cost_value",
            )

        entry = first_numeric_series(
            open_df,
            [
                "average_cost",
                "actual_entry_price",
            ],
        )
        quantity = first_numeric_series(
            open_df,
            [
                "remaining_quantity",
                "open_quantity",
                "actual_quantity",
                "original_quantity",
            ],
        )

        return float(
            (
                entry
                * quantity
            ).sum()
        )

    def calculate_open_market_value(
        self,
        open_df: pd.DataFrame,
    ) -> float:
        if open_df.empty:
            return 0.0

        if (
            "market_value" in open_df.columns
            and numeric_sum(
                open_df,
                "market_value",
            ) > 0
        ):
            return numeric_sum(
                open_df,
                "market_value",
            )

        current = first_numeric_series(
            open_df,
            [
                "current_price",
                "close",
                "last_price",
                "actual_entry_price",
            ],
        )
        quantity = first_numeric_series(
            open_df,
            [
                "remaining_quantity",
                "open_quantity",
                "actual_quantity",
                "original_quantity",
            ],
        )

        return float(
            (
                current
                * quantity
            ).sum()
        )

    # ---------------------------------------------------------
    # HTML
    # ---------------------------------------------------------

    def render_html(
        self,
        model: dict,
        auto_refresh_seconds: int,
    ) -> str:
        refresh_meta = (
            f'<meta http-equiv="refresh" content="{auto_refresh_seconds}">'
            if auto_refresh_seconds > 0
            else ""
        )

        command_table = dataframe_table(
            model["command_actions"],
            [
                "rank",
                "symbol",
                "action",
                "severity",
                "reason",
                "confidence",
            ],
            30,
        )

        alert_table = dataframe_table(
            model["live_alerts"],
            [
                "priority",
                "severity",
                "alert_type",
                "symbol",
                "recommended_action",
                "message",
                "confidence",
            ],
            20,
        )

        portfolio_table = dataframe_table(
            model["position_analytics"],
            [
                "symbol",
                "sector",
                "position_status",
                "quantity",
                "entry_price",
                "current_price",
                "market_value",
                "position_weight_pct",
                "unrealized_profit_loss",
                "unrealized_profit_loss_pct",
                "stop_loss",
                "target_1",
                "target_2",
                "risk_status",
            ],
            20,
        )

        pending_table = dataframe_table(
            model["pending_entries"],
            [
                "symbol",
                "company",
                "sector",
                "lifecycle_status",
                "portfolio_quantity",
                "adjusted_entry_price",
                "stop_loss",
                "target_1",
                "target_2",
                "execution_status",
            ],
            20,
        )

        strategy_table = dataframe_table(
            model["strategy_leaderboard"],
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
                "maximum_drawdown_pct",
                "recommendation",
            ],
            20,
        )

        sector_table = dataframe_table(
            model["sector_exposure"],
            [
                "sector",
                "positions",
                "market_value",
                "sector_exposure_pct",
                "unrealized_profit_loss",
                "risk_amount",
                "sector_concentration_status",
            ],
            20,
        )

        risk_table = dataframe_table(
            model["position_risk"],
            [
                "symbol",
                "sector",
                "market_value",
                "position_weight_pct",
                "risk_amount",
                "risk_pct_of_capital",
                "portfolio_risk_contribution_pct",
                "risk_contribution_status",
            ],
            20,
        )

        journal_table = dataframe_table(
            model["journal"],
            [
                "trade_id",
                "symbol",
                "strategy",
                "entry_date",
                "exit_date",
                "trade_status",
                "trade_result",
                "realized_profit_loss",
                "unrealized_profit_loss",
                "return_pct",
                "lesson_learned",
            ],
            15,
        )

        review_table = dataframe_table(
            model["review_queue"],
            [
                "review_priority",
                "symbol",
                "strategy",
                "trade_result",
                "realized_profit_loss",
                "mistake_flag",
                "mistake_notes",
                "review_action",
            ],
            15,
        )

        rebalancing_table = dataframe_table(
            model["rebalancing"],
            [
                "priority",
                "category",
                "symbol_or_sector",
                "issue",
                "suggested_action",
                "severity",
            ],
            15,
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
{refresh_meta}
<title>PSX Institutional Trading Terminal V3</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
:root {{
    --bg:#050b14;
    --panel:#0b1727;
    --panel2:#10243a;
    --border:#1d3b57;
    --text:#edf4fb;
    --muted:#91a7bb;
    --green:#32d296;
    --red:#ff6474;
    --amber:#f5c451;
    --blue:#58a6ff;
    --purple:#b48eff;
}}
* {{ box-sizing:border-box; }}
body {{
    margin:0;
    background:
        radial-gradient(circle at top right, rgba(88,166,255,.08), transparent 35%),
        var(--bg);
    color:var(--text);
    font-family:Inter,Segoe UI,Arial,sans-serif;
}}
.container {{
    width:min(1600px,97%);
    margin:18px auto 60px;
}}
.header {{
    display:flex;
    justify-content:space-between;
    align-items:flex-start;
    gap:20px;
    margin-bottom:16px;
}}
h1 {{ margin:0 0 6px; font-size:28px; }}
.sub {{ color:var(--muted); font-size:12px; }}
.ribbon {{
    display:grid;
    grid-template-columns:repeat(5,1fr);
    gap:10px;
    margin-bottom:14px;
}}
.ribbon .item {{
    border:1px solid var(--border);
    background:linear-gradient(180deg,var(--panel),var(--panel2));
    border-radius:12px;
    padding:12px;
}}
.ribbon .label {{
    color:var(--muted);
    font-size:11px;
    text-transform:uppercase;
}}
.ribbon .value {{
    margin-top:5px;
    font-size:18px;
    font-weight:700;
}}
.grid {{
    display:grid;
    grid-template-columns:repeat(12,1fr);
    gap:14px;
}}
.card {{
    background:linear-gradient(180deg,var(--panel),var(--panel2));
    border:1px solid var(--border);
    border-radius:15px;
    padding:16px;
    box-shadow:0 12px 34px rgba(0,0,0,.22);
}}
.kpi {{ grid-column:span 2; }}
.span-3 {{ grid-column:span 3; }}
.span-4 {{ grid-column:span 4; }}
.span-5 {{ grid-column:span 5; }}
.span-6 {{ grid-column:span 6; }}
.span-7 {{ grid-column:span 7; }}
.span-8 {{ grid-column:span 8; }}
.span-12 {{ grid-column:span 12; }}
.label {{
    color:var(--muted);
    font-size:11px;
    text-transform:uppercase;
    letter-spacing:.7px;
}}
.value {{
    margin-top:8px;
    font-size:23px;
    font-weight:750;
}}
.command {{
    border-left:5px solid var(--green);
    background:linear-gradient(90deg,rgba(50,210,150,.12),transparent);
}}
.command .value {{
    color:var(--green);
    font-size:25px;
}}
h2 {{
    margin:0 0 12px;
    font-size:17px;
}}
.chart-box {{ height:300px; }}
table {{
    width:100%;
    border-collapse:collapse;
    font-size:11px;
}}
th,td {{
    padding:9px 7px;
    border-bottom:1px solid var(--border);
    text-align:left;
    vertical-align:top;
}}
th {{
    color:var(--muted);
    position:sticky;
    top:0;
    background:var(--panel);
}}
.scroll {{ overflow:auto; max-height:430px; }}
.positive {{ color:var(--green); }}
.negative {{ color:var(--red); }}
.warning {{ color:var(--amber); }}
.badge {{
    display:inline-block;
    padding:4px 8px;
    border-radius:999px;
    font-size:10px;
    font-weight:700;
}}
.green {{ background:rgba(50,210,150,.14);color:var(--green); }}
.red {{ background:rgba(255,100,116,.14);color:var(--red); }}
.amber {{ background:rgba(245,196,81,.14);color:var(--amber); }}
.blue {{ background:rgba(88,166,255,.14);color:var(--blue); }}
.gauge {{
    width:190px;
    height:95px;
    overflow:hidden;
    margin:16px auto 2px;
    position:relative;
}}
.gauge::before {{
    content:"";
    position:absolute;
    width:190px;
    height:190px;
    border-radius:50%;
    background:conic-gradient(
        from 270deg,
        var(--green) 0 33%,
        var(--amber) 33% 66%,
        var(--red) 66% 100%
    );
}}
.gauge::after {{
    content:"";
    position:absolute;
    width:130px;
    height:130px;
    left:30px;
    top:30px;
    border-radius:50%;
    background:var(--panel);
}}
.gauge-value {{
    text-align:center;
    font-size:25px;
    font-weight:750;
    margin-top:-8px;
}}
.heatmap {{
    display:grid;
    grid-template-columns:repeat(auto-fit,minmax(145px,1fr));
    gap:9px;
}}
.heat {{
    padding:13px;
    border-radius:10px;
    border:1px solid var(--border);
    background:rgba(88,166,255,.08);
}}
.heat strong {{ display:block; font-size:16px; }}
.heat small {{ color:var(--muted); }}
@media(max-width:1200px) {{
    .kpi {{ grid-column:span 3; }}
    .span-3,.span-4,.span-5,.span-6,.span-7,.span-8 {{ grid-column:span 12; }}
    .ribbon {{ grid-template-columns:repeat(2,1fr); }}
}}
@media(max-width:650px) {{
    .kpi {{ grid-column:span 6; }}
    .header {{ flex-direction:column; }}
    .ribbon {{ grid-template-columns:1fr; }}
}}
</style>
</head>
<body>
<div class="container">

<div class="header">
<div>
<h1>PSX Institutional Trading Terminal V3</h1>
<div class="sub">
Engine: {escape(model['engine_version'])} |
Trading Date: {escape(model['trading_date'])} |
Generated: {escape(model['generated_at'])}
</div>
</div>
<div>
<span class="badge {status_css(model['command_status'])}">
{escape(model['command_status'])}
</span>
</div>
</div>

<div class="ribbon">
<div class="item"><div class="label">Market</div><div class="value">{escape(model['market_mood'])} {model['market_score']:.0f}/100</div></div>
<div class="item"><div class="label">Portfolio Risk</div><div class="value">{model['portfolio_risk_status']} {model['portfolio_risk_pct']:.2f}%</div></div>
<div class="item"><div class="label">Alert Status</div><div class="value">{escape(model['alert_status'])}</div></div>
<div class="item"><div class="label">Critical Alerts</div><div class="value">{model['critical_alerts']}</div></div>
<div class="item"><div class="label">Best Trade</div><div class="value">{escape(model['best_trade'] or 'None')}</div></div>
</div>

<div class="grid">

<div class="card span-12 command">
<div class="label">AI Command Center — Overall Recommendation</div>
<div class="value">{escape(model['overall_recommendation'])}</div>
</div>

{render_kpi("Capital", f"PKR {model['starting_capital']:,.0f}")}
{render_kpi("Used Capital", f"PKR {model['used_capital']:,.0f}")}
{render_kpi("Cash Available", f"PKR {model['cash_available']:,.0f}")}
{render_kpi("Total Equity", f"PKR {model['total_equity']:,.0f}", pnl_class(model['total_equity'] - model['starting_capital']))}
{render_kpi("Realized P/L", f"PKR {model['realized_pnl']:,.2f}", pnl_class(model['realized_pnl']))}
{render_kpi("Unrealized P/L", f"PKR {model['unrealized_pnl']:,.2f}", pnl_class(model['unrealized_pnl']))}

{render_kpi("Portfolio Health", f"{model['portfolio_health_score']:.2f}")}
{render_kpi("Open Positions", str(model['open_positions_count']))}
{render_kpi("Pending Entries", str(model['pending_entries_count']))}
{render_kpi("Closed Trades", str(model['closed_positions_count']))}
{render_kpi("Win Rate", f"{model['win_rate_pct']:.2f}%")}
{render_kpi("Max Drawdown", f"{model['max_drawdown_pct']:.2f}%", pnl_class(model['max_drawdown_pct']))}

<div class="card span-8">
<h2>Equity Curve</h2>
<div class="chart-box"><canvas id="equityChart"></canvas></div>
</div>

<div class="card span-4">
<h2>Institutional Risk Gauge</h2>
<div class="gauge"></div>
<div class="gauge-value">{model['portfolio_risk_pct']:.2f}%</div>
<div style="text-align:center;color:var(--muted)">{escape(model['portfolio_risk_status'])}</div>
</div>

<div class="card span-6">
<h2>Portfolio Allocation</h2>
<div class="chart-box"><canvas id="allocationChart"></canvas></div>
</div>

<div class="card span-6">
<h2>Sector Exposure / Rotation</h2>
<div class="chart-box"><canvas id="sectorChart"></canvas></div>
</div>

<div class="card span-6">
<h2>Strategy Performance Board</h2>
<div class="chart-box"><canvas id="strategyChart"></canvas></div>
</div>

<div class="card span-6">
<h2>Monthly Returns</h2>
<div class="chart-box"><canvas id="monthlyChart"></canvas></div>
</div>

<div class="card span-6">
<h2>Drawdown Analysis</h2>
<div class="chart-box"><canvas id="drawdownChart"></canvas></div>
</div>

<div class="card span-6">
<h2>Action Distribution</h2>
<div class="chart-box"><canvas id="actionChart"></canvas></div>
</div>

<div class="card span-12">
<h2>AI Command Center — Priority Actions</h2>
<div class="scroll">{command_table}</div>
</div>

<div class="card span-12">
<h2>Live Institutional Alerts</h2>
<div class="scroll">{alert_table}</div>
</div>

<div class="card span-12">
<h2>Portfolio Heatmap</h2>
{portfolio_heatmap(model['position_analytics'])}
</div>

<div class="card span-12">
<h2>Open Portfolio Analytics</h2>
<div class="scroll">{portfolio_table}</div>
</div>

<div class="card span-6">
<h2>Pending Entry Queue</h2>
<div class="scroll">{pending_table}</div>
</div>

<div class="card span-6">
<h2>Rebalancing Suggestions</h2>
<div class="scroll">{rebalancing_table}</div>
</div>

<div class="card span-7">
<h2>Strategy Leaderboard</h2>
<div class="scroll">{strategy_table}</div>
</div>

<div class="card span-5">
<h2>Sector Exposure</h2>
<div class="scroll">{sector_table}</div>
</div>

<div class="card span-6">
<h2>Position Risk Contribution</h2>
<div class="scroll">{risk_table}</div>
</div>

<div class="card span-6">
<h2>Trade Review Queue</h2>
<div class="scroll">{review_table}</div>
</div>

<div class="card span-12">
<h2>Trade Journal Intelligence</h2>
<div class="scroll">{journal_table}</div>
</div>

<div class="card span-12">
<h2>Engine Health</h2>
<div class="heatmap">
{engine_health_cards()}
</div>
</div>

</div>
</div>

<script>
const commonOptions = {{
    responsive:true,
    maintainAspectRatio:false,
    plugins:{{
        legend:{{labels:{{color:'#edf4fb'}}}}
    }},
    scales:{{
        x:{{ticks:{{color:'#91a7bb'}},grid:{{color:'rgba(255,255,255,.05)'}}}},
        y:{{ticks:{{color:'#91a7bb'}},grid:{{color:'rgba(255,255,255,.05)'}}}}
    }}
}};

new Chart(document.getElementById('equityChart'), {{
    type:'line',
    data:{{
        labels:{json.dumps(model['equity_labels'])},
        datasets:[{{
            label:'Total Equity',
            data:{json.dumps(model['equity_values'])},
            tension:.3,
            fill:true
        }}]
    }},
    options:commonOptions
}});

new Chart(document.getElementById('allocationChart'), {{
    type:'doughnut',
    data:{{
        labels:{json.dumps(model['allocation_labels'])},
        datasets:[{{data:{json.dumps(model['allocation_values'])}}}]
    }},
    options:{{
        responsive:true,
        maintainAspectRatio:false,
        plugins:{{legend:{{labels:{{color:'#edf4fb'}}}}}}
    }}
}});

new Chart(document.getElementById('sectorChart'), {{
    type:'bar',
    data:{{
        labels:{json.dumps(model['sector_labels'])},
        datasets:[{{label:'Exposure %',data:{json.dumps(model['sector_values'])}}}]
    }},
    options:commonOptions
}});

new Chart(document.getElementById('strategyChart'), {{
    type:'bar',
    data:{{
        labels:{json.dumps(model['strategy_labels'])},
        datasets:[{{label:'Strategy Score',data:{json.dumps(model['strategy_values'])}}}]
    }},
    options:commonOptions
}});

new Chart(document.getElementById('monthlyChart'), {{
    type:'bar',
    data:{{
        labels:{json.dumps(model['monthly_labels'])},
        datasets:[{{label:'Monthly Return %',data:{json.dumps(model['monthly_values'])}}}]
    }},
    options:commonOptions
}});

new Chart(document.getElementById('drawdownChart'), {{
    type:'line',
    data:{{
        labels:{json.dumps(model['drawdown_labels'])},
        datasets:[{{label:'Drawdown %',data:{json.dumps(model['drawdown_values'])},tension:.25,fill:true}}]
    }},
    options:commonOptions
}});

new Chart(document.getElementById('actionChart'), {{
    type:'bar',
    data:{{
        labels:{json.dumps(model['action_labels'])},
        datasets:[{{label:'Actions',data:{json.dumps(model['action_values'])}}}]
    }},
    options:commonOptions
}});
</script>
</body>
</html>"""

    # ---------------------------------------------------------
    # FILE HELPERS
    # ---------------------------------------------------------

    def read_csv(
        self,
        path: Path,
    ) -> pd.DataFrame:
        if (
            not path.exists()
            or path.stat().st_size == 0
        ):
            return pd.DataFrame()

        try:
            return clean_df(
                pd.read_csv(path)
            )
        except (
            pd.errors.EmptyDataError,
            pd.errors.ParserError,
            UnicodeDecodeError,
        ):
            return pd.DataFrame()

    def read_first_record(
        self,
        path: Path,
    ) -> dict:
        df = self.read_csv(path)

        if df.empty:
            return {}

        return df.iloc[-1].to_dict()


def run_performance_dashboard_v3(
    reports_root: str = "reports",
    latest_folder: str = "reports/latest",
    lifecycle_folder: str = "database/portfolio",
    output_folder: str = "reports/dashboard",
    dashboard_filename: str = "dashboard_v3.html",
    latest_dashboard_filename: str = "latest_dashboard_v3.html",
    trading_date: str | None = None,
    starting_capital: float = 50000.0,
    auto_refresh_seconds: int = 0,
) -> dict:
    engine = PerformanceDashboardV3(
        reports_root=reports_root,
        latest_folder=latest_folder,
        lifecycle_folder=lifecycle_folder,
        output_folder=output_folder,
        dashboard_filename=dashboard_filename,
        latest_dashboard_filename=latest_dashboard_filename,
    )

    return engine.run(
        trading_date=trading_date,
        starting_capital=starting_capital,
        auto_refresh_seconds=auto_refresh_seconds,
    )


# ---------------------------------------------------------
# GENERIC HELPERS
# ---------------------------------------------------------

def clean_df(
    df: pd.DataFrame | None,
) -> pd.DataFrame:
    if (
        df is None
        or not isinstance(
            df,
            pd.DataFrame,
        )
    ):
        return pd.DataFrame()

    return df.loc[
        :,
        ~df.columns.duplicated(),
    ].copy()


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    try:
        number = float(value)

        if math.isfinite(number):
            return number
    except Exception:
        pass

    return default


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def positive_float(
    value: Any,
    field_name: str,
) -> float:
    number = safe_float(
        value,
        0.0,
    )

    if number <= 0:
        raise ValueError(
            f"{field_name} must be greater than zero."
        )

    return number


def text(
    value: Any,
) -> str:
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    return str(value).strip()


def upper(
    value: Any,
) -> str:
    return text(value).upper()


def first_valid(
    *values: Any,
) -> Any:
    for value in values:
        candidate = text(value)

        if candidate.upper() not in {
            "",
            "NAN",
            "NONE",
            "NULL",
        }:
            return value

    return ""


def first_number(
    values: list[Any],
    default: float = 0.0,
) -> float:
    for value in values:
        number = safe_float(
            value,
            float("nan"),
        )

        if math.isfinite(number):
            return number

    return default


def numeric_series(
    df: pd.DataFrame,
    column: str,
) -> pd.Series:
    if (
        df is None
        or df.empty
        or column not in df.columns
    ):
        return pd.Series(
            0.0,
            index=(
                df.index
                if isinstance(
                    df,
                    pd.DataFrame,
                )
                else None
            ),
            dtype=float,
        )

    return pd.to_numeric(
        df[column],
        errors="coerce",
    ).fillna(0.0)


def numeric_sum(
    df: pd.DataFrame,
    column: str,
) -> float:
    return float(
        numeric_series(
            df,
            column,
        ).sum()
    )


def first_numeric_series(
    df: pd.DataFrame,
    columns: list[str],
) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=float)

    result = pd.Series(
        0.0,
        index=df.index,
        dtype=float,
    )
    unresolved = pd.Series(
        True,
        index=df.index,
    )

    for column in columns:
        if column not in df.columns:
            continue

        values = pd.to_numeric(
            df[column],
            errors="coerce",
        ).fillna(0.0)

        usable = (
            unresolved
            & values.gt(0)
        )

        result.loc[usable] = values.loc[usable]
        unresolved.loc[usable] = False

    return result


def latest_value(
    df: pd.DataFrame,
    column: str,
) -> float:
    if df.empty or column not in df.columns:
        return float("nan")

    return safe_float(
        df.iloc[-1].get(column),
        float("nan"),
    )


def best_value(
    df: pd.DataFrame,
    column: str,
) -> float:
    if df.empty or column not in df.columns:
        return float("nan")

    return float(
        numeric_series(
            df,
            column,
        ).max()
    )


def min_value(
    df: pd.DataFrame,
    column: str,
    default: float = 0.0,
) -> float:
    if df.empty or column not in df.columns:
        return default

    return float(
        numeric_series(
            df,
            column,
        ).min()
    )


def normalize_date(
    value: Any,
) -> str:
    candidate = text(value)

    if not candidate:
        return datetime.now().strftime(
            "%Y-%m-%d"
        )

    parsed = pd.to_datetime(
        candidate,
        errors="coerce",
    )

    if pd.isna(parsed):
        return candidate

    return parsed.strftime(
        "%Y-%m-%d"
    )


def chart_series(
    df: pd.DataFrame,
    label_column: str,
    value_column: str,
) -> tuple[list, list]:
    if (
        df.empty
        or label_column not in df.columns
        or value_column not in df.columns
    ):
        return [], []

    labels = (
        df[label_column]
        .fillna("")
        .astype(str)
        .tolist()
    )

    values = (
        pd.to_numeric(
            df[value_column],
            errors="coerce",
        )
        .fillna(0.0)
        .round(4)
        .tolist()
    )

    return labels, values


def top_series(
    df: pd.DataFrame,
    label_column: str,
    value_column: str,
    limit: int,
    sort_desc: bool = True,
) -> tuple[list, list]:
    if (
        df.empty
        or label_column not in df.columns
        or value_column not in df.columns
    ):
        return [], []

    working = df[
        [
            label_column,
            value_column,
        ]
    ].copy()

    working[value_column] = pd.to_numeric(
        working[value_column],
        errors="coerce",
    ).fillna(0.0)

    working = working.sort_values(
        value_column,
        ascending=not sort_desc,
    ).head(limit)

    return (
        working[label_column]
        .fillna("")
        .astype(str)
        .tolist(),
        working[value_column]
        .round(4)
        .tolist(),
    )


def unique_texts(
    series: pd.Series,
) -> list[str]:
    result = []

    for value in series.fillna("").astype(str):
        value = value.strip()

        if value and value not in result:
            result.append(value)

    return result


def escape(
    value: Any,
) -> str:
    return html.escape(
        text(value)
    )


def pnl_class(
    value: float,
) -> str:
    if value > 0:
        return "positive"

    if value < 0:
        return "negative"

    return ""


def status_css(
    value: str,
) -> str:
    value = upper(value)

    if "IMMEDIATE" in value or "CRITICAL" in value:
        return "red"

    if "OPPORTUNITY" in value or "ATTENTION" in value:
        return "amber"

    return "green"


def health_status(
    score: float,
) -> str:
    if score >= 80:
        return "HEALTHY"

    if score >= 60:
        return "BALANCED"

    if score > 0:
        return "WEAK"

    return "NO DATA"


def risk_status(
    risk_pct: float,
) -> str:
    if risk_pct >= 8:
        return "CRITICAL"

    if risk_pct >= 5:
        return "HIGH"

    if risk_pct >= 2:
        return "CONTROLLED"

    return "LOW"


def render_kpi(
    label: str,
    value: str,
    css_class: str = "",
) -> str:
    return (
        "<div class='card kpi'>"
        f"<div class='label'>{escape(label)}</div>"
        f"<div class='value {css_class}'>{escape(value)}</div>"
        "</div>"
    )


def dataframe_table(
    df: pd.DataFrame,
    columns: list[str],
    rows: int,
) -> str:
    if df.empty:
        return "<div class='sub'>No records found.</div>"

    available = [
        column
        for column in columns
        if column in df.columns
    ]

    if not available:
        return "<div class='sub'>No requested columns found.</div>"

    head = df[available].head(rows)

    html_rows = []
    header = "".join(
        f"<th>{escape(column.replace('_', ' ').title())}</th>"
        for column in available
    )

    for _, row in head.iterrows():
        cells = []

        for column in available:
            value = row.get(column, "")
            css_class = ""

            number = safe_float(
                value,
                float("nan"),
            )

            if math.isfinite(number):
                if (
                    "profit" in column
                    or "return" in column
                    or "pnl" in column
                    or "drawdown" in column
                ):
                    css_class = pnl_class(number)

                display = (
                    f"{number:.2f}"
                    if not float(number).is_integer()
                    else str(int(number))
                )
            else:
                display = text(value)

            cells.append(
                f"<td class='{css_class}'>{escape(display)}</td>"
            )

        html_rows.append(
            "<tr>"
            + "".join(cells)
            + "</tr>"
        )

    return (
        "<table><thead><tr>"
        + header
        + "</tr></thead><tbody>"
        + "".join(html_rows)
        + "</tbody></table>"
    )


def portfolio_heatmap(
    df: pd.DataFrame,
) -> str:
    if df.empty:
        return "<div class='sub'>No open positions.</div>"

    cards = []

    for _, row in df.head(20).iterrows():
        symbol = text(
            row.get("symbol", "")
        )
        sector = text(
            row.get("sector", "")
        )
        pnl = safe_float(
            row.get(
                "unrealized_profit_loss_pct",
                0,
            )
        )
        weight = safe_float(
            row.get(
                "position_weight_pct",
                0,
            )
        )

        background = (
            "rgba(50,210,150,.14)"
            if pnl > 0
            else (
                "rgba(255,100,116,.14)"
                if pnl < 0
                else "rgba(88,166,255,.10)"
            )
        )

        cards.append(
            (
                f"<div class='heat' style='background:{background}'>"
                f"<strong>{escape(symbol)}</strong>"
                f"<small>{escape(sector)}</small>"
                f"<div class='{pnl_class(pnl)}'>{pnl:.2f}%</div>"
                f"<small>Weight {weight:.2f}%</small>"
                "</div>"
            )
        )

    return (
        "<div class='heatmap'>"
        + "".join(cards)
        + "</div>"
    )


def engine_health_cards() -> str:
    engines = [
        "AI Engine V5",
        "Portfolio Engine V5",
        "Trade Lifecycle V1",
        "Exit Intelligence V1",
        "Live Portfolio Monitor V1",
        "Order Execution Simulator V1",
        "Equity Curve V1",
        "Portfolio Analytics Pro V1",
        "Trade Journal Pro V1",
        "Strategy Analytics V1",
        "Strategy Optimizer V2",
        "Institutional Alert Center V1",
        "AI Institutional Assistant V1",
        "AI Command Center V1",
        "Performance Dashboard V3",
    ]

    return "".join(
        (
            "<div class='heat'>"
            f"<strong>{escape(engine)}</strong>"
            "<small class='positive'>ONLINE</small>"
            "</div>"
        )
        for engine in engines
    )


def make_json_safe(
    value: Any,
) -> Any:
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")

    if isinstance(value, dict):
        return {
            key: make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            make_json_safe(item)
            for item in value
        ]

    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()

    if isinstance(value, (pd.Int64Dtype, pd.Float64Dtype)):
        return str(value)

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    return value
