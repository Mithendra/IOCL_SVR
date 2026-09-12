-- Facts read off the client's most recent Trial Balance tab, SEP12
-- (docs/01-BRD-Requirement-Gathering/ocr-samples/Trail_balance_12-SEP-2026.xlsx).
-- Two things that tab settles, both of which the app currently has wrong.
--
-- =====================================================================
-- 1. OIL RATES. Section 2.1 "Oil Sales" prices every row directly:
--
--        2T/1.50 ML                       17
--        Battery Water Total 5 Lts       120
--        Battery Water Total 1 Lts        20
--        Acid Water 1Lts                  30
--        20/40 Engine Total in 1/2Ltr    140
--        20/40 Engine Total in 1Ltr      270
--
--    Migration 0017/0018 had to infer these from the OLD five-row Daily Sales
--    list, and three of the six inferences were wrong:
--
--        oil1  2T/1.50 ML             30  ->  17    (carried the 2T/1.20 rate)
--        oil3  Acid Water Total 1 Lts 20  ->  30
--        oil5  20/40 Engine 1 Lts    130  ->  270
--        oil6  Battery Water 1 Lts     0  ->  20    (was "not set")
--        oil7  20/40 Engine 05. Lts    0  -> 140    (was "not set")
--        oil4  Battery Water 5 Lts   120  -> 120    (unchanged, confirmed)
--
--    So the renames did NOT carry their old rates across, which is exactly why
--    0018 was the wrong call. These six are now read off the client's own sheet
--    rather than inferred from a previous list.
--
--    oil2 (2T/2.40 ML Total#) does not appear on SEP12 at all. It is left at 17,
--    the rate the 2026-09-09/10 Daily Sales Reports price it at - the only
--    evidence on file for that row. Flagged to the client: SEP12's Oil Sales has
--    SIX rows and the Daily Sales Entry form the client specified on 2026-09-12
--    has SEVEN, the extra one being 2T/2.40 ML.
--
-- =====================================================================
-- 2. TESTING / DENSITY DEDUCTION is 5.5 per fuel on SEP12, not 10.
--
--    Section 1 "Daily Testing" = "Actual Consump" - 5.5, on both fuels
--    independently and exactly:
--
--        Diesel  591.87 - 586.37 = 5.5
--        Petrol  546.27 - 540.77 = 5.5
--
--    which reads as the 5 L test draw plus the 0.5 L density check named on the
--    Daily Sales Entry expenses row. The seeded 10.0 matched AUG11/AUG12, so this
--    is a real change over time rather than a seeding error - which is what
--    system_parameter's effective-dating exists for. Effective 2026-09-12, so
--    every earlier Trial Balance still computes with the 10.0 that was in force
--    on its own date and no historical record moves.

INSERT INTO rate_master (item_key, item_label, buy_rate, sell_rate, effective_date, updated_by)
VALUES
    ('oil1', '2T/1.50 ML Total#',             NULL,  17.00, '2026-09-12', 'sep12-trial-balance'),
    ('oil3', 'Acid Water Total 1 Lts',        NULL,  30.00, '2026-09-12', 'sep12-trial-balance'),
    ('oil4', 'Battery Water Total 5 Lts',     NULL, 120.00, '2026-09-12', 'sep12-trial-balance'),
    ('oil5', '20/40 Engine Total in 1 Lts',   NULL, 270.00, '2026-09-12', 'sep12-trial-balance'),
    ('oil6', 'Battery Water Total 1 Lts',     NULL,  20.00, '2026-09-12', 'sep12-trial-balance'),
    ('oil7', '20/40 Engine Total in 05. Lts', NULL, 140.00, '2026-09-12', 'sep12-trial-balance');

INSERT INTO system_parameter (name, value, effective_date, updated_by)
VALUES ('testing_density_deduction', 5.5, '2026-09-12', 'sep12-trial-balance');
