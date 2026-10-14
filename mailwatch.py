"""Read platform and payment mail from Gmail for auto mode.

Gmail over IMAP with an app password (Google account -> Security -> 2-Step
Verification -> App passwords). Nothing is sent or changed in the mailbox: it is
opened read-only and messages are fetched with BODY.PEEK, so unread stays unread.
Only mail from the domains in catalog.py is fetched, via Gmail's own search
(X-GM-RAW).

App passwords live in the system keyring (KDE Wallet / Windows Credential
Manager), never in the database. The address list is a setting.

The IMAP work runs on a background thread; results come back to the main thread
through a Qt signal, because the store's SQLite connection belongs to the main
thread.
"""

import datetime
import email
import email.policy
import email.utils
import html
import imaplib
import json
import re
import threading

from PyQt6.QtCore import QObject, pyqtSignal

import catalog
import maildetect
import paths

IMAP_HOST = "imap.gmail.com"
FIRST_LOOK_BACK_DAYS = 60
KEYRING_SERVICE = paths.APP_NAME + " mail"


# -- accounts -----------------------------------------------------------------

def get_accounts(store):
    try:
        return json.loads(store.get_setting("mail_accounts", "[]"))
    except ValueError:
        return []


def save_password(address, app_password):
    import keyring
    keyring.set_password(KEYRING_SERVICE, address, app_password)


def load_password(address):
    try:
        import keyring
        return keyring.get_password(KEYRING_SERVICE, address)
    except Exception:
        return None


def add_account(store, address, app_password):
    save_password(address, app_password)
    accounts = [a for a in get_accounts(store) if a.lower() != address.lower()]
    accounts.append(address)
    store.set_setting("mail_accounts", json.dumps(accounts))


def remove_account(store, address):
    accounts = [a for a in get_accounts(store) if a.lower() != address.lower()]
    store.set_setting("mail_accounts", json.dumps(accounts))
    try:
        import keyring
        keyring.delete_password(KEYRING_SERVICE, address)
    except Exception:
        pass


def clean_app_password(text):
    """Google shows it as 'abcd efgh ijkl mnop'; IMAP wants the 16 letters."""
    return re.sub(r"\s+", "", text or "")


# -- IMAP ---------------------------------------------------------------------

def test_login(address, app_password):
    """Returns None if the login works, else a sentence saying why not."""
    try:
        conn = imaplib.IMAP4_SSL(IMAP_HOST, timeout=30)
        try:
            conn.login(address, app_password)
        finally:
            try:
                conn.logout()
            except Exception:
                pass
    except imaplib.IMAP4.error as e:
        msg = str(e)
        if "AUTHENTICATIONFAILED" in msg or "Invalid credentials" in msg:
            return "Gmail said no: that address and app password don't match."
        return f"Gmail said no: {msg}"
    except OSError as e:
        return f"Couldn't reach Gmail: {e}"
    return None


def _all_mail_folder(conn):
    """Gmail's All Mail folder (its name is translated in non-English accounts)."""
    typ, data = conn.list()
    for line in data or []:
        text = line.decode(errors="replace") if isinstance(line, bytes) else str(line)
        if "\\All" in text:
            m = re.search(r'"([^"]+)"\s*$', text) or re.search(r"(\S+)\s*$", text)
            if m:
                return m.group(1)
    return "INBOX"


def _gmail_query(domains, since_days):
    senders = " OR ".join(domains)
    return f"from:({senders}) newer_than:{since_days}d"


def fetch_new(address, app_password, domains, last_uid, uidvalidity):
    """Fetch watched mail newer than last_uid. Returns (messages, new_last_uid, uidvalidity).

    On the first run (or if Gmail renumbered the folder) it looks back
    FIRST_LOOK_BACK_DAYS so the current state of each platform is picked up.
    """
    conn = imaplib.IMAP4_SSL(IMAP_HOST, timeout=60)
    try:
        conn.login(address, app_password)
        folder = _all_mail_folder(conn)
        typ, _ = conn.select(f'"{folder}"', readonly=True)
        if typ != "OK":
            raise imaplib.IMAP4.error(f"couldn't open {folder}")
        _, validity_data = conn.response("UIDVALIDITY")
        current_validity = (validity_data or [b""])[0] or b""
        current_validity = current_validity.decode() if isinstance(current_validity, bytes) else str(current_validity)
        if current_validity != uidvalidity:
            last_uid = 0
        days = FIRST_LOOK_BACK_DAYS if not last_uid else 14
        query = _gmail_query(domains, days).replace('"', "")
        typ, data = conn.uid("SEARCH", "X-GM-RAW", f'"{query}"')
        uids = [int(u) for u in (data[0] or b"").split()] if typ == "OK" else []
        uids = [u for u in uids if u > last_uid]
        messages = []
        for i in range(0, len(uids), 25):
            batch = ",".join(str(u) for u in uids[i:i + 25])
            typ, rows = conn.uid("FETCH", batch, "(UID BODY.PEEK[])")
            for row in rows or []:
                if isinstance(row, tuple) and len(row) == 2:
                    messages.append(parse_message(row[1], address))
        return messages, max(uids + [last_uid]), current_validity
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def _strip_html(text):
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_message(raw, account):
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    body = ""
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is not None:
        try:
            body = part.get_content()
        except (LookupError, ValueError):
            body = part.get_payload(decode=True).decode("utf-8", errors="replace")
        if part.get_content_type() == "text/html":
            body = _strip_html(body)
    try:
        when = email.utils.parsedate_to_datetime(msg["Date"]).astimezone(datetime.timezone.utc)
    except (TypeError, ValueError):
        when = datetime.datetime.now(datetime.timezone.utc)
    return {
        "sender": str(msg.get("From", "")),
        "subject": str(msg.get("Subject", "")),
        "body": re.sub(r"\s+", " ", body)[:4000],
        "date": when.isoformat(),
        "ref": "mail:" + (str(msg.get("Message-ID", "")).strip()
                          or f"{account}:{when.isoformat()}:{msg.get('Subject', '')}"),
    }


# -- the watcher ------------------------------------------------------------------

def process(store, messages):
    """Classify and apply fetched mail, oldest first. Returns the log lines added."""
    lines = []
    for m in sorted(messages, key=lambda m: m["date"]):
        det = maildetect.classify(m["sender"], m["subject"], m["body"], store.get_all_platforms())
        line = maildetect.apply(store, det, m["date"], m["ref"])
        if line:
            lines.append(line)
    return lines


class MailWatcher(QObject):
    """Checks each saved account on a background thread; applies results here."""

    finished = pyqtSignal(list, list)   # log lines, errors
    _fetched = pyqtSignal(list, list, list)   # messages, cursor updates, errors

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.busy = False
        self._fetched.connect(self._on_fetched)

    def check_now(self):
        accounts = get_accounts(self.store)
        if self.busy or not accounts:
            return False
        self.busy = True
        domains = catalog.all_watched_domains(self.store.get_all_platforms())
        jobs = []
        for address in accounts:
            cursor = json.loads(self.store.get_setting(f"mail_cursor:{address}", "{}") or "{}")
            jobs.append((address, cursor.get("uid", 0), cursor.get("validity", "")))
        threading.Thread(target=self._run, args=(jobs, domains), daemon=True).start()
        return True

    def _run(self, jobs, domains):
        messages, cursors, errors = [], [], []
        for address, last_uid, validity in jobs:
            password = load_password(address)
            if not password:
                errors.append(f"{address}: no app password saved - remove and add it again")
                continue
            try:
                got, new_uid, new_validity = fetch_new(address, password, domains, last_uid, validity)
                messages.extend(got)
                cursors.append((address, new_uid, new_validity))
            except imaplib.IMAP4.error as e:
                errors.append(f"{address}: Gmail said no ({e})")
            except OSError as e:
                errors.append(f"{address}: couldn't reach Gmail ({e})")
        self._fetched.emit(messages, cursors, errors)

    def _on_fetched(self, messages, cursors, errors):
        lines = process(self.store, messages)
        # Cursors move only after the mail is applied, so a crash re-reads it
        # (and source_ref stops anything being applied twice).
        for address, uid, validity in cursors:
            self.store.set_setting(f"mail_cursor:{address}",
                                   json.dumps({"uid": uid, "validity": validity}))
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.store.set_setting("mail_last_check", now)
        self.store.set_setting("mail_last_error", "; ".join(errors))
        self.busy = False
        self.finished.emit(lines, errors)
