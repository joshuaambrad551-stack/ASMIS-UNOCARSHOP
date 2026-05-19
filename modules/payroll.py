"""
modules/payroll.py
UnoCarshop ASMIS — Payroll Module (Integrated v2)

Key integrations:
- Auto-loads ALL active employees
- Computes regular 15-day salary from fixed monthly basic pay
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

REGULAR_MONTHLY_BASIC_PAY = 16200.00
REGULAR_SEMI_MONTHLY_PAY = REGULAR_MONTHLY_BASIC_PAY / 2.0
REGULAR_DAILY_WAGE = REGULAR_MONTHLY_BASIC_PAY / 30.0
REGULAR_HOURLY_WAGE = REGULAR_DAILY_WAGE / 8.0
OVERTIME_MULTIPLIER = 1.25
REGULAR_SSS_DEDUCTION = 400.00
REGULAR_PAGIBIG_DEDUCTION = 100.00
REGULAR_PHILHEALTH_DEDUCTION = 202.00


def employee_category(value):
    return "Non-Regular" if value == "On-Call" else (value or "Regular")


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
        self.s_emp    = StatCard("Regular Employees", "0",  "👥", "#9b59b6")
        for s in [self.s_total, self.s_paid, self.s_draft, self.s_emp]:
            s.setFixedHeight(88); stats.addWidget(s)
        layout.addLayout(stats)

        # Tabs
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane{border:1px solid #d7dee8;border-radius:10px;background:white;}
            QTabBar::tab{background:#f3f6fb;border:1px solid #d7dee8;border-radius:6px;
                padding:8px 20px;font-size:13px;margin-right:4px;}
            QTabBar::tab:selected{background:#0b1f3a;color:white;font-weight:700;}
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

        btn_gen     = OrangeButton("⚡  Generate Regular Payroll")
        btn_gen.clicked.connect(self._generate_from_attendance)
        btn_add     = GhostButton("➕  Manual / Non-Regular Pay")
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

        hint = QLabel("Regular payroll automatically uses PHP 8,100 basic pay for each 15-day period. Non-Regular payroll shows PHP 0 basic pay and accepts a manual total salary.")
        hint.setStyleSheet(f"color:{TEXT_SOFT};font-size:12px;background:#f6f8fb;border:1px solid {BORDER};border-radius:6px;padding:8px 10px;")
        layout.addWidget(hint)

        cols = ["Employee","Category","Schedule","Department","Basic Pay","OT Pay",
                "Total Salary","Deductions","Net Pay","Status","Actions"]
        self.payroll_table = StyledTable(cols)
        self.payroll_table.setColumnWidth(0, 150)
        self.payroll_table.setColumnWidth(1, 80)
        self.payroll_table.setColumnWidth(2, 95)
        self.payroll_table.setColumnWidth(3, 110)
        self.payroll_table.setColumnWidth(4, 90)
        self.payroll_table.setColumnWidth(5, 80)
        self.payroll_table.setColumnWidth(6, 90)
        self.payroll_table.setColumnWidth(7, 90)
        self.payroll_table.setColumnWidth(8, 90)
        self.payroll_table.setColumnWidth(9, 90)
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

        info_lbl = QLabel("Regular employees are computed at PHP 16,200 monthly basic pay, or PHP 8,100 per 15-day payroll period. Non-Regular employees are handled manually with PHP 0 basic pay.")
        info_lbl.setStyleSheet(f"color:{TEXT_SOFT};font-size:12px;background:#e7eef8;"
                                "border:1px solid #8aa4c4;border-radius:6px;padding:8px 12px;")
        layout.addWidget(info_lbl)

        cols = ["Employee","Schedule","Monthly Basic","Present","Absent",
                "Late","Half Day","On Leave","15-Day Salary"]
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
                SELECT py.payroll_id, e.full_name, COALESCE(e.classification,'Regular'),
                       COALESCE(e.pay_schedule,'Weekly'), d.dept_name,
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
                for c, val in enumerate(rd[1:9]):
                    if c >= 4:
                        text = f"PHP {float(val):,.2f}"
                    elif c == 1:
                        text = employee_category(val)
                    else:
                        text = str(val) if val else "-"
                    item = QTableWidgetItem(text)
                    item.setTextAlignment(
                        (Qt.AlignRight if c >= 4 else Qt.AlignLeft) | Qt.AlignVCenter
                    )
                    self.payroll_table.setItem(r, c, item)
                net = QTableWidgetItem(f"PHP {float(rd[9]):,.2f}")
                net.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.payroll_table.setItem(r, 8, net)
                self.payroll_table.setItem(r, 9, status_item(rd[10]))

                pid_ = rd[0]
                act = QWidget(); act.setStyleSheet("background:transparent;")
                al = QHBoxLayout(act); al.setContentsMargins(4,2,4,2); al.setSpacing(4)
                btn_e = QPushButton("Edit"); btn_e.setFixedHeight(27); btn_e.setCursor(Qt.PointingHandCursor)
                btn_e.setStyleSheet("QPushButton{background:#e7eef8;color:#123a63;border:1px solid #8aa4c4;border-radius:5px;font-size:11px;padding:0 8px;}QPushButton:hover{background:#dbe9ff;}")
                btn_e.clicked.connect(lambda _, p=pid_: self._edit_payroll(p))
                btn_d = QPushButton("Del"); btn_d.setFixedHeight(27); btn_d.setCursor(Qt.PointingHandCursor)
                btn_d.setStyleSheet("QPushButton{background:#ffebee;color:#c62828;border:1px solid #ef9a9a;border-radius:5px;font-size:11px;padding:0 8px;}QPushButton:hover{background:#ffcdd2;}")
                btn_d.clicked.connect(lambda _, p=pid_: self._delete_payroll(p))
                al.addWidget(btn_e); al.addWidget(btn_d)
                self.payroll_table.setCellWidget(r, 10, act)

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
                        SELECT full_name, pay_schedule, %s::numeric AS monthly_basic,
                               days_present, days_absent, days_late,
                               days_halfday, days_onleave, %s::numeric AS computed_basic_pay
                        FROM payroll_attendance_summary
                        WHERE period_id = %s
                        ORDER BY full_name
                    """, (REGULAR_MONTHLY_BASIC_PAY, REGULAR_SEMI_MONTHLY_PAY, pid))
                else:
                    cur.execute("SELECT 1 WHERE false")
            else:
                # Fallback: compute from raw tables
                cur.execute("""
                    SELECT e.full_name, COALESCE(e.pay_schedule,'Weekly'), %s::numeric AS monthly_basic,
                        COUNT(a.attend_id) FILTER (WHERE a.status='Present') AS present,
                        COUNT(a.attend_id) FILTER (WHERE a.status='Absent')  AS absent,
                        COUNT(a.attend_id) FILTER (WHERE a.status='Late')    AS late,
                        COUNT(a.attend_id) FILTER (WHERE a.status='Half Day') AS halfday,
                        COUNT(a.attend_id) FILTER (WHERE a.status='On Leave') AS onleave,
                        %s::numeric AS computed
                    FROM employees e
                    LEFT JOIN attendance a ON e.emp_id=a.emp_id
                    WHERE e.status='Active' AND COALESCE(e.classification,'Regular')='Regular'
                    GROUP BY e.emp_id, e.full_name, e.pay_schedule
                    ORDER BY e.full_name
                """, (REGULAR_MONTHLY_BASIC_PAY, REGULAR_SEMI_MONTHLY_PAY))

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
            cur.execute("SELECT COUNT(*) FROM employees WHERE status='Active' AND COALESCE(classification,'Regular')='Regular'")
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
            # Generate only Regular employees; Non-Regular payroll is manual.
            cur.execute("""
                SELECT e.emp_id, e.full_name, COALESCE(e.pay_schedule,'Weekly'),
                    COUNT(a.attend_id) FILTER (WHERE a.status IN ('Present','Late')) AS worked,
                    COUNT(a.attend_id) FILTER (WHERE a.status = 'Half Day') AS halfdays,
                    COALESCE(SUM(
                        CASE
                            WHEN a.time_out > TIME '16:00'
                            THEN EXTRACT(EPOCH FROM (a.time_out - TIME '16:00')) / 3600.0
                            ELSE 0
                        END
                    ), 0) AS overtime_hours
                FROM employees e
                LEFT JOIN attendance a ON e.emp_id=a.emp_id
                    AND a.attend_date BETWEEN %s AND %s
                WHERE e.status='Active' AND COALESCE(e.classification,'Regular')='Regular'
                GROUP BY e.emp_id, e.full_name, e.pay_schedule
            """, (start_date, end_date))
            emp_rows = cur.fetchall()
            generated = 0
            for emp_id, full_name, pay_schedule, worked_days, halfdays, overtime_hours in emp_rows:
                hourly_rate = REGULAR_HOURLY_WAGE
                basic_pay   = round(REGULAR_SEMI_MONTHLY_PAY, 2)
                overtime_pay = round(float(overtime_hours or 0) * hourly_rate * OVERTIME_MULTIPLIER, 2)
                sss        = REGULAR_SSS_DEDUCTION
                philhealth = REGULAR_PHILHEALTH_DEDUCTION
                pagibig    = REGULAR_PAGIBIG_DEDUCTION
                # Check if payroll already exists for this emp+period
                cur.execute(
                    "SELECT payroll_id FROM payroll WHERE emp_id=%s AND period_id=%s",
                    (emp_id, pid)
                )
                existing = cur.fetchone()
                if existing:
                    cur.execute("""
                        UPDATE payroll SET basic_pay=%s, overtime_pay=%s, sss=%s, philhealth=%s, pagibig=%s
                        WHERE payroll_id=%s
                    """, (basic_pay, overtime_pay, sss, philhealth, pagibig, existing[0]))
                else:
                    cur.execute("""
                        INSERT INTO payroll
                        (period_id, emp_id, basic_pay, overtime_pay, sss, philhealth, pagibig, status)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,'Draft')
                    """, (pid, emp_id, basic_pay, overtime_pay, sss, philhealth, pagibig))
                generated += 1
            conn.commit(); conn.close()
            info(self, "Generated", f"Regular payroll generated for {generated} employee(s). Non-Regular payroll remains manual.")
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
                     deductions,sss,philhealth,pagibig,status)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
                       deductions,sss,philhealth,pagibig,status
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
                        sss=%s,philhealth=%s,pagibig=%s,status=%s
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
        self.setStyleSheet("QDialog{background:#f3f6fb;font-family:'Segoe UI';}"
                           "QLineEdit,QDateEdit{border:1px solid #d7dee8;border-radius:7px;"
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
            QDialog{background:#f3f6fb;font-family:'Segoe UI';}
            QComboBox,QDoubleSpinBox{border:1px solid #d7dee8;border-radius:7px;
            padding:6px 10px;font-size:13px;background:white;}
        """)
        self._employees = {}
        self._employee_classes_by_id = {}
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT emp_id, emp_code||' — '||full_name FROM employees WHERE status='Active' ORDER BY emp_code")
            self._employees = {r[1]: r[0] for r in cur.fetchall()}; conn.close()
        except: pass
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT emp_id, COALESCE(classification,'Regular') FROM employees WHERE status='Active'")
            self._employee_classes_by_id = {r[0]: r[1] for r in cur.fetchall()}
            conn.close()
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
        self.f_category = QLabel("Regular")
        self.f_category.setStyleSheet("font-weight:700;color:#0b1f3a;")

        def spin(v=0):
            s = QDoubleSpinBox(); s.setMaximum(999999); s.setDecimals(2); s.setPrefix("₱ ")
            s.setValue(float(v) if v else 0); return s

        self.f_basic  = spin(ex[2] if ex else 0)
        self.f_ot     = spin(ex[3] if ex else 0)
        self.f_total_salary = spin(ex[4] if ex else 0)
        self.f_deduct = spin(ex[5] if ex else 0)
        self.f_sss    = spin(ex[6] if ex else 0)
        self.f_phil   = spin(ex[7] if ex else 0)
        self.f_pagibig= spin(ex[8] if ex else 0)
        self.f_status = QComboBox(); self.f_status.addItems(["Draft","Approved","Paid"])
        if ex and ex[9]: self.f_status.setCurrentText(ex[9])

        form.addRow("Period",          self.f_period)
        form.addRow("Employee",        self.f_emp)
        form.addRow("Category",        self.f_category)
        form.addRow("Basic Pay",       self.f_basic)
        form.addRow("Overtime Pay",    self.f_ot)
        form.addRow("Total Salary",    self.f_total_salary)
        form.addRow("Other Deductions",self.f_deduct)
        form.addRow("SSS",             self.f_sss)
        form.addRow("PhilHealth",      self.f_phil)
        form.addRow("Pag-IBIG",        self.f_pagibig)
        form.addRow("Status",          self.f_status)
        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        self.f_emp.currentTextChanged.connect(self._apply_employee_classification)
        self._apply_employee_classification()

    def _apply_employee_classification(self):
        emp_id = self._employees.get(self.f_emp.currentText())
        category = employee_category(self._employee_classes_by_id.get(emp_id, "Regular"))
        is_regular = category == "Regular"
        self.f_category.setText(category)
        if is_regular:
            self.f_basic.setValue(REGULAR_SEMI_MONTHLY_PAY)
            self.f_basic.setEnabled(False)
            self.f_ot.setEnabled(True)
            self.f_total_salary.setValue(0)
            self.f_total_salary.setEnabled(False)
            self.f_sss.setValue(REGULAR_SSS_DEDUCTION)
            self.f_phil.setValue(REGULAR_PHILHEALTH_DEDUCTION)
            self.f_pagibig.setValue(REGULAR_PAGIBIG_DEDUCTION)
        else:
            self.f_basic.setValue(0)
            self.f_basic.setEnabled(False)
            self.f_ot.setValue(0)
            self.f_ot.setEnabled(False)
            self.f_total_salary.setEnabled(True)
        for field in (self.f_sss, self.f_phil, self.f_pagibig):
            field.setEnabled(is_regular)
            if not is_regular:
                field.setValue(0)

    def get_data(self):
        return (
            self.periods.get(self.f_period.currentText()),
            self._employees.get(self.f_emp.currentText()),
            self.f_basic.value(), self.f_ot.value(),
            self.f_total_salary.value(), self.f_deduct.value(),
            self.f_sss.value(), self.f_phil.value(),
            self.f_pagibig.value(),
            self.f_status.currentText()
        )
