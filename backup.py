"""Backup: nightly timestamped backup (keep 30), restore from file dialog."""

import os
import shutil
from pathlib import Path
from datetime import datetime
import threading
import time

import paths

DB_PATH = paths.db_path()
BACKUP_DIR = paths.backup_dir()
MAX_BACKUPS = 30


def backup_db():
    """Copy the database to a timestamped file in BACKUP_DIR."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_path = BACKUP_DIR / f"rater-desk-{timestamp}.db"
    try:
        shutil.copy2(str(DB_PATH), str(backup_path))
        _cleanup_old_backups()
        return str(backup_path)
    except Exception as e:
        print(f"Backup failed: {e}")
        return None


def _cleanup_old_backups():
    """Remove oldest backups beyond MAX_BACKUPS."""
    backups = sorted(BACKUP_DIR.glob("rater-desk-*.db"), key=os.path.getmtime)
    while len(backups) > MAX_BACKUPS:
        oldest = backups.pop(0)
        try:
            oldest.unlink()
        except OSError:
            pass


def restore_from_file(file_path):
    """Replace the live database with the given backup file."""
    if not os.path.exists(file_path):
        return False
    backup_path = str(DB_PATH) + ".bak"
    try:
        if os.path.exists(backup_path):
            os.unlink(backup_path)
        shutil.copy2(file_path, str(DB_PATH))
        return True
    except Exception as e:
        print(f"Restore failed: {e}")
        return False


def schedule_daily_backup():
    """Run backup every 24 hours in a background thread."""
    while True:
        backup_db()
        time.sleep(86400)


def start_backup_thread():
    t = threading.Thread(target=schedule_daily_backup, daemon=True)
    t.start()
    return t
