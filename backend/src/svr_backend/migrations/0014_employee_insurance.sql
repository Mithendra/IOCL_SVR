-- 0014_employee_insurance.sql - Employee Master mockup sections 3-5:
-- Accidental Insurance (Yearly), Health Insurance (Yearly), and the Annual
-- Premium Summary (computed - Total Accidental + Total Health = Grand Total
-- Annual Insurance Cost). Manager + Owner only, same as the rest of the module.
--
-- employee_id is a soft link resolved by exact name match at save time (like
-- payroll_run_line); it goes NULL if the employee is later deleted, and
-- employee_name is kept as the readable record.

CREATE TABLE employee_insurance (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    kind           TEXT NOT NULL CHECK (kind IN ('accidental', 'health')),
    employee_id    INTEGER REFERENCES employee (id) ON DELETE SET NULL,
    employee_name  TEXT NOT NULL,
    provider       TEXT,
    policy_number  TEXT,
    yearly_premium REAL NOT NULL DEFAULT 0,
    renewal_date   TEXT,
    last_updated_by  TEXT,
    last_updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX idx_emp_insurance_kind ON employee_insurance (kind);
CREATE INDEX idx_emp_insurance_emp ON employee_insurance (employee_id);
