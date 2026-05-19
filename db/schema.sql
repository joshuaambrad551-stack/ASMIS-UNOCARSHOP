-- ============================================================
-- UnoCarshop ASMIS — PostgreSQL Schema Setup
-- Run this once to initialize the database
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- ROLES & USERS
-- ============================================================
CREATE TABLE IF NOT EXISTS roles (
    role_id     SERIAL PRIMARY KEY,
    role_name   VARCHAR(50) UNIQUE NOT NULL,
    permissions JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS users (
    user_id       SERIAL PRIMARY KEY,
    username      VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    full_name     VARCHAR(150) NOT NULL,
    role_id       INT REFERENCES roles(role_id),
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- EMPLOYEES
-- ============================================================
CREATE TABLE IF NOT EXISTS departments (
    dept_id   SERIAL PRIMARY KEY,
    dept_name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS positions (
    position_id   SERIAL PRIMARY KEY,
    position_name VARCHAR(100) UNIQUE NOT NULL,
    base_salary   NUMERIC(10,2) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS employees (
    emp_id        SERIAL PRIMARY KEY,
    emp_code      VARCHAR(20) UNIQUE NOT NULL,
    first_name    VARCHAR(80) NOT NULL,
    last_name     VARCHAR(80) NOT NULL,
    full_name     VARCHAR(160) GENERATED ALWAYS AS (first_name || ' ' || last_name) STORED,
    dept_id       INT REFERENCES departments(dept_id),
    position_id   INT REFERENCES positions(position_id),
    hire_date     DATE NOT NULL DEFAULT CURRENT_DATE,
    birth_date    DATE,
    gender        VARCHAR(10),
    phone         VARCHAR(30),
    email         VARCHAR(120),
    address       TEXT,
    classification VARCHAR(20) DEFAULT 'Regular' CHECK (classification IN ('Regular','Non-Regular')),
    pay_schedule  VARCHAR(20) DEFAULT 'Weekly' CHECK (pay_schedule IN ('Weekly','Semi-Monthly')),
    status        VARCHAR(20) DEFAULT 'Active' CHECK (status IN ('Active','On Leave','Resigned','Terminated')),
    photo_path    VARCHAR(255),
    created_at    TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- ATTENDANCE
-- ============================================================
CREATE TABLE IF NOT EXISTS attendance (
    attend_id   SERIAL PRIMARY KEY,
    emp_id      INT NOT NULL REFERENCES employees(emp_id) ON DELETE CASCADE,
    attend_date DATE NOT NULL DEFAULT CURRENT_DATE,
    time_in     TIME,
    time_out    TIME,
    status      VARCHAR(20) DEFAULT 'Present' CHECK (status IN ('Present','Absent','Late','Half Day','On Leave')),
    recorded_by INT REFERENCES users(user_id),
    created_at  TIMESTAMP DEFAULT NOW(),
    UNIQUE(emp_id, attend_date)
);

-- ============================================================
-- PAYROLL
-- ============================================================
CREATE TABLE IF NOT EXISTS payroll_periods (
    period_id    SERIAL PRIMARY KEY,
    period_name  VARCHAR(60) NOT NULL,
    start_date   DATE NOT NULL,
    end_date     DATE NOT NULL,
    status       VARCHAR(20) DEFAULT 'Open' CHECK (status IN ('Open','Closed','Paid')),
    created_at   TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS payroll (
    payroll_id      SERIAL PRIMARY KEY,
    period_id       INT REFERENCES payroll_periods(period_id),
    emp_id          INT NOT NULL REFERENCES employees(emp_id) ON DELETE CASCADE,
    basic_pay       NUMERIC(10,2) DEFAULT 0,
    overtime_pay    NUMERIC(10,2) DEFAULT 0,
    allowances      NUMERIC(10,2) DEFAULT 0,
    deductions      NUMERIC(10,2) DEFAULT 0,
    sss             NUMERIC(10,2) DEFAULT 0,
    philhealth      NUMERIC(10,2) DEFAULT 0,
    pagibig         NUMERIC(10,2) DEFAULT 0,
    net_pay         NUMERIC(10,2) GENERATED ALWAYS AS (
                        basic_pay + overtime_pay + allowances
                        - deductions - sss - philhealth - pagibig
                    ) STORED,
    status          VARCHAR(20) DEFAULT 'Draft' CHECK (status IN ('Draft','Approved','Paid')),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- INVENTORY
-- ============================================================
CREATE TABLE IF NOT EXISTS inventory_categories (
    cat_id    SERIAL PRIMARY KEY,
    cat_name  VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory (
    item_id      SERIAL PRIMARY KEY,
    item_code    VARCHAR(40) UNIQUE NOT NULL,
    item_name    VARCHAR(150) NOT NULL,
    cat_id       INT REFERENCES inventory_categories(cat_id),
    unit         VARCHAR(30) DEFAULT 'pcs',
    quantity     INT DEFAULT 0,
    unit_cost    NUMERIC(10,2) DEFAULT 0,
    unit_price   NUMERIC(10,2) DEFAULT 0,
    supplier     VARCHAR(120),
    location     VARCHAR(80),
    status       VARCHAR(20) DEFAULT 'Active',
    created_at   TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- CUSTOMERS
-- ============================================================
CREATE TABLE IF NOT EXISTS customers (
    cust_id      SERIAL PRIMARY KEY,
    cust_code    VARCHAR(20) UNIQUE NOT NULL,
    first_name   VARCHAR(80) NOT NULL,
    last_name    VARCHAR(80) NOT NULL,
    full_name    VARCHAR(160) GENERATED ALWAYS AS (first_name || ' ' || last_name) STORED,
    phone        VARCHAR(30),
    email        VARCHAR(120),
    address      TEXT,
    created_at   TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- VEHICLES
-- ============================================================
CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id   SERIAL PRIMARY KEY,
    cust_id      INT REFERENCES customers(cust_id) ON DELETE CASCADE,
    plate_no     VARCHAR(20) UNIQUE NOT NULL,
    make         VARCHAR(60),
    model        VARCHAR(60),
    year         INT,
    color        VARCHAR(40),
    vin          VARCHAR(60),
    created_at   TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- SERVICE ORDERS
-- ============================================================
CREATE TABLE IF NOT EXISTS service_types (
    svc_type_id   SERIAL PRIMARY KEY,
    type_name     VARCHAR(100) UNIQUE NOT NULL,
    base_price    NUMERIC(10,2) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS service_orders (
    order_id     SERIAL PRIMARY KEY,
    order_no     VARCHAR(30) UNIQUE NOT NULL,
    vehicle_id   INT REFERENCES vehicles(vehicle_id),
    cust_id      INT REFERENCES customers(cust_id),
    assign_emp   INT REFERENCES employees(emp_id),
    svc_type_id  INT REFERENCES service_types(svc_type_id),
    description  TEXT,
    status       VARCHAR(20) DEFAULT 'Pending' CHECK (status IN ('Pending','In Progress','Completed','Cancelled')),
    priority     VARCHAR(20) DEFAULT 'Normal' CHECK (priority IN ('Low','Normal','High','Urgent')),
    date_in      DATE DEFAULT CURRENT_DATE,
    date_out     DATE,
    remarks      TEXT,
    created_at   TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- BILLING
-- ============================================================
CREATE TABLE IF NOT EXISTS billing (
    bill_id      SERIAL PRIMARY KEY,
    bill_no      VARCHAR(30) UNIQUE NOT NULL,
    order_id     INT REFERENCES service_orders(order_id),
    cust_id      INT REFERENCES customers(cust_id),
    subtotal     NUMERIC(10,2) DEFAULT 0,
    manpower     NUMERIC(10,2) DEFAULT 0,
    total        NUMERIC(10,2) DEFAULT 0,
    amount_paid  NUMERIC(10,2) DEFAULT 0,
    balance      NUMERIC(10,2) GENERATED ALWAYS AS (total - amount_paid) STORED,
    status       VARCHAR(20) DEFAULT 'Unpaid' CHECK (status IN ('Unpaid','Partial','Paid','Void')),
    payment_method VARCHAR(40),
    bill_date    DATE DEFAULT CURRENT_DATE,
    created_at   TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- INSURANCE
-- ============================================================
CREATE TABLE IF NOT EXISTS insurance (
    ins_id       SERIAL PRIMARY KEY,
    vehicle_id   INT REFERENCES vehicles(vehicle_id),
    cust_id      INT REFERENCES customers(cust_id),
    provider     VARCHAR(120),
    policy_no    VARCHAR(60) UNIQUE NOT NULL,
    coverage     TEXT,
    start_date   DATE,
    end_date     DATE,
    premium      NUMERIC(10,2) DEFAULT 0,
    status       VARCHAR(20) DEFAULT 'Active' CHECK (status IN ('Active','Expired','Cancelled')),
    created_at   TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- DAILY SNAPSHOTS
-- ============================================================
CREATE TABLE IF NOT EXISTS daily_snapshots (
    snapshot_id   SERIAL PRIMARY KEY,
    snapshot_date DATE UNIQUE NOT NULL,
    summary       JSONB NOT NULL DEFAULT '{}'::jsonb,
    details       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by    INT REFERENCES users(user_id),
    generated_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================
-- SEED DATA
-- ============================================================

-- Roles
INSERT INTO roles (role_name, permissions) VALUES
('owner',     '{"all": true}'),
('manager',   '{"employees":true,"payroll":true,"inventory":true,"customers":true,"orders":true,"billing":true}'),
('mechanic',  '{"orders":true,"inventory":true}'),
('cashier',   '{"billing":true,"customers":true}'),
('hr',        '{"employees":true,"payroll":true,"attendance":true}')
ON CONFLICT (role_name) DO NOTHING;

-- Default admin user (password: admin123)
INSERT INTO users (username, password_hash, full_name, role_id) VALUES
('admin', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', 'Administrator', 1)
ON CONFLICT (username) DO NOTHING;

-- Departments
INSERT INTO departments (dept_name) VALUES
('Management'),('Utility'),('Front Desk')
ON CONFLICT (dept_name) DO NOTHING;

-- Positions
INSERT INTO positions (position_name, base_salary) VALUES
('Mechanic',22000),('Electrician',24000),('Painter',22000),('Cashier',18000)
ON CONFLICT (position_name) DO NOTHING;

-- Inventory Categories
INSERT INTO inventory_categories (cat_name) VALUES
('Engine Parts'),('Electrical'),('Body Parts'),('Fluids & Lubricants'),
('Tires & Wheels'),('Brake System'),('Suspension'),('Consumables')
ON CONFLICT (cat_name) DO NOTHING;

-- Service Types
INSERT INTO service_types (type_name, base_price) VALUES
('Oil Change',450),('Tune-Up',1500),('Brake Service',2500),
('Electrical Repair',1200),('Body Repair',5000),('Paint Job',8000),
('Aircon Service',1800),('Transmission Service',3500),('Full Inspection',800)
ON CONFLICT (type_name) DO NOTHING;

-- Sample Employees
INSERT INTO employees (emp_code, first_name, last_name, dept_id, position_id, hire_date, gender, phone, email, classification, pay_schedule, status)
VALUES
('EMP-001','Juan','Dela Cruz',
 (SELECT dept_id FROM departments WHERE dept_name='Management'),
 (SELECT position_id FROM positions WHERE position_name='Cashier'),
 '2020-01-15','Male','09171234567','juan.dc@unocarshop.ph','Regular','Weekly','Active'),
('EMP-002','Maria','Santos',
 (SELECT dept_id FROM departments WHERE dept_name='Utility'),
 (SELECT position_id FROM positions WHERE position_name='Mechanic'),
 '2021-03-01','Female','09181234567','maria.s@unocarshop.ph','Regular','Semi-Monthly','Active'),
('EMP-003','Pedro','Reyes',
 (SELECT dept_id FROM departments WHERE dept_name='Utility'),
 (SELECT position_id FROM positions WHERE position_name='Electrician'),
 '2022-06-10','Male','09191234567','pedro.r@unocarshop.ph','Non-Regular','Weekly','Active'),
('EMP-004','Ana','Gomez',
 (SELECT dept_id FROM departments WHERE dept_name='Front Desk'),
 (SELECT position_id FROM positions WHERE position_name='Cashier'),
 '2021-09-20','Female','09201234567','ana.g@unocarshop.ph','Regular','Weekly','Active'),
('EMP-005','Rizal','Bautista',
 (SELECT dept_id FROM departments WHERE dept_name='Utility'),
 (SELECT position_id FROM positions WHERE position_name='Painter'),
 '2020-11-05','Male','09211234567','rizal.b@unocarshop.ph','Non-Regular','Weekly','Active')
ON CONFLICT (emp_code) DO NOTHING;

-- Sample Customers
INSERT INTO customers (cust_code, first_name, last_name, phone, email, address)
VALUES
('CUST-001','Roberto','Fernandez','09221234567','roberto.f@email.com','123 Mabini St, Manila'),
('CUST-002','Liza','Pascual','09231234567','liza.p@email.com','456 Rizal Ave, Quezon City'),
('CUST-003','Dennis','Villanueva','09241234567','dennis.v@email.com','789 EDSA, Makati')
ON CONFLICT (cust_code) DO NOTHING;

-- Sample Vehicles
INSERT INTO vehicles (cust_id, plate_no, make, model, year, color)
VALUES
(1,'ABC-1234','Toyota','Fortuner',2020,'White'),
(2,'XYZ-5678','Honda','Civic',2019,'Black'),
(3,'DEF-9012','Ford','Ranger',2021,'Silver')
ON CONFLICT (plate_no) DO NOTHING;
