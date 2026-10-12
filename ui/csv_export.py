"""CSV export for payouts, costs, and sessions — a safety net for data portability."""

import csv
from datetime import datetime

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from ui.files import export_path


def export_csv_dialog(parent, store):
    """Prompt user for save location and write all three tables to one CSV."""
    default_name = f"rater-desk-export-{datetime.now().strftime('%Y-%m-%d')}.csv"
    file_path, _ = QFileDialog.getSaveFileName(
        parent,
        "Save CSV export",
        export_path(default_name),
        "CSV files (*.csv)",
    )
    if not file_path:
        return

    try:
        _write_csv(file_path, store)
        QMessageBox.information(parent, "Export complete",
                                f"Exported to:\n{file_path}")
    except Exception as e:
        QMessageBox.critical(parent, "Export failed", str(e))


def _write_csv(file_path, store):
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Payouts
        writer.writerow([])
        writer.writerow(["PAYOUTS"])
        writer.writerow(["id", "platform", "received_on", "amount_cents",
                         "kind", "method", "period_start", "period_end", "note"])
        payouts = store.get_payouts(limit=10000)
        for p in payouts:
            plat = store.get_platform(p['platform_id']) if p['platform_id'] else None
            writer.writerow([
                p['id'],
                plat['name'] if plat else "",
                p['received_on'],
                p['amount_cents'],
                p['kind'],
                p['method'] or "",
                p['period_start'] or "",
                p['period_end'] or "",
                p['note'] or "",
            ])

        # Costs
        writer.writerow([])
        writer.writerow(["COSTS"])
        writer.writerow(["id", "label", "amount_cents", "incurred_on",
                         "recurring", "note"])
        for c in store.get_costs():
            writer.writerow([
                c['id'], c['label'], c['amount_cents'],
                c['incurred_on'] or "", c['recurring'], c['note'] or "",
            ])

        # Sessions
        writer.writerow([])
        writer.writerow(["SESSIONS"])
        writer.writerow(["id", "platform", "project", "started_at", "ended_at",
                         "rate_cents_per_hour", "item_count", "note"])
        sessions = store.conn.execute(
            "SELECT * FROM work_sessions ORDER BY started_at"
        ).fetchall()
        for s in sessions:
            plat = store.get_platform(s['platform_id']) if s['platform_id'] else None
            proj = store.get_project(s['project_id']) if s['project_id'] else None
            writer.writerow([
                s['id'],
                plat['name'] if plat else "",
                proj['name'] if proj else "",
                s['started_at'] or "",
                s['ended_at'] or "",
                s['rate_cents_per_hour'],
                s['item_count'] or "",
                s['note'] or "",
            ])

        # Blocks
        writer.writerow([])
        writer.writerow(["BLOCKS"])
        writer.writerow(["id", "platform", "project", "starts_at", "ends_at",
                         "title", "calendar_uid", "recurring_rule"])
        blocks = store.conn.execute(
            "SELECT * FROM blocks ORDER BY starts_at"
        ).fetchall()
        for b in blocks:
            plat = store.get_platform(b['platform_id']) if b['platform_id'] else None
            proj = store.get_project(b['project_id']) if b['project_id'] else None
            writer.writerow([
                b['id'],
                plat['name'] if plat else "",
                proj['name'] if proj else "",
                b['starts_at'],
                b['ends_at'],
                b['title'],
                b['calendar_uid'] or "",
                b['recurring_rule'] or "",
            ])
