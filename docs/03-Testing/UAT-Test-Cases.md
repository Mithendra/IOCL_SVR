# SVR IOCL Station — UAT / Acceptance Test Cases

**Purpose:** the checklist the station runs over **2–3 days on the live PC** before
going to production. It covers deployment health, every form, the cross-module
flows, and role-based access. Nothing here needs a developer — a Manager and the
Owner can work through it.

**Related docs:** deployment steps in [`../../HANDOVER.md`](../../HANDOVER.md) §5;
form → code map in
[`../02-System-Design-Architecture/IMPLEMENTATION-MAP.md`](../02-System-Design-Architecture/IMPLEMENTATION-MAP.md);
per-form field reference in
[`../02-System-Design-Architecture/module-spec-book.html`](../02-System-Design-Architecture/module-spec-book.html).

## How to use this

- Run in order. Section A first (if the machine isn't healthy, nothing else matters).
- Mark each row **Pass / Fail / N/A** in the Result column and initial + date it.
- On a **Fail**, note exactly what you saw (screenshot the screen and the
  `C:\ProgramData\SVR-IOCL\logs\` file if it's an error) and stop that module —
  don't work around it.
- "N/A" is expected for anything marked *(stubbed)* below — OCR, Excel import/export,
  and full backup/restore are not in this build.

## Environment

| | |
|---|---|
| Machine | the actual production PC (post-install, per HANDOVER §5) |
| Backend | `http://127.0.0.1:8756` — the `SVR-IOCL-Backend` service |
| Data | `C:\ProgramData\SVR-IOCL\svr.sqlite` |
| Test accounts | create **one real account per role** in Manage Users first (§B‑5). Do **not** UAT on the `demo1234` seed users. |
| Roles | `Sales`, `Manager`, `Owner` — exactly three |
| Financial year | April–March |
| Timezone for the nightly rollover | `Asia/Kolkata` (23:59 IST), regardless of the PC's clock zone |

---

## Section A — Deployment & infrastructure

| ID | Check | Steps | Expected | Result |
|---|---|---|---|---|
| A‑1 | Services running | `Get-Service SVR-IOCL-Backend, SVR-IOCL-Scheduler` | Both `Running`, StartType `Automatic` | |
| A‑2 | Survives reboot | Restart the PC; before logging into the app, re-run A‑1 | Both services `Running` again with no manual action; the app auto-launches from the Startup shortcut | |
| A‑3 | API health | Browser / PowerShell: `http://127.0.0.1:8756/health` | `{"status":"ok","version":"…"}` | |
| A‑4 | DB + logs present | Look in `C:\ProgramData\SVR-IOCL\` | `svr.sqlite` exists; `logs\` has the 6 component files; `backend-service.log` shows "Application startup complete" and no repeating tracebacks | |
| A‑5 | Config persisted | `[Environment]::GetEnvironmentVariable('SVR_FIELD_KEY','Machine')` | A long value is set (needed so encrypted employee bank fields stay readable) | |
| A‑6 | Login works | Open the app, sign in as the Owner test account | Sidebar loads; the header shows the SVR / IndianOil lockup | |
| A‑7 | Nightly carry-forward | Enter a Daily Sales Entry today (§B‑1); next morning open a new Daily Sales Entry for the same pump | Yesterday's **Current Reading** appears as today's **Last Shift Reading**, locked, stamped from the 23:59 IST job. A skipped day (holiday) carries from the last day that had a reading. | |
| A‑8 | Nightly DB backup | Morning after A‑7, look in `C:\ProgramData\SVR-IOCL\backups\` | A dated `svr-YYYYMMDD.sqlite` from the 00:15 IST job | |
| A‑9 | Audit trail | After any save in §B, check the record's "Last Updated By / Last Updated" | Shows the account that saved and a timestamp; every save is recorded | |

> Full application backup to USB + restore is a **future module** — not in this build, skip.

---

## Section B — Per-form test cases

### B‑1  Daily Sales Entry

| ID | Scenario | Role | Steps | Expected | Result |
|---|---|---|---|---|---|
| 1.1 | Reach the form | Sales | Sidebar → Daily Sales Entry | Opens; pump + shift date selectable | |
| 1.2 | Carried reading is locked | Sales | Start a new entry for a pump | Last Shift Reading + Rate fields are pre-filled and **read-only** | |
| 1.3 | Gas amount uses **Sell Rate** | Sales | Enter a Current Reading; let Amount compute | Amount = (Current − Last) × **Sell Rate** from Rate Master — never the Buy Rate | |
| 1.4 | Backend is authoritative on save | Sales | Note the on-screen totals, then Save | After Save the figures are the backend's recomputed values; a tampered field is corrected, not trusted | |
| 1.5 | Opening stock comes from Inventory | Sales | Check the Oil Sale(s) opening-stock column | Matches current Inventory Tracking stock for those 5 SKUs at entry time | |
| 1.6 | One pump per submission | Sales | Save a submission | It covers only the selected pump; the other pump is a separate submission | |
| 1.7 | OCR / Excel import *(stubbed)* | Sales | Click Scan / Upload (OCR) or Import from Excel | Shows a "not yet available" message; no crash | N/A |
| 1.8 | Re-open after save | Sales | Navigate away and back to the same date/pump | Saved values reload; Last Updated By shows your account | |

### B‑2  Daily Sales Summary

| ID | Scenario | Role | Steps | Expected | Result |
|---|---|---|---|---|---|
| 2.1 | Combines both pumps | Manager | With both pump submissions saved for a date, open Daily Sales Summary | Both pumps' figures appear; the combined total = sum of the two | |
| 2.2 | Per-pump verification | Manager | Set each pump's Verified status | Independent per pump; a corrected entry can be marked "Verified – Corrections Made" | |
| 2.3 | Upload gate | Manager | Try "Upload to Daily Trial Balance" with only one pump verified | **Blocked** with a clear message; allowed only when **both** pumps are verified | |
| 2.4 | Prepared-by is auto | Manager | Save | "Prepared By" = the logged-in account, not typed by hand | |
| 2.5 | Feeds Trial Balance §3 | Manager | After a successful upload, open Daily Trial Balance | Its Section 3 (Day Sales Report) shows this combined, verified data, read-only | |

### B‑3  Rate Master

| ID | Scenario | Role | Steps | Expected | Result |
|---|---|---|---|---|---|
| 3.1 | Sales blocked | Sales | Look for Rate Master in the sidebar | Not present for Sales | |
| 3.2 | Manager view-only | Manager | Open Rate Master | Can see current Buy/Sell rates and history; **cannot** edit or push | |
| 3.3 | Owner posts a new rate | Owner | Push a new HS Sell Rate | Saved; appears at the top of the change-log with who/when | |
| 3.4 | Append-only history | Owner | Review the change-log | Prior rates are retained, not overwritten | |
| 3.5 | New rate flows forward | Owner→Sales | After 3.3, start a new Daily Sales Entry | The new Sell Rate is what the gas rows use; an entry created *before* the change keeps its original locked rate | |

### B‑4  Inventory Tracking

| ID | Scenario | Role | Steps | Expected | Result |
|---|---|---|---|---|---|
| 4.1 | Sales blocked | Sales | Sidebar | Not present for Sales | |
| 4.2 | Five SKUs | Manager | Open Inventory Tracking | Exactly the 5 oil SKUs listed with current stock | |
| 4.3 | Record a restock | Manager | Add a restock entry | Stock increases by that amount; the restock is logged | |
| 4.4 | Low-stock status | Manager | Set a SKU's stock below its reorder level | Status flips to low-stock / reorder | |
| 4.5 | Owner edits reorder level | Owner | Change a Reorder Level inline | Saves; low-stock threshold updates accordingly | |
| 4.6 | Feeds Daily Sales Entry | Manager→Sales | Note a SKU's stock, then open a new Daily Sales Entry | That SKU's opening stock in the entry matches | |

### B‑5  Manage Users

| ID | Scenario | Role | Steps | Expected | Result |
|---|---|---|---|---|---|
| 5.1 | Sales blocked | Sales | Sidebar | Not present for Sales | |
| 5.2 | Create the three UAT accounts | Owner | Add one Sales, one Manager, one Owner account | Created; login name derived; a password-reset link is issued (see B‑11) | |
| 5.3 | Role assignment | Owner | Set each account's role | Only `Sales` / `Manager` / `Owner` are selectable | |
| 5.4 | Per-user 2FA toggle | Owner | Toggle 2FA on an account | Saves the preference | |
| 5.5 | Last-Owner guard | Owner | Try to disable or downgrade the only Owner | Blocked — the system keeps at least one active Owner | |

### B‑6  Credit / Remittance Master

| ID | Scenario | Role | Steps | Expected | Result |
|---|---|---|---|---|---|
| 6.1 | Sales blocked | Sales | Sidebar | Not present for Sales | |
| 6.2 | Add a credit | Manager | Record a new credit for a creditor | Appears in the ledger; creditor's outstanding balance goes up | |
| 6.3 | Record a remittance | Manager | Record a repayment against that creditor | Same ledger; outstanding balance goes down | |
| 6.4 | Creditor Balance Summary | Manager | Open the grouped summary | Grouped by creditor, outstanding shown, creditors with a pending balance listed first | |

### B‑7  Monthly Expenses

| ID | Scenario | Role | Steps | Expected | Result |
|---|---|---|---|---|---|
| 7.1 | Sales blocked | Sales | Sidebar | Not present for Sales | |
| 7.2 | Add payroll + operational rows | Manager | Add one of each kind, with dates | Both saved; monthly subtotals update | |
| 7.3 | Add a new category | Manager | "+ New Category", then use it on a row | The new category is immediately usable and appears in filters | |
| 7.4 | Date-range + category report | Manager | Run the report for a range, filtered to one category | Isolates that category's total for the range; matches by the visible category name (works for both the original hardcoded rows and newly-added rows) | |

### B‑8  Employee Master + Payroll Run

| ID | Scenario | Role | Steps | Expected | Result |
|---|---|---|---|---|---|
| 8.1 | Sales blocked | Sales | Sidebar | Not present for Sales | |
| 8.2 | Add an employee with bank data | Manager | Create an employee, enter bank account + IFSC | Saved | |
| 8.3 | Bank data masked in the list | Manager | Return to the employee list | Bank account / IFSC shown masked (e.g. `****1234`), not in full | |
| 8.4 | Revealed only on edit | Manager | Open that employee for edit | Full value visible in the edit form only | |
| 8.5 | Payroll run | Manager | Run a bi-weekly payroll | Gross / net computed per employee | |
| 8.6 | Unknown employee rejected | Manager | Attempt payroll for an id that doesn't exist | Rejected with an error, nothing saved | |

### B‑9  Payment Receipt

| ID | Scenario | Role | Steps | Expected | Result |
|---|---|---|---|---|---|
| 9.1 | Sales can issue | Sales | Open Payment Receipt, issue a Diesel receipt | Rate defaults from Rate Master; total = qty × rate; receipt saved | |
| 9.2 | Sales cannot delete | Sales | Try to delete a receipt | Not allowed for Sales | |
| 9.3 | Manager/Owner can delete | Manager | Delete a receipt | Allowed; deletion is audited | |
| 9.4 | Rate follows Rate Master | Owner→Sales | Change the Sell Rate in Rate Master, issue a new receipt | New receipt uses the new rate | |

### B‑10  Yearly Sales Report

| ID | Scenario | Role | Steps | Expected | Result |
|---|---|---|---|---|---|
| 10.1 | Sales blocked | Sales | Sidebar | Not present for Sales | |
| 10.2 | Manager view-only | Manager | Open the FY report | Revenue / salaries / opex shown, computed live; the CA disclaimer is present; cannot edit COGS / commission | |
| 10.3 | Owner enters COGS + commission | Owner | Enter COGS and IOCL commission for the FY | Saved; the summary recalculates immediately | |
| 10.4 | FY window is Apr–Mar | Owner | Check which dated records roll into the FY total | Only April 1 – March 31 of that FY | |
| 10.5 | Repairs total workflow | Owner | Run Monthly Expenses' range report for the full FY filtered to "Repairs", read the total, type it into the Yearly Report field | The field states it's a manual entry from that report; value saves | |

### B‑11  Password Reset + Email

| ID | Scenario | Role | Steps | Expected | Result |
|---|---|---|---|---|---|
| 11.1 | Self-service request | any | On the login screen → "Forgot password?", enter a known login/email | Non-committal confirmation (no "account exists" leak); a reset email is sent | |
| 11.2 | Unknown account | — | Repeat with a made-up identifier | Same non-committal message — no enumeration | |
| 11.3 | Admin-initiated | Owner | In Manage Users, trigger a reset for an account | Reset link emailed to that user | |
| 11.4 | Complete the reset | user | Open the emailed link, set a new password | Backend-served reset page; link is **single-use** and time-limited; after setting, the user can sign in with the new password; the old link no longer works | |
| 11.5 | Email delivery | Owner | Confirm the SMTP settings are real (not the dev `memory`/`file` backend) for production | Real emails arrive; if not configured, this is a **go-live blocker** | |

### B‑12  Daily Trial Balance  *(maker–checker, ADR-2 — confirmed complete 2026-09-07)*

| ID | Scenario | Role | Steps | Expected | Result |
|---|---|---|---|---|---|
| 12.1 | Sales is the maker | Sales | Sidebar, then open the module | **Present** for Sales (widened 2026-09-06 for ADR-2); can enter Section 1 inputs and Save; the "Close & Sign Off" block/fields/button are hidden entirely — Sales cannot finalize | |
| 12.2 | Section 3 is pulled, read-only | Manager | After a Daily Sales Summary upload (2.3/2.5), open Trial Balance | Section 3 shows that combined verified data and cannot be hand-edited | |
| 12.3 | Sections 1 / 6 / 7 compute | Manager | Enter Section 1 inputs | Computed columns fill; **Stock Value uses the Buy Rate** (not the Sell Rate that Daily Sales Entry uses) | |
| 12.4 | Sections 2/4/5/8–11 manual | Manager | Enter values in the manual-JSON block | Accepted and round-trips as-is — this is the **confirmed final design (SDD ADR-1, "Manual Blob")**, not an interim state; no computed roll-up is expected here | |
| 12.5 | Close & Sign Off (checker only) | Manager or Owner | Finalize the day | Record locks against further edits; the checker-only fields (**Today's Projected Trial Balance**, optional; **Reason**, required only on breach) appear only for Manager/Owner, never for Sales | |
| 12.6 | Section 6 sign / density check | — | Cross-check the Section 6 litres sign and the density deduction against AUG11/AUG12/SEP05/SEP06 | **RESOLVED 2026-09-06** — Section 6 Stock Value litres corrected to the raw IOCL reading (was wrongly `diff − consumption`), Section 1 Benefit/Loss corrected to use `computer_pump_diff`; both fixed in `calc/daily_trial_balance.py` and covered by `test_daily_trial_balance_api.py`. Full evidence: `SVR-Trial-Balance-Audit-2026-09-06.md`. No longer an open reconciliation — re-run this case only as a regression check. | |
| 12.7 | Cannot skip an unclosed day | Sales or Manager | With date D open (not finalized), try to open/save date D+2 | Refused — the gate only allows the next date once the earlier one is Closed & Signed Off | |
| 12.8 | Auto-carry-forward | Manager or Owner | Close & Sign Off date D | Date D+1's draft is auto-created and seeded from D's own **Reported** (not Projected) values via a system FK — no hand-typed date/cell reference anywhere; opening D+1 shows "Carried forward from D" | |
| 12.9 | Variance/escalation gate | Manager or Owner | Enter a Projected total that differs from the Actual Reported figure by more than ±₹100, then Close & Sign Off with no Reason | Refused with a message naming the exact variance; entering a Reason allows it through. A difference within ±₹100 needs no reason. | |

---

## Section C — Cross-module flows

| ID | Flow | Steps | Expected | Result |
|---|---|---|---|---|
| C‑1 | Rate → Entry lock | Owner posts a new Sell Rate → Sales creates a new Daily Sales Entry → Owner posts another rate → open the earlier entry | Each entry keeps the rate that was effective when it was created | |
| C‑2 | Entry → Summary → Trial Balance | Both pumps' Daily Sales Entry for a date → verify both in Daily Sales Summary → upload → Daily Trial Balance §3 | The same numbers flow end-to-end unchanged; upload blocked until both verified | |
| C‑3 | Inventory → Entry | Record a restock → new Daily Sales Entry | Opening stock reflects the restock | |
| C‑4 | Expenses → Yearly Report | Enter "Repairs" rows across the FY → run the range+category report → enter the total in Yearly Sales Report | Totals agree | |
| C‑5 | Carry-forward chain | Day 1 entry → next day → skip a day → day after | Each day's Last Shift Reading = the previous *entered* day's Current Reading, set at 23:59 IST | |
| C‑6 | Sell Rate vs Buy Rate | Compare the Rate used on a Daily Sales Entry gas row vs the Stock Value rate on the same day's Daily Trial Balance §1 | Entry = Sell Rate; Trial Balance Stock Value = Buy Rate | |

---

## Section D — Role-based access (server-side)

For each row, sign in as the role and confirm both the **UI** hides it **and** a
direct save is refused (RBAC is enforced on the backend, not just the screen).

| Module | Sales | Manager | Owner |
|---|---|---|---|
| Daily Sales Entry | create/save | view/save | view/save |
| Daily Sales Summary | view | view + verify + upload | same |
| Daily Trial Balance | enter/save (maker) | enter/save + Close & Sign Off (checker) | same |
| Rate Master | none | **view-only** | full edit + push |
| Inventory Tracking | none | edit | edit + reorder levels |
| Manage Users | none | user CRUD | user CRUD (+ last-Owner guard) |
| Credit / Remittance Master | none | full | full |
| Monthly Expenses | none | full | full |
| Employee Master / Payroll | none | full | full |
| Payment Receipt | **issue only** | issue + delete | issue + delete |
| Yearly Sales Report | none | **view-only** | enter COGS / commission |

| ID | Check | Result |
|---|---|---|
| D‑1 | Sales sees only: Daily Sales Entry, Daily Sales Summary, Payment Receipt, Daily Trial Balance (maker: enter/save, no Close & Sign Off) | |
| D‑2 | Manager sees everything except the Owner-only edit rights above | |
| D‑3 | Owner sees everything | |
| D‑4 | A blocked save, attempted directly, is refused by the backend (not only hidden in the UI) | |

---

## Go-live blockers (must all be Pass before production)

- [ ] A‑1 … A‑9 all Pass
- [ ] B‑11.5 — real SMTP configured, reset emails actually arrive
- [ ] A‑5 — `SVR_FIELD_KEY` set (or encrypted employee data will not survive a restart)
- [ ] C‑2 and C‑6 — the money numbers flow correctly and Sell/Buy rate are used in the right places
- [x] 12.6 — Section 6 sign / density deduction reconciled against the workbooks — **done 2026-09-06**, see `SVR-Trial-Balance-Audit-2026-09-06.md`

## Sign-off

| Role | Name | Date | Result (Pass / Pass-with-notes / Fail) | Notes |
|---|---|---|---|---|
| Manager | | | | |
| Owner | | | | |
