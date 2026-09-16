-- Bank names as plain text, statement balance only (client, 2026-09-16).
--
--   "Incorporate the Bank Names like Yes, IOCL and Indian bank in the Daily
--    Trial (no need of actual a/c numbers), just text is fine (no need of
--    account numbers, IFSC codes, UPI handles and PANs) in this application -
--    Do not want expose those details in the application JUST STATEMENT
--    BALANCE ONLY"
--
-- Daily Trial Balance already holds exactly this shape at 3.8 / 3.9 / 3.10 -
-- a named bank and its statement ending balance, nothing else. This migration
-- makes the three names a real list so anything that needs to say WHICH bank
-- (a cash deposit, a remittance) picks a name instead of someone typing
-- "YB" one day and "Yes bank" the next, and so the names live in one place.
--
-- THE RULE, and it is a rule and not a preference: an account number, IFSC
-- code, UPI handle, MICR or PAN must never be stored, seeded, displayed or
-- logged by this application. A balance is what the station reconciles; an
-- account number adds nothing to that and turns a stolen laptop or a screen
-- share into a much worse day. backend/tests/test_no_bank_identifiers.py
-- fails the build if one appears in a migration, a seed or a screen.
--
-- The station's own bank and IOCL statement PDFs stay out of the repo for the
-- same reason (.gitignore) - this repo is public.

INSERT INTO trial_balance_option (list_key, value, sort_order, created_by) VALUES
    ('banks', 'Indian Bank', 1, 'client-2026-09-16'),
    ('banks', 'Yes Bank',    2, 'client-2026-09-16'),
    ('banks', 'IOCL Spana',  3, 'client-2026-09-16');
