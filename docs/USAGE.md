# User guide

## Automatic time tracking

Enable the automatic timer on the **Auto** screen. It matches the active browser
window's title against platform keywords. Customize those keywords on a platform's
**Auto** tab.

- Tracking starts after a recognized platform remains active for 45 seconds,
  with the session start recorded from the beginning of that interval.
- Leaving all recognized platform windows for five minutes ends the session at
  the time you left. Short visits to other applications do not split the session.
- Switching to another recognized platform for 45 seconds switches the timer.
- Fifteen minutes of inactivity or a screen lock ends the session at the last
  detected input.
- A manually started timer takes priority. Manually stopping an automatic session
  prevents it from restarting until you leave that platform and return.
- Automatic sessions shorter than two minutes are discarded.

Window detection supports Windows and KDE Plasma on Linux. On KDE, the activity
monitor detects mouse movement but does not detect keystrokes; extended typing
without mouse movement can therefore be counted as idle. Other Linux desktops
can use manual tracking. Recognition uses window titles rather than browser URLs,
so results depend on the titles and keywords in use.

## Gmail integration

Add a Gmail account on **Auto** using an app password. A working operating-system
keyring is required to store credentials. Multiple accounts can be connected.
The Gmail account must support app passwords.

The app searches for messages from the platform and payment-provider domains
defined in `catalog.py`, including PayPal and Payoneer. It checks every ten minutes,
with a 60-day lookback on the first check. The mailbox is opened read-only, and
fetching messages does not mark them as read.

| Recognized message | Action |
|---|---|
| Payment notice associated with a known platform | Add a payout |
| Account creation or welcome message | Advance the account status |
| Acceptance or approval message | Advance the platform to Active |
| Recent request to complete a setup step | Add a setup task |
| Confirmation that a tracked step is complete | Mark the matching task complete |
| Message from a recognized platform not yet tracked | Add the platform |
| Rejection, project invitation, or payment from an unknown payer | Log for review |

Detection uses sender and message-matching rules. Review the results under
**What auto mode found**, particularly payment amounts and status changes.
Statuses only advance; platforms marked Blocked, Paused, or Dead retain their status.

The app connects directly to Gmail over IMAP when this feature is configured.
Account addresses and detection records are stored in the local database; app
passwords are stored separately in the system keyring.

## Data and backups

| How the app is run | Default data folder |
|---|---|
| From source | `data/` inside the checkout |
| Packaged Windows executable | `%APPDATA%\Rater Desk\` |
| Packaged Linux application | `$XDG_DATA_HOME/rater-desk/`, or `~/.local/share/rater-desk/` |

Set `RATER_DESK_DATA` to override the data folder. The database is named
`rater-desk.sqlite3`. New databases start with twelve platform records and setup
tasks from `starter.py`. Platform rates and requirements can change; edit the
records to reflect your own accounts and projects.

Daily timestamped database backups are saved in a `backups/` subfolder, retaining
the most recent 30. Close the app before restoring a database backup. Backups
include the work records in SQLite, but do not include passwords from the keyring.

## Calendar and CSV export

Use **Plan → Export .ics** to save scheduled work blocks, then import the file
through your calendar application's import function. This is a file export rather
than ongoing calendar synchronization.

CSV export is available for payouts, expenses, work sessions, and scheduled blocks.

## Startup and the system tray

Closing the window leaves Rater Desk running in the system tray. Use the tray's
**Show** action to reopen it or **Quit** to exit.

The app registers startup at login on its first launch: an XDG autostart entry on
Linux or a Windows Run-key entry. Remove or disable that entry using your desktop's
startup settings if you prefer to launch it manually.

If a manual session was left running when the app exited, the next launch asks
whether to continue it or stop it at the current time. Automatic sessions are
recovered using the last saved activity time. Long-session notifications appear
after 90 minutes of tracking.
