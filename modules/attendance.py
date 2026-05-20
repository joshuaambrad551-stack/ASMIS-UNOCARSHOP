"""
modules/attendance.py
UnoCarshop ASMIS - Attendance Module (Integrated v2)

Key integrations:
- Auto-loads ALL active employees when page opens
- Inline status dropdowns per employee row
- Save All button commits entire day at once
- Fires attendance_changed + dashboard_refresh on save
- Connected to payroll computation
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QDialog, QFormLayout, QDialogButtonBox,
    QDateEdit, QTimeEdit, QTableWidgetItem,
    QPushButton, QFrame
)
from PyQt5.QtCore import Qt, QDate, QTime
from PyQt5.QtGui import QColor
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

TEXT_MID = "#354154"


class AttendancePage(QWidget):
    def __init__(self, user=None):
        super().__init__()
        self.user = user
        self.setStyleSheet(f"background: {PAGE_BG};")
        self._inline_combos  = {}
        self._emp_rows       = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Summary cards
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        self.s_present = StatCard("Present Today",  "0", "?", GREEN)
        self.s_absent  = StatCard("Absent Today",   "0", "?", RED)
        self.s_late    = StatCard("Late Today",     "0", "?", ORANGE)
        self.s_onleave = StatCard("On Leave Today", "0", "?", BLUE)
        self.s_halfday = StatCard("Half Day Today", "0", "?", "#9b59b6")
        for s in [self.s_present, self.s_absent, self.s_late, self.s_onleave, self.s_halfday]:
            s.setFixedHeight(88)
            stats_row.addWidget(s)
        layout.addLayout(stats_row)

        # Toolbar
        toolbar = QHBoxLayout()
        lbl_date = QLabel("Date:")
        lbl_date.setStyleSheet(f"color:{TEXT_DARK};font-size:13px;font-weight:600;")
        self.date_filter = QDateEdit()
        self.date_filter.setCalendarPopup(True)
        self.date_filter.setDate(QDate.currentDate())
        self.date_filter.setFixedHeight(38)
        self.date_filter.setFixedWidth(150)
        self.date_filter.setStyleSheet(self._cs())
        self.date_filter.dateChanged.connect(self.refresh)

        self.search = SearchBar("Search employee...")
        self.search.setFixedWidth(220)
        self.search.textChanged.connect(self._filter_table)

        self.dept_filter = QComboBox()
        self.dept_filter.setFixedHeight(38)
        self.dept_filter.setFixedWidth(160)
        self.dept_filter.setStyleSheet(self._cs())
        self.dept_filter.currentIndexChanged.connect(self._filter_table)

        btn_save    = OrangeButton("Save All")
        btn_save.clicked.connect(self._save_all)
        btn_refresh = GhostButton("Refresh")
        btn_refresh.clicked.connect(self.refresh)
        btn_manual  = GhostButton("?  Manual Entry")
        btn_manual.clicked.connect(self._manual_record)

        toolbar.addWidget(lbl_date)
        toolbar.addWidget(self.date_filter)
        toolbar.addWidget(self.search)
        toolbar.addWidget(self.dept_filter)
        toolbar.addStretch()
        toolbar.addWidget(btn_refresh)
        toolbar.addWidget(btn_manual)
        toolbar.addWidget(btn_save)
        layout.addLayout(toolbar)

        # Bulk action bar
        bulk_bar = QHBoxLayout()
        lbl = QLabel("Mark all as:")
        lbl.setStyleSheet(f"color:{TEXT_MID};font-size:12px;margin-right:6px;")
        bulk_bar.addWidget(lbl)
        for status, bg, fg in [
            ("Present",  "#e8f5e9", "#2e7d32"),
            ("Absent",   "#ffebee", "#c62828"),
            ("Late",     "#fbe8ea", "#9f0f1a"),
            ("On Leave", "#e3f2fd", "#1565c0"),
            ("Half Day", "#f3e5f5", "#6a1b9a"),
        ]:
            btn = QPushButton(status)
            btn.setFixedHeight(28)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton{{background:{bg};color:{fg};border:1px solid {bg};
                border-radius:5px;font-size:11px;padding:0 10px;font-weight:600;}}
            """)
            btn.clicked.connect(lambda _, s=status: self._mark_all(s))
            bulk_bar.addWidget(btn)
        bulk_bar.addStretch()
        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet(f"color:{TEXT_SOFT};font-size:12px;")
        bulk_bar.addWidget(self.count_lbl)
        layout.addLayout(bulk_bar)

        # Table
        cols = ["#", "Code", "Full Name", "Department", "Position",
                "Status", "Time In", "Time Out", "Save"]
        self.table = StyledTable(cols)
        self.table.setColumnWidth(0,  35)
        self.table.setColumnWidth(1,  85)
        self.table.setColumnWidth(2, 150)
        self.table.setColumnWidth(3, 120)
        self.table.setColumnWidth(4, 120)
        self.table.setColumnWidth(5, 120)
        self.table.setColumnWidth(6,  75)
        self.table.setColumnWidth(7,  75)
        self.table.setColumnWidth(8,  100)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSortingEnabled(False)
        layout.addWidget(self.table)

    # â”€â”€ Data loading â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def refresh(self):
        self._inline_combos.clear()
        self._emp_rows.clear()
        self._load_departments()
        self._load_all_employees()
        self._update_summary()

    def _load_departments(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT dept_name FROM departments ORDER BY dept_name")
            depts = [r[0] for r in cur.fetchall()]
            conn.close()
            self.dept_filter.blockSignals(True)
            self.dept_filter.clear()
            self.dept_filter.addItem("All Departments")
            self.dept_filter.addItems(depts)
            self.dept_filter.blockSignals(False)
        except: pass

    def _load_all_employees(self):
        date_str = self.date_filter.date().toString("yyyy-MM-dd")
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("""
                SELECT e.emp_id, e.emp_code, e.full_name,
                       COALESCE(d.dept_name,'-'), COALESCE(p.position_name,'-'),
                       a.attend_id, COALESCE(a.status,'Present'),
                       a.time_in, a.time_out
                FROM employees e
                LEFT JOIN departments d ON e.dept_id = d.dept_id
                LEFT JOIN positions p ON e.position_id = p.position_id
                LEFT JOIN attendance a ON e.emp_id = a.emp_id AND a.attend_date = %s
                WHERE e.status = 'Active'
                ORDER BY d.dept_name, e.emp_code
            """, (date_str,))
            rows = cur.fetchall()
            conn.close()

            self.table.setRowCount(0)
            for idx, rd in enumerate(rows):
                emp_id, emp_code, full_name, dept, position, \
                    attend_id, att_status, time_in, time_out = rd

                r = self.table.rowCount()
                self.table.insertRow(r)
                self.table.setRowHeight(r, 40)
                self._emp_rows[emp_id] = r

                num = QTableWidgetItem(str(idx + 1))
                num.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
                self.table.setItem(r, 0, num)

                for c, val in enumerate([emp_code, full_name, dept, position]):
                    item = QTableWidgetItem(str(val))
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    self.table.setItem(r, c + 1, item)

                # Status combo
                combo = QComboBox()
                combo.addItems(["Present", "Absent", "Late", "Half Day", "On Leave"])
                combo.setCurrentText(att_status)
                combo.setStyleSheet(f"""
                    QComboBox{{border:1px solid {BORDER};border-radius:6px;
                    padding:3px 8px;font-size:12px;background:white;}}
                    QComboBox::drop-down{{border:none;width:18px;}}
                """)
                combo.currentTextChanged.connect(lambda txt, eid=emp_id, row=r: self._color_row(row, txt))
                self.table.setCellWidget(r, 5, combo)
                self._inline_combos[emp_id] = combo

                # Time in / out
                ti = QTableWidgetItem(str(time_in)[:5] if time_in else "08:00")
                ti.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
                self.table.setItem(r, 6, ti)
                to_ = QTableWidgetItem(str(time_out)[:5] if time_out else "16:00")
                to_.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
                self.table.setItem(r, 7, to_)

                self._color_row(r, att_status)

                # Per-row save button
                btn_s = QPushButton("Save")
                btn_s.setFixedHeight(27)
                btn_s.setCursor(Qt.PointingHandCursor)
                btn_s.setStyleSheet("""
                    QPushButton{background:#0b1f3a;color:white;border:none;
                    border-radius:5px;font-size:11px;padding:0 10px;font-weight:600;}
                    QPushButton:hover{background:#123a63;}
                """)
                btn_s.clicked.connect(lambda _, eid=emp_id: self._save_one(eid))
                act = QWidget(); act.setStyleSheet("background:transparent;")
                al = QHBoxLayout(act); al.setContentsMargins(4,2,4,2)
                al.addWidget(btn_s)
                self.table.setCellWidget(r, 8, act)

            self.count_lbl.setText(f"{len(rows)} employee(s)")
        except Exception as e:
            error(self, "Load Error", str(e))

    def _color_row(self, row, status):
        colors = {
            "Present": "#f0faf0", "Absent": "#fff5f5",
            "Late": "#fffbf0", "On Leave": "#f0f5ff", "Half Day": "#faf0ff",
        }
        bg = QColor(colors.get(status, "#ffffff"))
        for c in range(6):  # only static cells
            item = self.table.item(row, c)
            if item:
                item.setBackground(bg)

    def _status_from_times(self, selected_status, time_in, time_out):
        if selected_status in ("Absent", "Half Day", "On Leave"):
            return selected_status
        if time_in:
            parsed = QTime.fromString(time_in, "HH:mm")
            if not parsed.isValid():
                parsed = QTime.fromString(time_in, "H:mm")
            if parsed.isValid() and parsed > QTime(8, 0):
                return "Late"
        return "Present"

    def _mark_all(self, status):
        for emp_id, combo in self._inline_combos.items():
            row = self._emp_rows.get(emp_id)
            if row is not None and not self.table.isRowHidden(row):
                combo.setCurrentText(status)

    def _filter_table(self):
        search = self.search.text().lower()
        dept   = self.dept_filter.currentText()
        for emp_id, row in self._emp_rows.items():
            n = (self.table.item(row, 2).text().lower() if self.table.item(row, 2) else "")
            c = (self.table.item(row, 1).text().lower() if self.table.item(row, 1) else "")
            d = (self.table.item(row, 3).text() if self.table.item(row, 3) else "")
            ok_search = not search or search in n or search in c
            ok_dept   = dept == "All Departments" or d == dept
            self.table.setRowHidden(row, not (ok_search and ok_dept))

    # â”€â”€ Save logic â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _save_one(self, emp_id):
        date_str = self.date_filter.date().toString("yyyy-MM-dd")
        combo    = self._inline_combos.get(emp_id)
        row      = self._emp_rows.get(emp_id)
        if combo is None: return
        ti_item  = self.table.item(row, 6)
        to_item  = self.table.item(row, 7)
        time_in = ti_item.text() if ti_item else "08:00"
        time_out = to_item.text() if to_item else "16:00"
        status = self._status_from_times(combo.currentText(), time_in, time_out)
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("""
                INSERT INTO attendance
                (emp_id,attend_date,time_in,time_out,status,recorded_by)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT (emp_id,attend_date) DO UPDATE SET
                    time_in=EXCLUDED.time_in, time_out=EXCLUDED.time_out,
                    status=EXCLUDED.status
            """, (emp_id, date_str,
                  time_in,
                  time_out,
                  status,
                  self.user[0] if self.user else None))
            conn.commit(); conn.close()
            combo.setCurrentText(status)
            self._color_row(row, status)
            self._update_summary()
            bus.attendance_changed.emit()
            bus.dashboard_refresh.emit()
        except Exception as e:
            error(self, "Save Error", str(e))

    def _save_all(self):
        date_str = self.date_filter.date().toString("yyyy-MM-dd")
        saved = 0
        try:
            conn = get_connection(); cur = conn.cursor()
            for emp_id, combo in self._inline_combos.items():
                row    = self._emp_rows.get(emp_id)
                if row is not None and self.table.isRowHidden(row):
                    continue
                ti_item = self.table.item(row, 6)
                to_item = self.table.item(row, 7)
                time_in = ti_item.text() if ti_item else "08:00"
                time_out = to_item.text() if to_item else "16:00"
                status = self._status_from_times(combo.currentText(), time_in, time_out)
                cur.execute("""
                    INSERT INTO attendance
                    (emp_id,attend_date,time_in,time_out,status,recorded_by)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (emp_id,attend_date) DO UPDATE SET
                        time_in=EXCLUDED.time_in, time_out=EXCLUDED.time_out,
                        status=EXCLUDED.status
                """, (emp_id, date_str,
                      time_in,
                      time_out,
                      status,
                      self.user[0] if self.user else None))
                combo.setCurrentText(status)
                self._color_row(row, status)
                saved += 1
            conn.commit(); conn.close()
            self._update_summary()
            bus.attendance_changed.emit()
            bus.dashboard_refresh.emit()
            info(self, "Saved", f"Attendance saved for {saved} employee(s).")
        except Exception as e:
            error(self, "Save Error", str(e))

    def _manual_record(self):
        dlg = AttendanceDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("""
                    INSERT INTO attendance
                    (emp_id,attend_date,time_in,time_out,status,recorded_by)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (emp_id,attend_date) DO UPDATE SET
                        time_in=EXCLUDED.time_in, time_out=EXCLUDED.time_out,
                        status=EXCLUDED.status
                """, data + (self.user[0] if self.user else None,))
                conn.commit(); conn.close()
                info(self, "Saved", "Attendance record saved.")
                self.refresh()
                bus.attendance_changed.emit()
                bus.dashboard_refresh.emit()
            except Exception as e:
                error(self, "Save Error", str(e))

    def _update_summary(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            date_str = self.date_filter.date().toString("yyyy-MM-dd")
            for stat, widget in [
                ("Present",  self.s_present),
                ("Absent",   self.s_absent),
                ("Late",     self.s_late),
                ("On Leave", self.s_onleave),
                ("Half Day", self.s_halfday),
            ]:
                cur.execute(
                    "SELECT COUNT(*) FROM attendance WHERE attend_date=%s AND status=%s",
                    (date_str, stat)
                )
                widget.set_value(cur.fetchone()[0])
            conn.close()
        except Exception as e:
            print(f"Summary error: {e}")

    def _cs(self):
        return f"""
            QComboBox, QDateEdit {{
                border:1px solid {BORDER}; border-radius:8px;
                padding:0 10px; font-size:13px; color:{TEXT_DARK}; background:white;
            }}
            QComboBox::drop-down {{ border:none; width:20px; }}
        """


class AttendanceDialog(QDialog):
    def __init__(self, parent, existing=None):
        super().__init__(parent)
        self.setWindowTitle("Manual Attendance Record")
        self.resize(620, 440)
        self.setMinimumSize(580, 420)
        self.setStyleSheet("""
            QDialog{background:#f3f6fb;font-family:'Segoe UI';}
            QLineEdit,QComboBox,QDateEdit,QTimeEdit,QTextEdit{
                border:1px solid #d7dee8;border-radius:7px;
                padding:6px 10px;font-size:13px;background:white;}
        """)
        self._employees = {}
        self._load_employees()
        self._build(existing)

    def _load_employees(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute(
                "SELECT emp_id, emp_code||' - '||full_name FROM employees "
                "WHERE status='Active' ORDER BY emp_code"
            )
            self._employees = {r[1]: r[0] for r in cur.fetchall()}
            conn.close()
        except: pass

    def _build(self, ex):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.f_emp = QComboBox()
        self.f_emp.addItems(list(self._employees.keys()))
        if ex:
            for label, eid in self._employees.items():
                if eid == ex[0]: self.f_emp.setCurrentText(label); break

        self.f_date = QDateEdit()
        self.f_date.setCalendarPopup(True)
        self.f_date.setDate(
            QDate.fromString(str(ex[1]),"yyyy-MM-dd") if ex and ex[1] else QDate.currentDate()
        )
        self.f_in  = QTimeEdit()
        self.f_in.setDisplayFormat("HH:mm")
        self.f_in.setTime(QTime.fromString(str(ex[2])[:5],"HH:mm") if ex and ex[2] else QTime(8,0))
        self.f_out = QTimeEdit()
        self.f_out.setDisplayFormat("HH:mm")
        self.f_out.setTime(QTime.fromString(str(ex[3])[:5],"HH:mm") if ex and ex[3] else QTime(16,0))
        self.f_status = QComboBox()
        self.f_status.addItems(["Present","Absent","Late","Half Day","On Leave"])
        if ex and ex[4]: self.f_status.setCurrentText(ex[4])

        form.addRow("Employee *", self.f_emp)
        form.addRow("Date *",     self.f_date)
        form.addRow("Time In",    self.f_in)
        form.addRow("Time Out",   self.f_out)
        form.addRow("Status",     self.f_status)
        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Save).setStyleSheet(
            "background:#0b1f3a;color:white;border:none;border-radius:6px;"
            "padding:6px 18px;font-weight:700;"
        )
        btns.button(QDialogButtonBox.Cancel).setStyleSheet(
            "background:#eee;color:#555;border:none;border-radius:6px;padding:6px 14px;"
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_data(self):
        emp_id = self._employees.get(self.f_emp.currentText())
        return (
            emp_id,
            self.f_date.date().toString("yyyy-MM-dd"),
            self.f_in.time().toString("HH:mm"),
            self.f_out.time().toString("HH:mm"),
            "Late" if self.f_status.currentText() == "Present" and self.f_in.time() > QTime(8, 0) else self.f_status.currentText(),
        )

