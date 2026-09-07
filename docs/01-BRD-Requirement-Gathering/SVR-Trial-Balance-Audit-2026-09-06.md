# Daily Trial Balance Audit — 2026-09-06

Read-only validation of the client's live Excel workbook (`Trail_balance_SEP062026 1.xlsx`), performed as reference material for the Daily Trial Balance module design (ties into ADR-1 and ADR-2). Scope: the `SEP05` and `SEP06` tabs in detail, then a formula-recompute pass across all 322 daily tabs (`OCT_17_2025` through `SEP06`, Oct 17 2025 – Sep 6 2026).

## Method

Every formula cell in every tab was parsed directly from the underlying XML (not via a live Excel recalculation), recomputed independently from its own precedent cells' cached values, and compared to Excel's own stored result. Cross-sheet carry-forward links were separately checked against the actual immediately-preceding day's tab in workbook order.

## Result: formula integrity

**23,025 formula cells across all 322 daily tabs recompute exactly to their cached values.** No broken formulas, no stale/uncalculated cells, no wrong-cell-reference errors in the arithmetic itself, in over 11 months of daily use.

## Result: SEP05 / SEP06 detail

- Cross-sheet carry-forward (`SEP06!D48 = 'SEP05'!D51`, `SEP06!D75 = 'SEP05'!D79`) correct and consistent.
- Sep 5 cash reconciliation difference: **-₹8,538.43** (breaches the sheet's own ₹100 escalation note), substantially offset in the day's variance-explanation column by a ₹8,525.95 power-bill expense entry, per the client's normal practice of posting recurring bills/salaries/advances through the "Expenses" drop-down (row 53) on the day they're actually paid.
- Sep 6 cash reconciliation difference: +₹21.87, within threshold on its own.
- No calculation defects found in either tab once the normal expense-posting practice above is accounted for.

## Result: two carry-forward failures found across the full history

Both are failures of the **hand-typed cross-sheet reference used to carry a value from one day's tab into the next**, not of the arithmetic:

1. **`SEP02!D96` skips a day.** Formula is `='AUG31'!D78` (₹3,291,666.27) instead of referencing Sep 1's equivalent closing figure (₹1,133,538.58). Produces a misleading ~₹22,538 "Difference – Actual Reported Minus Projected" on Sep 2 that is an artifact of the skipped link, not a real cash variance.
2. **Frozen reference, Jun 6 – Aug 1 (~56 consecutive tabs).** The "Computer Stock Value Margin Yesterday to Today Sale" panel's "Yesterday Stock Value" cell is hardcoded to `='JUN4'!D83` (₹1,614,438.75) on every one of those tabs instead of updating daily — consistent with that day's tab being copied forward repeatedly without the reference being updated. Confirmed not to feed into the main reported Trial Balance (Sections 6–8 equivalent), so headline totals are unaffected, but that panel's own "Balance / Close Number" check was non-functional for two months.

## Implication for the application design

Both failures are the direct motivation for **ADR-2** (`docs/02-System-Design-Architecture/ADR-2-Daily-Trial-Balance-Close-and-Carry-Forward.md`): carry-forward should be a system-generated link created at the moment a day is Closed & Signed Off, never a value a person re-types per day. See that document for the full decision and its consequences for the backend schema.

## Addendum — AUG11/AUG12 workbook audit and calc engine fix (2026-09-06)

Extended the same method to `GAS_STATION_AUG11_AUG12.xlsx` (`AUG11`/`AUG12` tabs) to settle the Section 6 stock-value sign-convention question CLAUDE.md had flagged as unresolved. This resolved as a genuine formula bug, not a sign ambiguity — **confirmed against four independent real days (AUG11, AUG12, SEP05, SEP06; SEP06 explicitly client-validated)** and fixed in `backend/src/svr_backend/calc/daily_trial_balance.py`:

1. **Section 6 Stock Value litres.** The calc engine computed `stock_ltrs = diff − consumption` (per an ambiguous BRD session-log note; the SDD's prose implied the opposite sign). Neither matches reality. In every real tab checked, the Stock Value section's Ltrs cell is a plain `=C3`/`=C4` formula — **today's current IOCL reading, taken verbatim, with no diff/consumption arithmetic at all**:

   | Day | Fuel | Old formula (`diff − cons`) | Real value | = current reading? |
   |---|---|---|---|---|
   | AUG11 | Diesel | 504 − 519.11 = **−15.11** | 6,678 | ✓ |
   | AUG12 | Diesel | 1285 − 1317.52 = **−32.52** | 5,393 | ✓ |
   | SEP06 | Diesel | 549 − 561.71 = **−12.71** | 9,119 | ✓ |

   The old formula produced negative litres — physically meaningless — and fed directly into `stock_value_total` → `trial_balance_7_2` → the grand total `trial_balance_7_3`. Using SEP06's real numbers, the bug reported Diesel stock as **-₹1,305.95** instead of the correct **₹936,977.25**. **Fixed**: `stock_ltrs` is now `current`, verbatim, computed independently of consumption (previously it was skipped entirely if Section 3 hadn't posted yet, even though the real formula doesn't need consumption at all).

2. **Section 1 Benefit/Loss.** Coded as `cons + diff`; real formula (confirmed on both AUG11 and AUG12: `G3 = E3 + F3`) is `cons + computer_pump_diff`. Lower severity — traced and confirmed nothing downstream (the actual Margin/Profit figure) is derived from this field, so it didn't corrupt any totals, but it displayed a wrong number. **Fixed**.

Everything else checked (`diff = yesterday − current`, `computer_pump_diff = cons − diff`, `deduct_testing = cons − testing`) matched real data exactly across all four days and needed no change.

**Verification**: the corrected formula reproduces SEP06's real Section 6 figures exactly — ₹936,977.25 (HS) + ₹1,140,483.08 (MS) = ₹2,077,460.33 total, matching the client-validated sheet. `backend/tests/test_daily_trial_balance_api.py` was updated to match the corrected expected values.
