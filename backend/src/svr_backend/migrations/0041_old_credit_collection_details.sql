-- Section 6, Old/Pending Credit Received: how the money actually came in
-- (client, 2026-09-25).
--
--   "Add column 'Payment' Full or Partial and add Column 'Remittance Entered'
--    Yes or No Add Col Collected by Drop down list of values Sriharsha, Girish,
--    Ravindra, Ashok, Gopi, Vijay Add col Payment Mode - Cash, Phone Pay,
--    Credit Card"
--
-- The row itself needs no schema change: old_credit_rows is a free-form list of
-- dicts on the Daily Sales Entry payload, so the four new fields ride along with
-- the ones already there. What is needed is the lists behind three of them.
--
-- Two of the four reuse a list that already exists rather than growing a second
-- one for the same job - the mistake migration 0040 was written to avoid:
--
--   Collected by      -> 'staff', which already holds Gopi, Girish and
--                        Sriharsha. Only Ravindra, Ashok and Vijay are missing,
--                        so they are added below. One list of people means a
--                        name taken on once is offered everywhere staff are
--                        named, instead of "Ravindra" existing in one dropdown
--                        and not another.
--   Remittance Entered -> 'yes_no', already Yes / No / N/A.
--
-- The other two are new, because nothing here means the same thing:
--
--   Payment       -> whether the credit is cleared or only part-paid. This is
--                    the one that decides whether the customer still owes, so it
--                    is a list of exactly two values, not free text.
--   Payment Mode  -> how it arrived. Cash and Phone Pay land in different places
--                    in Section 3, and a card payment is a third thing again, so
--                    the mode has to be recorded at the point of collection
--                    rather than reconstructed later.

INSERT INTO trial_balance_option (list_key, value, sort_order, created_by) VALUES
    -- the three the client named that the staff list did not already have
    ('staff', 'Ravindra', 6, 'client-2026-09-25'),
    ('staff', 'Ashok',    7, 'client-2026-09-25'),
    ('staff', 'Vijay',    8, 'client-2026-09-25'),

    ('payment_type', 'Full',    1, 'client-2026-09-25'),
    ('payment_type', 'Partial', 2, 'client-2026-09-25'),

    ('payment_modes', 'Cash',        1, 'client-2026-09-25'),
    ('payment_modes', 'Phone Pay',   2, 'client-2026-09-25'),
    ('payment_modes', 'Credit Card', 3, 'client-2026-09-25');
