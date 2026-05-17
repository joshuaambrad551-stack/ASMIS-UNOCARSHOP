"""
modules/service_orders.py
UnoCarshop ASMIS — Service Orders (Integrated v2)

Key integrations:
- Completing an order auto-creates billing (via DB trigger)
- Parts used auto-deduct inventory (via DB trigger)
- Fires service_orders_changed + billing_changed + inventory_changed
- Mechanic (employee) assignment tracked
- Connected to customers + vehicles + service types
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QDialog, QFormLayout, QDialogButtonBox,
    QTableWidgetItem, QPushButton, QLineEdit,
    QTextEdit, QDateEdit, QFrame, QTabWidget,
    QSpinBox, QDoubleSpinBox, QMessageBox
)
from PyQt5.QtCore import Qt, QDate
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.widgets import (
    OrangeButton, GhostButton, SearchBar, StyledTable,
    StatCard, status_item, confirm, info, error,
    PAGE_BG, ORANGE, BORDER, TEXT_DARK, TEXT_SOFT,
    GREEN, RED, BLUE
)
from db.connection import get_connection
from db.events import bus


class ServiceOrdersPage(QWidget):
    def __init__(self, user=None):
        super().__init__()
        self.user = user
        self.setStyleSheet(f"background: {PAGE_BG};")
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Stats
        stats = QHBoxLayout(); stats.setSpacing(12)
        self.s_pending  = StatCard("Pending",     "0", "⏳", ORANGE)
        self.s_inprog   = StatCard("In Progress", "0", "🔧", BLUE)
        self.s_done     = StatCard("Completed",   "0", "✅", GREEN)
        self.s_cancel   = StatCard("Cancelled",   "0", "❌", RED)
        for s in [self.s_pending, self.s_inprog, self.s_done, self.s_cancel]:
            s.setFixedHeight(88); stats.addWidget(s)
        layout.addLayout(stats)

        # Toolbar
        toolbar = QHBoxLayout()
        self.search = SearchBar("Search order #, customer, plate…")
        self.search.setFixedWidth(260)
        self.search.textChanged.connect(self._filter)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["All Status","Pending","In Progress","Completed","Cancelled"])
        self.status_filter.setFixedHeight(38); self.status_filter.setFixedWidth(150)
        self.status_filter.setStyleSheet(self._cs())
        self.status_filter.currentIndexChanged.connect(self._filter)

        self.priority_filter = QComboBox()
        self.priority_filter.addItems(["All Priority","Low","Normal","High","Urgent"])
        self.priority_filter.setFixedHeight(38); self.priority_filter.setFixedWidth(140)
        self.priority_filter.setStyleSheet(self._cs())
        self.priority_filter.currentIndexChanged.connect(self._filter)

        btn_add     = OrangeButton("➕  New Order")
        btn_add.clicked.connect(self._add_order)
        btn_refresh = GhostButton("🔄  Refresh")
        btn_refresh.clicked.connect(self.refresh)

        toolbar.addWidget(self.search)
        toolbar.addWidget(self.status_filter)
        toolbar.addWidget(self.priority_filter)
        toolbar.addStretch()
        toolbar.addWidget(btn_refresh)
        toolbar.addWidget(btn_add)
        layout.addLayout(toolbar)

        # Table
        cols = ["Order #","Customer","Vehicle","Service","Mechanic",
                "Priority","Date In","Status","Actions"]
        self.table = StyledTable(cols)
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(1, 140)
        self.table.setColumnWidth(2, 140)
        self.table.setColumnWidth(3, 130)
        self.table.setColumnWidth(4, 130)
        self.table.setColumnWidth(5, 80)
        self.table.setColumnWidth(6, 90)
        self.table.setColumnWidth(7, 100)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet(f"color:{TEXT_SOFT};font-size:12px;")
        layout.addWidget(self.count_lbl)

    def refresh(self):
        self._update_stats()
        self._load_orders()

    def _update_stats(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            for stat, widget in [
                ("Pending",     self.s_pending),
                ("In Progress", self.s_inprog),
                ("Completed",   self.s_done),
                ("Cancelled",   self.s_cancel),
            ]:
                cur.execute("SELECT COUNT(*) FROM service_orders WHERE status=%s", (stat,))
                widget.set_value(cur.fetchone()[0])
            conn.close()
        except: pass

    def _load_orders(self, search="", status="", priority=""):
        try:
            conn = get_connection(); cur = conn.cursor()
            q = """
                SELECT so.order_id, so.order_no, c.full_name,
                       v.plate_no||' '||COALESCE(v.make,'')||' '||COALESCE(v.model,''),
                       st.type_name,
                       COALESCE(e.full_name,'Unassigned'),
                       so.priority, so.date_in, so.status
                FROM service_orders so
                JOIN customers c ON so.cust_id=c.cust_id
                JOIN vehicles v ON so.vehicle_id=v.vehicle_id
                JOIN service_types st ON so.svc_type_id=st.svc_type_id
                LEFT JOIN employees e ON so.assign_emp=e.emp_id
                WHERE 1=1
            """
            params = []
            if search:
                q += " AND (LOWER(so.order_no) LIKE %s OR LOWER(c.full_name) LIKE %s OR LOWER(v.plate_no) LIKE %s)"
                s = f"%{search.lower()}%"; params += [s, s, s]
            if status and status != "All Status":
                q += " AND so.status=%s"; params.append(status)
            if priority and priority != "All Priority":
                q += " AND so.priority=%s"; params.append(priority)
            q += " ORDER BY so.created_at DESC"
            cur.execute(q, params)
            rows = cur.fetchall(); conn.close()

            self.table.setRowCount(0)
            self._order_ids = []
            for rd in rows:
                r = self.table.rowCount()
                self.table.insertRow(r); self.table.setRowHeight(r, 38)
                self._order_ids.append(rd[0])
                for c, val in enumerate(rd[1:8]):
                    item = QTableWidgetItem(str(val) if val else "")
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    self.table.setItem(r, c, item)
                self.table.setItem(r, 7, status_item(rd[8]))

                oid = rd[0]; cur_status = rd[8]
                act = QWidget(); act.setStyleSheet("background:transparent;")
                al = QHBoxLayout(act); al.setContentsMargins(4,2,4,2); al.setSpacing(4)

                btn_e = QPushButton("Edit"); btn_e.setFixedHeight(27)
                btn_e.setCursor(Qt.PointingHandCursor)
                btn_e.setStyleSheet("QPushButton{background:#fff4e0;color:#e08e0b;border:1px solid #f5c07a;border-radius:5px;font-size:11px;padding:0 8px;}QPushButton:hover{background:#ffe0a0;}")
                btn_e.clicked.connect(lambda _, o=oid: self._edit_order(o))

                btn_p = QPushButton("Parts"); btn_p.setFixedHeight(27)
                btn_p.setCursor(Qt.PointingHandCursor)
                btn_p.setStyleSheet("QPushButton{background:#e3f2fd;color:#1565c0;border:1px solid #90caf9;border-radius:5px;font-size:11px;padding:0 8px;}QPushButton:hover{background:#bbdefb;}")
                btn_p.clicked.connect(lambda _, o=oid: self._manage_parts(o))

                btn_d = QPushButton("Del"); btn_d.setFixedHeight(27)
                btn_d.setCursor(Qt.PointingHandCursor)
                btn_d.setStyleSheet("QPushButton{background:#ffebee;color:#c62828;border:1px solid #ef9a9a;border-radius:5px;font-size:11px;padding:0 8px;}QPushButton:hover{background:#ffcdd2;}")
                btn_d.clicked.connect(lambda _, o=oid: self._delete_order(o))

                al.addWidget(btn_e)
                al.addWidget(btn_p)
                al.addWidget(btn_d)
                self.table.setCellWidget(r, 8, act)

            self.count_lbl.setText(f"Showing {len(rows)} order(s)")
        except Exception as e:
            error(self, "Load Error", str(e))

    def _filter(self):
        self._load_orders(
            search=self.search.text(),
            status=self.status_filter.currentText(),
            priority=self.priority_filter.currentText()
        )

    def _add_order(self):
        dlg = ServiceOrderDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("SELECT COALESCE(MAX(CAST(SUBSTRING(order_no FROM 4) AS INT)),0)+1 FROM service_orders")
                next_num = cur.fetchone()[0]
                order_no = f"ORD{next_num:05d}"
                cur.execute("""
                    INSERT INTO service_orders
                    (order_no,vehicle_id,cust_id,assign_emp,svc_type_id,
                     description,status,priority,date_in,remarks)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (order_no,) + data)
                conn.commit(); conn.close()
                info(self, "Created", f"Service order {order_no} created.")
                self.refresh()
                bus.service_orders_changed.emit()
                bus.dashboard_refresh.emit()
            except Exception as e:
                error(self, "Error", str(e))

    def _edit_order(self, order_id):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("""
                SELECT vehicle_id,cust_id,assign_emp,svc_type_id,
                       description,status,priority,date_in,remarks
                FROM service_orders WHERE order_id=%s
            """, (order_id,))
            row = cur.fetchone()
            old_status = row[5]
            conn.close()
        except Exception as e:
            error(self, "Error", str(e)); return

        dlg = ServiceOrderDialog(self, row)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            new_status = data[5]
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("""
                    UPDATE service_orders SET vehicle_id=%s,cust_id=%s,assign_emp=%s,
                        svc_type_id=%s,description=%s,status=%s,priority=%s,
                        date_in=%s,remarks=%s
                    WHERE order_id=%s
                """, data + (order_id,))
                conn.commit(); conn.close()

                self.refresh()
                bus.service_orders_changed.emit()
                bus.dashboard_refresh.emit()

                # If just completed → billing was auto-created by trigger
                if new_status == "Completed" and old_status != "Completed":
                    bus.billing_changed.emit()
                    info(self, "Completed",
                         "Order marked as Completed.\n"
                         "An invoice has been automatically created in Billing.")
                else:
                    info(self, "Updated", "Order updated.")
            except Exception as e:
                error(self, "Error", str(e))

    def _manage_parts(self, order_id):
        """Open parts usage dialog — deducts inventory automatically."""
        dlg = PartsDialog(self, order_id)
        dlg.exec_()
        self.refresh()
        bus.inventory_changed.emit()
        bus.dashboard_refresh.emit()

    def _delete_order(self, order_id):
        if confirm(self, "Delete Order", "Delete this service order?\nLinked billing will also be removed."):
            try:
                conn = get_connection(); cur = conn.cursor()
                # Remove billing first (FK)
                cur.execute("DELETE FROM billing WHERE order_id=%s", (order_id,))
                cur.execute("DELETE FROM service_order_parts WHERE order_id=%s", (order_id,))
                cur.execute("DELETE FROM service_orders WHERE order_id=%s", (order_id,))
                conn.commit(); conn.close()
                self.refresh()
                bus.service_orders_changed.emit()
                bus.billing_changed.emit()
                bus.inventory_changed.emit()
                bus.dashboard_refresh.emit()
            except Exception as e:
                error(self, "Error", str(e))

    def _cs(self):
        return f"""
            QComboBox{{border:1px solid {BORDER};border-radius:8px;
            padding:0 10px;font-size:13px;color:{TEXT_DARK};background:white;}}
            QComboBox::drop-down{{border:none;width:20px;}}
        """


class ServiceOrderDialog(QDialog):
    def __init__(self, parent, existing=None):
        super().__init__(parent)
        self.setWindowTitle("Service Order")
        self.setFixedWidth(500)
        self.setStyleSheet("""
            QDialog{background:#f5f4f0;font-family:'Segoe UI';}
            QLineEdit,QComboBox,QDateEdit,QTextEdit{
                border:1px solid #e0ddd5;border-radius:7px;
                padding:6px 10px;font-size:13px;background:white;}
        """)
        self._vehicles = {}; self._customers = {}
        self._employees = {}; self._svc_types = {}
        self._load_lookups()
        self._build(existing)

    def _load_lookups(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT vehicle_id, plate_no||' - '||COALESCE(make,'')||' '||COALESCE(model,'') FROM vehicles ORDER BY plate_no")
            self._vehicles = {r[1]: r[0] for r in cur.fetchall()}
            cur.execute("SELECT cust_id, cust_code||' - '||full_name FROM customers ORDER BY cust_code")
            self._customers = {r[1]: r[0] for r in cur.fetchall()}
            cur.execute("SELECT emp_id, emp_code||' - '||full_name FROM employees WHERE status='Active' ORDER BY emp_code")
            self._employees = {"Unassigned": None}
            self._employees.update({r[1]: r[0] for r in cur.fetchall()})
            cur.execute("SELECT svc_type_id, type_name FROM service_types ORDER BY type_name")
            self._svc_types = {r[1]: r[0] for r in cur.fetchall()}
            conn.close()
        except: pass

    def _build(self, ex):
        layout = QVBoxLayout(self); layout.setContentsMargins(24,20,24,20)
        form = QFormLayout(); form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.f_veh = QComboBox(); self.f_veh.addItems(list(self._vehicles.keys()))
        if ex and ex[0]:
            for label, vid in self._vehicles.items():
                if vid == ex[0]: self.f_veh.setCurrentText(label); break

        self.f_cust = QComboBox(); self.f_cust.addItems(list(self._customers.keys()))
        if ex and ex[1]:
            for label, cid in self._customers.items():
                if cid == ex[1]: self.f_cust.setCurrentText(label); break

        # Auto-fill customer when vehicle selected
        self.f_veh.currentTextChanged.connect(self._auto_fill_customer)

        self.f_emp = QComboBox(); self.f_emp.addItems(list(self._employees.keys()))
        if ex and ex[2]:
            for label, eid in self._employees.items():
                if eid == ex[2]: self.f_emp.setCurrentText(label); break

        self.f_svc = QComboBox(); self.f_svc.addItems(list(self._svc_types.keys()))
        if ex and ex[3]:
            for label, sid in self._svc_types.items():
                if sid == ex[3]: self.f_svc.setCurrentText(label); break

        self.f_desc    = QTextEdit(ex[4] if ex and ex[4] else "")
        self.f_desc.setFixedHeight(60)
        self.f_status  = QComboBox()
        self.f_status.addItems(["Pending","In Progress","Completed","Cancelled"])
        if ex and ex[5]: self.f_status.setCurrentText(ex[5])
        self.f_priority= QComboBox()
        self.f_priority.addItems(["Low","Normal","High","Urgent"])
        if ex and ex[6]: self.f_priority.setCurrentText(ex[6])
        self.f_date    = QDateEdit(); self.f_date.setCalendarPopup(True)
        self.f_date.setDate(
            QDate.fromString(str(ex[7]),"yyyy-MM-dd") if ex and ex[7]
            else QDate.currentDate()
        )
        self.f_remarks = QTextEdit(ex[8] if ex and ex[8] else "")
        self.f_remarks.setFixedHeight(50)

        form.addRow("Vehicle *",   self.f_veh)
        form.addRow("Customer *",  self.f_cust)
        form.addRow("Mechanic",    self.f_emp)
        form.addRow("Service *",   self.f_svc)
        form.addRow("Description", self.f_desc)
        form.addRow("Status",      self.f_status)
        form.addRow("Priority",    self.f_priority)
        form.addRow("Date In",     self.f_date)
        form.addRow("Remarks",     self.f_remarks)
        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Save).setStyleSheet(
            "background:#f5a623;color:white;border:none;border-radius:6px;padding:6px 18px;font-weight:700;")
        btns.button(QDialogButtonBox.Cancel).setStyleSheet(
            "background:#eee;color:#555;border:none;border-radius:6px;padding:6px 14px;")
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _auto_fill_customer(self, veh_label):
        """Auto-select customer when vehicle is selected."""
        vid = self._vehicles.get(veh_label)
        if not vid: return
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("""
                SELECT c.cust_id, c.cust_code||' - '||c.full_name
                FROM vehicles v JOIN customers c ON v.cust_id=c.cust_id
                WHERE v.vehicle_id=%s
            """, (vid,))
            row = cur.fetchone(); conn.close()
            if row:
                label = row[1]
                if label in self._customers:
                    self.f_cust.setCurrentText(label)
        except: pass

    def _validate(self):
        if not self._vehicles or not self._vehicles.get(self.f_veh.currentText()):
            QMessageBox.warning(self, "Validation", "Please add or select a vehicle.")
            return
        if not self._customers or not self._customers.get(self.f_cust.currentText()):
            QMessageBox.warning(self, "Validation", "Please add or select a customer.")
            return
        if not self._svc_types or not self._svc_types.get(self.f_svc.currentText()):
            QMessageBox.warning(self, "Validation", "Please add or select a service type.")
            return
        self.accept()

    def get_data(self):
        return (
            self._vehicles.get(self.f_veh.currentText()),
            self._customers.get(self.f_cust.currentText()),
            self._employees.get(self.f_emp.currentText()),
            self._svc_types.get(self.f_svc.currentText()),
            self.f_desc.toPlainText().strip(),
            self.f_status.currentText(),
            self.f_priority.currentText(),
            self.f_date.date().toString("yyyy-MM-dd"),
            self.f_remarks.toPlainText().strip(),
        )


class PartsDialog(QDialog):
    """Manage parts used in a service order — auto-deducts inventory."""
    def __init__(self, parent, order_id):
        super().__init__(parent)
        self.order_id = order_id
        self.setWindowTitle("Parts Used in Service Order")
        self.setFixedWidth(620)
        self.setFixedHeight(480)
        self.setStyleSheet("""
            QDialog{background:#f5f4f0;font-family:'Segoe UI';}
            QComboBox,QSpinBox,QDoubleSpinBox{border:1px solid #e0ddd5;
            border-radius:7px;padding:5px 10px;font-size:12px;background:white;}
        """)
        self._inventory = {}
        self._load_inventory()
        self._build()

    def _load_inventory(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("""
                SELECT item_id, item_code||' — '||item_name, quantity, unit_price
                FROM inventory WHERE status='Active' AND quantity>0
                ORDER BY item_name
            """)
            self._inventory = {r[1]: (r[0], r[2], r[3]) for r in cur.fetchall()}
            conn.close()
        except: pass

    def _build(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(16,16,16,16); layout.setSpacing(12)

        # Header
        hdr = QLabel(f"Parts for Order ID: {self.order_id}")
        hdr.setStyleSheet(f"font-size:14px;font-weight:700;color:{TEXT_DARK};")
        layout.addWidget(hdr)

        # Add part row
        add_row = QHBoxLayout()
        self.f_item = QComboBox()
        self.f_item.addItems(list(self._inventory.keys()))
        self.f_item.setFixedHeight(36)
        self.f_qty  = QSpinBox(); self.f_qty.setMinimum(1); self.f_qty.setMaximum(9999)
        self.f_qty.setFixedHeight(36); self.f_qty.setFixedWidth(80)
        self.f_price= QDoubleSpinBox(); self.f_price.setMaximum(999999)
        self.f_price.setDecimals(2); self.f_price.setPrefix("₱ ")
        self.f_price.setFixedHeight(36); self.f_price.setFixedWidth(120)
        self.f_price.setReadOnly(True)
        self.f_price.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.f_item.currentTextChanged.connect(self._auto_fill_price)

        btn_add_part = OrangeButton("Add Part")
        btn_add_part.clicked.connect(self._add_part)

        add_row.addWidget(QLabel("Item:")); add_row.addWidget(self.f_item, 1)
        add_row.addWidget(QLabel("Qty:")); add_row.addWidget(self.f_qty)
        add_row.addWidget(QLabel("Price:")); add_row.addWidget(self.f_price)
        add_row.addWidget(btn_add_part)
        layout.addLayout(add_row)

        # Parts table
        cols = ["Part Code/Name","Qty Used","Unit Price","Subtotal","Action"]
        self.parts_table = StyledTable(cols)
        self.parts_table.setColumnWidth(0, 200)
        self.parts_table.setColumnWidth(1, 70)
        self.parts_table.setColumnWidth(2, 100)
        self.parts_table.setColumnWidth(3, 100)
        self.parts_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.parts_table)

        # Total
        self.total_lbl = QLabel("Total Parts Cost: ₱0.00")
        self.total_lbl.setStyleSheet(
            f"font-size:14px;font-weight:700;color:{TEXT_DARK};"
            "background:#fff4e0;border:1px solid #f5c07a;border-radius:6px;padding:8px 12px;"
        )
        layout.addWidget(self.total_lbl)

        btn_close = GhostButton("Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

        self._auto_fill_price(self.f_item.currentText())
        self._load_existing_parts()

    def _auto_fill_price(self, label):
        data = self._inventory.get(label)
        if data:
            self.f_price.setValue(float(data[2]) if data[2] else 0)
        else:
            self.f_price.setValue(0)

    def _refresh_inventory_choices(self, preferred_item_id=None):
        self.f_item.blockSignals(True)
        self.f_item.clear()
        self.f_item.addItems(list(self._inventory.keys()))
        if preferred_item_id:
            for item_label, item_data in self._inventory.items():
                if item_data[0] == preferred_item_id:
                    self.f_item.setCurrentText(item_label)
                    break
        self.f_item.blockSignals(False)
        self._auto_fill_price(self.f_item.currentText())

    def _load_existing_parts(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            # Check table exists
            cur.execute("""
                SELECT EXISTS(SELECT 1 FROM information_schema.tables
                WHERE table_name='service_order_parts')
            """)
            if not cur.fetchone()[0]: conn.close(); return

            cur.execute("""
                SELECT sop.part_usage_id,
                       i.item_code||' — '||i.item_name,
                       sop.qty_used, sop.unit_price,
                       sop.qty_used*sop.unit_price AS subtotal
                FROM service_order_parts sop
                JOIN inventory i ON sop.item_id=i.item_id
                WHERE sop.order_id=%s
            """, (self.order_id,))
            rows = cur.fetchall(); conn.close()
            self.parts_table.setRowCount(0)
            total = 0
            for rd in rows:
                r = self.parts_table.rowCount()
                self.parts_table.insertRow(r)
                self.parts_table.setRowHeight(r, 36)
                for c, val in enumerate(rd[1:]):
                    text = f"₱{float(val):,.2f}" if c in (2,3) else str(val)
                    item = QTableWidgetItem(text)
                    item.setTextAlignment(
                        (Qt.AlignRight if c in (2,3) else Qt.AlignLeft) | Qt.AlignVCenter
                    )
                    self.parts_table.setItem(r, c, item)
                total += float(rd[4]) if rd[4] else 0

                # Remove button
                puid = rd[0]
                btn_r = QPushButton("Remove"); btn_r.setFixedHeight(27)
                btn_r.setCursor(Qt.PointingHandCursor)
                btn_r.setStyleSheet("QPushButton{background:#ffebee;color:#c62828;border:1px solid #ef9a9a;border-radius:5px;font-size:11px;padding:0 8px;}QPushButton:hover{background:#ffcdd2;}")
                btn_r.clicked.connect(lambda _, p=puid: self._remove_part(p))
                act = QWidget(); act.setStyleSheet("background:transparent;")
                al = QHBoxLayout(act); al.setContentsMargins(4,2,4,2); al.addWidget(btn_r)
                self.parts_table.setCellWidget(r, 4, act)

            self.total_lbl.setText(f"Total Parts Cost: ₱{total:,.2f}")
        except Exception as e:
            print(f"Parts load error: {e}")

    def _add_part(self):
        label = self.f_item.currentText()
        data  = self._inventory.get(label)
        if not data: return
        item_id, qty_avail, unit_price = data
        qty   = self.f_qty.value()
        price = float(unit_price) if unit_price else 0
        self.f_price.setValue(price)

        if qty > qty_avail:
            error(self, "Insufficient Stock",
                  f"Only {qty_avail} units available in inventory.")
            return
        try:
            conn = get_connection(); cur = conn.cursor()
            # Check table exists first
            cur.execute("""
                SELECT EXISTS(SELECT 1 FROM information_schema.tables
                WHERE table_name='service_order_parts')
            """)
            if not cur.fetchone()[0]:
                conn.close()
                error(self, "Setup Required",
                      "Please run db/migrate_v2.sql first to enable parts tracking.")
                return

            cur.execute("""
                INSERT INTO service_order_parts (order_id, item_id, qty_used, unit_price)
                VALUES (%s,%s,%s,%s)
            """, (self.order_id, item_id, qty, price))
            conn.commit(); conn.close()
            self._load_inventory()  # refresh stock counts
            self._refresh_inventory_choices(item_id)
            self._load_existing_parts()
            bus.inventory_changed.emit()
            bus.billing_changed.emit()
            bus.dashboard_refresh.emit()
        except Exception as e:
            error(self, "Error", str(e))

    def _remove_part(self, part_usage_id):
        if confirm(self, "Remove Part", "Remove this part from the order?\nInventory will be restored."):
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("DELETE FROM service_order_parts WHERE part_usage_id=%s",
                            (part_usage_id,))
                conn.commit(); conn.close()
                self._load_existing_parts()
                bus.inventory_changed.emit()
                bus.billing_changed.emit()
                bus.dashboard_refresh.emit()
            except Exception as e:
                error(self, "Error", str(e))
