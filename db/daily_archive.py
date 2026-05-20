"""
db/daily_archive.py
Daily snapshot storage for UnoCarshop ASMIS.
"""
from datetime import date
from decimal import Decimal

from psycopg2.extras import Json

from db.connection import db_cursor, fetch_all, fetch_one


SNAPSHOT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS daily_snapshots (
    snapshot_id   SERIAL PRIMARY KEY,
    snapshot_date DATE UNIQUE NOT NULL,
    summary       JSONB NOT NULL DEFAULT '{}'::jsonb,
    details       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by    INT REFERENCES users(user_id),
    generated_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP NOT NULL DEFAULT NOW()
)
"""


def ensure_daily_snapshot_table():
    with db_cursor(commit=True) as cur:
        cur.execute(SNAPSHOT_TABLE_SQL)


def _json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date,)):
        return value.isoformat()
    return value


def _rows_as_dicts(cur):
    columns = [desc[0] for desc in cur.description]
    return [
        {columns[i]: _json_value(value) for i, value in enumerate(row)}
        for row in cur.fetchall()
    ]


def _fetch_dicts(cur, query, params=None):
    cur.execute(query, params or ())
    return _rows_as_dicts(cur)


def _scalar(cur, query, params=None):
    cur.execute(query, params or ())
    row = cur.fetchone()
    return _json_value(row[0]) if row else 0


def _table_exists(cur, table_name):
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema='public' AND table_name=%s
        )
    """, (table_name,))
    return bool(cur.fetchone()[0])


def build_daily_snapshot(snapshot_date):
    """
    Build a JSON-safe summary and detailed record set for one business day.
    """
    ensure_daily_snapshot_table()
    with db_cursor() as cur:
        params = (snapshot_date,)
        has_appointments = _table_exists(cur, "appointments")
        has_insurance = _table_exists(cur, "insurance")
        summary = {
            "total_customers": _scalar(cur, "SELECT COUNT(*) FROM customers"),
            "total_vehicles": _scalar(cur, "SELECT COUNT(*) FROM vehicles"),
            "active_employees": _scalar(cur, "SELECT COUNT(*) FROM employees WHERE status='Active'"),
            "inventory_items": _scalar(cur, "SELECT COUNT(*) FROM inventory WHERE status='Active'"),
            "out_of_stock_items": _scalar(
                cur,
                "SELECT COUNT(*) FROM inventory WHERE quantity <= 0 AND status='Active'",
            ),
            "new_customers": _scalar(cur, "SELECT COUNT(*) FROM customers WHERE created_at::date=%s", params),
            "new_vehicles": _scalar(cur, "SELECT COUNT(*) FROM vehicles WHERE created_at::date=%s", params),
            "new_service_orders": _scalar(cur, "SELECT COUNT(*) FROM service_orders WHERE date_in=%s OR created_at::date=%s", (snapshot_date, snapshot_date)),
            "completed_service_orders": _scalar(cur, "SELECT COUNT(*) FROM service_orders WHERE status='Completed' AND date_out=%s", params),
            "appointments": _scalar(cur, "SELECT COUNT(*) FROM appointments WHERE appt_date=%s", params) if has_appointments else 0,
            "invoices": _scalar(cur, "SELECT COUNT(*) FROM billing WHERE bill_date=%s", params),
            "revenue": _scalar(cur, "SELECT COALESCE(SUM(total),0) FROM billing WHERE bill_date=%s AND status!='Void'", params),
            "billed_total": _scalar(cur, "SELECT COALESCE(SUM(total),0) FROM billing WHERE bill_date=%s AND status!='Void'", params),
            "outstanding_balance": 0,
        }

        attendance = _fetch_dicts(cur, """
            SELECT a.attend_date, e.emp_code, e.full_name,
                   COALESCE(d.dept_name,'') AS department,
                   COALESCE(p.position_name,'') AS position,
                   a.status, a.time_in::text, a.time_out::text
            FROM attendance a
            JOIN employees e ON a.emp_id=e.emp_id
            LEFT JOIN departments d ON e.dept_id=d.dept_id
            LEFT JOIN positions p ON e.position_id=p.position_id
            WHERE a.attend_date=%s
            ORDER BY e.emp_code
        """, params)

        attendance_counts = {}
        for row in attendance:
            attendance_counts[row["status"]] = attendance_counts.get(row["status"], 0) + 1
        summary["attendance"] = attendance_counts

        details = {
            "attendance": attendance,
            "service_orders": _fetch_dicts(cur, """
                SELECT so.order_no, so.status, so.priority, so.date_in, so.date_out,
                       c.full_name AS customer, v.plate_no,
                       COALESCE(v.make,'') AS make, COALESCE(v.model,'') AS model,
                       COALESCE(st.type_name,'') AS service_type,
                       COALESCE(e.full_name,'') AS assigned_employee,
                       so.description, so.remarks, so.created_at
                FROM service_orders so
                LEFT JOIN customers c ON so.cust_id=c.cust_id
                LEFT JOIN vehicles v ON so.vehicle_id=v.vehicle_id
                LEFT JOIN service_types st ON so.svc_type_id=st.svc_type_id
                LEFT JOIN employees e ON so.assign_emp=e.emp_id
                WHERE so.date_in=%s OR so.date_out=%s OR so.created_at::date=%s
                ORDER BY so.created_at
            """, (snapshot_date, snapshot_date, snapshot_date)),
            "billing": _fetch_dicts(cur, """
                SELECT b.bill_no, c.full_name AS customer, COALESCE(so.order_no,'') AS order_no,
                       b.subtotal, COALESCE(b.manpower,0) AS manpower, b.total,
                       b.status, b.payment_method, b.bill_date,
                       b.created_at
                FROM billing b
                LEFT JOIN customers c ON b.cust_id=c.cust_id
                LEFT JOIN service_orders so ON b.order_id=so.order_id
                WHERE b.bill_date=%s OR b.created_at::date=%s
                ORDER BY b.created_at
            """, (snapshot_date, snapshot_date)),
            "appointments": _fetch_dicts(cur, """
                SELECT a.appt_date, a.appt_time::text, a.status,
                       c.full_name AS customer, COALESCE(v.plate_no,'') AS plate_no,
                       COALESCE(st.type_name,'') AS service_type,
                       COALESCE(e.full_name,'') AS assigned_employee,
                       a.notes, a.created_at
                FROM appointments a
                JOIN customers c ON a.cust_id=c.cust_id
                LEFT JOIN vehicles v ON a.vehicle_id=v.vehicle_id
                LEFT JOIN service_types st ON a.svc_type_id=st.svc_type_id
                LEFT JOIN employees e ON a.assign_emp=e.emp_id
                WHERE a.appt_date=%s OR a.created_at::date=%s
                ORDER BY a.appt_date, a.appt_time
            """, (snapshot_date, snapshot_date)) if has_appointments else [],
            "customers": _fetch_dicts(cur, """
                SELECT cust_code, full_name, phone, email, address, created_at
                FROM customers
                WHERE created_at::date=%s
                ORDER BY created_at
            """, params),
            "vehicles": _fetch_dicts(cur, """
                SELECT v.plate_no, v.make, v.model, v.year, v.color,
                       c.full_name AS customer, v.created_at
                FROM vehicles v
                LEFT JOIN customers c ON v.cust_id=c.cust_id
                WHERE v.created_at::date=%s
                ORDER BY v.created_at
            """, params),
            "inventory": _fetch_dicts(cur, """
                SELECT i.item_code, i.item_name, COALESCE(ic.cat_name,'') AS category,
                       i.quantity, i.unit_cost, i.unit_price,
                       i.supplier, i.location, i.status
                FROM inventory i
                LEFT JOIN inventory_categories ic ON i.cat_id=ic.cat_id
                ORDER BY i.item_name
            """),
            "payroll": _fetch_dicts(cur, """
                SELECT pp.period_name, pp.start_date, pp.end_date,
                       e.emp_code, e.full_name, p.basic_pay, p.overtime_pay,
                       p.allowances, p.deductions, p.sss, p.philhealth,
                       p.pagibig, p.net_pay, p.status, p.created_at
                FROM payroll p
                LEFT JOIN payroll_periods pp ON p.period_id=pp.period_id
                JOIN employees e ON p.emp_id=e.emp_id
                WHERE p.created_at::date=%s
                ORDER BY p.created_at
            """, params),
            "insurance": _fetch_dicts(cur, """
                SELECT i.provider, i.policy_no, i.coverage, i.start_date, i.end_date,
                       i.premium, i.status, c.full_name AS customer, v.plate_no,
                       i.created_at
                FROM insurance i
                LEFT JOIN customers c ON i.cust_id=c.cust_id
                LEFT JOIN vehicles v ON i.vehicle_id=v.vehicle_id
                WHERE i.created_at::date=%s
                ORDER BY i.created_at
            """, params) if has_insurance else [],
        }
        return summary, details


def store_daily_snapshot(snapshot_date=None, user_id=None):
    snapshot_date = snapshot_date or date.today()
    summary, details = build_daily_snapshot(snapshot_date)
    with db_cursor(commit=True) as cur:
        cur.execute("""
            INSERT INTO daily_snapshots (snapshot_date, summary, details, created_by)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (snapshot_date) DO UPDATE SET
                summary = EXCLUDED.summary,
                details = EXCLUDED.details,
                created_by = COALESCE(EXCLUDED.created_by, daily_snapshots.created_by),
                updated_at = NOW()
            RETURNING snapshot_id
        """, (snapshot_date, Json(summary), Json(details), user_id))
        return cur.fetchone()[0]


def list_daily_snapshots(limit=90):
    ensure_daily_snapshot_table()
    return fetch_all("""
        SELECT snapshot_id, snapshot_date, summary, generated_at, updated_at
        FROM daily_snapshots
        ORDER BY snapshot_date DESC
        LIMIT %s
    """, (limit,))


def get_daily_snapshot(snapshot_id):
    ensure_daily_snapshot_table()
    return fetch_one("""
        SELECT snapshot_id, snapshot_date, summary, details, generated_at, updated_at
        FROM daily_snapshots
        WHERE snapshot_id=%s
    """, (snapshot_id,))


def snapshot_exists(snapshot_date):
    ensure_daily_snapshot_table()
    row = fetch_one("SELECT 1 FROM daily_snapshots WHERE snapshot_date=%s", (snapshot_date,))
    return bool(row)
