-- ============================================================
-- UnoCarshop ASMIS - Employee/payroll/inventory/billing cleanup
-- Run on existing databases after backing up data.
-- ============================================================

ALTER TABLE employees
ADD COLUMN IF NOT EXISTS classification VARCHAR(20) DEFAULT 'Regular';

ALTER TABLE employees
ADD COLUMN IF NOT EXISTS pay_schedule VARCHAR(20) DEFAULT 'Weekly';

ALTER TABLE employees
DROP CONSTRAINT IF EXISTS employees_classification_check;

UPDATE employees
SET classification = 'Regular'
WHERE classification IS NULL;

UPDATE employees
SET classification = 'Non-Regular'
WHERE classification = 'On-Call';

ALTER TABLE employees
ADD CONSTRAINT employees_classification_check
CHECK (classification IN ('Regular','Non-Regular'));

ALTER TABLE employees
DROP CONSTRAINT IF EXISTS employees_pay_schedule_check;

ALTER TABLE employees
ADD CONSTRAINT employees_pay_schedule_check
CHECK (pay_schedule IN ('Weekly','Semi-Monthly'));

UPDATE employees
SET pay_schedule = 'Weekly'
WHERE pay_schedule IS NULL;

INSERT INTO departments (dept_name)
VALUES ('Utility')
ON CONFLICT (dept_name) DO NOTHING;

UPDATE employees
SET dept_id = (SELECT dept_id FROM departments WHERE dept_name='Utility')
WHERE dept_id IN (
    SELECT dept_id
    FROM departments
    WHERE dept_name IN ('Mechanical','Electrical','Body & Paint','Parts & Inventory')
);

DELETE FROM departments
WHERE dept_name IN ('Mechanical','Electrical','Body & Paint','Parts & Inventory');

UPDATE employees
SET position_id = (SELECT position_id FROM positions WHERE position_name='Mechanic')
WHERE position_id IN (
    SELECT position_id
    FROM positions
    WHERE position_name IN ('Senior Mechanic','Parts Controller','Service Advisor')
);

UPDATE employees
SET position_id = (SELECT position_id FROM positions WHERE position_name='Cashier')
WHERE position_id IN (
    SELECT position_id
    FROM positions
    WHERE position_name IN ('General Manager','Shop Owner')
);

DELETE FROM positions
WHERE position_name IN ('General Manager','Parts Controller','Senior Mechanic','Service Advisor','Shop Owner');

DROP VIEW IF EXISTS dashboard_stats;
DROP VIEW IF EXISTS payroll_attendance_summary;

ALTER TABLE attendance
DROP COLUMN IF EXISTS remarks;

ALTER TABLE inventory
DROP COLUMN IF EXISTS reorder_lvl;

ALTER TABLE payroll
DROP COLUMN IF EXISTS net_pay;

ALTER TABLE payroll
DROP COLUMN IF EXISTS tax;

ALTER TABLE payroll
ADD COLUMN net_pay NUMERIC(10,2) GENERATED ALWAYS AS (
    basic_pay + overtime_pay + allowances
    - deductions - sss - philhealth - pagibig
) STORED;

ALTER TABLE billing
DROP COLUMN IF EXISTS discount,
DROP COLUMN IF EXISTS tax_rate,
DROP COLUMN IF EXISTS tax_amount,
DROP COLUMN IF EXISTS due_date;

ALTER TABLE billing
ADD COLUMN IF NOT EXISTS manpower NUMERIC(10,2) DEFAULT 0;

UPDATE billing
SET manpower = 0
WHERE manpower IS NULL;

CREATE TABLE IF NOT EXISTS appointments (
    appt_id      SERIAL PRIMARY KEY,
    cust_id      INT NOT NULL REFERENCES customers(cust_id) ON DELETE CASCADE,
    vehicle_id   INT REFERENCES vehicles(vehicle_id),
    svc_type_id  INT REFERENCES service_types(svc_type_id),
    assign_emp   INT REFERENCES employees(emp_id),
    appt_date    DATE NOT NULL,
    appt_time    TIME,
    status       VARCHAR(20) DEFAULT 'Scheduled'
                 CHECK (status IN ('Scheduled','Confirmed','In Progress','Completed','Cancelled','No Show')),
    notes        TEXT,
    order_id     INT REFERENCES service_orders(order_id),
    created_at   TIMESTAMP DEFAULT NOW()
);

CREATE OR REPLACE VIEW payroll_attendance_summary AS
SELECT
    e.emp_id,
    e.emp_code,
    e.full_name,
    COALESCE(e.pay_schedule,'Weekly') AS pay_schedule,
    540.00::numeric AS daily_wage,
    pp.period_id,
    pp.period_name,
    pp.start_date,
    pp.end_date,
    COUNT(a.attend_id) FILTER (WHERE a.status = 'Present')  AS days_present,
    COUNT(a.attend_id) FILTER (WHERE a.status = 'Absent')   AS days_absent,
    COUNT(a.attend_id) FILTER (WHERE a.status = 'Late')     AS days_late,
    COUNT(a.attend_id) FILTER (WHERE a.status = 'Half Day') AS days_halfday,
    COUNT(a.attend_id) FILTER (WHERE a.status = 'On Leave') AS days_onleave,
    8100.00::numeric AS computed_basic_pay
FROM employees e
CROSS JOIN payroll_periods pp
LEFT JOIN attendance a ON e.emp_id = a.emp_id
    AND a.attend_date BETWEEN pp.start_date AND pp.end_date
WHERE e.status = 'Active' AND COALESCE(e.classification,'Regular') = 'Regular'
GROUP BY e.emp_id, e.emp_code, e.full_name,
         e.pay_schedule,
         pp.period_id, pp.period_name, pp.start_date, pp.end_date;

CREATE OR REPLACE VIEW dashboard_stats AS
SELECT
    (SELECT COUNT(*) FROM customers)                                          AS total_customers,
    (SELECT COUNT(*) FROM vehicles)                                           AS total_vehicles,
    (SELECT COUNT(*) FROM employees WHERE status = 'Active')                  AS active_employees,
    (SELECT COUNT(*) FROM service_orders WHERE status IN ('Pending','In Progress')) AS active_orders,
    (SELECT COUNT(*) FROM service_orders WHERE status = 'Completed'
        AND date_out = CURRENT_DATE)                                          AS completed_today,
    (SELECT COUNT(*) FROM appointments WHERE appt_date = CURRENT_DATE
        AND status NOT IN ('Cancelled','No Show'))                            AS appointments_today,
    (SELECT COALESCE(SUM(total),0) FROM billing
        WHERE EXTRACT(MONTH FROM bill_date) = EXTRACT(MONTH FROM CURRENT_DATE)
        AND EXTRACT(YEAR FROM bill_date) = EXTRACT(YEAR FROM CURRENT_DATE)
        AND status != 'Void')                                                AS monthly_revenue,
    (SELECT COALESCE(SUM(total),0) FROM billing
        WHERE bill_date = CURRENT_DATE AND status != 'Void')                  AS daily_revenue,
    (SELECT COUNT(*) FROM inventory
        WHERE quantity <= 0 AND status = 'Active')                            AS low_stock_count,
    (SELECT COUNT(*) FROM attendance
        WHERE attend_date = CURRENT_DATE AND status = 'Present')              AS present_today,
    (SELECT COUNT(*) FROM attendance
        WHERE attend_date = CURRENT_DATE AND status = 'Absent')               AS absent_today,
    (SELECT COUNT(*) FROM billing WHERE status = 'Unpaid')                    AS unpaid_invoices,
    (SELECT COALESCE(SUM(total),0) FROM billing WHERE status != 'Void')       AS total_receivables;
