"""All SQL and money math for Rater Desk. No UI imports here."""

import datetime
import sqlite3
import os

import paths
from migrations import (
    open_db, migrate, get_schema_version, utc_now, today_utc,
    VALID_PLATFORM_STATUS, VALID_PROJECT_STATUS, VALID_SETUP_STATUS,
    VALID_PAYOUT_KIND, VALID_COST_RECURRING, SCHEMA_VERSION,
)

DATA_DIR = str(paths.data_dir())
DB_PATH = str(paths.db_path())
BACKUP_DIR = str(paths.backup_dir())


# ---------------------------------------------------------------------------
# Money helpers — everything in integer cents
# ---------------------------------------------------------------------------

def cents_to_str(cents):
    """Format integer cents as a dollar string, e.g. 12345 -> '$123.45'."""
    if cents is None:
        return "—"
    sign = "-" if cents < 0 else ""
    c = abs(cents)
    return f"{sign}${c // 100}.{c % 100:02d}"


def cents_to_float(cents):
    """Convert integer cents to float dollars (only for calculations, never storage)."""
    if cents is None:
        return 0.0
    return cents / 100.0


def str_to_cents(s):
    """Parse a dollar string like '$123.45' or '123.45' into integer cents."""
    if s is None or s == "" or s == "—":
        return None
    cleaned = s.replace("$", "").replace(",", "").strip()
    if cleaned == "":
        return None
    parts = cleaned.split(".")
    if len(parts) == 1:
        return int(parts[0]) * 100
    dollars = int(parts[0])
    frac = parts[1]
    if len(frac) == 1:
        frac = frac + "0"
    elif len(frac) > 2:
        frac = frac[:2]
    cents_val = int(frac)
    if dollars < 0 or cleaned.startswith("-"):
        return -(abs(dollars) * 100 + cents_val)
    return dollars * 100 + cents_val


def real_rate(base_payouts_cents, hours):
    """Compute real $/hr as integer cents-per-hour. Returns None if hours==0."""
    if hours is None or hours == 0:
        return None
    return base_payouts_cents / hours  # cents per hour, fractional ok for display


def format_real_rate(base_payouts_cents, hours):
    """Format real $/hr: '—' when hours is 0, else '$X.XX'."""
    if hours is None or hours == 0:
        return "—"
    rate = real_rate(base_payouts_cents, hours)
    if rate is None:
        return "—"
    return cents_to_str(int(rate))


def hours_between(started_at, ended_at):
    """Decimal hours between two ISO timestamps. None if either is missing."""
    if not started_at or not ended_at:
        return None
    try:
        start = datetime.datetime.fromisoformat(started_at)
        end = datetime.datetime.fromisoformat(ended_at)
        delta = (end - start).total_seconds()
        if delta < 0:
            return None
        return delta / 3600.0
    except (ValueError, TypeError):
        return None


def days_in_period(start_date, end_date):
    """Number of days in a date range, inclusive of both endpoints."""
    if not start_date or not end_date:
        return 0
    try:
        start = datetime.date.fromisoformat(start_date)
        end = datetime.date.fromisoformat(end_date)
        return (end - start).days + 1
    except (ValueError, TypeError):
        return 0


def daily_cost(cents, start_date, end_date):
    """Spread a cost evenly across days in the period. Returns cents/day as float."""
    days = days_in_period(start_date, end_date)
    if days == 0:
        return 0.0
    return cents / days


# ---------------------------------------------------------------------------
# Store — wraps a sqlite3 connection
# ---------------------------------------------------------------------------

class Store:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.conn = open_db(db_path)

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # -- generic get

    def get_setting(self, key, default=None):
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        self.conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, str(value))
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Platforms

    def add_platform(self, name, login_url=None, status='not_started',
                     advertises_rate_cents=None, payout_method=None,
                     payout_notes=None, needs_vpn_off=False,
                     idle_warn_days=None, notes=None, sort_order=0,
                     seeded_from=None):
        assert status in VALID_PLATFORM_STATUS, f"Invalid status: {status}"
        row = self.conn.execute(
            """INSERT INTO platforms
               (name, login_url, status, advertises_rate_cents, payout_method,
                payout_notes, needs_vpn_off, idle_warn_days, notes, sort_order,
                seeded_from)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, login_url, status, advertises_rate_cents, payout_method,
             payout_notes, 1 if needs_vpn_off else 0, idle_warn_days,
             notes, sort_order, seeded_from)
        )
        self.conn.commit()
        return row.lastrowid

    def get_platform(self, platform_id):
        return self.conn.execute(
            "SELECT * FROM platforms WHERE id = ?", (platform_id,)
        ).fetchone()

    def get_platform_by_name(self, name):
        return self.conn.execute(
            "SELECT * FROM platforms WHERE name = ?", (name,)
        ).fetchone()

    def update_platform(self, platform_id, **fields):
        if not fields:
            return
        valid_cols = {'name', 'login_url', 'status', 'advertises_rate_cents',
                      'payout_method', 'payout_notes', 'needs_vpn_off',
                      'idle_warn_days', 'notes', 'sort_order', 'seeded_from',
                      'match_words', 'email_domains'}
        cols = {k: v for k, v in fields.items() if k in valid_cols}
        if not cols:
            return
        set_clause = ", ".join(f"{k} = ?" for k in cols)
        params = list(cols.values()) + [platform_id]
        self.conn.execute(
            f"UPDATE platforms SET {set_clause} WHERE id = ?",
            params
        )
        self.conn.commit()

    def get_all_platforms(self):
        return self.conn.execute(
            "SELECT * FROM platforms ORDER BY sort_order, name"
        ).fetchall()

    def get_active_session_for_platform(self, platform_id):
        """Return the open session for this platform, if any."""
        return self.conn.execute(
            "SELECT * FROM work_sessions WHERE platform_id = ? AND ended_at IS NULL",
            (platform_id,)
        ).fetchone()

    # ------------------------------------------------------------------
    # Projects

    def add_project(self, platform_id, name, rate_cents_per_hour=None,
                    rate_effective_from=None, status='applied', notes=None):
        assert status in VALID_PROJECT_STATUS, f"Invalid status: {status}"
        row = self.conn.execute(
            """INSERT INTO projects
               (platform_id, name, rate_cents_per_hour, rate_effective_from,
                status, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (platform_id, name, rate_cents_per_hour, rate_effective_from,
             status, notes)
        )
        self.conn.commit()
        return row.lastrowid

    def get_projects_for_platform(self, platform_id):
        return self.conn.execute(
            "SELECT * FROM projects WHERE platform_id = ? ORDER BY name",
            (platform_id,)
        ).fetchall()

    def get_project(self, project_id):
        return self.conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()

    def update_project(self, project_id, **fields):
        if not fields:
            return
        valid_cols = {'name', 'rate_cents_per_hour', 'rate_effective_from',
                      'status', 'notes'}
        cols = {k: v for k, v in fields.items() if k in valid_cols}
        if not cols:
            return
        set_clause = ", ".join(f"{k} = ?" for k in cols)
        params = list(cols.values()) + [project_id]
        self.conn.execute(
            f"UPDATE projects SET {set_clause} WHERE id = ?",
            params
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Setup tasks

    def add_setup_task(self, platform_id=None, project_id=None, title="",
                       detail=None, is_human_only=False, status='todo',
                       due_date=None, sort_order=0):
        assert status in VALID_SETUP_STATUS, f"Invalid status: {status}"
        row = self.conn.execute(
            """INSERT INTO setup_tasks
               (platform_id, project_id, title, detail, is_human_only,
                status, due_date, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (platform_id, project_id, title, detail,
             1 if is_human_only else 0, status, due_date, sort_order)
        )
        self.conn.commit()
        return row.lastrowid

    def get_setup_tasks(self, platform_id=None, status=None):
        query = "SELECT * FROM setup_tasks WHERE 1=1"
        params = []
        if platform_id is not None:
            query += " AND platform_id = ?"
            params.append(platform_id)
        if status is not None:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY sort_order, id"
        return self.conn.execute(query, params).fetchall()

    def update_setup_task(self, task_id, **fields):
        if not fields:
            return
        valid_cols = {'platform_id', 'project_id', 'title', 'detail',
                      'is_human_only', 'status', 'due_date', 'completed_at',
                      'sort_order'}
        cols = {k: v for k, v in fields.items() if k in valid_cols}
        if not cols:
            return
        set_clause = ", ".join(f"{k} = ?" for k in cols)
        params = list(cols.values()) + [task_id]
        self.conn.execute(
            f"UPDATE setup_tasks SET {set_clause} WHERE id = ?",
            params
        )
        self.conn.commit()

    def find_open_task(self, platform_id, title):
        """An unfinished setup task with this exact title on this platform."""
        return self.conn.execute(
            """SELECT * FROM setup_tasks
               WHERE platform_id = ? AND title = ? AND status IN ('todo', 'doing')
               ORDER BY id LIMIT 1""",
            (platform_id, title)
        ).fetchone()

    def get_due_setup_tasks(self, date_str=None):
        """Tasks that are due today or overdue (not done/skipped)."""
        if date_str is None:
            date_str = today_utc()
        return self.conn.execute(
            """SELECT * FROM setup_tasks
               WHERE status IN ('todo', 'doing')
               AND due_date IS NOT NULL
               AND due_date <= ?
               ORDER BY due_date, sort_order, id""",
            (date_str,)
        ).fetchall()

    # ------------------------------------------------------------------
    # Work sessions / Timer

    def start_session(self, platform_id, project_id=None, rate_cents_per_hour=None,
                      note=None, started_at=None, source='manual'):
        """Start a work session. Returns session id.

        Auto mode passes started_at (back-dated to when you opened the platform)
        and source='auto'.
        """
        if rate_cents_per_hour is None:
            proj = self.get_project(project_id) if project_id else None
            if proj and proj['rate_cents_per_hour'] is not None:
                rate_cents_per_hour = proj['rate_cents_per_hour']
            else:
                plat = self.get_platform(platform_id)
                rate_cents_per_hour = plat['advertises_rate_cents'] if (plat and plat['advertises_rate_cents'] is not None) else 0
        row = self.conn.execute(
            """INSERT INTO work_sessions
               (platform_id, project_id, started_at, rate_cents_per_hour, note, source)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (platform_id, project_id, started_at or utc_now(), rate_cents_per_hour, note,
             source)
        )
        self.conn.commit()
        return row.lastrowid

    def stop_session(self, session_id, item_count=None, note=None, ended_at=None):
        """Stop a work session, recording item_count (None if skipped).

        ended_at lets auto mode end it when you actually left, not when it noticed.
        """
        updates = ["ended_at = ?"]
        params = [ended_at or utc_now()]
        if note is not None:
            updates.append("note = ?")
            params.append(note)
        if item_count is not None:
            updates.append("item_count = ?")
            params.append(item_count)
        else:
            updates.append("item_count = NULL")
        params.append(session_id)
        self.conn.execute(
            f"UPDATE work_sessions SET {', '.join(updates)} WHERE id = ? AND ended_at IS NULL",
            params
        )
        self.conn.commit()
        return self.conn.total_changes

    def recover_sessions(self):
        """Return all open sessions (ended_at IS NULL)."""
        return self.conn.execute(
            "SELECT * FROM work_sessions WHERE ended_at IS NULL ORDER BY started_at"
        ).fetchall()

    def close_session(self, session_id):
        """Mark a session as closed (ended_at set) without stopping the timer — used for recovery cleanup."""
        now = utc_now()
        self.conn.execute(
            "UPDATE work_sessions SET ended_at = ? WHERE id = ? AND ended_at IS NULL",
            (now, session_id)
        )
        self.conn.commit()

    def delete_session(self, session_id):
        self.conn.execute("DELETE FROM work_sessions WHERE id = ?", (session_id,))
        self.conn.commit()

    def get_session(self, session_id):
        return self.conn.execute(
            "SELECT * FROM work_sessions WHERE id = ?", (session_id,)
        ).fetchone()

    def get_sessions(self, platform_id=None, project_id=None, limit=100):
        query = "SELECT * FROM work_sessions WHERE 1=1"
        params = []
        if platform_id is not None:
            query += " AND platform_id = ?"
            params.append(platform_id)
        if project_id is not None:
            query += " AND project_id = ?"
            params.append(project_id)
        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)
        return self.conn.execute(query, params).fetchall()

    # ------------------------------------------------------------------
    # Detections (auto mode's log)

    def add_detection(self, kind, summary, platform_id=None, change=None,
                      happened_at=None, source_ref=None, quiet=False):
        """Log something auto mode found. Returns the id, or None if source_ref was seen."""
        try:
            row = self.conn.execute(
                """INSERT INTO detections
                   (detected_at, happened_at, kind, platform_id, summary, change,
                    quiet, source_ref)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (utc_now(), happened_at, kind, platform_id, summary, change,
                 1 if quiet else 0, source_ref)
            )
        except sqlite3.IntegrityError:
            return None
        self.conn.commit()
        return row.lastrowid

    def has_detection(self, source_ref):
        if not source_ref:
            return False
        return self.conn.execute(
            "SELECT 1 FROM detections WHERE source_ref = ?", (source_ref,)
        ).fetchone() is not None

    def get_detections(self, limit=200, include_quiet=False):
        query = "SELECT * FROM detections"
        if not include_quiet:
            query += " WHERE quiet = 0"
        query += " ORDER BY COALESCE(happened_at, detected_at) DESC, id DESC LIMIT ?"
        return self.conn.execute(query, (limit,)).fetchall()

    # ------------------------------------------------------------------
    # Payouts

    def add_payout(self, platform_id, received_on, amount_cents, kind='base',
                   method=None, period_start=None, period_end=None, note=None):
        assert kind in VALID_PAYOUT_KIND, f"Invalid kind: {kind}"
        assert isinstance(amount_cents, int), "amount_cents must be integer"
        row = self.conn.execute(
            """INSERT INTO payouts
               (platform_id, received_on, amount_cents, kind, method,
                period_start, period_end, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (platform_id, received_on, amount_cents, kind, method,
             period_start, period_end, note)
        )
        self.conn.commit()
        return row.lastrowid

    def get_payouts(self, platform_id=None, limit=200):
        query = "SELECT * FROM payouts WHERE 1=1"
        params = []
        if platform_id is not None:
            query += " AND platform_id = ?"
            params.append(platform_id)
        query += " ORDER BY received_on DESC LIMIT ?"
        params.append(limit)
        return self.conn.execute(query, params).fetchall()

    # ------------------------------------------------------------------
    # Costs

    def add_cost(self, label, amount_cents=None, incurred_on=None,
                 recurring='one_off', note=None):
        assert recurring in VALID_COST_RECURRING, f"Invalid recurring: {recurring}"
        if amount_cents is not None:
            assert isinstance(amount_cents, int), "amount_cents must be integer"
        row = self.conn.execute(
            """INSERT INTO costs
               (label, amount_cents, incurred_on, recurring, note)
               VALUES (?, ?, ?, ?, ?)""",
            (label, amount_cents, incurred_on, recurring, note)
        )
        self.conn.commit()
        return row.lastrowid

    def get_costs(self, limit=500):
        return self.conn.execute(
            "SELECT * FROM costs ORDER BY incurred_on DESC, id"
        ).fetchall()

    # ------------------------------------------------------------------
    # Blocks (week plan)

    def add_block(self, starts_at, ends_at, title, platform_id=None,
                  project_id=None, recurring_rule=None):
        uid = f"raterdesk-block-{0}"  # placeholder, set below
        row = self.conn.execute(
            """INSERT INTO blocks
               (platform_id, project_id, starts_at, ends_at, title,
                calendar_uid, recurring_rule)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (platform_id, project_id, starts_at, ends_at, title,
             None, recurring_rule)
        )
        block_id = row.lastrowid
        uid = f"raterdesk-block-{block_id}@raterdesk"
        self.conn.execute(
            "UPDATE blocks SET calendar_uid = ? WHERE id = ?",
            (uid, block_id)
        )
        self.conn.commit()
        return block_id

    def get_blocks(self, start_date=None, end_date=None):
        query = "SELECT * FROM blocks WHERE 1=1"
        params = []
        if start_date:
            query += " AND starts_at >= ?"
            params.append(start_date)
        if end_date:
            query += " AND starts_at <= ?"
            params.append(end_date)
        query += " ORDER BY starts_at"
        return self.conn.execute(query, params).fetchall()

    def get_block(self, block_id):
        return self.conn.execute(
            "SELECT * FROM blocks WHERE id = ?", (block_id,)
        ).fetchone()

    def update_block(self, block_id, **fields):
        if not fields:
            return
        valid_cols = {'platform_id', 'project_id', 'starts_at', 'ends_at',
                      'title'}
        cols = {k: v for k, v in fields.items() if k in valid_cols}
        if not cols:
            return
        set_clause = ", ".join(f"{k} = ?" for k in cols)
        params = list(cols.values()) + [block_id]
        self.conn.execute(
            f"UPDATE blocks SET {set_clause} WHERE id = ?",
            params
        )
        self.conn.commit()

    def delete_block(self, block_id):
        self.conn.execute("DELETE FROM blocks WHERE id = ?", (block_id,))
        self.conn.commit()

    # ------------------------------------------------------------------
    # Derived money queries

    def platform_earnings_cents(self, platform_id, start_date=None, end_date=None):
        """Sum of BASE payouts in date range."""
        query = "SELECT COALESCE(SUM(amount_cents), 0) FROM payouts WHERE platform_id = ? AND kind = 'base'"
        params = [platform_id]
        if start_date:
            query += " AND received_on >= ?"
            params.append(start_date)
        if end_date:
            query += " AND received_on <= ?"
            params.append(end_date)
        row = self.conn.execute(query, params).fetchone()
        return row[0] if row else 0

    def platform_hours(self, platform_id, start_date=None, end_date=None):
        """Total hours from ended sessions in date range."""
        query = """SELECT COALESCE(SUM(
            (julianday(ended_at) - julianday(started_at)) * 24.0
        ), 0) FROM work_sessions WHERE platform_id = ? AND ended_at IS NOT NULL"""
        params = [platform_id]
        if start_date:
            query += " AND started_at >= ?"
            params.append(start_date)
        if end_date:
            query += " AND started_at <= ?"
            params.append(end_date)
        row = self.conn.execute(query, params).fetchone()
        return row[0] if row else 0.0

    def platform_bonus_cents(self, platform_id, start_date=None, end_date=None):
        """Sum of BONUS payouts in date range (excluded from real rate)."""
        query = "SELECT COALESCE(SUM(amount_cents), 0) FROM payouts WHERE platform_id = ? AND kind = 'bonus'"
        params = [platform_id]
        if start_date:
            query += " AND received_on >= ?"
            params.append(start_date)
        if end_date:
            query += " AND received_on <= ?"
            params.append(end_date)
        row = self.conn.execute(query, params).fetchone()
        return row[0] if row else 0

    def total_costs_cents(self, start_date=None, end_date=None):
        """Sum of all costs with known amounts in date range, including recurring spread."""
        base = self.conn.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) FROM costs WHERE amount_cents IS NOT NULL AND incurred_on BETWEEN COALESCE(?, incurred_on) AND COALESCE(?, incurred_on)",
            (start_date, end_date)
        ).fetchone()
        return base[0] if base else 0

    def all_costs_with_spread(self, start_date=None, end_date=None):
        """Return list of (cost_row, allocated_cents) for costs that overlap the period.

        Recurring costs are spread across days in the period.
        """
        rows = self.get_costs()
        result = []
        for cost in rows:
            amount = cost['amount_cents']
            if amount is None:
                result.append((cost, None))
                continue
            allocated = self._allocate_cost(cost, amount, start_date, end_date)
            result.append((cost, allocated))
        return result

    def _allocate_cost(self, cost, amount, start_date, end_date):
        """Allocate a cost to a period. Returns cents as int (rounded)."""
        recurring = cost['recurring']
        incurred = cost['incurred_on']

        if recurring == 'one_off':
            if start_date and end_date:
                if incurred and start_date <= incurred <= end_date:
                    return amount
                return 0
            return amount

        if recurring in ('monthly', 'annual'):
            days = days_in_period(start_date, end_date) if start_date and end_date else 0
            if days == 0:
                return 0
            per_day = daily_cost(amount, start_date, end_date)
            return int(round(per_day * days))

        return amount

    def platform_report(self, platform_id, start_date=None, end_date=None):
        """Full report for a platform in a date range."""
        earnings = self.platform_earnings_cents(platform_id, start_date, end_date)
        bonus = self.platform_bonus_cents(platform_id, start_date, end_date)
        hours = self.platform_hours(platform_id, start_date, end_date)
        plat = self.get_platform(platform_id)
        advert = plat['advertises_rate_cents'] if plat else None
        return {
            'platform_id': platform_id,
            'advertised_rate_cents': advert,
            'real_rate_cents_per_hour': real_rate(earnings, hours) if hours else None,
            'hours': hours,
            'earnings_cents': earnings,
            'bonus_cents': bonus,
            'sessions': self.get_sessions(platform_id) if hours else [],
        }

    def full_report(self, start_date=None, end_date=None):
        """Per-platform summary for the date range, plus net."""
        platforms = self.get_all_platforms()
        results = []
        for plat in platforms:
            report = self.platform_report(plat['id'], start_date, end_date)
            report['name'] = plat['name']
            results.append(report)
        costs = self.total_costs_cents(start_date, end_date)
        total_earnings = sum(r['earnings_cents'] for r in results)
        total_net = total_earnings - costs
        return {
            'platforms': results,
            'total_earnings_cents': total_earnings,
            'total_costs_cents': costs,
            'total_net_cents': total_net,
        }


def cents_per_hour_from_row(rate_cents_per_hour):
    """Just a helper to get formatted rate."""
    return rate_cents_per_hour
