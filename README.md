<p align="center">
  <img src="assets/icon.svg" width="88" alt="">
</p>

<h1 align="center">Rater Desk</h1>

<p align="center">
  A desktop app for AI rating and training work spread across several platforms.<br>
  It tracks each platform's setup steps, times your sessions, records payouts,<br>
  and shows what every platform really pays per hour.
</p>

<p align="center">
  <a href="https://github.com/nicholasphillips-systems/rater-desk/actions/workflows/tests.yml"><img src="https://github.com/nicholasphillips-systems/rater-desk/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <a href="https://github.com/nicholasphillips-systems/rater-desk/releases/latest"><img src="https://img.shields.io/github/v/release/nicholasphillips-systems/rater-desk" alt="Latest release"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-3776AB" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux-555" alt="Windows and Linux">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-2ea44f" alt="MIT license"></a>
</p>

![Money screen: each platform's advertised rate next to the real hourly rate earned](docs/screenshots/money.png)

## Features

- **Real hourly pay.** Puts each platform's advertised rate next to what you actually earned per hour worked, and flags the gap.
- **Session timer.** Start and stop it by hand, or let auto mode run it from the browser tab you're working in.
- **Email updates.** Reads platform and PayPal / Payoneer mail (read-only) and turns it into payouts, status changes and setup tasks.
- **Setup tracking.** Every platform's sign-up steps, with the ones only you can do (ID checks, video interviews) marked.
- **Weekly plan.** Block out work time and export the week to any calendar as an `.ics` file.
- **Local and private.** Everything lives in one SQLite file on your own machine, backed up daily.

## Download

**Windows:** download `RaterDesk.exe` from the [latest release](https://github.com/nicholasphillips-systems/rater-desk/releases/latest) and run it. Nothing to install, no Python needed. The file isn't code-signed, so the first launch shows "Windows protected your PC": choose **More info**, then **Run anyway**.

**Linux:** run it from source (below).

## Screenshots

| Today | Platforms |
|---|---|
| ![Today: a session being timed automatically, today's planned blocks and setup tasks due](docs/screenshots/today.png) | ![Platforms: every platform's status, with Outlier's details open](docs/screenshots/platforms.png) |

![Auto mode: what it found in platform and payment email, and what it changed](docs/screenshots/auto.png)

<sub>Screenshots use sample data.</sub>

## Run from source

Needs Python 3.10 or newer.

```bash
git clone https://github.com/nicholasphillips-systems/rater-desk.git
cd rater-desk
python3 -m venv ~/.venvs/rater-desk
~/.venvs/rater-desk/bin/pip install -r requirements.txt
./run.sh
```

To add it to the application menu, set the two paths in `rater-desk.desktop` to where you cloned the repo.

## Auto mode

The **Auto** screen turns on two things. Each works without the other.

**Auto timer.** Starts and stops the timer from the browser tab you're in, with no
button presses:

- A platform's site in front for 45 s starts its timer, back-dated to when you opened it.
- Leaving every platform tab for 5 min stops it at the moment you left. A quick look
  at notes in between doesn't break the session.
- Switching to another platform's tab moves the timer over.
- 15 min without mouse input, or locking the screen, stops it at your last input.
- A timer you start by hand always wins, and pressing Stop on an auto session keeps
  it stopped until you leave that platform and come back.
- Sessions under 2 min are dropped. The Sessions tab shows who started each one.

Only browser windows count, matched on words in the tab title (`catalog.py`; each
platform's **Auto** tab can override them). On KDE Plasma a small KWin script
(`activity.py`) reports the focused window and mouse movement to the app over
D-Bus, since Wayland gives apps no other view of other windows. On Windows the
app polls the foreground window and `GetLastInputInfo`. Other desktops show
"unavailable". KWin reports mouse movement but not key presses, so typing for
15 min without touching the mouse counts as idle.

**Email.** Reads only mail from the platforms and from PayPal / Payoneer, every 10 min
(read-only, so nothing gets marked read). Add a Gmail account with an
[app password](https://myaccount.google.com/apppasswords), which needs 2-Step
Verification. The password goes into the system keyring. Several accounts can be watched.

| Email says | What changes |
|---|---|
| Payment from a platform (PayPal / Payoneer / the platform) | Payout added |
| Account created, sign-in code, welcome | Status raised to Account Made |
| Accepted / approved / congratulations | Status raised to Active |
| "Verify your phone", "finish your application" (last 14 days) | Setup task added |
| "Phone verified", later sign-ins | Matching task marked done |
| Mail from a known platform not in your list | Platform added |
| Rejection, project invite, payment from an unknown payer | Logged only |

Statuses only move forward, and Blocked / Paused / Dead are never touched. Every
change is listed under *What auto mode found*. The rules live in `maildetect.py`, and
`tests/test_auto_mode.py` checks them against real subjects from the platforms.

## How it works

- **Storage.** One SQLite database: `data/rater-desk.sqlite3` beside the code, or the per-user data folder in the Windows build. `RATER_DESK_DATA=/some/folder` overrides both. `schema.sql` defines the tables and `migrations.py` upgrades older databases on startup.
- **Money.** Stored as integer cents, never floats. Real hourly pay counts base pay only, not bonuses.
- **Calendar export.** A hand-written `.ics` writer: TZID headers, stable UIDs per block, RFC 5545 escaping, 75-octet line folding and CRLF line endings.
- **Backups.** A timestamped copy of the database every day in `data/backups/`, keeping the last 30.
- **System tray.** Closing the window keeps it running in the tray. It can start at login.
- **Crash recovery.** A session still running when the app last closed is offered back on the next launch: keep timing it, or stop it at that moment.
- **Long sessions.** After 90 minutes on one session, a tray notification suggests a break.
- **First run.** A new database starts with a neutral list of twelve platforms (`starter.py`), with no one's account progress in it.

## Development

### Tests

```bash
~/.venvs/rater-desk/bin/pip install pytest
QT_QPA_PLATFORM=offscreen ~/.venvs/rater-desk/bin/python -m pytest
```

85 tests cover the schema, money math, sessions, payouts and costs, the `.ics` writer, per-OS data paths, the starter list, first run, start-at-login, the auto timer's rules, email detection, and opening every screen. They run on Linux and Windows on every push.

This public copy leaves out my own platform list and the 7 tests that cover it.

### Windows build

From Linux, using Windows Python under Wine in its own prefix:

```bash
./build-windows.sh        # -> dist/Rater Desk.exe
```

Or on a Windows PC with Python 3.10+, double-click `build-windows.bat`. The Windows build keeps its data in `%APPDATA%\Rater Desk\`, saves exports to Documents, and registers start-at-login under Task Manager's Startup apps.

### Project layout

<details>
<summary>Files</summary>

```
rater-desk/
├── main.py            # Entry point: QApplication, QMainWindow, tray, crash recovery
├── paths.py           # Where data lives on each OS (source run vs packaged build)
├── autostart.py       # Start at login: XDG autostart file / Windows Run key
├── schema.sql         # SQLite schema (version 2)
├── migrations.py      # Migration runner (creates tables on first open)
├── store.py           # All SQL + money math (integer cents only)
├── starter.py         # Neutral list of the same 12 platforms for a brand-new install
├── ics.py             # Hand-written .ics writer (TZID, stable UIDs, RFC 5545 folding)
├── backup.py          # Daily timestamped backup (keeps 30)
├── catalog.py         # How each platform is recognised: tab-title words, email domains, payer names
├── activity.py        # Focused window + input: KWin script over D-Bus / Windows API polling
├── autotimer.py       # Auto timer rules (start, stop, switch, idle, lock)
├── maildetect.py      # What a platform/payment email means, and applying it
├── mailwatch.py       # Gmail over IMAP (app password in the keyring), background thread
├── run.sh             # Launches with the venv in ~/.venvs/rater-desk
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
│   ├── auto.py        # Auto screen: auto timer switch, Gmail accounts, detection log
│   ├── dialogs.py     # ProjectDialog, PayoutDialog
│   ├── csv_export.py  # CSV export of payouts, costs, sessions, blocks
│   └── files.py       # Default export folder, open-in-file-manager
└── tests/
    ├── test_store_and_ics.py   # store, money math, .ics
    ├── test_auto_mode.py       # window matching, auto timer rules, email detection
    ├── test_store_calls.py     # every Store method the screens call exists
    ├── test_screens.py         # opens every screen, platform and tab offscreen
    └── test_cross_platform.py  # data paths, starter list, first run, autostart
```

</details>

## License

MIT. See [LICENSE](LICENSE).
