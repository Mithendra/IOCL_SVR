-- Section 5, Today New Credit(s): a Payment Mode column (client, 2026-09-26):
--
--   "under 5. Today New Credit(s) add col called Payment Mode - Credit(CR)"
--
-- Reuses 'payment_modes' (Cash / Phone Pay / Credit Card, seeded in 0041 for
-- Section 6) rather than a second list: it is the same question - how is this
-- money being handled - asked in the section that ISSUES the credit instead of
-- the one that COLLECTS it. One shared list means a value added in either
-- section is available in the other.
--
-- "Credit (CR)" is new: Section 5 is the credit itself, so its own payment mode
-- is usually neither cash nor card but the running account the client's own
-- abbreviation names.

INSERT INTO trial_balance_option (list_key, value, sort_order, created_by) VALUES
    ('payment_modes', 'Credit (CR)', 4, 'client-2026-09-26');
