"""Default platform records and setup tasks for new installations.

Includes platform URLs, reference rates, payout methods, and setup steps.
Account progress is initialized separately for each installation. Unknown values
are stored as NULL; platform details can be edited after initialization.
"""

from store import Store, DB_PATH

SOURCE = "starter list"

# name, login_url, advertises_rate_cents, payout_method, payout_notes, needs_vpn_off, notes
PLATFORMS = [
    ("Mercor", "https://work.mercor.com/",
     None, "PayPal / bank transfer", None, False,
     "Magic-link login (no password)."),

    ("Babel Audio", "https://dashboard.babel.audio/sign-in",
     5000, "PayPal / Venmo / bank transfer", None, False,
     "Passwordless — 6-digit email code each login. Best-paying listed role: "
     "English Video Conversation Partner, $50/hr."),

    ("TELUS Digital", "https://www.telusinternational.ai/snake/",
     None, "Direct deposit / check", None, False,
     "Sign-up order: email + password, Contributor Services Agreement "
     "(a legal e-signature), profile, then the qualification exam."),

    ("Outlier", "https://app.outlier.ai/login",
     3500, "PayPal / AirTM", None, True,
     "Sign-in is blocked on VPN connections. Order: email link -> profile -> "
     "government ID -> skills assessment -> projects. Up to $35/hr."),

    ("Clickworker", "https://www.clickworker.com/",
     None, None, None, True,
     "Cloudflare blocks registration from VPN addresses."),

    ("OneForma", "https://my.oneforma.com/center/signup",
     None, "PayPal capped $300/yr -> Payoneer above",
     "PayPal capped $300/calendar year; Payoneer above that.", False,
     "Sign-up ends with an hCaptcha, then an email confirmation."),

    ("Prolific", "https://app.prolific.com/register",
     None, "Payout needs ID check", "ID check required for payouts.", False,
     "Sign-up asks for date of birth and sex as shown on legal ID. ~3 min."),

    ("Mindrift", "https://mindrift.toloka.ai/",
     None, None, None, False,
     "Social login only (Google, LinkedIn, Facebook, GitHub, Microsoft, Apple). "
     "Replaced Toloka. Order: sign up -> tasks -> add skills -> qualifications -> "
     "specialized projects."),

    ("Alignerr", "https://alignerr.com/", None, None, None, False, None),
    ("CrowdGen", "https://crowdgen.com/", None, None, None, False, None),
    ("LXT", "https://www.lxt.ai/jobs/", None, None, None, False, None),
    ("Sigma", "https://sigma.ai/", None, None, None, False, None),
]

# platform name, task title, detail
SETUP_TASKS = [
    ("Mercor", "Create account and upload resume", None),
    ("Mercor", "Complete Work Authorization",
     "Onboarding -> Work authorization: date of birth, two tick boxes, typed signature."),

    ("Babel Audio", "Create account and fill in profile", None),
    ("Babel Audio", "Complete ID verification and payout setup", None),

    ("TELUS Digital", "Create account and accept the Contributor Services Agreement",
     "The agreement is a legal e-signature."),
    ("TELUS Digital", "Complete the qualification exam", None),

    ("Outlier", "Sign in via the email link (VPN off)", None),
    ("Outlier", "Confirm identity with government ID", None),
    ("Outlier", "Validate skills (graded assessment)", None),

    ("Clickworker", "Register at clickworker.com (VPN off)", None),

    ("OneForma", "Create account and confirm email", None),
    ("OneForma", "Apply to UHRS/project opportunities", "oneforma.com/projects/"),

    ("Prolific", "Complete Prolific signup", None),
    ("Mindrift", "Sign in with a social account", None),
    ("Alignerr", "Create account", None),
    ("CrowdGen", "Create account", None),
    ("LXT", "Create account", None),
    ("Sigma", "Create account", None),
]


def seed(db_path=None):
    """Add the starter platforms and setup tasks. Safe to run twice."""
    if db_path is None:
        db_path = DB_PATH

    store = Store(db_path)
    try:
        for order, p in enumerate(PLATFORMS):
            name, login_url, rate, payout_method, payout_notes, vpn_off, notes = p
            if store.get_platform_by_name(name) is None:
                store.add_platform(
                    name=name, login_url=login_url, status='not_started',
                    advertises_rate_cents=rate, payout_method=payout_method,
                    payout_notes=payout_notes, needs_vpn_off=vpn_off,
                    notes=notes, sort_order=order, seeded_from=SOURCE,
                )

        for pname, title, detail in SETUP_TASKS:
            plat = store.get_platform_by_name(pname)
            if plat is None:
                continue
            existing = store.conn.execute(
                "SELECT 1 FROM setup_tasks WHERE platform_id = ? AND title = ?",
                (plat['id'], title)
            ).fetchone()
            if existing is None:
                store.add_setup_task(
                    platform_id=plat['id'], title=title, detail=detail,
                    is_human_only=True, status='todo',
                )
    finally:
        store.close()

    return db_path
