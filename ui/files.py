"""Where exports are saved, and opening a folder in the OS file manager."""

import os

from PyQt6.QtCore import QStandardPaths, QUrl
from PyQt6.QtGui import QDesktopServices

import paths


def export_dir():
    """Default folder for .ics / .csv exports.

    From source it is the data folder (the original behaviour). A packaged build
    keeps its data in a hidden per-user folder, so exports go to Documents.
    """
    if not paths.IS_FROZEN:
        return str(paths.data_dir())
    docs = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DocumentsLocation
    )
    return docs or os.path.expanduser("~")


def export_path(filename):
    return os.path.join(export_dir(), filename)


def open_folder(folder):
    os.makedirs(folder, exist_ok=True)
    QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
