-- Credit/Remittance Master rebuild (client, 2026-09-26/27): Section 1 (New
-- Credit) and Section 2 (Remittance) gain Daily Sales Entry Section 5/6's own
-- columns, plus a Status showing whether a row arrived automatically from
-- Daily Trial Balance or was typed by hand.
--
--   "Both of these transaction should come from Daily Trial balance report
--    when posted." - confirmed route: Daily Sales Entry -> Daily Trial
--    Balance -> Credit Master, not through Daily Sales Summary (Summary
--    combines two pumps' numbers; it has no concept of an itemised row).
--
-- `payment_mode`, `given_on_date` and `pump_sales_man`/`note` apply to a
-- credit row; `payment`, `remittance_entered` and `collected_by` apply to a
-- remittance row only - nobody enforces that split at the schema level (kind
-- already does), so all six are just nullable columns on the one table, the
-- same way `fuel_type`/`ltrs`/`rate` already are credit-only.
--
-- `given_on_date` on a REMITTANCE row is the ORIGINAL credit's date, not this
-- remittance's own - `txn_date` already serves as the remittance's own date
-- (client's "Paid On Date"). A credit given weeks ago paid off today needs
-- both dates on screen at once.
--
-- `status` says how the row got here. Every row created through post_line()
-- (the Daily Trial Balance posting pipeline) is stamped 'posted_dt'; a row
-- added directly through Credit Master's own +New (add_credit/add_remittance)
-- is 'manual'. Existing rows default to 'manual' - they predate this pipeline
-- and were, in fact, typed by hand.
ALTER TABLE credit_transaction ADD COLUMN payment_mode      TEXT;
ALTER TABLE credit_transaction ADD COLUMN payment           TEXT;  -- 'Full' / 'Partial', remittance only
ALTER TABLE credit_transaction ADD COLUMN remittance_entered TEXT; -- 'Yes' / 'No', remittance only
ALTER TABLE credit_transaction ADD COLUMN collected_by      TEXT;  -- remittance only
ALTER TABLE credit_transaction ADD COLUMN given_on_date     TEXT;  -- remittance only: the credit's own date
ALTER TABLE credit_transaction ADD COLUMN status TEXT NOT NULL DEFAULT 'manual'
    CHECK (status IN ('manual', 'posted_dt'));
