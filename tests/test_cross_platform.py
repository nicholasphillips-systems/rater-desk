import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import autostart
import backup
import paths
import starter
import store
from store import Store


def fresh_db_path():
    """A path inside a new temp folder where no database exists yet."""
    return os.path.join(tempfile.mkdtemp(), "rater-desk.sqlite3")


class TestDataDir(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("RATER_DESK_DATA", None)

    def test_from_source_data_sits_beside_the_code(self):
        self.assertEqual(paths.data_dir(), Path(PROJECT_ROOT).resolve() / "data")

    def test_env_override_wins(self):
        os.environ["RATER_DESK_DATA"] = "/somewhere/else"
        self.assertEqual(paths.data_dir(), Path("/somewhere/else"))

    def test_packaged_windows_build_uses_appdata(self):
        os.environ["APPDATA"] = "/Users/pat/AppData/Roaming"
        with mock.patch.object(paths, "IS_FROZEN", True), \
                mock.patch.object(paths, "IS_WINDOWS", True):
            self.assertEqual(paths.data_dir(),
                             Path("/Users/pat/AppData/Roaming") / "Rater Desk")

    def test_packaged_linux_build_uses_xdg_data_home(self):
        os.environ["XDG_DATA_HOME"] = "/home/pat/.local/share"
        with mock.patch.object(paths, "IS_FROZEN", True), \
                mock.patch.object(paths, "IS_WINDOWS", False), \
                mock.patch.object(paths, "IS_MAC", False):
            self.assertEqual(paths.data_dir(),
                             Path("/home/pat/.local/share") / "rater-desk")

    def test_backup_copies_the_database_the_store_writes(self):
        self.assertEqual(str(backup.DB_PATH), store.DB_PATH)
        self.assertEqual(str(backup.BACKUP_DIR), store.BACKUP_DIR)


class TestBackup(unittest.TestCase):
    def test_backup_db_writes_a_copy(self):
        db_path = fresh_db_path()
        Store(db_path).close()
        backups = Path(db_path).parent / "backups"
        with mock.patch.object(backup, "DB_PATH", Path(db_path)), \
                mock.patch.object(backup, "BACKUP_DIR", backups):
            written = backup.backup_db()
        self.assertIsNotNone(written)
        self.assertEqual(os.path.getsize(written), os.path.getsize(db_path))


class TestStarterList(unittest.TestCase):
    def setUp(self):
        self.db_path = fresh_db_path()
        starter.seed(self.db_path)
        self.store = Store(self.db_path)
        self.addCleanup(self.store.close)

    def test_twelve_platforms_none_started(self):
        plats = self.store.get_all_platforms()
        self.assertEqual(len(plats), 12)
        self.assertEqual({p['status'] for p in plats}, {'not_started'})

    def test_every_platform_has_a_sign_in_page(self):
        for p in self.store.get_all_platforms():
            self.assertTrue((p['login_url'] or "").startswith("https://"), p['name'])

    def test_carries_no_account_progress(self):
        text = []
        for p in self.store.get_all_platforms():
            text += [p['notes'] or "", p['payout_notes'] or ""]
        for t in self.store.get_setup_tasks():
            text += [t['title'], t['detail'] or ""]
        blob = " ".join(text).lower()
        for personal in ("nick", "bot", "protonvpn", "0390", "stopped at",
                         "not created", "verified", "his "):
            self.assertNotIn(personal, blob)
        self.assertEqual(self.store.get_costs(), [])

    def test_running_twice_adds_nothing(self):
        before = (len(self.store.get_all_platforms()), len(self.store.get_setup_tasks()))
        starter.seed(self.db_path)
        after = (len(self.store.get_all_platforms()), len(self.store.get_setup_tasks()))
        self.assertEqual(before, after)


class TestFirstRun(unittest.TestCase):
    def test_new_database_gets_the_starter_list(self):
        from main import load_platform_list
        db_path = fresh_db_path()
        load_platform_list(db_path)
        with Store(db_path) as s:
            self.assertEqual(len(s.get_all_platforms()), 12)

    def test_empty_database_file_gets_the_starter_list(self):
        from main import load_platform_list
        db_path = fresh_db_path()
        Store(db_path).close()
        load_platform_list(db_path)
        with Store(db_path) as s:
            self.assertEqual(len(s.get_all_platforms()), 12)

    def test_existing_database_is_left_alone(self):
        from main import load_platform_list
        db_path = fresh_db_path()
        with Store(db_path) as s:
            s.add_platform(name="Only One")
        load_platform_list(db_path)
        with Store(db_path) as s:
            self.assertEqual([p['name'] for p in s.get_all_platforms()], ["Only One"])


class TestAutostart(unittest.TestCase):
    def test_from_source_launches_main_py_minimized(self):
        cmd = autostart.launch_command()
        self.assertEqual(cmd[0], sys.executable)
        self.assertEqual(cmd[1:], [str(Path(PROJECT_ROOT).resolve() / "main.py"),
                                   "--start-minimized"])

    def test_packaged_build_launches_the_exe_itself(self):
        with mock.patch.object(paths, "IS_FROZEN", True):
            self.assertEqual(autostart.launch_command(),
                             [sys.executable, "--start-minimized"])

    def test_linux_entry_written_once_then_removal_is_respected(self):
        folder = Path(tempfile.mkdtemp())
        entry = folder / "rater-desk.desktop"
        with mock.patch.object(autostart, "AUTOSTART_DIR", folder), \
                mock.patch.object(autostart, "AUTOSTART_FILE", entry), \
                mock.patch.object(paths, "IS_WINDOWS", False), \
                mock.patch.object(paths, "IS_LINUX", True):
            self.assertTrue(autostart.ensure(already_registered=False))
            self.assertIn("--start-minimized", entry.read_text())
            entry.unlink()
            self.assertFalse(autostart.ensure(already_registered=True))
            self.assertFalse(entry.exists())


if __name__ == "__main__":
    unittest.main()
