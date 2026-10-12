"""Platforms screen: list with status badges, VPN warnings, payout method; detail view."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
    QFormLayout, QTextEdit, QMessageBox, QDialog, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from store import Store, cents_to_str, today_utc
from ui.styles import header_font, body_font, badge_style, STATUS_COLORS, STATUS_LABELS, SETUP_STATUS_LABELS


class PlatformsScreen(QWidget):
    """Main screen listing all platforms."""

    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel("Platforms")
        header.setFont(header_font(18))
        layout.addWidget(header)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Platform", "Status", "Advertised Rate", "Payout", "Actions"]
        )
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setMinimumHeight(200)
        layout.addWidget(self.table)

        self.detail = PlatformDetail(self.store)
        layout.addWidget(self.detail)

        self._refresh()
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

    def _refresh(self):
        self._refresh_platforms()

    def _refresh_platforms(self):
        plats = self.store.get_all_platforms()
        self.table.setRowCount(len(plats))
        for i, plat in enumerate(plats):
            self.table.setItem(i, 0, QTableWidgetItem(plat['name']))

            status_item = QTableWidgetItem(STATUS_LABELS.get(plat['status'], plat['status']))
            color = STATUS_COLORS.get(plat['status'], '#6B7280')
            status_item.setBackground(QColor(color + "30"))
            status_item.setForeground(QColor(color))
            self.table.setItem(i, 1, status_item)

            rate_str = cents_to_str(plat['advertises_rate_cents']) if plat['advertises_rate_cents'] else "—"
            self.table.setItem(i, 2, QTableWidgetItem(rate_str))

            payout = plat['payout_method'] or "—"
            if plat['needs_vpn_off']:
                payout += " [VPN OFF]"
            self.table.setItem(i, 3, QTableWidgetItem(payout))

            btn = QPushButton("View")
            btn.clicked.connect(lambda _, p=plat: self.detail.show_platform(p['id']))
            self.table.setCellWidget(i, 4, btn)

    def _on_selection_changed(self):
        selected = self.table.currentRow()
        if selected >= 0:
            plat = self.store.get_all_platforms()[selected]
            self.detail.show_platform(plat['id'])


class PlatformDetail(QTabWidget):
    """Tabbed detail view for a single platform."""

    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self._current_platform_id = None

        self.addTab(self._make_overview_tab(), "Overview")
        self.addTab(self._make_projects_tab(), "Projects")
        self.addTab(self._make_setup_tab(), "Setup")
        self.addTab(self._make_sessions_tab(), "Sessions")
        self.addTab(self._make_payouts_tab(), "Payouts")
        self.addTab(self._make_notes_tab(), "Notes")

    def show_platform(self, platform_id):
        self._current_platform_id = platform_id
        self._refresh_all()

    def _make_overview_tab(self):
        widget = QWidget()
        layout = QFormLayout(widget)
        self._overview_items = {}
        layout.addRow("Name:", QLabel(""))
        layout.addRow("Status:", QLabel(""))
        layout.addRow("Login URL:", QLabel(""))
        layout.addRow("Advertised rate:", QLabel(""))
        layout.addRow("Payout method:", QLabel(""))
        layout.addRow("Needs VPN off:", QLabel(""))
        layout.addRow("Idle warn (days):", QLabel(""))
        return widget

    def _make_projects_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.projects_table = QTableWidget()
        self.projects_table.setColumnCount(4)
        self.projects_table.setHorizontalHeaderLabels(
            ["Project", "Rate/hr", "Status", "Effective From"]
        )
        self.projects_table.verticalHeader().setVisible(False)
        self.projects_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.projects_table)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add project")
        add_btn.clicked.connect(self._add_project)
        btn_layout.addWidget(add_btn)
        layout.addLayout(btn_layout)
        return widget

    def _make_setup_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.setup_table = QTableWidget()
        self.setup_table.setColumnCount(4)
        self.setup_table.setHorizontalHeaderLabels(
            ["Task", "Human-only", "Status", "Due"]
        )
        self.setup_table.verticalHeader().setVisible(False)
        self.setup_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setup_table.setMinimumHeight(150)
        layout.addWidget(self.setup_table)

        btn_layout = QHBoxLayout()
        self.setup_status_combo = QComboBox()
        self.setup_status_combo.addItems(["todo", "doing", "done", "skipped"])
        self.setup_status_combo.currentTextChanged.connect(self._change_setup_status)
        btn_layout.addWidget(QLabel("Mark selected:"))
        btn_layout.addWidget(self.setup_status_combo)
        layout.addLayout(btn_layout)
        return widget

    def _make_sessions_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.sessions_table = QTableWidget()
        self.sessions_table.setColumnCount(5)
        self.sessions_table.setHorizontalHeaderLabels(
            ["Started", "Ended", "Hours", "Rate/hr", "Items"]
        )
        self.sessions_table.verticalHeader().setVisible(False)
        self.sessions_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.sessions_table)
        return widget

    def _make_payouts_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.payouts_table = QTableWidget()
        self.payouts_table.setColumnCount(4)
        self.payouts_table.setHorizontalHeaderLabels(
            ["Date", "Amount", "Kind", "Method"]
        )
        self.payouts_table.verticalHeader().setVisible(False)
        self.payouts_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.payouts_table)

        add_btn = QPushButton("Add payout")
        add_btn.clicked.connect(self._add_payout)
        layout.addWidget(add_btn)
        return widget

    def _make_notes_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.notes_edit = QTextEdit()
        self.notes_edit.textChanged.connect(self._save_notes)
        layout.addWidget(self.notes_edit)
        return widget

    def _refresh_all(self):
        if not self._current_platform_id:
            return
        self._refresh_overview()
        self._refresh_projects()
        self._refresh_setup()
        self._refresh_sessions()
        self._refresh_payouts()
        self._refresh_notes()

    def _refresh_overview(self):
        plat = self.store.get_platform(self._current_platform_id)
        if not plat:
            return
        items = self.overview_widget().layout()
        labels = ["", ""]
        for i in range(1, items.rows()):
            lbl_widget = items.item(i, 1).widget()
            key = items.item(i, 0).widget().text().rstrip(":")
            self._set_overview_field(lbl_widget, key, plat)

    def overview_widget(self):
        return self.widget(0)

    def _set_overview_field(self, label_widget, key, plat):
        if key == "Name":
            label_widget.setText(plat['name'])
        elif key == "Status":
            label_widget.setText(STATUS_LABELS.get(plat['status'], plat['status']))
            label_widget.setStyleSheet(badge_style(STATUS_COLORS.get(plat['status'], '#6B7280')))
        elif key == "Login URL":
            label_widget.setText(plat['login_url'] or "—")
        elif key == "Advertised rate":
            label_widget.setText(cents_to_str(plat['advertises_rate_cents']) if plat['advertises_rate_cents'] else "—")
        elif key == "Payout method":
            txt = plat['payout_method'] or "—"
            if plat['needs_vpn_off']:
                txt += " (VPN OFF required)"
            label_widget.setText(txt)
        elif key == "Needs VPN off":
            label_widget.setText("Yes" if plat['needs_vpn_off'] else "No")
            if plat['needs_vpn_off']:
                label_widget.setStyleSheet("color: #EF4444; font-weight: bold;")
        elif key == "Idle warn (days)":
            label_widget.setText(str(plat['idle_warn_days']) if plat['idle_warn_days'] else "—")

    def _refresh_projects(self):
        projs = self.store.get_projects_for_platform(self._current_platform_id)
        self.projects_table.setRowCount(len(projs))
        for i, proj in enumerate(projs):
            self.projects_table.setItem(i, 0, QTableWidgetItem(proj['name']))
            self.projects_table.setItem(i, 1, QTableWidgetItem(
                cents_to_str(proj['rate_cents_per_hour']) if proj['rate_cents_per_hour'] else "—"
            ))
            status_item = QTableWidgetItem(proj['status'])
            color = STATUS_COLORS.get(proj['status'], '#6B7280')
            status_item.setForeground(QColor(color))
            self.projects_table.setItem(i, 2, status_item)
            self.projects_table.setItem(i, 3, QTableWidgetItem(
                proj['rate_effective_from'] or ""
            ))

    def _refresh_setup(self):
        tasks = self.store.get_setup_tasks(platform_id=self._current_platform_id)
        self.setup_table.setRowCount(len(tasks))
        self._setup_tasks = tasks
        for i, task in enumerate(tasks):
            self.setup_table.setItem(i, 0, QTableWidgetItem(task['title']))
            self.setup_table.setItem(i, 1, QTableWidgetItem("Yes" if task['is_human_only'] else "No"))
            status_item = QTableWidgetItem(task['status'])
            self.setup_table.setItem(i, 2, status_item)
            self.setup_table.setItem(i, 3, QTableWidgetItem(task['due_date'] or ""))

    def _change_setup_status(self, status):
        selected = self.setup_table.currentRow()
        if selected < 0:
            return
        task = self._setup_tasks[selected]
        self.store.update_setup_task(task['id'], status=status)
        if status in ('done', 'skipped'):
            self.store.update_setup_task(task['id'], completed_at=today_utc() + "T00:00:00+00:00")
        self._refresh_setup()

    def _refresh_sessions(self):
        sessions = self.store.get_sessions(platform_id=self._current_platform_id)
        self.sessions_table.setRowCount(len(sessions))
        for i, sess in enumerate(sessions):
            self.sessions_table.setItem(i, 0, QTableWidgetItem(sess['started_at'] or ""))
            self.sessions_table.setItem(i, 1, QTableWidgetItem(sess['ended_at'] or ""))
            hrs = _session_hours(sess)
            self.sessions_table.setItem(i, 2, QTableWidgetItem(
                f"{hrs:.2f}" if hrs is not None else "—"
            ))
            self.sessions_table.setItem(i, 3, QTableWidgetItem(
                cents_to_str(sess['rate_cents_per_hour']) + "/hr" if sess['rate_cents_per_hour'] else "—"
            ))
            count = sess['item_count']
            self.sessions_table.setItem(i, 4, QTableWidgetItem(
                str(count) if count is not None else "— (skipped)"
            ))

    def _refresh_payouts(self):
        payouts = self.store.get_payouts(platform_id=self._current_platform_id)
        self.payouts_table.setRowCount(len(payouts))
        for i, p in enumerate(payouts):
            self.payouts_table.setItem(i, 0, QTableWidgetItem(p['received_on'] or ""))
            self.payouts_table.setItem(i, 1, QTableWidgetItem(cents_to_str(p['amount_cents'])))
            self.payouts_table.setItem(i, 2, QTableWidgetItem(p['kind']))
            self.payouts_table.setItem(i, 3, QTableWidgetItem(p['method'] or ""))

    def _refresh_notes(self):
        plat = self.store.get_platform(self._current_platform_id)
        self.notes_edit.blockSignals(True)
        self.notes_edit.setPlainText(plat['notes'] or "")
        self.notes_edit.blockSignals(False)

    def _save_notes(self):
        if not self._current_platform_id:
            return
        self.store.update_platform(self._current_platform_id, notes=self.notes_edit.toPlainText())

    def _add_project(self):
        from ui.dialogs import ProjectDialog
        dialog = ProjectDialog(self, platform_id=self._current_platform_id, store=self.store)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh_projects()

    def _add_payout(self):
        from ui.dialogs import PayoutDialog
        dialog = PayoutDialog(self, platform_id=self._current_platform_id, store=self.store)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh_payouts()


def _session_hours(sess):
    if not sess['started_at'] or not sess['ended_at']:
        return None
    try:
        from store import hours_between
        return hours_between(sess['started_at'], sess['ended_at'])
    except Exception:
        return None


