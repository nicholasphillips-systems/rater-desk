"""Open every screen the way a click would, offscreen.

An exception in a Qt slot aborts the whole app, and the store-call check can't
see a wrong Qt call (the platform View button once crashed on QFormLayout.rows()).
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["RATER_DESK_NO_KWIN_SCRIPT"] = "1"
os.environ["RATER_DESK_DATA"] = tempfile.mkdtemp(prefix="rater-desk-test-")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from PyQt6.QtWidgets import QApplication

import main
import starter
from store import Store

app = QApplication.instance() or QApplication([])


class TestScreens(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        os.unlink(self.db_path)
        starter.seed(self.db_path)
        self.store = Store(self.db_path)
        # Never touch the real start-at-login entry from a test.
        with mock.patch("autostart.ensure", return_value=False):
            self.window = main.MainWindow(self.store)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        app.processEvents()
        self.store.close()
        os.unlink(self.db_path)

    def test_every_sidebar_tab_opens(self):
        for name in self.window.tab_names:
            with self.subTest(tab=name):
                self.window._switch_tab(name)
                app.processEvents()

    def test_view_every_platform(self):
        detail = self.window.platforms_screen.detail
        for plat in self.store.get_all_platforms():
            with self.subTest(platform=plat['name']):
                detail.show_platform(plat['id'])
                for tab in range(detail.count()):
                    detail.setCurrentIndex(tab)
                    app.processEvents()

    def test_overview_shows_the_platform(self):
        plat = self.store.get_all_platforms()[0]
        self.window.platforms_screen.detail.show_platform(plat['id'])
        form = self.window.platforms_screen.detail.overview_widget().layout()
        shown = [form.itemAt(r, form.ItemRole.FieldRole).widget().text()
                 for r in range(form.rowCount())]
        self.assertEqual(shown[0], plat['name'])


class TestTodayBlocks(unittest.TestCase):
    def test_block_times_show_as_hours(self):
        from ui.today import clock
        self.assertEqual(clock("2026-10-14T09:00:00"), "09:00")
        self.assertEqual(clock("2026-10-14T17:30:00+00:00"), "17:30")
        self.assertEqual(clock("not a time"), "not a time")
        self.assertEqual(clock(None), "")


if __name__ == "__main__":
    unittest.main()
