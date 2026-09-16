-- Acid Water written off - expired stock (client, 2026-09-15).
--
-- "There is inventory sitting and we are not selling anything, which is Acid
--  Water 64 - that also will be removed because it is expired... I'll ask them
--  to remove those inventory. You can remove it. Hopefully tomorrow's trial
--  balance will have those ones updated to zero."
--
-- 64 units of 'Acid Water Total 1 Lts' go to 0. They have not moved on any day
-- on file - SEP12 through SEP15 all show 64 opening, 0 sold, 64 closing - which
-- is what expired stock looks like in a ledger.
--
-- THIS IS A WRITE-OFF, NOT A SALE. Nothing is posted anywhere: no revenue, no
-- expense, no credit. The units are simply gone. Recorded here rather than by
-- setting on_hand through the Inventory screen so the REASON survives - the
-- audit log would otherwise show only "64 -> 0" and, in a year, nobody would
-- know whether that was expiry or a miscount.
--
-- Oil stock does not appear in the Trial Balance's Net Worth - Section 5 Stock
-- Value is Diesel and Petrol only (B67 = C3, B68 = C4) - so this moves no total
-- on any tab. Its whole effect is the oil Opening Stock on the Daily Sales
-- Report and the app's Inventory screen.
--
-- The SEP16 sheet going to the station carries 0 for this item to match, with a
-- note beside it saying why its opening is not SEP15's closing. Without that,
-- the next person to check the carry-forward finds a 64-unit gap and no reason.

UPDATE inventory_item SET on_hand = 0, last_updated_by = 'expired-write-off-2026-09-15'
    WHERE item_key = (SELECT item_key FROM oil_item WHERE label = 'Acid Water Total 1 Lts');
