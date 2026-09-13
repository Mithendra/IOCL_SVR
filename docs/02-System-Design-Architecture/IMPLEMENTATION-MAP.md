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
| Excel I/O | `backend/src/svr_backend/excel/daily_sales_entry.py` — `GET /{id}/export-excel`, `GET /import-excel/template`, `POST /import-excel` (parse-only, recompute-and-flag per ADR-5). Keyed SVR export/template parsed first; if column F carries none of our field keys, falls back to `_parse_paper_layout` - a natural, paper-shaped workbook (e.g. a handwritten form typed up via an AI chat tool) matched by the physical form's own labels. Either way never a visual replica of the printed form for the *export* side (BRD-flagged, out of scope). |
| Frontend screen | `frontend/src/renderer/screens/daily-sales-entry/{index.html,screen.js}` (Save/Update/Delete are three distinct toolbar buttons gated on whether the day is already saved and, for Delete, on Manager/Owner role - `syncButtonState()`; Import/Export/Scan buttons wired; `lib/api.js` `upload`/`download`/`del`) |
| Edit an existing day | **one entry per `(shift_date, pump_serial, submitted_by)`** — `POST` 409s with the existing id if one exists; the screen's `loadExisting()` opens that row on pump/date pick so Update is a `PUT` (a correction edits the same row, no duplicate); Delete is `DELETE` (Manager/Owner only, RBAC-enforced server-side). Editing a row whose day's Daily Sales Summary is already verified/uploaded resets that side (`summary.reverify_summary_for_entry`, returns `summary_note`). |
| First entry for a pump | Last Shift Reading is backend-owned (auto-carried) only once a prior reading exists (`carry_forward.carried_last_readings`); with nothing to carry, `_apply_locked_context` keeps the operator's own manual reading instead of nulling it, and the frontend enables `#hs-last`/`#ms-last` for that case (`loadPrefill()`, keyed off `carried_from`). |
| Pump serials | **The station's two real serials, client-confirmed 2026-09-11: `12BC4523V-RD` (Road) and `11CC2012V-OFF` (Office)** — set in the `#pump-serial` `<select>` and the two Print Blank buttons in `index.html`. `summary.classify_pump` maps office/road from an **explicit serial→side dict** (`PUMP_SIDE`), not a substring guess off the serial text — a prior version inferred the side from "OFF"/"RDF" inside the serial itself, which breaks the moment a serial's own suffix doesn't match its real-world side (exactly what happened here). Daily Trial Balance needed no change - it only reads Daily Sales Summary's *combined* (both-sides-summed) total, never a specific serial or side. `#pump-side-label` shows "(Road pump)"/"(Office pump)" next to the dropdown (`PUMP_LABELS`), matching the client's own reference blank forms `SVR_DSR_EMPTY_<serial>.pdf` - visible on screen and in Print/Print Blank output alike. |
| Import identity | **Pump Serial + Shift Date always come from the form's own `#pump-serial`/`#shift-date`, never from an imported document (2026-09-11).** Scan/Upload and the paper-layout Excel fallback already worked this way; a keyed SVR export/template's `meta.pump_serial`/`shift_date` used to silently switch the dropdown/date on import. `populateInputs()` no longer touches identity at all (dropped the `meta` param); `importExcel()` instead compares the file's `meta` to what's currently selected and surfaces a named mismatch note in the status line, without changing the selection. |
| "-" convention | The paper form uses a lone `-` as its universal "nothing to report" marker (blank oil qty, blank credit-card rows, blank summary lines - every real client sample does this consistently). Treated as blank everywhere: `calc.amounts.is_blank` and `excel/daily_sales_entry.py`'s own `_num_or_str` both recognize it (2026-09-11) - previously read as the literal string `"-"`, which didn't corrupt totals (parses to 0) but would show as filled-in `"-"` boxes on the review screen instead of genuinely blank ones. |
| Excel multi-sheet | A workbook can have more than one sheet (e.g. one file with a Road sheet and an Office sheet for the same day - a real client file). `parse_workbook(data, pump_serial=...)` picks the sheet whose name contains the given serial when there's more than one (else the single sheet, or our own keyed export's sheet name); `POST /import-excel` takes `pump_serial` as a query param, and the frontend passes `#pump-serial` automatically. No match with multiple sheets -> a warning naming every sheet found, not a silent guess (2026-09-11). |
| Excel paper-layout label tolerance | `_txt()` in `excel/daily_sales_entry.py` folds punctuation to spaces and splits a letter/digit boundary before matching a label/anchor (2026-09-11) - tolerant of real-world wording differences ("2T/1.20 ML" vs "2T-1.20ML" vs extra/missing spaces) that previously dropped a field silently. |
| Excel paper-layout Oil Sale(s) Opening Stock | **Client-reported gap, fixed 2026-09-11**: `_parse_paper_layout`'s Oil Sale(s) table only ever read Quantity - Opening Stock (the field made manually overridable by the row above) was never read from a natural/paper-shaped workbook at all, silently leaving Inventory's tracked default in place even when the sheet had a real override filled in. Now reads both columns independently per row (a row can have Opening Stock filled with Quantity genuinely blank, or vice versa). Oil Rate is deliberately still not read from the sheet - the backend always locks it from Rate Master on save regardless of import, same as Gas Rate, so reading it would be dead weight. Verified against the client's own blank A4 templates (`SVR_DSR_Empty_<serial>_A4.xlsx`), not just a hand-built approximation. |
| Oil Sale(s) Opening Stock | **Short-term fix, 2026-09-11** (client-confirmed as temporary, pending a proper day-close sync between Daily Sales Entry and Inventory Tracking): oil sales are handled by only one submitter on a given day, so the *other* submission's Opening Stock has nothing but Inventory's `on_hand` to default from and no automatic way to correct it. `#{key}-opening` is now editable (was locked); `_apply_locked_context` uses a manually-entered value when given, else falls back to `inventory.on_hand_map` as before. Rate stays fully locked (Rate Master governs pricing) — only Opening Stock changed. |
| Print & Sync (2026-09-11) | The day-close sync from the row above, built out: two buttons, `[data-sync="12BC4523V-RD"]` / `[data-sync="11CC2012V-OFF"]`, next to the Print Blank buttons - **Manager/Owner only** (`syncAndPrint()`, hidden client-side for Sales; server-enforced via `require("Manager","Owner")` on `POST /daily-sales-entry/sync-inventory`, same access as Inventory Tracking itself). `inventory.sync_from_daily_sales(conn, before_date, actor)` sets each oil item's `on_hand` to the most recent **real** Closing Stock recorded for it (qty not blank, gap-skip-back per item independently, same principle as gas Last Shift Reading) - a "set", not an increment, so re-running it, or a Manager correcting `on_hand` by hand afterward, is always safe. Click flow: sync → `loadPrefill()` (which already carries yesterday's Current Reading into today's Last Shift Reading, and now also picks up the freshly-synced Opening Stock) → plain-English status line naming what changed → `window.print()`. |
| Renderer calc mirror (UX only) | `frontend/src/renderer/lib/calc-mirror.js` |
| Backend tests | `backend/tests/test_daily_sales_entry_api.py`, `test_calc_daily_sales_entry.py`, `test_ocr_status.py`, `test_excel_daily_sales_entry.py`, `test_excel_paper_layout_import.py` |
| Playwright | `frontend/tests/daily-sales-entry.spec.js` |
| RBAC | Sales create/edit own · Manager/Owner full incl. delete |
| Skill | `skills/daily-sales-entry/` |
| OCR | engine bundled (`ADR-6`) + **draft-assist pipeline**: `ocr/pipeline.py` (PDF text layer first for typed/machine-generated documents - reliable, no OCR; PyMuPDF raster → Tesseract tsv → anchor mapping as the scan/photo fallback), `ocr/layout.py`, `POST /daily-sales-entry/ocr` (never saves, ADR-5 review, per-field confidence). `GET .../ocr/status` → `pipeline: draft-assist`. Tests `test_ocr_pipeline.py` (skip w/o staged Tesseract), `test_ocr_text_layer.py`. **Handwriting is not read reliably by OCR** — `docs/01-BRD-Requirement-Gathering/OCR-findings-2026-09-09.md`. A typed/AI-transcribed document is read reliably either as a PDF (text layer) or as a natural Excel workbook (paper-layout import fallback, above) - two working manual-conversion workflows that need no OCR engine at all. |
| Print | Print / Print Blank cover Sections 1-7 only, matching the physical paper form - Section 8 "Daily Summary" (an internal report, not on the paper form) and the operational banners/status line are hidden under `@media print` (`#daily-summary-block`, `#carried-note`, `#editing-note`, `#save-status`, `#toolbar-hint`, plus the Query/Browse controls). `@page` is **A4 portrait** (`app.css`, fixed 2026-09-11) - the client's own reference blank forms (`SVR_DSR_EMPTY_<serial>.pdf`) are single-page A4 portrait; the prior forced-landscape setting fought that badly enough that one pump's form didn't print at all. A table row / section heading is kept from splitting across a page break (`break-inside: avoid`). This rule is in the shared `@media print` block, so every module's print output is now portrait. |
| Print — one page | **2026-09-11**: the form printed across **3 pages**. Compact print-only metrics (8px cells, 9px inputs, trimmed header/section chrome) bring a standard form onto **one A4 sheet**, matching the reference blank form's density. Measured, not assumed — `daily-sales-entry.spec.js` renders the screen with `page.pdf()` and asserts the PDF has exactly one page. A heavy day can still legitimately run to a second page as the repeating credit sections grow; the paper form behaves the same way. |
| Print preview | **2026-09-11**: there was none — Electron's bare `window.print()` goes straight to the Windows print dialog with no preview pane. `main.js` now exposes `svr:print-preview` over IPC, rendering the page with `webContents.printToPDF({ pageSize: "A4", preferCSSPageSize: true })` into a preview `BrowserWindow`; Chromium's PDF viewer supplies Print and Save-as-PDF. Bridged via `preload.js` `printPreview()`; `printSheet()` in the screen falls back to `window.print()` in a plain browser (and in page-mode tests). |
| Net Bal Hand Off formula | **Client-confirmed 2026-09-11, revised 2026-09-12**: **every non-cash line is SUBTRACTED** — `(gas_total + oil_total) − (expenses_total + phone_pay_settled + phone_pay_not_settled + new_credits_total + credit_cards_total)`. Net Bal is the *physical cash* handed over, so money collected electronically or given on credit is not in the drawer. Reproduces all three real filled forms exactly (23,298.77 / 38,993.84 / 1,601.20); under the old all-additions formula the Sep 9 gap was 82,856 = exactly 2 × the two Phone Pay lines. **The paper form's own printed label still reads "+" and contradicts its own arithmetic** — worth correcting on the next print run. `new_credits_total` is blank on all three samples so its sign is inferred, not proven. In `calc/daily_sales_entry.py` (authoritative) + `lib/calc-mirror.js` (mirror, SDD §6.4/§7.3); locked by `tests/test_client_reconciliation_2026_09_11.py`. |
| Night Cash Hand Off — removed | **2026-09-12, client**: the `Night Cash Hand Off Total Amt` row is gone from section 7 entirely, and `night_cash` from the engine, the mirror, the Excel build/parse and the payload. The money it recorded is already carried by the section-3 Expenses row *"Last Night Cash Hand-off Person's Name-Signature-Amount"* — the two together double-counted it. Blank on every real sample, so all three reconciliations are unchanged (verified, not assumed). `CalcRequest` no longer declares the field, so an older client still posting it is accepted and the value dropped rather than 422-ing the save; an older *exported workbook* still parses (the key stays in `_KEY_EXACT`, `_assign` ignores it). |
| Oil Sale(s) — 7 rows | **2026-09-12, client**: five rows became seven, in this order — `2T/1.50 ML Total#`, `2T/2.40 ML Total#`, `Acid Water Total 1 Lts`, `Battery Water Total 1 Lts`, `Battery Water Total 5 Lts`, `20/40 Engine Total in 05. Lts`, `20/40 Engine Total in 1 Lts`. Corroborated by `daily_trial_balance_branded.html` §2.6, which already listed `2T/1.50 ML`, `Battery Water Total 1 Lts` and the 1/2-Ltr vs 1-Ltr engine-oil split — the Daily Sales form had simply never picked them up. **`item_key` identifies a product, not a row position**, so `oil1`/`oil4`/`oil5` were relabelled in place (keeping their Rate Master history and tracked stock) and `oil6`/`oil7` added — which is why the order is **not** numeric. Migration `0017_oil_items_2026_09_12.sql`. *(Superseded 2026-09-13 - the list is now the `oil_item` table; see the next row.)* |
| Oil Sale(s) — the list is DATA, not code | **2026-09-13, client** ("people should be able to add it, or people should be able to remove it"): the seven rows moved out of the `OIL_ITEMS` tuple into the `oil_item` table (migration `0023_oil_items_table.sql`), with `oil_item_alias` holding every label the station has ever used. `svr_backend/oil_items.py` is the registry (`active_items`, `labels`, `label_to_key`, `oils_by_key`, `next_key`); `api/oil_items.py` is the CRUD, Manager/Owner to change and Sales to read. **Adding an item creates three things together** — the item, a `rate_master` row and an `inventory_item` row — because an oil row without a rate and an opening stock is unusable; that is exactly what migration 0017 did by hand. **Removing is a deactivation, never a delete**: a recorded day names the item in its own saved rows, so the entry screen puts a read-only `retired` row back for it (`restoreRetiredRows`) rather than recomputing the day without it and silently shrinking its Oil Total. The first rate is filed effective `2000-01-01` — a brand-new product has no rate history to protect, and filing it under the seed's 2026-08-11 made any earlier day price the row at zero. `calc/daily_sales_entry.py` stays pure and label-driven; its constants remain only as the fallback for a payload that arrives with no labels. Tests: `backend/tests/test_oil_items.py`, plus three cases in `daily-sales-entry.spec.js`. |
| Oil rows — resolved by label, not position | The row-order change broke every positional read of a *stored* record. `resolve_oil_key()` / `oils_by_key()` (engine) and `oilKeyOf()` (screen, mirroring it) resolve a saved row to its item by the row's own stored `label`, falling back to position; the `oil_item_alias` table maps every label the station has ever used (was `LEGACY_OIL_LABELS`). Used by `summary._side_from_entry`, `inventory._sold_today`, `inventory.sync_from_daily_sales`, and the screen's `applyResult`/`populateInputs`. Position alone is only safe for a payload the *current* form built. |
| Oil rates across the relabel | **Every relabelled row keeps the rate it already had** — `oil1` 30.00, `oil2` 17.00, `oil3` 20.00, `oil4` 120.00, `oil5` 130.00, all five off the client's own filled September sheets. Migration 0017 initially held `oil1`/`oil4` at 0.00 pending confirmation that a renamed row is the same product; **migration 0018 carries them through**, the client having confirmed this round is form changes, not data validation (2026-09-12). `oil6` and `oil7` stay 0.00 because they are new rows with **no prior rate to carry**, not because anything is pending (`sell_rate` is `NOT NULL`, so 0 is the only way to say "unset"); the Owner sets them in Rate Master. Either way the Oil Sale(s) **Rate cell is now editable** on the form (gas Rate stays backend-locked), so a sale can be keyed from the paper sheet's own Rate column — the authoritative source for oils anyway. |
| Total Gas & Oil Sales Amt | **2026-09-12, client**: a closing row at the foot of section 2, `gas_oil_total = gas_total + oil_total`. Same figure as section 7's `Cash (Gas + Oils)`, which stays; both appear on the client's own form. Mirrored in `calc-mirror.js` and carried in the Excel export as `_chk.gas_oil_total`. |
| Expenses — writing width | **2026-09-12, client**: the Amount column in section 3 is sized to hold `9999999999999999` with room to spare (`.wide-amounts` in `app.css`, 30ch column / 26ch input), because that cell is written into **by hand** on the printed form in the paper's running-sum style (`527+588+100=1215`). The Description column gives up the width, not the writing space. |
| Rounding — truncate, not round | **2026-09-11**: `calc/amounts.py` `trunc2` cuts every row amount at paise; totals are the sum of the truncated rows. The station's forms do this — `629.49 × 105.36 = 66323.0664` prints as `66323.06`, not `.07`; truncation matched 4/4 sampled gas rows where rounding failed 2/4. `round4` is retained for other callers but Daily Sales Entry no longer uses it. **Consequence:** the SDD §9 worked example now reports **138813.90** rather than 138813.9072 — the underlying product is unchanged and still asserted. |
| Oil Rate source | **2026-09-11**: oil Rate is read from the imported sheet and used as given; `_apply_locked_context` falls back to Rate Master only when none was submitted (same pattern as Opening Stock). Gas Rate stays fully backend-locked. Rate Master's oil rates were placeholders never replaced with the station's real figures — corrected by migration `0015_oil_rate_correction.sql` (2T/1.20 62→30, 2T/2.40 118→17, Acid 1L 30→20, Acid 5L 130→120, 20/40 280→130). On the real Sep 9 sheet the stale seeds turned an oil total of 290 into 1,310. `rates.latest_effective_rates` now breaks same-date ties by newest `id`, so a same-day correction wins deterministically. |
| Query / Search | **2026-09-11, client-mandatory**: a **Query** button next to Shift Date / Pump Serial loads the saved entry for that day and *always reports what it found* — silently doing nothing was what made saved data look unreachable. **Browse saved entries** opens a date-range + pump search; `GET /daily-sales-entry` gained `date_from`/`date_to`/`limit`. Results are clickable through to the day. Hidden from print. |
| Two-decimal display | **2026-09-11**: `lib/format.js` `fmt2()`; applied at display choke points (`applyResult()` in Daily Sales Entry via `setNum`, and each other screen's render). Deliberately **not** applied to fields being typed into — the inline scratch-sum syntax (`527+588+100=1215`) must survive round-trip. Values stay numeric in the payload; this is presentation only. |
| Inventory: set vs add | **2026-09-11**: Restock **adds** (a dated receipt log); the new editable **Opening** column **sets** the level outright, including to 0. `PUT /inventory/{item_key}` widened from Owner-only to **Manager/Owner** — correcting a miscount is floor work. Previously only the additive path was reachable from the UI, so a corrected figure stacked on top of the old one and an opening count could not be established at all. |
| Scan / Upload (OCR) | **Removed from the UI 2026-09-11** at the client's request — stock Tesseract never read the station's handwriting, and for a typed document Import from Excel reads every section while the OCR path only ever covered gas readings + 3 summary lines. The backend `/daily-sales-entry/ocr` endpoint is left in place; retiring it also means unbundling Tesseract (~175 MB off the installer), which is its own change. |
| Gaps | OCR handwriting accuracy (input problem, not plumbing — see findings doc) |

## Module 2 — Daily Sales Summary  (mockup: `daily_sales_summary_branded.html`)

| Part | Path |
|---|---|
| Backend router | `backend/src/svr_backend/api/daily_sales_summary.py` |
| Combine/derive helper | `backend/src/svr_backend/summary.py` — `build_summary` (combined totals **derived live** from the entries' cached `result`, never stored) + `reverify_summary_for_entry` (a correction to an entry re-opens the verified/uploaded summary side, ADR-5) |
| Migration | `0003_daily_sales_summary.sql` |
| Frontend screen | `frontend/src/renderer/screens/daily-sales-summary/{index.html,screen.js}` — `#gate-status` names which pump's Daily Sales Entry is missing by side ("Missing the Daily Sales Entry for: Road pump...") rather than a generic "waiting" message, once both sides are required every day (2026-09-11 client confirmation - even a repaired/off-duty pump submits a zero-activity report rather than being skipped, see `test_real_data_2026_09_11.py`). |
| Pump serial tagging + check | **2026-09-12, client-requested validation.** `daily_sales_summary_branded.html` and `daily_trial_balance_branded.html` §2.1–2.4 had the two serials **the wrong way round** — Office labelled `12BC4523V-Off`, Road labelled `11CC2012V-Road`. The app itself was never wrong (`summary.PUMP_SIDE` has always mapped `11CC2012V-OFF`→office, `12BC4523V-RD`→road), but nothing on screen said so, so the error survived in the requirement docs unchallenged. Both mockups are corrected, and the pairing is now printed on the screen itself: section headings read *"1. Office Pump (11CC2012V-OFF) Submission"* / *"2. Road Pump (12BC4523V-RD) Submission"*, the combined table's column headers carry the serials, and `#serial-check` asserts each present submission's serial against `SIDE_SERIAL` on every render (green confirmation, red named mismatch). Daily Trial Balance's `#s3-src` line likewise names both serials behind the combined Section 3 figure. |
| Combined table | Carries one row per **active** oil item (auto, from the `oil_item` list - seven today, editable by the Owner since 2026-09-13) plus `Gas Total Amt` and `Total Amt Oil(s)` — the same three closing lines the Daily Sales Entry form has since 2026-09-12. `build_summary` gained `combined.gas_total`. Every figure goes through `fmt2` (two decimals, 2026-09-12 — this screen still printed raw `String(n)`). Per-side oil amounts are resolved by **label** via `oils_by_key`, not by position (Module 1, "Oil rows — resolved by label"). |
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
| **2FA (TOTP)** | `backend/src/svr_backend/totp.py`, `api/auth.py` (`/auth/login/totp`, `/auth/2fa/{status,setup,activate,disable}`), migration `0013_totp_challenge.sql`, `core/session.py` (`check_password`/`issue_session`). Secret Fernet-encrypted via `core/crypto`. Self-enroll: `screens/security/{index.html,screen.js}` (nav key `security`, all roles). Admin clears a locked-out user via `PUT /users/{id} {totp_enabled:false}` ("Clear 2FA" button); admin **cannot** enable (422). Tests: `test_totp.py`, `two-factor.spec.js` (+ `totpCode` in `tests/_helpers.js`). |

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
| Backend routers | `backend/src/svr_backend/api/employees.py` — `router` (employees), `payroll_router` (`/payroll-runs`), `insurance_router` (`/employee-insurance`) |
| Encryption | `backend/src/svr_backend/core/crypto.py` (bank account / IFSC / branch) |
| Migration | `0007_employee_master.sql` (employee, payroll_run, payroll_run_line); `0014_employee_insurance.sql` (employee_insurance) |
| Frontend screen | `frontend/src/renderer/screens/employee-master/{index.html,screen.js}` (sections 1–2 + insurance 3–5) |
| Backend tests | `backend/tests/test_employees_api.py`, `test_employee_insurance.py` |
| Playwright | `frontend/tests/employee-master.spec.js` |
| RBAC | Sales blocked · Manager/Owner full |
| Insurance (mockup 3–5) | `/employee-insurance` CRUD (`kind` = accidental \| health; employee linked by name, `ON DELETE SET NULL`) + `/employee-insurance/summary` (§5 Annual Premium Summary: accidental_total + health_total = grand_total). |
| Gaps | — |

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
| Backend tests | `backend/tests/test_daily_trial_balance_api.py` |
| Playwright | `frontend/tests/daily-trial-balance.spec.js` |
| RBAC | Sales = maker (`GET`/`PUT`) · Manager/Owner = checker, full + `finalize` (ADR-2, ADR-2-implemented 2026-09-06) |
| Carry-forward | ADR-2, implemented 2026-09-06 in full: `finalize` gates on the previous day being closed, auto-creates + seeds the next day via `prev_trial_balance_id`, and runs the ±₹100 variance/escalation check. Multi-day gap handling (holidays/skipped days) — **RESOLVED with client 2026-09-06, no code change**: sequential one-by-one catch-up is the confirmed final design; see ADR-2 "Point 5". |
| Frontend RBAC | **Closed out 2026-09-07**: `nav.js` widened to show the module to Sales too (maker); the screen itself hides the Close & Sign Off block/fields/button unless `me.role` is Manager/Owner (`canFinalize()`, mirrors `rate-master/screen.js`) and shows a role tag; adds `projected_total`/`reason` finalize inputs and a `carried_from`/`variance_amount`/`variance_reason` display line. Playwright spec rewritten to match; full frontend suite (31/31) verified before push. |
| Frontend screen | `frontend/src/renderer/screens/daily-trial-balance/{index.html,screen.js,sections.js}` — `sections.js` is the form definition for every section the backend does not compute |
| **All 11 sections on the form (2026-09-12)** | The screen rendered Sections 1/3/6/7 and put the other **seven** behind a single raw JSON textarea, so in live testing the form looked like it had three sections. ADR-1's *storage* decision is unchanged — every field still lands in the same `manual` dict — but they are now real labelled fields, defined declaratively in `sections.js` and bound by a dotted `data-manual="section3.onhand"` path, with repeating blocks (`data-rows`) for New Credit / Salary Advance, Expenses, Credit Remittance, Regular Expenses and the 26-column Daily Mgr Calculation ledger. An already-saved record round-trips untouched. |
| Section numbering | **Now the station's own workbook numbering (1–11)**, which is what the operator has in front of them. It previously showed the SDD §9 numbering, so the screen said "6. Stock Value" where the workbook says **5**, and "7. Trial Balance Total" where the workbook says **6** — a mismatch `CLAUDE.md` had recorded but the screen never reflected. Backend field names (`s54_cash_book_value`, `computed.section6`, `computed.section7`) deliberately keep the old numbering; the two are mapped at the render/payload boundary in `screen.js`. |
| Section 2 — Day Sales Report | Built 2026-09-12 as a **read-only live pull**: the screen fetches `GET /daily-sales-entry?shift_date=…` and renders each pump's HS/MS Current/Last/Consumption/Rate/Amount rows, the oil rows summed across both pumps **by stored label** (`oils_by_key` discipline — the row order changed that same day), 2.5 Total Sale Ltrs, 2.6 Oil total and 2.7 Daily Sales Total. Nothing here is stored on the Trial Balance record; it is the same pull Section 1's Actual Consump already used, now shown in full. |
| Section 1 extra columns | The workbook's Margin / Margin Total / 2T Sales / Total Sale Amt / IOCL Adv / IOCL Profit columns are **manual fields**, not computed — their formulas have never been confirmed against a filled workbook, and guessing one is what caused the 2026-09-11 oil-rate and Net-Bal defects. Labelled as manual on screen. |
| **Gaps** | Sections 2/4/5/8/9/10/11 are **captured, not computed** — their cross-section rollups (e.g. 4.3 Total-Projected, 7.3 Projected Trial Balance) are still typed by the operator. **CONFIRMED 2026-09-06 as the final design (SDD ADR-1)**; computing them needs the client's own formulas confirmed against a filled workbook first. |

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
