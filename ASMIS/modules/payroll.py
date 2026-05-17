"""
modules/payroll.py
UnoCarshop ASMIS — Payroll Module (Integrated v2)

Key integrations:
- Auto-loads ALL active employees
- Computes basic pay from attendance + base salary
- Connected to attendance via payroll_attendance_summary view
- Fires payroll_changed + dashboard_refresh on save
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QDialog, QFormLayout, QDialogButtonBox,
    QDoubleSpinBox, QTableWidgetItem, QPushButton,
    QFrame, QTabWidget, QLineEdit, QDateEdit, QSpinBox
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QColor
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.widgets import (
    OrangeButton, GhostButton, SearchBar, StyledTable,
    StatCard, status_item, confirm, info, error,
    PAGE_BG, ORANGE, BORDER, TEXT_DARK, TEXT_SOFT,
    GREEN, RED, BLUE, CARD_BG
)
from db.connection import get_connection
from db.events import bus


class PayrollPage(QWidget):
    def __init__(self, user=None):
        super().__init__()
        self.user = user
        self.setStyleSheet(f"background: {PAGE_BG};")
        self._periods = {}
        self._build_ui()
        # Listen for attendance changes → auto refresh payroll
        bus.attendance_changed.connect(self._on_attendance_changed)
        self.refresh()

    def _on_attendance_changed(self):
        """Auto-refresh payroll summary when attendance changes."""
        self._load_attendance_summary()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Stats
        stats = QHBoxLayout(); stats.setSpacing(12)
        self.s_total  = StatCard("Total Payroll",    "₱0", "💰", ORANGE)
        self.s_paid   = StatCard("Paid",             "0",  "✅", GREEN)
        self.s_draft  = StatCard("Draft",            "0",  "📝", BLUE)
        self.s_emp    = StatCard("Active Employees", "0",  "👥", "#9b59b6")
        for s in [self.s_total, self.s_paid, self.s_draft, self.s_emp]:
            s.setFixedHeight(88); stats.addWidget(s)
        layout.addLayout(stats)

        # Tabs
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane{border:1px solid #e0ddd5;border-radius:10px;background:white;}
            QTabBar::tab{background:#f5f4f0;border:1px solid #e0ddd5;border-radius:6px;
                padding:8px 20px;font-size:13px;margin-right:4px;}
            QTabBar::tab:selected{background:#f5a623;color:white;font-weight:700;}
        """)
        tabs.addTab(self._build_payroll_tab(),    "💰  Payroll Records")
        tabs.addTab(self._build_attendance_tab(), "📊  Attendance Summary")
        layout.addWidget(tabs)

    # ── TAB 1: Payroll Records ─────────────────────────────
    def _build_payroll_tab(self):
        w = QWidget(); w.setStyleSheet("background:white;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16,16,16,16)
        layout.setSpacing(12)

        toolbar = QHBoxLayout()
        self.search = SearchBar("Search employee…")
        self.search.setFixedWidth(240)
        self.search.textChanged.connect(self._filter_payroll)

        self.period_combo = QComboBox()
        self.period_combo.setFixedHeight(38); self.period_combo.setFixedWidth(220)
        self.period_combo.setStyleSheet(self._cs())
        self.period_combo.currentIndexChanged.connect(self._filter_payroll)

        btn_gen     = OrangeButton("⚡  Generate from Attendance")
        btn_gen.clicked.connect(self._generate_from_attendance)
        btn_add     = GhostButton("➕  Add Manual")
        btn_add.clicked.connect(self._add_payroll)
        btn_period  = GhostButton("📅  New Period")
        btn_period.clicked.connect(self._add_period)
        btn_refresh = GhostButton("🔄  Refresh")
        btn_refresh.clicked.connect(self.refresh)

        toolbar.addWidget(self.search)
        toolbar.addWidget(QLabel("Period:"))
        toolbar.addWidget(self.period_combo)
        toolbar.addStretch()
        toolbar.addWidget(btn_refresh)
        toolbar.addWidget(btn_period)
        toolbar.addWidget(btn_add)
        toolbar.addWidget(btn_gen)
        layout.addLayout(toolbar)

        cols = ["Employee","Department","Basic Pay","OT Pay",
                "Allowances","Deductions","Net Pay","Status","Actions"]
        self.payroll_table = StyledTable(cols)
        self.payroll_table.setColumnWidth(0, 150)
        self.payroll_table.setColumnWidth(1, 120)
        self.payroll_table.setColumnWidth(2, 90)
        self.payroll_table.setColumnWidth(3, 80)
        self.payroll_table.setColumnWidth(4, 90)
        self.payroll_table.setColumnWidth(5, 90)
        self.payroll_table.setColumnWidth(6, 90)
        self.payroll_table.setColumnWidth(7, 90)
        self.payroll_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.payroll_table)

        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet(f"color:{TEXT_SOFT};font-size:12px;")
        layout.addWidget(self.count_lbl)
        return w

    # ── TAB 2: Attendance Summary ──────────────────────────
    def _build_attendance_tab(self):
        w = QWidget(); w.setStyleSheet("background:white;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16,16,16,16)
        layout.setSpacing(12)

        toolbar2 = QHBoxLayout()
        self.att_period_combo = QComboBox()
        self.att_period_combo.setFixedHeight(38); self.att_period_combo.setFixedWidth(220)
        self.att_period_combo.setStyleSheet(self._cs())
        self.att_period_combo.currentIndexChanged.connect(self._load_attendance_summary)
        btn_ref2 = GhostButton("🔄 Refresh"); btn_ref2.clicked.connect(self._load_attendance_summary)
        toolbar2.addWidget(QLabel("Period:"))
        toolbar2.addWidget(self.att_period_combo)
        toolbar2.addStretch()
        toolbar2.addWidget(btn_ref2)
        layout.addLayout(toolbar2)

        info_lbl = QLabel("ℹ  This table shows computed pay based on actual attendance records.")
        info_lbl.setStyleSheet(f"color:{TEXT_SOFT};font-size:12px;background:#fff4e0;"
                                "border:1px solid #f5c07a;border-radius:6px;padding:8px 12px;")
        layout.addWidget(info_lbl)

        cols = ["Employee","Position","Base Salary","Present","Absent",
                "Late","Half Day","On Leave","Computed Pay"]
        self.att_table = StyledTable(cols)
        self.att_table.setColumnWidth(0, 160)
        self.att_table.setColumnWidth(1, 130)
        self.att_table.setColumnWidth(2, 100)
        self.att_table.setColumnWidth(3, 70)
        self.att_table.setColumnWidth(4, 65)
        self.att_table.setColumnWidth(5, 55)
        self.att_table.setColumnWidth(6, 70)
        self.att_table.setColumnWidth(7, 75)
        self.att_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.att_table)
        return w

    # ── Data loading ──────────────────────────────────────
    def refresh(self):
        self._load_periods()
        self._load_payroll()
        self._load_attendance_summary()
        self._update_stats()

    def _load_periods(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT period_id, period_name FROM payroll_periods ORDER BY start_date DESC")
            rows = cur.fetchall(); conn.close()
            self._periods = {r[1]: r[0] for r in rows}
            for combo in [self.period_combo, self.att_period_combo]:
                combo.blockSignals(True)
                combo.clear()
                combo.addItem("All Periods")
                combo.addItems(list(self._periods.keys()))
                combo.blockSignals(False)
        except Exception as e:
            print(f"Period load: {e}")

    def _load_payroll(self, search="", period_name=""):
        try:
            conn = get_connection(); cur = conn.cursor()
            q = """
                SELECT py.payroll_id, e.full_name, d.dept_name,
                       py.basic_pay, py.overtime_pay, py.allowances,
                       py.deductions, py.net_pay, py.status
                FROM payroll py
                JOIN employees e ON py.emp_id=e.emp_id
                LEFT JOIN departments d ON e.dept_id=d.dept_id
                LEFT JOIN payroll_periods pp ON py.period_id=pp.period_id
                WHERE 1=1
            """
            params = []
            if search:
                q += " AND LOWER(e.full_name) LIKE %s"
                params.append(f"%{search.lower()}%")
            if period_name and period_name != "All Periods":
                pid = self._periods.get(period_name)
                if pid: q += " AND py.period_id=%s"; params.append(pid)
            q += " ORDER BY e.full_name"
            cur.execute(q, params)
            rows = cur.fetchall()
            conn.close()

            self.payroll_table.setRowCount(0)
            for rd in rows:
                r = self.payroll_table.rowCount()
                self.payroll_table.insertRow(r)
                self.payroll_table.setRowHeight(r, 38)
                for c, val in enumerate(rd[1:7]):
                    item = QTableWidgetItem(
                        f"₱{float(val):,.2f}" if c >= 2 else str(val) if val else "—"
                    )
                    item.setTextAlignment(
                        (Qt.AlignRight if c >= 2 else Qt.AlignLeft) | Qt.AlignVCenter
                    )
                    self.payroll_table.setItem(r, c, item)
                net = QTableWidgetItem(f"₱{float(rd[7]):,.2f}")
                net.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.payroll_table.setItem(r, 6, net)
                self.payroll_table.setItem(r, 7, status_item(rd[8]))

                pid_ = rd[0]
                act = QWidget(); act.setStyleSheet("background:transparent;")
                al = QHBoxLayout(act); al.setContentsMargins(4,2,4,2); al.setSpacing(4)
                btn_e = QPushButton("Edit"); btn_e.setFixedHeight(27); btn_e.setCursor(Qt.PointingHandCursor)
                btn_e.setStyleSheet("QPushButton{background:#fff4e0;color:#e08e0b;border:1px solid #f5c07a;border-radius:5px;font-size:11px;padding:0 8px;}QPushButton:hover{background:#ffe0a0;}")
                btn_e.clicked.connect(lambda _, p=pid_: self._edit_payroll(p))
                btn_d = QPushButton("Del"); btn_d.setFixedHeight(27); btn_d.setCursor(Qt.PointingHandCursor)
                btn_d.setStyleSheet("QPushButton{background:#ffebee;color:#c62828;border:1px solid #ef9a9a;border-radius:5px;font-size:11px;padding:0 8px;}QPushButton:hover{background:#ffcdd2;}")
                btn_d.clicked.connect(lambda _, p=pid_: self._delete_payroll(p))
                al.addWidget(btn_e); al.addWidget(btn_d)
                self.payroll_table.setCellWidget(r, 8, act)

            self.count_lbl.setText(f"Showing {len(rows)} payroll record(s)")
        except Exception as e:
            error(self, "Load Error", str(e))

    def _load_attendance_summary(self):
        """Load computed pay from attendance-payroll view."""
        period_name = self.att_period_combo.currentText() if hasattr(self, 'att_period_combo') else "All Periods"
        try:
            conn = get_connection(); cur = conn.cursor()
            # Check if view exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.views
                    WHERE table_name='payroll_attendance_summary'
                )
            """)
            view_exists = cur.fetchone()[0]

            if view_exists and period_name != "All Periods":
                pid = self._periods.get(period_name)
                if pid:
                    cur.execute("""
                        SELECT full_name, position_name, base_salary,
                               days_present, days_absent, days_late,
                               days_halfday, days_onleave, computed_basic_pay
                        FROM payroll_attendance_summary
                        WHERE period_id = %s
                        ORDER BY full_name
                    """, (pid,))
                else:
                    cur.execute("SELECT 1 WHERE false")
            else:
                # Fallback: compute from raw tables
                cur.execute("""
                    SELECT e.full_name, p.position_name, p.base_salary,
                        COUNT(a.attend_id) FILTER (WHERE a.status='Present') AS present,
                        COUNT(a.attend_id) FILTER (WHERE a.status='Absent')  AS absent,
                        COUNT(a.attend_id) FILTER (WHERE a.status='Late')    AS late,
                        COUNT(a.attend_id) FILTER (WHERE a.status='Half Day') AS halfday,
                        COUNT(a.attend_id) FILTER (WHERE a.status='On Leave') AS onleave,
                        ROUND(p.base_salary/22.0 * (
                            COUNT(a.attend_id) FILTER (WHERE a.status IN ('Present','Late'))
                            + COUNT(a.attend_id) FILTER (WHERE a.status='Half Day')*0.5
                        ), 2) AS computed
                    FROM employees e
                    LEFT JOIN positions p ON e.position_id=p.position_id
                    LEFT JOIN attendance a ON e.emp_id=a.emp_id
                    WHERE e.status='Active'
                    GROUP BY e.emp_id, e.full_name, p.position_name, p.base_salary
                    ORDER BY e.full_name
                """)

            rows = cur.fetchall(); conn.close()
            self.att_table.setRowCount(0)
            for rd in rows:
                r = self.att_table.rowCount()
                self.att_table.insertRow(r)
                self.att_table.setRowHeight(r, 38)
                for c, val in enumerate(rd):
                    item = QTableWidgetItem(
                        f"₱{float(val):,.2f}" if c in (2, 8) else str(val) if val is not None else "0"
                    )
                    item.setTextAlignment(
                        (Qt.AlignRight if c in (2,3,4,5,6,7,8) else Qt.AlignLeft) | Qt.AlignVCenter
                    )
                    self.att_table.setItem(r, c, item)
        except Exception as e:
            print(f"Attendance summary error: {e}")

    def _update_stats(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT COALESCE(SUM(net_pay),0) FROM payroll")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM payroll WHERE status='Paid'")
            paid = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM payroll WHERE status='Draft'")
            draft = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM employees WHERE status='Active'")
            emp = cur.fetchone()[0]
            conn.close()
            self.s_total.set_value(f"₱{float(total):,.0f}")
            self.s_paid.set_value(paid)
            self.s_draft.set_value(draft)
            self.s_emp.set_value(emp)
        except: pass

    def _filter_payroll(self):
        self._load_payroll(
            search=self.search.text(),
            period_name=self.period_combo.currentText()
        )

    # ── Generate payroll from attendance ──────────────────
    def _generate_from_attendance(self):
        period_name = self.period_combo.currentText()
        if period_name == "All Periods":
            error(self, "Select Period", "Please select a specific payroll period first.")
            return
        pid = self._periods.get(period_name)
        if not pid: return
        try:
            conn = get_connection(); cur = conn.cursor()
            # Get period dates
            cur.execute("SELECT start_date, end_date FROM payroll_periods WHERE period_id=%s", (pid,))
            start_date, end_date = cur.fetchone()
            # Get all active employees with attendance in this period
            cur.execute("""
                SELECT e.emp_id, e.full_name, p.base_salary,
                    COUNT(a.attend_id) FILTER (WHERE a.status IN ('Present','Late')) AS worked,
                    COUNT(a.attend_id) FILTER (WHERE a.status = 'Half Day') AS halfdays
                FROM employees e
                LEFT JOIN positions p ON e.position_id=p.position_id
                LEFT JOIN attendance a ON e.emp_id=a.emp_id
                    AND a.attend_date BETWEEN %s AND %s
                WHERE e.status='Active'
                GROUP BY e.emp_id, e.full_name, p.base_salary
            """, (start_date, end_date))
            emp_rows = cur.fetchall()
            generated = 0
            for emp_id, full_name, base_salary, worked_days, halfdays in emp_rows:
                base_salary = base_salary or 0
                daily_rate  = base_salary / 22.0
                basic_pay   = round(daily_rate * (worked_days + halfdays * 0.5), 2)
                # SSS, PhilHealth, Pag-IBIG (standard PH deductions)
                sss        = round(min(basic_pay * 0.045, 1800), 2)
                philhealth = round(basic_pay * 0.02, 2)
                pagibig    = round(min(basic_pay * 0.02, 200), 2)
                # Check if payroll already exists for this emp+period
                cur.execute(
                    "SELECT payroll_id FROM payroll WHERE emp_id=%s AND period_id=%s",
                    (emp_id, pid)
                )
                existing = cur.fetchone()
                if existing:
                    cur.execute("""
                        UPDATE payroll SET basic_pay=%s, sss=%s, philhealth=%s, pagibig=%s
                        WHERE payroll_id=%s
                    """, (basic_pay, sss, philhealth, pagibig, existing[0]))
                else:
                    cur.execute("""
                        INSERT INTO payroll
                        (period_id, emp_id, basic_pay, sss, philhealth, pagibig, status)
                        VALUES (%s,%s,%s,%s,%s,%s,'Draft')
                    """, (pid, emp_id, basic_pay, sss, philhealth, pagibig))
                generated += 1
            conn.commit(); conn.close()
            info(self, "Generated", f"Payroll generated for {generated} employee(s) based on attendance.")
            self.refresh()
            bus.payroll_changed.emit()
            bus.dashboard_refresh.emit()
        except Exception as e:
            error(self, "Generate Error", str(e))

    # ── CRUD ──────────────────────────────────────────────
    def _add_period(self):
        dlg = PeriodDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute(
                    "INSERT INTO payroll_periods (period_name,start_date,end_date) VALUES (%s,%s,%s)",
                    data
                )
                conn.commit(); conn.close()
                info(self, "Created", "Payroll period created.")
                self._load_periods()
            except Exception as e:
                error(self, "Error", str(e))

    def _add_payroll(self):
        dlg = PayrollDialog(self, self._periods)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("""
                    INSERT INTO payroll
                    (period_id,emp_id,basic_pay,overtime_pay,allowances,
                     deductions,sss,philhealth,pagibig,tax,status)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, data)
                conn.commit(); conn.close()
                info(self, "Saved", "Payroll record saved.")
                self.refresh()
                bus.payroll_changed.emit()
                bus.dashboard_refresh.emit()
            except Exception as e:
                error(self, "Error", str(e))

    def _edit_payroll(self, payroll_id):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("""
                SELECT period_id,emp_id,basic_pay,overtime_pay,allowances,
                       deductions,sss,philhealth,pagibig,tax,status
                FROM payroll WHERE payroll_id=%s
            """, (payroll_id,))
            row = cur.fetchone(); conn.close()
        except Exception as e:
            error(self, "Error", str(e)); return
        dlg = PayrollDialog(self, self._periods, row)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("""
                    UPDATE payroll SET period_id=%s,emp_id=%s,basic_pay=%s,
                        overtime_pay=%s,allowances=%s,deductions=%s,
                        sss=%s,philhealth=%s,pagibig=%s,tax=%s,status=%s
                    WHERE payroll_id=%s
                """, data+(payroll_id,))
                conn.commit(); conn.close()
                info(self, "Updated", "Payroll updated.")
                self.refresh()
                bus.payroll_changed.emit()
                bus.dashboard_refresh.emit()
            except Exception as e:
                error(self, "Error", str(e))

    def _delete_payroll(self, payroll_id):
        if confirm(self, "Delete", "Delete this payroll record?"):
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("DELETE FROM payroll WHERE payroll_id=%s", (payroll_id,))
                conn.commit(); conn.close()
                self.refresh()
                bus.payroll_changed.emit()
            except Exception as e:
                error(self, "Error", str(e))

    def _cs(self):
        return f"""
            QComboBox{{border:1px solid {BORDER};border-radius:8px;
            padding:0 10px;font-size:13px;color:{TEXT_DARK};background:white;}}
            QComboBox::drop-down{{border:none;width:20px;}}
        """


class PeriodDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("New Payroll Period")
        self.setFixedWidth(360)
        self.setStyleSheet("QDialog{background:#f5f4f0;font-family:'Segoe UI';}"
                           "QLineEdit,QDateEdit{border:1px solid #e0ddd5;border-radius:7px;"
                           "padding:6px 10px;font-size:13px;background:white;}")
        layout = QVBoxLayout(self); layout.setContentsMargins(22,20,22,20)
        form = QFormLayout(); form.setSpacing(10)
        self.f_name  = QLineEdit()
        self.f_start = QDateEdit(QDate.currentDate()); self.f_start.setCalendarPopup(True)
        self.f_end   = QDateEdit(QDate.currentDate().addDays(14)); self.f_end.setCalendarPopup(True)
        form.addRow("Period Name *", self.f_name)
        form.addRow("Start Date",    self.f_start)
        form.addRow("End Date",      self.f_end)
        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_data(self):
        return (self.f_name.text().strip(),
                self.f_start.date().toString("yyyy-MM-dd"),
                self.f_end.date().toString("yyyy-MM-dd"))


class PayrollDialog(QDialog):
    def __init__(self, parent, periods, existing=None):
        super().__init__(parent)
        self.periods = periods
        self.setWindowTitle("Payroll Record")
        self.setFixedWidth(460)
        self.setStyleSheet("""
            QDialog{background:#f5f4f0;font-family:'Segoe UI';}
            QComboBox,QDoubleSpinBox{border:1px solid #e0ddd5;border-radius:7px;
            padding:6px 10px;font-size:13px;background:white;}
        """)
        self._employees = {}
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT emp_id, emp_code||' — '||full_name FROM employees WHERE status='Active' ORDER BY emp_code")
            self._employees = {r[1]: r[0] for r in cur.fetchall()}; conn.close()
        except: pass
        self._build(existing)

    def _build(self, ex):
        layout = QVBoxLayout(self); layout.setContentsMargins(22,18,22,18)
        form = QFormLayout(); form.setSpacing(10)

        self.f_period = QComboBox(); self.f_period.addItems(list(self.periods.keys()))
        if ex and ex[0]:
            for name, pid in self.periods.items():
                if pid == ex[0]: self.f_period.setCurrentText(name)

        self.f_emp = QComboBox(); self.f_emp.addItems(list(self._employees.keys()))
        if ex and ex[1]:
            for label, eid in self._employees.items():
                if eid == ex[1]: self.f_emp.setCurrentText(label)

        def spin(v=0):
            s = QDoubleSpinBox(); s.setMaximum(999999); s.setDecimals(2); s.setPrefix("₱ ")
            s.setValue(float(v) if v else 0); return s

        self.f_basic  = spin(ex[2] if ex else 0)
        self.f_ot     = spin(ex[3] if ex else 0)
        self.f_allow  = spin(ex[4] if ex else 0)
        self.f_deduct = spin(ex[5] if ex else 0)
        self.f_sss    = spin(ex[6] if ex else 0)
        self.f_phil   = spin(ex[7] if ex else 0)
        self.f_pagibig= spin(ex[8] if ex else 0)
        self.f_tax    = spin(ex[9] if ex else 0)
        self.f_status = QComboBox(); self.f_status.addItems(["Draft","Approved","Paid"])
        if ex and ex[10]: self.f_status.setCurrentText(ex[10])

        form.addRow("Period",          self.f_period)
        form.addRow("Employee",        self.f_emp)
        form.addRow("Basic Pay",       self.f_basic)
        form.addRow("Overtime Pay",    self.f_ot)
        form.addRow("Allowances",      self.f_allow)
        form.addRow("Other Deductions",self.f_deduct)
        form.addRow("SSS",             self.f_sss)
        form.addRow("PhilHealth",      self.f_phil)
        form.addRow("Pag-IBIG",        self.f_pagibig)
        form.addRow("Tax",             self.f_tax)
        form.addRow("Status",          self.f_status)
        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_data(self):
        return (
            self.periods.get(self.f_period.currentText()),
            self._employees.get(self.f_emp.currentText()),
            self.f_basic.value(), self.f_ot.value(),
            self.f_allow.value(), self.f_deduct.value(),
            self.f_sss.value(), self.f_phil.value(),
            self.f_pagibig.value(), self.f_tax.value(),
            self.f_status.currentText()
        )
