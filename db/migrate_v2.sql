-- ============================================================
-- UnoCarshop ASMIS — Schema Migration v2
-- Run this AFTER schema.sql to add integration tables
-- and apply all required adjustments
-- ============================================================

-- ── 1. Remove unwanted inventory categories ────────────────
DELETE FROM inventory_categories WHERE cat_name IN ('Consumables', 'Suspension');

-- ── 2. Service order parts usage (links inventory to repairs)
CREATE TABLE IF NOT EXISTS service_order_parts (
    part_usage_id  SERIAL PRIMARY KEY,
    order_id       INT NOT NULL REFERENCES service_orders(order_id) ON DELETE CASCADE,
    item_id        INT NOT NULL REFERENCES inventory(item_id),
    qty_used       INT NOT NULL DEFAULT 1,
    unit_price     NUMERIC(10,2) DEFAULT 0,
    created_at     TIMESTAMP DEFAULT NOW()
);

-- Keep part usage pricing derived from the inventory item price.
CREATE OR REPLACE FUNCTION fn_set_part_price_from_inventory()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        SELECT COALESCE(unit_price, 0)
        INTO NEW.unit_price
        FROM inventory
        WHERE item_id = NEW.item_id;
    ELSIF NEW.item_id IS DISTINCT FROM OLD.item_id THEN
        SELECT COALESCE(unit_price, 0)
        INTO NEW.unit_price
        FROM inventory
        WHERE item_id = NEW.item_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_set_part_price ON service_order_parts;
CREATE TRIGGER trg_set_part_price
BEFORE INSERT OR UPDATE OF item_id ON service_order_parts
FOR EACH ROW EXECUTE FUNCTION fn_set_part_price_from_inventory();

UPDATE service_order_parts sop
SET unit_price = COALESCE(i.unit_price, 0)
FROM inventory i
WHERE sop.item_id = i.item_id;

-- ── 3. Appointments table ──────────────────────────────────
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
    order_id     INT REFERENCES service_orders(order_id),  -- linked once converted
    created_at   TIMESTAMP DEFAULT NOW()
);

-- ── 4. Mechanic performance view ───────────────────────────
CREATE OR REPLACE VIEW mechanic_performance AS
SELECT
    e.emp_id,
    e.emp_code,
    e.full_name,
    d.dept_name,
    COUNT(so.order_id)                                          AS total_jobs,
    COUNT(so.order_id) FILTER (WHERE so.status = 'Completed')  AS completed_jobs,
    COUNT(so.order_id) FILTER (WHERE so.status = 'In Progress') AS ongoing_jobs,
    COALESCE(SUM(b.total) FILTER (WHERE so.status = 'Completed'), 0) AS total_revenue_generated
FROM employees e
LEFT JOIN departments d ON e.dept_id = d.dept_id
LEFT JOIN service_orders so ON e.emp_id = so.assign_emp
LEFT JOIN billing b ON so.order_id = b.order_id
WHERE e.status = 'Active'
GROUP BY e.emp_id, e.emp_code, e.full_name, d.dept_name;

-- ── 5. Attendance-payroll summary view ─────────────────────
CREATE OR REPLACE VIEW payroll_attendance_summary AS
SELECT
    e.emp_id,
    e.emp_code,
    e.full_name,
    p.position_name,
    p.base_salary,
    pp.period_id,
    pp.period_name,
    pp.start_date,
    pp.end_date,
    COUNT(a.attend_id) FILTER (WHERE a.status = 'Present')  AS days_present,
    COUNT(a.attend_id) FILTER (WHERE a.status = 'Absent')   AS days_absent,
    COUNT(a.attend_id) FILTER (WHERE a.status = 'Late')     AS days_late,
    COUNT(a.attend_id) FILTER (WHERE a.status = 'Half Day') AS days_halfday,
    COUNT(a.attend_id) FILTER (WHERE a.status = 'On Leave') AS days_onleave,
    -- Computed basic pay based on attendance
    ROUND(
        p.base_salary / 22.0 *
        (COUNT(a.attend_id) FILTER (WHERE a.status IN ('Present','Late'))
         + COUNT(a.attend_id) FILTER (WHERE a.status = 'Half Day') * 0.5),
    2) AS computed_basic_pay
FROM employees e
LEFT JOIN positions p ON e.position_id = p.position_id
CROSS JOIN payroll_periods pp
LEFT JOIN attendance a ON e.emp_id = a.emp_id
    AND a.attend_date BETWEEN pp.start_date AND pp.end_date
WHERE e.status = 'Active'
GROUP BY e.emp_id, e.emp_code, e.full_name,
         p.position_name, p.base_salary,
         pp.period_id, pp.period_name, pp.start_date, pp.end_date;

-- ── 6. Dashboard live stats view ──────────────────────────
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
    (SELECT COALESCE(SUM(amount_paid),0) FROM billing
        WHERE EXTRACT(MONTH FROM bill_date) = EXTRACT(MONTH FROM CURRENT_DATE)
        AND EXTRACT(YEAR FROM bill_date) = EXTRACT(YEAR FROM CURRENT_DATE))   AS monthly_revenue,
    (SELECT COALESCE(SUM(amount_paid),0) FROM billing
        WHERE bill_date = CURRENT_DATE)                                       AS daily_revenue,
    (SELECT COUNT(*) FROM inventory
        WHERE quantity <= reorder_lvl AND status = 'Active')                  AS low_stock_count,
    (SELECT COUNT(*) FROM attendance
        WHERE attend_date = CURRENT_DATE AND status = 'Present')              AS present_today,
    (SELECT COUNT(*) FROM attendance
        WHERE attend_date = CURRENT_DATE AND status = 'Absent')               AS absent_today,
    (SELECT COUNT(*) FROM billing WHERE status = 'Unpaid')                    AS unpaid_invoices,
    (SELECT COALESCE(SUM(balance),0) FROM billing WHERE status != 'Void')     AS total_receivables;

-- ── 7. Trigger: auto-decrease inventory when part used ─────
CREATE OR REPLACE FUNCTION fn_deduct_inventory()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE inventory
    SET quantity = quantity - NEW.qty_used
    WHERE item_id = NEW.item_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_deduct_inventory ON service_order_parts;
CREATE TRIGGER trg_deduct_inventory
AFTER INSERT ON service_order_parts
FOR EACH ROW EXECUTE FUNCTION fn_deduct_inventory();

-- Trigger: restore inventory when part usage deleted
CREATE OR REPLACE FUNCTION fn_restore_inventory()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE inventory
    SET quantity = quantity + OLD.qty_used
    WHERE item_id = OLD.item_id;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_restore_inventory ON service_order_parts;
CREATE TRIGGER trg_restore_inventory
AFTER DELETE ON service_order_parts
FOR EACH ROW EXECUTE FUNCTION fn_restore_inventory();

-- Recalculate invoice totals from service base price, parts, discount, and tax rate.
CREATE OR REPLACE FUNCTION fn_recalculate_order_billing(p_order_id INT)
RETURNS VOID AS $$
DECLARE
    v_subtotal NUMERIC(10,2);
    v_discount NUMERIC(10,2);
    v_tax_rate NUMERIC(5,2);
    v_tax NUMERIC(10,2);
    v_total NUMERIC(10,2);
BEGIN
    SELECT COALESCE(st.base_price, 0) + COALESCE(parts.parts_total, 0)
    INTO v_subtotal
    FROM service_orders so
    LEFT JOIN service_types st ON so.svc_type_id = st.svc_type_id
    LEFT JOIN (
        SELECT order_id, SUM(qty_used * unit_price) AS parts_total
        FROM service_order_parts
        WHERE order_id = p_order_id
        GROUP BY order_id
    ) parts ON parts.order_id = so.order_id
    WHERE so.order_id = p_order_id;

    IF v_subtotal IS NULL THEN
        RETURN;
    END IF;

    SELECT LEAST(COALESCE(discount, 0), v_subtotal), COALESCE(tax_rate, 12)
    INTO v_discount, v_tax_rate
    FROM billing
    WHERE order_id = p_order_id AND status != 'Void'
    LIMIT 1;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    v_tax := ROUND(GREATEST(v_subtotal - v_discount, 0) * (v_tax_rate / 100), 2);
    v_total := GREATEST(v_subtotal - v_discount, 0) + v_tax;

    UPDATE billing
    SET subtotal = v_subtotal,
        discount = v_discount,
        tax_amount = v_tax,
        total = v_total,
        status = CASE
            WHEN amount_paid >= v_total AND v_total > 0 THEN 'Paid'
            WHEN amount_paid > 0 THEN 'Partial'
            ELSE 'Unpaid'
        END
    WHERE order_id = p_order_id AND status != 'Void';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_recalculate_billing_after_part_change()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        PERFORM fn_recalculate_order_billing(OLD.order_id);
        RETURN OLD;
    END IF;
    PERFORM fn_recalculate_order_billing(NEW.order_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_recalculate_billing_parts ON service_order_parts;
CREATE TRIGGER trg_recalculate_billing_parts
AFTER INSERT OR UPDATE OR DELETE ON service_order_parts
FOR EACH ROW EXECUTE FUNCTION fn_recalculate_billing_after_part_change();

CREATE OR REPLACE FUNCTION fn_recalculate_billing_after_service_change()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM fn_recalculate_order_billing(NEW.order_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_recalculate_billing_service ON service_orders;
CREATE TRIGGER trg_recalculate_billing_service
AFTER UPDATE OF svc_type_id ON service_orders
FOR EACH ROW EXECUTE FUNCTION fn_recalculate_billing_after_service_change();

SELECT fn_recalculate_order_billing(order_id)
FROM billing
WHERE order_id IS NOT NULL AND status != 'Void';

-- ── 8. Trigger: auto-create billing when order completes ───
CREATE OR REPLACE FUNCTION fn_auto_create_billing()
RETURNS TRIGGER AS $$
DECLARE
    v_subtotal   NUMERIC(10,2);
    v_tax        NUMERIC(10,2);
    v_total      NUMERIC(10,2);
    v_bill_no    VARCHAR(30);
    v_base_price NUMERIC(10,2);
BEGIN
    -- Only fire when status changes TO 'Completed'
    IF NEW.status = 'Completed' AND OLD.status != 'Completed' THEN
        -- Check if billing already exists for this order
        IF NOT EXISTS (SELECT 1 FROM billing WHERE order_id = NEW.order_id) THEN
            -- Get base price from service type
            SELECT COALESCE(base_price, 0) INTO v_base_price
            FROM service_types WHERE svc_type_id = NEW.svc_type_id;
            -- Add parts cost
            SELECT COALESCE(SUM(qty_used * unit_price), 0) INTO v_subtotal
            FROM service_order_parts WHERE order_id = NEW.order_id;
            v_subtotal := v_subtotal + v_base_price;
            v_tax      := ROUND(v_subtotal * 0.12, 2);
            v_total    := v_subtotal + v_tax;
            -- Generate bill number
            SELECT 'INV' || LPAD(CAST(COALESCE(MAX(CAST(SUBSTRING(bill_no FROM 4) AS INT)),0)+1 AS TEXT), 5, '0')
            INTO v_bill_no FROM billing;
            -- Insert billing record
            INSERT INTO billing
                (bill_no, order_id, cust_id, subtotal, tax_rate, tax_amount, total, status, bill_date, due_date)
            VALUES
                (v_bill_no, NEW.order_id, NEW.cust_id, v_subtotal, 12, v_tax, v_total,
                 'Unpaid', CURRENT_DATE, CURRENT_DATE + INTERVAL '7 days');
            -- Set date_out on order
            UPDATE service_orders SET date_out = CURRENT_DATE WHERE order_id = NEW.order_id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_auto_billing ON service_orders;
CREATE TRIGGER trg_auto_billing
AFTER UPDATE ON service_orders
FOR EACH ROW EXECUTE FUNCTION fn_auto_create_billing();

-- ── 9. Trigger: auto-convert appointment to service order ──
CREATE OR REPLACE FUNCTION fn_appt_to_order()
RETURNS TRIGGER AS $$
DECLARE
    v_order_no VARCHAR(30);
BEGIN
    IF NEW.status = 'In Progress' AND OLD.status != 'In Progress' AND NEW.order_id IS NULL THEN
        SELECT 'ORD' || LPAD(CAST(COALESCE(MAX(CAST(SUBSTRING(order_no FROM 4) AS INT)),0)+1 AS TEXT),5,'0')
        INTO v_order_no FROM service_orders;

        INSERT INTO service_orders
            (order_no, vehicle_id, cust_id, assign_emp, svc_type_id, status, priority, date_in)
        VALUES
            (v_order_no, NEW.vehicle_id, NEW.cust_id, NEW.assign_emp,
             NEW.svc_type_id, 'In Progress', 'Normal', CURRENT_DATE)
        RETURNING order_id INTO NEW.order_id;

        UPDATE appointments SET order_id = NEW.order_id WHERE appt_id = NEW.appt_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_appt_to_order ON appointments;
CREATE TRIGGER trg_appt_to_order
AFTER UPDATE ON appointments
FOR EACH ROW EXECUTE FUNCTION fn_appt_to_order();

-- ── 10. Sample appointments ────────────────────────────────
INSERT INTO appointments (cust_id, vehicle_id, svc_type_id, appt_date, appt_time, status, notes)
SELECT
    c.cust_id,
    v.vehicle_id,
    1,
    CURRENT_DATE,
    '09:00',
    'Scheduled',
    'Regular oil change'
FROM customers c
JOIN vehicles v ON v.cust_id = c.cust_id
LIMIT 2
ON CONFLICT DO NOTHING;

-- 11. Daily snapshots for end-of-day data history
CREATE TABLE IF NOT EXISTS daily_snapshots (
    snapshot_id   SERIAL PRIMARY KEY,
    snapshot_date DATE UNIQUE NOT NULL,
    summary       JSONB NOT NULL DEFAULT '{}'::jsonb,
    details       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by    INT REFERENCES users(user_id),
    generated_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP NOT NULL DEFAULT NOW()
);
