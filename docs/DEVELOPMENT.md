# Development

## Tests

Install the application dependencies using the README, then install pytest in the
same environment. From the repository root on Linux:

```bash
~/.venvs/rater-desk/bin/python -m pip install pytest
QT_QPA_PLATFORM=offscreen ~/.venvs/rater-desk/bin/python -m pytest -q
```

On Windows, in PowerShell:

```powershell
& "$HOME\.venvs\rater-desk\Scripts\python.exe" -m pip install pytest
$env:QT_QPA_PLATFORM = "offscreen"
& "$HOME\.venvs\rater-desk\Scripts\python.exe" -m pytest -q
```

Tests cover SQLite migrations, financial calculations, calendar exports, starter
data, automation rules, email parsing, cross-platform paths, and screen navigation.
The GitHub Actions workflow runs on Linux and Windows with Python 3.12.

Use a separate `RATER_DESK_DATA` folder when running the application with development
data. The test suite uses temporary databases and mocks startup registration.

## Code layout

| Module | Responsibility |
|---|---|
| `main.py` | Application lifecycle, navigation, tray, and background services |
| `ui/` | Today, Platforms, Plan, Money, Reports, Auto, dialogs, and CSV exports |
| `store.py` | Database operations and earnings calculations |
| `schema.sql`, `migrations.py` | Database schema and migrations |
| `starter.py` | Initial platform records and setup tasks |
| `activity.py`, `autotimer.py` | OS activity detection and automatic session rules |
| `catalog.py`, `maildetect.py`, `mailwatch.py` | Platform matching, email classification, and Gmail polling |
| `ics.py` | Calendar export, escaping, stable event IDs, and line folding |
| `paths.py`, `autostart.py`, `backup.py` | File locations, startup registration, and database backups |
| `tests/` | Automated tests |

Money is stored as integer cents. Gmail work runs in a background thread and sends
results to the main thread through Qt signals; SQLite writes use the main thread's
connection.

## Windows builds

On Windows with Python 3.10 or newer:

```powershell
.\build-windows.bat
```

From Linux with Wine, curl, and unzip installed:

```bash
./build-windows.sh
```

The Linux build script downloads Windows Python and build dependencies into a
dedicated cache and Wine prefix at `~/.cache/rater-desk-winbuild`. Both build paths
produce `dist/Rater Desk.exe` using the PyInstaller recipe in `rater-desk.spec`.
Release assets may use the shorter filename `RaterDesk.exe`.

## Contributing

Describe the affected screen or workflow and include reproducible steps for bug
reports. For code changes, explain the resulting behavior, run the relevant tests,
and include regression coverage when changing financial or automation rules.
Use sample data in screenshots and test fixtures.
