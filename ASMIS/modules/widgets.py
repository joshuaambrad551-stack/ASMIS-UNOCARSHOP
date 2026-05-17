"""
modules/widgets.py
Reusable UI components for UnoCarshop ASMIS
"""
import re
import sys

from PyQt5.QtWidgets import (
    QPushButton, QLabel, QFrame, QLineEdit,
    QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QHBoxLayout, QVBoxLayout, QWidget,
    QMessageBox, QDialog, QFormLayout, QDialogButtonBox,
    QTextEdit, QDateEdit, QSpinBox, QDoubleSpinBox,
    QAbstractItemView, QSizePolicy
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor, QFont


# ── Color palette ──────────────────────────────────────────
ORANGE   = "#f5a623"
DARK_BG  = "#1c1c1a"
CARD_BG  = "#ffffff"
PAGE_BG  = "#f5f4f0"
BORDER   = "#e0ddd5"
TEXT_DARK= "#1a1a18"
TEXT_MID = "#555450"
TEXT_SOFT= "#888780"
RED      = "#d9534f"
GREEN    = "#2ecc71"
BLUE     = "#3498db"
YELLOW   = "#f5a623"


# ── Buttons ────────────────────────────────────────────────
class OrangeButton(QPushButton):
    def __init__(self, text, icon=""):
        super().__init__(f"{icon}  {text}" if icon else text)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(36)
        self.setStyleSheet(f"""
            QPushButton {{
                background: {ORANGE}; color: white;
                border: none; border-radius: 7px;
                font-size: 13px; font-weight: 600;
                padding: 0 18px;
            }}
            QPushButton:hover {{ background: #e08e0b; }}
            QPushButton:pressed {{ background: #c97d0a; }}
        """)


class GhostButton(QPushButton):
    def __init__(self, text, icon=""):
        super().__init__(f"{icon}  {text}" if icon else text)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(36)
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_MID};
                border: 1px solid {BORDER}; border-radius: 7px;
                font-size: 13px; padding: 0 14px;
            }}
            QPushButton:hover {{
                background: {BORDER}; color: {TEXT_DARK};
            }}
        """)


class DangerButton(QPushButton):
    def __init__(self, text, icon=""):
        super().__init__(f"{icon}  {text}" if icon else text)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(36)
        self.setStyleSheet(f"""
            QPushButton {{
                background: {RED}; color: white;
                border: none; border-radius: 7px;
                font-size: 13px; font-weight: 600;
                padding: 0 14px;
            }}
            QPushButton:hover {{ background: #c0392b; }}
        """)


# ── Cards ──────────────────────────────────────────────────
class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {CARD_BG};
                border-radius: 10px;
                border: 1px solid {BORDER};
            }}
        """)


class StatCard(Card):
    """KPI summary card with title, value, icon and color bar."""
    def __init__(self, title, value, icon, color=ORANGE, parent=None):
        super().__init__(parent)
        self.setFixedHeight(100)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)

        icon_lbl = QLabel(icon)
        icon_lbl.setFixedSize(46, 46)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(f"""
            background: {color}22; border-radius: 10px;
            font-size: 22px; border: none;
        """)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        self.val_lbl = QLabel(str(value))
        self.val_lbl.setStyleSheet(
            f"font-size: 24px; font-weight: 700; color: {TEXT_DARK}; border: none;"
        )

        ttl_lbl = QLabel(title)
        ttl_lbl.setStyleSheet(
            f"font-size: 11px; color: {TEXT_SOFT}; border: none; font-weight: 500;"
        )

        text_layout.addWidget(self.val_lbl)
        text_layout.addWidget(ttl_lbl)

        layout.addWidget(icon_lbl)
        layout.addSpacing(10)
        layout.addLayout(text_layout)
        layout.addStretch()

        # Left color bar
        bar = QFrame(self)
        bar.setFixedWidth(4)
        bar.setStyleSheet(f"background: {color}; border-radius: 2px; border: none;")
        bar.setGeometry(0, 12, 4, 76)

    def set_value(self, v):
        self.val_lbl.setText(str(v))


# ── Search Bar ─────────────────────────────────────────────
class SearchBar(QLineEdit):
    def __init__(self, placeholder="Search…"):
        super().__init__()
        self.setPlaceholderText(placeholder)
        self.setFixedHeight(38)
        self.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {BORDER}; border-radius: 8px;
                padding: 0 12px 0 34px;
                font-size: 13px; color: {TEXT_DARK};
                background: white url("") no-repeat left 10px center;
            }}
            QLineEdit:focus {{ border: 1px solid #aaa; }}
        """)


# ── Styled Table ───────────────────────────────────────────
class StyledTable(QTableWidget):
    def __init__(self, columns: list):
        super().__init__()
        self.setColumnCount(len(columns))
        self.setHorizontalHeaderLabels(columns)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.setShowGrid(False)
        self.setFocusPolicy(Qt.NoFocus)
        self.setSortingEnabled(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.setStyleSheet(f"""
            QTableWidget {{
                background: white; border: none;
                alternate-background-color: #f9f8f6;
                font-size: 13px; color: {TEXT_DARK};
                selection-background-color: #fff4e0;
                selection-color: {TEXT_DARK};
                outline: none;
            }}
            QHeaderView::section {{
                background: #f5f4f0; color: {TEXT_SOFT};
                font-size: 11px; font-weight: 600;
                padding: 8px 10px; border: none;
                border-bottom: 1px solid {BORDER};
                letter-spacing: 0.5px;
            }}
            QTableWidget::item {{
                padding: 8px 10px;
                border-bottom: 1px solid #f0ede8;
            }}
            QTableWidget::item:selected {{
                background: #fff4e0;
            }}
            QScrollBar:vertical {{
                width: 6px; background: transparent;
            }}
            QScrollBar::handle:vertical {{
                background: #ccc; border-radius: 3px;
            }}
        """)
        self.setRowHeight(0, 42)

    def populate(self, rows: list, col_align: dict = None):
        """Fill table from list of tuples/lists."""
        self.setSortingEnabled(False)
        self.setRowCount(0)
        for row_data in rows:
            r = self.rowCount()
            self.insertRow(r)
            self.setRowHeight(r, 38)
            for c, val in enumerate(row_data):
                item = QTableWidgetItem(str(val) if val is not None else "")
                if col_align and c in col_align:
                    item.setTextAlignment(col_align[c] | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.setItem(r, c, item)
        self.setSortingEnabled(True)

    def selected_row_data(self):
        row = self.currentRow()
        if row < 0:
            return None
        return [self.item(row, c).text() if self.item(row, c) else ""
                for c in range(self.columnCount())]


# ── Status Badge ───────────────────────────────────────────
STATUS_COLORS = {
    "Active":      ("#e8f5e9", "#2e7d32"),
    "Inactive":    ("#f5f5f5", "#757575"),
    "Pending":     ("#fff3e0", "#e65100"),
    "In Progress": ("#e3f2fd", "#1565c0"),
    "Completed":   ("#e8f5e9", "#2e7d32"),
    "Cancelled":   ("#ffebee", "#c62828"),
    "Present":     ("#e8f5e9", "#2e7d32"),
    "Absent":      ("#ffebee", "#c62828"),
    "Late":        ("#fff3e0", "#e65100"),
    "On Leave":    ("#e3f2fd", "#1565c0"),
    "Half Day":    ("#f3e5f5", "#6a1b9a"),
    "Unpaid":      ("#ffebee", "#c62828"),
    "Partial":     ("#fff3e0", "#e65100"),
    "Paid":        ("#e8f5e9", "#2e7d32"),
    "Open":        ("#e3f2fd", "#1565c0"),
    "Closed":      ("#f5f5f5", "#757575"),
    "Draft":       ("#f5f5f5", "#757575"),
    "Approved":    ("#e8f5e9", "#2e7d32"),
    "Expired":     ("#ffebee", "#c62828"),
    "Resigned":    ("#f5f5f5", "#757575"),
    "Terminated":  ("#ffebee", "#c62828"),
}


def status_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(f"  {text}  ")
    colors = STATUS_COLORS.get(text, ("#f5f5f5", "#333"))
    item.setBackground(QColor(colors[0]))
    item.setForeground(QColor(colors[1]))
    item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
    return item


# ── Section Header ─────────────────────────────────────────
def section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"font-size: 13px; font-weight: 700; color: {TEXT_SOFT}; "
        "letter-spacing: 0.5px; padding: 10px 0 4px;"
    )
    return lbl


# ── Confirm Dialog ─────────────────────────────────────────
def confirm(parent, title, msg) -> bool:
    dlg = QMessageBox(parent)
    dlg.setWindowTitle(title)
    dlg.setText(msg)
    dlg.setIcon(QMessageBox.Question)
    dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    dlg.setDefaultButton(QMessageBox.No)
    return dlg.exec_() == QMessageBox.Yes


def info(parent, title, msg):
    QMessageBox.information(parent, title, msg)


def _clean_db_name(raw_name):
    cleaned = raw_name.strip('"').replace("_", " ")
    return cleaned if cleaned else "record"


def user_friendly_error(title, msg):
    """
    Convert database/technical exceptions into text that can be shown to users.
    The original exception should still be logged by callers or the error helper.
    """
    raw = str(msg or "").strip()
    normalized = raw.lower()

    if not raw:
        return "Something went wrong. Please try again."

    # Keep already-friendly validation messages unchanged.
    friendly_starts = (
        "please ",
        "only ",
        "select ",
        "enter ",
        "no ",
        "cannot ",
        "this ",
    )
    sql_markers = (
        "select ",
        "insert ",
        "update ",
        "delete ",
        "where ",
        "violates",
        "psycopg2",
        "syntax error",
        "relation ",
        "column ",
        "constraint",
        "foreign key",
        "duplicate key",
        "null value",
        "invalid input",
        "could not connect",
        "connection refused",
        "server closed",
        "database ",
        "operator does not exist",
        "current transaction",
        "traceback",
    )
    if normalized.startswith(friendly_starts) and not any(marker in normalized for marker in sql_markers):
        return raw

    if any(text in normalized for text in (
        "could not connect",
        "connection refused",
        "connection timed out",
        "server closed the connection",
        "no route to host",
        "temporary failure in name resolution",
    )):
        return (
            "The system cannot connect to the database right now. "
            "Please check that the database is running, then try again."
        )

    if "password authentication failed" in normalized or "authentication failed" in normalized:
        return (
            "The system could not sign in to the database. "
            "Please check the database username and password settings."
        )

    if "permission denied" in normalized:
        return (
            "The system does not have permission to complete this action. "
            "Please contact an administrator."
        )

    duplicate_match = re.search(r"key \(([^)]+)\)=\(([^)]+)\) already exists", raw, re.IGNORECASE)
    if "duplicate key" in normalized or "unique constraint" in normalized:
        if duplicate_match:
            field = _clean_db_name(duplicate_match.group(1))
            value = duplicate_match.group(2)
            return f"A record with the same {field} ({value}) already exists. Please use a different value."
        return "This record already exists. Please use a different code, name, or number."

    if "foreign key constraint" in normalized or "is still referenced" in normalized:
        if "delete" in normalized:
            return (
                "This record is still being used in another part of the system, "
                "so it cannot be deleted yet."
            )
        return (
            "This record is linked to missing or unavailable data. "
            "Please refresh the page and select the related record again."
        )

    if "not-null constraint" in normalized or "null value" in normalized:
        column_match = re.search(r'column "([^"]+)"', raw, re.IGNORECASE)
        if column_match:
            field = _clean_db_name(column_match.group(1))
            return f"Please fill in the required {field} field before saving."
        return "Please complete all required fields before saving."

    if "check constraint" in normalized:
        return "One of the entered values is not allowed. Please review the form and try again."

    if "invalid input syntax" in normalized or "invalid literal" in normalized:
        return "One of the entered values has an invalid format. Please check the form and try again."

    if (
        "relation " in normalized and "does not exist" in normalized
        or "column " in normalized and "does not exist" in normalized
        or "undefinedtable" in normalized
        or "undefinedcolumn" in normalized
    ):
        return (
            "Some required database tables or fields are missing. "
            "Please run the database setup or migration, then try again."
        )

    if "syntax error" in normalized or "operator does not exist" in normalized or "current transaction is aborted" in normalized:
        return (
            "The system could not complete the database request. "
            "Please try again or contact an administrator if it keeps happening."
        )

    if "deadlock detected" in normalized or "could not obtain lock" in normalized:
        return "The record is busy right now. Please wait a moment, then try again."

    context = (title or "").lower()
    if "load" in context or "history" in context:
        return "The system could not load the information. Please refresh the page and try again."
    if "save" in context or "store" in context or "generate" in context or "create" in context:
        return "The system could not save the information. Please review the form and try again."
    if "update" in context:
        return "The system could not update the record. Please review the form and try again."
    if "delete" in context or "remove" in context:
        return "The system could not delete the record. Please refresh the page and try again."

    return "Something went wrong while processing your request. Please try again."


def error(parent, title, msg):
    technical = str(msg or "")
    friendly = user_friendly_error(title, technical)
    if technical and technical != friendly:
        print(f"{title}: {technical}", file=sys.stderr)
    QMessageBox.critical(parent, title, friendly)


def friendly_error_text(title, msg):
    return user_friendly_error(title, msg)


# ── Page Base ──────────────────────────────────────────────
class PageBase(QWidget):
    """Base class for all module pages."""
    def __init__(self, user=None):
        super().__init__()
        self.user = user
        self.setStyleSheet(f"background: {PAGE_BG};")
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(28, 24, 28, 24)
        self.layout_.setSpacing(16)
        self.build_ui()

    def build_ui(self):
        pass

    def refresh(self):
        pass
