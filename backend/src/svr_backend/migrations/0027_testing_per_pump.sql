-- Testing is 10 litres PER PUMP (client, 2026-09-14).
--
-- Their words, and the whole rule:
--
--     "one pump will have a 10 litre testing, two pumps means 20 litre testing.
--      Only if the pump is in repair we cannot test anything. In all other cases
--      there will be a 10 litre testing for each pump."
--
--     "if the pump is under repair the pump meter will not run and we don't
--      submit. In all other cases we submit. You take whatever we submit - not
--      based on the status."
--
-- So the deduction counts SUBMISSIONS. A pump out of service is not there to
-- count; one whose salesman was off submits like any other day.
--
--     both pumps submit     20 litres
--     one pump submits      10 litres
--
-- The Trial Balance deducts separately from diesel and from petrol (G3 and G4),
-- so each pump's 10 litres splits across its two nozzles - which is why the
-- station's SEP12 tab reads '=E3-5' and '=E4-5' on a one-pump day, and why the
-- Section 9 ledger carried 10 per fuel while both pumps were running.
--
-- `testing_density_deduction` stops being the input and survives only as the
-- fallback for a day with nothing submitted. Effective 2026-08-01, back to the
-- seed's own date, because the derivation reproduces the old figures: a two-pump
-- day computed 10 per fuel before and computes 10 now, so no closed day moves.

INSERT INTO system_parameter (name, value, effective_date, updated_by)
VALUES ('testing_litres_per_pump', 10, '2026-08-01', 'client-confirmed-2026-09-14');
