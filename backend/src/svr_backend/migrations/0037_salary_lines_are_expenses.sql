-- Salary and staff-advance lines belong in Monthly Expenses, not the credit
-- master. Client, 2026-09-25, twice:
--
--   "Salary advance should to Expneses section"
--   "Any Salary or Bi-weekly Salary or Month end salary entered in Daily Trial
--    balance as Expense and when those transaction are posted from Trail those
--    should appear in Monthly Expenses."
--
-- posting.category_for() routes them correctly from now on, but that only fires
-- when a line is (re)synced while still unposted. Lines ALREADY posted under the
-- old rule are sitting in credit_transaction, where they read as money the
-- station is owed - "Salary Advance Reavindra ... 10,000.00 outstanding" on the
-- Creditor Balance Summary, which is backwards: the station paid that out.
--
-- So move them. For each posted salary line:
--   1. add the matching monthly_expense row (payroll category, created if new),
--   2. delete the credit_transaction row it was wrongly filed as,
--   3. re-point the posting row at its new home and mark it 'expense'.
--
-- Matched on the same words posting.py uses ('salar' or 'advance'), and only on
-- rows this app itself posted from a Trial Balance - a credit typed straight
-- into Credit/Remittance Master is left alone, because nothing here knows it was
-- meant to be an expense.

-- 1. Every payroll category these lines need, created once.
INSERT INTO expense_category (name, kind)
SELECT DISTINCT p.label, 'payroll'
FROM trial_balance_posting p
WHERE p.category = 'credit'
  AND p.target_table = 'credit_transaction'
  AND p.status IN ('posted', 'paid')
  AND (LOWER(p.label) LIKE '%salar%' OR LOWER(p.label) LIKE '%advance%')
  AND NOT EXISTS (
    SELECT 1 FROM expense_category ec WHERE ec.name = p.label COLLATE NOCASE
  );

-- 2. The expense row, carrying the day it happened and where it came from.
INSERT INTO monthly_expense (
  expense_date, category_id, amount, description, created_by, last_updated_by
)
SELECT
  p.shift_date,
  (SELECT ec.id FROM expense_category ec WHERE ec.name = p.label COLLATE NOCASE LIMIT 1),
  p.amount,
  'Daily Trial Balance ' || p.shift_date || ' — ' || p.label,
  'migration-0037',
  'migration-0037'
FROM trial_balance_posting p
WHERE p.category = 'credit'
  AND p.target_table = 'credit_transaction'
  AND p.status IN ('posted', 'paid')
  AND (LOWER(p.label) LIKE '%salar%' OR LOWER(p.label) LIKE '%advance%');

-- 3. Out of the credit master. Done before the posting row is re-pointed, while
--    target_id still says which credit_transaction row this was.
DELETE FROM credit_transaction
WHERE id IN (
  SELECT p.target_id FROM trial_balance_posting p
  WHERE p.category = 'credit'
    AND p.target_table = 'credit_transaction'
    AND p.status IN ('posted', 'paid')
    AND (LOWER(p.label) LIKE '%salar%' OR LOWER(p.label) LIKE '%advance%')
    AND p.target_id IS NOT NULL
);

-- 4. Re-point the posting row at the expense it is now.
UPDATE trial_balance_posting
SET category = 'expense',
    target_table = 'monthly_expense',
    target_id = (
      SELECT me.id FROM monthly_expense me
      WHERE me.expense_date = trial_balance_posting.shift_date
        AND me.amount = trial_balance_posting.amount
        AND me.created_by = 'migration-0037'
      ORDER BY me.id DESC LIMIT 1
    ),
    last_updated_by = 'migration-0037'
WHERE category = 'credit'
  AND target_table = 'credit_transaction'
  AND status IN ('posted', 'paid')
  AND (LOWER(label) LIKE '%salar%' OR LOWER(label) LIKE '%advance%');

-- 5. And take the wording off the creditors list, so it cannot be picked in
--    3.14 again. "Salary Advance Reavindra" was added there by hand through
--    "+ New Name" after migration 0028 had already moved salary advances to the
--    expenses list; a list is not a rule, which is why the routing is enforced
--    in code as well.
DELETE FROM trial_balance_option
WHERE list_key = 'creditors'
  AND (LOWER(value) LIKE '%salar%' OR LOWER(value) LIKE '%advance%');
