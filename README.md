# Rater Desk

A PyQt6 desktop app for manually tracking AI rater/trainer platform work — setup steps, timer, earnings, and a weekly plan exported to `.ics` for calendar import.

## Quick start

```bash
python3 -m venv ~/.venvs/rater-desk
~/.venvs/rater-desk/bin/pip install -r requirements.txt
./run.sh
```

To add it to the application menu, set the two paths in `rater-desk.desktop` to
where you cloned the repo.

## Windows

The same code runs on Windows. The person using it needs only one file,
`Rater Desk.exe` — no Python, no install.

Build it from Linux (uses Windows Python under Wine, in its own prefix):

```bash
./build-windows.sh        # -> dist/Rater Desk.exe
```

or on a Windows PC with Python 3.10+: double-click `build-windows.bat`.

What differs on Windows:

- Data lives in `%APPDATA%\Rater Desk\` (database + backups); exports default to Documents.
- Start-at-login is a `Rater Desk` entry under Task Manager → Startup apps.
- The tray icon stays visible; clicking it brings the window back.
- A new install opens with the starter platform list in `starter.py` (the same twelve
  platforms, nobody's account progress).
- The .exe is unsigned, so the first launch shows "Windows protected your PC" —
  **More info → Run anyway**.

## Project layout

```
rater-desk/
├── main.py            # Entry point: QApplication, QMainWindow, tray, crash recovery
├── paths.py           # Where data lives on each OS (source run vs packaged build)
├── autostart.py       # Start at login: XDG autostart file / Windows Run key
├── schema.sql         # SQLite schema v1
├── migrations.py      # Migration runner (creates tables on first open)
├── store.py           # All SQL + money math (integer cents only)
├── starter.py         # Neutral list of the same 12 platforms for a brand-new install
├── ics.py             # Hand-written .ics writer (TZID, stable UIDs, RFC 5545 folding)
├── backup.py          # Daily timestamped backup (keeps 30)
├── run.sh             # Launches with venv Python
├── rater-desk.desktop # Desktop launcher
├── rater-desk.spec    # PyInstaller recipe for the one-file build
├── build-windows.sh   # Builds the Windows .exe from Linux (Wine)
├── build-windows.bat  # Builds the Windows .exe on a Windows PC
├── ui/
│   ├── styles.py      # Dark theme, badge colors
│   ├── today.py       # Today screen (timer, blocks, setup, money)
│   ├── platforms.py   # Platforms list + detail view (tabbed)
│   ├── plan.py        # Week grid with block create/edit + ICS export
│   ├── money.py       # Per-platform rate/net table, quick-add payout/cost
│   ├── reports.py     # Earnings summary, idle platforms, deadlines
│   ├── dialogs.py     # ProjectDialog, PayoutDialog
│   ├── csv_export.py  # CSV export of payouts, costs, sessions, blocks
│   └── files.py       # Default export folder, open-in-file-manager
└── tests/
    ├── test_store_and_ics.py   # store, money math, .ics
    └── test_cross_platform.py  # data paths, starter list, first run, autostart
```

## Database

- Location: `data/rater-desk.sqlite3` beside the code; a packaged build uses the per-user
  data folder instead (see Windows above). `RATER_DESK_DATA=/some/folder` overrides both.
- Schema: `schema.sql` defines all tables; `migrations.py` applies migrations on startup via `store.migrate()`
- A brand-new database is filled from `starter.py`

## Money

All money is stored as integer cents. No floats in storage. Key helpers in `store.py`:

- `cents_to_str(cents)` → "$42.50"
- `str_to_cents("$42.50")` → 4250
- `real_rate(payouts_cents, hours)` → cents/hr excluding base salary/bonuses
- `format_real_rate(earnings_cents, hours)` → "$42.50/hr"
- `hours_between(start, end)` — end can be `None` for "now"

## Calendar export

The **Plan** screen has an "Export .ics" button that writes a `.ics` file with:
- TZID headers
- Stable UIDs per block: `raterdesk-block-<id>@raterdesk`
- RFC 5545 escaping for commas, semicolons, backslashes, newlines
- 75-octet line folding
- CRLF line endings

Import the file into Google Calendar via **File → Import → Import ICS** (using Kontact as the bridge).

## Backup

Daily timestamped backups are written to `data/backups/` (keeps 30). A background thread starts automatically on launch.

## System tray

- Close the window → app minimizes to tray
- Right-click → "Show" / "Quit" (on Windows, left-click also restores)

## Crash recovery

On startup, any work sessions left running (no `ended_at`) trigger a recovery dialog:
- **Yes** → continue the session timer
- **No** → stop the timer at the current time

## Long-session reminders

Every minute while a session is open, the app checks if it's been running 90+ minutes. If so, a tray notification appears (on Linux `notify-send` is attempted as well).

## Tests

```bash
~/.venvs/rater-desk/bin/pip install pytest
QT_QPA_PLATFORM=offscreen ~/.venvs/rater-desk/bin/python -m pytest
```

52 tests cover the schema, the money math, sessions, payouts and costs, the `.ics`
writer, per-OS data paths, the starter list, first run and start-at-login.

This public copy leaves out my own platform list and the 7 tests that cover it.
