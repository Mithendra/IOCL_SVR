# CLAUDE.md — SVR Indian Oil Service Station

Repo-wide guidance for AI-assisted development. The authoritative product spec is
`docs/02-System-Design-Architecture/` (SDD); the requirement history is
`docs/01-BRD-Requirement-Gathering/`.

**When a form/screen misbehaves, start at
`docs/02-System-Design-Architecture/IMPLEMENTATION-MAP.md`** — it maps every form to
its exact backend router, calc engine, migration, frontend screen, and tests. One
module per fix, per the Daily Sales Entry reference pattern.

## Model & workflow

- **Model:** Claude Sonnet 5 (cost-effective) for all AI-assisted work in this repo
  (BRD §1).
- **Plan Mode by default** for any change that touches more than 2–3 files or a
  shared business formula (SDD §15). Formula dependencies cross module boundaries —
  a change to the Section 1 testing/density deduction moves Margin, Margin Total,
  and Total Sale Amt several sections away.
- **Verify every formula against real data** in
  `docs/01-BRD-Requirement-Gathering/*.xlsx` (the AUG11/AUG12 filled workbooks)
  before calling it correct. The design was built this way for 100+ sessions;
  keep the discipline.

## Non-negotiable conventions (from the SDD)

| Rule | Where |
|---|---|
| Daily Sales Entry gas rows use **Sell Rate**, never Buy Rate. Trial Balance Stock Value uses **Buy Rate**. | SDD §9 rows 3 & 6 |
| Last Shift Reading carries forward at **23:59 IST — `Asia/Kolkata` explicitly**, never the host tz. Gap days skip back to the last day with a reading; a missed night is caught up on startup; post-rollover edits need manual re-sync (no auto-correct). | SDD §7.7 |
| The **backend calculation engine is authoritative** on every save. Any renderer-side calc (`frontend/src/renderer/lib/calc-mirror.js`) is a responsive-UX mirror only and must stay in step with `backend/src/svr_backend/calc/daily_sales_entry.py`. | SDD §7.3, §6.4 |
| **Server-side RBAC on every write**, independent of the UI (`backend/src/svr_backend/core/rbac.py` `require(*roles)`). Roles are exactly `Sales`, `Manager`, `Owner`. | SDD §4.1–4.3 |
| **Human review before save** on every non-manual entry path (OCR, Excel import): recompute and flag mismatches, never silently trust. | SDD ADR-5 |
| **Audit everything**: `last_updated_by` / `last_updated_at` on every table + an `audit_log` row per write, via `core/audit.record_write`. Client called this non-negotiable. | SDD §13.4 |
| Frequently-revised constants live in `system_parameter` (versioned, Owner-editable), not in code. | SDD ADR-3 |

## Layout

- `backend/` — Python. FastAPI loopback API (`127.0.0.1` only), calc engine, RBAC,
  audit, SQL migrations, APScheduler. Console scripts: `svr-migrate`,
  `svr-backend`, `svr-scheduler`.
- `frontend/` — ElectronJS. `src/main/` (main + preload bridge, no Node in the
  renderer), `src/renderer/` (screens ported from the `docs` mockups),
  `tests/` (Playwright: page-mode + one `_electron` smoke).
- `installer/` — Windows installer. `build-all.ps1` = PyInstaller freeze of the
  backend (`backend/packaging/`) + electron-builder NSIS; `first-run.ps1` /
  `uninstall.ps1` (invoked elevated from `frontend/build/installer.nsh`) register /
  remove the two Windows Services, run migrations, set machine-wide `SVR_*` config.
- `skills/` — Agent Skills. `daily-sales-entry/` exists; see TODO below.

## Open items (SDD §19 — confirm with the client before locking in)

- ~~**Electron as a Windows Service vs. per-user startup item** (§19 item 23).~~
  **CONFIRMED with client 2026-09-06 (final).** The real requirement was: after any
  reboot or power-cut, the app must come up with zero human action. A literal NT
  service can't render a GUI (Session 0 isolation), so that was never the mechanism
  — the current design (Backend + Scheduler as Windows Services, Electron on a
  per-user Startup-folder shortcut) is the correct one, **unchanged**. Client
  confirmed 2026-09-06 that the reboot test already on file
  (`HANDOVER.md` §5.6, 2026-09-04) covers exactly this: after restarting the testing
  PC, both services and the Electron app came up on their own with no manual
  intervention. **No installer change needed.**
  One deployment note, not a code task: `installer/first-run.ps1` itself doesn't
  configure Windows auto-logon, so whatever let the *testing* PC's Windows session
  start unattended (auto-logon or a passwordless local account, most likely) should
  be set up the same way on each actual *station* PC at install time — that's a
  one-time Windows-account step for whoever deploys the machine, not something the
  app can do for itself.
- ~~**Retired Administrator role** → assumed folded into Manager (§19 item 25).~~
  **CONFIRMED with client 2026-09-06**: exactly three roles, final —
  `ROLES = ("Sales", "Manager", "Owner")` in `backend/src/svr_backend/core/rbac.py`
  is correct as built. No fourth role exists anywhere in the schema, seed data, or
  RBAC checks, so this required no code change. Revisit only if the client later
  asks for a distinct fourth role (that would mean a new permission matrix and a
  pass over every `require(...)` call site).
- ~~**Trial Balance normalization / canonical source-of-truth** (ADR-1, §8.5).~~
  **CONFIRMED with client 2026-09-06: Manual Blob.** SDD/ADR-1 Sections **2, 4, 5,
  8, 9, 10, 11** (Load/Unload Details, Daily Cash & Bank Balances, Cash/Book Value
  Reconciliation, Trial Balance–Projected, Daily Management Reporting, Daily Mgr
  Calculation, Old/New Credit Sales Details — SDD/ADR-1's own section numbers, which
  no longer match the live workbook's printed section labels; current row numbers
  for each, in the live SEP06 tab, are recorded in
  `docs/01-BRD-Requirement-Gathering/SVR-Trial-Balance-Audit-2026-09-06.md`
  (second addendum)) stay as the free-form `manual_json` blob already implemented
  (`TrialBalanceUpsert.manual: dict`, round-trip covered by
  `test_manual_blob_round_trips`). **No code change required** — this is the final
  design, not an interim one; computed rollups for these sections are out of scope
  unless the client asks again later for a specific section. Sections **1, 3, 6, 7**
  remain the only server-computed sections (SDD §9 formulas; Section 3 pulled
  read-only from Daily Sales Summary).
  ~~Also: the Section 6 stock-value litres sign (`diff − consumption`) ... not yet
  cross-checked against the AUG11/AUG12 workbooks~~ — **RESOLVED 2026-09-06**: this
  was a genuine formula bug, not a sign ambiguity. Cross-checked against AUG11,
  AUG12, SEP05, and SEP06 real data (SEP06 client-validated); Section 6 Stock Value
  litres is the current IOCL reading verbatim, not `diff − consumption` (which
  produced negative litres and corrupted the Section 7 grand total). A second,
  lower-severity mismatch in Section 1's Benefit/Loss (`cons + diff` vs the correct
  `cons + computer_pump_diff`) was also found and fixed. Both fixes are applied in
  `backend/src/svr_backend/calc/daily_trial_balance.py` and
  `backend/tests/test_daily_trial_balance_api.py`; full evidence in
  `docs/01-BRD-Requirement-Gathering/SVR-Trial-Balance-Audit-2026-09-06.md`
  (Addendum). The density-deduction question in the original wording above did not
  surface as a separate issue — `deduct_testing = cons − testing` matched real data
  exactly as already coded.
- ~~**Rate Master effective-dating / historical rate freezing** (§19 item 7).~~
  **CONFIRMED with client 2026-09-06**: rates change rarely (client: "hardly
  changes twice a year") and are entered manually by the Owner; from the
  effective date forward, the new rate flows into Daily Sales Entry and Daily
  Trial Balance automatically — this is exactly what's already built, no code
  change needed. `rate_master` is append-only by `effective_date`
  (`api/rate_master.py`), and `latest_effective_rates(conn, as_of)`
  (`rates.py`) resolves the rate in force on a given date rather than just the
  newest one ever entered. Daily Trial Balance calls this with
  `as_of=shift_date` (the record's own date), so re-opening an old Trial Balance
  still uses the Buy Rate that was active back then, never today's. Daily Sales
  Entry additionally locks its effective Sell Rate onto the record at creation
  time, so a historical entry's numbers can't shift even if the rate history
  changes later. Covered by `backend/tests/test_rate_master.py`.
- ~~**Daily Trial Balance close & carry-forward**~~ — see
  `docs/02-System-Design-Architecture/ADR-2-Daily-Trial-Balance-Close-and-Carry-Forward.md`.
  CONFIRMED 2026-09-06 and **IMPLEMENTED 2026-09-06, in full**: `finalize_trial_balance` now
  gates on the previous day being closed, auto-creates + seeds the next day's draft
  via a real FK (`prev_trial_balance_id`, migration `0012`), and runs the
  ±₹100 variance/escalation check (reason required on breach). RBAC opened up —
  Sales (maker) now has `GET`/`PUT` access; `finalize` (checker) stays
  Manager/Owner. Full backend suite verified green (94 passed) before push.
  Multi-day gap handling (holidays/skipped days) — **RESOLVED with client
  2026-09-06, no code change needed**: confirmed the desired behavior is exactly
  what's already built — on a gap, the maker fills each missed day in sequence
  before reaching today; there is no bulk/skip-ahead close. See the ADR's
  "Point 5" note for the client's own words.
  **Frontend closed out 2026-09-07**: `frontend/src/renderer/lib/nav.js` widened
  `daily-trial-balance`'s sidebar visibility to `Sales, Manager, Owner` (was
  `Manager, Owner` only — stale from before the RBAC change); the screen
  (`screens/daily-trial-balance/{index.html,screen.js}`) now shows a role tag
  ("Maker — entry & save only" vs "Checker — can Close & Sign Off"), hides the
  Close & Sign Off block/fields/button entirely for Sales via a `canFinalize()`
  gate (mirroring `rate-master/screen.js`'s pattern; server-side RBAC is still
  the real enforcement), adds the `projected_total`/`reason` inputs the new
  `finalize` endpoint accepts, and displays `carried_from` /
  `variance_amount` / `variance_reason` once a day is loaded. The stale
  "pending ADR-1" textarea label was also corrected to say Sections
  2/4/5/8/9/10/11 are final. `frontend/tests/daily-trial-balance.spec.js`
  rewritten to match (Sales sees the nav link but not the finalize controls;
  Manager finalizes and the next day shows the carry-forward line). Verified
  by running the real Playwright suite (31/31 passed) in a from-scratch
  sandbox venv + Chromium before pushing, mirroring the backend verification
  approach; `eslint .` clean on the changed files.

## TODO — future skill folders

Not created yet; scope when the corresponding module is built (BRD §4):
`skills/trial-balance-reconciliation/`, `skills/rate-master/`,
`skills/ocr-upload-review/`.
