import sqlite3
import os
import datetime

SCHEMA_VERSION = 1

MIGRATIONS = {
    1: """
-- Rater Desk database schema
-- All money stored as integer cents. No floats.

CREATE TABLE platforms (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    login_url       TEXT,
    status          TEXT NOT NULL DEFAULT 'not_started',
    advertises_rate_cents INTEGER,
    payout_method   TEXT,
    payout_notes    TEXT,
    needs_vpn_off   INTEGER NOT NULL DEFAULT 0,
    idle_warn_days  INTEGER,
    notes           TEXT,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    seeded_from     TEXT,
    UNIQUE(name)
);

CREATE TABLE projects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_id     INTEGER NOT NULL REFERENCES platforms(id),
    name            TEXT NOT NULL,
    rate_cents_per_hour INTEGER,
    rate_effective_from TEXT,
    status          TEXT NOT NULL DEFAULT 'applied',
    notes           TEXT,
    UNIQUE(platform_id, name)
);

CREATE TABLE setup_tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_id     INTEGER REFERENCES platforms(id),
    project_id      INTEGER REFERENCES projects(id),
    title           TEXT NOT NULL,
    detail          TEXT,
    is_human_only   INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'todo',
    due_date        TEXT,
    completed_at    TEXT,
    sort_order      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE work_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_id     INTEGER NOT NULL REFERENCES platforms(id),
    project_id      INTEGER REFERENCES projects(id),
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    rate_cents_per_hour INTEGER NOT NULL,
    item_count      INTEGER,
    note            TEXT
);

CREATE TABLE payouts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_id     INTEGER NOT NULL REFERENCES platforms(id),
    received_on     TEXT NOT NULL,
    amount_cents    INTEGER NOT NULL,
    kind            TEXT NOT NULL DEFAULT 'base',
    method          TEXT,
    period_start    TEXT,
    period_end      TEXT,
    note            TEXT
);

CREATE TABLE costs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    label           TEXT NOT NULL,
    amount_cents    INTEGER,
    incurred_on     TEXT,
    recurring       TEXT NOT NULL DEFAULT 'one_off',
    note            TEXT
);

CREATE TABLE blocks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_id     INTEGER REFERENCES platforms(id),
    project_id      INTEGER REFERENCES projects(id),
    starts_at       TEXT NOT NULL,
    ends_at         TEXT NOT NULL,
    title           TEXT NOT NULL,
    calendar_uid    TEXT,
    recurring_rule  TEXT
);

CREATE TABLE settings (
    key             TEXT PRIMARY KEY,
    value           TEXT
);
""",
}

VALID_PLATFORM_STATUS = {'not_started', 'account_made', 'profile_done', 'blocked', 'active', 'paused', 'dead'}
VALID_PROJECT_STATUS = {'applied', 'active', 'paused', 'completed', 'rejected'}
VALID_SETUP_STATUS = {'todo', 'doing', 'done', 'skipped'}
VALID_PAYOUT_KIND = {'base', 'bonus'}
VALID_COST_RECURRING = {'one_off', 'monthly', 'annual'}


def get_schema_version(conn):
    """Return current schema version from settings table, or 0 if not set."""
    try:
        row = conn.execute("SELECT value FROM settings WHERE key = 'schema_version'").fetchone()
        if row:
            return int(row[0])
    except sqlite3.OperationalError:
        pass
    return 0


def set_schema_version(conn, version):
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        ('schema_version', str(version))
    )
    conn.commit()


def migrate(conn):
    """Run all pending migrations up to SCHEMA_VERSION."""
    current = get_schema_version(conn)
    for version in range(current + 1, SCHEMA_VERSION + 1):
        if version not in MIGRATIONS:
            break
        conn.executescript(MIGRATIONS[version])
        set_schema_version(conn, version)
    conn.commit()


def open_db(db_path):
    """Open a database, running migrations if needed. Creates parent dir."""
    os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if get_schema_version(conn) == 0 and not table_exists(conn, 'platforms'):
        migrate(conn)
    elif get_schema_version(conn) < SCHEMA_VERSION:
        migrate(conn)
    return conn


def table_exists(conn, table_name):
    result = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    ).fetchone()
    return result is not None


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def today_utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')
