# Implementation Map — form → module → files

**Addendum to SDD §5 (Functional Modules → System Mapping).** Where SDD §5 maps
each branded mockup to a production screen, this file adds the *actual file
locations* so a problem report about a form goes straight to the code that owns it.

A designed, print-to-PDF companion of the same material — one page per form, with
sections/fields/formulas — is `module-spec-book.html` in this folder (open in a
browser, then Print → Save as PDF).

Kept in sync by hand. If you add/rename a module file, update the matching row.

## How to use this

1. User reports "X is wrong on the **<form>** screen."
2. Find the form's row below → open the **backend router**, the **frontend screen**,
   and the **tests** listed.
3. Reproduce with the test file (add a failing case), fix, re-run
   `cd backend && pytest` + `cd frontend && npm test`.
4. One module per commit/branch, per the Daily Sales Entry reference pattern.

Paths are relative to the repo root. `SDE` = Daily Sales Entry.

---

## Cross-cutting — touched by every module

| Concern | File |
|---|---|
| Router wiring (add a new module here) | `backend/src/svr_backend/app.py` |
| Server-side RBAC — `require("Manager", "Owner")` etc. | `backend/src/svr_backend/core/rbac.py` |
| Audit log — `record_write(...)` on every write | `backend/src/svr_backend/core/audit.py` |
| Sessions / login token | `backend/src/svr_backend/core/session.py` |
| SQLite connection + `transaction()` | `backend/src/svr_backend/core/db.py` |
| Env-driven config (`SVR_*`) | `backend/src/svr_backend/core/config.py` |
| Migration runner (`svr-migrate`) | `backend/src/svr_backend/migrations/runner.py` |
| Numeric helpers (`parse_amt`, `round4`) | `backend/src/svr_backend/calc/amounts.py` |
| Versioned constants (`system_parameter`) | `backend/src/svr_backend/params.py` |
| 23:59 IST carry-forward job | `backend/src/svr_backend/scheduler.py`, `backend/src/svr_backend/carry_forward.py` |
| Field encryption at rest (Fernet) | `backend/src/svr_backend/core/crypto.py` |
| Email (memory / file / smtp) | `backend/src/svr_backend/core/email.py` |
| Nav list + role gating (**add a screen link here**) | `frontend/src/renderer/app.js` (`MODULES`) |
| Loopback API client | `frontend/src/renderer/lib/api.js` |
| Shared styles / IOCL theme | `frontend/src/renderer/styles/app.css` |
| Electron main + preload bridge | `frontend/src/main/main.js`, `frontend/src/main/preload.js` |
| Playwright backend+static bootstrap | `frontend/tests/global-setup.js`, `frontend/tests/_helpers.js` |
| Foundation schema (users, sessions, rate_master, system_parameter, audit_log, …) | `backend/src/svr_backend/migrations/0001_init.sql` |
| Migration/auth/RBAC/carry-forward tests | `backend/tests/test_migrations.py`, `test_auth_rbac.py`, `test_carry_forward.py` |

---

## Module 1 — Daily Sales Entry  (mockup: `daily_sales_report_branded.html`)

| Part | Path |
|---|---|
| Backend router | `backend/src/svr_backend/api/daily_sales_entry.py` |
| Calculation engine (authoritative) | `backend/src/svr_backend/calc/daily_sales_entry.py` |
| Consumes | `carry_forward.py` (last-reading), `rates.py` (locked Sell rate), `inventory.py` (opening stock) |
| Migration | `0002_daily_sales_entry.sql` |
| Frontend screen | `frontend/src/renderer/screens/daily-sales-entry/{index.html,screen.js}` |
| Renderer calc mirror (UX only) | `frontend/src/renderer/lib/calc-mirror.js` |
| Backend tests | `backend/tests/test_daily_sales_entry_api.py`, `test_calc_daily_sales_entry.py` |
| Playwright | `frontend/tests/daily-sales-entry.spec.js` |
| RBAC | Sales create/edit own · Manager/Owner full incl. delete |
| Skill | `skills/daily-sales-entry/` |
| Gaps | OCR (`/ocr` → 501), Excel import/export (→ 501) |

## Module 2 — Daily Sales Summary  (mockup: `daily_sales_summary_branded.html`)

| Part | Path |
|---|---|
| Backend router | `backend/src/svr_backend/api/daily_sales_summary.py` |
| Combine/derive helper | `backend/src/svr_backend/summary.py` (`build_summary`) |
| Migration | `0003_daily_sales_summary.sql` |
| Frontend screen | `frontend/src/renderer/screens/daily-sales-summary/{index.html,screen.js}` |
| Backend tests | `backend/tests/test_daily_sales_summary_api.py` |
| Playwright | `frontend/tests/daily-sales-summary.spec.js` |
| RBAC | Sales verify own pump only · Manager/Owner full · upload gated on both-verified |

## Module 3 — Rate Master  (mockup: `rate_master_branded.html`)

| Part | Path |
|---|---|
| Backend router | `backend/src/svr_backend/api/rate_master.py` |
| Lookup helper (Buy vs Sell) | `backend/src/svr_backend/rates.py` |
| Table | `rate_master` in `0001_init.sql` (seeded) |
| Frontend screen | `frontend/src/renderer/screens/rate-master/{index.html,screen.js}` |
| Backend tests | `backend/tests/test_rate_master.py` |
| Playwright | `frontend/tests/rate-master.spec.js` |
| RBAC | Sales blocked · Manager view-only · Owner edit (append-only versioning) |

## Module 4 — Inventory Tracking  (mockup: `inventory_tracking_branded.html`)

| Part | Path |
|---|---|
| Backend router | `backend/src/svr_backend/api/inventory.py` |
| Stock-level helper | `backend/src/svr_backend/inventory.py` (`stock_levels`, `on_hand_map`) |
| Migration | `0004_inventory.sql` |
| Frontend screen | `frontend/src/renderer/screens/inventory-tracking/{index.html,screen.js}` |
| Backend tests | `backend/tests/test_inventory_api.py` |
| Playwright | `frontend/tests/inventory-tracking.spec.js` |
| RBAC | Sales no access · Manager/Owner full · reorder-level edit Owner-only |
| Note | feeds Daily Sales Entry oil "Opening Stock" via `inventory.on_hand_map` |

## Module 5 — Manage Users  (mockup: `manage_users_branded.html`)

| Part | Path |
|---|---|
| Backend router | `backend/src/svr_backend/api/users.py` |
| Login-name / projection helper | `backend/src/svr_backend/users.py` |
| Table | `users` in `0001_init.sql` |
| Frontend screen | `frontend/src/renderer/screens/manage-users/{index.html,screen.js}` |
| Backend tests | `backend/tests/test_users_api.py` |
| Playwright | `frontend/tests/manage-users.spec.js` |
| RBAC | Manager/Owner only · last-active-Owner guard · no self-delete |
| Related | reset button → Module 11 |

## Module 6 — Credit / Remittance Master  (mockup: `credit_remittance_master_branded.html`; supersedes retired `new_credit_entry`, `record_repayment`)

| Part | Path |
|---|---|
| Backend router | `backend/src/svr_backend/api/credit_master.py` |
| Migration | `0005_credit_master.sql` |
| Frontend screen | `frontend/src/renderer/screens/credit-remittance-master/{index.html,screen.js}` |
| Backend tests | `backend/tests/test_credit_master_api.py` |
| Playwright | `frontend/tests/credit-remittance-master.spec.js` |
| RBAC | Sales blocked · Manager/Owner full |

## Module 7 — Monthly Expenses  (mockup: `monthly_expenses_branded.html`)

| Part | Path |
|---|---|
| Backend router | `backend/src/svr_backend/api/expenses.py` |
| Migration | `0006_monthly_expenses.sql` (categories seeded) |
| Frontend screen | `frontend/src/renderer/screens/monthly-expenses/{index.html,screen.js}` |
| Backend tests | `backend/tests/test_expenses_api.py` |
| Playwright | `frontend/tests/monthly-expenses.spec.js` |
| RBAC | Sales no access · Manager/Owner full · add-category Owner-only |

## Module 8 — Employee Master + Payroll Run  (mockup: `employee_master_branded.html`)

| Part | Path |
|---|---|
| Backend routers | `backend/src/svr_backend/api/employees.py` — `router` (employees) **and** `payroll_router` (`/payroll-runs`) |
| Encryption | `backend/src/svr_backend/core/crypto.py` (bank account / IFSC / branch) |
| Migration | `0007_employee_master.sql` (employee, payroll_run, payroll_run_line) |
| Frontend screen | `frontend/src/renderer/screens/employee-master/{index.html,screen.js}` |
| Backend tests | `backend/tests/test_employees_api.py` |
| Playwright | `frontend/tests/employee-master.spec.js` |
| RBAC | Sales blocked · Manager/Owner full |
| Gaps | Insurance sections 3–5 (Accidental / Health / Annual Premium Summary) not built |

## Module 9 — Payment Receipt  (mockup: `payment_receipt_branded.html`)

| Part | Path |
|---|---|
| Backend router | `backend/src/svr_backend/api/receipts.py` |
| Consumes | `rates.py` (default Sell rate by fuel) |
| Migration | `0008_payment_receipt.sql` |
| Frontend screen | `frontend/src/renderer/screens/payment-receipt/{index.html,screen.js}` |
| Backend tests | `backend/tests/test_receipts_api.py` |
| Playwright | `frontend/tests/payment-receipt.spec.js` |
| RBAC | Sales/Manager/Owner may issue · delete Manager/Owner only · English-only |

## Module 10 — Yearly Sales Report  (mockup: `yearly_sales_report_branded.html`)

| Part | Path |
|---|---|
| Backend router | `backend/src/svr_backend/api/reports.py` (`/reports/yearly/{fy_start_year}`) |
| Consumes | `daily_sales_entry`, `payroll_run`, `monthly_expense` (live aggregation) |
| Migration | `0009_yearly_report.sql` (per-FY manual figures) |
| Frontend screen | `frontend/src/renderer/screens/yearly-sales-report/{index.html,screen.js}` |
| Backend tests | `backend/tests/test_reports_api.py` |
| Playwright | `frontend/tests/yearly-sales-report.spec.js` |
| RBAC | Sales no access · Manager view · Owner edits COGS + IOCL commission |

## Module 11 — Password Reset + Email  (mockup: `password_reset_branded.html`)

| Part | Path |
|---|---|
| Self-service endpoints | `backend/src/svr_backend/api/auth.py` (`/password-reset/request`, `/confirm`) |
| Admin-initiated | `backend/src/svr_backend/api/users.py` (`POST /users/{id}/reset-password`) |
| Token issue/consume + email body | `backend/src/svr_backend/reset.py` |
| Email backends | `backend/src/svr_backend/core/email.py` |
| Password hashing | `backend/src/svr_backend/core/security.py` |
| **Server-rendered reset page** (email link target) | `backend/src/svr_backend/api/pages.py` (`/password-reset.html`) |
| Migration | `0010_password_reset.sql` |
| Frontend touchpoints | login "Forgot password?" in `frontend/src/renderer/app.js`; reset button in `screens/manage-users/screen.js` |
| Backend tests | `backend/tests/test_password_reset.py` |
| Playwright | `frontend/tests/password-reset.spec.js` |
| Prod config | `SVR_EMAIL_BACKEND=smtp` + `SVR_SMTP_*` + `SVR_APP_BASE_URL` |

## Module 12 — Daily Trial Balance  (mockup: `daily_trial_balance_branded.html`)

| Part | Path |
|---|---|
| Backend router | `backend/src/svr_backend/api/daily_trial_balance.py` |
| Calculation engine (SDD §9) | `backend/src/svr_backend/calc/daily_trial_balance.py` |
| Consumes | `summary.py` (Section 3 consumption), `rates.py` (Buy rate), `params.py` (density deduction) |
| Migration | `0011_daily_trial_balance.sql`, `0012_daily_trial_balance_carry_forward.sql` (ADR-2) |
| Frontend screen | `frontend/src/renderer/screens/daily-trial-balance/{index.html,screen.js}` |
| Backend tests | `backend/tests/test_daily_trial_balance_api.py` |
| Playwright | `frontend/tests/daily-trial-balance.spec.js` |
| RBAC | Sales = maker (`GET`/`PUT`) · Manager/Owner = checker, full + `finalize` (ADR-2, ADR-2-implemented 2026-09-06) |
| Carry-forward | ADR-2, implemented 2026-09-06 in full: `finalize` gates on the previous day being closed, auto-creates + seeds the next day via `prev_trial_balance_id`, and runs the ±₹100 variance/escalation check. Multi-day gap handling (holidays/skipped days) — **RESOLVED with client 2026-09-06, no code change**: sequential one-by-one catch-up is the confirmed final design; see ADR-2 "Point 5". |
| Frontend RBAC | **Closed out 2026-09-07**: `nav.js` widened to show the module to Sales too (maker); the screen itself hides the Close & Sign Off block/fields/button unless `me.role` is Manager/Owner (`canFinalize()`, mirrors `rate-master/screen.js`) and shows a role tag; adds `projected_total`/`reason` finalize inputs and a `carried_from`/`variance_amount`/`variance_reason` display line. Playwright spec rewritten to match; full frontend suite (31/31) verified before push. |
| **Gaps** | Only Sections **1, 3, 6, 7** modelled. Sections 2/4/5/8/9/10/11 live in a `manual_json` blob — **CONFIRMED 2026-09-06 as the final design (SDD ADR-1)**, not pending. Section 6 stock-value litres and Benefit/Loss were cross-checked against AUG11/AUG12/SEP05/SEP06 real workbooks 2026-09-06 and corrected (CLAUDE.md, audit doc) — no longer an open question. No remaining gaps on this module. |

---

## Retired forms (no module — subsumed by Module 6)

| Mockup | Disposition |
|---|---|
| `new_credit_entry_branded.html` | retired → Credit / Remittance Master §1 "New Credit" |
| `record_repayment_branded.html` | retired → Credit / Remittance Master §2 "Remittance" |

## Not a numbered module

| Concern | Where |
|---|---|
| Home Page / navigation landing (SDD §5.2) | login + role-filtered nav shell: `frontend/src/renderer/{index.html,app.js}` |
| Login | same shell + `backend/src/svr_backend/api/auth.py` |
