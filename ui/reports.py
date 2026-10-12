"""Reports screen: this week / this month, best real $/hr, idle platforms, deadlines."""

import datetime
from datetime import date, timedelta

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from store import Store, cents_to_str, format_real_rate, hours_between, today_utc
from ui.styles import header_font, body_font


class ReportsScreen(QWidget):
    """Reports: earnings summary, best real $/hr, idle platforms, deadlines."""

    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel("Reports")
        header.setFont(header_font(18))
        layout.addWidget(header)

        # Period selector
        period_layout = QHBoxLayout()
        self.period_label = QLabel("Period: This week")
        period_layout.addWidget(self.period_label)

        this_week_btn = QPushButton("This week")
        this_week_btn.clicked.connect(lambda: self._set_period("week"))
        period_layout.addWidget(this_week_btn)

        this_month_btn = QPushButton("This month")
        this_month_btn.clicked.connect(lambda: self._set_period("month"))
        period_layout.addWidget(this_month_btn)

        all_btn = QPushButton("All time")
        all_btn.clicked.connect(lambda: self._set_period("all"))
        period_layout.addWidget(all_btn)

        period_layout.addStretch()
        layout.addLayout(period_layout)

        self._period_key = "week"

        # Earnings table
        self.earnings_table = QTableWidget()
        self.earnings_table.setColumnCount(4)
        self.earnings_table.setHorizontalHeaderLabels(
            ["Platform", "Real $/hr", "Hours", "Earnings"]
        )
        header_view = self.earnings_table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 4):
            header_view.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.earnings_table.verticalHeader().setVisible(False)
        layout.addWidget(self.earnings_table)

        # Idle platforms
        idle_label = QLabel("Idle platforms (no work since setup)")
        idle_label.setStyleSheet("color: #9CA3AF; margin-top: 12px;")
        layout.addWidget(idle_label)

        self.idle_table = QTableWidget()
        self.idle_table.setColumnCount(3)
        self.idle_table.setHorizontalHeaderLabels(
            ["Platform", "Status", "Last activity"]
        )
        self.idle_table.verticalHeader().setVisible(False)
        self.idle_table.setMinimumHeight(150)
        layout.addWidget(self.idle_table)

        # Deadlines
        deadlines_label = QLabel("Upcoming deadlines")
        deadlines_label.setStyleSheet("color: #9CA3AF; margin-top: 12px;")
        layout.addWidget(deadlines_label)

        self.deadlines_table = QTableWidget()
        self.deadlines_table.setColumnCount(3)
        self.deadlines_table.setHorizontalHeaderLabels(
            ["Platform", "Task", "Due"]
        )
        self.deadlines_table.verticalHeader().setVisible(False)
        self.deadlines_table.setMinimumHeight(150)
        layout.addWidget(self.deadlines_table)

        self._set_period("week")

    def _set_period(self, period):
        if period == "week":
            self.period_label.setText("Period: This week")
            start, end = _week_bounds("week")
        elif period == "month":
            self.period_label.setText("Period: This month")
            start, end = _week_bounds("month")
        else:
            self.period_label.setText("Period: All time")
            start, end = None, None

        self._render_table(start, end)
        self._render_idle(start, end)
        self._render_deadlines()

    def _render_table(self, start, end):
        report = self.store.full_report(start_date=start, end_date=end)
        plats = [p for p in report['platforms'] if p['earnings_cents'] > 0 or p['hours'] > 0]
        self.earnings_table.setRowCount(len(plats))

        for i, p in enumerate(plats):
            self.earnings_table.setItem(i, 0, QTableWidgetItem(p['name']))
            self.earnings_table.setItem(i, 1, QTableWidgetItem(
                format_real_rate(p['earnings_cents'], p['hours'])
            ))
            self.earnings_table.setItem(i, 2, QTableWidgetItem(
                f"{p['hours']:.2f}" if p['hours'] else "—"
            ))
            self.earnings_table.setItem(i, 3, QTableWidgetItem(
                cents_to_str(p['earnings_cents'])
            ))

        # Add net row
        self.earnings_table.insertRow(len(plats))
        self.earnings_table.setItem(len(plats), 0, QTableWidgetItem("NET"))
        net_item = self.earnings_table.item(len(plats), 0)
        if net_item:
            net_item.setFont(body_font(12))
            net_item.setForeground(Qt.GlobalColor.white)
        for col in range(1, 3):
            item = QTableWidgetItem("")
            self.earnings_table.setItem(len(plats), col, item)
        net_item = QTableWidgetItem(cents_to_str(report['total_net_cents']))
        if report['total_net_cents'] < 0:
            net_item.setForeground(Qt.GlobalColor.red)
        self.earnings_table.setItem(len(plats), 3, net_item)

    def _render_idle(self, start, end):
        plats = self.store.get_all_platforms()
        idle = []
        for plat in plats:
            if plat['status'] in ('active', 'paused'):
                sessions = self.store.get_sessions(platform_id=plat['id'], limit=1)
                if not sessions:
                    idle.append(plat)
                elif not sessions[0]['ended_at']:
                    # Still running session — not idle
                    pass
                elif hours_between(sessions[0]['ended_at'], None) < 0:
                    idle.append(plat)

        self.idle_table.setRowCount(len(idle))
        for i, plat in enumerate(idle):
            self.idle_table.setItem(i, 0, QTableWidgetItem(plat['name']))
            self.idle_table.setItem(i, 1, QTableWidgetItem(plat['status']))
            sessions = self.store.get_sessions(platform_id=plat['id'], limit=1)
            last = sessions[0]['ended_at'] if sessions else "never"
            self.idle_table.setItem(i, 2, QTableWidgetItem(last or "never"))

    def _render_deadlines(self):
        today = today_utc()

        tasks = self.store.get_due_setup_tasks(today)
        self.deadlines_table.setRowCount(len(tasks))
        for i, task in enumerate(tasks):
            plat_name = ""
            if task['platform_id']:
                plat = self.store.get_platform(task['platform_id'])
                if plat:
                    plat_name = plat['name']
            self.deadlines_table.setItem(i, 0, QTableWidgetItem(plat_name))
            self.deadlines_table.setItem(i, 1, QTableWidgetItem(task['title']))
            self.deadlines_table.setItem(i, 2, QTableWidgetItem(
                task['due_date'] or "no due date"
            ))


def _week_bounds(period):
    today = date.today()
    if period == "week":
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        return monday.isoformat(), sunday.isoformat()
    elif period == "month":
        first = today.replace(day=1)
        next_month = first.replace(day=28) + timedelta(days=4)
        last = next_month - timedelta(days=next_month.day)
        return first.isoformat(), last.isoformat()
    return None, None


def _month_end(date_str):
    try:
        d = datetime.date.fromisoformat(date_str)
        next_month = d.replace(day=28) + datetime.timedelta(days=4)
        return next_month - datetime.timedelta(days=next_month.day)
    except Exception:
        return None
