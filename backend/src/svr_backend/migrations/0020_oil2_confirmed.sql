-- 2T/2.40 ML Total# (oil2) stays on the forms - client-confirmed 2026-09-12.
--
-- It is the one Oil Sale(s) row that does NOT appear on the client's SEP12 Trial
-- Balance tab, whose Oil Sales block lists six rows to the Daily Sales Entry
-- form's seven. Flagged to the client on 2026-09-12; confirmed to keep it.
--
-- Nothing about oil2 was broken - it has been on every form throughout (Daily
-- Sales Entry, Daily Sales Summary, Daily Trial Balance §2.1, Inventory Tracking
-- and Rate Master). What it lacked was a rate row carrying the same 2026-09-12
-- effective date as its six siblings: migration 0019 re-priced those from the
-- SEP12 sheet and left oil2 resolving back to its 2026-08-11 row. The rate is
-- unchanged at 17.00 - the figure the 2026-09-09 and 2026-09-10 Daily Sales
-- Reports price that row at, which remains the only evidence on file for it.
--
-- This row exists so Rate Master shows all seven items at one effective date and
-- so the confirmation is recorded against the data rather than only in a commit
-- message.

INSERT INTO rate_master (item_key, item_label, buy_rate, sell_rate, effective_date, updated_by)
VALUES ('oil2', '2T/2.40 ML Total#', NULL, 17.00, '2026-09-12', 'client-confirmed-2026-09-12');
