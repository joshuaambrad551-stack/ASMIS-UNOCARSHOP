-- ============================================================
-- Move insurance selection into customers flow
-- Safe to run on existing databases
-- ============================================================

ALTER TABLE customers
ADD COLUMN IF NOT EXISTS payment_type VARCHAR(20) DEFAULT 'Cash';

ALTER TABLE customers
ADD COLUMN IF NOT EXISTS coverage_type VARCHAR(30) DEFAULT 'Own Damage';

ALTER TABLE customers
ADD COLUMN IF NOT EXISTS insurance_provider VARCHAR(160);

ALTER TABLE customers
ADD COLUMN IF NOT EXISTS loa_amount NUMERIC(12,2) DEFAULT 0;

ALTER TABLE customers
ADD COLUMN IF NOT EXISTS assured_share NUMERIC(12,2) DEFAULT 0;

UPDATE customers
SET payment_type = 'Cash'
WHERE payment_type IS NULL;

UPDATE customers
SET coverage_type = 'Own Damage'
WHERE coverage_type IS NULL;

ALTER TABLE customers
DROP CONSTRAINT IF EXISTS customers_payment_type_check;

ALTER TABLE customers
ADD CONSTRAINT customers_payment_type_check
CHECK (payment_type IN ('Cash','Insurance'));

ALTER TABLE customers
DROP CONSTRAINT IF EXISTS customers_coverage_type_check;

ALTER TABLE customers
ADD CONSTRAINT customers_coverage_type_check
CHECK (coverage_type IN ('Own Damage','Property Damage'));
