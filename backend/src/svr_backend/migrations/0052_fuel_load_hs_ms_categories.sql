-- "Fuel Procurement" (0048) was one line for both fuels; the client asked for
-- it split so a Diesel load and a Petrol load are two different expense
-- categories, not one bucket that hides which fuel actually came in
-- (2026-09-28).
--
-- Retired (is_active = 0), not deleted - anything already recorded under it
-- still reports correctly by category_id.
UPDATE expense_category SET is_active = 0 WHERE name = 'Fuel Procurement';

INSERT INTO expense_category (name, kind) VALUES
    ('Fuel Load - HS', 'operational'),
    ('Fuel Load - MS', 'operational');
