-- "Expense Master" (client, 2026-09-27) turns out to already be Monthly
-- Expenses - search by category and date range is already built
-- (api/expenses.py list_expenses, screens/monthly-expenses "2. Search"). The
-- one real gap is the category list: today's generic seed (Rent,
-- Maintenance, Supplies, Misc) doesn't match the 11 named categories given.
--
-- The old generic ones are retired (is_active = 0), not deleted - anything
-- already recorded under them still reports correctly by category_id; the
-- Add-Expense dropdown only offers active categories, so they simply stop
-- being offered for new entries.
UPDATE expense_category SET is_active = 0
WHERE name IN ('Rent', 'Maintenance', 'Supplies', 'Misc', 'Bi-weekly Salary', 'Salary Advances');

INSERT INTO expense_category (name, kind) VALUES
    ('Fuel Procurement',                            'operational'),
    ('Fuel Transport',                               'operational'),
    ('Employee payroll - Middle of Month',           'payroll'),
    ('Employee payroll - End of Month',              'payroll'),
    ('Electricity - Monthly Power Bill',              'operational'),
    ('Monthly Wi-Fi',                                 'operational'),
    ('Equipment maintenance & repairs',               'operational'),
    ('Calibration, testing & inspection',             'operational'),
    ('Licences, permits & statutory compliance',      'operational'),
    ('Employee Insurance',                            'operational'),
    ('POS - Maintenance',                             'operational');
