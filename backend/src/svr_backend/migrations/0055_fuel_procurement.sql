-- 0055_fuel_procurement.sql - Fuel Procurement (new module, client 2026-09-30).
--
-- One row per fuel per load - a typical delivery is two rows sharing the same
-- shift_date/vehicle_ref (client: "every load will have both MS and HS for
-- sure", ~95% of the time). Lost and Amount are computed, never stored:
--   lost   = iocl_load_litres - received_litres  (informational only)
--   amount = iocl_load_litres * rate              (IOCL debits on what they
--            say they loaded, not on what arrived)
--
-- Explicitly separate from Daily Trial Balance's own "10. Load/Unload
-- Details" - that section stays exactly as-is (client, 2026-09-30), tracking
-- the sensor/IOCL-load reconciliation that feeds Section 1's benefit/loss
-- numbers. This table is the commercial side: what was bought, what it cost,
-- and posting that cost to Monthly Expenses (the two existing "Fuel Load -
-- HS"/"Fuel Load - MS" categories from migration 0052).
CREATE TABLE fuel_load (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    shift_date         TEXT NOT NULL,
    fuel_type          TEXT NOT NULL CHECK (fuel_type IN ('HS', 'MS')),
    iocl_load_litres   REAL NOT NULL,
    received_litres    REAL NOT NULL,
    rate               REAL NOT NULL,
    vehicle_ref        TEXT,
    status             TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'posted')),
    posted_expense_id  INTEGER REFERENCES monthly_expense (id),
    created_by         TEXT NOT NULL,
    last_updated_by    TEXT,
    last_updated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX idx_fuel_load_date ON fuel_load (shift_date);
CREATE INDEX idx_fuel_load_status ON fuel_load (status);
