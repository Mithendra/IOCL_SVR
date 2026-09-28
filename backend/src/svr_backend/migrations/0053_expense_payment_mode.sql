-- 3.13a Daily Expenses' own Payment Mode (client, 2026-09-28): a till only
-- balances against money that actually moved cash - a Salary Advance paid in
-- cash reduces today's cash projection the same way Beta/Testing already
-- does; the same category paid by bank transfer, or bought on credit terms,
-- never touched the till and must not. See calc/daily_trial_balance.py's
-- `s3_daily_expenses_cash_total`.
INSERT INTO trial_balance_option (list_key, value, sort_order) VALUES
    ('expense_payment_mode', 'Cash', 1),
    ('expense_payment_mode', 'Bank', 2),
    ('expense_payment_mode', 'Credit', 3);
