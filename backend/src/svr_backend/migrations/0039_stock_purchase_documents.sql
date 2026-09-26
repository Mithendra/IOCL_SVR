-- Purchase paperwork for the Inventory Tracking Master, kept indefinitely.
--
-- Client, 2026-09-25: "this form should have a capability to upload the Stock
-- Purchase document uploaded like invoice in pdf, jpg any other supported format
-- so that we can see what we bought to keep track forever."
--
-- The FILE lives on disk under <data_dir>/stock-purchases/, not in this table.
-- A scanned invoice is a megabyte or two and they are never deleted; putting
-- them in the database would grow it without bound, and every backup, copy and
-- VACUUM would carry them. The row is the record - who uploaded what, when, for
-- which item, and how to find it again - and `stored_name` is the only link.
--
-- `stored_name` is generated, never the name the file arrived with: an uploaded
-- filename is user input and must not be allowed to choose a path on disk.
-- `original_name` keeps what the operator called it, for display only.
CREATE TABLE stock_purchase_document (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_date    TEXT NOT NULL,              -- the invoice's own date
    item_key         TEXT REFERENCES inventory_item (item_key),  -- NULL = a mixed invoice
    supplier         TEXT,
    amount           REAL,
    note             TEXT,
    original_name    TEXT NOT NULL,
    stored_name      TEXT NOT NULL UNIQUE,
    content_type     TEXT NOT NULL,
    size_bytes       INTEGER NOT NULL,
    uploaded_by      TEXT NOT NULL,
    uploaded_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    last_updated_by  TEXT,
    last_updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX idx_stock_purchase_date ON stock_purchase_document (purchase_date DESC);
CREATE INDEX idx_stock_purchase_item ON stock_purchase_document (item_key);
