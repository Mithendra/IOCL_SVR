-- One nullable column to carry Section 5/6's richer fields (litres, rate,
-- payment mode, dates, collected by, submitted-by pump salesman) from
-- sync_lines() through to post_line(), for the two new pulled-row categories
-- only. Every existing category (expense, typed credit, typed remittance)
-- leaves this NULL and is unaffected - post_line() only reads it for the rows
-- that have it to give.
ALTER TABLE trial_balance_posting ADD COLUMN extra_json TEXT;
