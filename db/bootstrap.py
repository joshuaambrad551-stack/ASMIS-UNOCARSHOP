"""
db/bootstrap.py
Runtime-safe schema guards for older databases.
Only applies additive, idempotent changes.
"""
from db.connection import get_connection


def ensure_runtime_schema():
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Billing compatibility
        cur.execute("ALTER TABLE billing ADD COLUMN IF NOT EXISTS manpower NUMERIC(10,2) DEFAULT 0")
        cur.execute("UPDATE billing SET manpower = 0 WHERE manpower IS NULL")

        # Service order compatibility
        cur.execute("ALTER TABLE service_orders ADD COLUMN IF NOT EXISTS assign_emp INT REFERENCES employees(emp_id)")
        cur.execute("ALTER TABLE service_orders ADD COLUMN IF NOT EXISTS priority VARCHAR(20) DEFAULT 'Normal'")
        cur.execute("ALTER TABLE service_orders ADD COLUMN IF NOT EXISTS remarks TEXT")
        cur.execute("ALTER TABLE service_orders ADD COLUMN IF NOT EXISTS date_out DATE")

        cur.execute("ALTER TABLE service_orders DROP CONSTRAINT IF EXISTS service_orders_priority_check")
        cur.execute(
            "ALTER TABLE service_orders ADD CONSTRAINT service_orders_priority_check "
            "CHECK (priority IN ('Low','Normal','High','Urgent'))"
        )

        # Customer insurance flow compatibility
        cur.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS payment_type VARCHAR(20) DEFAULT 'Cash'")
        cur.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS coverage_type VARCHAR(30) DEFAULT 'Own Damage'")
        cur.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS insurance_provider VARCHAR(160)")
        cur.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS loa_amount NUMERIC(12,2) DEFAULT 0")
        cur.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS assured_share NUMERIC(12,2) DEFAULT 0")
        cur.execute("UPDATE customers SET payment_type='Cash' WHERE payment_type IS NULL")
        cur.execute("UPDATE customers SET coverage_type='Own Damage' WHERE coverage_type IS NULL")

        cur.execute("ALTER TABLE customers DROP CONSTRAINT IF EXISTS customers_payment_type_check")
        cur.execute(
            "ALTER TABLE customers ADD CONSTRAINT customers_payment_type_check "
            "CHECK (payment_type IN ('Cash','Insurance'))"
        )
        cur.execute("ALTER TABLE customers DROP CONSTRAINT IF EXISTS customers_coverage_type_check")
        cur.execute(
            "ALTER TABLE customers ADD CONSTRAINT customers_coverage_type_check "
            "CHECK (coverage_type IN ('Own Damage','Property Damage'))"
        )

        # Parts tracking compatibility
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS service_order_parts (
                part_usage_id  SERIAL PRIMARY KEY,
                order_id       INT NOT NULL REFERENCES service_orders(order_id) ON DELETE CASCADE,
                item_id        INT NOT NULL REFERENCES inventory(item_id),
                qty_used       INT NOT NULL DEFAULT 1,
                unit_price     NUMERIC(10,2) DEFAULT 0,
                created_at     TIMESTAMP DEFAULT NOW()
            )
            """
        )

        conn.commit()
    finally:
        cur.close()
        conn.close()

