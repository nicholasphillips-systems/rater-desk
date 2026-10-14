"""Auto mode: window matching, the auto timer's rules, and email detection.

The email cases are real subjects and opening lines from the platforms' own mail
(October 2026, personal details changed), so a wording change on their side shows up here first.
"""

import datetime
import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import catalog
import maildetect
from autotimer import AutoTimer
from store import Store
from starter import seed as starter_seed

CHROMIUM = "chromium-browser"
T0 = datetime.datetime(2026, 10, 14, 15, 0, tzinfo=datetime.timezone.utc)


def at(seconds):
    return T0 + datetime.timedelta(seconds=seconds)


def make_store():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    os.unlink(db_path)
    starter_seed(db_path)
    return Store(db_path)


class TestWindowMatching(unittest.TestCase):
    def setUp(self):
        self.store = make_store()
        self.plats = self.store.get_all_platforms()

    def name(self, title, cls=CHROMIUM):
        p = catalog.match_window(title, cls, self.plats)
        return p['name'] if p else None

    def test_browser_tabs_match(self):
        self.assertEqual(self.name("Outlier - Chromium"), "Outlier")
        self.assertEqual(self.name("AI Community Platform - Chromium"), "TELUS Digital")
        self.assertEqual(self.name("Dashboard | Babel Audio - Chromium"), "Babel Audio")
        self.assertEqual(self.name("Mercor — LibreWolf", "librewolf"), "Mercor")

    def test_only_browsers_count(self):
        self.assertIsNone(self.name("outlier detection.ipynb - Visual Studio Code", "code"))
        self.assertIsNone(self.name("Claude Code — Konsole", "org.kde.konsole"))

    def test_generic_words_do_not_fire(self):
        self.assertIsNone(self.name("babel.config.js - GitHub - Chromium"))
        self.assertIsNone(self.name("Sigma notation - Wikipedia - Chromium"))

    def test_override_words(self):
        pid = self.store.get_platform_by_name("Outlier")['id']
        self.store.update_platform(pid, match_words="Playground")
        plats = self.store.get_all_platforms()
        self.assertEqual(catalog.match_window("Playground - Chromium", CHROMIUM, plats)['name'], "Outlier")
        self.assertIsNone(catalog.match_window("Outlier - Chromium", CHROMIUM, plats))


class TestAutoTimer(unittest.TestCase):
    def setUp(self):
        self.store = make_store()
        self.events = []
        self.t = AutoTimer(self.store, on_change=lambda *a: self.events.append(a))
        self.outlier = self.store.get_platform_by_name("Outlier")['id']
        self.mercor = self.store.get_platform_by_name("Mercor")['id']

    def open_sessions(self):
        return self.store.recover_sessions()

    def work(self, title, start, end, step=20):
        """Focus a window at `start`, then keep moving the mouse until `end`."""
        self.t.focus(title, CHROMIUM, at(start))
        s = start
        while s < end:
            s = min(s + step, end)
            self.t.activity(at(s))
            self.t.tick(at(s))

    def test_starts_after_settle_backdated(self):
        self.work("Outlier - Chromium", 0, 30)
        self.assertEqual(self.open_sessions(), [])
        self.work("Outlier - Chromium", 30, 60)
        sess = self.open_sessions()
        self.assertEqual(len(sess), 1)
        self.assertEqual(sess[0]['platform_id'], self.outlier)
        self.assertEqual(sess[0]['source'], 'auto')
        # Started when the tab was opened, not when the 45 s ran out
        self.assertEqual(sess[0]['started_at'], at(0).isoformat())

    def test_short_look_away_keeps_session(self):
        self.work("Outlier - Chromium", 0, 600)
        self.work("Claude Code — Konsole", 600, 780)       # 3 min away
        self.work("Outlier - Chromium", 780, 1200)
        sess = self.store.get_sessions()
        self.assertEqual(len(sess), 1)
        self.assertIsNone(sess[0]['ended_at'])

    def test_leaving_stops_at_time_left(self):
        self.work("Outlier - Chromium", 0, 1200)
        self.t.focus("Claude Code — Konsole", "org.kde.konsole", at(1200))
        for s in range(1200, 1600, 20):
            self.t.activity(at(s))
            self.t.tick(at(s))
        sess = self.store.get_sessions()[0]
        self.assertEqual(sess['ended_at'], at(1200).isoformat())

    def test_idle_stops_at_last_input_and_restarts_fresh(self):
        self.work("Outlier - Chromium", 0, 1200)
        self.t.tick(at(1200 + 16 * 60))                    # nobody touched anything
        first = self.store.get_sessions()[0]
        self.assertEqual(first['ended_at'], at(1200).isoformat())
        # Back at the desk, same tab still open
        self.work("Outlier - Chromium", 3000, 3060)
        newest = self.store.get_sessions()[0]
        self.assertNotEqual(newest['id'], first['id'])
        self.assertEqual(newest['started_at'], at(3000).isoformat())

    def test_lock_stops(self):
        self.work("Outlier - Chromium", 0, 600)
        self.t.lock(True, at(610))
        self.assertEqual(self.open_sessions(), [])

    def test_switching_platforms(self):
        self.work("Outlier - Chromium", 0, 600)
        self.work("Mercor - Chromium", 600, 700)
        sessions = self.store.get_sessions()
        self.assertEqual([s['platform_id'] for s in sessions], [self.mercor, self.outlier])
        self.assertEqual(sessions[1]['ended_at'], at(600).isoformat())
        self.assertEqual(sessions[0]['started_at'], at(600).isoformat())

    def test_manual_timer_wins(self):
        self.store.start_session(self.mercor)
        self.work("Outlier - Chromium", 0, 300)
        self.assertEqual(len(self.open_sessions()), 1)
        self.assertEqual(self.open_sessions()[0]['source'], 'manual')

    def test_stopped_by_hand_stays_stopped_until_you_return(self):
        self.work("Outlier - Chromium", 0, 600)
        sid = self.open_sessions()[0]['id']
        self.store.stop_session(sid, ended_at=at(600).isoformat())
        self.t.stopped_by_hand(self.outlier)
        self.work("Outlier - Chromium", 600, 900)
        self.assertEqual(self.open_sessions(), [])
        self.work("Claude Code — Konsole", 900, 960)
        self.work("Outlier - Chromium", 960, 1020)
        self.assertEqual(len(self.open_sessions()), 1)

    def test_blip_is_discarded(self):
        self.work("Outlier - Chromium", 0, 50)              # starts at 45 s
        self.t.lock(True, at(60))
        self.assertEqual(self.store.get_sessions(), [])

    def test_recover_ends_at_last_saved_input(self):
        self.work("Outlier - Chromium", 0, 1800)
        saved = self.store.get_setting("auto_last_activity")
        fresh = AutoTimer(self.store)
        fresh.recover()
        sess = self.store.get_sessions()[0]
        self.assertEqual(sess['ended_at'], saved)
        self.assertGreaterEqual(datetime.datetime.fromisoformat(saved), at(1740))


# (sender, subject, opening of body) -> expected kind, platform, task
REAL_MAIL = [
    ("no-reply@outlier.ai", "Your Outlier account is waiting on one quick step",
     "Outlier Your Outlier account is waiting on one quick step Hey there, Just a heads up: "
     "you can't move forward with your Outlier account until your phone number is verified.",
     "action", "Outlier", maildetect.TASK_PHONE),
    ("no-reply@outlier.ai", "One quick code unlocks your next step",
     "Friendly reminder: you still need to verify your phone number to continue setting up "
     "your Outlier account.", "action", "Outlier", maildetect.TASK_PHONE),
    ("no-reply@outlier.ai", "You're Invited: Join an Outlier Welcome Session",
     "You're invited to a Welcome Session to help you get started", "ignore", None, None),
    ("insideoutlier@outlier.ai", "Inside Outlier: What to tell an AI agent before you ask it anything",
     "TL;DR This week's tip", "ignore", None, None),
    ("support@outlier.ai", "Your link to sign in to Outlier",
     "Click below to sign in securely to your Outlier account.", "login", "Outlier", maildetect.TASK_EMAIL),
    ("noreply@alignerr.com", "Alignerr Account Created",
     "Your Alignerr account has been created. Apply for a job and start earning!",
     "account", "Alignerr", None),
    ("no-reply@mercor.com", "Your phone number has been verified",
     "This is a confirmation that your phone number ending in 0000 has been successfully verified",
     "done", "Mercor", maildetect.TASK_PHONE),
    ("no-reply@mercor.com", "Onboarding Onto Mercor",
     "Welcome to Mercor We connect you with top paying remote AI projects.", "account", "Mercor", None),
    ("auth@mercor.com", "Sign in to Mercor", "Click the link below to sign in", "login", "Mercor",
     maildetect.TASK_EMAIL),
    ("no-reply@telusinternational.ai", "Verification code for your account",
     "Here's your verification code", "login", "TELUS Digital", maildetect.TASK_EMAIL),
    ("no-reply@telusinternational.ai", "Confirm your email address on AI Community",
     "Thank you for creating an AI Community Platform account. To activate your account",
     "action", "TELUS Digital", maildetect.TASK_EMAIL),
    ("team@babel.audio", "Complete your video application from a laptop today",
     "We have the final few spots left for our English Video project", "action", "Babel Audio",
     maildetect.TASK_FINISH),
    ("team@babel.audio", "Hey, you're one step from $50/recorded hour",
     "I noticed you signed up for the video project with us but didn't complete the final step",
     "action", "Babel Audio", maildetect.TASK_FINISH),
    ("team@babel.audio", "Reminder: Apply now to Model Analysis projects on Babel Audio!",
     "applications for our new Model Analysis project is still open", "opportunity", "Babel Audio", None),
    ("notifications@babel.audio", "123456 is your verification code",
     "Enter the following verification code", "login", "Babel Audio", maildetect.TASK_EMAIL),
    # Payment mail that is not income
    ("service@paypal.com", "A PayPal Debit Card transaction was declined",
     "Your $0.00 USD PayPal Debit Card x-0000 transaction at an online store", "ignore", None, None),
    ("service@paypal.com", "Don't forget your cart—checkout fast with PayPal!",
     "See the items you left in your cart", "ignore", None, None),
    ("samsung@innovations.samsungusa.com", "Save up to $1,300 on Galaxy devices", "", "ignore", None, None),
]


class TestMailClassify(unittest.TestCase):
    def setUp(self):
        self.store = make_store()
        self.plats = self.store.get_all_platforms()

    def test_real_mail(self):
        for sender, subject, body, kind, plat, task in REAL_MAIL:
            with self.subTest(subject=subject):
                d = maildetect.classify(sender, subject, body, self.plats)
                self.assertEqual(d.kind, kind)
                if plat:
                    self.assertEqual(d.platform_name, plat)
                if task:
                    self.assertEqual(d.task, task)

    def test_paypal_payout_names_platform(self):
        d = maildetect.classify("service@paypal.com", "You've got money",
                                "Smart Ecosystem sent you $123.45 USD", self.plats)
        self.assertEqual((d.kind, d.platform_name, d.amount_cents), ("payout", "Outlier", 12345))

    def test_payoneer_payout(self):
        d = maildetect.classify("noreply@payoneer.com", "You've received a payment",
                                "You've received USD 1,050.00 from TELUS International", self.plats)
        self.assertEqual((d.kind, d.platform_name, d.amount_cents), ("payout", "TELUS Digital", 105000))

    def test_unknown_payer(self):
        d = maildetect.classify("service@paypal.com", "You've got money",
                                "Grandma sent you $20.00 USD", self.plats)
        self.assertEqual(d.kind, "payout_unmatched")


class TestMailApply(unittest.TestCase):
    def setUp(self):
        self.store = make_store()

    def run_mail(self, sender, subject, body, when, ref):
        d = maildetect.classify(sender, subject, body, self.store.get_all_platforms())
        return maildetect.apply(self.store, d, when, ref)

    def now(self, days_ago=0):
        return (datetime.datetime.now(datetime.timezone.utc)
                - datetime.timedelta(days=days_ago)).isoformat()

    def test_reminder_then_done_closes_task(self):
        merc = self.store.get_platform_by_name("Mercor")['id']
        self.run_mail("no-reply@mercor.com", "Verify your phone to move forward",
                      "we'll send you a code to your phone", self.now(3), "<a>")
        self.assertIsNotNone(self.store.find_open_task(merc, maildetect.TASK_PHONE))
        self.assertEqual(self.store.get_platform(merc)['status'], 'account_made')
        self.run_mail("no-reply@mercor.com", "Your phone number has been verified",
                      "your phone number has been successfully verified", self.now(1), "<b>")
        self.assertIsNone(self.store.find_open_task(merc, maildetect.TASK_PHONE))

    def test_same_email_twice_is_one_change(self):
        args = ("service@paypal.com", "You've got money", "Prolific sent you $8.50 USD",
                self.now(), "<pay1>")
        self.assertIsNotNone(self.run_mail(*args))
        self.assertIsNone(self.run_mail(*args))
        pid = self.store.get_platform_by_name("Prolific")['id']
        self.assertEqual([p['amount_cents'] for p in self.store.get_payouts(pid)], [850])
        self.assertEqual(self.store.get_platform(pid)['status'], 'active')

    def test_old_reminder_makes_no_task(self):
        self.run_mail("team@babel.audio", "Finish your video application", "",
                      self.now(40), "<old>")
        pid = self.store.get_platform_by_name("Babel Audio")['id']
        self.assertIsNone(self.store.find_open_task(pid, maildetect.TASK_FINISH))

    def test_status_never_goes_backwards_or_touches_blocked(self):
        pid = self.store.get_platform_by_name("Outlier")['id']
        self.store.update_platform(pid, status='blocked')
        self.run_mail("support@outlier.ai", "Your link to sign in to Outlier", "", self.now(), "<o>")
        self.assertEqual(self.store.get_platform(pid)['status'], 'blocked')

    def test_new_platform_is_added_from_account_mail(self):
        self.assertIsNone(self.store.get_platform_by_name("Welo Data"))
        self.run_mail("noreply@welodata.ai", "Welcome to Welo Data", "Your account has been created",
                      self.now(), "<w>")
        plat = self.store.get_platform_by_name("Welo Data")
        self.assertIsNotNone(plat)
        self.assertEqual(plat['status'], 'account_made')

    def test_invite_from_unlisted_platform_adds_nothing(self):
        self.run_mail("jobs@welodata.ai", "New projects available - apply now", "", self.now(), "<x>")
        self.assertIsNone(self.store.get_platform_by_name("Welo Data"))


if __name__ == "__main__":
    unittest.main()


class TestMailParsing(unittest.TestCase):
    def test_html_only_message(self):
        import mailwatch
        raw = (b"From: Outlier <no-reply@outlier.ai>\r\n"
               b"Subject: Verify your phone to move forward: takes 30 seconds\r\n"
               b"Date: Fri, 02 Oct 2026 13:29:46 +0000\r\n"
               b"Message-ID: <abc@outlier.ai>\r\n"
               b"Content-Type: text/html; charset=utf-8\r\n\r\n"
               b"<html><style>p{}</style><p>The next step is verifying your&nbsp;phone number</p></html>")
        m = mailwatch.parse_message(raw, "me@gmail.com")
        self.assertEqual(m["ref"], "mail:<abc@outlier.ai>")
        self.assertEqual(m["date"], "2026-10-02T13:29:46+00:00")
        self.assertIn("verifying your phone number", m["body"])
        self.assertNotIn("<p>", m["body"])

    def test_multipart_prefers_plain(self):
        import mailwatch
        from email.message import EmailMessage
        msg = EmailMessage()
        msg["From"] = "service@paypal.com"
        msg["Subject"] = "You've got money"
        msg["Date"] = "Wed, 14 Oct 2026 10:00:00 -0400"
        msg["Message-ID"] = "<pp1@paypal.com>"
        msg.set_content("Smart Ecosystem sent you $64.20 USD")
        msg.add_alternative("<p>html version</p>", subtype="html")
        m = mailwatch.parse_message(msg.as_bytes(), "me@gmail.com")
        self.assertIn("$64.20", m["body"])
        self.assertEqual(m["date"], "2026-10-14T14:00:00+00:00")

    def test_process_applies_oldest_first(self):
        import mailwatch
        store = make_store()
        now = datetime.datetime.now(datetime.timezone.utc)
        newer = {"sender": "no-reply@mercor.com", "subject": "Your phone number has been verified",
                 "body": "successfully verified", "date": now.isoformat(), "ref": "mail:<2>"}
        older = {"sender": "no-reply@mercor.com", "subject": "Verify your phone to move forward",
                 "body": "phone", "date": (now - datetime.timedelta(days=2)).isoformat(),
                 "ref": "mail:<1>"}
        lines = mailwatch.process(store, [newer, older])     # handed over newest first
        self.assertEqual(len(lines), 2)
        merc = store.get_platform_by_name("Mercor")['id']
        self.assertIsNone(store.find_open_task(merc, maildetect.TASK_PHONE))
