-- Two checks the operator answers before Close & Sign Off (client, 2026-09-16).
--
--   "Make one additional change to Trial bal - two rows above Close & Sign Off:
--    1. Density Reports updated?
--    2. Off Load Testing MS & HS performed by - list of values Sarath, Gopi,
--       Sriharsha & Girish, also give + symbol to add more names for future ref."
--
-- Both are dropdowns, and the tester list is editable through the same "+ New
-- Name" button the sign-off block already has - the client asked for that
-- explicitly, and a name they cannot add on the day is a name they will type
-- into the wrong cell instead.
--
-- 'offload_testers' is its own list rather than reusing 'staff'. The staff list
-- is who PREPARES and VERIFIES the trial balance (Gopi, Girish, Sriharsha, and
-- the paired "Gopi & Girish" entries); who performed the off-load testing is a
-- different question with a different set of people - Sarath is on this one and
-- not on that one.

INSERT INTO trial_balance_option (list_key, value, sort_order, created_by) VALUES
    ('offload_testers', 'Sarath',    1, 'client-2026-09-16'),
    ('offload_testers', 'Gopi',      2, 'client-2026-09-16'),
    ('offload_testers', 'Sriharsha', 3, 'client-2026-09-16'),
    ('offload_testers', 'Girish',    4, 'client-2026-09-16');

-- A plain yes/no, as a list so the answer is one of three known values rather
-- than free text that has to be interpreted later. "N/A" is there because a day
-- with no off-load has no density report to update, and forcing a "No" onto
-- such a day would read as a missed task.
INSERT INTO trial_balance_option (list_key, value, sort_order, created_by) VALUES
    ('yes_no', 'Yes', 1, 'client-2026-09-16'),
    ('yes_no', 'No',  2, 'client-2026-09-16'),
    ('yes_no', 'N/A', 3, 'client-2026-09-16');
