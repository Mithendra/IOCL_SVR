-- Each pump's state for the shift (client, 2026-09-14).
--
-- Three states, the client's own words and order:
--
--     1. Sales Man Off    the pump works; nobody was on it
--     2. Repair/Offline   the pump is out of service
--     3. Online           normal
--
-- "so that we can avoid that pump data Entry only when the pump is
--  2.Repair/Offline. In other two cases, there will be data entry."
--
-- So Repair/Offline is the ONLY state that excuses a submission. A pump whose
-- salesman is off still files a report - Current = Last on both nozzles, which
-- is exactly how 11CC2012V-OFF was filed on 13 and 14 September.
--
-- WHY THIS IS A COLUMN AND NOT A NOTE: it decides the day's testing deduction.
-- Testing is 5 litres per nozzle and it is mandatory, but "if the pump is
-- broken, they don't do the testing" (client, 2026-09-14). Two pumps running is
-- 10 litres per fuel; one in repair is 5. That is the whole explanation for a
-- figure this project has chased for three days:
--
--     24 Aug - 06 Sep   ledger deducts 10 / 10.5     both pumps running
--     07 Sep onwards    ledger deducts 5 / 5.5       one pump under repair
--
-- and it is why Section 1 has been deducting 5 per fuel all week while
-- migration 0024's own note recorded the contradiction ("20 litres a day across
-- two pumps is 10 litres per fuel, yet Section 1 deducts 5") without being able
-- to resolve it. Nothing was wrong; one pump was in the workshop.
--
-- Defaulting to 'online' is deliberate and safe: every entry already on file was
-- made by someone who turned up to a working pump, so 'online' is true of all of
-- them. It also keeps the existing testing figures intact for closed days.

ALTER TABLE daily_sales_entry
    ADD COLUMN pump_status TEXT NOT NULL DEFAULT 'online'
    CHECK (pump_status IN ('online', 'salesman_off', 'repair'));

CREATE INDEX idx_dse_status ON daily_sales_entry (shift_date, pump_status);
