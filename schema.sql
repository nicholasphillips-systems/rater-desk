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
