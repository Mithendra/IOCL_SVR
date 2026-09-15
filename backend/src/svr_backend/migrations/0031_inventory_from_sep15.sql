-- Oil stock set to the station's own cleaned-up count (client, 2026-09-15).
--
-- "We have sorted out all the oil rates as well as the inventory - all the
--  inventory they have cleaned it up."
--
-- Every figure in `inventory_item` was still the placeholder seeded in migration
-- 0004 on day one. Six of the seven were wrong against the station's own sheet,
-- and nobody had ever set them:
--
--     item                            seeded    actual    gap
--     2T/1.50 ML Total#                   40         0    -40
--     2T/2.40 ML Total#                   30        10    -20
--     Acid Water Total 1 Lts              60        64     +4
--     Battery Water Total 1 Lts            0        27    +27
--     Battery Water Total 5 Lts           18        18      -    (the only one right)
--     20/40 Engine Total in 05. Lts        0        38    +38
--     20/40 Engine Total in 1 Lts        120         0   -120
--
-- Taken from the SEP15 tab's own Opening Stock column, D19:D25 of
-- Trail_balance_15SEP2026.xlsx, which both SEP15 DSRs agree with (column L).
--
-- This is a SET, not an adjustment - `on_hand` is the tracked Opening Stock and
-- a count replaces it outright. The same distinction the Inventory screen makes
-- between its Opening column and a Restock receipt.
--
-- STILL OUTSTANDING, and deliberately not acted on here: the client said on
-- 2026-09-14 that the 64 units of Acid Water are expired and are to be written
-- off. They are still 64 on the SEP15 sheet, so the write-off has not happened
-- in the data yet. Setting them to zero on that conversation alone would put the
-- app out of step with the station's own count - which is exactly the state this
-- migration exists to end. Raised with the client instead.

UPDATE inventory_item SET on_hand =   0, last_updated_by = 'client-count-2026-09-15'
    WHERE item_key = (SELECT item_key FROM oil_item WHERE label = '2T/1.50 ML Total#');
UPDATE inventory_item SET on_hand =  10, last_updated_by = 'client-count-2026-09-15'
    WHERE item_key = (SELECT item_key FROM oil_item WHERE label = '2T/2.40 ML Total#');
UPDATE inventory_item SET on_hand =  64, last_updated_by = 'client-count-2026-09-15'
    WHERE item_key = (SELECT item_key FROM oil_item WHERE label = 'Acid Water Total 1 Lts');
UPDATE inventory_item SET on_hand =  27, last_updated_by = 'client-count-2026-09-15'
    WHERE item_key = (SELECT item_key FROM oil_item WHERE label = 'Battery Water Total 1 Lts');
UPDATE inventory_item SET on_hand =  18, last_updated_by = 'client-count-2026-09-15'
    WHERE item_key = (SELECT item_key FROM oil_item WHERE label = 'Battery Water Total 5 Lts');
UPDATE inventory_item SET on_hand =  38, last_updated_by = 'client-count-2026-09-15'
    WHERE item_key = (SELECT item_key FROM oil_item WHERE label = '20/40 Engine Total in 05. Lts');
UPDATE inventory_item SET on_hand =   0, last_updated_by = 'client-count-2026-09-15'
    WHERE item_key = (SELECT item_key FROM oil_item WHERE label = '20/40 Engine Total in 1 Lts');
