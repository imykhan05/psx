from __future__ import annotations

import hashlib
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


VERSION = "institutional_alert_center_v1_0"
ALERT_COLUMNS = [
    "alert_id", "trading_date", "generated_at", "priority", "severity",
    "alert_category", "alert_type", "symbol", "title", "message",
    "recommended_action", "current_price", "reference_price", "confidence",
    "source_engine", "acknowledged", "active",
]


def run_institutional_alert_center_v1(
    market_df: pd.DataFrame | None = None,
    portfolio_risk_pct: float = 0.0,
    portfolio_health_score: float = 0.0,
    trading_date: str | None = None,
    portfolio_folder: str = "database/portfolio",
    reports_latest_folder: str = "reports/latest",
    strategy_optimizer_folder: str = "reports/strategy_optimizer",
    output_folder: str = "reports/alerts",
) -> dict:
    engine = InstitutionalAlertCenterV1(
        portfolio_folder=portfolio_folder,
        reports_latest_folder=reports_latest_folder,
        strategy_optimizer_folder=strategy_optimizer_folder,
        output_folder=output_folder,
    )
    return engine.run(
        market_df=market_df,
        portfolio_risk_pct=portfolio_risk_pct,
        portfolio_health_score=portfolio_health_score,
        trading_date=trading_date,
    )


class InstitutionalAlertCenterV1:
    def __init__(
        self,
        portfolio_folder: str = "database/portfolio",
        reports_latest_folder: str = "reports/latest",
        strategy_optimizer_folder: str = "reports/strategy_optimizer",
        output_folder: str = "reports/alerts",
    ):
        self.portfolio_folder = Path(portfolio_folder)
        self.reports_latest_folder = Path(reports_latest_folder)
        self.strategy_optimizer_folder = Path(strategy_optimizer_folder)
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)

        self.open_path = self.portfolio_folder / "open_positions.csv"
        self.closed_path = self.portfolio_folder / "closed_positions.csv"
        self.pending_path = self.portfolio_folder / "pending_entries.csv"
        self.strategy_path = self.strategy_optimizer_folder / "strategy_actions_v2.csv"

        self.live_path = self.output_folder / "live_alerts.csv"
        self.critical_path = self.output_folder / "critical_alerts.csv"
        self.summary_path = self.output_folder / "alert_summary.csv"
        self.history_path = self.output_folder / "alert_history.csv"

    def run(
        self,
        market_df: pd.DataFrame | None,
        portfolio_risk_pct: float,
        portfolio_health_score: float,
        trading_date: str | None,
    ) -> dict:
        date = normalize_date(trading_date)
        market_df = clean_df(market_df)
        open_df = read_csv(self.open_path)
        closed_df = read_csv(self.closed_path)
        pending_df = read_csv(self.pending_path)
        strategy_df = read_csv(self.strategy_path)

        alerts: list[dict] = []
        alerts += self.position_alerts(open_df, market_df, date)
        alerts += self.closed_alerts(closed_df, date)
        alerts += self.pending_alerts(pending_df, market_df, date)
        alerts += self.market_alerts(market_df, date)
        alerts += self.strategy_alerts(strategy_df, date)
        alerts += self.portfolio_alerts(
            safe_float(portfolio_risk_pct),
            safe_float(portfolio_health_score),
            date,
        )

        live = self.finalize(alerts)
        critical = live[
            live.get("severity", pd.Series(dtype=str)).astype(str).str.upper().isin(["CRITICAL", "HIGH"])
        ].reset_index(drop=True) if not live.empty else pd.DataFrame(columns=ALERT_COLUMNS)

        summary = self.summary(live, critical, date)
        history = read_csv(self.history_path)
        history = pd.concat([history, live], ignore_index=True, sort=False)
        if not history.empty and "alert_id" in history.columns:
            history = history.drop_duplicates("alert_id", keep="last").tail(5000)

        save_csv(live, self.live_path, ALERT_COLUMNS)
        save_csv(critical, self.critical_path, ALERT_COLUMNS)
        pd.DataFrame([summary]).to_csv(self.summary_path, index=False, encoding="utf-8-sig")
        save_csv(history, self.history_path, ALERT_COLUMNS)

        return {
            "status": "success",
            "engine_version": VERSION,
            "total_alerts": len(live),
            "critical_alerts": len(critical),
            "buy_alerts": count_category(live, "BUY"),
            "exit_alerts": count_category(live, "EXIT"),
            "target_alerts": count_category(live, "TARGET"),
            "strategy_alerts": count_category(live, "STRATEGY"),
            "risk_alerts": count_category(live, "RISK"),
            "live_alerts_csv": str(self.live_path),
            "critical_alerts_csv": str(self.critical_path),
            "alert_summary_csv": str(self.summary_path),
            "alert_history_csv": str(self.history_path),
            "reason": "Institutional alerts generated successfully",
        }

    def position_alerts(self, open_df: pd.DataFrame, market_df: pd.DataFrame, date: str) -> list[dict]:
        alerts = []
        lookup = symbol_lookup(market_df)
        for _, row in open_df.iterrows():
            symbol = upper(row.get("symbol"))
            market = lookup.get(symbol, {})
            price = first_positive([market, row.to_dict()], ["close", "current_price", "exit_current_price", "last_price"])
            entry = first_positive([row.to_dict()], ["actual_entry_price", "average_cost"])
            stop = first_positive([row.to_dict()], ["current_stop_loss", "initial_stop_loss", "stop_loss"])
            t1 = first_positive([row.to_dict()], ["target_1"])
            t2 = first_positive([row.to_dict()], ["target_2"])
            status = upper(first_valid(row.get("position_status"), row.get("lifecycle_status"), "OPEN"))

            if stop > 0 and price > 0 and price <= stop:
                alerts.append(self.make(date, 1, "CRITICAL", "EXIT", "STOP LOSS HIT", symbol,
                    f"{symbol} stop loss triggered", f"Price {price:.2f} is at/below stop {stop:.2f}.",
                    "EXIT NOW", price, stop, 100, "Live Portfolio Monitor V1"))
            elif t2 > 0 and price >= t2:
                alerts.append(self.make(date, 2, "HIGH", "TARGET", "TARGET 2 HIT", symbol,
                    f"{symbol} Target 2 reached", f"Price {price:.2f} reached Target 2 {t2:.2f}.",
                    "BOOK FULL PROFIT", price, t2, 95, "Live Portfolio Monitor V1"))
            elif t1 > 0 and price >= t1:
                alerts.append(self.make(date, 3, "HIGH", "TARGET", "TARGET 1 HIT", symbol,
                    f"{symbol} Target 1 reached", f"Price {price:.2f} reached Target 1 {t1:.2f}.",
                    "BOOK PARTIAL PROFIT", price, t1, 92, "Live Portfolio Monitor V1"))
            elif status in {"TRAIL STOP", "PARTIAL EXIT", "TARGET 1 HIT"}:
                alerts.append(self.make(date, 5, "MEDIUM", "EXIT", "TRAILING STOP", symbol,
                    f"{symbol} trailing stop active", f"Status {status}; current stop {stop:.2f}.",
                    "HOLD WITH TRAILING STOP", price, stop, 85, "Live Portfolio Monitor V1"))
            elif entry > 0 and price > 0 and ((price-entry)/entry*100) <= -5:
                alerts.append(self.make(date, 7, "MEDIUM", "RISK", "POSITION WEAKNESS", symbol,
                    f"{symbol} position weakening", f"Position is down {((price-entry)/entry*100):.2f}%.",
                    "REVIEW POSITION", price, entry, 75, "Live Portfolio Monitor V1"))
        return alerts

    def closed_alerts(self, closed_df: pd.DataFrame, date: str) -> list[dict]:
        alerts = []
        for _, row in closed_df.tail(20).iterrows():
            exit_date = normalize_date(row.get("exit_date"))
            if date and exit_date and exit_date != date:
                continue
            symbol = upper(row.get("symbol"))
            realized = safe_float(row.get("realized_profit_loss"))
            status = upper(row.get("position_status"))
            if status == "STOP LOSS HIT":
                severity, priority, atype, category, action = "CRITICAL", 1, "STOP LOSS HIT", "EXIT", "REVIEW LOSS"
            elif realized > 0:
                severity, priority, atype, category, action = "MEDIUM", 6, "PROFIT BOOKED", "TARGET", "RECORD JOURNAL"
            else:
                severity, priority, atype, category, action = "HIGH", 4, "TRADE CLOSED", "EXIT", "REVIEW TRADE"
            alerts.append(self.make(date, priority, severity, category, atype, symbol,
                f"{symbol} trade closed", f"Realized P/L {realized:.2f}. {clean(row.get('close_reason'))}",
                action, safe_float(row.get("final_exit_price")), safe_float(row.get("actual_entry_price")),
                90, "Order Execution Simulator V1"))
        return alerts

    def pending_alerts(self, pending_df: pd.DataFrame, market_df: pd.DataFrame, date: str) -> list[dict]:
        alerts = []
        lookup = symbol_lookup(market_df)
        for _, row in pending_df.iterrows():
            if upper(row.get("execution_status")) in {"BUY EXECUTED", "CANCELLED", "CLOSED"}:
                continue
            symbol = upper(row.get("symbol"))
            status = upper(first_valid(row.get("lifecycle_status"), row.get("portfolio_position_status"), "READY TO BUY"))
            price = first_positive([lookup.get(symbol, {}), row.to_dict()], ["close", "current_price"])
            entry = first_positive([row.to_dict()], ["adjusted_entry_price", "suggested_entry_price", "entry_high"])
            confidence = first_positive([row.to_dict()], ["confidence", "confidence_v3", "buy_probability"])
            atype = "BUY NOW" if status in {"READY TO BUY", "BUY NOW"} else "WATCH"
            alerts.append(self.make(date, 4 if atype == "BUY NOW" else 9,
                "HIGH" if atype == "BUY NOW" else "LOW", "BUY", atype, symbol,
                f"{symbol} {'approved entry' if atype == 'BUY NOW' else 'watch entry'}",
                f"Current {price:.2f}; planned entry {entry:.2f}.", atype,
                price, entry, confidence, "Trade Lifecycle Engine V1"))
        return alerts

    def market_alerts(self, market_df: pd.DataFrame, date: str) -> list[dict]:
        alerts = []
        for _, row in market_df.head(100).iterrows() if not market_df.empty else []:
            symbol = upper(row.get("symbol"))
            exit_action = upper(row.get("exit_action"))
            price = safe_float(first_valid(row.get("close"), row.get("current_price"), 0))
            if exit_action in {"EMERGENCY EXIT", "EXIT TODAY"}:
                alerts.append(self.make(date, 1, "CRITICAL", "EXIT", exit_action, symbol,
                    f"{symbol} {exit_action.lower()}", clean(row.get("exit_reason")) or "Exit signal generated.",
                    exit_action, price, safe_float(row.get("exit_suggested_stop_loss")),
                    safe_float(row.get("exit_confidence")), "Exit Intelligence Engine V1"))
            smart = safe_float(row.get("smart_money_score"))
            buy_prob = safe_float(row.get("buy_probability"))
            if smart >= 90 and upper(row.get("final_decision")) == "BUY" and buy_prob >= 75:
                alerts.append(self.make(date, 6, "MEDIUM", "BUY", "SMART MONEY", symbol,
                    f"{symbol} smart money signal", f"Smart money {smart:.1f}; buy probability {buy_prob:.1f}%.",
                    "WATCH / VALIDATE", price, safe_float(row.get("suggested_entry_price"), price),
                    buy_prob, "AI Engine V5"))
        return alerts

    def strategy_alerts(self, strategy_df: pd.DataFrame, date: str) -> list[dict]:
        alerts = []
        for _, row in strategy_df.iterrows():
            action = upper(row.get("recommended_action"))
            if action not in {"INCREASE", "REDUCE", "DISABLE", "LEARN"}:
                continue
            severity = {"DISABLE":"CRITICAL", "REDUCE":"HIGH", "INCREASE":"MEDIUM", "LEARN":"LOW"}[action]
            priority = {"DISABLE":2, "REDUCE":4, "INCREASE":6, "LEARN":10}[action]
            strategy = clean(row.get("strategy"))
            alerts.append(self.make(date, priority, severity, "STRATEGY",
                "STRATEGY LEARNING" if action == "LEARN" else "STRATEGY WEIGHT CHANGE",
                strategy, f"{strategy} strategy: {action}",
                clean(first_valid(row.get("operational_instruction"), row.get("optimizer_reason"))),
                action, 0, safe_float(row.get("suggested_weight"), 1),
                safe_float(row.get("optimizer_quality_score")), "Strategy Optimizer V2"))
        return alerts

    def portfolio_alerts(self, risk: float, health: float, date: str) -> list[dict]:
        alerts = []
        if risk >= 8:
            alerts.append(self.make(date, 1, "CRITICAL", "RISK", "PORTFOLIO RISK", "PORTFOLIO",
                "Portfolio risk is critical", f"Portfolio risk reached {risk:.2f}%.",
                "REDUCE EXPOSURE", risk, 8, 100, "Portfolio Analytics Pro V1"))
        elif risk >= 5:
            alerts.append(self.make(date, 3, "HIGH", "RISK", "PORTFOLIO RISK", "PORTFOLIO",
                "Portfolio risk elevated", f"Portfolio risk is {risk:.2f}%.",
                "REVIEW EXPOSURE", risk, 5, 90, "Portfolio Analytics Pro V1"))
        if 0 < health < 50:
            alerts.append(self.make(date, 4, "HIGH", "RISK", "PORTFOLIO HEALTH", "PORTFOLIO",
                "Portfolio health weakened", f"Portfolio health score {health:.2f}.",
                "REBALANCE", health, 50, 85, "Portfolio Analytics Pro V1"))
        return alerts

    def make(self, date, priority, severity, category, atype, symbol, title, message,
             action, current, reference, confidence, source):
        key = f"{date}|{atype}|{symbol}|{action}"
        return {
            "alert_id": hashlib.sha1(key.encode()).hexdigest()[:16].upper(),
            "trading_date": date,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "priority": int(priority),
            "severity": upper(severity),
            "alert_category": upper(category),
            "alert_type": upper(atype),
            "symbol": upper(symbol),
            "title": clean(title),
            "message": clean(message),
            "recommended_action": upper(action),
            "current_price": round(safe_float(current), 4),
            "reference_price": round(safe_float(reference), 4),
            "confidence": round(safe_float(confidence), 2),
            "source_engine": clean(source),
            "acknowledged": False,
            "active": True,
        }

    def finalize(self, alerts: list[dict]) -> pd.DataFrame:
        if not alerts:
            return pd.DataFrame(columns=ALERT_COLUMNS)
        df = pd.DataFrame(alerts).drop_duplicates("alert_id", keep="last")
        rank = {"CRITICAL":1, "HIGH":2, "MEDIUM":3, "LOW":4, "INFO":5}
        df["_rank"] = df["severity"].map(rank).fillna(9)
        return df.sort_values(["priority", "_rank", "confidence"], ascending=[True, True, False]).drop(columns="_rank")[ALERT_COLUMNS].reset_index(drop=True)

    def summary(self, live: pd.DataFrame, critical: pd.DataFrame, date: str) -> dict:
        critical_count = int((critical.get("severity", pd.Series(dtype=str)).astype(str).str.upper() == "CRITICAL").sum()) if not critical.empty else 0
        high_count = int((critical.get("severity", pd.Series(dtype=str)).astype(str).str.upper() == "HIGH").sum()) if not critical.empty else 0
        return {
            "engine_version": VERSION,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "trading_date": date,
            "total_alerts": len(live),
            "critical_alerts": critical_count,
            "high_alerts": high_count,
            "buy_alerts": count_category(live, "BUY"),
            "exit_alerts": count_category(live, "EXIT"),
            "target_alerts": count_category(live, "TARGET"),
            "strategy_alerts": count_category(live, "STRATEGY"),
            "risk_alerts": count_category(live, "RISK"),
            "alert_center_status": "CRITICAL" if critical_count else ("ATTENTION" if high_count else "NORMAL"),
        }


def clean_df(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    return df.loc[:, ~df.columns.duplicated()].copy()


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return clean_df(pd.read_csv(path))
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError):
        return pd.DataFrame()


def save_csv(df: pd.DataFrame, path: Path, columns: list[str]) -> None:
    df = clean_df(df)
    path.parent.mkdir(parents=True, exist_ok=True)
    for column in columns:
        if column not in df.columns:
            df[column] = False if column in {"acknowledged", "active"} else (0 if column == "priority" else (0.0 if column in {"current_price", "reference_price", "confidence"} else ""))
    df[columns].to_csv(path, index=False, encoding="utf-8-sig")


def symbol_lookup(df: pd.DataFrame) -> dict[str, dict]:
    if df.empty or "symbol" not in df.columns:
        return {}
    return {upper(row.get("symbol")): row.to_dict() for _, row in df.iterrows() if upper(row.get("symbol"))}


def first_positive(sources: list[dict], columns: list[str]) -> float:
    for source in sources:
        for column in columns:
            value = safe_float(source.get(column)) if source else 0.0
            if value > 0:
                return value
    return 0.0


def first_valid(*values: Any) -> Any:
    for value in values:
        try:
            if pd.isna(value):
                continue
        except Exception:
            pass
        if str(value).strip().upper() not in {"", "NAN", "NONE", "NULL"}:
            return value
    return ""


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


def clean(value: Any) -> str:
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def upper(value: Any) -> str:
    return clean(value).upper()


def normalize_date(value: Any) -> str:
    if value is None or not clean(value):
        return datetime.now().strftime("%Y-%m-%d")
    parsed = pd.to_datetime(value, errors="coerce")
    return parsed.strftime("%Y-%m-%d") if not pd.isna(parsed) else clean(value)


def count_category(df: pd.DataFrame, category: str) -> int:
    if df.empty or "alert_category" not in df.columns:
        return 0
    return int(df["alert_category"].astype(str).str.upper().eq(category.upper()).sum())
