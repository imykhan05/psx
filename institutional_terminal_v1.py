from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QProcess,
    QProcessEnvironment,
    QThread,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QPainter, QPen, QTextCursor
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


APP_VERSION = "Institutional Trading Terminal V1.0"
DEFAULT_CAPITAL = 50000
DEFAULT_MAX_PRICE = 500.0


@dataclass(frozen=True)
class TerminalPaths:
    root: Path

    @property
    def main_py(self) -> Path:
        return self.root / "main.py"

    @property
    def reports(self) -> Path:
        return self.root / "reports"

    @property
    def portfolio(self) -> Path:
        return self.root / "database" / "portfolio"

    def report(self, *parts: str) -> Path:
        return self.reports.joinpath(*parts)


REPORTS = {
    "full_market": ("latest", "full_market_scan.csv"),
    "trade_lifecycle": ("latest", "trade_lifecycle.csv"),
    "exit_intelligence": ("latest", "exit_intelligence.csv"),
    "live_positions": ("live_portfolio", "live_positions.csv"),
    "live_portfolio_summary": ("live_portfolio", "live_portfolio_summary.csv"),
    "backtest_overall": ("backtests", "overall_performance.csv"),
    "backtest_by_decision": ("backtests", "performance_by_decision.csv"),
    "strategy_optimizer": ("strategy_optimizer", "strategy_optimizer_output.csv"),
    "opportunities": ("opportunity_ranking", "opportunity_ranking.csv"),
    "opportunity_categories": ("opportunity_ranking", "opportunity_categories.csv"),
    "breadth": ("market_breadth", "market_breadth_summary.csv"),
    "breadth_sectors": ("market_breadth", "market_breadth_by_sector.csv"),
    "smart_money": ("smart_money", "smart_money_stocks.csv"),
    "smart_money_summary": ("smart_money", "smart_money_summary.csv"),
    "alerts": ("alerts", "live_alerts.csv"),
    "critical_alerts": ("alerts", "critical_alerts.csv"),
    "command_actions": ("command_center", "ai_command_center_actions.csv"),
    "command_summary": ("command_center", "ai_command_center_summary.csv"),
    "portfolio_analytics": ("portfolio_analytics", "portfolio_analytics.csv"),
    "portfolio_summary": ("portfolio_analytics", "portfolio_analytics_summary.csv"),
    "equity": ("performance", "daily_equity_curve.csv"),
    "strategy": ("strategy_analytics", "strategy_analytics.csv"),
    "strategy_leaderboard": ("strategy_analytics", "strategy_leaderboard.csv"),
    "journal": ("trade_journal", "trade_journal.csv"),
    "review_queue": ("trade_journal", "trade_review_queue.csv"),
}


FULL_MARKET_COLUMNS = [
    "symbol", "company", "sector", "industry", "close", "change_pct",
    "volume", "final_score", "final_decision", "buy_probability",
    "sell_probability", "confidence_v3", "risk_permission", "risk_status",
    "entry_timing_action", "suggested_entry_price", "stop_loss",
    "target_1", "target_2", "risk_reward_t1", "smart_money_score",
    "trade_validation_status", "lifecycle_status",
]


DARK_STYLE = """
QMainWindow, QWidget { background: #07111f; color: #edf4fb; }
QToolBar { background: #0b1727; border: 0; spacing: 7px; padding: 6px; }
QToolButton, QPushButton {
    background: #132942; border: 1px solid #244966; border-radius: 7px;
    padding: 7px 11px; color: #edf4fb; font-weight: 600;
}
QToolButton:hover, QPushButton:hover { background: #194067; }
QPushButton#danger { background: #642936; border-color: #a44a5c; }
QPushButton#success { background: #15533f; border-color: #238166; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {
    background: #0d1c2d; border: 1px solid #244966; border-radius: 6px;
    padding: 6px; selection-background-color: #235a88;
}
QTableWidget {
    background: #0a1828; alternate-background-color: #0e2033;
    gridline-color: #1b3852; border: 1px solid #1f405e;
}
QHeaderView::section {
    background: #10243a; color: #a9bed1; padding: 7px;
    border: 0; border-right: 1px solid #1f405e; font-weight: 700;
}
QFrame#card { background: #0d1c2d; border: 1px solid #21415f; border-radius: 12px; }
QLabel#muted { color: #91a8bd; }
QLabel#kpi { font-size: 23px; font-weight: 800; }
QLabel#title { font-size: 18px; font-weight: 800; }
QStatusBar { background: #0b1727; color: #9db2c5; }
"""


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except (OSError, UnicodeDecodeError, csv.Error):
        return []


def read_last(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    return rows[-1] if rows else {}


def number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def integer(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def money(value: Any) -> str:
    return f"PKR {number(value):,.2f}"


def report_path(paths: TerminalPaths, key: str) -> Path:
    folder, filename = REPORTS[key]
    return paths.report(folder, filename)


class KpiCard(QFrame):
    def __init__(self, title: str, value: str = "—", accent: str = "#58a6ff"):
        super().__init__()
        self.setObjectName("card")
        self.setMinimumHeight(92)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(13, 11, 13, 11)
        self.title_label = QLabel(title.upper())
        self.title_label.setObjectName("muted")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("kpi")
        self.value_label.setStyleSheet(f"color:{accent};")
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addStretch()

    def set_value(self, value: Any, accent: str | None = None) -> None:
        self.value_label.setText(str(value))
        if accent:
            self.value_label.setStyleSheet(f"color:{accent};")


class SimpleLineChart(QWidget):
    def __init__(self, title: str):
        super().__init__()
        self.title = title
        self.values: list[float] = []
        self.setMinimumHeight(230)

    def set_values(self, values: list[float]) -> None:
        self.values = values[-120:]
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0d1c2d"))
        painter.setPen(QColor("#a9bed1"))
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        painter.drawText(12, 22, self.title)
        if len(self.values) < 2:
            painter.setPen(QColor("#70889e"))
            painter.drawText(self.rect(), Qt.AlignCenter, "No chart data")
            return

        left, top, right, bottom = 40, 38, 14, 26
        width = max(1, self.width() - left - right)
        height = max(1, self.height() - top - bottom)
        minimum, maximum = min(self.values), max(self.values)
        spread = maximum - minimum or 1.0

        painter.setPen(QPen(QColor("#1f405e"), 1))
        for i in range(5):
            y = top + height * i / 4
            painter.drawLine(left, int(y), left + width, int(y))

        points = []
        for index, value in enumerate(self.values):
            x = left + width * index / (len(self.values) - 1)
            y = top + height - (value - minimum) / spread * height
            points.append((int(x), int(y)))

        color = QColor("#32d296" if self.values[-1] >= self.values[0] else "#ff6474")
        painter.setPen(QPen(color, 2.5))
        for p1, p2 in zip(points, points[1:]):
            painter.drawLine(p1[0], p1[1], p2[0], p2[1])

        painter.setPen(QColor("#91a8bd"))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(5, top + 5, f"{maximum:,.2f}")
        painter.drawText(5, top + height, f"{minimum:,.2f}")


class ReportTable(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)

    def load_rows(
        self,
        rows: list[dict[str, str]],
        columns: list[str] | None = None,
        limit: int = 200,
    ) -> None:
        self.setSortingEnabled(False)
        if not rows:
            self.clear()
            self.setRowCount(0)
            self.setColumnCount(0)
            return
        columns = columns or list(rows[0].keys())
        columns = [column for column in columns if any(column in row for row in rows)]
        self.clear()
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels([column.replace("_", " ").title() for column in columns])
        limited = rows[:limit]
        self.setRowCount(len(limited))
        for row_index, row in enumerate(limited):
            for column_index, column in enumerate(columns):
                value = row.get(column, "")
                item = QTableWidgetItem(str(value))
                numeric = number(value, float("nan"))
                if not math_is_nan(numeric):
                    item.setData(Qt.UserRole, numeric)
                upper = str(value).upper()
                if any(token in upper for token in ("BUY TODAY", "BUY NOW", "A+", "HEALTHY", "LOW")):
                    item.setForeground(QColor("#52e0a7"))
                elif any(token in upper for token in ("CRITICAL", "EXIT", "AVOID", "HIGH RISK", "SELL")):
                    item.setForeground(QColor("#ff7685"))
                elif any(token in upper for token in ("WATCH", "WAIT", "MEDIUM", "ATTENTION")):
                    item.setForeground(QColor("#f5c451"))
                self.setItem(row_index, column_index, item)
        self.resizeColumnsToContents()
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.setSortingEnabled(True)


def math_is_nan(value: float) -> bool:
    return value != value


class ChatWorker(QThread):
    """Streams an assistant answer off the UI thread so the terminal stays responsive."""

    chunk = Signal(str)
    done = Signal()
    failed = Signal(str)

    def __init__(self, project_root: Path, messages: list[dict]):
        super().__init__()
        self.project_root = project_root
        self.messages = messages

    def run(self) -> None:
        try:
            if str(self.project_root) not in sys.path:
                sys.path.insert(0, str(self.project_root))
            from app.engines.nl_query_engine import (
                get_client,
                load_context,
                build_system_prompt,
                stream_answer,
            )

            client = get_client()
            system_prompt = build_system_prompt(load_context())
            for text in stream_answer(client, system_prompt, self.messages):
                self.chunk.emit(text)
            self.done.emit()
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class ExecutionDialog(QDialog):
    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.setWindowTitle(f"Manual {mode.title()} Execution")
        self.setMinimumWidth(430)
        form = QFormLayout(self)
        self.symbol = QLineEdit()
        self.price = QDoubleSpinBox()
        self.price.setRange(0.01, 1_000_000)
        self.price.setDecimals(4)
        self.quantity = QSpinBox()
        self.quantity.setRange(0, 100_000_000)
        self.reference = QLineEdit()
        self.notes = QLineEdit()
        self.commission = QDoubleSpinBox()
        self.commission.setRange(0, 1_000_000)
        self.commission.setDecimals(2)
        form.addRow("Symbol", self.symbol)
        form.addRow("Execution price", self.price)
        form.addRow("Quantity (0 = full sell only)", self.quantity)
        form.addRow("Broker reference", self.reference)
        form.addRow("Commission", self.commission)
        form.addRow("Notes", self.notes)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def arguments(self) -> list[str]:
        args = [
            "--execute-buy" if self.mode == "buy" else "--execute-sell",
            "--symbol", self.symbol.text().strip().upper(),
            "--price", str(self.price.value()),
        ]
        if self.quantity.value() > 0:
            args += ["--quantity", str(self.quantity.value())]
        if self.reference.text().strip():
            args += ["--broker-reference", self.reference.text().strip()]
        if self.notes.text().strip():
            args += ["--execution-notes", self.notes.text().strip()]
        if self.commission.value() > 0:
            args += ["--commission", str(self.commission.value())]
        return args


class TerminalWindow(QMainWindow):
    process_output = Signal(str)

    def __init__(self, project_root: Path):
        super().__init__()
        self.paths = TerminalPaths(project_root.resolve())
        self.process: QProcess | None = None
        self.setWindowTitle(f"PSX {APP_VERSION}")
        self.resize(1580, 940)
        self.setStyleSheet(DARK_STYLE)
        self._build_toolbar()
        self._build_ui()
        self._build_statusbar()
        self.refresh_all()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(60_000)
        self.refresh_timer.timeout.connect(self.refresh_all)
        self.refresh_timer.start()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Terminal")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self.refresh_all)
        toolbar.addAction(refresh_action)

        scan_action = QAction("Run Scanner", self)
        scan_action.triggered.connect(self.run_scanner)
        toolbar.addAction(scan_action)

        order_action = QAction("Pending Orders", self)
        order_action.triggered.connect(self.list_pending_orders)
        toolbar.addAction(order_action)

        buy_action = QAction("Confirm Buy", self)
        buy_action.triggered.connect(lambda: self.open_execution("buy"))
        toolbar.addAction(buy_action)

        sell_action = QAction("Confirm Sell", self)
        sell_action.triggered.connect(lambda: self.open_execution("sell"))
        toolbar.addAction(sell_action)

        dashboard_action = QAction("Open Dashboard V3", self)
        dashboard_action.triggered.connect(self.open_dashboard)
        toolbar.addAction(dashboard_action)

        export_action = QAction("Export Snapshot", self)
        export_action.triggered.connect(self.export_snapshot)
        toolbar.addAction(export_action)

    def _build_ui(self) -> None:
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        navigation = QFrame()
        navigation.setObjectName("card")
        navigation.setFixedWidth(205)
        nav_layout = QVBoxLayout(navigation)
        nav_layout.setContentsMargins(10, 12, 10, 12)
        title = QLabel("PSX TERMINAL")
        title.setObjectName("title")
        nav_layout.addWidget(title)
        subtitle = QLabel(APP_VERSION)
        subtitle.setObjectName("muted")
        nav_layout.addWidget(subtitle)
        nav_layout.addSpacing(10)

        self.stack = QStackedWidget()
        pages = [
            ("Market Signal", self._market_signal_page()),
            ("Command Center", self._command_page()),
            ("Full Market", self._full_market_page()),
            ("Opportunities", self._table_page("opportunities")),
            ("Smart Money", self._table_page("smart_money")),
            ("Market Breadth", self._breadth_page()),
            ("Portfolio", self._portfolio_page()),
            ("Positions", self._table_page("trade_lifecycle")),
            ("Exit Signals", self._table_page("exit_intelligence")),
            ("Live Monitor", self._live_portfolio_page()),
            ("Backtest & Learning", self._backtest_page()),
            ("Alerts", self._table_page("alerts")),
            ("Strategy", self._table_page("strategy_leaderboard")),
            ("Trade Journal", self._table_page("journal")),
            ("AI Assistant", self._ai_assistant_page()),
            ("Execution Console", self._console_page()),
        ]
        self.nav_buttons: list[QPushButton] = []
        for index, (name, page) in enumerate(pages):
            button = QPushButton(name)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, i=index: self.select_page(i))
            nav_layout.addWidget(button)
            self.nav_buttons.append(button)
            self.stack.addWidget(page)
        nav_layout.addStretch()

        root.addWidget(navigation)
        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.select_page(0)

    def _build_statusbar(self) -> None:
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.path_label = QLabel(str(self.paths.root))
        self.status.addPermanentWidget(self.path_label)

    def select_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for button_index, button in enumerate(self.nav_buttons):
            button.setChecked(button_index == index)

    def _market_signal_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header = QLabel("Daily Market Signal")
        header.setObjectName("title")
        layout.addWidget(header)

        verdict_card = QFrame()
        verdict_card.setObjectName("card")
        verdict_layout = QVBoxLayout(verdict_card)
        verdict_layout.setContentsMargins(24, 24, 24, 24)
        self.signal_verdict_label = QLabel("—")
        self.signal_verdict_label.setStyleSheet(
            "font-size:64px;font-weight:900;color:#91a8bd;"
        )
        self.signal_confidence_label = QLabel("")
        self.signal_confidence_label.setObjectName("muted")
        self.signal_confidence_label.setStyleSheet("font-size:16px;")
        self.signal_date_label = QLabel("")
        self.signal_date_label.setObjectName("muted")
        verdict_layout.addWidget(self.signal_verdict_label)
        verdict_layout.addWidget(self.signal_confidence_label)
        verdict_layout.addWidget(self.signal_date_label)
        layout.addWidget(verdict_card)

        body = QSplitter(Qt.Horizontal)

        reasons_frame = QFrame()
        reasons_frame.setObjectName("card")
        reasons_layout = QVBoxLayout(reasons_frame)
        reasons_title = QLabel("Why")
        reasons_title.setObjectName("title")
        self.signal_reasons_label = QLabel("Run the scanner to generate today's signal.")
        self.signal_reasons_label.setWordWrap(True)
        self.signal_reasons_label.setStyleSheet("font-size:15px;line-height:1.6;")
        self.signal_reasons_label.setAlignment(Qt.AlignTop)
        reasons_layout.addWidget(reasons_title)
        reasons_layout.addWidget(self.signal_reasons_label)
        reasons_layout.addStretch()
        body.addWidget(reasons_frame)

        ops_frame = QFrame()
        ops_frame.setObjectName("card")
        ops_layout = QVBoxLayout(ops_frame)
        ops_title = QLabel("Top Opportunities")
        ops_title.setObjectName("title")
        self.signal_opportunities_label = QLabel("—")
        self.signal_opportunities_label.setWordWrap(True)
        self.signal_opportunities_label.setStyleSheet("font-size:18px;font-weight:700;")
        self.signal_opportunities_label.setAlignment(Qt.AlignTop)
        ops_layout.addWidget(ops_title)
        ops_layout.addWidget(self.signal_opportunities_label)
        ops_layout.addStretch()
        body.addWidget(ops_frame)
        body.setSizes([820, 480])
        layout.addWidget(body, 1)

        self.signal_updated_label = QLabel("")
        self.signal_updated_label.setObjectName("muted")
        layout.addWidget(self.signal_updated_label)
        return page

    def _refresh_market_signal(self) -> None:
        path = self.paths.root / "database" / "ai_learning" / "daily_signal.json"
        if not path.exists():
            self.signal_verdict_label.setText("NO SIGNAL")
            self.signal_verdict_label.setStyleSheet(
                "font-size:64px;font-weight:900;color:#91a8bd;"
            )
            self.signal_reasons_label.setText("Run the scanner to generate today's signal.")
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return

        verdict = str(data.get("verdict", "—")).upper()
        colors = {"BULLISH": "#32d296", "BEARISH": "#ff6474", "NEUTRAL": "#f5c451"}
        color = colors.get(verdict, "#91a8bd")
        self.signal_verdict_label.setText(verdict)
        self.signal_verdict_label.setStyleSheet(
            f"font-size:64px;font-weight:900;color:{color};"
        )

        confidence = data.get("confidence", 0)
        self.signal_confidence_label.setText(
            f"Confidence: {float(confidence) * 100:.0f}%"
        )
        self.signal_date_label.setText(f"Trading date: {data.get('date', '—')}")

        reasons = data.get("reasons", []) or []
        self.signal_reasons_label.setText(
            "\n\n".join(f"•  {r}" for r in reasons) if reasons else "No reasons available."
        )

        ops = data.get("top_opportunities", []) or []
        self.signal_opportunities_label.setText(
            "\n".join(ops) if ops else "None flagged today."
        )

        sentiment = data.get("sentiment_summary", {})
        self.signal_updated_label.setText(
            f"Generated: {data.get('generated_at', '—')}   |   "
            f"News sentiment — bullish {sentiment.get('bullish', 0)}, "
            f"bearish {sentiment.get('bearish', 0)}, neutral {sentiment.get('neutral', 0)}"
        )

    def _command_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header = QLabel("AI Institutional Command Center")
        header.setObjectName("title")
        layout.addWidget(header)

        kpi_grid = QGridLayout()
        self.kpis = {
            "market": KpiCard("Market", "—", "#58a6ff"),
            "breadth": KpiCard("Breadth", "—", "#b48eff"),
            "risk": KpiCard("Portfolio Risk", "—", "#f5c451"),
            "alerts": KpiCard("Alert Status", "—", "#ff6474"),
            "cash": KpiCard("Cash Available", "—", "#32d296"),
            "equity": KpiCard("Total Equity", "—", "#32d296"),
            "best": KpiCard("Best Trade", "—", "#32d296"),
            "open": KpiCard("Open Positions", "—", "#58a6ff"),
        }
        for index, card in enumerate(self.kpis.values()):
            kpi_grid.addWidget(card, index // 4, index % 4)
        layout.addLayout(kpi_grid)

        recommendation = QFrame()
        recommendation.setObjectName("card")
        rec_layout = QVBoxLayout(recommendation)
        rec_title = QLabel("OVERALL RECOMMENDATION")
        rec_title.setObjectName("muted")
        self.recommendation_label = QLabel("No command-center report found")
        self.recommendation_label.setWordWrap(True)
        self.recommendation_label.setStyleSheet("font-size:22px;font-weight:800;color:#32d296;")
        rec_layout.addWidget(rec_title)
        rec_layout.addWidget(self.recommendation_label)
        layout.addWidget(recommendation)

        splitter = QSplitter(Qt.Horizontal)
        chart_frame = QFrame()
        chart_frame.setObjectName("card")
        chart_layout = QVBoxLayout(chart_frame)
        self.equity_chart = SimpleLineChart("Equity Curve")
        chart_layout.addWidget(self.equity_chart)

        assistant_frame = QFrame()
        assistant_frame.setObjectName("card")
        assistant_layout = QVBoxLayout(assistant_frame)
        assistant_title = QLabel("AI Institutional Assistant Brief")
        assistant_title.setObjectName("title")
        self.assistant_brief = QTextEdit()
        self.assistant_brief.setReadOnly(True)
        assistant_layout.addWidget(assistant_title)
        assistant_layout.addWidget(self.assistant_brief)
        chart_layout.addWidget(assistant_frame)
        splitter.addWidget(chart_frame)

        actions_frame = QFrame()
        actions_frame.setObjectName("card")
        actions_layout = QVBoxLayout(actions_frame)
        actions_title = QLabel("Priority Actions")
        actions_title.setObjectName("title")
        self.command_table = ReportTable()
        actions_layout.addWidget(actions_title)
        actions_layout.addWidget(self.command_table)
        splitter.addWidget(actions_frame)
        splitter.setSizes([560, 850])
        layout.addWidget(splitter, 1)
        return page

    def _full_market_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        title = QLabel("Full Market Scan — Every Stock")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(QLabel("Search"))
        self.full_market_search = QLineEdit()
        self.full_market_search.setPlaceholderText("Symbol, company or sector…")
        self.full_market_search.setFixedWidth(260)
        self.full_market_search.textChanged.connect(self._filter_full_market)
        header.addWidget(self.full_market_search)
        self.full_market_count_label = QLabel("")
        self.full_market_count_label.setObjectName("muted")
        header.addWidget(self.full_market_count_label)
        layout.addLayout(header)
        self.table_full_market = ReportTable()
        layout.addWidget(self.table_full_market, 1)
        self._full_market_rows: list[dict[str, str]] = []
        return page

    def _filter_full_market(self) -> None:
        query = self.full_market_search.text().strip().upper()
        rows = self._full_market_rows
        if query:
            rows = [
                row
                for row in rows
                if query in str(row.get("symbol", "")).upper()
                or query in str(row.get("company", "")).upper()
                or query in str(row.get("sector", "")).upper()
            ]
        self.table_full_market.load_rows(rows, FULL_MARKET_COLUMNS, 2000)
        self.full_market_count_label.setText(f"{len(rows)} of {len(self._full_market_rows)} stocks")

    def _table_page(self, key: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel(key.replace("_", " ").title())
        title.setObjectName("title")
        table = ReportTable()
        layout.addWidget(title)
        layout.addWidget(table, 1)
        setattr(self, f"table_{key}", table)
        return page

    def _breadth_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Market Breadth & Sector Rotation")
        title.setObjectName("title")
        layout.addWidget(title)
        self.breadth_cards = {
            "score": KpiCard("Breadth Score", "—", "#b48eff"),
            "advance": KpiCard("Advance / Decline", "—", "#58a6ff"),
            "volume": KpiCard("Up Volume", "—", "#32d296"),
            "upper": KpiCard("Upper-Cap Environment", "—", "#f5c451"),
        }
        grid = QGridLayout()
        for index, card in enumerate(self.breadth_cards.values()):
            grid.addWidget(card, 0, index)
        layout.addLayout(grid)
        self.table_breadth_sectors = ReportTable()
        layout.addWidget(self.table_breadth_sectors, 1)
        return page

    def _portfolio_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Portfolio, Risk & Open Positions")
        title.setObjectName("title")
        layout.addWidget(title)
        self.portfolio_cards = {
            "health": KpiCard("Health", "—", "#32d296"),
            "realized": KpiCard("Realized P/L", "—", "#32d296"),
            "unrealized": KpiCard("Unrealized P/L", "—", "#58a6ff"),
            "exposure": KpiCard("Exposure", "—", "#f5c451"),
        }
        grid = QGridLayout()
        for index, card in enumerate(self.portfolio_cards.values()):
            grid.addWidget(card, 0, index)
        layout.addLayout(grid)
        self.table_portfolio_analytics = ReportTable()
        layout.addWidget(self.table_portfolio_analytics, 1)
        return page

    def _live_portfolio_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Live Portfolio Monitor")
        title.setObjectName("title")
        layout.addWidget(title)
        self.live_portfolio_cards = {
            "active": KpiCard("Active Positions", "—", "#58a6ff"),
            "winning": KpiCard("Winning / Losing", "—", "#32d296"),
            "unrealized": KpiCard("Unrealized P/L", "—", "#32d296"),
            "return": KpiCard("Portfolio Return", "—", "#f5c451"),
        }
        grid = QGridLayout()
        for index, card in enumerate(self.live_portfolio_cards.values()):
            grid.addWidget(card, 0, index)
        layout.addLayout(grid)
        self.table_live_positions = ReportTable()
        layout.addWidget(self.table_live_positions, 1)
        return page

    def _refresh_live_portfolio(self) -> None:
        summary = read_last(report_path(self.paths, "live_portfolio_summary"))
        self.live_portfolio_cards["active"].set_value(
            integer(summary.get("active_positions"))
        )
        self.live_portfolio_cards["winning"].set_value(
            f"{integer(summary.get('winning_open_positions'))} / "
            f"{integer(summary.get('losing_open_positions'))}"
        )
        unrealized = number(summary.get("unrealized_profit_loss"))
        self.live_portfolio_cards["unrealized"].set_value(
            money(unrealized), "#32d296" if unrealized >= 0 else "#ff7685"
        )
        self.live_portfolio_cards["return"].set_value(
            f"{number(summary.get('portfolio_return_pct')):.2f}%"
        )
        self.table_live_positions.load_rows(
            read_csv(report_path(self.paths, "live_positions")),
            [
                "symbol", "company", "sector", "entry_date",
                "actual_entry_price", "remaining_quantity", "current_price",
                "market_value", "current_stop_loss", "target_1", "target_2",
                "unrealized_profit_loss", "unrealized_profit_loss_pct",
                "holding_days", "position_status", "recommended_action",
            ],
            300,
        )

    def _backtest_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        title = QLabel("Historical Backtest & Self-Learning Optimizer")
        title.setObjectName("title")
        layout.addWidget(title)

        self.backtest_cards = {
            "win_rate": KpiCard("Overall Win Rate", "—", "#32d296"),
            "profit_factor": KpiCard("Profit Factor", "—", "#58a6ff"),
            "expectancy": KpiCard("Expectancy / Trade", "—", "#f5c451"),
            "rating": KpiCard("Engine Rating", "—", "#b48eff"),
        }
        grid = QGridLayout()
        for index, card in enumerate(self.backtest_cards.values()):
            grid.addWidget(card, 0, index)
        layout.addLayout(grid)

        splitter = QSplitter(Qt.Vertical)

        decision_frame = QFrame()
        decision_frame.setObjectName("card")
        decision_layout = QVBoxLayout(decision_frame)
        decision_title = QLabel("Win Rate by Verdict Tier (STRONG BUY / BUY / WATCH)")
        decision_title.setObjectName("muted")
        self.table_backtest_by_decision = ReportTable()
        decision_layout.addWidget(decision_title)
        decision_layout.addWidget(self.table_backtest_by_decision)
        splitter.addWidget(decision_frame)

        optimizer_frame = QFrame()
        optimizer_frame.setObjectName("card")
        optimizer_layout = QVBoxLayout(optimizer_frame)
        optimizer_title = QLabel("Self-Learning Strategy Optimizer — Current Weights")
        optimizer_title.setObjectName("muted")
        self.table_strategy_optimizer = ReportTable()
        optimizer_layout.addWidget(optimizer_title)
        optimizer_layout.addWidget(self.table_strategy_optimizer)
        splitter.addWidget(optimizer_frame)

        splitter.setSizes([300, 300])
        layout.addWidget(splitter, 1)
        return page

    def _refresh_backtest(self) -> None:
        overall = read_last(report_path(self.paths, "backtest_overall"))
        self.backtest_cards["win_rate"].set_value(
            f"{number(overall.get('win_rate_pct')):.1f}%"
        )
        self.backtest_cards["profit_factor"].set_value(
            f"{number(overall.get('profit_factor')):.2f}"
        )
        self.backtest_cards["expectancy"].set_value(
            money(overall.get("expectancy_per_trade"))
        )
        self.backtest_cards["rating"].set_value(overall.get("engine_rating") or "—")
        self.table_backtest_by_decision.load_rows(
            read_csv(report_path(self.paths, "backtest_by_decision")),
            [
                "decision", "signals", "wins", "losses", "time_exits",
                "win_rate_pct", "profitable_rate_pct", "average_return_pct",
                "total_profit_loss", "profit_factor", "average_holding_days",
            ],
            50,
        )
        self.table_strategy_optimizer.load_rows(
            read_csv(report_path(self.paths, "strategy_optimizer")),
            [
                "strategy", "operating_status", "closed_trades",
                "win_rate_pct", "profit_factor", "current_weight",
                "suggested_weight", "weight_change_pct",
                "recommended_action", "optimizer_reason",
            ],
            50,
        )

    def _ai_assistant_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("AI Assistant  —  ask about today's scan (English or Urdu)")
        title.setObjectName("title")
        layout.addWidget(title)

        note = QLabel(
            "Answers come from today's scanner snapshot via Claude (claude-sonnet-4-6). "
            "Decision-support only, not financial advice. Needs ANTHROPIC_API_KEY in .env."
        )
        note.setObjectName("muted")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setFont(QFont("Segoe UI", 10))
        layout.addWidget(self.chat_history, 1)

        input_row = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText(
            "e.g. Is today good for buying?  /  MCB ke baare mein kya sochte ho?"
        )
        self.chat_input.returnPressed.connect(self.send_chat)
        self.chat_send = QPushButton("Send")
        self.chat_send.setObjectName("success")
        self.chat_send.clicked.connect(self.send_chat)
        input_row.addWidget(self.chat_input, 1)
        input_row.addWidget(self.chat_send)
        layout.addLayout(input_row)

        self.chat_messages: list[dict] = []
        self.chat_worker: ChatWorker | None = None
        self._chat_answer_parts: list[str] = []
        return page

    def send_chat(self) -> None:
        if self.chat_worker and self.chat_worker.isRunning():
            return
        question = self.chat_input.text().strip()
        if not question:
            return
        self.chat_input.clear()
        self.chat_history.append(f"<b>You:</b> {question}")
        self.chat_history.append("<b>AI:</b> ")
        self.chat_messages.append({"role": "user", "content": question})

        self._chat_answer_parts = []
        self.chat_input.setEnabled(False)
        self.chat_send.setEnabled(False)

        self.chat_worker = ChatWorker(self.paths.root, list(self.chat_messages))
        self.chat_worker.chunk.connect(self._chat_on_chunk)
        self.chat_worker.done.connect(self._chat_on_done)
        self.chat_worker.failed.connect(self._chat_on_error)
        self.chat_worker.start()

    def _chat_on_chunk(self, text: str) -> None:
        self._chat_answer_parts.append(text)
        cursor = self.chat_history.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.chat_history.setTextCursor(cursor)
        self.chat_history.ensureCursorVisible()

    def _chat_on_done(self) -> None:
        answer = "".join(self._chat_answer_parts)
        self.chat_messages.append({"role": "assistant", "content": answer})
        self.chat_history.append("")  # blank line between turns
        self.chat_input.setEnabled(True)
        self.chat_send.setEnabled(True)
        self.chat_input.setFocus()

    def _chat_on_error(self, message: str) -> None:
        self.chat_history.append(
            f"<span style='color:#ff7685;'>[error] {message}</span>"
        )
        self.chat_history.append("")
        # roll back the unanswered user turn so history stays consistent
        if self.chat_messages and self.chat_messages[-1]["role"] == "user":
            self.chat_messages.pop()
        self.chat_input.setEnabled(True)
        self.chat_send.setEnabled(True)
        self.chat_input.setFocus()

    def _console_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Scanner & Manual Execution Console")
        title.setObjectName("title")
        layout.addWidget(title)

        controls = QHBoxLayout()
        self.capital_input = QSpinBox()
        self.capital_input.setRange(1000, 1_000_000_000)
        self.capital_input.setValue(DEFAULT_CAPITAL)
        self.max_price_input = QDoubleSpinBox()
        self.max_price_input.setRange(1, 1_000_000)
        self.max_price_input.setValue(DEFAULT_MAX_PRICE)
        self.max_price_input.setDecimals(2)
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Optional daily file")
        browse = QPushButton("Browse")
        browse.clicked.connect(self.browse_daily_file)
        run = QPushButton("Run Full Scanner")
        run.setObjectName("success")
        run.clicked.connect(self.run_scanner)
        stop = QPushButton("Stop Process")
        stop.setObjectName("danger")
        stop.clicked.connect(self.stop_process)
        controls.addWidget(QLabel("Capital"))
        controls.addWidget(self.capital_input)
        controls.addWidget(QLabel("Max Price"))
        controls.addWidget(self.max_price_input)
        controls.addWidget(self.file_input, 1)
        controls.addWidget(browse)
        controls.addWidget(run)
        controls.addWidget(stop)
        layout.addLayout(controls)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Consolas", 9))
        layout.addWidget(self.console, 1)
        return page

    def refresh_all(self) -> None:
        self.status.showMessage("Refreshing reports…")
        self._refresh_market_signal()
        self._refresh_command_center()
        self._refresh_full_market()
        self._refresh_standard_tables()
        self._refresh_breadth()
        self._refresh_portfolio()
        self._refresh_live_portfolio()
        self._refresh_backtest()
        self.status.showMessage(
            f"Reports refreshed at {datetime.now().strftime('%H:%M:%S')}",
            5000,
        )

    def _refresh_command_center(self) -> None:
        command = read_last(report_path(self.paths, "command_summary"))
        breadth = read_last(report_path(self.paths, "breadth"))
        portfolio = read_last(report_path(self.paths, "portfolio_summary"))
        alerts = read_last(self.paths.report("alerts", "alert_summary.csv"))
        equity_rows = read_csv(report_path(self.paths, "equity"))
        opportunity = read_last(report_path(self.paths, "opportunity_categories"))

        market = command.get("market_view") or command.get("market_mood") or "—"
        self.kpis["market"].set_value(market)
        self.kpis["breadth"].set_value(
            f"{number(breadth.get('breadth_score')):.1f} {breadth.get('breadth_label', '')}"
        )
        risk = number(
            portfolio.get("portfolio_risk_pct")
            or command.get("portfolio_risk_pct")
        )
        self.kpis["risk"].set_value(f"{risk:.2f}%", "#32d296" if risk < 2 else "#f5c451")
        critical = integer(alerts.get("critical_alerts"))
        self.kpis["alerts"].set_value("CRITICAL" if critical else "NORMAL", "#ff6474" if critical else "#32d296")
        self.kpis["cash"].set_value(money(command.get("cash_available")))
        self.kpis["equity"].set_value(money(command.get("total_equity") or portfolio.get("total_equity")))
        self.kpis["best"].set_value(command.get("best_trade") or opportunity.get("symbol") or "—")
        self.kpis["open"].set_value(command.get("open_positions") or portfolio.get("open_positions") or "0")
        self.recommendation_label.setText(
            command.get("overall_recommendation")
            or "Run the scanner to generate institutional recommendations."
        )
        actions = read_csv(report_path(self.paths, "command_actions"))
        self.command_table.load_rows(
            actions,
            ["rank", "priority", "symbol", "action", "severity", "confidence", "reason", "source"],
            50,
        )
        values = [
            number(row.get("total_equity") or row.get("equity"))
            for row in equity_rows
        ]
        self.equity_chart.set_values([value for value in values if value > 0])

        brief_path = self.paths.report("ai_assistant", "ai_institutional_brief.md")
        if brief_path.exists():
            self.assistant_brief.setMarkdown(brief_path.read_text(encoding="utf-8"))
        else:
            self.assistant_brief.setPlainText(
                "Run the scanner to generate the AI Institutional Assistant brief."
            )

    def _refresh_full_market(self) -> None:
        self._full_market_rows = read_csv(report_path(self.paths, "full_market"))
        self._filter_full_market()

    def _refresh_standard_tables(self) -> None:
        specifications = {
            "opportunities": [
                "overall_rank", "symbol", "company", "sector", "close",
                "final_decision", "buy_probability", "smart_money_score",
                "trade_validation_score", "risk_permission", "risk_status",
                "entry_timing_action", "reward_risk_ratio", "opportunity_score",
                "opportunity_grade", "execution_bucket", "opportunity_type",
            ],
            "smart_money": [
                "rank", "symbol", "company", "sector", "close", "change_pct",
                "volume", "volume_ratio", "accumulation_score",
                "distribution_pressure", "breakout_quality", "retail_trap_risk",
                "smart_money_score_v2", "smart_money_label", "recommended_action",
            ],
            "alerts": [
                "priority", "severity", "alert_type", "symbol", "title",
                "recommended_action", "confidence", "message", "source_engine",
            ],
            "strategy_leaderboard": [
                "rank", "strategy", "strategy_score", "status", "closed_trades",
                "win_rate_pct", "profit_factor", "expectancy", "net_profit_loss",
                "maximum_drawdown_pct", "recommendation",
            ],
            "journal": [
                "trade_id", "symbol", "strategy", "entry_date", "exit_date",
                "trade_status", "trade_result", "realized_profit_loss",
                "unrealized_profit_loss", "return_pct", "lesson_learned",
            ],
            "trade_lifecycle": [
                "symbol", "company", "sector", "lifecycle_status", "trade_id",
                "portfolio_position_status", "actual_entry_price",
                "actual_quantity", "remaining_quantity", "average_cost",
                "current_stop_loss", "target_1", "target_2",
                "unrealized_profit_loss", "unrealized_profit_loss_pct",
                "holding_days_numeric",
            ],
            "exit_intelligence": [
                "symbol", "company", "sector", "lifecycle_status",
                "exit_action", "exit_suggested_action", "exit_reason",
                "exit_risk_level", "exit_current_price", "exit_entry_price",
                "exit_profit_loss_pct", "exit_suggested_stop_loss",
                "exit_trailing_stop", "exit_target_status", "exit_confidence",
            ],
        }
        for key, columns in specifications.items():
            table_widget = getattr(self, f"table_{key}")
            table_widget.load_rows(read_csv(report_path(self.paths, key)), columns, 500)

    def _refresh_breadth(self) -> None:
        summary = read_last(report_path(self.paths, "breadth"))
        self.breadth_cards["score"].set_value(
            f"{number(summary.get('breadth_score')):.1f} {summary.get('breadth_label', '')}"
        )
        self.breadth_cards["advance"].set_value(
            f"{integer(summary.get('advancing'))} / {integer(summary.get('declining'))}"
        )
        self.breadth_cards["volume"].set_value(f"{number(summary.get('up_volume_pct')):.1f}%")
        self.breadth_cards["upper"].set_value(summary.get("upper_cap_probability") or "—")
        self.table_breadth_sectors.load_rows(
            read_csv(report_path(self.paths, "breadth_sectors")),
            [
                "sector", "stocks", "advancing", "declining", "advance_pct",
                "average_change_pct", "up_volume_pct", "trend_positive_pct",
                "ai_strength_pct", "sector_breadth_score", "sector_breadth_label",
            ],
            100,
        )

    def _refresh_portfolio(self) -> None:
        summary = read_last(report_path(self.paths, "portfolio_summary"))
        self.portfolio_cards["health"].set_value(
            f"{number(summary.get('portfolio_health_score')):.1f}"
        )
        self.portfolio_cards["realized"].set_value(money(summary.get("realized_profit_loss")))
        self.portfolio_cards["unrealized"].set_value(money(summary.get("unrealized_profit_loss")))
        self.portfolio_cards["exposure"].set_value(
            f"{number(summary.get('portfolio_exposure_pct')):.1f}%"
        )
        self.table_portfolio_analytics.load_rows(
            read_csv(report_path(self.paths, "portfolio_analytics")),
            [
                "symbol", "sector", "position_status", "quantity", "entry_price",
                "current_price", "market_value", "position_weight_pct",
                "unrealized_profit_loss", "unrealized_profit_loss_pct",
                "stop_loss", "target_1", "target_2", "risk_status",
            ],
            200,
        )

    def run_scanner(self) -> None:
        args = [
            "--capital", str(self.capital_input.value()),
            "--max-price", str(self.max_price_input.value()),
        ]
        if self.file_input.text().strip():
            args += ["--file", self.file_input.text().strip()]
        self.start_main_process(args, "Full scanner")

    def list_pending_orders(self) -> None:
        self.start_main_process(["--order-list"], "Pending order list")

    def open_execution(self, mode: str) -> None:
        dialog = ExecutionDialog(mode, self)
        if dialog.exec() != QDialog.Accepted:
            return
        arguments = dialog.arguments()
        if not dialog.symbol.text().strip() or dialog.price.value() <= 0:
            QMessageBox.warning(self, "Missing details", "Symbol and execution price are required.")
            return
        command_text = " ".join([sys.executable, "main.py", *arguments])
        confirmation = QMessageBox.question(
            self,
            "Confirm manual execution",
            f"This records a manually confirmed broker execution.\n\n{command_text}\n\nProceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirmation == QMessageBox.Yes:
            self.start_main_process(arguments, f"Manual {mode}")

    def start_main_process(self, arguments: list[str], label: str) -> None:
        if self.process and self.process.state() != QProcess.NotRunning:
            QMessageBox.information(self, "Process running", "A scanner process is already running.")
            return
        if not self.paths.main_py.exists():
            QMessageBox.critical(self, "main.py missing", f"Not found:\n{self.paths.main_py}")
            return
        self.console.append(f"\n[{datetime.now():%H:%M:%S}] {label}")
        self.console.append(f"> {sys.executable} main.py {' '.join(arguments)}\n")
        self.process = QProcess(self)

        process_environment = QProcessEnvironment.systemEnvironment()
        process_environment.insert("PYTHONUTF8", "1")
        process_environment.insert("PYTHONIOENCODING", "utf-8")
        self.process.setProcessEnvironment(process_environment)

        self.process.setWorkingDirectory(str(self.paths.root))
        self.process.setProgram(sys.executable)
        self.process.setArguments([str(self.paths.main_py), *arguments])
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_process_output)
        self.process.finished.connect(self._process_finished)
        self.process.start()
        self.status.showMessage(f"{label} running…")
        self.select_page(15)

    def _read_process_output(self) -> None:
        if not self.process:
            return
        output = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        self.console.insertPlainText(output)
        self.console.ensureCursorVisible()

    def _process_finished(self, exit_code: int, exit_status) -> None:
        self.console.append(f"\nProcess finished with exit code {exit_code}.\n")
        self.status.showMessage(f"Process completed: exit code {exit_code}", 8000)
        if exit_code == 0:
            self.refresh_all()
        else:
            QMessageBox.warning(self, "Process failed", f"The process exited with code {exit_code}. Check the console.")

    def stop_process(self) -> None:
        if self.process and self.process.state() != QProcess.NotRunning:
            self.process.terminate()
            if not self.process.waitForFinished(3000):
                self.process.kill()
            self.console.append("\nProcess stopped by user.\n")

    def browse_daily_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select PSX daily file",
            str(self.paths.root),
            "PSX Files (*.Z *.zip *.csv);;All Files (*.*)",
        )
        if filename:
            self.file_input.setText(filename)

    def open_dashboard(self) -> None:
        candidates = [
            self.paths.report("latest_dashboard_v3.html"),
            self.paths.report("dashboard", "dashboard_v3.html"),
            self.paths.report("command_center", "ai_command_center.html"),
        ]
        for candidate in candidates:
            if candidate.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(candidate.resolve())))
                return
        QMessageBox.information(self, "Dashboard missing", "Run the scanner first to generate Dashboard V3.")

    def export_snapshot(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export terminal snapshot",
            str(self.paths.root / f"terminal_snapshot_{datetime.now():%Y%m%d_%H%M%S}.json"),
            "JSON Files (*.json)",
        )
        if not filename:
            return
        payload = {
            "terminal_version": APP_VERSION,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "command_summary": read_last(report_path(self.paths, "command_summary")),
            "breadth_summary": read_last(report_path(self.paths, "breadth")),
            "smart_money_summary": read_last(report_path(self.paths, "smart_money_summary")),
            "portfolio_summary": read_last(report_path(self.paths, "portfolio_summary")),
            "opportunity_categories": read_csv(report_path(self.paths, "opportunity_categories")),
            "critical_alerts": read_csv(report_path(self.paths, "critical_alerts")),
        }
        Path(filename).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        self.status.showMessage(f"Snapshot exported: {filename}", 8000)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.process and self.process.state() != QProcess.NotRunning:
            answer = QMessageBox.question(
                self,
                "Process running",
                "A scanner process is still running. Stop it and exit?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self.stop_process()
        event.accept()


def resolve_project_root(argument: str | None) -> Path:
    if argument:
        return Path(argument).expanduser().resolve()
    current = Path.cwd()
    if (current / "main.py").exists():
        return current
    script_parent = Path(__file__).resolve().parent
    if (script_parent / "main.py").exists():
        return script_parent
    return current


def main() -> int:
    parser = argparse.ArgumentParser(description=APP_VERSION)
    parser.add_argument("--project-root", default=None)
    args = parser.parse_args()

    project_root = resolve_project_root(args.project_root)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_VERSION)
    app.setOrganizationName("PSX AI Scanner")
    window = TerminalWindow(project_root)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
