"""
modules/daily_history.py
UnoCarshop ASMIS daily snapshot history page.
"""
import json
import os
import sys
from datetime import date

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QHeaderView,
    QTableWidgetItem, QTextEdit, QSplitter
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.daily_archive import (
    get_daily_snapshot,
    list_daily_snapshots,
    store_daily_snapshot,
)
from db.events import bus
from modules.widgets import (
    Card, GhostButton, OrangeButton, StyledTable, error, info,
    PAGE_BG, TEXT_DARK, TEXT_MID, TEXT_SOFT, ORANGE, GREEN, BLUE, RED
)


class DailyHistoryPage(QWidget):
    def __init__(self, user=None):
        super().__init__()
        self.user = user
        self._snapshot_ids = []
        self.setStyleSheet(f"background: {PAGE_BG};")
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Daily Data History")
        title.setStyleSheet(f"font-size:20px;font-weight:700;color:{TEXT_DARK};")
        subtitle = QLabel("Stored end-of-day records for business activity, totals, and detailed data.")
        subtitle.setStyleSheet(f"font-size:12px;color:{TEXT_SOFT};")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()

        btn_refresh = GhostButton("Refresh")
        btn_refresh.clicked.connect(self.refresh)
        btn_store = OrangeButton("Store Today")
        btn_store.clicked.connect(self._store_today)
        header.addWidget(btn_refresh)
        header.addWidget(btn_store)
        layout.addLayout(header)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setStyleSheet("QSplitter::handle{background:#d7dee8;}")

        left = Card()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(10)
        left_title = QLabel("Snapshots")
        left_title.setStyleSheet(f"font-size:14px;font-weight:700;color:{TEXT_DARK};border:none;")
        left_layout.addWidget(left_title)
        self.table = StyledTable(["Date", "Revenue", "Invoices", "Orders", "Attendance", "Updated"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self._load_selected_snapshot)
        left_layout.addWidget(self.table)
        splitter.addWidget(left)

        right = Card()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(14, 14, 14, 14)
        right_layout.setSpacing(12)

        self.detail_title = QLabel("Select a snapshot")
        self.detail_title.setStyleSheet(f"font-size:15px;font-weight:700;color:{TEXT_DARK};border:none;")
        right_layout.addWidget(self.detail_title)

        stats = QHBoxLayout()
        stats.setSpacing(8)
        self.summary_labels = {}
        for key, label, color in [
            ("revenue", "Revenue", GREEN),
            ("billed_total", "Billed", ORANGE),
            ("new_service_orders", "Orders", BLUE),
            ("low_stock_items", "Low Stock", RED),
        ]:
            box = Card()
            box.setFixedHeight(72)
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(12, 8, 12, 8)
            value = QLabel("0")
            value.setStyleSheet(f"font-size:18px;font-weight:700;color:{color};border:none;")
            caption = QLabel(label)
            caption.setStyleSheet(f"font-size:11px;color:{TEXT_SOFT};border:none;")
            box_layout.addWidget(value)
            box_layout.addWidget(caption)
            stats.addWidget(box)
            self.summary_labels[key] = value
        right_layout.addLayout(stats)

        self.summary_text = QLabel("")
        self.summary_text.setWordWrap(True)
        self.summary_text.setStyleSheet(f"font-size:12px;color:{TEXT_MID};border:none;")
        right_layout.addWidget(self.summary_text)

        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setStyleSheet("""
            QTextEdit {
                background: #f8fafc;
                border: 1px solid #d7dee8;
                border-radius: 8px;
                padding: 10px;
                font-family: Consolas, monospace;
                font-size: 12px;
                color: #101820;
            }
        """)
        right_layout.addWidget(self.details, 1)
        splitter.addWidget(right)
        splitter.setSizes([520, 700])
        layout.addWidget(splitter, 1)

    def refresh(self):
        try:
            rows = list_daily_snapshots()
            self._snapshot_ids = []
            self.table.setSortingEnabled(False)
            self.table.setRowCount(0)
            for row in rows:
                snapshot_id, snapshot_date, summary, generated_at, updated_at = row
                self._snapshot_ids.append(snapshot_id)
                r = self.table.rowCount()
                self.table.insertRow(r)
                self.table.setRowHeight(r, 38)
                attendance = summary.get("attendance", {}) if summary else {}
                present = attendance.get("Present", 0)
                total_attendance = sum(attendance.values()) if attendance else 0
                values = [
                    snapshot_date,
                    f"PHP {float(summary.get('revenue', 0)):,.2f}" if summary else "PHP 0.00",
                    summary.get("invoices", 0) if summary else 0,
                    summary.get("new_service_orders", 0) if summary else 0,
                    f"{present}/{total_attendance}",
                    updated_at.strftime("%Y-%m-%d %H:%M") if updated_at else "",
                ]
                for c, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    item.setTextAlignment((Qt.AlignRight if c in (1, 2, 3) else Qt.AlignLeft) | Qt.AlignVCenter)
                    self.table.setItem(r, c, item)
            self.table.setSortingEnabled(True)
            if rows:
                self.table.selectRow(0)
            else:
                self.detail_title.setText("No snapshots stored yet")
                self.details.clear()
        except Exception as exc:
            error(self, "Daily History Error", str(exc))

    def _store_today(self):
        try:
            user_id = self.user[0] if self.user else None
            store_daily_snapshot(date.today(), user_id)
            info(self, "Stored", "Today's data snapshot has been stored.")
            bus.publish("dashboard")
            self.refresh()
        except Exception as exc:
            error(self, "Store Failed", str(exc))

    def _load_selected_snapshot(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._snapshot_ids):
            return
        try:
            snapshot = get_daily_snapshot(self._snapshot_ids[row])
            if not snapshot:
                return
            _, snapshot_date, summary, details, generated_at, updated_at = snapshot
            self.detail_title.setText(f"Snapshot for {snapshot_date}")
            for key, label in self.summary_labels.items():
                value = summary.get(key, 0) if summary else 0
                if key in ("revenue", "billed_total"):
                    label.setText(f"PHP {float(value):,.2f}")
                else:
                    label.setText(str(value))

            attendance = summary.get("attendance", {}) if summary else {}
            summary_parts = [
                f"Generated: {generated_at:%Y-%m-%d %H:%M}" if generated_at else "",
                f"Updated: {updated_at:%Y-%m-%d %H:%M}" if updated_at else "",
                f"Customers: {summary.get('total_customers', 0)} total, {summary.get('new_customers', 0)} new",
                f"Vehicles: {summary.get('total_vehicles', 0)} total, {summary.get('new_vehicles', 0)} new",
                f"Attendance: {', '.join(f'{k} {v}' for k, v in attendance.items()) or 'No records'}",
                f"Outstanding balance: PHP {float(summary.get('outstanding_balance', 0)):,.2f}",
            ]
            self.summary_text.setText(" | ".join(part for part in summary_parts if part))
            self.details.setPlainText(json.dumps(details or {}, indent=2, sort_keys=True, default=str))
        except Exception as exc:
            error(self, "Load Snapshot Failed", str(exc))

