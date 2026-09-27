-- 3.13 "New Credit / Salary Advance" becomes two visible sections (client,
-- 2026-09-27): "Daily Credits" and "Daily Expenses", instead of one mixed
-- dropdown invisibly separated by posting.category_for() matching
-- "salar"/"advance" in the label.
--
-- The 'creditors' list backs the new Daily Credits dropdown, so a salary
-- advance sitting in it - typed there before this split existed - no longer
-- belongs: it would offer a payroll item in a list of fuel creditors. Removed
-- from the LIST only; any day already saved with that value keeps reading it
-- back exactly as recorded (this is an option list, not the record).
DELETE FROM trial_balance_option
WHERE list_key = 'creditors' AND (LOWER(value) LIKE '%salar%' OR LOWER(value) LIKE '%advance%');
