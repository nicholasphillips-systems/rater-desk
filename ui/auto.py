"""Auto screen: the auto timer switch, Gmail accounts for email detection, and a log
of everything auto mode found and changed."""

import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QCheckBox,
    QListWidget, QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QFormLayout, QLineEdit, QMessageBox, QApplication,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

import mailwatch
from store import Store
from ui.styles import header_font, badge_style

SECTION_STYLE = "color: #9CA3AF; font-size: 13px; margin-top: 16px;"
HINT_STYLE = "color: #6B7280; font-size: 11px;"

KIND_COLORS = {
    'payout': '#10B981', 'accepted': '#10B981', 'account': '#3B82F6', 'done': '#3B82F6',
    'action': '#F59E0B', 'opportunity': '#8B5CF6', 'rejected': '#EF4444',
    'payout_unmatched': '#F59E0B',
}


def local_time(iso):
    """'2026-10-14T15:02:11+00:00' -> 'Oct 14 11:02' in local time."""
    try:
        when = datetime.datetime.fromisoformat(iso).astimezone()
    except (TypeError, ValueError):
        return iso or ""
    return when.strftime("%b %d %H:%M")


class AutoScreen(QWidget):
    auto_timer_toggled = pyqtSignal(bool)
    check_mail_requested = pyqtSignal()

    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel("Auto")
        header.setFont(header_font(18))
        layout.addWidget(header)

        # -- Auto timer
        label = QLabel("Auto timer")
        label.setStyleSheet(SECTION_STYLE)
        layout.addWidget(label)

        self.timer_check = QCheckBox("Start and stop the timer from the browser tab I'm in")
        self.timer_check.setChecked(self.store.get_setting("auto_timer", "1") == "1")
        self.timer_check.toggled.connect(self._on_timer_toggled)
        layout.addWidget(self.timer_check)

        self.timer_status = QLabel("")
        self.timer_status.setStyleSheet("font-size: 13px;")
        layout.addWidget(self.timer_status)

        hint = QLabel("Starts 45 s after a platform's site is in front, counted from when you opened it. "
                      "Stops 5 min after you leave every platform tab, 15 min after your last input, "
                      "or when the screen locks. A timer you start by hand always wins.")
        hint.setWordWrap(True)
        hint.setStyleSheet(HINT_STYLE)
        layout.addWidget(hint)

        # -- Email
        label = QLabel("Email")
        label.setStyleSheet(SECTION_STYLE)
        layout.addWidget(label)

        self.accounts_list = QListWidget()
        self.accounts_list.setMaximumHeight(70)
        layout.addWidget(self.accounts_list)

        row = QHBoxLayout()
        add_btn = QPushButton("Add Gmail...")
        add_btn.clicked.connect(self._add_account)
        row.addWidget(add_btn)
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self._remove_account)
        row.addWidget(self.remove_btn)
        self.check_btn = QPushButton("Check now")
        self.check_btn.setStyleSheet(badge_style("#3B82F6"))
        self.check_btn.clicked.connect(self.check_mail_requested.emit)
        row.addWidget(self.check_btn)
        row.addStretch()
        layout.addLayout(row)

        self.mail_status = QLabel("")
        self.mail_status.setWordWrap(True)
        self.mail_status.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.mail_status)

        hint = QLabel("Reads only mail from the platforms and from PayPal / Payoneer, every 10 minutes. "
                      "Payments become payouts, sign-ups and acceptances move the platform's status "
                      "forward, and \"finish this step\" reminders become setup tasks. Nothing in your "
                      "mailbox is changed or marked read.")
        hint.setWordWrap(True)
        hint.setStyleSheet(HINT_STYLE)
        layout.addWidget(hint)

        # -- Log
        label = QLabel("What auto mode found")
        label.setStyleSheet(SECTION_STYLE)
        layout.addWidget(label)

        self.log_table = QTableWidget()
        self.log_table.setColumnCount(3)
        self.log_table.setHorizontalHeaderLabels(["When", "What", "Changed"])
        hv = self.log_table.horizontalHeader()
        hv.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hv.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hv.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.log_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.log_table, 1)

    # -- refresh

    def refresh(self):
        self._refresh_accounts()
        self._refresh_mail_status()
        self._refresh_log()

    def set_timer_status(self, text):
        self.timer_status.setText(text)

    def set_mail_busy(self, busy):
        self.check_btn.setEnabled(not busy)
        if busy:
            self.mail_status.setText("Checking mail...")

    def _refresh_accounts(self):
        self.accounts_list.clear()
        accounts = mailwatch.get_accounts(self.store)
        for address in accounts:
            self.accounts_list.addItem(address)
        if not accounts:
            self.accounts_list.addItem("No Gmail added yet")
        self.remove_btn.setEnabled(bool(accounts))
        self.check_btn.setEnabled(bool(accounts))

    def _refresh_mail_status(self):
        last = self.store.get_setting("mail_last_check")
        error = self.store.get_setting("mail_last_error")
        if not mailwatch.get_accounts(self.store):
            self.mail_status.setText("")
            return
        text = f"Last checked {local_time(last)}" if last else "Not checked yet"
        if error:
            text += f"  -  {error}"
            self.mail_status.setStyleSheet("font-size: 12px; color: #F87171;")
        else:
            self.mail_status.setStyleSheet("font-size: 12px; color: #9CA3AF;")
        self.mail_status.setText(text)

    def _refresh_log(self):
        rows = self.store.get_detections(limit=300)
        self.log_table.setRowCount(len(rows))
        for i, d in enumerate(rows):
            self.log_table.setItem(i, 0, QTableWidgetItem(local_time(d['happened_at'] or d['detected_at'])))
            what = QTableWidgetItem(d['summary'])
            what.setToolTip(d['summary'])
            self.log_table.setItem(i, 1, what)
            change = QTableWidgetItem(d['change'] or "logged only")
            if not d['change']:
                change.setForeground(QColor("#6B7280"))
            color = KIND_COLORS.get(d['kind'])
            if color:
                what.setForeground(QColor(color))
            self.log_table.setItem(i, 2, change)

    # -- actions

    def _on_timer_toggled(self, on):
        self.store.set_setting("auto_timer", "1" if on else "0")
        self.auto_timer_toggled.emit(on)

    def _add_account(self):
        dialog = AddGmailDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                mailwatch.add_account(self.store, dialog.address, dialog.app_password)
            except Exception as e:
                QMessageBox.warning(self, "Couldn't save", f"The password store refused it: {e}")
                return
            self.refresh()
            self.check_mail_requested.emit()

    def _remove_account(self):
        item = self.accounts_list.currentItem()
        accounts = mailwatch.get_accounts(self.store)
        address = item.text() if item and item.text() in accounts else (accounts[0] if len(accounts) == 1 else None)
        if not address:
            QMessageBox.information(self, "Remove", "Click the address to remove first.")
            return
        mailwatch.remove_account(self.store, address)
        self.refresh()


class AddGmailDialog(QDialog):
    """Address + app password; checks the login with Gmail before saving."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Gmail")
        self.setMinimumWidth(440)
        self.address = None
        self.app_password = None

        layout = QVBoxLayout(self)
        steps = QLabel(
            "Gmail needs an <b>app password</b> for this, not your normal one:<br>"
            "1. Open <a href='https://myaccount.google.com/apppasswords'>"
            "myaccount.google.com/apppasswords</a> signed in as this address.<br>"
            "2. Name it <i>Rater Desk</i> and click Create.<br>"
            "3. Paste the 16 letters below.<br>"
            "<span style='color:#9CA3AF'>No App passwords page? Turn on 2-Step Verification first.</span>")
        steps.setOpenExternalLinks(True)
        steps.setWordWrap(True)
        layout.addWidget(steps)

        form = QFormLayout()
        self.address_edit = QLineEdit()
        self.address_edit.setPlaceholderText("you@gmail.com")
        form.addRow("Gmail address:", self.address_edit)
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("abcd efgh ijkl mnop")
        form.addRow("App password:", self.password_edit)
        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #F87171;")
        layout.addWidget(self.error_label)

        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        self.save_btn = QPushButton("Check and save")
        self.save_btn.setStyleSheet(badge_style("#3B82F6"))
        self.save_btn.clicked.connect(self._save)
        row.addWidget(self.save_btn)
        layout.addLayout(row)

    def _save(self):
        address = self.address_edit.text().strip()
        password = mailwatch.clean_app_password(self.password_edit.text())
        if "@" not in address or not password:
            self.error_label.setText("Fill in both.")
            return
        self.error_label.setText("Checking with Gmail...")
        self.save_btn.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            problem = mailwatch.test_login(address, password)
        finally:
            QApplication.restoreOverrideCursor()
            self.save_btn.setEnabled(True)
        if problem:
            self.error_label.setText(problem)
            return
        self.address, self.app_password = address, password
        self.accept()
