-- The original seed's "Power Bill" category (pre-dating the 11 named
-- categories, migration 0048) was left active after "Electricity - Monthly
-- Power Bill" was added as its replacement (2026-09-27/28 cross-check with
-- item 6). Both meant the same thing and both showing up in the dropdown
-- risked new entries splitting across two categories instead of one.
--
-- Retired (is_active = 0), not deleted - anything already recorded under it
-- still reports correctly by category_id.
UPDATE expense_category SET is_active = 0 WHERE name = 'Power Bill';
