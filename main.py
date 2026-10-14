"""Rater Desk — main entry point.

QApplication lifecycle, QMainWindow with sidebar navbar (Today / Platforms / Plan / Money /
Reports / Auto), system tray icon, close-to-tray, start at login, crash recovery on
startup, reminders for long sessions, and auto mode (timer from the focused window,
updates from email). Runs on Linux and Windows; the OS-specific parts live in paths.py
and autostart.py.
"""

import datetime
import functools
import os
import sys
import subprocess
import traceback

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget, QWidget, QHBoxLayout,
    QVBoxLayout, QPushButton, QLabel, QSystemTrayIcon, QMenu, QMessageBox,
    QStyle, QFileDialog,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QAction

import autostart
import paths
from store import Store, DB_PATH, DATA_DIR, today_utc, hours_between
from backup import backup_db, start_backup_thread
from ui.styles import APP_STYLE, body_font, header_font
from ui.today import TodayScreen
from ui.platforms import PlatformsScreen
from ui.plan import PlanScreen
from ui.money import MoneyScreen
from ui.reports import ReportsScreen
from ui.auto import AutoScreen
from activity import ActivitySource
from autotimer import AutoTimer
from mailwatch import MailWatcher


APP_NAME = paths.APP_NAME
# Windows wants an .ico for the taskbar and tray; everywhere else the SVG is used.
ICON_PATH = paths.app_dir() / "assets" / ("icon.ico" if paths.IS_WINDOWS else "icon.svg")

LONG_SESSION_MINUTES = 90
AUTO_TICK_MS = 15 * 1000
MAIL_CHECK_MS = 10 * 60 * 1000


def guarded(method):
    """For Qt slots: an exception escaping a slot aborts the whole app, so auto mode
    logs its errors and carries on instead."""
    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except Exception:
            traceback.print_exc()
    return wrapper


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


class MainWindow(QMainWindow):
    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(self._app_icon())
        self.resize(1100, 650)

        self._setup_sidebar()
        self._setup_tray()
        self._setup_autostart()
        self._setup_auto()
        self._check_crash_recovery()
        self._setup_long_session_timer()

    def _setup_sidebar(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Sidebar
        sidebar = QWidget()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet("""
            QWidget { background-color: #1F2937; }
            QPushButton {
                text-align: left;
                padding: 12px 16px;
                border: none;
                color: #9CA3AF;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #374151; color: #e2e8f0; }
            QPushButton#active_btn {
                background-color: #3B82F6;
                color: #fff;
            }
        """)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 50, 0, 0)
        sidebar_layout.setSpacing(0)

        title_label = QLabel("RATER DESK")
        title_label.setStyleSheet("color: #60A5FA; padding: 16px; font-size: 11px; font-weight: bold;")
        sidebar_layout.addWidget(title_label)

        self.nav_buttons = {}
        self.tab_names = ["today", "platforms", "plan", "money", "reports", "auto"]
        self.tab_labels = {
            "today": "Today", "platforms": "Platforms",
            "plan": "Plan", "money": "Money", "reports": "Reports", "auto": "Auto",
        }

        for name in self.tab_names:
            btn = QPushButton(self.tab_labels[name])
            btn.setFixedHeight(40)
            btn.setObjectName(name)
            btn.clicked.connect(self._on_nav_clicked)
            self.nav_buttons[name] = btn
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()

        # Divider
        divider = QLabel()
        divider.setFixedWidth(1)
        divider.setStyleSheet("background-color: #374151;")

        # Stack
        self.stack = QStackedWidget()

        main_layout.addWidget(sidebar)
        main_layout.addWidget(divider)
        main_layout.addWidget(self.stack, 1)

        # Create screens
        self.today_screen = TodayScreen(self.store)
        self.platforms_screen = PlatformsScreen(self.store)
        self.plan_screen = PlanScreen(self.store)
        self.money_screen = MoneyScreen(self.store)
        self.reports_screen = ReportsScreen(self.store)
        self.auto_screen = AutoScreen(self.store)

        self.stack.addWidget(self.today_screen)
        self.stack.addWidget(self.platforms_screen)
        self.stack.addWidget(self.plan_screen)
        self.stack.addWidget(self.money_screen)
        self.stack.addWidget(self.reports_screen)
        self.stack.addWidget(self.auto_screen)

        # Connect signals
        self.today_screen.refresh_requested.connect(self._on_today_refresh)
        self.money_screen_period = "week"

        self._switch_tab("today")

    def _on_nav_clicked(self):
        btn = self.sender()
        if isinstance(btn, QPushButton):
            self._switch_tab(btn.objectName())

    def _switch_tab(self, name):
        index_map = {
            'today': 0, 'platforms': 1, 'plan': 2,
            'money': 3, 'reports': 4, 'auto': 5,
        }
        idx = index_map.get(name, 0)
        self.stack.setCurrentIndex(idx)

        # Update active button
        for key, btn in self.nav_buttons.items():
            btn.setProperty("active", False)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            if key == name:
                btn.setProperty("active", True)
                btn.style().unpolish(btn)
                btn.style().polish(btn)

        # Refresh the screen if needed
        if name == "money":
            self.money_screen._refresh()
        elif name == "reports":
            self.reports_screen._set_period(self.money_screen_period)
        elif name == "platforms":
            self.platforms_screen._refresh_platforms()
        elif name == "today":
            self.today_screen.refresh_all()
        elif name == "auto":
            self.auto_screen.refresh()

    def _setup_tray(self):
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(self._app_icon())
        self.tray.setToolTip(APP_NAME)

        # Parented to the window: without an owner Python frees the actions as soon
        # as this method returns and the tray menu comes up empty.
        tray_menu = QMenu(self)

        show_action = QAction("Show", self)
        show_action.triggered.connect(self._show_window)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit)
        tray_menu.addAction(quit_action)

        self.tray.setContextMenu(tray_menu)
        if not paths.IS_LINUX:
            # Clicking the tray icon is how a hidden window comes back on Windows.
            self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self._show_window()

    def _setup_autostart(self):
        try:
            registered = self.store.get_setting("autostart_registered") == "1"
            if autostart.ensure(registered) and not registered:
                self.store.set_setting("autostart_registered", "1")
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Auto mode

    def _setup_auto(self):
        self.autotimer = AutoTimer(self.store, on_change=self._on_auto_change)
        # Auto sessions left open by a crash end at the last input seen, before
        # the recovery dialog asks about manual ones.
        self.autotimer.recover()

        self.activity = ActivitySource(self)
        self.activity.focus_changed.connect(self._on_focus)
        self.activity.input_seen.connect(self._on_input)
        self.activity.lock_changed.connect(self._on_lock)
        self._auto_available = self.activity.start()
        self.autotimer.enabled = (self._auto_available
                                  and self.store.get_setting("auto_timer", "1") == "1")
        self.auto_screen.auto_timer_toggled.connect(self._on_auto_toggled)
        self.today_screen.session_stopped.connect(self._on_stopped_by_hand)

        self._auto_tick = QTimer(self)
        self._auto_tick.timeout.connect(self._tick_auto)
        self._auto_tick.start(AUTO_TICK_MS)
        self._tick_auto()

        self.mail = MailWatcher(self.store, self)
        self.mail.finished.connect(self._on_mail_checked)
        self.auto_screen.check_mail_requested.connect(self._check_mail)
        self._mail_timer = QTimer(self)
        self._mail_timer.timeout.connect(self._check_mail)
        self._mail_timer.start(MAIL_CHECK_MS)
        QTimer.singleShot(20 * 1000, self._check_mail)

    @guarded
    def _on_focus(self, title, app_class, when):
        # Tracked even while off, so switching it on with a platform open starts it.
        self.autotimer.focus(title, app_class, when)
        self._show_auto_status()

    @guarded
    def _on_input(self, when):
        self.autotimer.activity(when)

    @guarded
    def _on_lock(self, locked, when):
        self.autotimer.lock(locked, when)
        self._show_auto_status()

    @guarded
    def _tick_auto(self):
        if self.autotimer.enabled:
            self.autotimer.tick(utc_now())
        self._show_auto_status()

    def _show_auto_status(self):
        if not self._auto_available:
            text = f"Auto timer unavailable: {self.activity.why_unavailable}"
        elif not self.autotimer.enabled:
            text = "Auto timer off"
        else:
            text = f"Auto: {self.autotimer.status}"
        self.auto_screen.set_timer_status(text)
        self.today_screen.timer_card.set_auto_status(text)

    @guarded
    def _on_auto_toggled(self, on):
        if self._auto_available:
            self.autotimer.set_enabled(on, utc_now())
        self._show_auto_status()

    @guarded
    def _on_stopped_by_hand(self, platform_id):
        self.autotimer.stopped_by_hand(platform_id)
        self._show_auto_status()

    def _on_auto_change(self, event, session_id, platform_id, reason):
        plat = self.store.get_platform(platform_id)
        name = plat['name'] if plat else "Platform"
        card = self.today_screen.timer_card
        if event == "started":
            session = self.store.get_session(session_id)
            if session and card._session_id is None:
                card.show_running(session)
            self._notify(f"{name} timer started", "Started automatically. Stops when you leave.")
        else:
            if card._session_id == session_id:
                card.end_active()
            session = self.store.get_session(session_id)
            if session and session['ended_at']:
                mins = round(hours_between(session['started_at'], session['ended_at']) * 60)
                self._notify(f"{name} timer stopped", f"{mins // 60}h {mins % 60:02d}m - {reason}")
            self.today_screen.refresh_all()
            self._on_today_refresh()

    @guarded
    def _check_mail(self):
        if self.mail.check_now():
            self.auto_screen.set_mail_busy(True)

    @guarded
    def _on_mail_checked(self, lines, errors):
        self.auto_screen.set_mail_busy(False)
        self.auto_screen.refresh()
        if lines:
            more = f" (+{len(lines) - 1} more on the Auto screen)" if len(lines) > 1 else ""
            self._notify("Rater Desk: news from your email", lines[0] + more)
            self.platforms_screen._refresh_platforms()
            self.today_screen.refresh_all()
            self._on_today_refresh()

    def _notify(self, title, text):
        if self.tray.isVisible():
            self.tray.showMessage(title, text, QSystemTrayIcon.MessageIcon.Information, 5000)
        elif paths.IS_LINUX:
            try:
                subprocess.Popen(["notify-send", "-a", APP_NAME, title, text])
            except OSError:
                pass

    def _check_crash_recovery(self):
        """On startup, check for work sessions that were left running and offer to recover them."""
        open_sessions = self.store.recover_sessions()
        if open_sessions:
            msg = QMessageBox(self)
            msg.setWindowTitle("Recover work session?")
            msg.setText(f"There are {len(open_sessions)} work session(s) that appear to be still running from a previous session.\n\nWould you like to continue them?")
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg.setInformativeText("Choosing 'No' will stop the timer (ended_at = now).")
            result = msg.exec()

            if result == QMessageBox.StandardButton.No:
                for s in open_sessions:
                    self.store.stop_session(s['id'])
            else:
                # Re-show today screen to pick up the recovered session
                self.today_screen.refresh_all()
                self.today_screen.timer_card.show_running(open_sessions[0])

    def _setup_long_session_timer(self):
        self._session_check_timer = QTimer()
        self._session_check_timer.timeout.connect(self._check_long_session)
        self._session_check_timer.start(60000)  # check every minute
        self._long_warned = False

    def _check_long_session(self):
        current = self.store.recover_sessions()
        if current:
            session = current[0]
            duration = hours_between(session['started_at'], utc_now().isoformat()) or 0
            if duration * 60 >= LONG_SESSION_MINUTES and not self._long_warned:
                self._notify_long_session(session, duration)
                self._long_warned = True
        else:
            self._long_warned = False

    def _notify_long_session(self, session, hours):
        proj_name = ""
        if session['project_id']:
            proj = self.store.get_project(session['project_id'])
            if proj:
                proj_name = proj['name']
        plat_name = ""
        if session['platform_id']:
            plat = self.store.get_platform(session['platform_id'])
            if plat:
                plat_name = plat['name']

        self.tray.showMessage(
            APP_NAME,
            f"Long session: {hours:.1f}h on {plat_name} / {proj_name}. Consider a break!",
            QSystemTrayIcon.MessageIcon.Information,
            5000,
        )

        if not paths.IS_LINUX:
            return
        try:
            subprocess.Popen(
                ["notify-send", "Long session", f"{hours:.1f}h on {plat_name} / {proj_name}"],
                env={
                    "XDG_RUNTIME_DIR": f"/run/user/{os.getuid()}",
                    "DISPLAY": os.environ.get("DISPLAY", ":0"),
                },
            )
        except Exception:
            pass

    def _on_today_refresh(self):
        self.money_screen._refresh()
        self.reports_screen._set_period(self.money_screen_period)

    def _show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()
        if paths.IS_LINUX:
            # notify-send covers reminders while the icon is hidden. Elsewhere the
            # tray icon is what delivers them, so it stays up.
            self.tray.hide()

    def _quit(self):
        try:
            self.autotimer.shutdown(utc_now())
            self.activity.stop()
        except Exception:
            traceback.print_exc()
        self.store.close()
        QApplication.quit()

    def _app_icon(self):
        if ICON_PATH.exists():
            return QIcon(str(ICON_PATH))
        return self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        # The icon is the only way back to a hidden window.
        self.tray.show()
        self.tray.showMessage(
            APP_NAME,
            "Still running in tray. Click 'Show' from tray icon.",
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )


def load_platform_list(db_path, reseed=False):
    """Fill a database that has no platforms with the starter list; --seed re-runs the seed.

    Checks for platforms rather than for the file: something that opens the
    database before first launch leaves an empty file behind, and the app then
    opened with no platforms at all.
    """
    if reseed:
        try:
            from seed import seed  # the original list; left out of packaged builds
        except ImportError:
            from starter import seed
        seed(db_path)
    elif not _has_platforms(db_path):
        from starter import seed
        seed(db_path)


def _has_platforms(db_path):
    if not os.path.exists(db_path):
        return False
    with Store(db_path) as s:
        return bool(s.get_all_platforms())


def main():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    if not paths.IS_LINUX:
        # The stylesheet assumes Qt's Fusion style on a dark palette, which is what
        # Linux gives it. Ask for the same so a light-mode desktop stays readable.
        app.setStyle("Fusion")
        app.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    app.setStyleSheet(APP_STYLE)

    # DATA_DIR is created by Store's open_db
    load_platform_list(DB_PATH, reseed="--seed" in sys.argv)
    store = Store(DB_PATH)

    window = MainWindow(store)

    # Start daily backup thread
    start_backup_thread()

    if "--start-minimized" not in sys.argv:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
