"""Plan screen: week grid, click-drag to add blocks, Export .ics, Open folder."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QFormLayout, QLineEdit, QComboBox, QTextEdit, QFileDialog, QMessageBox,
    QDateEdit
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QFont

import paths
from store import Store, utc_now
from ui.styles import header_font, body_font, badge_style
from ui.files import export_dir, export_path, open_folder
from ics import build_ics, write_ics_file


class BlockDialog(QDialog):
    """Dialog for adding/editing a work block on the week plan."""

    def __init__(self, parent=None, store=None, platforms=None, block=None):
        super().__init__(parent)
        self.store = store
        self.block = block
        self.setWindowTitle("Edit Block" if block else "Add Block")
        self.resize(400, 250)

        layout = QFormLayout(self)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("e.g. Babel Audio work, Mercury rating, etc.")
        layout.addRow("Title:", self.title_edit)

        self.start_edit = QDateEdit()
        self.start_edit.setCalendarPopup(True)
        self.start_edit.setDate(QDate.currentDate())
        layout.addRow("Start date:", self.start_edit)

        self.platform_combo = QComboBox()
        self.platform_combo.addItem("-- None --", None)
        if platforms:
            for p in platforms:
                self.platform_combo.addItem(p['name'], p['id'])
        layout.addRow("Platform:", self.platform_combo)

        self.project_combo = QComboBox()
        self.project_combo.addItem("-- None --", None)
        layout.addRow("Project:", self.project_combo)

        self.platform_combo.currentIndexChanged.connect(self._on_platform_changed)
        self._on_platform_changed()

        self.tzid_edit = QLineEdit()
        self.tzid_edit.setText("America/New_York")
        layout.addRow("Timezone:", self.tzid_edit)

        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        ok_btn = QPushButton("Save")
        ok_btn.setObjectName("primary")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        layout.addRow(btn_layout)

    def _on_platform_changed(self):
        plat_id = self.platform_combo.currentData()
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        self.project_combo.addItem("-- None --", None)
        if plat_id and self.store:
            for proj in self.store.get_projects_for_platform(plat_id):
                self.project_combo.addItem(proj['name'], proj['id'])
        self.project_combo.blockSignals(False)

    def get_block_data(self):
        return {
            'title': self.title_edit.text().strip(),
            'start_date': self.start_edit.date().toString("yyyy-MM-dd"),
            'platform_id': self.platform_combo.currentData(),
            'project_id': self.project_combo.currentData(),
            'tzid': self.tzid_edit.text().strip() or "America/New_York",
        }


class PlanScreen(QWidget):
    """Week grid with block management and ICS export."""

    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self._current_week_start = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel("Plan")
        header.setFont(header_font(18))
        layout.addWidget(header)

        # Week navigation
        nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton("← Prev week")
        self.prev_btn.clicked.connect(self._prev_week)
        nav_layout.addWidget(self.prev_btn)

        self.week_label = QLabel("")
        self.week_label.setStyleSheet("font-size: 13px; color: #9CA3AF;")
        nav_layout.addWidget(self.week_label, 1)

        self.next_btn = QPushButton("Next week →")
        self.next_btn.clicked.connect(self._next_week)
        nav_layout.addWidget(self.next_btn)

        today_btn = QPushButton("This week")
        today_btn.clicked.connect(self._this_week)
        nav_layout.addWidget(today_btn)

        layout.addLayout(nav_layout)

        # Week grid
        self.grid = WeekGrid(self.store)
        layout.addWidget(self.grid)

        # Export buttons
        export_layout = QHBoxLayout()
        self.export_ics_btn = QPushButton("Export .ics")
        self.export_ics_btn.setObjectName("primary")
        self.export_ics_btn.clicked.connect(self._export_ics)
        export_layout.addWidget(self.export_ics_btn)

        self.open_folder_btn = QPushButton("Open folder")
        self.open_folder_btn.clicked.connect(self._open_folder)
        export_layout.addWidget(self.open_folder_btn)

        self.copy_week_btn = QPushButton("Copy week (text)")
        self.copy_week_btn.setFlat(True)
        self.copy_week_btn.clicked.connect(self._copy_week_text)
        export_layout.addWidget(self.copy_week_btn)

        export_layout.addStretch()
        layout.addLayout(export_layout)

        self._this_week()

    def _this_week(self):
        from datetime import date, timedelta
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        self._current_week_start = monday
        self._refresh()

    def _prev_week(self):
        from datetime import timedelta
        self._current_week_start = self._current_week_start - timedelta(days=7)
        self._refresh()

    def _next_week(self):
        from datetime import timedelta
        self._current_week_start = self._current_week_start + timedelta(days=7)
        self._refresh()

    def _refresh(self):
        from datetime import timedelta
        start = self._current_week_start
        end = start + timedelta(days=6)
        self.week_label.setText(f"{start.isoformat()} — {end.isoformat()}")
        self.grid.show_week(start, end)

    def _export_ics(self):
        from datetime import timedelta
        tzid = self.store.get_setting("tzid", "America/New_York")
        start = self._current_week_start.isoformat()
        end = (self._current_week_start + timedelta(days=6)).isoformat()

        blocks = self.store.get_blocks(
            start_date=f"{start}T00:00:00",
            end_date=f"{end}T23:59:59",
        )
        if not blocks:
            QMessageBox.information(self, "No blocks",
                                    "No blocks to export for this week.")
            return

        default_name = f"rater-desk-{start}-to-{end}.ics"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save .ics file",
            export_path(default_name),
            "ICS files (*.ics)",
        )
        if not file_path:
            return

        block_dicts = []
        for b in blocks:
            block_dicts.append({
                'starts_at': b['starts_at'],
                'ends_at': b['ends_at'],
                'title': b['title'],
                'calendar_uid': b['calendar_uid'],
                'tzid': tzid,
            })

        write_ics_file(block_dicts, file_path, tzid=tzid)
        self.store.set_setting("ics_path", file_path)
        if paths.IS_LINUX:
            how_to = ("Import this file into Google Calendar via Kontact "
                      "(File -> Import -> Import ICS).")
        else:
            how_to = "Import this file into your calendar app."
        QMessageBox.information(self, "Export complete",
                                f"ICS file saved:\n{file_path}\n\n{how_to}")

    def _open_folder(self):
        open_folder(export_dir())

    def _copy_week_text(self):
        from datetime import timedelta
        start = self._current_week_start
        end = start + timedelta(days=6)
        blocks = self.store.get_blocks(
            start_date=f"{start.isoformat()}T00:00:00",
            end_date=f"{end.isoformat()}T23:59:59",
        )
        lines = []
        for b in blocks:
            plat_name = ""
            if b['platform_id']:
                plat = self.store.get_platform(b['platform_id'])
                if plat:
                    plat_name = plat['name']
            proj_name = ""
            if b['project_id']:
                proj = self.store.get_project(b['project_id'])
                if proj:
                    proj_name = proj['name']
            lines.append(f"{b['starts_at']} — {b['ends_at']}: {b['title']} ({plat_name} / {proj_name})")

        from PyQt6.QtGui import QClipboard
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText("\n".join(lines))
        QMessageBox.information(self, "Copied", "Week plan copied to clipboard.")


import os


class WeekGrid(QWidget):
    """A 7-column week grid showing blocks per day."""

    DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self._start_date = None
        self._end_date = None
        self._grid_layout = None
        self._setup_ui()

    def _setup_ui(self):
        from PyQt6.QtWidgets import QGridLayout
        layout = QGridLayout(self)
        layout.setSpacing(2)

        for col, day_name in enumerate(self.DAYS):
            lbl = QLabel(day_name)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #9CA3AF; font-size: 12px; padding: 4px;")
            layout.addWidget(lbl, 0, col)

        self._day_widgets = []
        for col in range(7):
            day_widget = DayColumn(self.store, col)
            layout.addWidget(day_widget, 1, col)
            self._day_widgets.append(day_widget)

        self.setMinimumHeight(200)

    def show_week(self, start_date, end_date):
        self._start_date = start_date
        self._end_date = end_date
        for i, day_widget in enumerate(self._day_widgets):
            from datetime import timedelta
            day = start_date + timedelta(days=i)
            day_widget.show_day(day)

    def get_blocks_in_range(self, start_date, end_date):
        start_str = start_date.isoformat()
        end_str = end_date.isoformat()
        return self.store.get_blocks(
            start_date=f"{start_str}T00:00:00",
            end_date=f"{end_str}T23:59:59",
        )


class DayColumn(QWidget):
    """A single day column in the week grid."""

    def __init__(self, store: Store, day_offset: int):
        super().__init__()
        self.store = store
        self._day_offset = day_offset
        self._date = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        self.date_label = QLabel("")
        self.date_label.setStyleSheet("font-size: 10px; color: #6B7280;")
        layout.addWidget(self.date_label)

        self.block_layout = QVBoxLayout()
        self.block_layout.setSpacing(2)
        layout.addLayout(self.block_layout)

        self.add_btn = QPushButton("+ Block")
        self.add_btn.setFlat(True)
        self.add_btn.setStyleSheet("font-size: 10px; color: #60A5FA;")
        self.add_btn.clicked.connect(self._add_block)
        layout.addWidget(self.add_btn)

    def show_day(self, date_obj):
        self._date = date_obj
        self.date_label.setText(date_obj.strftime("%b %d"))
        self._refresh_blocks()

    def _refresh_blocks(self):
        from PyQt6.QtWidgets import QSpacerItem, QSizePolicy
        for i in reversed(range(self.block_layout.count())):
            widget = self.block_layout.itemAt(i).widget()
            if widget and not isinstance(widget, QPushButton):
                widget.setParent(None)

        if not self._date:
            return

        from datetime import datetime as dt_module
        day_str = self._date.isoformat()
        blocks = self.store.get_blocks(
            start_date=f"{day_str}T00:00:00",
            end_date=f"{day_str}T23:59:59",
        )

        for block in blocks:
            block_widget = BlockWidget(self.store, block)
            self.block_layout.addWidget(block_widget)

        spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.block_layout.addItem(spacer)

    def _add_block(self):
        platforms = self.store.get_all_platforms()
        dialog = BlockDialog(parent=self, store=self.store, platforms=platforms)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_block_data()
            start_dt = f"{data['start_date']}T09:00:00"
            end_dt = f"{data['start_date']}T10:00:00"
            self.store.add_block(
                starts_at=start_dt, ends_at=end_dt,
                title=data['title'],
                platform_id=data['platform_id'],
                project_id=data['project_id'],
            )
            self._refresh_blocks()


class BlockWidget(QWidget):
    """A visual block in the week grid."""

    def __init__(self, store: Store, block):
        super().__init__()
        self.store = store
        self.block = block

        self.setStyleSheet("""
            BlockWidget {
                background-color: #3B82F620;
                border: 1px solid #3B82F6;
                border-radius: 4px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)

        title_label = QLabel(block['title'])
        title_label.setStyleSheet("font-size: 11px; color: #e2e8f0;")
        layout.addWidget(title_label)

        time_label = QLabel(_short_time(block['starts_at']))
        time_label.setStyleSheet("font-size: 10px; color: #9CA3AF; margin-left: auto;")
        layout.addWidget(time_label)

    def get_platform_id(self):
        return self.block['platform_id']


from PyQt6.QtWidgets import QHBoxLayout


def _short_time(iso_str):
    if not iso_str:
        return ""
    try:
        return iso_str.split("T")[1][:5]
    except Exception:
        return ""
