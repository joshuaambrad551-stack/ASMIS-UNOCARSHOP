"""
modules/billing.py
UnoCarshop ASMIS - Billing
- Auto-created when service order is marked Completed
- Subtotal is parts/items used, manpower is manual, total is automatic
- Fires billing_changed + dashboard_refresh on CRUD
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QDialog, QFormLayout, QDialogButtonBox, QTableWidgetItem,
    QPushButton, QDoubleSpinBox, QDateEdit
)
from PyQt5.QtCore import Qt, QDate
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.widgets import (
    OrangeButton, GhostButton, SearchBar, StyledTable,
    StatCard, status_item, confirm, info, error,
    PAGE_BG, ORANGE, BORDER, TEXT_DARK, TEXT_SOFT, GREEN, RED, BLUE
)
from db.connection import get_connection
from db.events import bus


def ensure_billing_manpower_column():
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("ALTER TABLE billing ADD COLUMN IF NOT EXISTS manpower NUMERIC(10,2) DEFAULT 0")
        cur.execute("UPDATE billing SET manpower = 0 WHERE manpower IS NULL")
        conn.commit()
        conn.close()
    except Exception:
        pass


class BillingPage(QWidget):
    def __init__(self, user=None):
        super().__init__()
        ensure_billing_manpower_column()
        self.user = user
        self.setStyleSheet(f"background: {PAGE_BG};")
        self._build_ui()
        bus.billing_changed.connect(self.refresh)
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.s_total = StatCard("Total Billed", "PHP 0", "INV", ORANGE)
        self.s_parts = StatCard("Parts Subtotal", "PHP 0", "ITM", GREEN)
        self.s_labor = StatCard("Manpower", "PHP 0", "LAB", RED)
        self.s_count = StatCard("Total Invoices", "0", "DOC", BLUE)
        for s in [self.s_total, self.s_parts, self.s_labor, self.s_count]:
            s.setFixedHeight(88)
            stats.addWidget(s)
        layout.addLayout(stats)

        info_bar = QLabel("Invoices are automatically created when a Service Order is marked as Completed.")
        info_bar.setStyleSheet(
            "background:#e3f2fd;border:1px solid #90caf9;border-radius:6px;"
            "padding:8px 12px;font-size:12px;color:#1565c0;"
        )
        layout.addWidget(info_bar)

        toolbar = QHBoxLayout()
        self.search = SearchBar("Search bill #, customer...")
        self.search.setFixedWidth(260)
        self.search.textChanged.connect(self._filter)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["All Status", "Unpaid", "Paid", "Void"])
        self.status_filter.setFixedHeight(38)
        self.status_filter.setFixedWidth(140)
        self.status_filter.setStyleSheet(self._cs())
        self.status_filter.currentIndexChanged.connect(self._filter)

        btn_add = OrangeButton("+ New Invoice")
        btn_add.clicked.connect(self._add_bill)
        btn_ref = GhostButton("Refresh")
        btn_ref.clicked.connect(self.refresh)
        toolbar.addWidget(self.search)
        toolbar.addWidget(self.status_filter)
        toolbar.addStretch()
        toolbar.addWidget(btn_ref)
        toolbar.addWidget(btn_add)
        layout.addLayout(toolbar)

        cols = ["Bill #", "Customer", "Order #", "Subtotal", "Manpower", "Total", "Status", "Actions"]
        self.table = StyledTable(cols)
        for i, w in enumerate([90, 140, 90, 95, 95, 95, 85]):
            self.table.setColumnWidth(i, w)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet(f"color:{TEXT_SOFT};font-size:12px;")
        layout.addWidget(self.count_lbl)

    def refresh(self):
        self._load_bills()

    def _load_bills(self, search="", status=""):
        try:
            conn = get_connection()
            cur = conn.cursor()
            q = """
                SELECT b.bill_id, b.bill_no, c.full_name,
                       COALESCE(so.order_no,'N/A'),
                       b.subtotal, COALESCE(b.manpower,0), b.total, b.status
                FROM billing b
                JOIN customers c ON b.cust_id=c.cust_id
                LEFT JOIN service_orders so ON b.order_id=so.order_id
                WHERE 1=1
            """
            params = []
            if search:
                q += " AND (LOWER(b.bill_no) LIKE %s OR LOWER(c.full_name) LIKE %s)"
                s = f"%{search.lower()}%"
                params += [s, s]
            if status and status != "All Status":
                q += " AND b.status=%s"
                params.append(status)
            q += " ORDER BY b.created_at DESC"
            cur.execute(q, params)
            rows = cur.fetchall()

            cur.execute("""
                SELECT COALESCE(SUM(total),0),
                       COALESCE(SUM(subtotal),0),
                       COALESCE(SUM(manpower),0),
                       COUNT(*)
                FROM billing
                WHERE status!='Void'
            """)
            totals = cur.fetchone()
            conn.close()

            self.s_total.set_value(f"PHP {float(totals[0]):,.0f}")
            self.s_parts.set_value(f"PHP {float(totals[1]):,.0f}")
            self.s_labor.set_value(f"PHP {float(totals[2]):,.0f}")
            self.s_count.set_value(totals[3])

            self.table.setRowCount(0)
            for rd in rows:
                r = self.table.rowCount()
                self.table.insertRow(r)
                self.table.setRowHeight(r, 38)
                for c, val in enumerate(rd[1:7]):
                    text = f"PHP {float(val):,.2f}" if c in (3, 4, 5) else str(val) if val else ""
                    item = QTableWidgetItem(text)
                    item.setTextAlignment((Qt.AlignRight if c in (3, 4, 5) else Qt.AlignLeft) | Qt.AlignVCenter)
                    self.table.setItem(r, c, item)
                self.table.setItem(r, 6, status_item(rd[7]))

                bid = rd[0]
                act = QWidget()
                act.setStyleSheet("background:transparent;")
                al = QHBoxLayout(act)
                al.setContentsMargins(4, 2, 4, 2)
                al.setSpacing(4)

                btn_e = QPushButton("Edit")
                btn_e.setFixedHeight(27)
                btn_e.setCursor(Qt.PointingHandCursor)
                btn_e.setStyleSheet("QPushButton{background:#e7eef8;color:#123a63;border:1px solid #8aa4c4;border-radius:5px;font-size:11px;padding:0 8px;}QPushButton:hover{background:#dbe9ff;}")
                btn_e.clicked.connect(lambda _, b=bid: self._edit_bill(b))

                btn_v = QPushButton("Void")
                btn_v.setFixedHeight(27)
                btn_v.setCursor(Qt.PointingHandCursor)
                btn_v.setStyleSheet("QPushButton{background:#ffebee;color:#c62828;border:1px solid #ef9a9a;border-radius:5px;font-size:11px;padding:0 8px;}QPushButton:hover{background:#ffcdd2;}")
                btn_v.clicked.connect(lambda _, b=bid: self._void_bill(b))

                al.addWidget(btn_e)
                al.addWidget(btn_v)
                self.table.setCellWidget(r, 7, act)

            self.count_lbl.setText(f"Showing {len(rows)} invoice(s)")
        except Exception as e:
            error(self, "Load Error", str(e))

    def _filter(self):
        self._load_bills(search=self.search.text(), status=self.status_filter.currentText())

    def _add_bill(self):
        dlg = BillingDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("SELECT COALESCE(MAX(CAST(SUBSTRING(bill_no FROM 4) AS INT)),0)+1 FROM billing")
                bill_no = f"INV{cur.fetchone()[0]:05d}"
                cur.execute("""
                    INSERT INTO billing
                        (bill_no,order_id,cust_id,subtotal,manpower,total,amount_paid,status,payment_method,bill_date)
                    VALUES (%s,%s,%s,%s,%s,%s,0,%s,%s,%s)
                """, (bill_no,) + data)
                conn.commit()
                conn.close()
                info(self, "Created", f"Invoice {bill_no} created.")
                self.refresh()
                bus.billing_changed.emit()
                bus.dashboard_refresh.emit()
            except Exception as e:
                error(self, "Error", str(e))

    def _edit_bill(self, bill_id):
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT order_id,cust_id,subtotal,COALESCE(manpower,0),total,status,payment_method,bill_date
                FROM billing
                WHERE bill_id=%s
            """, (bill_id,))
            row = cur.fetchone()
            conn.close()
        except Exception as e:
            error(self, "Error", str(e))
            return

        dlg = BillingDialog(self, row)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("""
                    UPDATE billing
                    SET order_id=%s,cust_id=%s,subtotal=%s,manpower=%s,total=%s,
                        amount_paid=0,status=%s,payment_method=%s,bill_date=%s
                    WHERE bill_id=%s
                """, data + (bill_id,))
                conn.commit()
                conn.close()
                info(self, "Updated", "Invoice updated.")
                self.refresh()
                bus.billing_changed.emit()
                bus.dashboard_refresh.emit()
            except Exception as e:
                error(self, "Error", str(e))

    def _void_bill(self, bill_id):
        if confirm(self, "Void Invoice", "Mark this invoice as Void?"):
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("UPDATE billing SET status='Void' WHERE bill_id=%s", (bill_id,))
                conn.commit()
                conn.close()
                self.refresh()
                bus.billing_changed.emit()
                bus.dashboard_refresh.emit()
            except Exception as e:
                error(self, "Error", str(e))

    def _cs(self):
        return f"QComboBox{{border:1px solid {BORDER};border-radius:8px;padding:0 10px;font-size:13px;color:{TEXT_DARK};background:white;}}QComboBox::drop-down{{border:none;width:20px;}}"


class BillingDialog(QDialog):
    def __init__(self, parent, existing=None):
        super().__init__(parent)
        ensure_billing_manpower_column()
        self.setWindowTitle("Invoice")
        self.setFixedWidth(460)
        self.setStyleSheet(
            "QDialog{background:#f3f6fb;font-family:'Segoe UI';}"
            "QComboBox,QDoubleSpinBox,QDateEdit{border:1px solid #d7dee8;border-radius:7px;padding:6px 10px;font-size:13px;background:white;}"
        )
        self._customers = {}
        self._orders = {}
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT cust_id, cust_code||' - '||full_name FROM customers ORDER BY cust_code")
            self._customers = {r[1]: r[0] for r in cur.fetchall()}
            cur.execute("SELECT order_id, order_no FROM service_orders WHERE status='Completed' ORDER BY order_no")
            self._orders = {"None": None}
            self._orders.update({r[1]: r[0] for r in cur.fetchall()})
            conn.close()
        except Exception:
            pass
        self._build(existing)

    def _build(self, ex):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.f_order = QComboBox()
        self.f_order.addItems(list(self._orders.keys()))
        if ex and ex[0]:
            for label, oid in self._orders.items():
                if oid == ex[0]:
                    self.f_order.setCurrentText(label)
                    break

        self.f_cust = QComboBox()
        self.f_cust.addItems(list(self._customers.keys()))
        if ex and ex[1]:
            for label, cid in self._customers.items():
                if cid == ex[1]:
                    self.f_cust.setCurrentText(label)
                    break

        def money(v=0):
            s = QDoubleSpinBox()
            s.setMaximum(9999999)
            s.setDecimals(2)
            s.setPrefix("PHP ")
            s.setValue(float(v) if v else 0)
            return s

        self.f_sub = money(ex[2] if ex else 0)
        self.f_manpower = money(ex[3] if ex else 0)
        self.f_total = money(ex[4] if ex else 0)
        self.f_total.setReadOnly(True)
        self.f_total.setButtonSymbols(QDoubleSpinBox.NoButtons)

        self.f_status = QComboBox()
        self.f_status.addItems(["Unpaid", "Paid", "Void"])
        if ex and ex[5] in ["Unpaid", "Paid", "Void"]:
            self.f_status.setCurrentText(ex[5])

        self.f_method = QComboBox()
        self.f_method.addItems(["Cash", "GCash", "Maya", "Bank Transfer", "Card", "Other"])
        if ex and ex[6]:
            self.f_method.setCurrentText(ex[6])

        self.f_date = QDateEdit()
        self.f_date.setCalendarPopup(True)
        self.f_date.setDate(QDate.fromString(str(ex[7]), "yyyy-MM-dd") if ex and ex[7] else QDate.currentDate())

        form.addRow("Service Order", self.f_order)
        form.addRow("Customer *", self.f_cust)
        form.addRow("Subtotal", self.f_sub)
        form.addRow("Manpower", self.f_manpower)
        form.addRow("Total", self.f_total)
        form.addRow("Status", self.f_status)
        form.addRow("Payment Method", self.f_method)
        form.addRow("Bill Date", self.f_date)
        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self.f_order.currentTextChanged.connect(self._auto_fill_from_order)
        self.f_sub.valueChanged.connect(self._recalculate_totals)
        self.f_manpower.valueChanged.connect(self._recalculate_totals)
        self._recalculate_totals()

    def _auto_fill_from_order(self, label):
        order_id = self._orders.get(label)
        if not order_id:
            return
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT so.cust_id,
                       COALESCE(SUM(sop.qty_used * sop.unit_price), 0) AS subtotal
                FROM service_orders so
                LEFT JOIN service_order_parts sop ON so.order_id=sop.order_id
                WHERE so.order_id=%s
                GROUP BY so.order_id, so.cust_id
            """, (order_id,))
            row = cur.fetchone()
            conn.close()
            if not row:
                return

            cust_id, subtotal = row
            for cust_label, cid in self._customers.items():
                if cid == cust_id:
                    self.f_cust.setCurrentText(cust_label)
                    break
            self.f_sub.setValue(float(subtotal) if subtotal else 0)
            self._recalculate_totals()
        except Exception as e:
            error(self, "Order Pricing Error", str(e))

    def _recalculate_totals(self):
        total = self.f_sub.value() + self.f_manpower.value()
        self.f_total.blockSignals(True)
        self.f_total.setValue(total)
        self.f_total.blockSignals(False)

    def get_data(self):
        self._recalculate_totals()
        return (
            self._orders.get(self.f_order.currentText()),
            self._customers.get(self.f_cust.currentText()),
            self.f_sub.value(),
            self.f_manpower.value(),
            self.f_total.value(),
            self.f_status.currentText(),
            self.f_method.currentText(),
            self.f_date.date().toString("yyyy-MM-dd"),
        )
