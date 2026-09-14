-- Trial Balance escalation threshold is Rs 50, not Rs 100 (client, 2026-09-13).
--
-- 0001_init.sql seeded 'trial_balance_alert_threshold' at 100 from SDD 9 row 8,
-- and nothing has changed it since. Close & Sign Off therefore accepted a
-- variance anywhere between 50 and 100 WITHOUT asking for a reason - the check
-- in api/daily_trial_balance.py finalize() reads this parameter and only demands
-- a reason once abs(variance) exceeds it.
--
-- The client's own checklist has said Rs 50 all along; the figure was confirmed
-- again on 2026-09-13 ("Anything 50 is fine"). Their workbook's printed notes at
-- E53, E86 and E95 still read "Anything Above Rs 100 Call/inform mgmt
-- immediately" - those are stale text in the sheet, not the rule, and the
-- handover documents already tell the station to go by Rs 50.
--
-- Effective 2026-09-13, the date it was confirmed. system_parameter is
-- append-only by effective_date and get_param() resolves the value in force on
-- a given shift_date, so days already closed under the 100 threshold keep the
-- variance decision they were signed off under - re-opening an August day does
-- not retroactively demand a reason it was never asked for.

INSERT INTO system_parameter (name, value, effective_date, updated_by)
VALUES ('trial_balance_alert_threshold', 50, '2026-09-13', 'client-confirmed-2026-09-13');
