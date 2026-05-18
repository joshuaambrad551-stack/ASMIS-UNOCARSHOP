"""
modules/inventory.py
UnoCarshop ASMIS — Inventory (Integrated v2)

Key changes:
- Removed Consumables and Suspension categories
- Fires inventory_changed + dashboard_refresh on all CRUD
- Low stock alerts reflected on dashboard in real time
- Parts used in service orders auto-deduct quantity via DB trigger
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QDialog, QFormLayout, QDialogButtonBox,
    QSpinBox, QDoubleSpinBox, QTableWidgetItem,
    QPushButton, QLineEdit, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.widgets import (
    OrangeButton, GhostButton, SearchBar, StyledTable,
    StatCard, confirm, info, error,
    PAGE_BG, ORANGE, BORDER, TEXT_DARK, TEXT_SOFT,
    GREEN, RED, BLUE
)
from db.connection import get_connection
from db.events import bus


class InventoryPage(QWidget):
    def __init__(self, user=None):
        super().__init__()
        self.user = user
        self.setStyleSheet(f"background: {PAGE_BG};")
        self._categories = {}
        self._build_ui()
        # Auto-refresh when service orders use parts
        bus.inventory_changed.connect(self.refresh)
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        stats = QHBoxLayout(); stats.setSpacing(12)
        self.s_total = StatCard("Total Items",  "0",  "📦", ORANGE)
        self.s_low   = StatCard("Low Stock",    "0",  "⚠",  RED)
        self.s_value = StatCard("Stock Value",  "₱0", "💰", GREEN)
        self.s_cats  = StatCard("Categories",   "0",  "🏷",  BLUE)
        for s in [self.s_total, self.s_low, self.s_value, self.s_cats]:
            s.setFixedHeight(88); stats.addWidget(s)
        layout.addLayout(stats)

        toolbar = QHBoxLayout()
        self.search = SearchBar("Search by name, code, supplier…")
        self.search.setFixedWidth(280)
        self.search.textChanged.connect(self._filter)

        self.cat_filter = QComboBox()
        self.cat_filter.setFixedHeight(38); self.cat_filter.setFixedWidth(180)
        self.cat_filter.setStyleSheet(self._cs())
        self.cat_filter.currentIndexChanged.connect(self._filter)

        self.stock_filter = QComboBox()
        self.stock_filter.addItems(["All Stock","⚠ Low Stock","✅ In Stock"])
        self.stock_filter.setFixedHeight(38); self.stock_filter.setFixedWidth(140)
        self.stock_filter.setStyleSheet(self._cs())
        self.stock_filter.currentIndexChanged.connect(self._filter)

        btn_add     = OrangeButton("➕  Add Item")
        btn_add.clicked.connect(self._add_item)
        btn_refresh = GhostButton("🔄  Refresh")
        btn_refresh.clicked.connect(self.refresh)

        toolbar.addWidget(self.search)
        toolbar.addWidget(self.cat_filter)
        toolbar.addWidget(self.stock_filter)
        toolbar.addStretch()
        toolbar.addWidget(btn_refresh)
        toolbar.addWidget(btn_add)
        layout.addLayout(toolbar)

        cols = ["Code","Item Name","Category","Unit","Qty",
                "Reorder Lvl","Unit Cost","Unit Price","Supplier","Actions"]
        self.table = StyledTable(cols)
        self.table.setColumnWidth(0,  90)
        self.table.setColumnWidth(1, 180)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3,  55)
        self.table.setColumnWidth(4,  55)
        self.table.setColumnWidth(5,  80)
        self.table.setColumnWidth(6,  90)
        self.table.setColumnWidth(7,  90)
        self.table.setColumnWidth(8, 120)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet(f"color:{TEXT_SOFT};font-size:12px;")
        layout.addWidget(self.count_lbl)

    def refresh(self):
        self._load_categories()
        self._load_items()

    def _load_categories(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            # Ensure Consumables and Suspension are removed
            cur.execute("DELETE FROM inventory_categories WHERE cat_name IN ('Consumables','Suspension')")
            conn.commit()
            cur.execute("SELECT cat_id, cat_name FROM inventory_categories ORDER BY cat_name")
            rows = cur.fetchall(); conn.close()
            self._categories = {r[1]: r[0] for r in rows}
            self.cat_filter.blockSignals(True)
            self.cat_filter.clear()
            self.cat_filter.addItem("All Categories")
            self.cat_filter.addItems(list(self._categories.keys()))
            self.cat_filter.blockSignals(False)
        except Exception as e:
            print(f"Category load: {e}")

    def _load_items(self, search="", cat="", stock_filter=""):
        try:
            conn = get_connection(); cur = conn.cursor()
            q = """
                SELECT i.item_id, i.item_code, i.item_name,
                       COALESCE(c.cat_name,'—'), i.unit,
                       i.quantity, i.reorder_lvl,
                       i.unit_cost, i.unit_price, COALESCE(i.supplier,'')
                FROM inventory i
                LEFT JOIN inventory_categories c ON i.cat_id=c.cat_id
                WHERE i.status='Active'
            """
            params = []
            if search:
                q += " AND (LOWER(i.item_name) LIKE %s OR i.item_code LIKE %s OR LOWER(COALESCE(i.supplier,'')) LIKE %s)"
                s = f"%{search.lower()}%"; params += [s, s, s]
            if cat and cat != "All Categories":
                q += " AND c.cat_name=%s"; params.append(cat)
            if "Low Stock" in stock_filter:
                q += " AND i.quantity<=i.reorder_lvl"
            elif "In Stock" in stock_filter:
                q += " AND i.quantity>i.reorder_lvl"
            q += " ORDER BY i.item_code"
            cur.execute(q, params); rows = cur.fetchall()

            cur.execute("SELECT COUNT(*) FROM inventory WHERE status='Active'")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM inventory WHERE quantity<=reorder_lvl AND status='Active'")
            low = cur.fetchone()[0]
            cur.execute("SELECT COALESCE(SUM(quantity*unit_cost),0) FROM inventory WHERE status='Active'")
            val = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM inventory_categories")
            cats = cur.fetchone()[0]
            conn.close()

            self.s_total.set_value(total)
            self.s_low.set_value(low)
            self.s_value.set_value(f"₱{float(val):,.0f}")
            self.s_cats.set_value(cats)

            self.table.setRowCount(0)
            self._item_ids = []
            for rd in rows:
                r = self.table.rowCount()
                self.table.insertRow(r); self.table.setRowHeight(r, 38)
                self._item_ids.append(rd[0])
                low_flag = rd[5] <= rd[6]
                data = [rd[1], rd[2], rd[3], rd[4],
                        rd[5], rd[6],
                        f"₱{float(rd[7]):,.2f}",
                        f"₱{float(rd[8]):,.2f}",
                        rd[9]]
                for c, val_ in enumerate(data):
                    item = QTableWidgetItem(str(val_))
                    item.setTextAlignment(
                        (Qt.AlignRight if c in (4,5,6,7) else Qt.AlignLeft) | Qt.AlignVCenter
                    )
                    if c == 4 and low_flag:
                        item.setForeground(QColor(RED))
                        item.setBackground(QColor("#fff5f5"))
                    self.table.setItem(r, c, item)

                iid = rd[0]
                act = QWidget(); act.setStyleSheet("background:transparent;")
                al = QHBoxLayout(act); al.setContentsMargins(4,2,4,2); al.setSpacing(4)
                btn_e = QPushButton("Edit"); btn_e.setFixedHeight(27); btn_e.setCursor(Qt.PointingHandCursor)
                btn_e.setStyleSheet("QPushButton{background:#e7eef8;color:#123a63;border:1px solid #8aa4c4;border-radius:5px;font-size:11px;padding:0 8px;}QPushButton:hover{background:#dbe9ff;}")
                btn_e.clicked.connect(lambda _, i=iid: self._edit_item(i))
                btn_d = QPushButton("Del"); btn_d.setFixedHeight(27); btn_d.setCursor(Qt.PointingHandCursor)
                btn_d.setStyleSheet("QPushButton{background:#ffebee;color:#c62828;border:1px solid #ef9a9a;border-radius:5px;font-size:11px;padding:0 8px;}QPushButton:hover{background:#ffcdd2;}")
                btn_d.clicked.connect(lambda _, i=iid: self._delete_item(i))
                al.addWidget(btn_e); al.addWidget(btn_d)
                self.table.setCellWidget(r, 9, act)

            self.count_lbl.setText(f"Showing {len(rows)} item(s)  |  Low stock: {low}")
        except Exception as e:
            error(self, "Load Error", str(e))

    def _filter(self):
        self._load_items(
            search=self.search.text(),
            cat=self.cat_filter.currentText(),
            stock_filter=self.stock_filter.currentText()
        )

    def _add_item(self):
        dlg = InventoryDialog(self, self._categories)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("SELECT 1 FROM inventory WHERE item_code=%s", (data[0],))
                if cur.fetchone():
                    conn.close()
                    error(self, "Duplicate Code", f"Item code '{data[0]}' already exists. Use a different code or edit the existing item.")
                    return
                cur.execute("""
                    INSERT INTO inventory
                    (item_code,item_name,cat_id,unit,quantity,reorder_lvl,
                     unit_cost,unit_price,supplier,location)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, data)
                conn.commit(); conn.close()
                info(self, "Saved", "Item added to inventory.")
                self.refresh()
                bus.inventory_changed.emit()
                bus.dashboard_refresh.emit()
            except Exception as e: error(self, "Error", str(e))

    def _edit_item(self, item_id):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("""SELECT item_code,item_name,cat_id,unit,quantity,reorder_lvl,
                                  unit_cost,unit_price,supplier,location
                           FROM inventory WHERE item_id=%s""", (item_id,))
            row = cur.fetchone(); conn.close()
        except Exception as e: error(self, "Error", str(e)); return
        dlg = InventoryDialog(self, self._categories, row)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("SELECT 1 FROM inventory WHERE item_code=%s AND item_id<>%s", (data[0], item_id))
                if cur.fetchone():
                    conn.close()
                    error(self, "Duplicate Code", f"Item code '{data[0]}' already exists. Use a different code.")
                    return
                cur.execute("""UPDATE inventory SET item_code=%s,item_name=%s,cat_id=%s,unit=%s,
                    quantity=%s,reorder_lvl=%s,unit_cost=%s,unit_price=%s,supplier=%s,location=%s
                    WHERE item_id=%s""", data+(item_id,))
                conn.commit(); conn.close()
                info(self, "Updated", "Item updated.")
                self.refresh()
                bus.inventory_changed.emit()
                bus.dashboard_refresh.emit()
            except Exception as e: error(self, "Error", str(e))

    def _delete_item(self, item_id):
        if confirm(self, "Delete", "Remove this item from inventory?"):
            try:
                conn = get_connection(); cur = conn.cursor()
                cur.execute("UPDATE inventory SET status='Inactive' WHERE item_id=%s", (item_id,))
                conn.commit(); conn.close()
                self.refresh()
                bus.inventory_changed.emit()
                bus.dashboard_refresh.emit()
            except Exception as e: error(self, "Error", str(e))

    def _cs(self):
        return f"QComboBox{{border:1px solid {BORDER};border-radius:8px;padding:0 10px;font-size:13px;color:{TEXT_DARK};background:white;}}QComboBox::drop-down{{border:none;width:20px;}}"


class InventoryDialog(QDialog):
    def __init__(self, parent, categories, existing=None):
        super().__init__(parent)
        self.categories = categories
        self.setWindowTitle("Inventory Item")
        self.setFixedWidth(460)
        self.setStyleSheet("""
            QDialog{background:#f3f6fb;font-family:'Segoe UI';}
            QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox{border:1px solid #d7dee8;
            border-radius:7px;padding:6px 10px;font-size:13px;background:white;}
        """)
        self._build(existing)

    def _build(self, ex):
        layout = QVBoxLayout(self); layout.setContentsMargins(22,18,22,18)
        form = QFormLayout(); form.setSpacing(10)

        self.f_code  = QLineEdit(ex[0] if ex else "")
        self.f_name  = QLineEdit(ex[1] if ex else "")
        self.f_cat   = QComboBox(); self.f_cat.addItems(list(self.categories.keys()))
        if ex and ex[2]:
            for name, cid in self.categories.items():
                if cid == ex[2]: self.f_cat.setCurrentText(name)
        self.f_unit  = QLineEdit(ex[3] if ex else "pcs")
        self.f_qty   = QSpinBox(); self.f_qty.setMaximum(999999)
        self.f_qty.setValue(int(ex[4]) if ex and ex[4] else 0)
        self.f_reord = QSpinBox(); self.f_reord.setMaximum(9999)
        self.f_reord.setValue(int(ex[5]) if ex and ex[5] else 5)

        def money(v=0):
            s = QDoubleSpinBox(); s.setMaximum(999999); s.setDecimals(2); s.setPrefix("₱ ")
            s.setValue(float(v) if v else 0); return s

        self.f_cost  = money(ex[6] if ex else 0)
        self.f_price = money(ex[7] if ex else 0)
        self.f_supp  = QLineEdit(ex[8] if ex and ex[8] else "")
        self.f_loc   = QLineEdit(ex[9] if ex and ex[9] else "")

        form.addRow("Item Code *",   self.f_code)
        form.addRow("Item Name *",   self.f_name)
        form.addRow("Category",      self.f_cat)
        form.addRow("Unit",          self.f_unit)
        form.addRow("Quantity",      self.f_qty)
        form.addRow("Reorder Level", self.f_reord)
        form.addRow("Unit Cost",     self.f_cost)
        form.addRow("Unit Price",    self.f_price)
        form.addRow("Supplier",      self.f_supp)
        form.addRow("Location",      self.f_loc)
        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Save).setStyleSheet("background:#0b1f3a;color:white;border:none;border-radius:6px;padding:6px 18px;font-weight:700;")
        btns.button(QDialogButtonBox.Cancel).setStyleSheet("background:#eee;color:#555;border:none;border-radius:6px;padding:6px 14px;")
        btns.accepted.connect(self._validate); btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _validate(self):
        if not self.f_code.text().strip() or not self.f_name.text().strip():
            QMessageBox.warning(self, "Validation", "Item code and name are required.")
            return
        self.accept()

    def get_data(self):
        cat_id = self.categories.get(self.f_cat.currentText())
        return (self.f_code.text().strip(), self.f_name.text().strip(),
                cat_id, self.f_unit.text().strip(),
                self.f_qty.value(), self.f_reord.value(),
                self.f_cost.value(), self.f_price.value(),
                self.f_supp.text().strip(), self.f_loc.text().strip())
