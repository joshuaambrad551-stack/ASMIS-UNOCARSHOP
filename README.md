# UnoCarshop ASMIS — v2 Integrated
### Auto Shop Management & Information System — Fully Connected

---

## 🗂 Project Structure

```
ASMIS/
├── main.py
├── requirements.txt
├── README.md
├── db/
│   ├── connection.py        # PostgreSQL connection config
│   ├── events.py            # NEW: Centralized EventBus
│   ├── schema.sql           # Full schema + seed data
│   └── migrate_v2.sql       # NEW: Integration tables, views, triggers
└── modules/
    ├── widgets.py
    ├── login.py
    ├── main_window.py
    ├── dashboard.py          # Live stats, auto-refresh on all events
    ├── employees.py          # Emits events on CRUD
    ├── attendance.py         # Auto-loads all employees inline
    ├── payroll.py            # Connected to attendance, auto-compute
    ├── inventory.py          # Removed Consumables/Suspension
    ├── customers.py          # Vehicles use free-text fields
    ├── service_orders.py     # Parts usage, auto-billing trigger
    ├── billing.py            # Auto-created when order completes
    └── insurance.py          # Auto-fills customer from vehicle
```

---

## ⚙️ Setup Instructions

### Step 1 — Install dependencies
```powershell
pip install PyQt5 psycopg2-binary
```

### Step 2 — Create database
```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -c "CREATE DATABASE unocarshop;"
```

### Step 3 — Run base schema
```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d unocarshop -f db/schema.sql
```

### Step 4 — Run v2 migration (REQUIRED)
```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d unocarshop -f db/migrate_v2.sql
```

### Step 5 — Set your password in db/connection.py
```python
"password": os.environ.get("ASMIS_DB_PASS", "YOUR_POSTGRESQL_PASSWORD"),
```

### Step 6 — Run
```powershell
python main.py
```

### Login
| Field    | Value     |
|----------|-----------|
| Username | `admin`   |
| Password | `admin123`|

---

## 🔗 Integration Map

```
EVENT BUS (db/events.py)
  └── All modules emit signals on data change
  └── data_changed broadcasts one centralized refresh signal for cached pages
  └── Dashboard subscribes to ALL signals → auto-refreshes

DATABASE LAYER (db/connection.py)
  └── PostgreSQL is the single source of truth
  └── db_cursor / fetch_one / fetch_all / execute_write provide shared access helpers

CUSTOMERS → VEHICLES → SERVICE ORDERS → BILLING (auto-created)
                             │
                        PARTS USED → INVENTORY (auto-deducted)

EMPLOYEES → ATTENDANCE → PAYROLL (auto-computed)

APPOINTMENTS → SERVICE ORDERS (auto-converted when In Progress)
```

---

## ✅ Key v2 Features

### Attendance Module
- Opens with ALL active employees already listed
- Inline status dropdown per employee row
- Bulk "Mark All As" buttons (Present/Absent/Late etc.)
- Save All button saves entire day in one click
- Individual Save button per row
- Auto-syncs with Payroll when saved

### Payroll Module
- "Generate from Attendance" button computes pay automatically
- Attendance Summary tab shows days present/absent per period
- Auto-calculates SSS, PhilHealth, Pag-IBIG deductions
- Listens to attendance changes and auto-refreshes

### Service Orders
- Parts dialog — select inventory items, auto-deducts stock
- Mark as Completed → invoice auto-created in Billing
- Vehicle selection auto-fills customer field

### Dashboard
- Pulls live data from `dashboard_stats` database view
- Auto-refreshes every 60 seconds
- Reacts instantly to changes in any module
- Shows: KPIs, recent orders, attendance, low stock, billing, appointments

### Inventory
- Consumables and Suspension categories removed
- Stock auto-decreases when parts used in service orders
- Low stock alerts visible on dashboard in real time

### Vehicles
- Make, Model, Year, Color are all free-text inputs
- No predefined dropdown selections

---

## 🛠 Troubleshooting

| Error | Fix |
|-------|-----|
| `No module named 'psycopg2'` | `pip install psycopg2-binary` |
| `No module named 'PyQt5'` | `pip install PyQt5` |
| `password authentication failed` | Update password in `db/connection.py` |
| `relation "dashboard_stats" does not exist` | Run `db/migrate_v2.sql` |
| `relation "service_order_parts" does not exist` | Run `db/migrate_v2.sql` |
| `relation "appointments" does not exist` | Run `db/migrate_v2.sql` |
| Parts dialog says "Setup Required" | Run `db/migrate_v2.sql` |
| `High DPI` warning on startup | Already fixed in main.py |

---

*© 2026 UnoCarshop. All rights reserved.*
