-- Section 3 (Creditor Balance Summary) needs fields that don't belong on a
-- transaction row - a phone number, whether this is a long-standing pre-app
-- balance or one accrued since go-live, a running note, and documents. Today
-- Section 3 is only a GROUP BY over credit_transaction, so a creditor with no
-- transactions yet cannot exist at all - "+ Add" (client, 2026-09-27) needs
-- somewhere to write to.
--
-- Kept separate from trial_balance_option's 'customers'/'creditors' lists,
-- which stay the single source of truth for WHICH names are selectable on
-- Daily Sales Entry and here - this table adds detail about a name already on
-- that list (credit_type, note, documents), it doesn't replace the list.
-- Credit Master's own "+ Add Creditor" writes to both, so a name typed either
-- place works in both (client: "should have +Add to add new creditor Name
-- same as above").
CREATE TABLE creditor (
    name            TEXT PRIMARY KEY,
    phone           TEXT,
    -- 'old': existed before the app went live, tracked here for the record
    -- only. 'new': accrued through daily operations, the normal case.
    credit_type     TEXT NOT NULL DEFAULT 'new' CHECK (credit_type IN ('old', 'new')),
    note            TEXT,
    created_by      TEXT NOT NULL,
    last_updated_by TEXT,
    last_updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- "This section is to keep track [of] very long and old credits" - a scanned
-- agreement, a handwritten ledger page, anything that predates the app.
-- Same shape as stock_purchase_document (migration 0039): the file lives on
-- disk, never in the database, and is never deleted - `stored_name` is
-- generated so an uploaded filename can never choose where it's written.
CREATE TABLE creditor_document (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    creditor_name   TEXT NOT NULL REFERENCES creditor (name),
    note            TEXT,
    original_name   TEXT NOT NULL,
    stored_name     TEXT NOT NULL UNIQUE,
    content_type    TEXT NOT NULL,
    size_bytes      INTEGER NOT NULL,
    uploaded_by     TEXT NOT NULL,
    uploaded_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    last_updated_by TEXT,
    last_updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX idx_creditor_document_name ON creditor_document (creditor_name);

-- Backfill: every name that already has a credit_transaction row gets a
-- creditor row too, so existing balances show up in Section 3 immediately
-- rather than only appearing once someone happens to click "+ Add" for them.
INSERT INTO creditor (name, credit_type, created_by)
SELECT DISTINCT creditor_name, 'new', 'migration-0046'
FROM credit_transaction
WHERE creditor_name NOT IN (SELECT name FROM creditor);
