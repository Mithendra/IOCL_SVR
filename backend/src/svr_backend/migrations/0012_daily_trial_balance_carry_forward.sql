-- 0012_daily_trial_balance_carry_forward.sql - ADR-2: Daily Trial Balance Close &
-- Sign-Off carry-forward.
--
-- Replaces the legacy workbook's hand-typed cross-sheet carry-forward (a human-typed
-- reference like ='SEP05'!D51, which caused two real bugs across 11 months of daily
-- use - see docs/01-BRD-Requirement-Gathering/SVR-Trial-Balance-Audit-2026-09-06.md)
-- with a system-generated link to the prior *finalized* row, so a skipped day fails
-- loudly instead of silently linking past it.

-- The prior Trial Balance row this one carried its opening values forward from.
-- NULL for the first-ever row in the system, or when created directly with no
-- finalized predecessor. Set once at creation, never updated afterward.
ALTER TABLE daily_trial_balance
    ADD COLUMN prev_trial_balance_id INTEGER REFERENCES daily_trial_balance(id);

-- Escalation check at Close & Sign Off (ADR-2 Decision step 1; threshold is the
-- existing 'trial_balance_alert_threshold' system_parameter, seeded +/-Rs100 in
-- 0001_init.sql). NULL when no projected_total was supplied to compare against.
ALTER TABLE daily_trial_balance ADD COLUMN variance_amount REAL;
ALTER TABLE daily_trial_balance ADD COLUMN variance_reason TEXT;

CREATE INDEX idx_dtb_prev ON daily_trial_balance (prev_trial_balance_id);
