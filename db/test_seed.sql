-- ============================================================
-- UnoCarshop ASMIS test data
-- Safe to rerun: unique records use ON CONFLICT, and dependent
-- records are checked before insert where no natural unique key exists.
-- ============================================================

-- Employees
INSERT INTO employees
    (emp_code, first_name, last_name, dept_id, position_id, hire_date, birth_date, gender, phone, email, address, status)
VALUES
    ('EMP-006', 'Carlo', 'Mendoza',
        (SELECT dept_id FROM departments WHERE dept_name = 'Mechanical'),
        (SELECT position_id FROM positions WHERE position_name = 'Mechanic'),
        '2023-02-13', '1996-05-18', 'Male', '09301234567', 'carlo.m@unocarshop.ph', 'Pasig City', 'Active'),
    ('EMP-007', 'Jessa', 'Lim',
        (SELECT dept_id FROM departments WHERE dept_name = 'Electrical'),
        (SELECT position_id FROM positions WHERE position_name = 'Electrician'),
        '2022-10-03', '1994-11-09', 'Female', '09311234567', 'jessa.l@unocarshop.ph', 'Mandaluyong City', 'Active'),
    ('EMP-008', 'Mark', 'Flores',
        (SELECT dept_id FROM departments WHERE dept_name = 'Body & Paint'),
        (SELECT position_id FROM positions WHERE position_name = 'Painter'),
        '2024-01-22', '1998-02-26', 'Male', '09321234567', 'mark.f@unocarshop.ph', 'Taguig City', 'On Leave')
ON CONFLICT (emp_code) DO NOTHING;

-- Inventory items
INSERT INTO inventory
    (item_code, item_name, cat_id, unit, quantity, reorder_lvl, unit_cost, unit_price, supplier, location, status)
VALUES
    ('OIL-5W30-001', '5W-30 Fully Synthetic Engine Oil',
        (SELECT cat_id FROM inventory_categories WHERE cat_name = 'Fluids & Lubricants'),
        'liter', 28, 8, 380.00, 520.00, 'Metro Auto Supply', 'Rack A1', 'Active'),
    ('FIL-OIL-001', 'Oil Filter - Toyota/Honda',
        (SELECT cat_id FROM inventory_categories WHERE cat_name = 'Engine Parts'),
        'pcs', 18, 5, 180.00, 320.00, 'Metro Auto Supply', 'Rack A2', 'Active'),
    ('BRK-PAD-001', 'Front Brake Pad Set',
        (SELECT cat_id FROM inventory_categories WHERE cat_name = 'Brake System'),
        'set', 4, 5, 950.00, 1450.00, 'Prime Parts PH', 'Rack B1', 'Active'),
    ('BAT-12V-001', '12V Maintenance-Free Battery',
        (SELECT cat_id FROM inventory_categories WHERE cat_name = 'Electrical'),
        'pcs', 6, 3, 3900.00, 5200.00, 'PowerCell Trading', 'Rack C1', 'Active'),
    ('TIRE-16-001', 'All-Season Tire 265/70R16',
        (SELECT cat_id FROM inventory_categories WHERE cat_name = 'Tires & Wheels'),
        'pcs', 10, 4, 4300.00, 5900.00, 'RoadGrip Supply', 'Tire Bay', 'Active')
ON CONFLICT (item_code) DO NOTHING;

-- More customers
INSERT INTO customers
    (cust_code, first_name, last_name, phone, email, address)
VALUES
    ('CUST-004', 'Angela', 'Cruz', '09401234567', 'angela.cruz@email.com', 'Greenhills, San Juan'),
    ('CUST-005', 'Miguel', 'Torres', '09411234567', 'miguel.torres@email.com', 'BF Homes, Paranaque'),
    ('CUST-006', 'Patricia', 'Navarro', '09421234567', 'patricia.navarro@email.com', 'Lahug, Cebu City')
ON CONFLICT (cust_code) DO NOTHING;

-- Vehicles for the new customers
INSERT INTO vehicles
    (cust_id, plate_no, make, model, year, color, vin)
VALUES
    ((SELECT cust_id FROM customers WHERE cust_code = 'CUST-004'), 'NCR-4821', 'Mitsubishi', 'Montero Sport', 2022, 'Gray', 'VINTEST000004821'),
    ((SELECT cust_id FROM customers WHERE cust_code = 'CUST-005'), 'NBL-7742', 'Nissan', 'Navara', 2021, 'Blue', 'VINTEST000007742'),
    ((SELECT cust_id FROM customers WHERE cust_code = 'CUST-006'), 'CEB-1908', 'Hyundai', 'Accent', 2018, 'Red', 'VINTEST000001908')
ON CONFLICT (plate_no) DO NOTHING;

-- Service orders in varied states
INSERT INTO service_orders
    (order_no, vehicle_id, cust_id, assign_emp, svc_type_id, description, status, priority, date_in, date_out, remarks)
VALUES
    ('ORD00010',
        (SELECT vehicle_id FROM vehicles WHERE plate_no = 'NCR-4821'),
        (SELECT cust_id FROM customers WHERE cust_code = 'CUST-004'),
        (SELECT emp_id FROM employees WHERE emp_code = 'EMP-006'),
        (SELECT svc_type_id FROM service_types WHERE type_name = 'Oil Change'),
        'Oil change with oil filter replacement.', 'Pending', 'Normal', CURRENT_DATE, NULL, 'Customer waiting for confirmation.'),
    ('ORD00011',
        (SELECT vehicle_id FROM vehicles WHERE plate_no = 'NBL-7742'),
        (SELECT cust_id FROM customers WHERE cust_code = 'CUST-005'),
        (SELECT emp_id FROM employees WHERE emp_code = 'EMP-007'),
        (SELECT svc_type_id FROM service_types WHERE type_name = 'Electrical Repair'),
        'Intermittent starting issue and battery inspection.', 'In Progress', 'High', CURRENT_DATE - INTERVAL '1 day', NULL, 'Diagnostics ongoing.'),
    ('ORD00012',
        (SELECT vehicle_id FROM vehicles WHERE plate_no = 'CEB-1908'),
        (SELECT cust_id FROM customers WHERE cust_code = 'CUST-006'),
        (SELECT emp_id FROM employees WHERE emp_code = 'EMP-002'),
        (SELECT svc_type_id FROM service_types WHERE type_name = 'Brake Service'),
        'Front brake pad replacement and road test.', 'Completed', 'Normal', CURRENT_DATE - INTERVAL '3 days', CURRENT_DATE - INTERVAL '2 days', 'Released to customer.')
ON CONFLICT (order_no) DO NOTHING;

-- Billing samples
INSERT INTO billing
    (bill_no, order_id, cust_id, subtotal, discount, tax_rate, tax_amount, total, amount_paid, status, payment_method, bill_date, due_date)
VALUES
    ('INV00010',
        (SELECT order_id FROM service_orders WHERE order_no = 'ORD00010'),
        (SELECT cust_id FROM customers WHERE cust_code = 'CUST-004'),
        970.00, 0.00, 12.00, 116.40, 1086.40, 0.00, 'Unpaid', NULL, CURRENT_DATE, CURRENT_DATE + INTERVAL '7 days'),
    ('INV00011',
        (SELECT order_id FROM service_orders WHERE order_no = 'ORD00011'),
        (SELECT cust_id FROM customers WHERE cust_code = 'CUST-005'),
        6400.00, 500.00, 12.00, 708.00, 6608.00, 3000.00, 'Partial', 'Cash', CURRENT_DATE - INTERVAL '1 day', CURRENT_DATE + INTERVAL '6 days'),
    ('INV00012',
        (SELECT order_id FROM service_orders WHERE order_no = 'ORD00012'),
        (SELECT cust_id FROM customers WHERE cust_code = 'CUST-006'),
        3950.00, 0.00, 12.00, 474.00, 4424.00, 4424.00, 'Paid', 'GCash', CURRENT_DATE - INTERVAL '2 days', CURRENT_DATE + INTERVAL '5 days')
ON CONFLICT (bill_no) DO NOTHING;

-- Insurance policies
INSERT INTO insurance
    (vehicle_id, cust_id, provider, policy_no, coverage, start_date, end_date, premium, status)
VALUES
    ((SELECT vehicle_id FROM vehicles WHERE plate_no = 'NCR-4821'),
        (SELECT cust_id FROM customers WHERE cust_code = 'CUST-004'),
        'Pioneer Insurance', 'POL-TEST-004', 'Comprehensive with acts of nature', CURRENT_DATE - INTERVAL '60 days', CURRENT_DATE + INTERVAL '305 days', 18500.00, 'Active'),
    ((SELECT vehicle_id FROM vehicles WHERE plate_no = 'NBL-7742'),
        (SELECT cust_id FROM customers WHERE cust_code = 'CUST-005'),
        'Malayan Insurance', 'POL-TEST-005', 'Comprehensive commercial vehicle coverage', CURRENT_DATE - INTERVAL '20 days', CURRENT_DATE + INTERVAL '345 days', 22400.00, 'Active'),
    ((SELECT vehicle_id FROM vehicles WHERE plate_no = 'CEB-1908'),
        (SELECT cust_id FROM customers WHERE cust_code = 'CUST-006'),
        'Standard Insurance', 'POL-TEST-006', 'TPL renewal test case', CURRENT_DATE - INTERVAL '400 days', CURRENT_DATE - INTERVAL '35 days', 1800.00, 'Expired')
ON CONFLICT (policy_no) DO NOTHING;

-- Payroll period and payroll rows
INSERT INTO payroll_periods
    (period_name, start_date, end_date, status)
SELECT
    'May 2026 - First Half', DATE '2026-05-01', DATE '2026-05-15', 'Closed'
WHERE NOT EXISTS (
    SELECT 1 FROM payroll_periods WHERE period_name = 'May 2026 - First Half'
);

INSERT INTO payroll
    (period_id, emp_id, basic_pay, overtime_pay, allowances, deductions, sss, philhealth, pagibig, tax, status)
SELECT
    (SELECT period_id FROM payroll_periods WHERE period_name = 'May 2026 - First Half'),
    e.emp_id,
    CASE e.emp_code
        WHEN 'EMP-006' THEN 11000.00
        WHEN 'EMP-007' THEN 12000.00
        WHEN 'EMP-008' THEN 8800.00
    END,
    CASE e.emp_code
        WHEN 'EMP-006' THEN 750.00
        WHEN 'EMP-007' THEN 1200.00
        WHEN 'EMP-008' THEN 0.00
    END,
    1000.00, 0.00, 500.00, 300.00, 100.00, 450.00, 'Approved'
FROM employees e
WHERE e.emp_code IN ('EMP-006', 'EMP-007', 'EMP-008')
  AND NOT EXISTS (
      SELECT 1
      FROM payroll p
      WHERE p.period_id = (SELECT period_id FROM payroll_periods WHERE period_name = 'May 2026 - First Half')
        AND p.emp_id = e.emp_id
  );

-- Recent attendance
INSERT INTO attendance
    (emp_id, attend_date, time_in, time_out, status, remarks, recorded_by)
SELECT emp_id, CURRENT_DATE, '08:02', '17:05', 'Present', 'Seed attendance', (SELECT user_id FROM users WHERE username = 'admin')
FROM employees
WHERE emp_code IN ('EMP-001', 'EMP-002', 'EMP-006')
ON CONFLICT (emp_id, attend_date) DO NOTHING;

INSERT INTO attendance
    (emp_id, attend_date, time_in, time_out, status, remarks, recorded_by)
SELECT emp_id, CURRENT_DATE, '08:45', '17:20', 'Late', 'Traffic delay', (SELECT user_id FROM users WHERE username = 'admin')
FROM employees
WHERE emp_code = 'EMP-007'
ON CONFLICT (emp_id, attend_date) DO NOTHING;

INSERT INTO attendance
    (emp_id, attend_date, time_in, time_out, status, remarks, recorded_by)
SELECT emp_id, CURRENT_DATE, NULL, NULL, 'On Leave', 'Approved leave', (SELECT user_id FROM users WHERE username = 'admin')
FROM employees
WHERE emp_code = 'EMP-008'
ON CONFLICT (emp_id, attend_date) DO NOTHING;
