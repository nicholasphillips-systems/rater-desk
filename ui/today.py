"""Today screen: timer card, planned blocks, setup tasks due today, money this week."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QTableWidget, QTableWidgetItem, QSizePolicy, QHeaderView,
    QMessageBox, QDialog, QComboBox, QSpinBox
)
from PyQt6.QtCore import Qt, QTimer, QDateTime, pyqtSignal
from PyQt6.QtGui import QFont

import datetime

from store import Store, cents_to_str, format_real_rate, hours_between, utc_now, today_utc
from ui.styles import app_font, header_font, body_font, badge_style, STATUS_COLORS


class TimerCard(QFrame):
    """Big Start/Stop timer card. Emits signals when timer starts/stops."""
    start_requested = pyqtSignal(int, int)  # platform_id, project_id
    stop_requested = pyqtSignal()

    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self._session_id = None
        self._current_platform_id = None
        self._current_project_id = None
        self._elapsed = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_display)

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            TimerCard {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #25262b, stop:1 #1e1e24);
                border: 1px solid #4B5563;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        # Platform/project selector
        self.selector_layout = QHBoxLayout()
        self.platform_combo = self._make_combo()
        self.project_combo = self._make_combo()
        self.selector_layout.addWidget(QLabel("Platform:"))
        self.selector_layout.addWidget(self.platform_combo, 1)
        self.selector_layout.addWidget(QLabel("Project (opt):"))
        self.selector_layout.addWidget(self.project_combo, 1)
        layout.addLayout(self.selector_layout)

        # Timer display
        self.timer_label = QLabel("00:00:00")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_label.setFont(app_font(32, bold=True))
        layout.addWidget(self.timer_label, 1)

        # Controls
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.setObjectName("primary")
        self.start_btn.setStyleSheet(badge_style("#10B981"))
        self.start_btn.clicked.connect(self._on_start)
        btn_layout.addWidget(self.start_btn, 1)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(badge_style("#EF4444"))
        self.stop_btn.clicked.connect(self._on_stop)
        btn_layout.addWidget(self.stop_btn, 1)
        layout.addLayout(btn_layout)

        self.note_label = QLabel("")
        self.note_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.note_label.setStyleSheet("color: #9CA3AF; font-size: 11px;")
        layout.addWidget(self.note_label)

        self.auto_label = QLabel("")
        self.auto_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.auto_label.setStyleSheet("color: #60A5FA; font-size: 11px;")
        layout.addWidget(self.auto_label)

        self._refresh_selector()

    def _make_combo(self):
        combo = QComboBox()
        combo.setMinimumHeight(32)
        return combo

    def _refresh_selector(self):
        """Reload platforms and projects into the combos."""
        current_plat = self.platform_combo.currentText()
        current_proj = self.project_combo.currentText()

        self.platform_combo.blockSignals(True)
        self.platform_combo.clear()
        self.platform_combo.addItem("-- Select platform --", 0)
        for plat in self.store.get_all_platforms():
            self.platform_combo.addItem(plat['name'], plat['id'])
        self.platform_combo.blockSignals(False)

        self._on_platform_changed()
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        self.project_combo.addItem("-- No project --", None)
        if current_plat:
            idx = self.platform_combo.findText(current_plat)
            if idx >= 0:
                self.platform_combo.setCurrentIndex(idx)

    def _on_platform_changed(self):
        plat_id = self.platform_combo.currentData()
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        self.project_combo.addItem("-- No project --", None)
        if plat_id and plat_id != 0:
            for proj in self.store.get_projects_for_platform(plat_id):
                self.project_combo.addItem(proj['name'], proj['id'])
        self.project_combo.blockSignals(False)

    def _on_start(self):
        plat_id = self.platform_combo.currentData()
        proj_id = self.project_combo.currentData()
        if not plat_id or plat_id == 0:
            QMessageBox.warning(self, "No platform", "Select a platform first.")
            return

        existing = self.store.get_active_session_for_platform(plat_id)
        if existing:
            reply = QMessageBox.question(
                self, "Timer already running",
                f"You already have a timer running for this platform.\n\n"
                f"Started at: {existing['started_at']}\n\n"
                f"Start anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        self.start_requested.emit(plat_id, proj_id or 0)

    def _on_stop(self):
        self.stop_requested.emit()

    def begin_active(self, session_id, platform_id, project_id):
        self._session_id = session_id
        self._current_platform_id = platform_id
        self._current_project_id = project_id
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._elapsed = 0
        self._timer.start(1000)
        self.note_label.setText(f"Session #{session_id}")
        self._update_display()

    def show_running(self, session):
        """Show a session that is already running (started by auto mode, or recovered)."""
        self.begin_active(session['id'], session['platform_id'], session['project_id'])
        hrs = hours_between(session['started_at'], utc_now())
        self._elapsed = int(hrs * 3600) if hrs else 0
        self._update_display_no_increment()
        idx = self.platform_combo.findData(session['platform_id'])
        if idx >= 0:
            self.platform_combo.setCurrentIndex(idx)
        if session['source'] == 'auto':
            self.note_label.setText(f"Session #{session['id']} - started automatically")

    def set_auto_status(self, text):
        self.auto_label.setText(text)

    def end_active(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._timer.stop()
        self._elapsed = 0
        self.timer_label.setText("00:00:00")
        self._session_id = None
        self._current_platform_id = None
        self._current_project_id = None
        self.note_label.setText("")

    def _update_display(self):
        self._elapsed += 1
        hours = self._elapsed // 3600
        minutes = (self._elapsed % 3600) // 60
        secs = self._elapsed % 60
        self.timer_label.setText(f"{hours:02d}:{minutes:02d}:{secs:02d}")

    def set_display_from_session(self, started_at, ended_at=None):
        """When recovering an open session, show elapsed time from started_at."""
        if started_at:
            start = QDateTime.fromString(started_at, Qt.DateFormat.ISODate)
            if start.isValid():
                secs = start.secsTo(QDateTime.currentDateTime())
                if secs > 0:
                    self._elapsed = secs
                    self._update_display_no_increment()
        self._timer.start(1000)

    def _update_display_no_increment(self):
        hours = self._elapsed // 3600
        minutes = (self._elapsed % 3600) // 60
        secs = self._elapsed % 60
        self.timer_label.setText(f"{hours:02d}:{minutes:02d}:{secs:02d}")


class ItemCountDialog(QDialog):
    """Dialog shown on timer stop: ask for item count, with Skip."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About how many items?")
        self.last_count = None

        layout = QVBoxLayout(self)

        self.info_label = QLabel("How many items did you process in this session?")
        layout.addWidget(self.info_label)

        self.count_edit = self._make_spin(0)
        layout.addWidget(self.count_edit)

        btn_layout = QHBoxLayout()
        self.skip_btn = QPushButton("Skip")
        self.skip_btn.clicked.connect(self._on_skip)
        btn_layout.addWidget(self.skip_btn)
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setStyleSheet(badge_style("#3B82F6"))
        self.ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(self.ok_btn)
        layout.addLayout(btn_layout)

    def _make_spin(self, default):
        spin = QSpinBox()
        spin.setMinimum(0)
        spin.setMaximum(999999)
        spin.setValue(default)
        spin.setMinimumHeight(32)
        return spin

    def _on_ok(self):
        self.last_count = self.count_edit.value()
        self.accept()

    def _on_skip(self):
        self.last_count = None
        self.accept()

    @property
    def count(self):
        return self.last_count


class TodayScreen(QWidget):
    """The default screen Nick looks at while working."""

    refresh_requested = pyqtSignal()
    session_stopped = pyqtSignal(int)  # platform_id, when you press Stop

    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self._setup_ui()
        self._check_long_sessions()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QLabel("Today")
        header.setFont(header_font(18))
        layout.addWidget(header)

        # Timer card
        self.timer_card = TimerCard(self.store)
        self.timer_card.start_requested.connect(self._on_start)
        self.timer_card.stop_requested.connect(self._on_stop)
        layout.addWidget(self.timer_card)

        # Planned blocks section
        blocks_label = QLabel("Planned blocks")
        blocks_label.setStyleSheet("color: #9CA3AF; font-size: 13px; margin-top: 16px;")
        layout.addWidget(blocks_label)

        self.blocks_table = QTableWidget()
        self.blocks_table.setColumnCount(4)
        self.blocks_table.setHorizontalHeaderLabels(["Time", "Block", "Platform", "Project"])
        self.blocks_table.verticalHeader().setVisible(False)
        self.blocks_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.blocks_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.blocks_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.blocks_table.setMinimumHeight(120)
        layout.addWidget(self.blocks_table)

        # Setup tasks due today
        tasks_label = QLabel("Setup tasks due today or overdue")
        tasks_label.setStyleSheet("color: #9CA3AF; font-size: 13px; margin-top: 12px;")
        layout.addWidget(tasks_label)

        self.tasks_table = QTableWidget()
        self.tasks_table.setColumnCount(4)
        self.tasks_table.setHorizontalHeaderLabels(["Platform", "Task", "Human-only", "Due"])
        self.tasks_table.verticalHeader().setVisible(False)
        self.tasks_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tasks_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tasks_table.setMinimumHeight(120)
        layout.addWidget(self.tasks_table)

        # Money this week
        money_label = QLabel("Money this week")
        money_label.setStyleSheet("color: #9CA3AF; font-size: 13px; margin-top: 12px;")
        layout.addWidget(money_label)

        self.money_label = QLabel("Earnings this week: —")
        self.money_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.money_label)

        self._refresh_blocks()
        self._refresh_tasks()
        self._refresh_money()

    def _on_start(self, platform_id, project_id):
        session_id = self.store.start_session(platform_id, project_id or None)
        self.timer_card.begin_active(session_id, platform_id, project_id if project_id else None)

    def _on_stop(self):
        if self.timer_card._session_id is None:
            return
        session_id = self.timer_card._session_id
        platform_id = self.timer_card._current_platform_id
        dialog = ItemCountDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.store.stop_session(session_id, item_count=dialog.count)
            if self.timer_card._session_id == session_id:
                self.timer_card.end_active()
            if platform_id:
                self.session_stopped.emit(platform_id)
            self._refresh_money()
            self.refresh_requested.emit()

    def refresh_all(self):
        """Refresh all sections of the Today screen."""
        self._refresh_blocks()
        self._refresh_tasks()
        self._refresh_money()
        self.timer_card._refresh_selector()

    def _refresh_blocks(self):
        today = today_utc()
        blocks = self.store.get_blocks(
            start_date=f"{today}T00:00:00",
            end_date=f"{today}T23:59:59",
        )
        self.blocks_table.setRowCount(len(blocks))
        for i, block in enumerate(blocks):
            self.blocks_table.setItem(i, 0, QTableWidgetItem(
                f"{clock(block['starts_at'])}–{clock(block['ends_at'])}"
            ))
            self.blocks_table.setItem(i, 1, QTableWidgetItem(block['title'] or ""))
            plat_name = ""
            if block['platform_id']:
                plat = self.store.get_platform(block['platform_id'])
                if plat:
                    plat_name = plat['name']
            self.blocks_table.setItem(i, 2, QTableWidgetItem(plat_name))
            proj_name = ""
            if block['project_id']:
                proj = self.store.get_project(block['project_id'])
                if proj:
                    proj_name = proj['name']
            self.blocks_table.setItem(i, 3, QTableWidgetItem(proj_name))

    def _refresh_tasks(self):
        today = today_utc()
        tasks = self.store.get_due_setup_tasks(today)
        self.tasks_table.setRowCount(len(tasks))
        for i, task in enumerate(tasks):
            plat_name = ""
            if task['platform_id']:
                plat = self.store.get_platform(task['platform_id'])
                if plat:
                    plat_name = plat['name']
            self.tasks_table.setItem(i, 0, QTableWidgetItem(plat_name))
            self.tasks_table.setItem(i, 1, QTableWidgetItem(task['title']))
            human_str = "Yes" if task['is_human_only'] else "No"
            self.tasks_table.setItem(i, 2, QTableWidgetItem(human_str))
            self.tasks_table.setItem(i, 3, QTableWidgetItem(
                task['due_date'] or "no due date"
            ))

    def _refresh_money(self):
        today = today_utc()
        week_start = _week_start_iso(today)
        plats = self.store.get_all_platforms()
        total = 0
        for plat in plats:
            total += self.store.platform_earnings_cents(
                plat['id'],
                start_date=f"{week_start}T00:00:00",
                end_date=f"{today}T23:59:59",
            )
        self.money_label.setText(f"Earnings this week: {cents_to_str(total)}")

    def _check_long_sessions(self):
        """On launch, warn about sessions running > 12h."""
        open_sessions = self.store.recover_sessions()
        for sess in open_sessions:
            if sess['started_at']:
                hrs = hours_between(sess['started_at'], utc_now())
                if hrs and hrs > 12:
                    QMessageBox.warning(
                        self, "Long-running session",
                        f"Session #{sess['id']} has been running for {hrs:.1f} hours.\n\n"
                        f"It will appear as open in the timer. You can close it from the "
                        f"sessions list or click Stop to record it."
                    )


def _week_start_iso(date_str):
    """Return the Monday of the current ISO week as YYYY-MM-DD."""
    d = date_str.split("T")[0]
    dt = datetime.date.fromisoformat(d)
    monday = dt - datetime.timedelta(days=dt.weekday())
    return monday.isoformat()


def clock(iso):
    """'2026-10-14T09:00:00' -> '09:00'; anything unparseable comes back as it was."""
    try:
        return datetime.datetime.fromisoformat(iso).strftime("%H:%M")
    except (TypeError, ValueError):
        return iso or ""
