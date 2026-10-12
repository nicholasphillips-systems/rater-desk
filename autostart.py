"""Start Rater Desk at login: an XDG autostart file on Linux, the Run key on Windows.

No UI imports here.
"""

import os
import subprocess
import sys
from pathlib import Path

import paths

AUTOSTART_DIR = Path.home() / ".config" / "autostart"
AUTOSTART_FILE = AUTOSTART_DIR / "rater-desk.desktop"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def launch_command():
    """The command that starts the app hidden in the tray, as an argument list."""
    if paths.IS_FROZEN:
        return [sys.executable, "--start-minimized"]
    python = sys.executable
    if paths.IS_WINDOWS:
        # pythonw starts without flashing a console window at login
        pythonw = Path(python).with_name("pythonw.exe")
        if pythonw.exists():
            python = str(pythonw)
    return [python, str(paths.app_dir() / "main.py"), "--start-minimized"]


def ensure(already_registered):
    """Register the app to start at login the first time it runs.

    Returns True if a login entry exists afterwards. Once it has been registered,
    a missing entry means the user removed it, so it is left removed.
    """
    if paths.IS_WINDOWS:
        return _ensure_windows(already_registered)
    if paths.IS_LINUX:
        return _ensure_linux(already_registered)
    return False


def _ensure_linux(already_registered):
    if AUTOSTART_FILE.exists():
        return True
    if already_registered:
        return False

    icon = paths.app_dir() / "assets" / "icon.svg"
    AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
    AUTOSTART_FILE.write_text(f"""[Desktop Entry]
Type=Application
Name={paths.APP_NAME}
Exec={" ".join(launch_command())}
Icon={icon if icon.exists() else ""}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
""")
    return True


def _ensure_windows(already_registered):
    import winreg

    command = subprocess.list2cmdline(launch_command())
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                        winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
        try:
            current, _ = winreg.QueryValueEx(key, paths.APP_NAME)
        except FileNotFoundError:
            current = None

        if current is None and already_registered:
            return False
        # A packaged .exe gets moved around (Downloads -> Desktop); keep the entry
        # pointing at wherever it runs from now.
        if current is None or (paths.IS_FROZEN and current != command):
            winreg.SetValueEx(key, paths.APP_NAME, 0, winreg.REG_SZ, command)
    return True
