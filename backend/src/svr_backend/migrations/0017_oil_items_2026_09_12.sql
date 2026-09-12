-- Oil Sale(s) revised from five rows to seven (client, 2026-09-12).
--
-- The form's new row list, in order:
--
--     2T/1.50 ML Total#
--     2T/2.40 ML Total#
--     Acid Water Total 1 Lts
--     Battery Water Total 1 Lts        <- new
--     Battery Water Total 5 Lts
--     20/40 Engine Total in 05. Lts    <- new
--     20/40 Engine Total in 1 Lts
--
-- item_key identifies a PRODUCT, not a row position, so three existing keys are
-- relabelled in place and keep their rate history and their tracked stock:
--
--     oil1  2T/1.20 ML Total#          -> 2T/1.50 ML Total#
--     oil4  Acid Water Total 5 Lts     -> Battery Water Total 5 Lts
--     oil5  20/40 Engine Total in Lts  -> 20/40 Engine Total in 1 Lts
--
-- and two new keys are added for the rows that did not exist before:
--
--     oil6  Battery Water Total 1 Lts
--     oil7  20/40 Engine Total in 05. Lts
--
-- That is why OIL_KEYS in calc/daily_sales_entry.py is not in numeric order.
--
-- RATES. A rate is carried forward ONLY where the evidence actually reaches the
-- new row. A plausible-looking placeholder is precisely what put the 2026-09-09
-- Oil total out by 1,020.01 (migration 0015), so anything not evidenced is seeded
-- 0.00 - which is also the client's own stated rule for that column ("when there
-- is blank it should be zero"), not a silent guess:
--
--   oil2  17.00  carried - label unchanged, priced on the 09Sep/10Sep sheets
--   oil3  20.00  carried - label unchanged, priced on the 10Sep sheet
--   oil5 130.00  carried - the old single "20/40 Engine Total in Lts" row is
--                unambiguously the 1 Lts one now that a 0.5 Lts row exists beside
--                it (daily_trial_balance_branded.html 2.6.4/2.6.5 already listed
--                the two pack sizes separately), and the 10Sep sheet prices that
--                row at 130 for one unit
--   oil1   0.00  NOT carried. The old row was "2T/1.20 ML" at 30.00, but the
--                Trial Balance mockup lists 2T/1.20 ML and 2T/1.50 ML as two
--                DIFFERENT items (2.6.1 / 2.6.2), so 30.00 may well be the 1.20
--                pack's price. Owner to confirm.
--   oil4   0.00  NOT carried. The old row was "Acid Water Total 5 Lts" at 120.00.
--                Battery water and acid water are plausibly the same commodity
--                renamed, but nothing on file says so. Owner to confirm.
--   oil6   0.00  new row, no rate on any sheet or in the BRD
--   oil7   0.00  new row, no rate on any sheet or in the BRD
--
-- The Owner sets the real figures in Rate Master. Until then the Oil Sale(s) Rate
-- cell on the form is editable, so a day's sale can still be keyed straight from
-- the paper sheet's own Rate column - which is the authoritative source for oils
-- anyway (client-confirmed 2026-09-11).
--
-- sell_rate is NOT NULL in the schema, so 0.00 is the only way to say "not set".
--
-- rate_master is append-only by effective_date and latest_effective_rates()
-- breaks a same-date tie by newest id, so these rows carry the same 2026-08-11
-- effective date as the seed and win over it. Entries already saved keep the
-- rate locked onto them at creation time and are not rewritten.

INSERT INTO rate_master (item_key, item_label, buy_rate, sell_rate, effective_date, updated_by)
VALUES
    ('oil1', '2T/1.50 ML Total#',             NULL,   0.00, '2026-08-11', 'form-change-2026-09-12'),
    ('oil2', '2T/2.40 ML Total#',             NULL,  17.00, '2026-08-11', 'form-change-2026-09-12'),
    ('oil3', 'Acid Water Total 1 Lts',        NULL,  20.00, '2026-08-11', 'form-change-2026-09-12'),
    ('oil6', 'Battery Water Total 1 Lts',     NULL,   0.00, '2026-08-11', 'form-change-2026-09-12'),
    ('oil4', 'Battery Water Total 5 Lts',     NULL,   0.00, '2026-08-11', 'form-change-2026-09-12'),
    ('oil7', '20/40 Engine Total in 05. Lts', NULL,   0.00, '2026-08-11', 'form-change-2026-09-12'),
    ('oil5', '20/40 Engine Total in 1 Lts',   NULL, 130.00, '2026-08-11', 'form-change-2026-09-12');

-- Inventory Tracking: relabel the three renamed products (on_hand and
-- reorder_level untouched - the stock on the shelf did not move because the form
-- changed), and add the two new ones with nothing counted yet. A Manager sets the
-- opening figure directly on the Inventory Tracking screen (the editable On Hand
-- column added 2026-09-11), which replaces the value rather than adding to it.

UPDATE inventory_item
   SET item_label = '2T/1.50 ML Total#',
       last_updated_by = 'form-change-2026-09-12',
       last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
 WHERE item_key = 'oil1';

UPDATE inventory_item
   SET item_label = 'Battery Water Total 5 Lts',
       last_updated_by = 'form-change-2026-09-12',
       last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
 WHERE item_key = 'oil4';

UPDATE inventory_item
   SET item_label = '20/40 Engine Total in 1 Lts',
       last_updated_by = 'form-change-2026-09-12',
       last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
 WHERE item_key = 'oil5';

INSERT INTO inventory_item (item_key, item_label, unit, on_hand, reorder_level, last_updated_by)
VALUES
    ('oil6', 'Battery Water Total 1 Lts',     'ltr', 0, 20, 'form-change-2026-09-12'),
    ('oil7', '20/40 Engine Total in 05. Lts', 'ltr', 0, 40, 'form-change-2026-09-12');
