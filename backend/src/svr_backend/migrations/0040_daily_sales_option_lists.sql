-- Dropdown lists for the Daily Sales Entry form (client, 2026-09-25).
--
--   "requested for Card Types also + Add Card Type instead of Manully adding
--    and writing the text for example Xtra Power, Visa, Master"
--   "Card Holder Name instead of Card Holder / Terminal ID add Card Holders
--    names ... like Airtel Hari, I.O.C.L, B.S.N.L and Sri Chaithanya"
--   "Section 5 is missing the Creditor Names also need drop down"
--   "Section 6 is also missing the Customer name also need drop down"
--
-- Typed free-hand, the same customer arrives as "Airtel Hari", "AirTel hari" and
-- "airtel", and the Creditor Balance Summary - which groups by name - reports
-- three people who owe a third each. A list is the only thing that stops that.
--
-- Stored in trial_balance_option despite the table's name. It is the station's
-- option store: one table, one API, one "+ New" pattern already built and
-- tested. A second table for the same job would be a second place to look when
-- a value is missing, which is how the SEP12 dropdowns drifted out of date.

INSERT INTO trial_balance_option (list_key, value, sort_order, created_by) VALUES
    ('card_types', 'Xtra Power',       1, 'client-2026-09-25'),
    ('card_types', 'Visa',             2, 'client-2026-09-25'),
    ('card_types', 'Master',           3, 'client-2026-09-25'),

    ('card_holders', 'AirTel Hari',      1, 'client-2026-09-25'),
    ('card_holders', 'I.O.C.L',          2, 'client-2026-09-25'),
    ('card_holders', 'B.S.N.L',          3, 'client-2026-09-25'),
    ('card_holders', 'Sri Chaithanya',   4, 'client-2026-09-25'),

    -- Sections 5 and 6 name the same people: a credit given today and an old
    -- credit repaid are two ends of one customer, so they share one list. Plain
    -- names, not the Trial Balance's "... New Credit" phrases - the Daily Sales
    -- form asks who, and the section already says what.
    ('customers', 'AirTel Hari',          1, 'client-2026-09-25'),
    ('customers', 'Anil/Nani',            2, 'client-2026-09-25'),
    ('customers', 'Sajja Function Hall',  3, 'client-2026-09-25'),
    ('customers', 'I.O.C.L',              4, 'client-2026-09-25'),
    ('customers', 'B.S.N.L',              5, 'client-2026-09-25'),
    ('customers', 'Sri Chaithanya',       6, 'client-2026-09-25');
