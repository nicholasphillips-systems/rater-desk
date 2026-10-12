"""Where Rater Desk keeps its files on each OS. No UI imports here."""

import os
import sys
from pathlib import Path

APP_NAME = "Rater Desk"
APP_SLUG = "rater-desk"
DB_FILENAME = "rater-desk.sqlite3"

IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
# True when running as a packaged .exe / app bundle rather than from source.
IS_FROZEN = bool(getattr(sys, "frozen", False))


def app_dir():
    """Folder holding the bundled read-only files (assets)."""
    if IS_FROZEN:
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def data_dir():
    """Folder holding the database and its backups.

    Run from source, data stays beside the code (the original layout). A packaged
    build can be dropped anywhere, so it uses the per-user data folder instead.
    RATER_DESK_DATA overrides both.
    """
    override = os.environ.get("RATER_DESK_DATA")
    if override:
        return Path(override).expanduser()
    if not IS_FROZEN:
        return app_dir() / "data"
    if IS_WINDOWS:
        base = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_NAME
    if IS_MAC:
        return Path.home() / "Library" / "Application Support" / APP_NAME
    base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / APP_SLUG


def db_path():
    return data_dir() / DB_FILENAME


def backup_dir():
    return data_dir() / "backups"
