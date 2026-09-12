-- Carry the existing rate onto the two rows that were RELABELLED by the
-- 2026-09-12 form change, rather than leaving them at the 0.00 placeholder
-- migration 0017 set.
--
-- 0017 held these back pending confirmation that the renamed row is the same
-- product. That confirmation is not being sought - this round is form changes,
-- not data validation (client, 2026-09-12) - so the rate on the row as it stood
-- carries through the rename:
--
--     oil1  2T/1.20 ML Total#       -> 2T/1.50 ML Total#          30.00
--     oil4  Acid Water Total 5 Lts  -> Battery Water Total 5 Lts  120.00
--
-- Both figures come from the client's own filled sheet
-- (SVR_DSR_11CC2012V-OFF_09Sep2026_A4.xlsx prices those two rows at 30 and 120).
--
-- oil6 (Battery Water Total 1 Lts) and oil7 (20/40 Engine Total in 05. Lts) stay
-- at 0.00: they are new rows with no prior rate to carry, so there is nothing to
-- bring forward. The Owner sets them in Rate Master, and the Oil Sale(s) Rate
-- cell on the form is editable either way, so a sale can still be keyed from the
-- paper sheet's own Rate column.
--
-- Same effective date as the seed, newest id wins the tie (latest_effective_rates).

INSERT INTO rate_master (item_key, item_label, buy_rate, sell_rate, effective_date, updated_by)
VALUES
    ('oil1', '2T/1.50 ML Total#',         NULL,  30.00, '2026-08-11', 'rate-carry-2026-09-12'),
    ('oil4', 'Battery Water Total 5 Lts', NULL, 120.00, '2026-08-11', 'rate-carry-2026-09-12');
