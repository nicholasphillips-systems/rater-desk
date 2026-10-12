"""Money screen: quick-add payout, add cost, per-platform real $/hr and net table."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QComboBox, QFormLayout, QLineEdit, QTextEdit, QTabWidget
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont

from store import (
    Store, cents_to_str, str_to_cents, format_real_rate,
    real_rate, hours_between, VALID_PAYOUT_KIND, VALID_COST_RECURRING,
    today_utc,
)
from ui.styles import header_font, body_font, badge_style, STATUS_COLORS
from ui.dialogs import PayoutDialog, ProjectDialog


class MoneyScreen(QWidget):
    """Money screen: per-platform rate/net table with date-range picker."""

    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel("Money")
        header.setFont(header_font(18))
        layout.addWidget(header)

        # Date range controls
        range_layout = QHBoxLayout()
        range_layout.addWidget(QLabel("Date range:"))

        self.start_date_edit = QLineEdit()
        self.start_date_edit.setPlaceholderText("2026-01-01 (leave blank = all)")
        self.start_date_edit.setMaximumWidth(150)
        range_layout.addWidget(self.start_date_edit)

        self.end_date_edit = QLineEdit()
        self.end_date_edit.setPlaceholderText("2026-12-31 (leave blank = all)")
        self.end_date_edit.setMaximumWidth(150)
        range_layout.addWidget(self.end_date_edit)

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._on_date_range)
        range_layout.addWidget(apply_btn)

        this_week_btn = QPushButton("This week")
        this_week_btn.clicked.connect(self._set_this_week)
        range_layout.addWidget(this_week_btn)

        this_month_btn = QPushButton("This month")
        this_month_btn.clicked.connect(self._set_this_month)
        range_layout.addWidget(this_month_btn)

        range_layout.addStretch()
        layout.addLayout(range_layout)

        # Summary row
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("font-size: 14px; margin: 10px 0;")
        layout.addWidget(self.summary_label)

        # Platform rate table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Platform", "Advt Rate", "Real $/hr", "Hours",
            "Earnings", "Cost", "Net"
        ])
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 7):
            header_view.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        # Quick action buttons
        btn_layout = QHBoxLayout()
        self.quick_payout_btn = QPushButton("Quick-add payout")
        self.quick_payout_btn.setObjectName("primary")
        self.quick_payout_btn.clicked.connect(self._quick_add_payout)
        btn_layout.addWidget(self.quick_payout_btn)

        self.add_cost_btn = QPushButton("Add cost")
        self.add_cost_btn.clicked.connect(self._add_cost)
        btn_layout.addWidget(self.add_cost_btn)

        export_btn = QPushButton("Export CSV")
        export_btn.clicked.connect(self._export_csv)
        btn_layout.addWidget(export_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._refresh()

    def _set_this_week(self):
        from ui.today import _week_start_iso
        start = _week_start_iso(today_utc())
        self.start_date_edit.setText(start)
        self.end_date_edit.setText(today_utc())
        self._on_date_range()

    def _set_this_month(self):
        today = today_utc()
        year, month = today.split("-")[:2]
        self.start_date_edit.setText(f"{year}-{month}-01")
        self.end_date_edit.setText(today)
        self._on_date_range()

    def _on_date_range(self):
        self._refresh()

    def _get_date_range(self):
        start = self.start_date_edit.text().strip() or None
        end = self.end_date_edit.text().strip() or None
        return start, end

    def _refresh(self):
        start, end = self._get_date_range()
        report = self.store.full_report(start_date=start, end_date=end)
        self._render_report(report)

    def _render_report(self, report):
        plats = report['platforms']
        self.table.setRowCount(len(plats))

        for i, p in enumerate(plats):
            self.table.setItem(i, 0, QTableWidgetItem(p['name']))

            advt = cents_to_str(p['advertised_rate_cents']) if p['advertised_rate_cents'] else "—"
            self.table.setItem(i, 1, QTableWidgetItem(advt))

            real_rate_str = format_real_rate(p['earnings_cents'], p['hours'])
            self.table.setItem(i, 2, QTableWidgetItem(real_rate_str))

            self.table.setItem(i, 3, QTableWidgetItem(f"{p['hours']:.2f}" if p['hours'] else "—"))

            self.table.setItem(i, 4, QTableWidgetItem(cents_to_str(p['earnings_cents']) if p['earnings_cents'] else "$0.00"))

            # Color-code real rate vs advertised
            if p['advertised_rate_cents'] and p['real_rate_cents_per_hour']:
                advt_cents = p['advertised_rate_cents']
                real_cents = p['real_rate_cents_per_hour']
                if abs(real_cents - advt_cents) / max(advt_cents, 1) > 0.3:
                    rate_item = self.table.item(i, 2)
                    rate_item.setForeground(Qt.GlobalColor.red)

        total = report['total_earnings_cents']
        costs = report['total_costs_cents']
        net = report['total_net_cents']

        self.summary_label.setText(
            f"Total earnings: {cents_to_str(total)}  |  Total costs: {cents_to_str(costs)}  |  "
            f"<b>Net: {cents_to_str(net)}</b>"
        )

    def _quick_add_payout(self):
        platforms = self.store.get_all_platforms()
        if not platforms:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Quick-add Payout")
        dialog.resize(350, 180)
        layout = QFormLayout(dialog)

        platform_combo = QComboBox()
        for plat in platforms:
            platform_combo.addItem(plat['name'], plat['id'])
        layout.addRow("Platform:", platform_combo)

        amount_edit = QLineEdit()
        amount_edit.setPlaceholderText("$125.00")
        layout.addRow("Amount:", amount_edit)

        kind_combo = QComboBox()
        kind_combo.addItems(list(VALID_PAYOUT_KIND))
        layout.addRow("Kind:", kind_combo)

        method_edit = QLineEdit()
        method_edit.setPlaceholderText("PayPal (repeats last)")
        layout.addRow("Method:", method_edit)

        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        ok_btn = QPushButton("Add")
        ok_btn.setObjectName("primary")
        btn_layout.addWidget(ok_btn)
        layout.addRow(btn_layout)

        def do_add():
            amount = str_to_cents(amount_edit.text())
            if amount is None or amount <= 0:
                return
            pid = platform_combo.currentData()
            self.store.add_payout(
                platform_id=pid,
                received_on=today_utc(),
                amount_cents=amount,
                kind=kind_combo.currentText(),
                method=method_edit.text().strip() or None,
            )
            dialog.accept()

        ok_btn.clicked.connect(do_add)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh()

    def _add_cost(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Cost")
        dialog.resize(350, 200)
        layout = QFormLayout(dialog)

        label_edit = QLineEdit()
        label_edit.setPlaceholderText("e.g. ProtonVPN, tax software")
        layout.addRow("Label:", label_edit)

        amount_edit = QLineEdit()
        amount_edit.setPlaceholderText("$10.00")
        layout.addRow("Amount:", amount_edit)

        date_edit = QLineEdit()
        date_edit.setPlaceholderText(today_utc())
        layout.addRow("Date:", date_edit)

        recurring_combo = QComboBox()
        recurring_combo.addItems(list(VALID_COST_RECURRING))
        layout.addRow("Recurring:", recurring_combo)

        note_edit = QTextEdit()
        note_edit.setPlaceholderText("Note...")
        note_edit.setMaximumHeight(60)
        layout.addRow("Note:", note_edit)

        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        ok_btn = QPushButton("Save")
        ok_btn.setObjectName("primary")
        btn_layout.addWidget(ok_btn)
        layout.addRow(btn_layout)

        def do_save():
            label = label_edit.text().strip()
            if not label:
                return
            amount = str_to_cents(amount_edit.text())
            if amount is not None and amount < 0:
                amount = None
            date_str = date_edit.text().strip() or today_utc()
            self.store.add_cost(
                label=label,
                amount_cents=amount,
                incurred_on=date_str,
                recurring=recurring_combo.currentText(),
                note=note_edit.toPlainText().strip() or None,
            )
            dialog.accept()

        ok_btn.clicked.connect(do_save)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh()

    def _export_csv(self):
        from ui.csv_export import export_csv_dialog
        export_csv_dialog(self, self.store)
