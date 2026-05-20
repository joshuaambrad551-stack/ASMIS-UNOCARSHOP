"""
modules/customers.py
UnoCarshop ASMIS - Customers & Vehicles (Integrated v2)

Key changes:
- Vehicle make/model/year/color are FREE TEXT fields (no dropdowns)
- Fires customers_changed + vehicles_changed + dashboard_refresh
- Customer -> Vehicle -> Service history chain visible
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QDialog, QFormLayout, QDialogButtonBox,
    QTableWidgetItem, QPushButton, QLineEdit,
    QTextEdit, QSpinBox, QFrame, QDoubleSpinBox, QScrollArea
)
from PyQt5.QtCore import Qt
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.widgets import (
    OrangeButton, GhostButton, SearchBar, StyledTable,
    StatCard, status_item, confirm, info, error,
    PAGE_BG, ORANGE, BORDER, TEXT_DARK, TEXT_SOFT, GREEN, BLUE
)
from db.connection import get_connection
from db.events import bus

INSURANCE_PROVIDERS = [
    "Pioneer",
    "Western Guaranty Corporation",
    "Government Service Insurance System",
    "The Mercantile Insurance Co. Inc.",
    "CommonWealth Insurance Company",
    "Sterling Insurance Company Inc.",
    "Standard Insurance",
    "PhilBritish Insurance",
    "Milestone Gruaranty and Assurance Corp.",
    "Pacific Union Insurance Company",
    "Paramount Life & General Insurance",
    "Stronghold Insurance Company. Incorporated",
    "Visayan Surety & Insurance Corp.",
    "BPI MS Insurance Corporation",
    "PhilFirst Insurance Company Inc.",
    "Oona Insurance",
]


class CustomersPage(QWidget):
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

        stats = QHBoxLayout(); stats.setSpacing(12)
        self.s_cust = StatCard("Total Customers", "0", "?", ORANGE)
        self.s_veh  = StatCard("Total Vehicles",  "0", "?", BLUE)
        self.s_orders= StatCard("Active Orders",  "0", "?", GREEN)
        for s in [self.s_cust, self.s_veh, self.s_orders]:
            s.setFixedHeight(88); stats.addWidget(s)
        stats.addStretch()
        layout.addLayout(stats)

        layout.addWidget(self._build_customers_tab())

    def _build_customers_tab(self):
        w = QWidget(); w.setStyleSheet("background:white;")
        layout = QVBoxLayout(w); layout.setContentsMargins(16,16,16,16); layout.setSpacing(12)
        toolbar = QHBoxLayout()
        self.cust_search = SearchBar("Search customers...")
        self.cust_search.setFixedWidth(280)
        self.cust_search.textChanged.connect(self._filter_customers)
        btn_add = OrangeButton("?  Add Customer"); btn_add.clicked.connect(self._add_customer)
        btn_ref = GhostButton("Refresh");       btn_ref.clicked.connect(self.refresh)
        toolbar.addWidget(self.cust_search); toolbar.addStretch()
        btn_add = OrangeButton("Add Customer + Vehicle"); btn_add.clicked.connect(self._add_customer)
        toolbar.addWidget(btn_ref); toolbar.addWidget(btn_add)
        layout.addLayout(toolbar)
        cols = ["Code","Full Name","Phone","Email","Address","Vehicles","Actions"]
        self.cust_table = StyledTable(cols)
        self.cust_table.setColumnWidth(0, 90)
        self.cust_table.setColumnWidth(1, 150)
        self.cust_table.setColumnWidth(2, 120)
        self.cust_table.setColumnWidth(3, 160)
        self.cust_table.setColumnWidth(4, 160)
        self.cust_table.setColumnWidth(5, 75)
        self.cust_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.cust_table)
        self.cust_count = QLabel(""); self.cust_count.setStyleSheet(f"color:{TEXT_SOFT};font-size:12px;")
        layout.addWidget(self.cust_count)
        return w

    def _build_vehicles_tab(self):
        w = QWidget(); w.setStyleSheet("background:white;")
        layout = QVBoxLayout(w); layout.setContentsMargins(16,16,16,16); layout.setSpacing(12)
        toolbar = QHBoxLayout()
        self.veh_search = SearchBar("Search by plate, brand, model, owner...")
        self.veh_search.setFixedWidth(300)
        self.veh_search.textChanged.connect(self._filter_vehicles)
        btn_add = OrangeButton("?  Add Vehicle"); btn_add.clicked.connect(self._add_vehicle)
        btn_ref = GhostButton("Refresh");      btn_ref.clicked.connect(self.refresh)
        toolbar.addWidget(self.veh_search); toolbar.addStretch()
        toolbar.addWidget(btn_ref); toolbar.addWidget(btn_add)
        layout.addLayout(toolbar)
        cols = ["Plate No.","Owner","Brand","Model","Year","Color","Actions"]
        self.veh_table = StyledTable(cols)
        self.veh_table.setColumnWidth(0, 100)
        self.veh_table.setColumnWidth(1, 150)
        self.veh_table.setColumnWidth(2, 100)
        self.veh_table.setColumnWidth(3, 100)
        self.veh_table.setColumnWidth(4, 55)
        self.veh_table.setColumnWidth(5, 80)
        self.veh_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.veh_table)
        self.veh_count = QLabel(""); self.veh_count.setStyleSheet(f"color:{TEXT_SOFT};font-size:12px;")
        layout.addWidget(self.veh_count)
        return w

    def refresh(self):
        self._load_customers()
        self._update_stats()

    def _update_stats(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM customers")
            self.s_cust.set_value(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM vehicles")
            self.s_veh.set_value(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM service_orders WHERE status IN ('Pending','In Progress')")
            self.s_orders.set_value(cur.fetchone()[0])
            conn.close()
        except: pass

    def _load_customers(self, search=""):
        try:
            conn = get_connection(); cur = conn.cursor()
            q = """
                SELECT c.cust_id, c.cust_code, c.full_name, c.phone, c.email, c.address,
                       COUNT(v.vehicle_id) AS vehicle_count
                FROM customers c
                LEFT JOIN vehicles v ON c.cust_id=v.cust_id
                WHERE 1=1
            """
            params = []
            if search:
                q += " AND (LOWER(c.full_name) LIKE %s OR c.cust_code LIKE %s OR c.phone LIKE %s)"
                s = f"%{search.lower()}%"; params += [s, s, s]
            q += " GROUP BY c.cust_id, c.cust_code, c.full_name, c.phone, c.email, c.address ORDER BY c.cust_code"
            cur.execute(q, params)
            rows = cur.fetchall(); conn.close()

            self.cust_table.setRowCount(0)
            self._cust_ids = []
            for rd in rows:
                r = self.cust_table.rowCount()
                self.cust_table.insertRow(r); self.cust_table.setRowHeight(r, 38)
                self._cust_ids.append(rd[0])
                for c, val in enumerate(rd[1:7]):
                    item = QTableWidgetItem(str(val) if val else "")
                    item.setTextAlignment(
                        (Qt.AlignCenter if c == 5 else Qt.AlignLeft) | Qt.AlignVCenter
                    )
                    self.cust_table.setItem(r, c, item)

                cid = rd[0]
                act = QWidget(); act.setStyleSheet("background:transparent;")
                al = QHBoxLayout(act); al.setContentsMargins(4,2,4,2); al.setSpacing(4)
                btn_e = QPushButton("Edit"); btn_e.setFixedHeight(27); btn_e.setCursor(Qt.PointingHandCursor)
                btn_e.setStyleSheet("QPushButton{background:#e7eef8;color:#123a63;border:1px solid #8aa4c4;border-radius:5px;font-size:11px;padding:0 8px;}QPushButton:hover{background:#dbe9ff;}")
                btn_e.clicked.connect(lambda _, c_=cid: self._edit_customer(c_))
                btn_v = QPushButton("Vehicles"); btn_v.setFixedHeight(27); btn_v.setCursor(Qt.PointingHandCursor)
                btn_v.setStyleSheet("QPushButton{background:#e8f4ff;color:#1976d2;border:1px solid #90caf9;border-radius:5px;font-size:11px;padding:0 8px;}QPushButton:hover{background:#d3eafd;}")
                btn_v.clicked.connect(lambda _, c_=cid: self._show_customer_vehicles(c_))
                btn_d = QPushButton("Del"); btn_d.setFixedHeight(27); btn_d.setCursor(Qt.PointingHandCursor)
                btn_d.setStyleSheet("QPushButton{background:#ffebee;color:#c62828;border:1px solid #ef9a9a;border-radius:5px;font-size:11px;padding:0 8px;}QPushButton:hover{background:#ffcdd2;}")
                btn_d.clicked.connect(lambda _, c_=cid: self._delete_customer(c_))
                al.addWidget(btn_v); al.addWidget(btn_e); al.addWidget(btn_d)
                self.cust_table.setCellWidget(r, 6, act)

            self.cust_count.setText(f"Showing {len(rows)} customer(s)")
        except Exception as e:
            error(self, "Load Error", str(e))

    def _load_vehicles(self, search=""):
        try:
            conn = get_connection(); cur = conn.cursor()
            q = """
                SELECT v.vehicle_id, v.plate_no, c.full_name,
                       COALESCE(v.make,''), COALESCE(v.model,''),
                       COALESCE(CAST(v.year AS TEXT),''),
                       COALESCE(v.color,'')
                FROM vehicles v JOIN customers c ON v.cust_id=c.cust_id
                WHERE 1=1
            """
            params = []
            if search:
                q += " AND (LOWER(v.plate_no) LIKE %s OR LOWER(v.make) LIKE %s OR LOWER(v.model) LIKE %s OR LOWER(c.full_name) LIKE %s)"
                s = f"%{search.lower()}%"; params += [s, s, s, s]
            q += " ORDER BY v.plate_no"
            cur.execute(q, params)
            rows = cur.fetchall(); conn.close()

            self.veh_table.setRowCount(0)
            self._veh_ids = []
            for rd in rows:
                r = self.veh_table.rowCount()
                self.veh_table.insertRow(r); self.veh_table.setRowHeight(r, 38)
                self._veh_ids.append(rd[0])
                for c, val in enumerate(rd[1:7]):
                    item = QTableWidgetItem(str(val) if val else "")
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    self.veh_table.setItem(r, c, item)

                vid = rd[0]
                act = QWidget(); act.setStyleSheet("background:transparent;")
                al = QHBoxLayout(act); al.setContentsMargins(4,2,4,2); al.setSpacing(4)
                btn_e = QPushButton("Edit"); btn_e.setFixedHeight(27); btn_e.setCursor(Qt.PointingHandCursor)
                btn_e.setStyleSheet("QPushButton{background:#e7eef8;color:#123a63;border:1px solid #8aa4c4;border-radius:5px;font-size:11px;padding:0 8px;}QPushButton:hover{background:#dbe9ff;}")
                btn_e.clicked.connect(lambda _, v_=vid: self._edit_vehicle(v_))
                btn_d = QPushButton("Del"); btn_d.setFixedHeight(27); btn_d.setCursor(Qt.PointingHandCursor)
                btn_d.setStyleSheet("QPushButton{background:#ffebee;color:#c62828;border:1px solid #ef9a9a;border-radius:5px;font-size:11px;padding:0 8px;}QPushButton:hover{background:#ffcdd2;}")
                btn_d.clicked.connect(lambda _, v_=vid: self._delete_vehicle(v_))
                al.addWidget(btn_e); al.addWidget(btn_d)
                self.veh_table.setCellWidget(r, 6, act)

            self.veh_count.setText(f"Showing {len(rows)} vehicle(s)")
        except Exception as e:
            error(self, "Load Error", str(e))

    def _filter_customers(self): self._load_customers(self.cust_search.text())
    def _filter_vehicles(self):  self._load_vehicles(self.veh_search.text())

    # â”€â”€ Customer CRUD â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _add_customer(self):
        dlg = CustomerVehicleDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            cust_data, vehicle_data = dlg.get_data()
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute(
                    """INSERT INTO customers
                       (cust_code,first_name,last_name,phone,email,address,
                        payment_type,coverage_type,insurance_provider,loa_amount,assured_share)
                       VALUES (
                        ('TMP-' || SUBSTRING(MD5(RANDOM()::TEXT || CLOCK_TIMESTAMP()::TEXT), 1, 10)),
                        %s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                       )
                       RETURNING cust_id""",
                    cust_data
                )
                cust_id = cur.fetchone()[0]
                cur.execute(
                    "UPDATE customers SET cust_code=('CUST-' || LPAD(%s::TEXT, 3, '0')) WHERE cust_id=%s",
                    (cust_id, cust_id)
                )
                cur.execute(
                    "INSERT INTO vehicles (cust_id,plate_no,make,model,year,color) VALUES (%s,%s,%s,%s,%s,%s)",
                    (cust_id,) + vehicle_data
                )
                conn.commit(); conn.close()
                info(self, "Saved", "Customer and vehicle added.")
                self.refresh()
                bus.customers_changed.emit()
                bus.vehicles_changed.emit()
                bus.dashboard_refresh.emit()
            except Exception as e: error(self, "Error", str(e))

    def _edit_customer(self, cust_id):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("""SELECT first_name,last_name,phone,email,address,
                                  COALESCE(payment_type,'Cash'),
                                  COALESCE(coverage_type,'Own Damage'),
                                  COALESCE(insurance_provider,''),
                                  COALESCE(loa_amount,0),
                                  COALESCE(assured_share,0)
                           FROM customers WHERE cust_id=%s""", (cust_id,))
            row = cur.fetchone(); conn.close()
        except Exception as e: error(self, "Error", str(e)); return
        dlg = CustomerDialog(self, row)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("""UPDATE customers
                               SET first_name=%s,last_name=%s,phone=%s,email=%s,address=%s,
                                   payment_type=%s,coverage_type=%s,insurance_provider=%s,
                                   loa_amount=%s,assured_share=%s
                               WHERE cust_id=%s""", data+(cust_id,))
                conn.commit(); conn.close()
                info(self, "Updated", "Customer updated.")
                self.refresh()
                bus.customers_changed.emit()
                bus.dashboard_refresh.emit()
            except Exception as e: error(self, "Error", str(e))

    def _delete_customer(self, cust_id):
        if confirm(self, "Delete", "Delete this customer and all their vehicles?"):
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("""
                    SELECT
                        (SELECT COUNT(*) FROM service_orders WHERE cust_id=%s),
                        (SELECT COUNT(*) FROM billing WHERE cust_id=%s AND status!='Void')
                """, (cust_id, cust_id))
                order_count, billing_count = cur.fetchone()
                if order_count or billing_count:
                    conn.close()
                    error(
                        self,
                        "Cannot Delete Customer",
                        "This customer is still linked to "
                        f"{order_count} service order(s) and {billing_count} bill(s). "
                        "Delete or reassign those records first."
                    )
                    return
                cur.execute("DELETE FROM customers WHERE cust_id=%s", (cust_id,))
                conn.commit(); conn.close()
                self.refresh()
                bus.customers_changed.emit()
                bus.dashboard_refresh.emit()
            except Exception as e: error(self, "Error", str(e))

    # â”€â”€ Vehicle CRUD â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _show_customer_vehicles(self, cust_id):
        dlg = CustomerVehiclesDialog(self, cust_id)
        dlg.exec_()
        self.refresh()

    def _add_vehicle_for_customer(self, cust_id):
        dlg = VehicleDialog(self, owner_id=cust_id, lock_owner=True)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("INSERT INTO vehicles (cust_id,plate_no,make,model,year,color) VALUES (%s,%s,%s,%s,%s,%s)", data)
                conn.commit(); conn.close()
                info(self, "Saved", "Vehicle added.")
                self.refresh()
                bus.vehicles_changed.emit()
                bus.dashboard_refresh.emit()
            except Exception as e: error(self, "Error", str(e))

    def _edit_vehicle_for_customer(self, vehicle_id, cust_id):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT cust_id,plate_no,make,model,year,color FROM vehicles WHERE vehicle_id=%s AND cust_id=%s", (vehicle_id, cust_id))
            row = cur.fetchone(); conn.close()
        except Exception as e: error(self, "Error", str(e)); return
        if not row:
            error(self, "Error", "Vehicle not found for this customer.")
            return
        dlg = VehicleDialog(self, row, owner_id=cust_id, lock_owner=True)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("UPDATE vehicles SET cust_id=%s,plate_no=%s,make=%s,model=%s,year=%s,color=%s WHERE vehicle_id=%s", data+(vehicle_id,))
                conn.commit(); conn.close()
                info(self, "Updated", "Vehicle updated.")
                self.refresh()
                bus.vehicles_changed.emit()
                bus.dashboard_refresh.emit()
            except Exception as e: error(self, "Error", str(e))

    def _add_vehicle(self):
        dlg = VehicleDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("INSERT INTO vehicles (cust_id,plate_no,make,model,year,color) VALUES (%s,%s,%s,%s,%s,%s)", data)
                conn.commit(); conn.close()
                info(self, "Saved", "Vehicle added.")
                self.refresh()
                bus.vehicles_changed.emit()
                bus.dashboard_refresh.emit()
            except Exception as e: error(self, "Error", str(e))

    def _edit_vehicle(self, vehicle_id):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT cust_id,plate_no,make,model,year,color FROM vehicles WHERE vehicle_id=%s", (vehicle_id,))
            row = cur.fetchone(); conn.close()
        except Exception as e: error(self, "Error", str(e)); return
        dlg = VehicleDialog(self, row)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("UPDATE vehicles SET cust_id=%s,plate_no=%s,make=%s,model=%s,year=%s,color=%s WHERE vehicle_id=%s", data+(vehicle_id,))
                conn.commit(); conn.close()
                info(self, "Updated", "Vehicle updated.")
                self.refresh()
                bus.vehicles_changed.emit()
                bus.dashboard_refresh.emit()
            except Exception as e: error(self, "Error", str(e))

    def _delete_vehicle(self, vehicle_id):
        if confirm(self, "Delete", "Delete this vehicle?"):
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("""
                    SELECT
                        (SELECT COUNT(*) FROM service_orders WHERE vehicle_id=%s)
                """, (vehicle_id,))
                order_count = cur.fetchone()[0]
                if order_count:
                    conn.close()
                    error(
                        self,
                        "Cannot Delete Vehicle",
                        "This vehicle is still linked to "
                        f"{order_count} service order(s). "
                        "Delete or reassign those records first."
                    )
                    return
                cur.execute("DELETE FROM vehicles WHERE vehicle_id=%s", (vehicle_id,))
                conn.commit(); conn.close()
                self.refresh()
                bus.vehicles_changed.emit()
                bus.dashboard_refresh.emit()
            except Exception as e: error(self, "Error", str(e))


class CustomerDialog(QDialog):
    def __init__(self, parent, existing=None):
        super().__init__(parent)
        self.setWindowTitle("Customer")
        self.resize(760, 700)
        self.setMinimumSize(700, 640)
        self.setStyleSheet("QDialog{background:#f3f6fb;font-family:'Segoe UI';}"
                           "QLineEdit,QTextEdit,QComboBox,QDoubleSpinBox{border:1px solid #d7dee8;border-radius:7px;padding:6px 10px;font-size:13px;background:white;}")
        layout = QVBoxLayout(self); layout.setContentsMargins(28,22,28,22)
        form = QFormLayout(); form.setSpacing(14); form.setLabelAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.f_first = QLineEdit(existing[0] if existing else "")
        self.f_last  = QLineEdit(existing[1] if existing else "")
        self.f_phone = QLineEdit(existing[2] if existing and existing[2] else "")
        self.f_email = QLineEdit(existing[3] if existing and existing[3] else "")
        self.f_addr  = QTextEdit(existing[4] if existing and existing[4] else ""); self.f_addr.setFixedHeight(90)
        self.f_payment = QComboBox(); self.f_payment.addItems(["Cash", "Insurance"])
        self.f_payment.setCurrentText(existing[5] if existing and existing[5] else "Cash")
        self.f_coverage = QComboBox(); self.f_coverage.addItems(["Own Damage", "Property Damage"])
        self.f_coverage.setCurrentText(existing[6] if existing and existing[6] else "Own Damage")
        self.f_provider = QComboBox(); self.f_provider.addItems(INSURANCE_PROVIDERS)
        if existing and existing[7]:
            self.f_provider.setCurrentText(existing[7])
        self.f_loa = QDoubleSpinBox(); self.f_loa.setMaximum(99999999); self.f_loa.setDecimals(2)
        self.f_loa.setPrefix("PHP "); self.f_loa.setValue(float(existing[8]) if existing else 0)
        self.f_assured = QDoubleSpinBox(); self.f_assured.setMaximum(99999999); self.f_assured.setDecimals(2)
        self.f_assured.setPrefix("PHP "); self.f_assured.setValue(float(existing[9]) if existing else 0)
        form.addRow("First Name *", self.f_first)
        form.addRow("Last Name *",  self.f_last)
        form.addRow("Phone",        self.f_phone)
        form.addRow("Email",        self.f_email)
        form.addRow("Address",      self.f_addr)
        form.addRow("Payment Type *", self.f_payment)
        form.addRow("Coverage *", self.f_coverage)
        self.provider_label = QLabel("Insurance *")
        self.loa_label = QLabel("Letter of Authority Amount *")
        self.assured_label = QLabel("Assured Share *")
        form.addRow(self.provider_label, self.f_provider)
        form.addRow(self.loa_label, self.f_loa)
        form.addRow(self.assured_label, self.f_assured)
        layout.addLayout(form)
        self.f_payment.currentTextChanged.connect(self._toggle_insurance_fields)
        self._toggle_insurance_fields()
        btns = QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Save).setStyleSheet("background:#0b1f3a;color:white;border:none;border-radius:6px;padding:6px 18px;font-weight:700;")
        btns.button(QDialogButtonBox.Cancel).setStyleSheet("background:#eee;color:#555;border:none;border-radius:6px;padding:6px 14px;")
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def accept(self):
        if not self.f_first.text().strip() or not self.f_last.text().strip():
            error(self, "Validation", "First name and last name are required.")
            return
        if self.f_payment.currentText() == "Insurance":
            if not self.f_provider.currentText().strip():
                error(self, "Validation", "Insurance provider is required.")
                return
        super().accept()

    def get_data(self):
        is_insured = self.f_payment.currentText() == "Insurance"
        return (self.f_first.text().strip(),
                self.f_last.text().strip(), self.f_phone.text().strip(),
                self.f_email.text().strip(), self.f_addr.toPlainText().strip(),
                self.f_payment.currentText().strip(),
                self.f_coverage.currentText().strip(),
                (self.f_provider.currentText().strip() if is_insured else None),
                (self.f_loa.value() if is_insured else 0),
                (self.f_assured.value() if is_insured else 0))

    def _toggle_insurance_fields(self):
        insured = self.f_payment.currentText() == "Insurance"
        self.provider_label.setVisible(insured); self.f_provider.setVisible(insured)
        self.loa_label.setVisible(insured); self.f_loa.setVisible(insured)
        self.assured_label.setVisible(insured); self.f_assured.setVisible(insured)


class CustomerVehicleDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Add Customer and Vehicle")
        self.resize(980, 820)
        self.setMinimumSize(900, 760)
        self.setStyleSheet("QDialog{background:#f3f6fb;font-family:'Segoe UI';}"
                           "QLineEdit,QTextEdit,QSpinBox,QComboBox,QDoubleSpinBox{border:1px solid #d7dee8;border-radius:8px;padding:9px 12px;font-size:15px;background:white;min-height:40px;}"
                           "QLabel{font-size:15px;color:#3b362f;}")
        layout = QVBoxLayout(self); layout.setContentsMargins(20,16,20,16); layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 12, 16, 12)
        content_layout.setSpacing(18)

        section_customer = QLabel("Customer")
        section_customer.setStyleSheet("font-size:18px;font-weight:700;color:#0b1f3a;")
        content_layout.addWidget(section_customer)
        cust_form = QFormLayout(); cust_form.setSpacing(16); cust_form.setLabelAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.f_first = QLineEdit()
        self.f_last  = QLineEdit()
        self.f_phone = QLineEdit()
        self.f_email = QLineEdit()
        self.f_addr  = QTextEdit(); self.f_addr.setFixedHeight(120)
        self.f_payment = QComboBox(); self.f_payment.addItems(["Cash", "Insurance"])
        self.f_coverage = QComboBox(); self.f_coverage.addItems(["Own Damage", "Property Damage"])
        self.f_provider = QComboBox(); self.f_provider.addItems(INSURANCE_PROVIDERS)
        self.f_loa = QDoubleSpinBox(); self.f_loa.setMaximum(99999999); self.f_loa.setDecimals(2); self.f_loa.setPrefix("PHP ")
        self.f_assured = QDoubleSpinBox(); self.f_assured.setMaximum(99999999); self.f_assured.setDecimals(2); self.f_assured.setPrefix("PHP ")
        cust_form.addRow("First Name *", self.f_first)
        cust_form.addRow("Last Name *",  self.f_last)
        cust_form.addRow("Phone",        self.f_phone)
        cust_form.addRow("Email",        self.f_email)
        cust_form.addRow("Address",      self.f_addr)
        cust_form.addRow("Payment Type *", self.f_payment)
        cust_form.addRow("Coverage *", self.f_coverage)
        self.provider_label = QLabel("Insurance *")
        self.loa_label = QLabel("Letter of Authority Amount *")
        self.assured_label = QLabel("Assured Share *")
        cust_form.addRow(self.provider_label, self.f_provider)
        cust_form.addRow(self.loa_label, self.f_loa)
        cust_form.addRow(self.assured_label, self.f_assured)
        content_layout.addLayout(cust_form)
        self.f_payment.currentTextChanged.connect(self._toggle_insurance_fields)
        self._toggle_insurance_fields()

        section_vehicle = QLabel("Vehicle")
        section_vehicle.setStyleSheet("font-size:18px;font-weight:700;color:#0b1f3a;")
        content_layout.addWidget(section_vehicle)
        veh_form = QFormLayout(); veh_form.setSpacing(16); veh_form.setLabelAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.f_plate = QLineEdit()
        self.f_make  = QLineEdit(); self.f_make.setPlaceholderText("e.g. Toyota, Honda, Ford")
        self.f_model = QLineEdit(); self.f_model.setPlaceholderText("e.g. Fortuner, Civic, Ranger")
        self.f_year  = QSpinBox(); self.f_year.setRange(1900,2030); self.f_year.setValue(2020)
        self.f_color = QLineEdit()
        veh_form.addRow("Plate No. *", self.f_plate)
        veh_form.addRow("Brand",       self.f_make)
        veh_form.addRow("Model",       self.f_model)
        veh_form.addRow("Year",        self.f_year)
        veh_form.addRow("Color",       self.f_color)
        content_layout.addLayout(veh_form)

        scroll.setWidget(content)
        layout.addWidget(scroll)

        btns = QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Save).setStyleSheet("background:#0b1f3a;color:white;border:none;border-radius:6px;padding:6px 18px;font-weight:700;")
        btns.button(QDialogButtonBox.Cancel).setStyleSheet("background:#eee;color:#555;border:none;border-radius:6px;padding:6px 14px;")
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def accept(self):
        if not self.f_first.text().strip() or not self.f_last.text().strip():
            error(self, "Validation", "First name and last name are required.")
            return
        if not self.f_plate.text().strip():
            error(self, "Validation", "Plate number is required.")
            return
        if self.f_payment.currentText() == "Insurance":
            if not self.f_provider.currentText().strip():
                error(self, "Validation", "Insurance provider is required.")
                return
        super().accept()

    def get_data(self):
        is_insured = self.f_payment.currentText() == "Insurance"
        customer = (
            self.f_first.text().strip(),
            self.f_last.text().strip(),
            self.f_phone.text().strip(),
            self.f_email.text().strip(),
            self.f_addr.toPlainText().strip(),
            self.f_payment.currentText().strip(),
            self.f_coverage.currentText().strip(),
            (self.f_provider.currentText().strip() if is_insured else None),
            (self.f_loa.value() if is_insured else 0),
            (self.f_assured.value() if is_insured else 0)
        )
        vehicle = (
            self.f_plate.text().strip(),
            self.f_make.text().strip(),
            self.f_model.text().strip(),
            self.f_year.value(),
            self.f_color.text().strip()
        )
        return customer, vehicle

    def _toggle_insurance_fields(self):
        insured = self.f_payment.currentText() == "Insurance"
        self.provider_label.setVisible(insured); self.f_provider.setVisible(insured)
        self.loa_label.setVisible(insured); self.f_loa.setVisible(insured)
        self.assured_label.setVisible(insured); self.f_assured.setVisible(insured)


class VehicleDialog(QDialog):
    """Vehicle dialog - all fields are FREE TEXT (no dropdowns for make/model)."""
    def __init__(self, parent, existing=None, owner_id=None, lock_owner=False):
        super().__init__(parent)
        self.setWindowTitle("Vehicle")
        self.resize(640, 520)
        self.setMinimumSize(600, 480)
        self.setStyleSheet("QDialog{background:#f3f6fb;font-family:'Segoe UI';}"
                           "QLineEdit,QComboBox,QSpinBox{border:1px solid #d7dee8;border-radius:7px;padding:6px 10px;font-size:13px;background:white;}")
        self._customers = {}
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT cust_id, cust_code||' - '||full_name FROM customers ORDER BY cust_code")
            self._customers = {r[1]: r[0] for r in cur.fetchall()}; conn.close()
        except: pass

        layout = QVBoxLayout(self); layout.setContentsMargins(28,22,28,22)
        form = QFormLayout(); form.setSpacing(14); form.setLabelAlignment(Qt.AlignRight|Qt.AlignVCenter)

        self.f_cust  = QComboBox(); self.f_cust.addItems(list(self._customers.keys()))
        selected_owner = owner_id if owner_id else (existing[0] if existing else None)
        if selected_owner:
            for label, cid in self._customers.items():
                if cid == selected_owner: self.f_cust.setCurrentText(label); break
        self.f_cust.setEnabled(not lock_owner)

        # All free-text fields
        self.f_plate = QLineEdit(existing[1] if existing else "")
        self.f_make  = QLineEdit(existing[2] if existing and existing[2] else "")
        self.f_make.setPlaceholderText("e.g. Toyota, Honda, Ford...")
        self.f_model = QLineEdit(existing[3] if existing and existing[3] else "")
        self.f_model.setPlaceholderText("e.g. Fortuner, Civic, Ranger...")
        self.f_year  = QSpinBox(); self.f_year.setRange(1900,2030)
        self.f_year.setValue(int(existing[4]) if existing and existing[4] else 2020)
        self.f_color = QLineEdit(existing[5] if existing and existing[5] else "")
        self.f_color.setPlaceholderText("e.g. White, Black, Silver...")

        form.addRow("Owner *",     self.f_cust)
        form.addRow("Plate No. *", self.f_plate)
        form.addRow("Brand",       self.f_make)
        form.addRow("Model",       self.f_model)
        form.addRow("Year",        self.f_year)
        form.addRow("Color",       self.f_color)
        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Save).setStyleSheet("background:#0b1f3a;color:white;border:none;border-radius:6px;padding:6px 18px;font-weight:700;")
        btns.button(QDialogButtonBox.Cancel).setStyleSheet("background:#eee;color:#555;border:none;border-radius:6px;padding:6px 14px;")
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_data(self):
        cid = self._customers.get(self.f_cust.currentText())
        return (cid, self.f_plate.text().strip(), self.f_make.text().strip(),
                self.f_model.text().strip(), self.f_year.value(),
                self.f_color.text().strip())


class CustomerVehiclesDialog(QDialog):
    def __init__(self, parent, cust_id):
        super().__init__(parent)
        self.page = parent
        self.cust_id = cust_id
        self.setWindowTitle("Customer Vehicles")
        self.setFixedSize(780, 460)
        self.setStyleSheet("QDialog{background:#f3f6fb;font-family:'Segoe UI';}")

        layout = QVBoxLayout(self); layout.setContentsMargins(18,16,18,16); layout.setSpacing(12)
        self.title = QLabel("")
        self.title.setStyleSheet(f"font-size:16px;font-weight:700;color:{TEXT_DARK};")
        layout.addWidget(self.title)

        toolbar = QHBoxLayout()
        self.count = QLabel("")
        self.count.setStyleSheet(f"color:{TEXT_SOFT};font-size:12px;")
        btn_add = OrangeButton("Add Vehicle")
        btn_add.clicked.connect(self._add_vehicle)
        btn_close = GhostButton("Close")
        btn_close.clicked.connect(self.accept)
        toolbar.addWidget(self.count); toolbar.addStretch()
        toolbar.addWidget(btn_close); toolbar.addWidget(btn_add)
        layout.addLayout(toolbar)

        self.table = StyledTable(["Plate No.","Brand","Model","Year","Color","Actions"])
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 60)
        self.table.setColumnWidth(4, 90)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        self._load()

    def _load(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT cust_code, full_name FROM customers WHERE cust_id=%s", (self.cust_id,))
            customer = cur.fetchone()
            cur.execute("""
                SELECT vehicle_id, plate_no, COALESCE(make,''), COALESCE(model,''),
                       COALESCE(CAST(year AS TEXT),''), COALESCE(color,'')
                FROM vehicles
                WHERE cust_id=%s
                ORDER BY plate_no
            """, (self.cust_id,))
            rows = cur.fetchall(); conn.close()
        except Exception as e:
            error(self, "Load Error", str(e))
            return

        name = f"{customer[0]} - {customer[1]}" if customer else "Customer"
        self.title.setText(f"Vehicles for {name}")
        self.table.setRowCount(0)
        for rd in rows:
            r = self.table.rowCount()
            self.table.insertRow(r); self.table.setRowHeight(r, 38)
            for c, val in enumerate(rd[1:6]):
                item = QTableWidgetItem(str(val) if val else "")
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.table.setItem(r, c, item)

            vehicle_id = rd[0]
            act = QWidget(); act.setStyleSheet("background:transparent;")
            al = QHBoxLayout(act); al.setContentsMargins(4,2,4,2); al.setSpacing(4)
            btn_e = QPushButton("Edit"); btn_e.setFixedHeight(27); btn_e.setCursor(Qt.PointingHandCursor)
            btn_e.setStyleSheet("QPushButton{background:#e7eef8;color:#123a63;border:1px solid #8aa4c4;border-radius:5px;font-size:11px;padding:0 8px;}QPushButton:hover{background:#dbe9ff;}")
            btn_e.clicked.connect(lambda _, v_=vehicle_id: self._edit_vehicle(v_))
            btn_d = QPushButton("Del"); btn_d.setFixedHeight(27); btn_d.setCursor(Qt.PointingHandCursor)
            btn_d.setStyleSheet("QPushButton{background:#ffebee;color:#c62828;border:1px solid #ef9a9a;border-radius:5px;font-size:11px;padding:0 8px;}QPushButton:hover{background:#ffcdd2;}")
            btn_d.clicked.connect(lambda _, v_=vehicle_id: self._delete_vehicle(v_))
            al.addWidget(btn_e); al.addWidget(btn_d)
            self.table.setCellWidget(r, 5, act)
        self.count.setText(f"{len(rows)} vehicle(s)")

    def _add_vehicle(self):
        self.page._add_vehicle_for_customer(self.cust_id)
        self._load()

    def _edit_vehicle(self, vehicle_id):
        self.page._edit_vehicle_for_customer(vehicle_id, self.cust_id)
        self._load()

    def _delete_vehicle(self, vehicle_id):
        self.page._delete_vehicle(vehicle_id)
        self._load()

