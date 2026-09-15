-- Posting the Trial Balance's expense, credit and remittance lines out to the
-- master forms, and tracking each line's life afterwards (client, 2026-09-14).
--
-- THE RULE: "Part of the Close and Sign off, all three categories should be
-- posted... Unless posted do not allow Close & Sign Off."
--
-- THE LIFECYCLE, in the client's own description:
--
--   Expenses    posted on the day -> stay visible on the Trial Balance for the
--               rest of the month -> cleared at month end.
--
--   Credits     not posted -> posted -> PAID (when a remittance comes in
--               against them) -> cleared in the first week of the next month.
--               "These are all very short term credits - typically they take
--               today and they pay off the next day or the following day."
--
-- So a line does NOT vanish once it is posted. The operator keeps seeing it,
-- every day, until it is cleared - which is the whole point: an unpaid credit
-- from Tuesday must still be in front of them on Thursday.
--
-- WHY A SEPARATE TABLE AND NOT A FLAG ON THE MANUAL BLOB. Three reasons:
--   * the blob is per-day, and this view deliberately spans days;
--   * a posting has a life of its own after the day closes (paid, cleared),
--     and rewriting a signed-off day's blob to record that would be wrong;
--   * `target_table`/`target_id` is what makes a re-post replace its own rows
--     instead of duplicating - the same reverse-and-reapply rule agreed for the
--     Inventory sync.
--
-- WHAT THIS IS NOT. These lines are already counted in the Trial Balance's own
-- arithmetic, and the client was explicit that "expenses and remittance are not
-- part of the next day accounting". Posting copies them OUT to the master forms
-- for reporting; it never feeds back into any total here and never touches
-- carry-forward.

CREATE TABLE trial_balance_posting (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    shift_date      TEXT NOT NULL,          -- the day the line was entered on
    category        TEXT NOT NULL CHECK (category IN ('expense', 'credit', 'remittance')),
    -- Which block it came from, so a re-post can find its own row again:
    -- 'section4.expenses', 'section8.regular_expenses', 'section3.new_credits',
    -- 'section4.remittance', 'section8.old_credit_collections'.
    source_block    TEXT NOT NULL,
    row_index       INTEGER NOT NULL,
    label           TEXT NOT NULL,          -- the dropdown value, verbatim
    amount          REAL NOT NULL,
    -- 'not_posted' the moment it is seen; 'posted' once it exists in a master
    -- form; 'paid' when a remittance settles a credit; 'cleared' when the month
    -- is tidied up and it drops off the view.
    status          TEXT NOT NULL DEFAULT 'not_posted'
                    CHECK (status IN ('not_posted', 'posted', 'paid', 'cleared')),
    target_table    TEXT,                   -- 'monthly_expense' | 'credit_transaction'
    target_id       INTEGER,
    paid_by_posting INTEGER REFERENCES trial_balance_posting (id),  -- the remittance that settled it
    posted_by       TEXT,
    posted_at       TEXT,
    paid_at         TEXT,
    cleared_by      TEXT,
    cleared_at      TEXT,
    last_updated_by TEXT,
    last_updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- One row per line of a day's block. A correction to that line updates this row
-- rather than adding a second one, which is what keeps a re-post idempotent.
CREATE UNIQUE INDEX idx_tbp_line
    ON trial_balance_posting (shift_date, source_block, row_index);

-- The screen's running view: everything not yet cleared, newest day first.
CREATE INDEX idx_tbp_open ON trial_balance_posting (status, shift_date);
CREATE INDEX idx_tbp_date ON trial_balance_posting (shift_date, category);
