"""
modules/dashboard.py
UnoCarshop ASMIS - Dashboard (Integrated v2)

Key integrations:
- Subscribes to ALL module events via EventBus
- Auto-refreshes when ANY module changes data
- Pulls live stats from dashboard_stats view
- Shows: customers, vehicles, orders, billing, attendance,
         out-of-stock alerts, recent transactions, appointments
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QGridLayout, QScrollArea, QTableWidget,
    QTableWidgetItem, QHeaderView, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.widgets import (
    Card, StatCard, StyledTable, status_item,
    PAGE_BG, ORANGE, BORDER, TEXT_DARK, TEXT_SOFT, TEXT_MID,
    GREEN, BLUE, RED, CARD_BG
)
from db.connection import get_connection
from db.events import bus


class DashboardPage(QWidget):
    def __init__(self, user=None):
        super().__init__()
        self.user = user
        self.setStyleSheet(f"background: {PAGE_BG};")
        self._build_ui()

        # â”€â”€ Subscribe to ALL module events â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        bus.customers_changed.connect(self.refresh)
        bus.vehicles_changed.connect(self.refresh)
        bus.employees_changed.connect(self.refresh)
        bus.attendance_changed.connect(self.refresh)
        bus.payroll_changed.connect(self.refresh)
        bus.inventory_changed.connect(self.refresh)
        bus.service_orders_changed.connect(self.refresh)
        bus.billing_changed.connect(self.refresh)
        bus.dashboard_refresh.connect(self.refresh)

        # â”€â”€ Auto-refresh every 60 seconds â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._timer = QTimer(self)
        self._timer.setInterval(60000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

        self.refresh()

    def _build_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none;background:transparent;")

        container = QWidget()
        container.setStyleSheet(f"background:{PAGE_BG};")
        self.main_layout = QVBoxLayout(container)
        self.main_layout.setContentsMargins(28, 24, 28, 24)
        self.main_layout.setSpacing(20)

        # â”€â”€ Row 1: KPI Cards â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        kpi = QGridLayout(); kpi.setSpacing(14)

        self.kpi_customers   = StatCard("Total Customers",   "-", "?", ORANGE)
        self.kpi_vehicles    = StatCard("Total Vehicles",    "-", "?", "#1abc9c")
        self.kpi_employees   = StatCard("Active Employees",  "-", "EMP", BLUE)
        self.kpi_orders      = StatCard("Active Orders",     "-", "?", "#c1121f")
        self.kpi_completed   = StatCard("Completed Today",   "-", "?", GREEN)
        self.kpi_revenue_day = StatCard("Today's Revenue",   "-", "?", GREEN)
        self.kpi_revenue_mon = StatCard("Monthly Revenue",   "-", "?", "#9b59b6")
        self.kpi_low_stock   = StatCard("Out of Stock",      "-", "?",  RED)
        self.kpi_appts       = StatCard("Appts Today",       "-", "APT", "#16a085")
        self.kpi_unpaid      = StatCard("Unpaid Invoices",   "-", "?", RED)
        self.kpi_present     = StatCard("Present Today",     "-", "?", GREEN)
        self.kpi_receivables = StatCard("Total Billed", "-", "?", "#8e44ad")

        cards = [
            self.kpi_customers, self.kpi_vehicles, self.kpi_employees, self.kpi_orders,
            self.kpi_completed, self.kpi_revenue_day, self.kpi_revenue_mon, self.kpi_low_stock,
            self.kpi_appts, self.kpi_unpaid, self.kpi_present, self.kpi_receivables
        ]
        for i, c in enumerate(cards):
            c.setFixedHeight(96)
            kpi.addWidget(c, i // 4, i % 4)
        self.main_layout.addLayout(kpi)

        # â”€â”€ Row 2: Recent Orders + Out of Stock + Attendance â”€â”€
        row2 = QHBoxLayout(); row2.setSpacing(16)

        # Recent orders
        orders_card = Card()
        ol = QVBoxLayout(orders_card); ol.setContentsMargins(16,16,16,16); ol.setSpacing(10)
        hdr1 = QLabel("Recent Service Orders")
        hdr1.setStyleSheet(f"font-size:14px;font-weight:700;color:{TEXT_DARK};border:none;")
        ol.addWidget(hdr1)
        self.orders_table = StyledTable(["Order #","Customer","Vehicle","Service","Status"])
        self.orders_table.setFixedHeight(230)
        self.orders_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        ol.addWidget(self.orders_table)

        # Attendance summary
        att_card = Card(); att_card.setFixedWidth(240)
        al = QVBoxLayout(att_card); al.setContentsMargins(16,16,16,16); al.setSpacing(8)
        hdr2 = QLabel("Today's Attendance")
        hdr2.setStyleSheet(f"font-size:14px;font-weight:700;color:{TEXT_DARK};border:none;")
        al.addWidget(hdr2)
        self.att_bars = {}
        for label, color in [
            ("Present",  GREEN),
            ("Absent",   RED),
            ("Late",     ORANGE),
            ("On Leave", BLUE),
            ("Half Day", "#9b59b6"),
        ]:
            row_ = QHBoxLayout()
            dot = QLabel("?"); dot.setStyleSheet(f"color:{color};border:none;font-size:14px;")
            lbl = QLabel(label); lbl.setStyleSheet(f"color:{TEXT_MID};font-size:13px;border:none;")
            val = QLabel("0"); val.setStyleSheet(
                f"color:{TEXT_DARK};font-size:15px;font-weight:700;border:none;"
            )
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row_.addWidget(dot); row_.addWidget(lbl); row_.addStretch(); row_.addWidget(val)
            al.addLayout(row_)
            self.att_bars[label] = val
        al.addStretch()

        # Out of stock
        low_card = Card(); low_card.setFixedWidth(260)
        ll = QVBoxLayout(low_card); ll.setContentsMargins(16,16,16,16); ll.setSpacing(10)
        hdr3 = QLabel("?  Out of Stock")
        hdr3.setStyleSheet(f"font-size:14px;font-weight:700;color:{TEXT_DARK};border:none;")
        ll.addWidget(hdr3)
        self.low_table = StyledTable(["Item","Qty"])
        self.low_table.setFixedHeight(220)
        self.low_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        ll.addWidget(self.low_table)

        row2.addWidget(orders_card, 1)
        row2.addWidget(att_card)
        row2.addWidget(low_card)
        self.main_layout.addLayout(row2)

        # â”€â”€ Row 3: Recent Billing â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        row3 = QHBoxLayout(); row3.setSpacing(16)

        bill_card = Card()
        bl = QVBoxLayout(bill_card); bl.setContentsMargins(16,16,16,16); bl.setSpacing(10)
        hdr4 = QLabel("Recent Transactions")
        hdr4.setStyleSheet(f"font-size:14px;font-weight:700;color:{TEXT_DARK};border:none;")
        bl.addWidget(hdr4)
        self.bill_table = StyledTable(["Bill #","Customer","Subtotal","Manpower","Total","Status"])
        self.bill_table.setFixedHeight(200)
        self.bill_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        bl.addWidget(self.bill_table)

        row3.addWidget(bill_card, 1)
        self.main_layout.addLayout(row3)
        self.main_layout.addStretch()

        scroll.setWidget(container)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0,0,0,0)
        outer.addWidget(scroll)

    # â”€â”€ Live data refresh â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def refresh(self):
        self._load_kpis()
        self._load_recent_orders()
        self._load_attendance_bars()
        self._load_low_stock()
        self._load_recent_billing()

    def _load_kpis(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            # Try dashboard_stats view first
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.views
                    WHERE table_name='dashboard_stats'
                )
            """)
            view_exists = cur.fetchone()[0]

            if view_exists:
                cur.execute("SELECT * FROM dashboard_stats")
                row = cur.fetchone()
                if row:
                    (total_cust, total_veh, active_emp, active_orders,
                     completed_today, appts_today, monthly_rev, daily_rev,
                     low_stock, present_today, absent_today,
                     unpaid_inv, total_recv) = row
                    self.kpi_customers.set_value(total_cust)
                    self.kpi_vehicles.set_value(total_veh)
                    self.kpi_employees.set_value(active_emp)
                    self.kpi_orders.set_value(active_orders)
                    self.kpi_completed.set_value(completed_today)
                    self.kpi_revenue_day.set_value(f"PHP {float(daily_rev):,.0f}")
                    self.kpi_revenue_mon.set_value(f"PHP {float(monthly_rev):,.0f}")
                    self.kpi_low_stock.set_value(low_stock)
                    self.kpi_appts.set_value(appts_today)
                    self.kpi_unpaid.set_value(unpaid_inv)
                    self.kpi_present.set_value(present_today)
                    self.kpi_receivables.set_value(f"PHP {float(total_recv):,.0f}")
                    conn.close(); return
            # Fallback: individual queries
            cur.execute("SELECT COUNT(*) FROM customers")
            self.kpi_customers.set_value(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM vehicles")
            self.kpi_vehicles.set_value(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM employees WHERE status='Active'")
            self.kpi_employees.set_value(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM service_orders WHERE status IN ('Pending','In Progress')")
            self.kpi_orders.set_value(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM service_orders WHERE status='Completed' AND date_out=CURRENT_DATE")
            self.kpi_completed.set_value(cur.fetchone()[0])
            cur.execute("SELECT COALESCE(SUM(total),0) FROM billing WHERE bill_date=CURRENT_DATE AND status!='Void'")
            self.kpi_revenue_day.set_value(f"PHP {float(cur.fetchone()[0]):,.0f}")
            cur.execute("""SELECT COALESCE(SUM(total),0) FROM billing
                WHERE EXTRACT(MONTH FROM bill_date)=EXTRACT(MONTH FROM CURRENT_DATE)
                AND EXTRACT(YEAR FROM bill_date)=EXTRACT(YEAR FROM CURRENT_DATE)
                AND status!='Void'""")
            self.kpi_revenue_mon.set_value(f"PHP {float(cur.fetchone()[0]):,.0f}")
            cur.execute("SELECT COUNT(*) FROM inventory WHERE quantity<=0 AND status='Active'")
            self.kpi_low_stock.set_value(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM billing WHERE status='Unpaid'")
            self.kpi_unpaid.set_value(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM attendance WHERE attend_date=CURRENT_DATE AND status='Present'")
            self.kpi_present.set_value(cur.fetchone()[0])
            cur.execute("SELECT COALESCE(SUM(total),0) FROM billing WHERE status!='Void'")
            self.kpi_receivables.set_value(f"PHP {float(cur.fetchone()[0]):,.0f}")
            self.kpi_appts.set_value("-")
            conn.close()
        except Exception as e:
            print(f"Dashboard KPI error: {e}")

    def _load_recent_orders(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("""
                SELECT so.order_no, c.full_name,
                       v.plate_no||' '||COALESCE(v.make,'')||' '||COALESCE(v.model,''),
                       st.type_name, so.status
                FROM service_orders so
                JOIN customers c ON so.cust_id=c.cust_id
                JOIN vehicles v ON so.vehicle_id=v.vehicle_id
                JOIN service_types st ON so.svc_type_id=st.svc_type_id
                ORDER BY so.created_at DESC LIMIT 10
            """)
            rows = cur.fetchall(); conn.close()
            self.orders_table.setRowCount(0)
            for rd in rows:
                r = self.orders_table.rowCount()
                self.orders_table.insertRow(r)
                self.orders_table.setRowHeight(r, 36)
                for c, val in enumerate(rd[:-1]):
                    item = QTableWidgetItem(str(val) if val else "")
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    self.orders_table.setItem(r, c, item)
                self.orders_table.setItem(r, 4, status_item(rd[4]))
        except Exception as e:
            print(f"Orders load error: {e}")

    def _load_attendance_bars(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            for label, widget in self.att_bars.items():
                cur.execute(
                    "SELECT COUNT(*) FROM attendance WHERE attend_date=CURRENT_DATE AND status=%s",
                    (label,)
                )
                widget.setText(str(cur.fetchone()[0]))
            conn.close()
        except Exception as e:
            print(f"Attendance bars error: {e}")

    def _load_low_stock(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("""
                SELECT item_name, quantity
                FROM inventory
                WHERE quantity<=0 AND status='Active'
                ORDER BY quantity ASC LIMIT 8
            """)
            rows = cur.fetchall(); conn.close()
            self.low_table.setRowCount(0)
            for rd in rows:
                r = self.low_table.rowCount()
                self.low_table.insertRow(r)
                self.low_table.setRowHeight(r, 34)
                name_item = QTableWidgetItem(rd[0])
                name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                qty_item = QTableWidgetItem(str(rd[1]))
                qty_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
                qty_item.setForeground(QColor(RED))
                self.low_table.setItem(r, 0, name_item)
                self.low_table.setItem(r, 1, qty_item)
        except Exception as e:
            print(f"Out-of-stock error: {e}")

    def _load_recent_billing(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("ALTER TABLE billing ADD COLUMN IF NOT EXISTS manpower NUMERIC(10,2) DEFAULT 0")
            conn.commit()
            cur.execute("""
                SELECT b.bill_no, c.full_name, b.subtotal, COALESCE(b.manpower,0), b.total, b.status
                FROM billing b
                JOIN customers c ON b.cust_id=c.cust_id
                ORDER BY b.created_at DESC LIMIT 8
            """)
            rows = cur.fetchall(); conn.close()
            self.bill_table.setRowCount(0)
            for rd in rows:
                r = self.bill_table.rowCount()
                self.bill_table.insertRow(r)
                self.bill_table.setRowHeight(r, 34)
                for c, val in enumerate(rd[:-1]):
                    text = f"PHP {float(val):,.2f}" if c in (2, 3, 4) else str(val) if val else ""
                    item = QTableWidgetItem(text)
                    item.setTextAlignment(
                        (Qt.AlignRight if c in (2, 3, 4) else Qt.AlignLeft) | Qt.AlignVCenter
                    )
                    self.bill_table.setItem(r, c, item)
                self.bill_table.setItem(r, 5, status_item(rd[5]))
        except Exception as e:
            print(f"Billing load error: {e}")


