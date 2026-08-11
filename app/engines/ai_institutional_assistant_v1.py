from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


class AIInstitutionalAssistantV1:
    VERSION = "ai_institutional_assistant_v1_0"

    def __init__(
        self,
        reports_folder: str = "reports/ai_assistant",
        alerts_folder: str = "reports/alerts",
        portfolio_folder: str = "database/portfolio",
        optimizer_folder: str = "reports/strategy_optimizer",
    ):
        self.reports_folder = Path(reports_folder)
        self.alerts_folder = Path(alerts_folder)
        self.portfolio_folder = Path(portfolio_folder)
        self.optimizer_folder = Path(optimizer_folder)
        self.reports_folder.mkdir(parents=True, exist_ok=True)

        self.report_path = self.reports_folder / "ai_institutional_assistant.csv"
        self.actions_path = self.reports_folder / "ai_institutional_actions.csv"
        self.summary_path = self.reports_folder / "ai_institutional_assistant_summary.csv"
        self.brief_path = self.reports_folder / "ai_institutional_brief.md"

    def run(
        self,
        market_df: pd.DataFrame | None = None,
        market_summary: dict | None = None,
        portfolio_summary: dict | None = None,
        lifecycle_summary: dict | None = None,
        alert_summary: dict | None = None,
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
        strategy_summary = strategy_summary or {}
        optimizer_summary = optimizer_summary or {}

        open_df = self.read_csv(self.portfolio_folder / "open_positions.csv")
        pending_df = self.read_csv(self.portfolio_folder / "pending_entries.csv")
        alerts_df = self.read_csv(self.alerts_folder / "live_alerts.csv")
        optimizer_df = self.read_csv(self.optimizer_folder / "strategy_optimizer_output.csv")

        actions_df = self.build_actions(
            market_df=market_df,
            open_df=open_df,
            pending_df=pending_df,
            alerts_df=alerts_df,
            optimizer_df=optimizer_df,
        )

        summary = self.build_summary(
            market_summary=market_summary,
            portfolio_summary=portfolio_summary,
            lifecycle_summary=lifecycle_summary,
            alert_summary=alert_summary,
            strategy_summary=strategy_summary,
            optimizer_summary=optimizer_summary,
            actions_df=actions_df,
            starting_capital=starting_capital,
            trading_date=trading_date,
        )

        report_df = pd.DataFrame([
            {"section": "MARKET", "metric": "Market View", "value": summary["market_view"], "status": summary["market_mood"]},
            {"section": "PORTFOLIO", "metric": "Portfolio View", "value": summary["portfolio_view"], "status": summary["risk_view"]},
            {"section": "ACTION", "metric": "Top Action", "value": summary["top_action"], "status": summary["top_symbol"]},
            {"section": "ASSISTANT", "metric": "Assistant Status", "value": summary["assistant_status"], "status": f"{summary['actions_count']} actions"},
        ])

        report_df.to_csv(self.report_path, index=False, encoding="utf-8-sig")
        actions_df.to_csv(self.actions_path, index=False, encoding="utf-8-sig")
        pd.DataFrame([summary]).to_csv(self.summary_path, index=False, encoding="utf-8-sig")
        self.brief_path.write_text(self.build_brief(summary, actions_df), encoding="utf-8")

        return {
            "status": "success",
            "engine_version": self.VERSION,
            "market_view": summary["market_view"],
            "portfolio_view": summary["portfolio_view"],
            "risk_view": summary["risk_view"],
            "top_action": summary["top_action"],
            "actions_count": int(len(actions_df)),
            "assistant_report_csv": str(self.report_path),
            "assistant_actions_csv": str(self.actions_path),
            "assistant_summary_csv": str(self.summary_path),
            "assistant_brief_md": str(self.brief_path),
            "reason": "Institutional assistant brief generated successfully",
        }

    def build_actions(
        self,
        market_df: pd.DataFrame,
        open_df: pd.DataFrame,
        pending_df: pd.DataFrame,
        alerts_df: pd.DataFrame,
        optimizer_df: pd.DataFrame,
    ) -> pd.DataFrame:
        rows: list[dict] = []

        if not alerts_df.empty:
            for _, row in alerts_df.head(40).iterrows():
                rows.append({
                    "priority": safe_int(row.get("priority", 9), 9),
                    "category": upper(row.get("alert_category", "ALERT")),
                    "symbol": upper(row.get("symbol", "")),
                    "recommended_action": upper(row.get("recommended_action", "")),
                    "reason": text(first_valid(row.get("message"), row.get("title"), "")),
                    "confidence": safe_float(row.get("confidence", 0)),
                    "severity": upper(row.get("severity", "INFO")),
                    "source_engine": text(row.get("source_engine", "Institutional Alert Center V1")),
                })

        market_lookup = symbol_lookup(market_df)
        if not open_df.empty:
            for _, row in open_df.iterrows():
                symbol = upper(row.get("symbol", ""))
                market_row = market_lookup.get(symbol, {})
                current = first_positive([market_row, row.to_dict()], ["close", "current_price", "last_price"])
                entry = first_positive([row.to_dict()], ["actual_entry_price", "average_cost"])
                stop = first_positive([row.to_dict()], ["current_stop_loss", "initial_stop_loss", "stop_loss"])
                target1 = first_positive([row.to_dict()], ["target_1"])

                if stop > 0 and current > 0 and current <= stop:
                    action, priority, severity = "EXIT NOW", 1, "CRITICAL"
                    reason = f"Current price {current:.2f} is at/below stop loss {stop:.2f}."
                elif target1 > 0 and current >= target1:
                    action, priority, severity = "BOOK PARTIAL PROFIT", 3, "HIGH"
                    reason = f"Target 1 {target1:.2f} reached."
                else:
                    action, priority, severity = "HOLD", 8, "MEDIUM"
                    pnl = ((current - entry) / entry * 100) if entry > 0 else 0.0
                    reason = f"Open position; current P/L {pnl:.2f}%."

                rows.append({
                    "priority": priority,
                    "category": "PORTFOLIO",
                    "symbol": symbol,
                    "recommended_action": action,
                    "reason": reason,
                    "confidence": 85.0,
                    "severity": severity,
                    "source_engine": self.VERSION,
                })

        if not pending_df.empty:
            for _, row in pending_df.iterrows():
                if upper(row.get("execution_status", "")) in {"BUY EXECUTED", "CANCELLED", "CLOSED"}:
                    continue
                rows.append({
                    "priority": 6,
                    "category": "ENTRY",
                    "symbol": upper(row.get("symbol", "")),
                    "recommended_action": "BUY NOW",
                    "reason": "Approved pending entry; execute only after actual broker confirmation.",
                    "confidence": first_positive([row.to_dict()], ["confidence", "buy_probability"]),
                    "severity": "HIGH",
                    "source_engine": "Trade Lifecycle Engine V1",
                })

        if not optimizer_df.empty:
            for _, row in optimizer_df.iterrows():
                action = upper(row.get("recommended_action", ""))
                if action not in {"INCREASE", "REDUCE", "DISABLE", "LEARN"}:
                    continue
                rows.append({
                    "priority": 4 if action in {"REDUCE", "DISABLE"} else 10,
                    "category": "STRATEGY",
                    "symbol": upper(row.get("strategy", "")),
                    "recommended_action": action,
                    "reason": text(row.get("optimizer_reason", "")),
                    "confidence": safe_float(row.get("optimizer_quality_score", 0)),
                    "severity": "HIGH" if action in {"REDUCE", "DISABLE"} else "LOW",
                    "source_engine": "Strategy Optimizer & Self-Learning V2",
                })

        if not rows:
            return pd.DataFrame(columns=self.action_columns())

        result = pd.DataFrame(rows)
        result = result.drop_duplicates(
            subset=["category", "symbol", "recommended_action"],
            keep="first",
        )
        result = result.sort_values(["priority", "confidence"], ascending=[True, False]).reset_index(drop=True)
        return result[self.action_columns()]

    def build_summary(
        self,
        market_summary: dict,
        portfolio_summary: dict,
        lifecycle_summary: dict,
        alert_summary: dict,
        strategy_summary: dict,
        optimizer_summary: dict,
        actions_df: pd.DataFrame,
        starting_capital: float,
        trading_date: str | None,
    ) -> dict:
        mood = upper(first_valid(market_summary.get("market_mood"), market_summary.get("mood"), "UNKNOWN"))
        market_score = safe_float(first_valid(market_summary.get("market_score"), market_summary.get("score"), 0))
        health = safe_float(portfolio_summary.get("portfolio_health_score", 0))
        risk = safe_float(first_valid(portfolio_summary.get("portfolio_risk_pct"), portfolio_summary.get("total_risk_pct"), 0))
        pending = safe_int(lifecycle_summary.get("pending_entries", 0))
        open_positions = safe_int(lifecycle_summary.get("open_positions", 0))
        critical = safe_int(alert_summary.get("critical_alerts", 0))

        top_action = text(actions_df.iloc[0].get("recommended_action", "NO ACTION")) if not actions_df.empty else "NO ACTION"
        top_symbol = text(actions_df.iloc[0].get("symbol", "")) if not actions_df.empty else ""

        market_view = f"{mood} market" + (f" with score {market_score:.0f}" if market_score > 0 else "")
        portfolio_view = "STRONG" if health >= 80 else "BALANCED" if health >= 60 else "WEAK" if health > 0 else "NO DATA"
        risk_view = "CRITICAL" if critical > 0 else "HIGH" if risk >= 5 else "CONTROLLED" if risk >= 2 else "LOW"
        assistant_status = "IMMEDIATE ACTION REQUIRED" if critical > 0 else "ACTION AVAILABLE" if pending > 0 else "MONITOR"

        return {
            "engine_version": self.VERSION,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "trading_date": normalize_date(trading_date),
            "starting_capital": round(safe_float(starting_capital), 2),
            "market_view": market_view,
            "market_mood": mood,
            "market_score": round(market_score, 2),
            "portfolio_view": portfolio_view,
            "portfolio_health_score": round(health, 2),
            "portfolio_risk_pct": round(risk, 4),
            "risk_view": risk_view,
            "pending_entries": pending,
            "open_positions": open_positions,
            "critical_alerts": critical,
            "strategy_status": text(first_valid(optimizer_summary.get("summary_status"), strategy_summary.get("summary_status"), "LEARNING")),
            "top_action": top_action,
            "top_symbol": top_symbol,
            "assistant_status": assistant_status,
            "actions_count": int(len(actions_df)),
        }

    def build_brief(self, summary: dict, actions_df: pd.DataFrame) -> str:
        lines = [
            "# AI Institutional Assistant Brief",
            "",
            f"- Trading Date: **{summary['trading_date']}**",
            f"- Market: **{summary['market_view']}**",
            f"- Portfolio: **{summary['portfolio_view']}**",
            f"- Risk: **{summary['risk_view']}**",
            f"- Assistant Status: **{summary['assistant_status']}**",
            "",
            "## Recommended Actions",
            "",
        ]
        if actions_df.empty:
            lines.append("_No actionable recommendations available._")
        else:
            for _, row in actions_df.head(15).iterrows():
                lines.append(
                    f"- **{text(row.get('symbol', ''))}** — {text(row.get('recommended_action', ''))}: {text(row.get('reason', ''))}"
                )
        lines.extend([
            "",
            "## Safety Note",
            "",
            "This assistant summarizes system outputs only. Actual orders require manual confirmation.",
        ])
        return "\n".join(lines)

    def read_csv(self, path: Path) -> pd.DataFrame:
        if not path.exists() or path.stat().st_size == 0:
            return pd.DataFrame()
        try:
            return clean_df(pd.read_csv(path))
        except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError):
            return pd.DataFrame()

    def action_columns(self) -> list[str]:
        return [
            "priority", "category", "symbol", "recommended_action",
            "reason", "confidence", "severity", "source_engine",
        ]


def run_ai_institutional_assistant_v1(
    market_df: pd.DataFrame | None = None,
    market_summary: dict | None = None,
    portfolio_summary: dict | None = None,
    lifecycle_summary: dict | None = None,
    alert_summary: dict | None = None,
    strategy_summary: dict | None = None,
    optimizer_summary: dict | None = None,
    starting_capital: float = 50000.0,
    trading_date: str | None = None,
    reports_folder: str = "reports/ai_assistant",
    alerts_folder: str = "reports/alerts",
    portfolio_folder: str = "database/portfolio",
    optimizer_folder: str = "reports/strategy_optimizer",
) -> dict:
    engine = AIInstitutionalAssistantV1(
        reports_folder=reports_folder,
        alerts_folder=alerts_folder,
        portfolio_folder=portfolio_folder,
        optimizer_folder=optimizer_folder,
    )
    return engine.run(
        market_df=market_df,
        market_summary=market_summary,
        portfolio_summary=portfolio_summary,
        lifecycle_summary=lifecycle_summary,
        alert_summary=alert_summary,
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


def first_valid(*values: Any) -> Any:
    for value in values:
        try:
            if pd.isna(value):
                continue
        except Exception:
            pass
        candidate = str(value).strip()
        if candidate.upper() not in {"", "NAN", "NONE", "NULL"}:
            return value
    return ""


def first_positive(sources: list[dict], columns: list[str]) -> float:
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
    result: dict[str, dict] = {}
    for _, row in df.iterrows():
        symbol = upper(row.get("symbol", ""))
        if symbol:
            result[symbol] = row.to_dict()
    return result


def normalize_date(value: Any) -> str:
    parsed = pd.to_datetime(text(value), errors="coerce")
    if pd.isna(parsed):
        return text(value) or datetime.now().strftime("%Y-%m-%d")
    return parsed.strftime("%Y-%m-%d")


def text(value: Any) -> str:
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def upper(value: Any) -> str:
    return text(value).upper()
