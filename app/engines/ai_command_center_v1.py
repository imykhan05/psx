from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class AICommandCenterConfigV1:
    output_folder: str = "reports/command_center"
    portfolio_folder: str = "database/portfolio"
    alerts_folder: str = "reports/alerts"
    assistant_folder: str = "reports/ai_assistant"
    strategy_folder: str = "reports/strategy_analytics"
    optimizer_folder: str = "reports/strategy_optimizer"

    snapshot_filename: str = "ai_command_center_snapshot.csv"
    actions_filename: str = "ai_command_center_actions.csv"
    summary_filename: str = "ai_command_center_summary.csv"
    json_filename: str = "ai_command_center.json"
    brief_filename: str = "ai_command_center.md"
    html_filename: str = "ai_command_center.html"


class AICommandCenterV1:
    """
    AI Command Center V1

    Combines market, portfolio, lifecycle, alerts, AI assistant, strategy,
    risk and cash information into one institutional decision screen.

    This module is decision-support only. It never executes broker orders.
    """

    VERSION = "ai_command_center_v1_0_unified_decision_screen"

    def __init__(
        self,
        output_folder: str = "reports/command_center",
        portfolio_folder: str = "database/portfolio",
        alerts_folder: str = "reports/alerts",
        assistant_folder: str = "reports/ai_assistant",
        strategy_folder: str = "reports/strategy_analytics",
        optimizer_folder: str = "reports/strategy_optimizer",
    ):
        self.config = AICommandCenterConfigV1(
            output_folder=output_folder,
            portfolio_folder=portfolio_folder,
            alerts_folder=alerts_folder,
            assistant_folder=assistant_folder,
            strategy_folder=strategy_folder,
            optimizer_folder=optimizer_folder,
        )

        self.output_folder = Path(output_folder)
        self.portfolio_folder = Path(portfolio_folder)
        self.alerts_folder = Path(alerts_folder)
        self.assistant_folder = Path(assistant_folder)
        self.strategy_folder = Path(strategy_folder)
        self.optimizer_folder = Path(optimizer_folder)

        self.output_folder.mkdir(parents=True, exist_ok=True)

        self.snapshot_path = (
            self.output_folder / self.config.snapshot_filename
        )
        self.actions_path = (
            self.output_folder / self.config.actions_filename
        )
        self.summary_path = (
            self.output_folder / self.config.summary_filename
        )
        self.json_path = (
            self.output_folder / self.config.json_filename
        )
        self.brief_path = (
            self.output_folder / self.config.brief_filename
        )
        self.html_path = (
            self.output_folder / self.config.html_filename
        )

    def run(
        self,
        market_df: pd.DataFrame | None = None,
        market_summary: dict | None = None,
        portfolio_summary: dict | None = None,
        lifecycle_summary: dict | None = None,
        alert_summary: dict | None = None,
        assistant_summary: dict | None = None,
        strategy_summary: dict | None = None,
        optimizer_summary: dict | None = None,
        starting_capital: float = 50000.0,
        trading_date: str | None = None,
    ) -> dict:
        market_df = clean_df(market_df)
        market_summary = market_summary or {}
        portfolio_summary = portfolio_summary or {}
        lifecycle_summary = lifecycle_summary or {}
        alert_summary = alert_summary or {}
        assistant_summary = assistant_summary or {}
        strategy_summary = strategy_summary or {}
        optimizer_summary = optimizer_summary or {}

        open_df = self.read_csv(
            self.portfolio_folder / "open_positions.csv"
        )
        pending_df = self.read_csv(
            self.portfolio_folder / "pending_entries.csv"
        )
        alerts_df = self.read_csv(
            self.alerts_folder / "live_alerts.csv"
        )
        assistant_actions_df = self.read_csv(
            self.assistant_folder / "ai_institutional_actions.csv"
        )
        strategy_df = self.read_csv(
            self.strategy_folder / "strategy_analytics.csv"
        )
        optimizer_df = self.read_csv(
            self.optimizer_folder / "strategy_optimizer_output.csv"
        )

        resolved_date = normalize_date(trading_date)

        actions_df = self.build_unified_actions(
            assistant_actions_df=assistant_actions_df,
            alerts_df=alerts_df,
            open_df=open_df,
            pending_df=pending_df,
            market_df=market_df,
        )

        summary = self.build_summary(
            market_summary=market_summary,
            portfolio_summary=portfolio_summary,
            lifecycle_summary=lifecycle_summary,
            alert_summary=alert_summary,
            assistant_summary=assistant_summary,
            strategy_summary=strategy_summary,
            optimizer_summary=optimizer_summary,
            strategy_df=strategy_df,
            optimizer_df=optimizer_df,
            actions_df=actions_df,
            open_df=open_df,
            pending_df=pending_df,
            starting_capital=starting_capital,
            trading_date=resolved_date,
        )

        snapshot_df = self.build_snapshot(summary)

        self.save_dataframe(
            snapshot_df,
            self.snapshot_path,
            self.snapshot_columns(),
        )
        self.save_dataframe(
            actions_df,
            self.actions_path,
            self.action_columns(),
        )

        pd.DataFrame([summary]).to_csv(
            self.summary_path,
            index=False,
            encoding="utf-8-sig",
        )

        payload = {
            "engine_version": self.VERSION,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "summary": summary,
            "actions": actions_df.to_dict(orient="records"),
        }

        self.json_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self.brief_path.write_text(
            self.build_markdown(summary, actions_df),
            encoding="utf-8",
        )
        self.html_path.write_text(
            self.build_html(summary, actions_df),
            encoding="utf-8",
        )

        return {
            "status": "success",
            "engine_version": self.VERSION,
            "trading_date": resolved_date,
            "command_status": summary["command_status"],
            "overall_recommendation": summary["overall_recommendation"],
            "best_trade": summary["best_trade"],
            "top_action": summary["top_action"],
            "action_count": int(len(actions_df)),
            "snapshot_csv": str(self.snapshot_path),
            "actions_csv": str(self.actions_path),
            "summary_csv": str(self.summary_path),
            "command_center_json": str(self.json_path),
            "command_center_md": str(self.brief_path),
            "command_center_html": str(self.html_path),
            "reason": "Unified institutional command center generated successfully",
        }

    def build_unified_actions(
        self,
        assistant_actions_df: pd.DataFrame,
        alerts_df: pd.DataFrame,
        open_df: pd.DataFrame,
        pending_df: pd.DataFrame,
        market_df: pd.DataFrame,
    ) -> pd.DataFrame:
        rows: list[dict] = []

        if not assistant_actions_df.empty:
            for _, row in assistant_actions_df.iterrows():
                rows.append({
                    "priority": safe_int(row.get("priority"), 20),
                    "category": upper(row.get("category", "ASSISTANT")),
                    "symbol": upper(row.get("symbol", "")),
                    "action": upper(row.get("recommended_action", "")),
                    "reason": text(row.get("reason", "")),
                    "confidence": safe_float(row.get("confidence", 0)),
                    "severity": upper(row.get("severity", "INFO")),
                    "source": text(row.get("source_engine", "AI Institutional Assistant V1")),
                })

        if not alerts_df.empty:
            for _, row in alerts_df.iterrows():
                rows.append({
                    "priority": safe_int(row.get("priority"), 20),
                    "category": upper(row.get("alert_category", "ALERT")),
                    "symbol": upper(row.get("symbol", "")),
                    "action": upper(row.get("recommended_action", "")),
                    "reason": text(
                        first_valid(
                            row.get("message"),
                            row.get("title"),
                            "",
                        )
                    ),
                    "confidence": safe_float(row.get("confidence", 0)),
                    "severity": upper(row.get("severity", "INFO")),
                    "source": text(row.get("source_engine", "Institutional Alert Center V1")),
                })

        market_lookup = symbol_lookup(market_df)

        if not open_df.empty:
            for _, row in open_df.iterrows():
                symbol = upper(row.get("symbol", ""))
                current = first_positive(
                    [market_lookup.get(symbol, {}), row.to_dict()],
                    ["close", "current_price", "last_price"],
                )
                entry = first_positive(
                    [row.to_dict()],
                    ["actual_entry_price", "average_cost"],
                )
                stop = first_positive(
                    [row.to_dict()],
                    ["current_stop_loss", "initial_stop_loss", "stop_loss"],
                )
                target_1 = first_positive(
                    [row.to_dict()],
                    ["target_1"],
                )

                if stop > 0 and current > 0 and current <= stop:
                    action = "EXIT NOW"
                    priority = 1
                    severity = "CRITICAL"
                    reason = f"Price {current:.2f} is at/below stop {stop:.2f}."
                elif target_1 > 0 and current >= target_1:
                    action = "BOOK PARTIAL PROFIT"
                    priority = 3
                    severity = "HIGH"
                    reason = f"Target 1 {target_1:.2f} has been reached."
                else:
                    pnl_pct = (
                        (current - entry) / entry * 100
                        if entry > 0 and current > 0
                        else 0.0
                    )
                    action = "HOLD"
                    priority = 8
                    severity = "MEDIUM"
                    reason = (
                        f"Position open; P/L {pnl_pct:.2f}%; "
                        f"stop {stop:.2f} remains active."
                    )

                rows.append({
                    "priority": priority,
                    "category": "PORTFOLIO",
                    "symbol": symbol,
                    "action": action,
                    "reason": reason,
                    "confidence": 85.0,
                    "severity": severity,
                    "source": "AI Command Center V1",
                })

        if not pending_df.empty:
            for _, row in pending_df.iterrows():
                status = upper(row.get("execution_status", ""))
                if status in {"BUY EXECUTED", "CANCELLED", "CLOSED"}:
                    continue

                rows.append({
                    "priority": 6,
                    "category": "ENTRY",
                    "symbol": upper(row.get("symbol", "")),
                    "action": "BUY NOW",
                    "reason": "Approved pending entry; broker confirmation required.",
                    "confidence": first_positive(
                        [row.to_dict()],
                        ["confidence", "buy_probability"],
                    ),
                    "severity": "HIGH",
                    "source": "Trade Lifecycle Engine V1",
                })

        if not rows:
            return pd.DataFrame(columns=self.action_columns())

        df = pd.DataFrame(rows)
        df = self.merge_duplicate_actions(df)
        df = df.sort_values(
            ["priority", "confidence"],
            ascending=[True, False],
        ).reset_index(drop=True)

        df.insert(0, "rank", range(1, len(df) + 1))
        return df[self.action_columns()]

    def merge_duplicate_actions(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        severity_rank = {
            "CRITICAL": 1,
            "HIGH": 2,
            "MEDIUM": 3,
            "LOW": 4,
            "INFO": 5,
        }

        df = df.copy()
        df["_severity_rank"] = (
            df["severity"].map(severity_rank).fillna(9)
        )

        merged_rows = []

        for (_, symbol, action), group in df.groupby(
            ["category", "symbol", "action"],
            dropna=False,
            sort=False,
        ):
            group = group.sort_values(
                ["priority", "_severity_rank", "confidence"],
                ascending=[True, True, False],
            )

            best = group.iloc[0].to_dict()
            reasons = []
            sources = []

            for value in group["reason"].fillna("").astype(str):
                value = value.strip()
                if value and value not in reasons:
                    reasons.append(value)

            for value in group["source"].fillna("").astype(str):
                value = value.strip()
                if value and value not in sources:
                    sources.append(value)

            best["reason"] = " | ".join(reasons[:4])
            best["source"] = " + ".join(sources[:3])
            best["confidence"] = round(
                float(group["confidence"].max()),
                2,
            )
            merged_rows.append(best)

        result = pd.DataFrame(merged_rows)
        return result.drop(columns=["_severity_rank"], errors="ignore")

    def build_summary(
        self,
        market_summary: dict,
        portfolio_summary: dict,
        lifecycle_summary: dict,
        alert_summary: dict,
        assistant_summary: dict,
        strategy_summary: dict,
        optimizer_summary: dict,
        strategy_df: pd.DataFrame,
        optimizer_df: pd.DataFrame,
        actions_df: pd.DataFrame,
        open_df: pd.DataFrame,
        pending_df: pd.DataFrame,
        starting_capital: float,
        trading_date: str,
    ) -> dict:
        market_mood = upper(
            first_valid(
                market_summary.get("market_mood"),
                market_summary.get("mood"),
                "UNKNOWN",
            )
        )
        market_score = safe_float(
            first_valid(
                market_summary.get("market_score"),
                market_summary.get("score"),
                0,
            )
        )

        health = safe_float(
            portfolio_summary.get("portfolio_health_score", 0)
        )
        risk = safe_float(
            first_valid(
                portfolio_summary.get("portfolio_risk_pct"),
                portfolio_summary.get("total_risk_pct"),
                0,
            )
        )

        used_capital = safe_float(
            first_valid(
                portfolio_summary.get("total_cost_value"),
                portfolio_summary.get("used_capital"),
                0,
            )
        )
        cash_balance = safe_float(
            first_valid(
                portfolio_summary.get("cash_balance"),
                starting_capital - used_capital,
            )
        )

        critical_alerts = safe_int(
            alert_summary.get("critical_alerts", 0)
        )

        top_action = "NO ACTION"
        top_symbol = ""
        top_reason = ""

        if not actions_df.empty:
            first = actions_df.iloc[0]
            top_action = text(first.get("action", "NO ACTION"))
            top_symbol = text(first.get("symbol", ""))
            top_reason = text(first.get("reason", ""))

        best_trade = ""
        best_trade_confidence = 0.0

        entry_actions = actions_df[
            actions_df.get(
                "action",
                pd.Series(dtype=str),
            )
            .astype(str)
            .str.upper()
            .isin(["BUY NOW", "NEW ENTRY"])
        ] if not actions_df.empty else pd.DataFrame()

        if not entry_actions.empty:
            best_row = entry_actions.sort_values(
                ["priority", "confidence"],
                ascending=[True, False],
            ).iloc[0]
            best_trade = text(best_row.get("symbol", ""))
            best_trade_confidence = safe_float(
                best_row.get("confidence", 0)
            )

        hold_symbols = join_symbols(
            actions_df,
            ["HOLD", "TRAIL STOP", "HOLD WITH TRAILING STOP"],
        )
        buy_symbols = join_symbols(
            actions_df,
            ["BUY NOW", "NEW ENTRY"],
        )
        exit_symbols = join_symbols(
            actions_df,
            ["EXIT NOW", "EXIT TODAY", "EMERGENCY EXIT"],
        )
        watch_symbols = join_symbols(
            actions_df,
            ["WATCH", "WATCH / WAIT", "WATCH / VALIDATE"],
        )

        best_strategy = text(
            first_valid(
                strategy_summary.get("best_strategy"),
                (
                    strategy_df.iloc[0].get("strategy")
                    if not strategy_df.empty
                    else ""
                ),
                "",
            )
        )

        strategy_status = text(
            first_valid(
                optimizer_summary.get("summary_status"),
                strategy_summary.get("summary_status"),
                "LEARNING",
            )
        )

        if critical_alerts > 0 or exit_symbols:
            command_status = "IMMEDIATE ACTION REQUIRED"
        elif buy_symbols:
            command_status = "TRADE OPPORTUNITY"
        else:
            command_status = "MONITOR"

        overall_parts = []
        if buy_symbols:
            overall_parts.append(f"BUY {buy_symbols}")
        if hold_symbols:
            overall_parts.append(f"HOLD {hold_symbols}")
        if watch_symbols:
            overall_parts.append(f"WATCH {watch_symbols}")
        if exit_symbols:
            overall_parts.insert(0, f"EXIT {exit_symbols}")

        overall_recommendation = (
            " | ".join(overall_parts)
            if overall_parts
            else "NO NEW TRADE; CONTINUE MONITORING"
        )

        return {
            "engine_version": self.VERSION,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "trading_date": trading_date,
            "command_status": command_status,
            "market_mood": market_mood,
            "market_score": round(market_score, 2),
            "market_view": f"{market_mood} ({market_score:.0f}/100)",
            "portfolio_health_score": round(health, 2),
            "portfolio_status": portfolio_status(health),
            "portfolio_risk_pct": round(risk, 4),
            "risk_status": risk_status(risk, critical_alerts),
            "starting_capital": round(safe_float(starting_capital), 2),
            "used_capital": round(used_capital, 2),
            "cash_available": round(cash_balance, 2),
            "cash_available_pct": round(
                cash_balance / starting_capital * 100
                if starting_capital > 0
                else 0.0,
                2,
            ),
            "open_positions": int(len(open_df)),
            "pending_entries": int(len(pending_df)),
            "critical_alerts": critical_alerts,
            "best_trade": best_trade,
            "best_trade_confidence": round(best_trade_confidence, 2),
            "hold_symbols": hold_symbols,
            "buy_symbols": buy_symbols,
            "watch_symbols": watch_symbols,
            "exit_symbols": exit_symbols,
            "best_strategy": best_strategy,
            "strategy_status": strategy_status,
            "top_action": top_action,
            "top_symbol": top_symbol,
            "top_reason": top_reason,
            "overall_recommendation": overall_recommendation,
            "action_count": int(len(actions_df)),
            "manual_confirmation_required": True,
        }

    def build_snapshot(self, summary: dict) -> pd.DataFrame:
        rows = [
            {
                "section": "MARKET",
                "metric": "Market View",
                "value": summary["market_view"],
                "status": summary["market_mood"],
            },
            {
                "section": "PORTFOLIO",
                "metric": "Portfolio Health",
                "value": summary["portfolio_health_score"],
                "status": summary["portfolio_status"],
            },
            {
                "section": "RISK",
                "metric": "Portfolio Risk",
                "value": summary["portfolio_risk_pct"],
                "status": summary["risk_status"],
            },
            {
                "section": "CASH",
                "metric": "Cash Available",
                "value": summary["cash_available"],
                "status": f"{summary['cash_available_pct']:.2f}%",
            },
            {
                "section": "TRADE",
                "metric": "Best Trade",
                "value": summary["best_trade"],
                "status": summary["best_trade_confidence"],
            },
            {
                "section": "COMMAND",
                "metric": "Overall Recommendation",
                "value": summary["overall_recommendation"],
                "status": summary["command_status"],
            },
        ]
        return pd.DataFrame(rows)

    def build_markdown(
        self,
        summary: dict,
        actions_df: pd.DataFrame,
    ) -> str:
        lines = [
            "# AI Command Center",
            "",
            f"- Trading Date: **{summary['trading_date']}**",
            f"- Status: **{summary['command_status']}**",
            f"- Market: **{summary['market_view']}**",
            f"- Portfolio: **{summary['portfolio_status']}**",
            f"- Risk: **{summary['risk_status']} ({summary['portfolio_risk_pct']:.2f}%)**",
            f"- Cash Available: **PKR {summary['cash_available']:,.2f}**",
            f"- Best Trade: **{summary['best_trade'] or 'None'}**",
            f"- Best Strategy: **{summary['best_strategy'] or 'Learning'}**",
            "",
            "## Overall Recommendation",
            "",
            f"**{summary['overall_recommendation']}**",
            "",
            "## Priority Actions",
            "",
        ]

        if actions_df.empty:
            lines.append("_No active actions._")
        else:
            for _, row in actions_df.head(15).iterrows():
                lines.append(
                    f"{safe_int(row.get('rank'), 0)}. "
                    f"**{text(row.get('symbol', ''))} — "
                    f"{text(row.get('action', ''))}**: "
                    f"{text(row.get('reason', ''))}"
                )

        lines.extend([
            "",
            "## Safety",
            "",
            "All broker orders require manual confirmation.",
        ])
        return "\n".join(lines)

    def build_html(
        self,
        summary: dict,
        actions_df: pd.DataFrame,
    ) -> str:
        rows = ""

        for _, row in actions_df.head(25).iterrows():
            severity = upper(row.get("severity", "INFO"))
            css_class = {
                "CRITICAL": "critical",
                "HIGH": "high",
                "MEDIUM": "medium",
                "LOW": "low",
            }.get(severity, "info")

            rows += (
                "<tr>"
                f"<td>{safe_int(row.get('rank'), 0)}</td>"
                f"<td>{escape_html(row.get('symbol', ''))}</td>"
                f"<td>{escape_html(row.get('action', ''))}</td>"
                f"<td><span class='badge {css_class}'>{escape_html(severity)}</span></td>"
                f"<td>{escape_html(row.get('reason', ''))}</td>"
                f"<td>{safe_float(row.get('confidence', 0)):.1f}%</td>"
                "</tr>"
            )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Command Center</title>
<style>
body {{
    margin: 0;
    font-family: Arial, sans-serif;
    background: #07111f;
    color: #e7f0f8;
}}
.container {{
    width: min(1400px, 96%);
    margin: 24px auto;
}}
.grid {{
    display: grid;
    grid-template-columns: repeat(12, 1fr);
    gap: 14px;
}}
.card {{
    background: linear-gradient(180deg, #0d1b2a, #10243a);
    border: 1px solid #1f3a56;
    border-radius: 14px;
    padding: 16px;
}}
.kpi {{
    grid-column: span 3;
}}
.full {{
    grid-column: span 12;
}}
.label {{
    color: #94a8bc;
    font-size: 12px;
    text-transform: uppercase;
}}
.value {{
    font-size: 24px;
    font-weight: 700;
    margin-top: 8px;
}}
.command {{
    font-size: 22px;
    color: #38d996;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
}}
th, td {{
    padding: 10px 8px;
    border-bottom: 1px solid #1f3a56;
    text-align: left;
}}
th {{
    color: #94a8bc;
}}
.badge {{
    padding: 4px 8px;
    border-radius: 999px;
}}
.critical {{ background: #6e2020; color: #ffb3b3; }}
.high {{ background: #654b18; color: #ffd978; }}
.medium {{ background: #173f65; color: #8bc7ff; }}
.low, .info {{ background: #174936; color: #8df0c4; }}
@media (max-width: 900px) {{
    .kpi {{ grid-column: span 6; }}
}}
</style>
</head>
<body>
<div class="container">
<h1>AI Institutional Command Center</h1>
<p>Trading Date: {escape_html(summary['trading_date'])} |
Status: {escape_html(summary['command_status'])}</p>

<div class="grid">
<div class="card kpi"><div class="label">Market</div><div class="value">{escape_html(summary['market_view'])}</div></div>
<div class="card kpi"><div class="label">Portfolio</div><div class="value">{escape_html(summary['portfolio_status'])}</div></div>
<div class="card kpi"><div class="label">Risk</div><div class="value">{escape_html(summary['risk_status'])}</div></div>
<div class="card kpi"><div class="label">Cash</div><div class="value">PKR {summary['cash_available']:,.0f}</div></div>
<div class="card full"><div class="label">Overall Recommendation</div><div class="value command">{escape_html(summary['overall_recommendation'])}</div></div>
<div class="card kpi"><div class="label">Best Trade</div><div class="value">{escape_html(summary['best_trade'] or 'None')}</div></div>
<div class="card kpi"><div class="label">Hold</div><div class="value">{escape_html(summary['hold_symbols'] or 'None')}</div></div>
<div class="card kpi"><div class="label">Watch</div><div class="value">{escape_html(summary['watch_symbols'] or 'None')}</div></div>
<div class="card kpi"><div class="label">Danger</div><div class="value">{escape_html(summary['exit_symbols'] or 'None')}</div></div>
<div class="card full">
<h2>Priority Actions</h2>
<div style="overflow:auto">
<table>
<thead><tr><th>#</th><th>Symbol</th><th>Action</th><th>Severity</th><th>Reason</th><th>Confidence</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</div>
</div>
</div>
</div>
</body>
</html>"""

    def read_csv(self, path: Path) -> pd.DataFrame:
        if not path.exists() or path.stat().st_size == 0:
            return pd.DataFrame()

        try:
            return clean_df(pd.read_csv(path))
        except (
            pd.errors.EmptyDataError,
            pd.errors.ParserError,
            UnicodeDecodeError,
        ):
            return pd.DataFrame()

    def save_dataframe(
        self,
        df: pd.DataFrame,
        path: Path,
        columns: list[str],
    ) -> None:
        df = clean_df(df.copy())
        path.parent.mkdir(parents=True, exist_ok=True)

        if df.empty:
            pd.DataFrame(columns=columns).to_csv(
                path,
                index=False,
                encoding="utf-8-sig",
            )
            return

        for column in columns:
            if column not in df.columns:
                df[column] = ""

        df[columns].to_csv(
            path,
            index=False,
            encoding="utf-8-sig",
        )

    def snapshot_columns(self) -> list[str]:
        return [
            "section",
            "metric",
            "value",
            "status",
        ]

    def action_columns(self) -> list[str]:
        return [
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


def run_ai_command_center_v1(
    market_df: pd.DataFrame | None = None,
    market_summary: dict | None = None,
    portfolio_summary: dict | None = None,
    lifecycle_summary: dict | None = None,
    alert_summary: dict | None = None,
    assistant_summary: dict | None = None,
    strategy_summary: dict | None = None,
    optimizer_summary: dict | None = None,
    starting_capital: float = 50000.0,
    trading_date: str | None = None,
    output_folder: str = "reports/command_center",
    portfolio_folder: str = "database/portfolio",
    alerts_folder: str = "reports/alerts",
    assistant_folder: str = "reports/ai_assistant",
    strategy_folder: str = "reports/strategy_analytics",
    optimizer_folder: str = "reports/strategy_optimizer",
) -> dict:
    engine = AICommandCenterV1(
        output_folder=output_folder,
        portfolio_folder=portfolio_folder,
        alerts_folder=alerts_folder,
        assistant_folder=assistant_folder,
        strategy_folder=strategy_folder,
        optimizer_folder=optimizer_folder,
    )

    return engine.run(
        market_df=market_df,
        market_summary=market_summary,
        portfolio_summary=portfolio_summary,
        lifecycle_summary=lifecycle_summary,
        alert_summary=alert_summary,
        assistant_summary=assistant_summary,
        strategy_summary=strategy_summary,
        optimizer_summary=optimizer_summary,
        starting_capital=starting_capital,
        trading_date=trading_date,
    )


def clean_df(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or not isinstance(df, pd.DataFrame):
        return pd.DataFrame()

    return df.loc[:, ~df.columns.duplicated()].copy()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def text(value: Any) -> str:
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    return str(value).strip()


def upper(value: Any) -> str:
    return text(value).upper()


def first_valid(*values: Any) -> Any:
    for value in values:
        candidate = text(value)
        if candidate.upper() not in {"", "NAN", "NONE", "NULL"}:
            return value
    return ""


def first_positive(
    sources: list[dict],
    columns: list[str],
) -> float:
    for source in sources:
        if not source:
            continue

        for column in columns:
            number = safe_float(source.get(column, 0))
            if number > 0:
                return number

    return 0.0


def symbol_lookup(df: pd.DataFrame) -> dict[str, dict]:
    if df.empty or "symbol" not in df.columns:
        return {}

    result = {}
    for _, row in df.iterrows():
        symbol = upper(row.get("symbol", ""))
        if symbol:
            result[symbol] = row.to_dict()

    return result


def join_symbols(
    actions_df: pd.DataFrame,
    actions: list[str],
) -> str:
    if actions_df.empty:
        return ""

    mask = (
        actions_df["action"]
        .fillna("")
        .astype(str)
        .str.upper()
        .isin([item.upper() for item in actions])
    )

    symbols = (
        actions_df.loc[mask, "symbol"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )

    unique = []
    for symbol in symbols:
        if symbol and symbol not in unique:
            unique.append(symbol)

    return ", ".join(unique[:10])


def portfolio_status(score: float) -> str:
    if score >= 80:
        return "HEALTHY"
    if score >= 60:
        return "BALANCED"
    if score > 0:
        return "WEAK"
    return "NO DATA"


def risk_status(
    risk_pct: float,
    critical_alerts: int,
) -> str:
    if critical_alerts > 0:
        return "CRITICAL"
    if risk_pct >= 5:
        return "HIGH"
    if risk_pct >= 2:
        return "CONTROLLED"
    return "LOW"


def normalize_date(value: Any) -> str:
    candidate = text(value)

    if not candidate:
        return datetime.now().strftime("%Y-%m-%d")

    parsed = pd.to_datetime(candidate, errors="coerce")

    if pd.isna(parsed):
        return candidate

    return parsed.strftime("%Y-%m-%d")


def escape_html(value: Any) -> str:
    import html
    return html.escape(text(value))
