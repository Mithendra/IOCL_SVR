-- Daily Trial Balance dropdown lists, so the station can add a value itself.
--
-- The client's SEP12 tab carries four Excel Data Validation lists (plus the 8.9
-- sign-off names). They are not fixed: a new customer asks for credit, a new
-- expense category appears, and the form has to accept it that day - client,
-- 2026-09-12. Hard-coding them in the renderer made that impossible.
--
-- Stored here rather than in the record's `manual` blob because these are MASTER
-- data, not a day's figures: a value added while entering Tuesday must be there
-- on Wednesday, and for every other user. `system_parameter` cannot hold them -
-- its `value` column is REAL.
--
-- Seeds are transcribed verbatim from the SEP12 sheet's own validation formulas
-- (A42:A45, A54:A57 + A87:A89, A59:A61, A92:A93), leading/trailing spaces
-- trimmed. Note the sheet really does carry both "Anil/Nani New Credit" and
-- "Anil New Credit" as separate entries, and spells the remittance names
-- differently in Section 4 than in Section 8 - both kept as-is rather than
-- tidied, because matching the operator's own list is the point.
--
-- `expenses` is deliberately ONE list shared by Section 4.6 and Section 8.6: the
-- sheet points both at the same validation range, so a category added in either
-- place must appear in both.

CREATE TABLE trial_balance_option (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    list_key    TEXT NOT NULL,      -- 'creditors' | 'expenses' | 'remittance' | 'old_credit' | 'staff'
    value       TEXT NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_by  TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE UNIQUE INDEX idx_tb_option_unique ON trial_balance_option (list_key, value);
CREATE INDEX idx_tb_option_list ON trial_balance_option (list_key, sort_order);

INSERT INTO trial_balance_option (list_key, value, sort_order, created_by) VALUES
    ('creditors',  'Anil/Nani New Credit',              1, 'seed'),
    ('creditors',  'Anil New Credit',                   2, 'seed'),
    ('creditors',  'AirTel Hari New Credit',            3, 'seed'),
    ('creditors',  'Salary Advance Viaj',               4, 'seed'),
    ('creditors',  'Salary Advance Ashok',              5, 'seed'),
    ('creditors',  'Salary Advance Sriharsha',          6, 'seed'),
    ('creditors',  'Salary Advance Ravindra',           7, 'seed'),
    ('creditors',  'Sajja Function Hall - New Credit',  8, 'seed'),

    ('expenses',   'Salaries Mid/End of Month - Total', 1, 'seed'),
    ('expenses',   'Power Bill',                        2, 'seed'),
    ('expenses',   'Unload Beta',                       3, 'seed'),
    ('expenses',   'Salary Advances Total',             4, 'seed'),

    ('remittance', 'Sajja Old Credit Remitted Amt',        1, 'seed'),
    ('remittance', 'Anil/Nani Old Credit Remitted Amt',    2, 'seed'),
    ('remittance', 'AirTel Hari Old Credit Remitted Amt',  3, 'seed'),
    ('remittance', 'AirTel New Credit Remitted Amt',       4, 'seed'),

    ('old_credit', 'Sajja Old Credit Remitted Amt',     1, 'seed'),
    ('old_credit', 'Anil Old Credit Remitted',          2, 'seed'),
    ('old_credit', 'AirTel Hari Old Credit Remitted',   3, 'seed'),
    ('old_credit', 'AirTel New Credit Remitted',        4, 'seed'),

    ('staff',      'Gopi',                              1, 'seed'),
    ('staff',      'Girish',                            2, 'seed'),
    ('staff',      'Sriharsha',                         3, 'seed'),
    ('staff',      'Gopi & Girish',                     4, 'seed'),
    ('staff',      'Girish/Sriharsha',                  5, 'seed');
