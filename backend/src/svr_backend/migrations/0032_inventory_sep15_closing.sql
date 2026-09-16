-- Inventory Master carried to SEP15's CLOSING stock (client, 2026-09-15).
--
-- "This testing goes for one or two days, so you can update the Inventory Master
--  as well with SEP15th data."
--
-- Migration 0031 set `on_hand` from SEP15's OPENING column (D19:D25), which was
-- right while SEP15 was the day in progress. SEP15 is finished now, so the stock
-- the station actually has - and the figure SEP16 opens on - is its CLOSING
-- column, E19:E25 of Trail_balance_15SEP2026.xlsx:
--
--     item                            opening  sold  closing
--     2T/1.50 ML Total#                     0     0        0
--     2T/2.40 ML Total#                    10     5        5   <- the only mover
--     Acid Water Total 1 Lts               64     0       64
--     Battery Water Total 1 Lts            27     0       27
--     Battery Water Total 5 Lts            18     0       18
--     20/40 Engine Total in 05. Lts        38     0       38
--     20/40 Engine Total in 1 Lts           0     0        0
--
-- Only 2T/2.40 moved, so only it changes: 10 -> 5. The other six are restated
-- anyway so this file is the single place to read the current count from, and so
-- that a future reader does not have to hold 0031 and this one in their head at
-- once to know what the stock is.
--
-- A SET, not an adjustment - `on_hand` is the tracked Opening Stock and a count
-- replaces it outright, the same distinction the Inventory screen makes between
-- its Opening column and a Restock receipt.
--
-- The 64 units of Acid Water the client described as expired are still 64 here.
-- The write-off has not happened on the station's own sheet, and putting the app
-- ahead of their count is exactly the drift these migrations exist to end.

UPDATE inventory_item SET on_hand =   0, last_updated_by = 'sep15-closing-2026-09-15'
    WHERE item_key = (SELECT item_key FROM oil_item WHERE label = '2T/1.50 ML Total#');
UPDATE inventory_item SET on_hand =   5, last_updated_by = 'sep15-closing-2026-09-15'
    WHERE item_key = (SELECT item_key FROM oil_item WHERE label = '2T/2.40 ML Total#');
UPDATE inventory_item SET on_hand =  64, last_updated_by = 'sep15-closing-2026-09-15'
    WHERE item_key = (SELECT item_key FROM oil_item WHERE label = 'Acid Water Total 1 Lts');
UPDATE inventory_item SET on_hand =  27, last_updated_by = 'sep15-closing-2026-09-15'
    WHERE item_key = (SELECT item_key FROM oil_item WHERE label = 'Battery Water Total 1 Lts');
UPDATE inventory_item SET on_hand =  18, last_updated_by = 'sep15-closing-2026-09-15'
    WHERE item_key = (SELECT item_key FROM oil_item WHERE label = 'Battery Water Total 5 Lts');
UPDATE inventory_item SET on_hand =  38, last_updated_by = 'sep15-closing-2026-09-15'
    WHERE item_key = (SELECT item_key FROM oil_item WHERE label = '20/40 Engine Total in 05. Lts');
UPDATE inventory_item SET on_hand =   0, last_updated_by = 'sep15-closing-2026-09-15'
    WHERE item_key = (SELECT item_key FROM oil_item WHERE label = '20/40 Engine Total in 1 Lts');
