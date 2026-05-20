"""
modules/main_window.py
UnoCarshop ASMIS — Main Application Window
"""
import sys
import os
from datetime import date, datetime, time, timedelta

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout,
    QVBoxLayout, QLabel, QPushButton, QStackedWidget,
    QFrame, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.events import bus
from db.daily_archive import ensure_daily_snapshot_table, snapshot_exists, store_daily_snapshot
from modules.widgets import (
    BLACK, BORDER, PAGE_BG, RED, TEXT_DARK, TEXT_SOFT,
    friendly_error_text
)


class MainWindow(QMainWindow):
    def __init__(self, user):
        super().__init__()
        # user = (user_id, full_name, role_name, permissions_json)
        self.user = user
        self.setWindowTitle("UnoCarshop ASMIS")
        self.showMaximized()
        self.setStyleSheet(f"background-color: {PAGE_BG}; font-family: 'Segoe UI';")
        self._pages_cache = {}
        bus.data_changed.connect(self._refresh_cached_pages)
        self._init_ui()
        self._init_daily_snapshot_service()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_sidebar())

        # Content
        content_wrapper = QWidget()
        content_wrapper.setStyleSheet(f"background: {PAGE_BG};")
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        content_layout.addWidget(self._build_topbar())

        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background: {PAGE_BG};")
        content_layout.addWidget(self.stack)

        root.addWidget(content_wrapper)

        # Load dashboard by default
        self._switch_page(0)

    # ─────────────────────────────────────────────────────────
    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setFixedWidth(234)
        sidebar.setStyleSheet(f"background-color: {BLACK};")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Brand
        brand = QFrame()
        brand.setStyleSheet("border-bottom: 1px solid rgba(255,255,255,0.06);")
        b_layout = QVBoxLayout(brand)
        b_layout.setContentsMargins(20, 22, 20, 18)
        b_layout.setSpacing(4)

        badge = QLabel("ASMIS")
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(28)
        badge.setStyleSheet("""
            background-color: #c1121f; color: white;
            font-weight: 700; font-size: 13px;
            border-radius: 6px; padding: 4px 10px;
        """)
        shop_name = QLabel("UnoCarshop")
        shop_name.setStyleSheet("color: white; font-size: 15px; font-weight: 700; border: none;")
        shop_sub = QLabel("Auto Shop Management")
        shop_sub.setStyleSheet(f"color: {TEXT_SOFT}; font-size: 11px; border: none;")

        b_layout.addWidget(badge)
        b_layout.addWidget(shop_name)
        b_layout.addWidget(shop_sub)
        layout.addWidget(brand)

        # Nav items
        self.nav_items = [
            ("\U0001F4CA", "Dashboard"),
            ("\U0001F465", "Employees"),
            ("\U0001F550", "Attendance"),
            ("\U0001F4B0", "Payroll"),
            ("\U0001F4E6", "Inventory"),
            ("\U0001F697", "Customers"),
            ("\U0001F527", "Service Orders"),
            ("\U0001F9FE", "Billing"),
        ]

        sec = QLabel("CORE MODULES")
        sec.setStyleSheet(
            "color: rgba(255,255,255,0.3); font-size: 10px; font-weight: 600; "
            "letter-spacing: 1px; padding: 16px 20px 6px;"
        )
        layout.addWidget(sec)

        self.nav_buttons = []
        for i, (icon, name) in enumerate(self.nav_items):
            btn = QPushButton(f"  {icon}  {name}")
            btn.setFixedHeight(38)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(self._nav_style(False))
            btn.clicked.connect(lambda _, idx=i: self._switch_page(idx))
            layout.addWidget(btn)
            self.nav_buttons.append(btn)

        layout.addStretch()

        # User info panel
        user_frame = QFrame()
        user_frame.setStyleSheet("border-top: 1px solid rgba(255,255,255,0.06);")
        u_layout = QVBoxLayout(user_frame)
        u_layout.setContentsMargins(16, 12, 16, 12)
        u_layout.setSpacing(4)

        lbl_name = QLabel(f"\U0001F464  {self.user[1]}")
        lbl_name.setStyleSheet("color: white; font-size: 12px; font-weight: 600; border: none;")
        lbl_role = QLabel(self.user[2].upper())
        lbl_role.setStyleSheet(f"color: {RED}; font-size: 10px; letter-spacing: 1px; border: none;")

        btn_logout = QPushButton("\u23FB  Logout")
        btn_logout.setCursor(Qt.PointingHandCursor)
        btn_logout.setFixedHeight(32)
        btn_logout.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.08); color: #a8b3c2;
                border: none; border-radius: 6px; font-size: 12px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.15); color: white; }
        """)
        btn_logout.clicked.connect(self._logout)

        u_layout.addWidget(lbl_name)
        u_layout.addWidget(lbl_role)
        u_layout.addWidget(btn_logout)
        layout.addWidget(user_frame)

        return sidebar

    def _build_topbar(self):
        bar = QFrame()
        bar.setFixedHeight(60)
        bar.setStyleSheet(f"background: white; border-bottom: 1px solid {BORDER};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(28, 0, 24, 0)

        self.topbar_title = QLabel("Dashboard")
        self.topbar_title.setStyleSheet(
            f"font-size: 20px; font-weight: 700; font-style: italic; color: {TEXT_DARK};"
        )
        layout.addWidget(self.topbar_title)
        layout.addStretch()

        # Notification stub
        self.notif_lbl = QLabel("")
        self.notif_lbl.setStyleSheet(f"font-size: 12px; color: {TEXT_SOFT};")
        layout.addWidget(self.notif_lbl)

        self.btn_daily_store = QPushButton("Store Daily Data")
        self.btn_daily_store.setCursor(Qt.PointingHandCursor)
        self.btn_daily_store.setFixedHeight(34)
        self.btn_daily_store.setStyleSheet("""
            QPushButton {
                background: #0b1f3a; color: white;
                border: none; border-radius: 7px;
                font-size: 12px; font-weight: 600;
                padding: 0 14px;
            }
            QPushButton:hover { background: #123a63; }
            QPushButton:pressed { background: #071426; }
        """)
        self.btn_daily_store.clicked.connect(self._store_today_and_open_history)
        layout.addWidget(self.btn_daily_store)

        return bar

    # ─────────────────────────────────────────────────────────
    def _get_page(self, index):
        if index in self._pages_cache:
            return self._pages_cache[index]

        name = self.nav_items[index][1]

        if name == "Dashboard":
            from modules.dashboard import DashboardPage
            page = DashboardPage(self.user)
        elif name == "Employees":
            from modules.employees import EmployeesPage
            page = EmployeesPage(self.user)
        elif name == "Attendance":
            from modules.attendance import AttendancePage
            page = AttendancePage(self.user)
        elif name == "Payroll":
            from modules.payroll import PayrollPage
            page = PayrollPage(self.user)
        elif name == "Inventory":
            from modules.inventory import InventoryPage
            page = InventoryPage(self.user)
        elif name == "Customers":
            from modules.customers import CustomersPage
            page = CustomersPage(self.user)
        elif name == "Service Orders":
            from modules.service_orders import ServiceOrdersPage
            page = ServiceOrdersPage(self.user)
        elif name == "Billing":
            from modules.billing import BillingPage
            page = BillingPage(self.user)
        else:
            page = QLabel(f"{name} — Module coming soon")
            page.setAlignment(Qt.AlignCenter)
            page.setStyleSheet(f"font-size: 18px; color: {TEXT_SOFT};")

        self._pages_cache[index] = page
        self.stack.addWidget(page)
        return page

    def _switch_page(self, index):
        page = self._get_page(index)
        self.stack.setCurrentWidget(page)
        name = self.nav_items[index][1]
        self.topbar_title.setText(name)
        for i, btn in enumerate(self.nav_buttons):
            btn.setStyleSheet(self._nav_style(i == index))
        # Refresh data when switching
        if hasattr(page, "refresh"):
            page.refresh()

    def _open_daily_history(self):
        key = "daily_history"
        if key not in self._pages_cache:
            from modules.daily_history import DailyHistoryPage
            page = DailyHistoryPage(self.user)
            self._pages_cache[key] = page
            self.stack.addWidget(page)
        page = self._pages_cache[key]
        self.stack.setCurrentWidget(page)
        self.topbar_title.setText("Daily Data History")
        for btn in self.nav_buttons:
            btn.setStyleSheet(self._nav_style(False))
        if hasattr(page, "refresh"):
            page.refresh()

    def _store_today_and_open_history(self):
        try:
            user_id = self.user[0] if self.user else None
            store_daily_snapshot(date.today(), user_id)
            self.notif_lbl.setText("Today's data stored.")
            self._open_daily_history()
        except Exception as e:
            print(f"Daily snapshot error: {e}", file=sys.stderr)
            QMessageBox.critical(self, "Daily Snapshot Error", friendly_error_text("Daily Snapshot Error", e))

    def _init_daily_snapshot_service(self):
        try:
            ensure_daily_snapshot_table()
            self._store_yesterday_if_missing()
        except Exception as e:
            print(f"Daily storage unavailable: {e}", file=sys.stderr)
            self.notif_lbl.setText("Daily storage is unavailable. Please check the database setup.")
        self._schedule_end_of_day_snapshot()

    def _store_yesterday_if_missing(self):
        yesterday = date.today() - timedelta(days=1)
        if not snapshot_exists(yesterday):
            user_id = self.user[0] if self.user else None
            store_daily_snapshot(yesterday, user_id)
            self.notif_lbl.setText(f"Stored missing snapshot for {yesterday}.")

    def _schedule_end_of_day_snapshot(self):
        now = datetime.now()
        next_run = datetime.combine(now.date() + timedelta(days=1), time(0, 0, 5))
        delay_ms = max(1000, int((next_run - now).total_seconds() * 1000))
        QTimer.singleShot(delay_ms, self._run_end_of_day_snapshot)

    def _run_end_of_day_snapshot(self):
        snapshot_day = date.today() - timedelta(days=1)
        try:
            user_id = self.user[0] if self.user else None
            store_daily_snapshot(snapshot_day, user_id)
            self.notif_lbl.setText(f"Daily data stored for {snapshot_day}.")
            page = self._pages_cache.get("daily_history")
            if page is not None and hasattr(page, "refresh"):
                page.refresh()
        except Exception as e:
            print(f"Daily storage failed: {e}", file=sys.stderr)
            self.notif_lbl.setText("Daily storage failed. Please try again later.")
        finally:
            self._schedule_end_of_day_snapshot()

    def _refresh_cached_pages(self, areas):
        current = self.stack.currentWidget() if hasattr(self, "stack") else None
        for page in self._pages_cache.values():
            if page is current:
                continue
            if hasattr(page, "refresh"):
                page.refresh()

    def _nav_style(self, active: bool) -> str:
        if active:
            return """
                QPushButton {
                    background: rgba(193,18,31,0.16); color: #ff5a66;
                    border: none; border-radius: 8px; margin: 1px 6px;
                    text-align: left; padding-left: 8px;
                    font-size: 13px; font-weight: 600;
                }
            """
        return """
            QPushButton {
                background: transparent; color: #b8b6b0;
                border: none; border-radius: 8px; margin: 1px 6px;
                text-align: left; padding-left: 8px; font-size: 13px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.06); color: white;
            }
        """

    def _logout(self):
        reply = QMessageBox.question(
            self, "Logout", "Are you sure you want to logout?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            from modules.login import LoginWindow
            self.login_win = LoginWindow()
            self.login_win.show()
            self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow((1, "Administrator", "owner", {}))
    sys.exit(app.exec_())

