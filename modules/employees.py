"""
modules/employees.py
UnoCarshop ASMIS — Employees (Integrated v2)
Fires employees_changed + dashboard_refresh on all CRUD
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QDialog,
    QFormLayout, QDialogButtonBox, QDateEdit,
    QMessageBox, QTextEdit, QAbstractItemView
)
from PyQt5.QtCore import Qt, QDate
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.widgets import (
    OrangeButton, GhostButton, DangerButton,
    SearchBar, StyledTable, Card, status_item,
    confirm, info, error,
    PAGE_BG, ORANGE, BORDER, TEXT_DARK, TEXT_SOFT, CARD_BG
)
from db.connection import get_connection
from db.events import bus


def employee_category(value):
    return "Non-Regular" if value == "On-Call" else (value or "Regular")


class EmployeesPage(QWidget):
    def __init__(self, user=None):
        super().__init__()
        self.user = user
        self.setStyleSheet(f"background: {PAGE_BG};")
        self._depts = {}
        self._positions = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        toolbar = QHBoxLayout()
        self.search = SearchBar("Search by name, code, department…")
        self.search.setFixedWidth(320)
        self.search.textChanged.connect(self._filter)

        self.filter_dept = QComboBox()
        self.filter_dept.setFixedHeight(38); self.filter_dept.setFixedWidth(160)
        self.filter_dept.setStyleSheet(self._combo_style())
        self.filter_dept.currentIndexChanged.connect(self._filter)

        self.filter_status = QComboBox()
        self.filter_status.addItems(["All Status","Active","On Leave","Resigned","Terminated"])
        self.filter_status.setFixedHeight(38); self.filter_status.setFixedWidth(140)
        self.filter_status.setStyleSheet(self._combo_style())
        self.filter_status.currentIndexChanged.connect(self._filter)

        btn_add     = OrangeButton("➕  Add Employee"); btn_add.clicked.connect(self._add_employee)
        btn_refresh = GhostButton("🔄  Refresh");      btn_refresh.clicked.connect(self.refresh)

        toolbar.addWidget(self.search)
        toolbar.addWidget(self.filter_dept)
        toolbar.addWidget(self.filter_status)
        toolbar.addStretch()
        toolbar.addWidget(btn_refresh)
        toolbar.addWidget(btn_add)
        layout.addLayout(toolbar)

        cols = ["Code","Full Name","Category","Schedule","Department","Position","Hire Date","Gender","Phone","Status","Actions"]
        self.table = StyledTable(cols)
        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(1, 160)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 105)
        self.table.setColumnWidth(4, 130)
        self.table.setColumnWidth(5, 130)
        self.table.setColumnWidth(6, 100)
        self.table.setColumnWidth(7, 70)
        self.table.setColumnWidth(8, 110)
        self.table.setColumnWidth(9, 90)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet(f"color: {TEXT_SOFT}; font-size: 12px;")
        layout.addWidget(self.count_lbl)

    def refresh(self):
        self._load_lookups()
        self._load_employees()

    def _load_lookups(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT dept_id, dept_name FROM departments ORDER BY dept_name")
            self._depts = {r[1]: r[0] for r in cur.fetchall()}
            cur.execute("SELECT position_id, position_name FROM positions ORDER BY position_name")
            self._positions = {r[1]: r[0] for r in cur.fetchall()}
            conn.close()
            self.filter_dept.blockSignals(True)
            self.filter_dept.clear()
            self.filter_dept.addItem("All Departments")
            self.filter_dept.addItems(list(self._depts.keys()))
            self.filter_dept.blockSignals(False)
        except Exception as e:
            print(f"Lookup error: {e}")

    def _load_employees(self, search="", dept="", status=""):
        try:
            conn = get_connection(); cur = conn.cursor()
            q = """
                SELECT e.emp_id, e.emp_code, e.full_name,
                       COALESCE(e.classification,'Regular'),
                       COALESCE(e.pay_schedule,'Weekly'),
                       COALESCE(d.dept_name,'—'), COALESCE(p.position_name,'—'),
                       e.hire_date, COALESCE(e.gender,'—'), COALESCE(e.phone,'—'), e.status
                FROM employees e
                LEFT JOIN departments d ON e.dept_id=d.dept_id
                LEFT JOIN positions p ON e.position_id=p.position_id
                WHERE 1=1
            """
            params = []
            if search:
                q += " AND (LOWER(e.full_name) LIKE %s OR e.emp_code LIKE %s OR LOWER(d.dept_name) LIKE %s)"
                s = f"%{search.lower()}%"; params += [s, s, s]
            if dept and dept != "All Departments":
                q += " AND d.dept_name=%s"; params.append(dept)
            if status and status != "All Status":
                q += " AND e.status=%s"; params.append(status)
            q += " ORDER BY e.emp_code"
            cur.execute(q, params); rows = cur.fetchall(); conn.close()

            self.table.setRowCount(0)
            for rd in rows:
                r = self.table.rowCount(); self.table.insertRow(r)
                self.table.setRowHeight(r, 38)
                for c, val in enumerate(rd[1:10]):
                    from PyQt5.QtWidgets import QTableWidgetItem
                    text = employee_category(val) if c == 2 else str(val) if val else ""
                    item = QTableWidgetItem(text)
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    self.table.setItem(r, c, item)
                self.table.setItem(r, 9, status_item(rd[10]))

                emp_id = rd[0]
                act = QWidget(); act.setStyleSheet("background:transparent;")
                al = QHBoxLayout(act); al.setContentsMargins(4,2,4,2); al.setSpacing(4)
                btn_e = QPushButton("Edit"); btn_e.setFixedHeight(27); btn_e.setCursor(Qt.PointingHandCursor)
                btn_e.setStyleSheet("QPushButton{background:#e7eef8;color:#123a63;border:1px solid #8aa4c4;border-radius:5px;font-size:11px;padding:0 8px;}QPushButton:hover{background:#dbe9ff;}")
                btn_e.clicked.connect(lambda _, eid=emp_id: self._edit_employee(eid))
                btn_d = QPushButton("Delete"); btn_d.setFixedHeight(27); btn_d.setCursor(Qt.PointingHandCursor)
                btn_d.setStyleSheet("QPushButton{background:#ffebee;color:#c62828;border:1px solid #ef9a9a;border-radius:5px;font-size:11px;padding:0 8px;}QPushButton:hover{background:#ffcdd2;}")
                btn_d.clicked.connect(lambda _, eid=emp_id: self._delete_employee(eid))
                al.addWidget(btn_e); al.addWidget(btn_d)
                self.table.setCellWidget(r, 10, act)

            self.count_lbl.setText(f"Showing {len(rows)} employee(s)")
        except Exception as e:
            error(self, "Load Error", str(e))

    def _filter(self):
        self._load_employees(
            search=self.search.text(),
            dept=self.filter_dept.currentText(),
            status=self.filter_status.currentText()
        )

    def _add_employee(self):
        dlg = EmployeeDialog(self, self._depts, self._positions)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("""INSERT INTO employees
                    (emp_code,first_name,last_name,dept_id,position_id,hire_date,
                     birth_date,gender,phone,email,address,classification,pay_schedule,status)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", data)
                conn.commit(); conn.close()
                info(self, "Success", "Employee added.")
                self.refresh()
                bus.employees_changed.emit()
                bus.dashboard_refresh.emit()
            except Exception as e: error(self, "Save Error", str(e))

    def _edit_employee(self, emp_id):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("""SELECT emp_code,first_name,last_name,dept_id,position_id,
                                  hire_date,birth_date,gender,phone,email,address,classification,pay_schedule,status
                           FROM employees WHERE emp_id=%s""", (emp_id,))
            row = cur.fetchone(); conn.close()
        except Exception as e: error(self, "Load Error", str(e)); return
        dlg = EmployeeDialog(self, self._depts, self._positions, row)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("""UPDATE employees SET emp_code=%s,first_name=%s,last_name=%s,
                    dept_id=%s,position_id=%s,hire_date=%s,birth_date=%s,gender=%s,
                    phone=%s,email=%s,address=%s,classification=%s,pay_schedule=%s,status=%s WHERE emp_id=%s""", data+(emp_id,))
                conn.commit(); conn.close()
                info(self, "Updated", "Employee record updated.")
                self.refresh()
                bus.employees_changed.emit()
                bus.dashboard_refresh.emit()
            except Exception as e: error(self, "Update Error", str(e))

    def _delete_employee(self, emp_id):
        if confirm(self, "Delete Employee", "Delete this employee? Existing service orders will be left unassigned."):
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("UPDATE service_orders SET assign_emp=NULL WHERE assign_emp=%s", (emp_id,))
                cur.execute("DELETE FROM employees WHERE emp_id=%s", (emp_id,))
                conn.commit(); conn.close()
                info(self, "Deleted", "Employee deleted.")
                self.refresh()
                bus.employees_changed.emit()
                bus.dashboard_refresh.emit()
            except Exception as e: error(self, "Delete Error", str(e))

    def _combo_style(self):
        return f"""
            QComboBox{{border:1px solid {BORDER};border-radius:8px;
            padding:0 12px;font-size:13px;color:{TEXT_DARK};background:white;}}
            QComboBox::drop-down{{border:none;width:24px;}}
        """


class EmployeeDialog(QDialog):
    def __init__(self, parent, depts, positions, existing=None):
        super().__init__(parent)
        self.depts = depts; self.positions = positions
        self.setWindowTitle("Add Employee" if not existing else "Edit Employee")
        self.setFixedWidth(500)
        self.setStyleSheet("""
            QDialog{background:#f3f6fb;font-family:'Segoe UI';}
            QLineEdit,QComboBox,QDateEdit,QTextEdit{border:1px solid #d7dee8;
            border-radius:7px;padding:6px 10px;font-size:13px;background:white;}
        """)
        self._build(existing)

    def _build(self, ex):
        layout = QVBoxLayout(self); layout.setContentsMargins(24,20,24,20); layout.setSpacing(14)
        form = QFormLayout(); form.setSpacing(10); form.setLabelAlignment(Qt.AlignRight|Qt.AlignVCenter)

        self.f_code  = QLineEdit(ex[0] if ex else "")
        self.f_first = QLineEdit(ex[1] if ex else "")
        self.f_last  = QLineEdit(ex[2] if ex else "")

        self.f_dept = QComboBox(); self.f_dept.addItems(list(self.depts.keys()))
        if ex and ex[3]:
            for n, did in self.depts.items():
                if did == ex[3]: self.f_dept.setCurrentText(n)

        self.f_pos = QComboBox(); self.f_pos.addItems(list(self.positions.keys()))
        if ex and ex[4]:
            for n, pid in self.positions.items():
                if pid == ex[4]: self.f_pos.setCurrentText(n)

        self.f_hire = QDateEdit(); self.f_hire.setCalendarPopup(True)
        self.f_hire.setDate(QDate.fromString(str(ex[5]),"yyyy-MM-dd") if ex and ex[5] else QDate.currentDate())
        self.f_bday = QDateEdit(); self.f_bday.setCalendarPopup(True)
        self.f_bday.setDate(QDate.fromString(str(ex[6]),"yyyy-MM-dd") if ex and ex[6] else QDate(1990,1,1))
        self.f_gender = QComboBox(); self.f_gender.addItems(["Male","Female","Other"])
        if ex and ex[7]: self.f_gender.setCurrentText(ex[7])
        self.f_phone = QLineEdit(ex[8] if ex and ex[8] else "")
        self.f_email = QLineEdit(ex[9] if ex and ex[9] else "")
        self.f_addr  = QTextEdit(ex[10] if ex and ex[10] else ""); self.f_addr.setFixedHeight(60)
        self.f_class = QComboBox(); self.f_class.addItems(["Regular","Non-Regular"])
        if ex and ex[11]: self.f_class.setCurrentText(employee_category(ex[11]))
        self.f_schedule = QComboBox(); self.f_schedule.addItems(["Weekly","Semi-Monthly"])
        if ex and ex[12]: self.f_schedule.setCurrentText(ex[12])
        self.f_status= QComboBox(); self.f_status.addItems(["Active","On Leave","Resigned","Terminated"])
        if ex and ex[13]: self.f_status.setCurrentText(ex[13])

        form.addRow("Employee Code *", self.f_code)
        form.addRow("First Name *",    self.f_first)
        form.addRow("Last Name *",     self.f_last)
        form.addRow("Department",      self.f_dept)
        form.addRow("Position",        self.f_pos)
        form.addRow("Hire Date",       self.f_hire)
        form.addRow("Birth Date",      self.f_bday)
        form.addRow("Gender",          self.f_gender)
        form.addRow("Phone",           self.f_phone)
        form.addRow("Email",           self.f_email)
        form.addRow("Address",         self.f_addr)
        form.addRow("Category",        self.f_class)
        form.addRow("Pay Schedule",    self.f_schedule)
        form.addRow("Status",          self.f_status)
        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Save).setStyleSheet("background:#0b1f3a;color:white;border:none;border-radius:6px;padding:6px 18px;font-weight:700;")
        btns.button(QDialogButtonBox.Cancel).setStyleSheet("background:#eee;color:#555;border:none;border-radius:6px;padding:6px 14px;")
        btns.accepted.connect(self._validate); btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _validate(self):
        if not self.f_code.text().strip():
            QMessageBox.warning(self, "Validation", "Employee code is required."); return
        if not self.f_first.text().strip() or not self.f_last.text().strip():
            QMessageBox.warning(self, "Validation", "First and last name are required."); return
        self.accept()

    def get_data(self):
        return (
            self.f_code.text().strip(), self.f_first.text().strip(), self.f_last.text().strip(),
            self.depts.get(self.f_dept.currentText()), self.positions.get(self.f_pos.currentText()),
            self.f_hire.date().toString("yyyy-MM-dd"), self.f_bday.date().toString("yyyy-MM-dd"),
            self.f_gender.currentText(), self.f_phone.text().strip(),
            self.f_email.text().strip(), self.f_addr.toPlainText().strip(),
            self.f_class.currentText(),
            self.f_schedule.currentText(),
            self.f_status.currentText()
        )
