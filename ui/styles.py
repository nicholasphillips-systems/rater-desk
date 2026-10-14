"""Shared UI utilities for Rater Desk."""

from PyQt6.QtGui import QFont

STATUS_COLORS = {
    'not_started': '#6B7280',
    'account_made': '#F59E0B',
    'profile_done': '#3B82F6',
    'blocked': '#EF4444',
    'active': '#10B981',
    'paused': '#8B5CF6',
    'dead': '#1F2937',
}

PROJECT_STATUS_COLORS = {
    'applied': '#F59E0B',
    'active': '#10B981',
    'paused': '#8B5CF6',
    'completed': '#06B6D4',
    'rejected': '#EF4444',
}

STATUS_LABELS = {
    'not_started': 'Not Started',
    'account_made': 'Account Made',
    'profile_done': 'Profile Done',
    'blocked': 'Blocked',
    'active': 'Active',
    'paused': 'Paused',
    'dead': 'Dead',
}

SETUP_STATUS_LABELS = {
    'todo': 'To Do',
    'doing': 'Doing',
    'done': 'Done',
    'skipped': 'Skipped',
}


def badge_style(color_hex):
    """Return a style string for a colored badge label."""
    return f"""
        background-color: {color_hex}20;
        color: {color_hex};
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: 600;
    """


# Inter where it is installed, otherwise the native UI font.
FONT_FAMILIES = ["Inter", "Segoe UI", "Helvetica Neue"]


def app_font(size, bold=False):
    f = QFont(FONT_FAMILIES, size)
    f.setBold(bold)
    return f


def header_font(size=14):
    return app_font(size, bold=True)


def body_font(size=11):
    return app_font(size)


APP_STYLE = """
QMainWindow {
    background-color: #1e1e24;
    color: #e2e8f0;
}

QWidget {
    font-family: 'Inter', 'Segoe UI', 'Helvetica Neue', sans-serif;
    color: #e2e8f0;
}

QPushButton {
    background-color: #374151;
    border: 1px solid #4B5563;
    border-radius: 6px;
    padding: 6px 14px;
    color: #e2e8f0;
}

QPushButton:hover {
    background-color: #4B5563;
}

QPushButton:pressed {
    background-color: #1F2937;
}

QPushButton.primary {
    background-color: #3B82F6;
    border: 1px solid #3B82F6;
}

QPushButton.primary:hover {
    background-color: #60A5FA;
}

QPushButton.danger {
    background-color: #EF4444;
    border: 1px solid #EF4444;
}

QPushButton.danger:hover {
    background-color: #F87171;
}

QPushButton.flat {
    background-color: transparent;
    border: none;
    padding: 4px 8px;
}

QPushButton.flat:hover {
    background-color: rgba(255,255,255,0.05);
}

QTableWidget, QTreeWidget {
    background-color: #25262b;
    border: 1px solid #4B5563;
    border-radius: 6px;
    gridline-color: #374151;
}

QListWidget {
    background-color: #25262b;
    border: 1px solid #4B5563;
    border-radius: 6px;
    color: #e2e8f0;
    padding: 4px;
}

QHeaderView::section {
    background-color: #374151;
    color: #9CA3AF;
    border: none;
    padding: 6px 10px;
    font-size: 12px;
    font-weight: 600;
}

QTabBar::tab {
    background-color: #2d2d33;
    border: 1px solid #4B5563;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    color: #9CA3AF;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #1e1e24;
    color: #e2e8f0;
    border-bottom: 2px solid #3B82F6;
}

QTabBar::tab:hover {
    color: #e2e8f0;
}

QLineEdit, QComboBox, QDateEdit {
    background-color: #25262b;
    border: 1px solid #4B5563;
    border-radius: 4px;
    padding: 6px 10px;
    color: #e2e8f0;
}

QComboBox::drop-down {
    border: none;
    background-color: transparent;
}

QPlainTextEdit, QTextEdit {
    background-color: #25262b;
    border: 1px solid #4B5563;
    border-radius: 4px;
    padding: 8px;
    color: #e2e8f0;
}

QDialog {
    background-color: #1e1e24;
}

QDialogButtonBox QPushButton {
    min-width: 80px;
}
"""
