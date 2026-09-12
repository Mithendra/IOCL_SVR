-- Correct the Oil Sale(s) rates in Rate Master.
--
-- The five oil rates seeded in 0001_init.sql were placeholders that were never
-- replaced with the station's real figures. Confirmed against the client's real
-- filled Daily Sales Reports (2026-09-11):
--
--     item                      seeded    real
--     oil1 2T/1.20 ML            62.00    30.00
--     oil2 2T/2.40 ML           118.00    17.00
--     oil3 Acid Water 1 Lts      30.00    20.00
--     oil4 Acid Water 5 Lts     130.00   120.00
--     oil5 20/40 Engine         280.00   130.00
--
-- On the real 2026-09-09 Office sheet this turned an Oil total of 290 into 1310
-- and put Net Bal Hand Off out by 1020.01. Gas rates (105.36 / 117.70) were
-- seeded correctly and are untouched.
--
-- rate_master is append-only by effective_date and latest_effective_rates()
-- resolves the rate in force on a given date, so these rows carry the same
-- 2026-08-11 effective date as the seed - the September records they need to
-- price were entered after that, and no real entry predates it. Entries already
-- saved keep the rate locked onto them at creation time and are not rewritten.

INSERT INTO rate_master (item_key, item_label, buy_rate, sell_rate, effective_date, updated_by)
VALUES
    ('oil1', '2T/1.20 ML Total#',         NULL,  30.00, '2026-08-11', 'correction-2026-09-11'),
    ('oil2', '2T/2.40 ML Total#',         NULL,  17.00, '2026-08-11', 'correction-2026-09-11'),
    ('oil3', 'Acid Water Total 1 Lts',    NULL,  20.00, '2026-08-11', 'correction-2026-09-11'),
    ('oil4', 'Acid Water Total 5 Lts',    NULL, 120.00, '2026-08-11', 'correction-2026-09-11'),
    ('oil5', '20/40 Engine Total in Lts', NULL, 130.00, '2026-08-11', 'correction-2026-09-11');
