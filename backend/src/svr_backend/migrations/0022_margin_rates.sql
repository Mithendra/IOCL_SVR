-- Margin rates and the daily-expenses deduction, read out of the SEP12 tab's own
-- formulas (skills/trial-balance-reconciliation/references/sep12-formula-register.md).
--
-- Four Section 1 columns were manual entry with a note saying their formulas had
-- "never been confirmed against a filled workbook". They are confirmed now - the
-- workbook states them outright, and extracting them mechanically is what turned
-- them up:
--
--     H3 = G3*2.61     Margin HS  = Daily Testing x 2.61
--     H4 = G4*4.14     Margin MS  = Daily Testing x 4.14
--     L3 = F3*C67      IOCL Adv HS = Consump Diff x Buy Rate HS
--     L4 = F4*C68      IOCL Adv MS = Consump Diff x Buy Rate MS
--
-- 2.61 and 4.14 are per-litre margin (commission) rates. They are not one day's
-- constants: the Section 9 ledger uses the same two for its MS Comm / HS Comm
-- columns (V109 = D109*4.14, W109 = E109*2.61), which is what makes them rates.
--
-- D102 = D98-300-1666.66-666.66-666.66 - "Actual Profit all Daily Expenses
-- Rs3300". The four constants total 3,299.98, which is the Rs3300 in the label.
-- Stored as one parameter rather than four magic numbers; if the station ever
-- changes a component the Owner edits the total here.
--
-- system_parameter is versioned by effective_date, so a later change never
-- rewrites a closed day.

INSERT INTO system_parameter (name, value, effective_date, updated_by) VALUES
    ('margin_rate_hs',            2.61,    '2026-09-12', 'sep12-formula-register'),
    ('margin_rate_ms',            4.14,    '2026-09-12', 'sep12-formula-register'),
    ('daily_expenses_deduction',  3299.98, '2026-09-12', 'sep12-formula-register');
