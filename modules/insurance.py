"""
modules/insurance.py
UnoCarshop ASMIS - Insurance (Integrated v2)
Fires insurance_changed + dashboard_refresh on all CRUD
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QDialog, QFormLayout, QDialogButtonBox,
    QTableWidgetItem, QPushButton, QLineEdit,
    QTextEdit, QDateEdit, QDoubleSpinBox
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


class InsurancePage(QWidget):
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
        self.s_active  = StatCard("Active Policies",  "0", "?", GREEN)
        self.s_expired = StatCard("Expired Policies", "0", "?",  RED)
        self.s_expiring= StatCard("Expiring (30 days)","0","?", ORANGE)
        self.s_total   = StatCard("Total Policies",   "0", "?", BLUE)
        for s in [self.s_active, self.s_expired, self.s_expiring, self.s_total]:
            s.setFixedHeight(88); stats.addWidget(s)
        layout.addLayout(stats)

        toolbar = QHBoxLayout()
        self.search = SearchBar("Search policy #, provider, customer...")
        self.search.setFixedWidth(300)
        self.search.textChanged.connect(self._filter)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["All Status","Active","Expired","Cancelled"])
        self.status_filter.setFixedHeight(38); self.status_filter.setFixedWidth(140)
        self.status_filter.setStyleSheet(self._cs())
        self.status_filter.currentIndexChanged.connect(self._filter)

        btn_add = OrangeButton("?  Add Policy"); btn_add.clicked.connect(self._add_policy)
        btn_ref = GhostButton("Refresh");    btn_ref.clicked.connect(self.refresh)

        toolbar.addWidget(self.search); toolbar.addWidget(self.status_filter)
        toolbar.addStretch(); toolbar.addWidget(btn_ref); toolbar.addWidget(btn_add)
        layout.addLayout(toolbar)

        cols = ["Policy #","Customer","Vehicle","Provider",
                "Coverage","Start Date","End Date","Premium","Status","Actions"]
        self.table = StyledTable(cols)
        for i, w in enumerate([110,130,130,120,120,90,90,90,80]):
            self.table.setColumnWidth(i, w)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet(f"color:{TEXT_SOFT};font-size:12px;")
        layout.addWidget(self.count_lbl)

    def refresh(self):
        self._update_stats()
        self._load_policies()

    def _update_stats(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM insurance WHERE status='Active'")
            self.s_active.set_value(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM insurance WHERE status='Expired'")
            self.s_expired.set_value(cur.fetchone()[0])
            cur.execute("""SELECT COUNT(*) FROM insurance
                WHERE status='Active' AND end_date BETWEEN CURRENT_DATE AND CURRENT_DATE+30""")
            self.s_expiring.set_value(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM insurance")
            self.s_total.set_value(cur.fetchone()[0])
            conn.close()
        except: pass

    def _load_policies(self, search="", status=""):
        try:
            conn = get_connection(); cur = conn.cursor()
            q = """
                SELECT i.ins_id, i.policy_no, c.full_name,
                       v.plate_no||' '||COALESCE(v.make,'')||' '||COALESCE(v.model,''),
                       i.provider, COALESCE(i.coverage,''),
                       i.start_date, i.end_date, i.premium, i.status
                FROM insurance i
                JOIN customers c ON i.cust_id=c.cust_id
                JOIN vehicles v ON i.vehicle_id=v.vehicle_id
                WHERE 1=1
            """
            params = []
            if search:
                q += " AND (LOWER(i.policy_no) LIKE %s OR LOWER(i.provider) LIKE %s OR LOWER(c.full_name) LIKE %s)"
                s = f"%{search.lower()}%"; params += [s, s, s]
            if status and status != "All Status":
                q += " AND i.status=%s"; params.append(status)
            q += " ORDER BY i.end_date"
            cur.execute(q, params); rows = cur.fetchall(); conn.close()

            self.table.setRowCount(0)
            self._ins_ids = []
            for rd in rows:
                r = self.table.rowCount(); self.table.insertRow(r)
                self.table.setRowHeight(r, 38)
                self._ins_ids.append(rd[0])
                data = [rd[1], rd[2], rd[3], rd[4], rd[5],
                        str(rd[6]) if rd[6] else "",
                        str(rd[7]) if rd[7] else "",
                        f"PHP {float(rd[8]):,.2f}"]
                for c, val in enumerate(data):
                    item = QTableWidgetItem(str(val))
                    item.setTextAlignment(
                        (Qt.AlignRight if c == 7 else Qt.AlignLeft) | Qt.AlignVCenter
                    )
                    self.table.setItem(r, c, item)
                self.table.setItem(r, 8, status_item(rd[9]))

                iid = rd[0]
                act = QWidget(); act.setStyleSheet("background:transparent;")
                al = QHBoxLayout(act); al.setContentsMargins(4,2,4,2); al.setSpacing(4)
                btn_e = QPushButton("Edit"); btn_e.setFixedHeight(27); btn_e.setCursor(Qt.PointingHandCursor)
                btn_e.setStyleSheet("QPushButton{background:#e7eef8;color:#123a63;border:1px solid #8aa4c4;border-radius:5px;font-size:11px;padding:0 8px;}QPushButton:hover{background:#dbe9ff;}")
                btn_e.clicked.connect(lambda _, i=iid: self._edit_policy(i))
                btn_d = QPushButton("Del"); btn_d.setFixedHeight(27); btn_d.setCursor(Qt.PointingHandCursor)
                btn_d.setStyleSheet("QPushButton{background:#ffebee;color:#c62828;border:1px solid #ef9a9a;border-radius:5px;font-size:11px;padding:0 8px;}QPushButton:hover{background:#ffcdd2;}")
                btn_d.clicked.connect(lambda _, i=iid: self._delete_policy(i))
                al.addWidget(btn_e); al.addWidget(btn_d)
                self.table.setCellWidget(r, 9, act)

            self.count_lbl.setText(f"Showing {len(rows)} policy(ies)")
        except Exception as e:
            error(self, "Load Error", str(e))

    def _filter(self):
        self._load_policies(
            search=self.search.text(),
            status=self.status_filter.currentText()
        )

    def _add_policy(self):
        dlg = InsuranceDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("""INSERT INTO insurance
                    (vehicle_id,cust_id,provider,policy_no,coverage,
                     start_date,end_date,premium,status)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""", data)
                conn.commit(); conn.close()
                info(self, "Saved", "Insurance policy added.")
                self.refresh()
                bus.insurance_changed.emit()
            except Exception as e:
                error(self, "Error", str(e))

    def _edit_policy(self, ins_id):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("""SELECT vehicle_id,cust_id,provider,policy_no,coverage,
                                  start_date,end_date,premium,status
                           FROM insurance WHERE ins_id=%s""", (ins_id,))
            row = cur.fetchone(); conn.close()
        except Exception as e: error(self, "Error", str(e)); return
        dlg = InsuranceDialog(self, row)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("""UPDATE insurance SET vehicle_id=%s,cust_id=%s,provider=%s,
                    policy_no=%s,coverage=%s,start_date=%s,end_date=%s,
                    premium=%s,status=%s WHERE ins_id=%s""", data+(ins_id,))
                conn.commit(); conn.close()
                info(self, "Updated", "Policy updated.")
                self.refresh()
                bus.insurance_changed.emit()
            except Exception as e:
                error(self, "Error", str(e))

    def _delete_policy(self, ins_id):
        if confirm(self, "Delete Policy", "Delete this insurance policy?"):
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("DELETE FROM insurance WHERE ins_id=%s", (ins_id,))
                conn.commit(); conn.close()
                self.refresh()
                bus.insurance_changed.emit()
            except Exception as e:
                error(self, "Error", str(e))

    def _cs(self):
        return f"QComboBox{{border:1px solid {BORDER};border-radius:8px;padding:0 10px;font-size:13px;color:{TEXT_DARK};background:white;}}QComboBox::drop-down{{border:none;width:20px;}}"


class InsuranceDialog(QDialog):
    def __init__(self, parent, existing=None):
        super().__init__(parent)
        self.setWindowTitle("Insurance Policy")
        self.setFixedWidth(440)
        self.setStyleSheet("""
            QDialog{background:#f3f6fb;font-family:'Segoe UI';}
            QLineEdit,QComboBox,QDateEdit,QDoubleSpinBox,QTextEdit{
                border:1px solid #d7dee8;border-radius:7px;
                padding:6px 10px;font-size:13px;background:white;}
        """)
        self._vehicles = {}; self._customers = {}
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT vehicle_id, plate_no||' - '||COALESCE(make,'')||' '||COALESCE(model,'') FROM vehicles ORDER BY plate_no")
            self._vehicles = {r[1]: r[0] for r in cur.fetchall()}
            cur.execute("SELECT cust_id, cust_code||' - '||full_name FROM customers ORDER BY cust_code")
            self._customers = {r[1]: r[0] for r in cur.fetchall()}
            conn.close()
        except: pass
        self._build(existing)

    def _build(self, ex):
        layout = QVBoxLayout(self); layout.setContentsMargins(22,18,22,18)
        form = QFormLayout(); form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight|Qt.AlignVCenter)

        self.f_veh = QComboBox(); self.f_veh.addItems(list(self._vehicles.keys()))
        if ex and ex[0]:
            for label, vid in self._vehicles.items():
                if vid == ex[0]: self.f_veh.setCurrentText(label); break

        self.f_cust = QComboBox(); self.f_cust.addItems(list(self._customers.keys()))
        if ex and ex[1]:
            for label, cid in self._customers.items():
                if cid == ex[1]: self.f_cust.setCurrentText(label); break

        # Auto-fill customer from vehicle
        self.f_veh.currentTextChanged.connect(self._auto_fill_customer)

        self.f_prov   = QLineEdit(ex[2] if ex and ex[2] else "")
        self.f_policy = QLineEdit(ex[3] if ex and ex[3] else "")
        self.f_cov    = QTextEdit(ex[4] if ex and ex[4] else "")
        self.f_cov.setFixedHeight(60)

        self.f_start = QDateEdit(); self.f_start.setCalendarPopup(True)
        self.f_start.setDate(
            QDate.fromString(str(ex[5]),"yyyy-MM-dd") if ex and ex[5]
            else QDate.currentDate()
        )
        self.f_end = QDateEdit(); self.f_end.setCalendarPopup(True)
        self.f_end.setDate(
            QDate.fromString(str(ex[6]),"yyyy-MM-dd") if ex and ex[6]
            else QDate.currentDate().addYears(1)
        )

        self.f_prem = QDoubleSpinBox()
        self.f_prem.setMaximum(9999999); self.f_prem.setDecimals(2); self.f_prem.setPrefix("PHP  ")
        self.f_prem.setValue(float(ex[7]) if ex and ex[7] else 0)

        self.f_status = QComboBox()
        self.f_status.addItems(["Active","Expired","Cancelled"])
        if ex and ex[8]: self.f_status.setCurrentText(ex[8])

        form.addRow("Vehicle *",    self.f_veh)
        form.addRow("Customer *",   self.f_cust)
        form.addRow("Provider",     self.f_prov)
        form.addRow("Policy No. *", self.f_policy)
        form.addRow("Coverage",     self.f_cov)
        form.addRow("Start Date",   self.f_start)
        form.addRow("End Date",     self.f_end)
        form.addRow("Premium",      self.f_prem)
        form.addRow("Status",       self.f_status)
        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Save).setStyleSheet(
            "background:#0b1f3a;color:white;border:none;border-radius:6px;"
            "padding:6px 18px;font-weight:700;")
        btns.button(QDialogButtonBox.Cancel).setStyleSheet(
            "background:#eee;color:#555;border:none;border-radius:6px;padding:6px 14px;")
        btns.accepted.connect(self._validate); btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _auto_fill_customer(self, veh_label):
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
            if row and row[1] in self._customers:
                self.f_cust.setCurrentText(row[1])
        except: pass

    def _validate(self):
        from PyQt5.QtWidgets import QMessageBox
        if not self._vehicles or not self._vehicles.get(self.f_veh.currentText()):
            QMessageBox.warning(self, "Validation", "Please add or select a vehicle.")
            return
        if not self._customers or not self._customers.get(self.f_cust.currentText()):
            QMessageBox.warning(self, "Validation", "Please add or select a customer.")
            return
        if not self.f_policy.text().strip():
            QMessageBox.warning(self, "Validation", "Policy number is required.")
            return
        self.accept()

    def get_data(self):
        return (
            self._vehicles.get(self.f_veh.currentText()),
            self._customers.get(self.f_cust.currentText()),
            self.f_prov.text().strip(),
            self.f_policy.text().strip(),
            self.f_cov.toPlainText().strip(),
            self.f_start.date().toString("yyyy-MM-dd"),
            self.f_end.date().toString("yyyy-MM-dd"),
            self.f_prem.value(),
            self.f_status.currentText()
        )

