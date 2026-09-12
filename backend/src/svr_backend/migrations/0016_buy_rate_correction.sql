-- Correct the Buy Rates in Rate Master.
--
-- Seeded 101.50 (HS) / 112.30 (MS); the station's real figures are
-- 102.75 / 113.56. Confirmed against SEPTEMBER data (the client's most recent),
-- and independently corroborated by AUG11:
--
--   SEP06 Section 6, client-validated (SVR-Trial-Balance-Audit-2026-09-06.md):
--     Diesel  9,119 L x 102.75 = 936,977.25   <- matches the sheet exactly
--     Petrol 10,043 L x 113.56 = 1,140,483.08 <- matches the sheet exactly
--     Total                      2,077,460.33 <- matches the sheet exactly
--
-- The seeded rates cannot be right: they imply 9,231.30 L and 10,155.68 L for
-- those same rupee figures, and IOCL stock readings are whole litres.
--
-- Buy Rate feeds only Section 6 Stock Value -> the Section 7 grand total. Daily
-- Sales Entry is unaffected (it locks the SELL rate, 105.36 / 117.70, which the
-- September Daily Sales Reports confirm is already correct).
--
-- Effective 2026-08-11, the same date as the seed: both AUG11 and SEP06 price
-- stock at these rates, so they held across the whole period we have evidence
-- for. latest_effective_rates() breaks the same-date tie by newest id, so this
-- correction wins. Entries already saved keep the rate locked on at creation.

INSERT INTO rate_master (item_key, item_label, buy_rate, sell_rate, effective_date, updated_by)
VALUES
    ('HS', 'Diesel (HS)', 102.75, 105.36, '2026-08-11', 'correction-2026-09-11'),
    ('MS', 'Petrol (MS)', 113.56, 117.70, '2026-08-11', 'correction-2026-09-11');
