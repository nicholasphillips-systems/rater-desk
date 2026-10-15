# Rater Desk

**A desktop time and earnings tracker for AI raters and data annotators.**

Rater Desk helps freelancers track work across multiple AI rating, training, and
annotation platforms. Keep platform accounts and projects organized, log work
hours and payments, and plan your week. Earnings reports show recorded pay per
hour alongside each platform's advertised rate.

Built with **Python, PyQt6, and SQLite** for **Windows and Linux**.

[![Tests](https://github.com/nicholasphillips-systems/rater-desk/actions/workflows/tests.yml/badge.svg)](https://github.com/nicholasphillips-systems/rater-desk/actions/workflows/tests.yml)
[![Release](https://img.shields.io/github/v/release/nicholasphillips-systems/rater-desk)](https://github.com/nicholasphillips-systems/rater-desk/releases/latest)

![Rater Desk's Today screen showing sample work sessions and a weekly schedule](docs/screenshots/today.png)

## Features

- **Platform management:** track account status, application progress, setup tasks,
  project rates, and deadlines across multiple platforms.
- **Time tracking:** start sessions manually or enable automatic tracking based on
  the active browser window. Manual timers take priority over automatic tracking.
- **Earnings and expenses:** record payouts, bonuses, and costs; compare recorded
  base payments per tracked hour with each platform's advertised rate.
- **Weekly planning:** schedule work blocks and export them as an `.ics` calendar file.
- **Reports and exports:** review hours, earnings, expenses, deadlines, and inactive
  platforms. Export payouts, costs, sessions, and scheduled blocks to CSV.
- **Optional Gmail integration:** detect payment notices, account updates, and
  setup reminders from recognized senders. Review detected changes in the app.
- **Local storage and backups:** keep work records in a local SQLite database with
  daily backups. No Rater Desk account or hosted service is required.
- **Desktop integration:** system tray, startup at login, interrupted-session
  recovery, and reminders after 90 minutes of tracking.

Automatic window tracking supports Windows and KDE Plasma. Manual tracking works
on other Linux desktops. Gmail integration and automatic tracking can be enabled
independently.

## Installation

### Windows application

Download `RaterDesk.exe` from the [latest release](https://github.com/nicholasphillips-systems/rater-desk/releases/latest).
The standalone application does not require a Python installation. The executable
is currently unsigned, so Windows may display a publisher warning.

### Run from source

Requires Python 3.10 or newer and a graphical desktop.

```bash
git clone https://github.com/nicholasphillips-systems/rater-desk.git
cd rater-desk
python3 -m venv ~/.venvs/rater-desk
~/.venvs/rater-desk/bin/python -m pip install -r requirements.txt
~/.venvs/rater-desk/bin/python main.py
```

On Windows, use PowerShell after cloning the repository:

```powershell
py -m venv "$HOME\.venvs\rater-desk"
& "$HOME\.venvs\rater-desk\Scripts\python.exe" -m pip install -r requirements.txt
& "$HOME\.venvs\rater-desk\Scripts\python.exe" main.py
```

The Linux launcher, `./run.sh`, uses `~/.venvs/rater-desk`. To add an application-menu
entry, update the `Exec` and `Icon` paths in `rater-desk.desktop` for your checkout.

## Getting started

1. Open **Platforms** to review the starter list, add platforms, and update account
   status and project rates.
2. Use **Today** to start and stop work sessions. Use **Plan** to schedule work blocks.
3. Record payments and expenses in **Money**, then review totals in **Reports**.
4. Enable the automatic timer or connect Gmail from **Auto** if you want those features.

Effective hourly earnings use recorded base payments divided by tracked hours in
the selected period. Bonuses are tracked separately. Payment dates and work dates
may fall in different periods, so this figure reflects the records selected.

See the [user guide](docs/USAGE.md) for automation rules, data locations, and backups.

## Screenshots

| Earnings and expenses | Platform management |
|---|---|
| ![Money screen with sample earnings](docs/screenshots/money.png) | ![Platforms screen with sample platform records](docs/screenshots/platforms.png) |

![Auto screen showing optional tracking and email settings](docs/screenshots/auto.png)

Screenshots use sample data.

## Development

The [development guide](docs/DEVELOPMENT.md) covers the code layout, test commands,
and Windows builds. GitHub Actions runs the test suite on Linux and Windows.

## License

[MIT](LICENSE).
