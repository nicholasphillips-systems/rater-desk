"""Turn a platform or payment email into a change in Rater Desk. No UI imports here.

classify() reads one email and says what it means; apply() makes that change in the
store and logs it. Mail is processed oldest first, so a later email (a phone-verified
notice) closes what an earlier one opened (a verify-your-phone reminder).

What changes on its own:
  - a payment email naming a platform     -> payout on the Money screen
  - an account / sign-in / welcome email   -> status raised to at least Account Made
  - an acceptance email                    -> status raised to Active
  - a "finish this step" reminder          -> setup task, closed again by the done email
  - mail from a known platform not in the list -> the platform is added
Statuses only ever move forward, and Blocked / Paused / Dead are never touched.
Rejections, project invites and unmatched payments are logged, not applied.
"""

import datetime
import re
from collections import namedtuple

import catalog

Detection = namedtuple("Detection", [
    "kind",            # payout, payout_unmatched, accepted, rejected, account, action, done, opportunity, login, ignore
    "platform",        # platform row, or None
    "platform_name",   # name even when the platform is not in the list yet
    "summary",
    "amount_cents",
    "task",            # setup task title this email opens or closes
])

STATUS_RANK = {'not_started': 0, 'account_made': 1, 'profile_done': 2, 'active': 3}
STATUS_FLOOR = {'login': 'account_made', 'account': 'account_made', 'done': 'account_made',
                'action': 'account_made', 'accepted': 'active', 'payout': 'active'}

# A reminder older than this is history, not a to-do.
TASK_MAX_AGE_DAYS = 14

TASK_PHONE = "Verify phone number"
TASK_EMAIL = "Confirm email address"
TASK_FINISH = "Finish sign-up"

_LOGIN = ["verification code", "your code", "sign in to", "sign-in link", "link to sign in",
          "login link", "log in to", "magic link", "reset your", "password", "one-time"]
_REJECTED = ["unfortunately", "not been selected", "not selected", "unable to move forward",
             "not moving forward", "not be moving forward", "we regret", "were not successful"]
_ACCEPTED = ["congratulations", "you've been accepted", "you have been accepted", "you're accepted",
             "application approved", "has been approved", "you qualified", "you passed",
             "welcome to the team", "you've been selected", "you have been selected",
             "added to the project", "onboarded to"]
_DONE = ["has been verified", "successfully verified", "verified successfully",
         "email confirmed", "email address confirmed", "identity verified"]
_ACTION = ["verify your phone", "phone number", "complete your", "finish your",
           "one step from", "one quick step", "more steps", "steps to complete", "waiting on",
           "action required", "incomplete", "almost complete",
           "confirm your email", "verify your email", "unlocks your next step"]
_ACCOUNT = ["account created", "account has been created", "welcome to", "thanks for signing up",
            "thank you for signing up", "thank you for creating", "onboarding", "get started"]
_OPPORTUNITY = ["apply now", "new project", "projects available", "now open", "opportunit",
                "spots left", "invited to apply", "new task", "tasks available", "apply to"]
_NOISE = ["welcome session", "webinar", "newsletter", "inside outlier", "this week's tip",
          "digest", "unsubscribe from"]
_PAY_IN = ["you've got money", "you got money", "you received", "you've received", "sent you",
           "payment received", "received a payment", "payment from", "money is on its way",
           "payout sent", "payment sent", "you've been paid", "you have been paid",
           "payment processed", "payout processed", "payout of", "has been paid"]
_PAY_OUT = ["declined", "you sent", "you paid", "receipt for your", "your cart", "checkout",
            "debit card", "refund", "request for", "requested", "invoice due", "money request"]

_AMOUNT = [
    re.compile(r"\$\s?([\d,]+(?:\.\d{2})?)\s*(?:USD)?", re.IGNORECASE),
    re.compile(r"USD\s?\$?\s?([\d,]+(?:\.\d{2})?)", re.IGNORECASE),
    re.compile(r"([\d,]+\.\d{2})\s?USD", re.IGNORECASE),
]


def _has(text, phrases):
    return any(p in text for p in phrases)


def find_amount_cents(text):
    for rx in _AMOUNT:
        m = rx.search(text or "")
        if m:
            raw = m.group(1).replace(",", "")
            if not raw:
                continue
            if "." in raw:
                dollars, cents = raw.split(".", 1)
                value = int(dollars or 0) * 100 + int((cents + "00")[:2])
            else:
                value = int(raw) * 100
            if value > 0:
                return value
    return None


def _task_for(text):
    if "phone" in text:
        return TASK_PHONE
    if "email" in text and ("confirm" in text or "verify" in text):
        return TASK_EMAIL
    return TASK_FINISH


def classify(sender, subject, body, platforms):
    """Read one email. Returns a Detection (kind 'ignore' for mail that means nothing)."""
    subj = (subject or "").strip()
    subj_l = subj.lower()
    # The subject carries the meaning; the opening of the body backs it up.
    head = (subj + "\n" + (body or "")[:1500]).lower()

    if catalog.is_payment_sender(sender):
        if _has(subj_l, _PAY_OUT) or not _has(head, _PAY_IN):
            return Detection("ignore", None, None, subj, None, None)
        amount = find_amount_cents(subj + "\n" + (body or "")[:3000])
        if amount is None:
            return Detection("ignore", None, None, subj, None, None)
        plat, name = catalog.platform_for_payer(subj + "\n" + (body or "")[:3000], platforms)
        if name is None:
            return Detection("payout_unmatched", None, None, subj, amount, None)
        return Detection("payout", plat, name, subj, amount, None)

    plat, name = catalog.platform_for_sender(sender, platforms)
    if name is None:
        return Detection("ignore", None, None, subj, None, None)

    def det(kind, amount=None, task=None):
        return Detection(kind, plat, name, subj, amount, task)

    if _has(subj_l, _NOISE):
        return det("ignore")
    if _has(subj_l, _LOGIN):
        return det("login", task=TASK_EMAIL)
    if _has(head, _REJECTED):
        return det("rejected")
    if _has(subj_l, _PAY_IN) or ("payout" in subj_l or "payment" in subj_l):
        amount = find_amount_cents(subj + "\n" + (body or "")[:3000])
        if amount is not None and not _has(subj_l, _PAY_OUT):
            return det("payout", amount)
    if _has(head, _DONE):
        return det("done", task=_task_for(head))
    if _has(subj_l, _ACCEPTED):
        return det("accepted")
    if _has(subj_l, _ACTION):
        # The subject says "one quick step"; the first lines say which step.
        return det("action", task=_task_for((subj + "\n" + (body or "")[:400]).lower()))
    if _has(subj_l, _ACCOUNT):
        return det("account")
    if _has(head, _OPPORTUNITY):
        return det("opportunity")
    return det("ignore")


def _age_days(happened_at):
    try:
        when = datetime.datetime.fromisoformat(happened_at)
    except (TypeError, ValueError):
        return 0
    if when.tzinfo is None:
        when = when.replace(tzinfo=datetime.timezone.utc)
    return (datetime.datetime.now(datetime.timezone.utc) - when).days


def _ensure_platform(store, det):
    """The platform row for this detection, adding it if a known platform is missing."""
    if det.platform is not None:
        return store.get_platform(det.platform['id']), None
    existing = store.get_platform_by_name(det.platform_name)
    if existing:
        return existing, None
    entry = catalog.catalog_entry(det.platform_name)
    pid = store.add_platform(det.platform_name, login_url=entry[4] if entry else None,
                             notes="Added by auto mode from an email.",
                             seeded_from="auto mode")
    return store.get_platform(pid), f"New platform added: {det.platform_name}"


def apply(store, det, happened_at, source_ref):
    """Make the change this email calls for and log it. Returns the log line, or None.

    source_ref (the email's Message-ID) makes this safe to run twice on one email.
    """
    if det.kind == "ignore" or store.has_detection(source_ref):
        return None

    if det.kind == "payout_unmatched":
        summary = f"Payment {_money(det.amount_cents)} - couldn't tell which platform: {det.summary}"
        store.add_detection("payout_unmatched", summary, change="Not added; add it on Money if it's yours",
                            happened_at=happened_at, source_ref=source_ref)
        return summary

    # Rejections and invites don't justify adding a platform nobody signed up for.
    if det.platform is None and det.kind in ("rejected", "opportunity", "login"):
        if not store.get_platform_by_name(det.platform_name):
            return None

    plat, added = _ensure_platform(store, det)
    changes = [added] if added else []

    floor = STATUS_FLOOR.get(det.kind)
    if floor and plat['status'] in STATUS_RANK and STATUS_RANK[plat['status']] < STATUS_RANK[floor]:
        store.update_platform(plat['id'], status=floor)
        changes.append(f"Status -> {floor.replace('_', ' ').title()}")

    if det.kind == "payout":
        day = (happened_at or datetime.date.today().isoformat())[:10]
        store.add_payout(plat['id'], day, det.amount_cents, method="email",
                         note=f"Auto: {det.summary}"[:200])
        changes.append(f"Payout {_money(det.amount_cents)} added")

    if det.kind == "action" and det.task and _age_days(happened_at) <= TASK_MAX_AGE_DAYS:
        if not store.find_open_task(plat['id'], det.task):
            store.add_setup_task(platform_id=plat['id'], title=det.task, is_human_only=True,
                                 detail=f"From email: {det.summary}",
                                 due_date=datetime.date.today().isoformat())
            changes.append(f"Task added: {det.task}")

    if det.kind in ("done", "login") and det.task:
        task = store.find_open_task(plat['id'], det.task)
        if task:
            store.update_setup_task(task['id'], status='done',
                                    completed_at=happened_at or datetime.date.today().isoformat())
            changes.append(f"Task done: {det.task}")

    # Sign-ins are routine; only log one when it actually changed something.
    if det.kind == "login" and not changes:
        store.add_detection("login", f"{plat['name']} - {det.summary}", platform_id=plat['id'],
                            change=None, happened_at=happened_at, source_ref=source_ref, quiet=True)
        return None

    label = {"payout": "Payment", "accepted": "Accepted", "rejected": "Rejected",
             "account": "Account", "action": "Needs you", "done": "Done",
             "opportunity": "Opening", "login": "Sign-in"}.get(det.kind, det.kind)
    summary = f"{label}: {plat['name']} - {det.summary}"
    store.add_detection(det.kind, summary, platform_id=plat['id'],
                        change="; ".join(changes) or None,
                        happened_at=happened_at, source_ref=source_ref)
    return summary


def _money(cents):
    return f"${cents // 100:,}.{cents % 100:02d}"
