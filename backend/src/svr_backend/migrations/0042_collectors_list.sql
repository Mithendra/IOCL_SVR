-- Section 6 "Collected by" gets its own list of people (client, 2026-09-26).
--
--   "Collected by Drop down list of values Sriharsha, Girish, Ravindra, Ashok,
--    Vijay and remove the names like Gopi & Girish and Girish/Sriharsha - No
--    Combinations names"
--
-- 0041 pointed this column at the existing 'staff' list, to avoid a second list
-- of the same people. That was the wrong call for one reason that only shows up
-- now: 'staff' legitimately holds PAIRS - 'Gopi & Girish', 'Girish/Sriharsha' -
-- because the Trial Balance's 8.16 sign-off and Section 10 record work two
-- people did together. One person collects a credit; two people sign off a
-- shift. They are different questions and cannot share one list.
--
-- So the pairs stay exactly where they are. 'staff' is untouched by this
-- migration - the Trial Balance screen, sections.js and the Excel export's
-- D103:D105 validation all still read it - and Section 6 gets the plain list of
-- individuals the client asked for.
--
-- Gopi appears in the client's first list (2026-09-25) but not the second
-- (2026-09-26). Seeded as asked, without him: the form's own "+ New" adds a name
-- back in seconds, and inventing an entry the client left out is the worse of
-- the two mistakes.

INSERT INTO trial_balance_option (list_key, value, sort_order, created_by) VALUES
    ('collectors', 'Sriharsha', 1, 'client-2026-09-26'),
    ('collectors', 'Girish',    2, 'client-2026-09-26'),
    ('collectors', 'Ravindra',  3, 'client-2026-09-26'),
    ('collectors', 'Ashok',     4, 'client-2026-09-26'),
    ('collectors', 'Vijay',     5, 'client-2026-09-26');
