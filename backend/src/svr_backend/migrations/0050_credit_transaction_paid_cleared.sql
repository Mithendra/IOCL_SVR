-- Credit/Remittance Master: a credit needs a real Paid/Cleared lifecycle,
-- visible on THIS screen - not just inferred from Section 3's outstanding
-- total dropping (client, 2026-09-27):
--
--   "Once the Payment is entered in Remittance it should show Posted as
--    Paid and then should be able to clear."
--
-- Settlement has to work the same way regardless of which screen collects
-- the payment - Daily Sales Entry Section 6 -> Trial Balance -> Post, OR a
-- remittance typed straight onto this screen's own Section 2 (client:
-- "Either Daily Sales man has to do it or Daily Mgr has to do it"). Today
-- Trial Balance's own settlement (posting._settle_remittances) only ever
-- flips its OWN internal trial_balance_posting row to 'paid' - it never
-- touches credit_transaction at all, which is why this table's own status
-- has stayed stuck at 'posted_dt' forever even after a credit is fully
-- repaid. posting.settle_credit_transactions() (added alongside this
-- migration) is the shared engine both paths now call.
--
-- SQLite can't ALTER a CHECK constraint in place, so the table is rebuilt -
-- first table-rebuild migration in this repo; every column, both indexes,
-- and every existing row are carried over unchanged.

CREATE TABLE credit_transaction_new (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    kind               TEXT NOT NULL CHECK (kind IN ('credit', 'remittance')),
    creditor_name      TEXT NOT NULL,
    phone              TEXT,
    fuel_type          TEXT,
    ltrs               REAL,
    rate               REAL,
    amount             REAL NOT NULL,
    txn_date           TEXT NOT NULL,
    source             TEXT,
    pump_sales_man     TEXT,
    note               TEXT,
    payment_mode       TEXT,
    payment            TEXT,
    remittance_entered TEXT,
    collected_by       TEXT,
    given_on_date      TEXT,
    -- 'paid'/'cleared' only ever apply to a kind='credit' row - a remittance
    -- IS the payment; it is never itself paid or cleared.
    status TEXT NOT NULL DEFAULT 'manual'
        CHECK (status IN ('manual', 'posted_dt', 'paid', 'cleared')),
    paid_at            TEXT,
    paid_by            TEXT,
    cleared_at         TEXT,
    cleared_by         TEXT,
    created_by         TEXT NOT NULL,
    last_updated_by    TEXT,
    last_updated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

INSERT INTO credit_transaction_new (
    id, kind, creditor_name, phone, fuel_type, ltrs, rate, amount, txn_date,
    source, pump_sales_man, note, payment_mode, payment, remittance_entered,
    collected_by, given_on_date, status, created_by, last_updated_by,
    last_updated_at, created_at
)
SELECT
    id, kind, creditor_name, phone, fuel_type, ltrs, rate, amount, txn_date,
    source, pump_sales_man, note, payment_mode, payment, remittance_entered,
    collected_by, given_on_date, status, created_by, last_updated_by,
    last_updated_at, created_at
FROM credit_transaction;

DROP TABLE credit_transaction;
ALTER TABLE credit_transaction_new RENAME TO credit_transaction;

CREATE INDEX idx_credit_txn_name ON credit_transaction (creditor_name);
CREATE INDEX idx_credit_txn_kind_date ON credit_transaction (kind, txn_date);
