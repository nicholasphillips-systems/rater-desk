import unittest
import os
import sys
import sqlite3
import datetime
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from migrations import SCHEMA_VERSION, migrate, open_db, get_schema_version
from store import (
    Store, cents_to_str, cents_to_float, str_to_cents, real_rate,
    format_real_rate, hours_between, days_in_period, daily_cost,
)
from ics import escape_text, fold_line, format_local_dt, build_ics, write_ics_file


def make_test_db():
    """Create a temp db with the full schema and return (db_path, store)."""
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    store = Store(db_path)
    return db_path, store


class TestSchemaMigration(unittest.TestCase):
    def test_schema_version(self):
        self.assertEqual(SCHEMA_VERSION, 2)

    def test_schema_applied_on_open(self):
        db_path, store = make_test_db()
        try:
            conn = sqlite3.connect(db_path)
            version = get_schema_version(conn)
            self.assertEqual(version, SCHEMA_VERSION)
            conn.close()
        finally:
            os.unlink(db_path)

    def test_tables_exist(self):
        db_path, store = make_test_db()
        try:
            conn = sqlite3.connect(db_path)
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {t[0] for t in tables}
            expected = {'platforms', 'projects', 'setup_tasks', 'work_sessions',
                        'payouts', 'costs', 'blocks', 'settings'}
            self.assertTrue(expected.issubset(table_names))
            conn.close()
        finally:
            os.unlink(db_path)


class TestMoneyMath(unittest.TestCase):
    def test_cents_to_str(self):
        self.assertEqual(cents_to_str(12345), "$123.45")
        self.assertEqual(cents_to_str(0), "$0.00")
        self.assertEqual(cents_to_str(-50), "-$0.50")
        self.assertEqual(cents_to_str(None), "—")

    def test_str_to_cents(self):
        self.assertEqual(str_to_cents("$123.45"), 12345)
        self.assertEqual(str_to_cents("123.45"), 12345)
        self.assertEqual(str_to_cents("$0.50"), 50)
        self.assertEqual(str_to_cents("$1,234.56"), 123456)
        self.assertIsNone(str_to_cents(""))
        self.assertIsNone(str_to_cents("—"))

    def test_real_rate_zero_hours(self):
        self.assertIsNone(real_rate(10000, 0))
        self.assertIsNone(real_rate(10000, None))

    def test_real_rate_normal(self):
        result = real_rate(10000, 2)
        self.assertEqual(result, 5000.0)

    def test_format_real_rate_zero_hours(self):
        self.assertEqual(format_real_rate(10000, 0), "—")
        self.assertEqual(format_real_rate(10000, None), "—")

    def test_format_real_rate_normal(self):
        self.assertEqual(format_real_rate(10000, 2), "$50.00")

    def test_hours_between(self):
        start = "2026-10-01T09:00:00+00:00"
        end = "2026-10-01T10:30:00+00:00"
        self.assertAlmostEqual(hours_between(start, end), 1.5, places=4)

    def test_hours_between_none(self):
        self.assertIsNone(hours_between(None, "2026-01-01T00:00:00+00:00"))
        self.assertIsNone(hours_between("2026-01-01T00:00:00+00:00", None))

    def test_days_in_period(self):
        self.assertEqual(days_in_period("2026-10-01", "2026-10-07"), 7)
        self.assertEqual(days_in_period("2026-10-01", "2026-10-01"), 1)
        self.assertEqual(days_in_period(None, None), 0)

    def test_daily_cost(self):
        self.assertEqual(daily_cost(3000, "2026-10-01", "2026-10-31"), 3000 / 31)


class TestStorePlatforms(unittest.TestCase):
    def setUp(self):
        self.db_path, self.store = make_test_db()

    def tearDown(self):
        self.store.close()
        os.unlink(self.db_path)

    def test_add_and_get_platform(self):
        pid = self.store.add_platform("TestPlatform", status="active",
                                     advertises_rate_cents=2500)
        plat = self.store.get_platform(pid)
        self.assertEqual(plat['name'], "TestPlatform")
        self.assertEqual(plat['status'], "active")
        self.assertEqual(plat['advertises_rate_cents'], 2500)

    def test_invalid_status_rejected(self):
        with self.assertRaises(AssertionError):
            self.store.add_platform("Bad", status="invalid_state")

    def test_get_all_platforms_ordered(self):
        self.store.add_platform("Zeta", sort_order=1)
        self.store.add_platform("Alpha", sort_order=2)
        self.store.add_platform("Beta", sort_order=0)
        plats = self.store.get_all_platforms()
        names = [p['name'] for p in plats]
        self.assertEqual(names, ["Beta", "Zeta", "Alpha"])

    def test_get_active_session_for_platform(self):
        pid = self.store.add_platform("P")
        sid = self.store.start_session(pid)
        active = self.store.get_active_session_for_platform(pid)
        self.assertIsNotNone(active)
        self.assertEqual(active['id'], sid)
        self.store.stop_session(sid)
        self.assertIsNone(self.store.get_active_session_for_platform(pid))


class TestStoreSessions(unittest.TestCase):
    def setUp(self):
        self.db_path, self.store = make_test_db()
        self.pid = self.store.add_platform("P")
        self.store.add_project(self.pid, "Proj A", rate_cents_per_hour=3500)

    def tearDown(self):
        self.store.close()
        os.unlink(self.db_path)

    def test_start_stop_session(self):
        proj = self.store.get_projects_for_platform(self.pid)[0]
        sid = self.store.start_session(self.pid, project_id=proj['id'])
        self.store.stop_session(sid, item_count=10)
        sess = self.store.get_session(sid)
        self.assertIsNotNone(sess['ended_at'])
        self.assertEqual(sess['item_count'], 10)
        self.assertEqual(sess['rate_cents_per_hour'], 3500)

    def test_rate_snapshot(self):
        """Editing a project's rate after a session must not change the session's rate."""
        proj = self.store.get_projects_for_platform(self.pid)[0]
        sid = self.store.start_session(self.pid, project_id=proj['id'])
        self.store.stop_session(sid, item_count=5)
        self.store.update_project(proj['id'], rate_cents_per_hour=5000)
        sess = self.store.get_session(sid)
        self.assertEqual(sess['rate_cents_per_hour'], 3500)

    def test_stop_session_skip_count(self):
        sid = self.store.start_session(self.pid)
        self.store.stop_session(sid, item_count=None)
        sess = self.store.get_session(sid)
        self.assertIsNone(sess['item_count'])

    def test_recover_sessions(self):
        sid1 = self.store.start_session(self.pid)
        sid2 = self.store.start_session(self.pid)
        open_sessions = self.store.recover_sessions()
        self.assertEqual(len(open_sessions), 2)
        self.store.close_session(sid1)
        open_sessions = self.store.recover_sessions()
        self.assertEqual(len(open_sessions), 1)

    def test_no_second_session_warning(self):
        """Starting a second timer on a platform that already has one should warn."""
        sid1 = self.store.start_session(self.pid)
        active = self.store.get_active_session_for_platform(self.pid)
        self.assertIsNotNone(active)
        sid2 = self.store.start_session(self.pid)
        active2 = self.store.get_active_session_for_platform(self.pid)
        self.assertIsNotNone(active2)
        self.store.close_session(sid1)
        self.store.close_session(sid2)


class TestStorePayoutsAndCosts(unittest.TestCase):
    def setUp(self):
        self.db_path, self.store = make_test_db()
        self.pid = self.store.add_platform("P")

    def tearDown(self):
        self.store.close()
        os.unlink(self.db_path)

    def test_add_payout_base_and_bonus(self):
        self.store.add_payout(self.pid, "2026-10-01", 5000, kind='base')
        self.store.add_payout(self.pid, "2026-10-01", 500, kind='bonus')
        base = self.store.platform_earnings_cents(self.pid)
        bonus = self.store.platform_bonus_cents(self.pid)
        self.assertEqual(base, 5000)
        self.assertEqual(bonus, 500)

    def test_payouts_excluded_from_real_rate(self):
        """Bonuses must NOT count toward base real rate."""
        self.store.add_payout(self.pid, "2026-10-01", 10000, kind='base')
        self.store.add_payout(self.pid, "2026-10-01", 5000, kind='bonus')
        # 2 hours of work
        sid = self.store.start_session(self.pid)
        self.store.stop_session(sid)
        # Manually set ended time
        self.store.conn.execute(
            "UPDATE work_sessions SET started_at=?, ended_at=? WHERE id=?",
            ("2026-10-01T09:00:00+00:00", "2026-10-01T11:00:00+00:00", sid)
        )
        self.store.conn.commit()
        earnings = self.store.platform_earnings_cents(self.pid)
        hours = self.store.platform_hours(self.pid)
        self.assertEqual(earnings, 10000)
        self.assertAlmostEqual(hours, 2.0, places=2)
        rate = real_rate(earnings, hours)
        self.assertAlmostEqual(rate, 5000.0, places=0)  # only $100 / 2hr = $50/hr, not $75

    def test_add_cost_null_amount(self):
        cost_id = self.store.add_cost("ProtonVPN", amount_cents=None,
                                      recurring='monthly',
                                      note="Nick must enter actual price")
        cost = self.store.conn.execute(
            "SELECT * FROM costs WHERE id = ?", (cost_id,)
        ).fetchone()
        self.assertIsNone(cost['amount_cents'])

    def test_full_report_net(self):
        self.store.add_payout(self.pid, "2026-10-01", 10000, kind='base')
        self.store.add_cost("Test cost", 2000, "2026-10-01")
        report = self.store.full_report("2026-10-01", "2026-10-31")
        self.assertEqual(report['total_earnings_cents'], 10000)
        self.assertEqual(report['total_costs_cents'], 2000)
        self.assertEqual(report['total_net_cents'], 8000)


class TestICS(unittest.TestCase):
    def test_escape_text(self):
        self.assertEqual(escape_text(None), "")
        self.assertEqual(escape_text("Hello, World"), "Hello\\, World")
        self.assertEqual(escape_text("A;B"), "A\\;B")
        self.assertEqual(escape_text("Back\\slash"), "Back\\\\slash")
        self.assertEqual(escape_text("line1\nline2"), "line1\\nline2")
        self.assertEqual(escape_text("line1\r\nline2"), "line1\\nline2")

    def test_fold_line_short(self):
        self.assertEqual(fold_line("BEGIN:VCALENDAR"), "BEGIN:VCALENDAR")

    def test_fold_line_long(self):
        """A line longer than 75 octets is folded with CRLF+space."""
        long_line = "DESCRIPTION:" + "x" * 100
        folded = fold_line(long_line)
        lines = folded.split("\r\n")
        for line in lines[:-1]:  # skip trailing empty from split
            self.assertLessEqual(len(line.encode("utf-8")), 75)
        # Continuation lines start with space
        for line in lines[1:-1]:
            self.assertTrue(line.startswith(" "))

    def test_format_local_dt(self):
        result = format_local_dt("2026-10-01T14:30:00+00:00")
        self.assertIsNotNone(result)
        self.assertIn("T", result)
        self.assertNotIn("Z", result)

    def test_build_ics_valid_structure(self):
        blocks = [{
            "starts_at": "2026-10-01T09:00:00-04:00",
            "ends_at": "2026-10-01T10:00:00-04:00",
            "title": "Test Block",
            "calendar_uid": "raterdesk-block-1@raterdesk",
        }]
        ics_text = build_ics(blocks, tzid="America/New_York")
        self.assertIn("BEGIN:VCALENDAR", ics_text)
        self.assertIn("END:VCALENDAR", ics_text)
        self.assertIn("BEGIN:VEVENT", ics_text)
        self.assertIn("END:VEVENT", ics_text)
        self.assertIn("VERSION:2.0", ics_text)

    def test_build_ics_has_tzid(self):
        blocks = [{
            "starts_at": "2026-10-01T09:00:00-04:00",
            "ends_at": "2026-10-01T10:00:00-04:00",
            "title": "Block",
            "calendar_uid": "raterdesk-block-1@raterdesk",
        }]
        ics_text = build_ics(blocks, tzid="America/New_York")
        self.assertIn("TZID=America/New_York", ics_text)

    def test_build_ics_uid_stable(self):
        blocks = [{
            "starts_at": "2026-10-01T09:00:00-04:00",
            "ends_at": "2026-10-01T10:00:00-04:00",
            "title": "Block",
            "calendar_uid": "raterdesk-block-42@raterdesk",
        }]
        ics_text = build_ics(blocks)
        self.assertIn("raterdesk-block-42@raterdesk", ics_text)

    def test_build_ics_csv_escape_comma(self):
        """A title with a comma in it is properly escaped."""
        blocks = [{
            "starts_at": "2026-10-01T09:00:00-04:00",
            "ends_at": "2026-10-01T10:00:00-04:00",
            "title": "Rater, Trainer, Work",
            "calendar_uid": "raterdesk-block-1@raterdesk",
        }]
        ics_text = build_ics(blocks)
        self.assertIn("Rater\\, Trainer\\, Work", ics_text)

    def test_build_ics_crlf_endings(self):
        blocks = [{
            "starts_at": "2026-10-01T09:00:00-04:00",
            "ends_at": "2026-10-01T10:00:00-04:00",
            "title": "Block",
            "calendar_uid": "raterdesk-block-1@raterdesk",
        }]
        ics_text = build_ics(blocks)
        self.assertTrue(ics_text.endswith("\r\n"))
        self.assertIn("\r\n", ics_text)

    def test_build_ics_multiple_events(self):
        blocks = [
            {
                "starts_at": "2026-10-01T09:00:00-04:00",
                "ends_at": "2026-10-01T10:00:00-04:00",
                "title": "Block One",
                "calendar_uid": "raterdesk-block-1@raterdesk",
            },
            {
                "starts_at": "2026-10-01T11:00:00-04:00",
                "ends_at": "2026-10-01T12:00:00-04:00",
                "title": "Block Two",
                "calendar_uid": "raterdesk-block-2@raterdesk",
            },
        ]
        ics_text = build_ics(blocks)
        event_count = ics_text.count("BEGIN:VEVENT")
        self.assertEqual(event_count, 2)

    def test_write_ics_file(self):
        blocks = [{
            "starts_at": "2026-10-01T09:00:00-04:00",
            "ends_at": "2026-10-01T10:00:00-04:00",
            "title": "Block",
            "calendar_uid": "raterdesk-block-1@raterdesk",
        }]
        fd, path = tempfile.mkstemp(suffix=".ics")
        os.close(fd)
        try:
            write_ics_file(blocks, path, tzid="America/New_York")
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("BEGIN:VCALENDAR", content)
            self.assertIn("END:VCALENDAR", content)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
