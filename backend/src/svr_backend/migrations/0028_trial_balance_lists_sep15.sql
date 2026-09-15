-- The station's own dropdown lists, restated (client, 2026-09-14).
--
-- Supplied as a typed list and cross-checked against the SEP15 tab's own Excel
-- data validations in Trail_balance_14SEP2026._Claude_corrected.xlsx (A87/A88
-- for expenses, A60 for remittance, A43 for credits). Where the two differ the
-- CLIENT'S TYPED LIST WINS - they wrote it deliberately and it adds
-- "Other - If Any", which the sheet's validation does not carry.
--
-- The big change is that SALARY ADVANCES MOVE from the creditors list to the
-- expenses list. Confirmed 2026-09-14: "salary advances, salaries, power bill,
-- other expenses, load/unload, everything goes to the expenses sheet." An
-- advance to a member of staff is an expense, not fuel taken on credit, and it
-- must post to Monthly Expenses rather than to a creditor's balance.
--
-- Named per person now, not "Salary Advances Total": Vijay, Ravindra, Ashok.
-- "Salaries Mid/End of Month - Total" likewise splits into Middle and End, which
-- is how the station actually pays.
--
-- NOTHING IS DELETED. Rows already saved keep the label they were entered with,
-- and the screen renders a retired value even when it is no longer offered
-- (optionMarkup keeps `selected` in the list) - the same discipline as the
-- retired Oil Sale(s) rows. So superseded entries are removed from the OFFER
-- only, by deleting the option row, while every saved record is untouched.

-- Regular Expenses - replaces the four seeded in 0021.
DELETE FROM trial_balance_option WHERE list_key = 'expenses';
INSERT INTO trial_balance_option (list_key, value, sort_order, created_by) VALUES
    ('expenses', 'Salaries Middle of the Month - Total', 1, 'client-2026-09-14'),
    ('expenses', 'Salaries End of the Month Total',      2, 'client-2026-09-14'),
    ('expenses', 'Power Bill',                           3, 'client-2026-09-14'),
    ('expenses', 'Unload Beta',                          4, 'client-2026-09-14'),
    ('expenses', 'Salary Advances Vijay',                5, 'client-2026-09-14'),
    ('expenses', 'Salary Advances Ravindra',             6, 'client-2026-09-14'),
    ('expenses', 'Salary Advances Ashok',                7, 'client-2026-09-14'),
    ('expenses', 'Other - If Any',                       8, 'client-2026-09-14');

-- Credit - Regular Customers. Three names; the salary advances that used to sit
-- here have moved to expenses above, and "Anil New Credit" folds into
-- "Anil/Nani New Credit" - the client confirmed on 2026-09-14 that Anil and Nani
-- are one person ("his nickname is nani and his name is anil"), so they must not
-- carry two separate balances.
DELETE FROM trial_balance_option WHERE list_key = 'creditors';
INSERT INTO trial_balance_option (list_key, value, sort_order, created_by) VALUES
    ('creditors', 'Anil/Nani New Credit',              1, 'client-2026-09-14'),
    ('creditors', 'AirTel Hari New Credit',            2, 'client-2026-09-14'),
    ('creditors', 'Sajja Function Hall - New Credit',  3, 'client-2026-09-14');

-- Remittances were already correct in 0021 and are restated only so this file
-- is the single place to read the current lists from.
DELETE FROM trial_balance_option WHERE list_key = 'remittance';
INSERT INTO trial_balance_option (list_key, value, sort_order, created_by) VALUES
    ('remittance', 'Sajja Old Credit Remitted Amt',        1, 'client-2026-09-14'),
    ('remittance', 'Anil/Nani Old Credit Remitted Amt',    2, 'client-2026-09-14'),
    ('remittance', 'AirTel Hari Old Credit Remitted Amt',  3, 'client-2026-09-14'),
    ('remittance', 'AirTel New Credit Remitted Amt',       4, 'client-2026-09-14');

-- Section 8.7 Old Credit Collections. The client did not restate this one. It
-- is the same four people as Remittances, spelled differently in the sheet
-- ("Anil Old Credit Remitted" vs "Anil/Nani Old Credit Remitted Amt"), and two
-- spellings of one creditor is exactly how a balance splits in two. Aligned to
-- the Remittances wording; FLAGGED for the client rather than assumed settled.
DELETE FROM trial_balance_option WHERE list_key = 'old_credit';
INSERT INTO trial_balance_option (list_key, value, sort_order, created_by) VALUES
    ('old_credit', 'Sajja Old Credit Remitted Amt',        1, 'client-2026-09-14'),
    ('old_credit', 'Anil/Nani Old Credit Remitted Amt',    2, 'client-2026-09-14'),
    ('old_credit', 'AirTel Hari Old Credit Remitted Amt',  3, 'client-2026-09-14'),
    ('old_credit', 'AirTel New Credit Remitted Amt',       4, 'client-2026-09-14');
