"""Dialogs for adding/editing projects and payouts."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QSpinBox,
    QPushButton, QHBoxLayout, QComboBox, QTextEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from store import Store, VALID_PROJECT_STATUS, VALID_PAYOUT_KIND
from ui.styles import body_font


class ProjectDialog(QDialog):
    """Dialog for adding a project to a platform."""

    def __init__(self, parent=None, platform_id=None, store=None):
        super().__init__(parent)
        self.setWindowTitle("Add Project")
        self.resize(400, 300)
        self.store = store or parent.store if hasattr(parent, 'store') else None
        self.platform_id = platform_id

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. English Video Conversation Partner")
        form.addRow("Name:", self.name_edit)

        self.rate_edit = QLineEdit()
        self.rate_edit.setPlaceholderText("$50.00")
        form.addRow("Rate/hr ($):", self.rate_edit)

        self.eff_date_edit = QLineEdit()
        self.eff_date_edit.setPlaceholderText("2026-10-01")
        form.addRow("Effective from:", self.eff_date_edit)

        self.status_combo = QComboBox()
        self.status_combo.addItems(list(VALID_PROJECT_STATUS))
        form.addRow("Status:", self.status_combo)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Notes about this project...")
        self.notes_edit.setMaximumHeight(80)
        form.addRow("Notes:", self.notes_edit)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        ok_btn = QPushButton("Save")
        ok_btn.setObjectName("primary")
        ok_btn.clicked.connect(self._save)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def _save(self):
        from store import str_to_cents
        name = self.name_edit.text().strip()
        if not name:
            return
        rate = str_to_cents(self.rate_edit.text())
        eff_from = self.eff_date_edit.text().strip() or None
        status = self.status_combo.currentText()
        notes = self.notes_edit.toPlainText().strip() or None

        if self.store and self.platform_id:
            self.store.add_project(
                platform_id=self.platform_id,
                name=name,
                rate_cents_per_hour=rate,
                rate_effective_from=eff_from,
                status=status,
                notes=notes,
            )
        self.accept()


class PayoutDialog(QDialog):
    """Dialog for adding a payout to a platform."""

    def __init__(self, parent=None, platform_id=None, store=None):
        super().__init__(parent)
        self.setWindowTitle("Add Payout")
        self.resize(400, 250)
        self.store = store or parent.store if hasattr(parent, 'store') else None
        self.platform_id = platform_id

        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("2026-10-01")
        form.addRow("Received on:", self.date_edit)

        self.amount_edit = QLineEdit()
        self.amount_edit.setPlaceholderText("$125.00")
        form.addRow("Amount ($):", self.amount_edit)

        self.kind_combo = QComboBox()
        self.kind_combo.addItems(list(VALID_PAYOUT_KIND))
        form.addRow("Kind:", self.kind_combo)

        self.method_edit = QLineEdit()
        self.method_edit.setPlaceholderText("PayPal, AirTM, etc.")
        form.addRow("Method:", self.method_edit)

        self.period_edit = QLineEdit()
        self.period_edit.setPlaceholderText("2026-09-15 to 2026-09-30")
        form.addRow("Period:", self.period_edit)

        self.note_edit = QTextEdit()
        self.note_edit.setPlaceholderText("Note...")
        self.note_edit.setMaximumHeight(60)
        form.addRow("Note:", self.note_edit)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        ok_btn = QPushButton("Save")
        ok_btn.setObjectName("primary")
        ok_btn.clicked.connect(self._save)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def _save(self):
        from store import str_to_cents
        received_on = self.date_edit.text().strip()
        if not received_on:
            return
        amount = str_to_cents(self.amount_edit.text())
        if amount is None or amount <= 0:
            return
        kind = self.kind_combo.currentText()
        method = self.method_edit.text().strip() or None
        period = self.period_edit.text().strip() or None
        note = self.note_edit.toPlainText().strip() or None

        if self.store and self.platform_id:
            self.store.add_payout(
                platform_id=self.platform_id,
                received_on=received_on,
                amount_cents=amount,
                kind=kind,
                method=method,
                period_start=period.split(" to ")[0] if period and " to " in period else None,
                period_end=period.split(" to ")[1] if period and " to " in period else None,
                note=note,
            )
        self.accept()
