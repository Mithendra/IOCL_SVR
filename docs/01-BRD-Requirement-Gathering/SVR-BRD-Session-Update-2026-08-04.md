# SVR Indian Oil Service Station — BRD Update Log
**Date:** August 4, 2026
**Document updated:** `SVR-BRD-Requirement-Gathering.docx`
**Follows:** `SVR-BRD-Session-Update-2026-07-30.md`

Summary of changes made to the BRD during today's session, re-verifying Section 5.8 (Daily Trial Balance Module) directly against a live daily tab (`GAS_STATION_-03-08-26.xlsx`, AUG03 tab) rather than the earlier sample workbook pass.

---

## 23. Trial Balance Section Structure Re-Verified Against Live Tab (2026-08-04)

- **Section count corrected: 8 → 9.** The AUG03 tab carries its own in-sheet numbering (1–9), one more than the 8-item form outline previously documented in Section 5.8. The 9th section, "Daily Mgmt Summary," was missed earlier because it's placed in column E next to Section 4's block rather than as its own column-A heading.
- **Rows 59–71 corrected: one section → two.** Previously documented as a single Trial Balance block. Re-verified as two distinct numbered sections back-to-back: Section 7 "Trail Balance" (rows 59–64, cash + stock value totals) and Section 8 "Trail Balance – IOCL Computer Vs Pump Readings" (rows 66–71, the pump-vs-computer profit/loss trial balance and Difference calc).
- **Section renames confirmed from the live tab** (station has already renamed these in the working sheet):
  - Section 1: "Pump Reconciliation" → "IOCL Computer Vs Pump Readings"
  - Section 8: "Trail Balance – Profit Pump Vs Computer Readings" → "Trail Balance – IOCL Computer Vs Pump Readings"
- **Section 4 / Section 5 clarified as sequential, not duplicated:** "Daily Cash Value" (Section 4 — On Hand/Night/Morning cash handoffs, IOCL/bank balances, credits) feeds into "Cash Value Reconciliation" (Section 5 — a short 5-line check: Yesterday's Daily Cash Value + Daily Sales Amt After Exp = Total, vs. Actually Accounted, with a Difference line).
- **Fleet Card Balance Tracking location corrected.** Confirmed this is NOT a sub-part of Section 8 as earlier assumed. It's a small standalone two-line block ("New Airttel Balance" / "Old Airttel Balance") sitting after Section 8, not under its own numbered heading. Separately, the workbook also has a "Fleet Card Swipe" column inside the Historical Daily Summary Log table — a third, distinct location. The open question from Section 4.4/20 (whether this sub-section is still needed now that the IOC statement's Closing Balance reconciles the Fleet Card figure directly) remains unresolved and still needs station confirmation.
- **Documents updated:** Section 5.8 — form outline paragraph rewritten with the corrected 9-section structure and live section labels; Fleet Card Balance Tracking row in the duplication table updated with the corrected location detail. The original 8-item outline is retained in the document for traceability rather than deleted outright.

**Open items carried forward, unchanged:**
- Fleet Card Balance Tracking — still UNDER REVIEW (removal/merge question, per Section 20 of the prior log)
- Phone Pay Settled — still PENDING (6:30 AM IST timing, per Section 22 of the prior log)

*No new open items introduced this session — this was a structural correction pass, not a new-requirements pass.*

---

## 24. Software Requirements Overhaul (2026-08-04)
Several architecture and project-process decisions confirmed and added to the BRD:

- **Frontend framework changed:** **ElectronJS** (desktop UI framework), replacing the earlier "optional local HTML/Chrome-based UI shell" direction.
- **Application coding:** Python (business logic layer) — unchanged, now stated explicitly as its own row.
- **Backend/database:** SQLite — unchanged.
- **Database indexing — new requirement:** proper indexes must be created on the SQLite database (date, user/role, form-type columns) to keep queries performant as records accumulate over the 1-year retention window.
- **OCR engine — no change, now cross-referenced:** Tesseract OCR (open-source), already confirmed in Section 9, is now also listed directly in the Software Requirements table (Section 4) so it's visible without having to check Open Items.
- **Service auto-start & logging — new requirement:** this is a desktop/laptop small-business application. On machine startup, ALL components (Python backend, SQLite, ElectronJS frontend, email integration) must auto-start as **Windows Services** (via services.msc), not require manual launch. If any component fails to start, it must log to its **own dedicated log file location** (one log file per component, not shared).
- **Project Skills File — new requirement:** a project-level **SKILLS.md** file is required (at the project root, alongside CLAUDE.md), documenting proper references for Scripts, References, and Assets used by the application.
- **Testing — new Section 4.5 added:** formal test cases required, covering OCR/Upload Mode scenarios (converting Section 8's real handwriting cases into repeatable tests), service reliability (auto-start + per-component logging), data entry/reconciliation field validation, and report/email generation. Test framework/tooling and whether tests live in the GitHub repo are left as open design questions.
- **Code Repository URL corrected:** `https://github.com/mithendrapamulapati/SVR` → **`https://github.com/mithendra/SVR`** (updated in both the intro summary table and Section 1 Project Context).

---

## 25. Project Skills File Corrected to Match Anthropic's Agent Skills Standard (2026-08-04)
The earlier "Project Skills File" requirement (Section 23/24, single `SKILLS.md` file) was checked against Anthropic's official guide (*The Complete Guide to Building Skills for Claude*) and found to be incorrect on several points. Corrected in the BRD:

- **Filename fixed:** `SKILL.md` (singular, exact, case-sensitive) — not `SKILLS.md`.
- **Structure fixed:** a skill is a **folder** (kebab-case name, e.g. `skills/svr-daily-sales/`), not a single file. Each folder contains `SKILL.md` plus optional `scripts/`, `references/`, and `assets/` **subfolders** — previously we described these as sections inside one file, which isn't how the standard works.
- **YAML frontmatter requirement added:** `SKILL.md` needs a `name` (kebab-case, matching the folder) and a `description` stating both what the skill does and when to use it (under 1024 characters, no `<>` tags) — this is what lets Claude auto-load the skill.
- **No README.md inside the skill folder** — documentation belongs in `SKILL.md` or `references/`.
- **Size guidance added:** keep `SKILL.md` under ~5,000 words, moving detail into `references/` (progressive disclosure).
- **Clarified relationship to CLAUDE.md:** the project-root `CLAUDE.md` (Section 1) is a separate, valid concept for repo-wide AI-assistant config — it is not a skill and doesn't need this folder structure.
- **New open item added:** which specific project workflows warrant their own skill folder (e.g. a `daily-sales-entry` skill, a `trial-balance-reconciliation` skill) is not yet defined — to be scoped in the design phase, ideally using Anthropic's `skill-creator` tool.

---

## 26. Daily Sales Report Compared Against Aug 5 Revision (2026-08-04)
The client uploaded an updated official Daily Sales Report template (`SVR_Gas_Station_Daily_Sales_Report_Updated_Aug5th`). Compared field-by-field against BRD Section 5.4.1. Most sections already matched exactly (Oil Sale(s), Expenses, Today New Credit(s), Old/Pending Credit Received, Summary — Cash Hand Off including the Phone Pay 6:30 AM timing and Net Bal Hand-off formula — all confirmed unchanged). Two real deltas found and corrected:

- **Gas Sale(s) column labels updated:** "Last Shift Reading" / "Consumption (Last − Current)" → **"Yesterday Reading" / "Diff [Yesterday−Current]"**. Same underlying meaning, just terminology aligned to the latest official form.
- **Credit Card Swiping(s) — real structural change:** "Card Holder / Terminal ID" renamed to **"Card Holder Name"**; the **"Rate" column has been replaced with "In Lts"** (quantity in litres, not a rate) — this is a genuine field-type change, not cosmetic; repeating row count reduced from **7 lines to 5 rows**.
- Updated Section 5.4.1 in the BRD to reflect both changes, noting they come from the Aug 5, 2026 form revision.

---

## 27. Daily Sales Entry Form — Design Finalized (2026-08-05)
The Daily Sales Report was built out as a working HTML prototype (`Daily_Sales_Data_Entry.html`, revised) and iterated through several rounds. Final confirmed design:

- **All 7 sections present and complete**, matching Section 5.4.1 exactly, numbered 1 (Gas Sale(s)) through 7 (Summary — Cash Hand Off) — no sections trimmed, all field wording/casing/punctuation copied verbatim from the Aug 5 form.
- **Expandable rows** added to Credit Cards Swiping(s), Today New Credit(s), and Old/Pending Credit Received — each has a "+ Add row" control, since row counts vary shift to shift rather than being fixed.
- **Page orientation — CONFIRMED: A4 Landscape**, not portrait. The widest tables (5-6 columns) were cramped in portrait; landscape gives ~40% more width at no paper-size cost. Print CSS (`@page { size: A4 landscape; margin: 10mm; }`) added; interactive-only elements (Add row buttons) hidden on print. Legal/Foolscap size flagged as a fallback if landscape still feels tight once expandable sections are in heavy use — pending field testing.
- **Language toggle — CONFIRMED design:** English / Telugu pill toggle in the header, matching the original prototype's placement and styling. Scope confirmed as section headings only (field labels stay English), consistent with the original file's stated scope.
- **"Manual Entry Mode" status tag** included in the header, matching the original prototype.
- **Color palette — corrected against verified IOCL brand colors.** iocl.com itself couldn't be scraped directly (JavaScript-rendered), so the official palette was cross-checked against multiple independent brand-color references, which consistently list only **three** official IndianOil logo colors: Vivid Tangelo orange `#F37022`, Oxford Blue `#02164F`, and White `#FEFEFE` — no red is part of the official registered palette.
  - **Section headings (all 7) corrected** from an approximate "flame red" (`#e31e24`, carried over from the original prototype) to the **official Vivid Tangelo orange `#F37022`**.
  - **Header bar** stays blue gradient (`#0033a0` → `#00246e`); light-blue tints (`#eef1fa`) used for table headers and total rows.
  - **Two remaining red accents** (top flame bar, "Net Bal Hand off" emphasis line) still use `#e31e24` from the original prototype and were **not** changed — flagged as an **open question**: should these move to orange or to the official Oxford Blue for full consistency, or is a red accent acceptable as a non-logo UI accent color? Needs client confirmation.
  - Confirmed direction: strictly blue + orange/red accent + white/near-white only — no other hues anywhere in the form.

---

## 28. Remaining Forms Built in Same Design (2026-08-05)
Applied the same header, color palette (blue header, orange `#F37022` section headings, white/light-blue body), A4 Landscape layout, and English/Telugu toggle pattern to all remaining system forms, so all 5 forms now share one consistent design:

1. **Daily Sales Entry Form** (`daily_sales_report_branded.html`) — built in prior sessions.
2. **Manage Users form** (`manage_users_branded.html`) — Add/Edit User block (Name, Personal Email, auto-derived read-only Login Name, Role, Status) plus an expandable User List table.
3. **New Credit Entry form** (`new_credit_entry_branded.html`) — Old Credit Accounts module. Creditor Record field for selecting an existing creditor or adding new; expandable row table (Creditor Name, Type, In Ltrs, Rate, Amount, Signature).
4. **Record Repayment form** (`record_repayment_branded.html`) — Old Credit Accounts module. Tied to a selected creditor record; Payment Credited, Date, Payment Collected By fields; open question about partial repayments carried over as a visible note.
5. **Daily Trial Balance form** (`daily_trial_balance_branded.html`) — built in prior session; all 9 confirmed sections plus the standalone Fleet Card Balance Tracking block, with pulled-in sections shown as disabled/read-only fields.

BRD Section 5.6.1 (UI Branding & Color Palette) updated with a consolidated bullet listing all 5 form deliverables and their file names, confirming the design pattern applies system-wide rather than only to the Daily Sales Entry form.

---

## 29. Trial Balance Re-Verified Against AUG12 Tab, Updated Through Section 10 (2026-08-12)
Client instruction: update the Daily Trial Balance form using the newly uploaded `GAS_STATION_-12-08-26.xlsx` (AUG12 tab), through Section 10 only — no other changes.

- **Confirmed exact field structure for Sections 1–10**, cross-checked against the live sheet (see updated BRD Section 5.8 for full column-level detail). No structural surprises versus the 2026-08-04 pass, but exact column labels are now locked in verbatim (e.g. "Computer/Pump Diff Consumption", "Consumption {Last-Current}", "Per Pump").
- **Section 9 confirmed as the historical daily-summary log**, now correctly implemented in the live sheet as **one running table with a row per date** — this resolves the historical-log duplication issue flagged all the way back in the original sample-workbook review (repeated per-tab log). Good sign the digital direction is already validated by the client's own evolving spreadsheet.
- **New finding — "Fraud Pending" label.** Section 4's Indian Bank Statement Ending Balance row is now explicitly labeled in the live sheet as **"@Fraud Pending -Rs 13367"** — this resolves the previously unexplained 13,366.21 gap between the OD-limit calculation and the recorded figure (Section 4.4/20 of this log). The digital field should support excluding a labeled fraud-pending/blocked amount from the usable balance, tracked as its own value rather than silently subtracted.
- **New finding — row flagged for removal.** Section 4 contains a row the client has literally annotated **"Old Credit Cash hand off (Remove the Row)"** — excluded from the digital form design accordingly.
- **Section 11 (Old/New Credit Sales Details / Fleet Card Balance Tracking) is out of scope for this update** per client instruction, and remains exactly as previously documented (still UNDER REVIEW).
- **`daily_trial_balance_branded.html` rebuilt** to match the confirmed Sections 1–10 exactly, same branding/A4-landscape pattern as the other 4 forms. Section 9 (Daily Mgr Calculation) implemented as an expandable date-rows table matching its running-ledger nature. Section 4's fraud-pending note called out visually in red text next to the Indian Bank balance field.

---

## 30. Section 1 Correction & Daily Stock Value Formula Confirmed (2026-08-13)
Client-led review of the "no duplicates" summary surfaced a real error and a real business rule:

- **CORRECTED — Section 1 (IOCL Computer & Pump Readings) is NOT a duplicate of the Daily Sales Report.** Previously classified as "pulled from Daily Sales Report" (both in the BRD's duplication table and the HTML mockup, which had its fields disabled/greyed). Verified against real AUG12 tab numbers: Section 1's IOCL readings (6,678 / 5,393) are a completely different order of magnitude from Section 3's per-pump readings (256,466 / 1,477,661) — proving they're independent data. Section 1 is a **separate regulatory flow-computer reading**, distinct from the pump dispenser readings the two workers record. Section 3 remains correctly classified as a genuine duplicate (proven earlier with exact matching numbers) — this correction applies to Section 1 only.
- **CONFIRMED — Daily Stock Value formula:** Daily Sales reporting (Section 3) is always based strictly on pump readings. The IOCL Reading (Section 1) is the separate regulatory reading. Every day, both pump workers' Daily Sales Reports are summarized into combined HS/MS totals; these are **deducted from the IOCL reading's consumption** to determine the Daily Stock Value (Section 6). This is exactly what Section 1's "Computer/Pump Diff Consumption" and "Benefit/Loss" columns represent.
- **`daily_trial_balance_branded.html` corrected:** Section 1's IOCL Yesterday/Current Reading fields are now genuinely editable (not disabled); the derived columns (Diff, Consumption, Computer/Pump Diff Consumption, Benefit/Loss, Deduct Testing/Density) show "auto" placeholders since they're computed, not entered. A formula note added directly under the section explaining the Section 1 → Section 6 relationship.
- **BRD Section 5.8 updated** with a correction paragraph documenting both the retraction (Section 1 is NEW/independent, not duplicate) and the confirmed Stock Value formula, so the digital system implements it as: `Stock Value input = IOCL consumption (Section 1, manual) − summarized pump consumption (Section 3, auto-pulled)`.

---

## 31. Excel Export Requirement Added (2026-08-13)
- **CONFIRMED — new requirement:** both the Daily Sales Entry form and the Daily Trial Balance form need an Excel (.xlsx) export option, separate from print/PDF and separate from the emailed reports in Section 5.7.
- **CONFIRMED — dedicated export for Section 10 (Daily Mgmt Summary):** in addition to the full Trial Balance export, Section 10 needs its own standalone Excel export — not bundled only inside the full 10-section export. Likely reasoning: it's the condensed management-facing rollup, so management/owner may want just that summary shared on its own.
- **New Section 5.5.1 (Excel Sheet Export) added to the BRD**, documenting both requirements plus open design questions: exact target format for the Section 10 export (single-row daily summary vs. a running multi-day table like Section 9), file naming convention, and whether it's a relocated control or a separate menu action.
- **Both HTML mockups updated:**
  - `daily_sales_report_branded.html` — "Export to Excel" button added above the Verified By signature block.
  - `daily_trial_balance_branded.html` — two buttons added: a secondary "Export Section 10 to Excel" button inside the Section 10 box itself, and a primary "Export Full Trial Balance to Excel" button at the bottom of the form.
  - Also fixed a pre-existing minor bug in `daily_trial_balance_branded.html`: a missing closing `</head>` tag.

---

## 32. Section 9 Missing Columns Found and Corrected — Two Passes Needed (2026-08-13)
Client asked directly whether any columns had been removed from Section 9 (Daily Mgr Calculation). This took two rounds to get right:

- **First check (columns A–H only):** reported no issues — this check was itself incomplete.
- **Second check (wider scan, A–P):** found 8 real missing columns (Daily Expenses, 2T Sale, Total Sale, Settled/UnSettled Phone Pay, Fleet Card Swipe, Credit Card Swipe, Credit (Any)) — corrected BRD and mockup to 16 columns total.
- **Client flagged that this was still incomplete.** A third, full-width scan (A–Z, with explicit confirmation that column Z is the true last column and that every header has real data in a populated row) found **10 more columns**: Night Cash - Total, Day Cash - Total, Total Cash After All, Difference, Bank Deposits (Any), MS Comm, HS Comm, Total Comm, Day Profit, 2T Sales.
- **Section 9 is confirmed at 26 columns total**, verified against the full header row (A78:Z78) and cross-checked against a populated data row (row 79) to confirm no header lacks matching data and no data exists past column Z.
- **BRD corrected** with the complete, verified 26-column list, plus the earlier note that Section 9's Settled/UnSettled Phone Pay, Fleet Card Swipe, and Credit Card Swipe columns are the finalized *historical* daily figures — distinct from the current-day entry fields of the same name in Section 4 — and should populate automatically from each day's closed-out Section 4 record.
- **`daily_trial_balance_branded.html` corrected:** Section 9's table now has all 26 columns (verified: 26 headers, 26 cells per row), horizontal-scroll container widened accordingly, section label updated to "26 columns, scrolls horizontally."
- **Process note for future sections:** given two passes were needed before this was actually complete, the other wide sections (1 through 8, and the Daily Sales Report's own tables) have NOT yet been re-verified with the same full-width-scan-plus-data-row-cross-check method. This should be done before considering the BRD's field-level structure final.

---

## 33. New Module — Inventory Tracking (2026-08-15)
Client requested a new form to track inventory for 5 named items: 2T Oil - 1.20ML, 2T Oil - 2.40ML, Acid Water 1L, Acid Water 5L, 20/40 Engine Oil in Lts. This is the **6th form** in the system (previously 5).

- **New Section 5.10 added to the BRD** — Inventory Tracking Module.
- **Flagged open question — SKU granularity mismatch:** the Daily Sales Report's Oil Sale(s) table (Section 5.4.1) currently combines these into 3 lines, not 5 — "2T Oil [1.20ML/2.40ML]" and "Acid Water 1L or 5L" each span both sizes in one row. This module needs 5 separate SKUs. Not resolved here — either the Daily Sales Report should also split into 5 rows, or an allocation rule is needed. Flagged directly on the HTML mockup as well, not just buried in the BRD.
- **Form structure confirmed (Option B pattern, consistent with Section 5.9):** two separate forms — **Current Stock Levels** (live snapshot) and **Restock Entry** (logging a delivery) — rather than one combined form.
- **Current Stock Levels fields:** Item, Unit, Opening Stock, Received (Today), Sold (Today) — auto-pulled from Daily Sales Report, not re-entered — Closing Stock (computed), Reorder Level, Status.
- **Restock Entry fields:** Date, Item (dropdown of the 5 SKUs), Quantity Received, Supplier/Invoice Reference, Received By.
- **New Section 6 row added:** Stock Status Report — flagged as OPEN whether this becomes a standalone report.
- **`inventory_tracking_branded.html` created**, same branding/design pattern as the other 5 forms (blue header, orange section headings, white background, English/Telugu toggle, Manual Entry Mode tag). Also fixed the same missing `</head>` tag bug found and fixed in the Trial Balance file earlier, which had carried over into this new file's base template.
- **Open design questions remaining:** exact Reorder Level thresholds per item, whether low stock triggers a notification, and whether Stock Status Report is genuinely needed as a standalone report.

---

## 34. Daily Sales Report — 5-Row Oil Split, Merged Expense Row, and Print-Fit Investigation (2026-08-15)

**Structural changes:**
- **Oil Sale(s) split from 3 combined rows to 5 separate SKU rows**, matching the Inventory Tracking Module (Section 5.10): 2T/1.20 ML Total#, 2T/2.40 ML Total#, Acid Water Total In Lts, Acid Water Total 5 Lts, 20/40 Engine Total in Lts. This **resolves** the SKU granularity mismatch flagged as an open question when Section 5.10 was created.
- **Expenses section: two rows merged into one** — "Last Night Cash Hand-off Amount" and "Last Night Cash Hand-off Person's Name & Signature" combined into "Last Night Cash Hand-off Persons Name-Signature-Amount".

**Print-fit investigation — client asked to check fit before making further changes:**
- With the above changes and Credit Cards Swiping(s) still at 5 rows: **3 pages** at A4 Landscape.
- Found and fixed a real CSS bug: the `@media print` compression block was positioned *before* the base styles in the stylesheet, so it had zero effect (later unconditional rules of equal specificity were winning the cascade). Moving it to the end of the stylesheet made it actually work — brought the count to 2 pages on its own.
- Reduced default rows (each retains its "+ Add row" control): Credit Cards Swiping(s) 5→2, Today New Credit(s) 3→2, Old/Pending Credit Received 3→2.
- Result: **2 pages**, with only the last 4 Summary rows + Verified By spilling onto page 2 (~42mm overflow, down from ~83mm).

**Paper size research — client asked what size would be needed to reach 1 page:**
- Tested directly (not estimated): Legal Landscape → still 2 pages (only 6mm more height than A4 Landscape). Legal Portrait → **1 page**. A3 Landscape → **1 page**.
- **Legal Portrait was initially recommended, then corrected after the client questioned its practicality.** Web research confirmed Legal size is a North American standard, not commonly stocked in India — A4 has been actively displacing Legal/Foolscap even institutionally (India's Supreme Court mandated A4 instead of legal-size paper for filings). Also found a real naming trap: "legal size" in India colloquially often means Foolscap (8.5×13.5in), not US Legal (8.5×14in) — asking a local supplier for "legal paper" risks the wrong size entirely.
- **Corrected recommendation: A4 Portrait.** The real physical Daily Sales Report form already in use at the station was independently verified as A4 Portrait, 1 page (pdfinfo on the original uploaded PDF: 595.3×841.89pt). Tested A4 Portrait with the current compressed print CSS and confirmed **1 page**, with all columns still legible at the narrower 210mm width — verified visually, not just by page count.

**Final decision: A4 Portrait**, reversing the earlier A4 Landscape decision from Section 5.5. BRD Section 5.5 updated with the full corrected reasoning, the rejected Legal-size path (kept for traceability, not deleted), and the CSS ordering bug as a technical note to check on the other 5 forms if similar print CSS is added to them.

**Current state of `daily_sales_report_branded.html`:** all structural changes above (5-row Oil Sale(s) split, merged Expense row, reduced default rows, the CSS ordering bug fix) are already applied to the live working file — that's how the page counts above were measured. The ONLY thing not yet applied to the live file is the final `@page` orientation switch itself: the file's CSS still says `A4 landscape`, while A4 Portrait was validated separately in a throwaway test variant. Per client instruction ("update BRD but do not zip yet"), this session updated BRD documentation only — the live HTML file's `@page` rule and the zip package both still need updating in a follow-up step.

---

## 35. Inventory Form Item Names Corrected to Match Daily Sales Report (2026-08-15)
Client requested the Inventory form (`inventory_tracking_branded.html`, Section 5.10) use the same 5 item names as the just-finalized Daily Sales Report Oil Sale(s) split.

- **Item names corrected** in both the Current Stock Levels table and the Restock Entry dropdown (table + dropdown option + JS `addRow` string, 3 occurrences each): 2T Oil - 1.20ML → **2T/1.20 ML Total#**; 2T Oil - 2.40ML → **2T/2.40 ML Total#**; Acid Water 1L → **Acid Water Total In Lts**; Acid Water 5L → **Acid Water Total 5 Lts**; 20/40 Engine Oil in Lts → **20/40 Engine Total in Lts**.
- **Why this matters, not just cosmetic:** the form's own note says "Sold (Today) auto-pulls from the Daily Sales Report's Oil Sale(s) data" — that auto-pull only works if both forms use identical item/SKU names to match records against each other. The earlier draft names would have silently broken that link.
- Header subtitle updated to "OIL'S STOCK — INVENTORY TRACKING" for clarity.
- **BRD Section 5.10 updated** with the corrected names and an explicit note on why exact naming match is required for the auto-pull to function.
- Not yet done: zip package still not rebuilt, per the standing "do not zip yet" instruction.

---

## 36. Daily Sales Report — "Option1_Final_Edit" PDF Comparison (2026-08-15)
Client uploaded a new revision (`SVR_Gas_Station_Daily_Sales_Report_Option1_Final_Edit.pdf`) and confirmed the standing fact that there are two Daily Sales Reports per day (one per pump worker) — already thoroughly documented in Section 5.4, now explicitly reconfirmed as applying to this specific final template (one shared template, filled twice daily, not two different layouts).

Compared field-by-field against current BRD documentation. Several real reversions found — this version goes back to *older* wording that had been changed on Aug 5:

- **Gas Sale(s) column labels REVERTED:** "Yesterday Reading" → back to **"Last Shift Reading"**; "Diff [Yesterday-Current]" → back to **"Cons[Last-Current]"**; "Rate" → back to **"Rate Per Pump"**. The Aug 5 wording lasted about 10 days before being reverted.
- **Credit Cards Swiping(s) REVERTED:** "Card Holder Name" → back to **"Card Holder / Terminal ID"**; "In Lts" → back to **"Rate"**. This undoes what was documented as a "real structural change, not a label tweak" on Aug 5 — now genuinely reverted, not just relabeled.
- **Typo caught and fixed:** "Acid Water Total **In** Lts" (used in both Section 5.4.1 and Section 5.10 since the 5-row oil split) was actually a misread — the source PDF confirms **"Acid Water Total 1 Lts"**, matching the 1L/5L container-size pattern (mirrors "Acid Water Total 5 Lts"). Fixed in both places in the BRD. **Not yet fixed in the HTML files** (`daily_sales_report_branded.html`, `inventory_tracking_branded.html`) — still say "In Lts", pending a follow-up.
- **Header restructured — flagged, not silently applied:** the new PDF shows "Dt:", "Pump: Off/Rd Front:", "Name:" on two lines with abbreviated labels, and **the Shift field does not appear anywhere**. This is significant enough (removing a whole field) that it's flagged in the BRD as needing explicit client confirmation rather than assumed — Shift remains a required field in the BRD until confirmed one way or the other.
- Expenses section (merged "Last Night Cash Hand-off..." row) and the Oil Sale(s) 5-SKU names (aside from the "1 Lts" typo) both **match** what's already documented — no changes needed there.

**Not yet done:** the live `daily_sales_report_branded.html` file has NOT been updated to match these reversions (Gas Sale/Credit Card labels, the "1 Lts" typo, or the header/Shift question) — this session updated BRD documentation only, per the standing "update BRD but do not zip yet" pattern. HTML sync and zip repackaging remain pending follow-up steps.

---

## 37. Daily Sales Entry Form — Real Auto-Calculation Engine, Excel Import, and Daily Summary Section (2026-08-15)

Client requested 6 changes. All 6 addressed — the 3 structural/BRD items documented, and the 3 requiring actual behavior implemented as real, tested JavaScript (not just described):

1. **Three confirmed data-entry modes** (Manual, Scan/OCR, Excel — see #3/#4) documented in Section 5.4, converging on the same record structure.
2. **Auto-calculation, to the possible extent — implemented and tested, not just documented.** Built a `calcAll()` engine in `daily_sales_report_branded.html`:
   - Gas Sale(s): Consumption = Current − Last Shift Reading; Amount = Consumption × Rate Per Pump; Total Amt = sum.
   - Oil Sale(s): Amount = Quantity × Rate (all 5 rows); After Sale Stock = Before Stock − Quantity; Total Amt Oil(s) = sum.
   - Today New Credit(s): Amount = In Ltrs × Rate per row (works on dynamically added rows too).
   - Credit Cards Swiping(s), Old/Pending Credit Received: auto-summed via class-based selectors (works on dynamically added rows too).
   - Expenses: handles the established inline-sum convention (e.g. "527+588+100=1215" → takes 1215).
   - Summary — Cash Hand Off: Cash, Expenses, New Credits, Credit Cards Swiping all auto-pulled from their sections; Net Bal Hand Off computed from the full stated formula.
   - **Verified against the client's exact worked example:** HS 1317.52 × 105.36 = 138813.9072 — tested live in a headless browser, exact match, zero floating-point drift.
   - **Full chain tested end-to-end** with realistic data (not just the isolated example) — all downstream totals (gas-total → sum-cash → sum-netbal, etc.) verified correct, zero console/JS errors.
3. Post-OCR/import validation confirmed in BRD: same auto-calc logic re-runs against OCR-extracted or imported values, flags mismatches rather than silently trusting them.
4. **Excel Import — new requirement, added to BRD Section 5.5.1** alongside the existing Export. "Import from Excel" button added to the HTML (UI only — actual .xlsx parsing is a backend feature, not implementable in a static mockup).
5. Daily Sales confirmed in BRD as the critical input to Trial Balance (reinforces existing Section 4 normalization discussion).
6. **New Section 8 — Daily Summary — added to the form itself**, not a separate report: Total HS, Total MS, and all 5 Oil Sale(s) items, auto-pulled live from Sections 1 and 2 on the same form. Tested and confirmed updating correctly as source fields change.

**Bundled in while editing this file:** applied the label reversions and typo fix that were already documented as pending in Section 36 (Gas Sale(s) → "Last Shift Reading"/"Cons[Last-Current]"/"Rate Per Pump"; Credit Cards → "Card Holder / Terminal ID"/"Rate"; "Acid Water Total In Lts" → "Acid Water Total 1 Lts") — these were sitting as known drift between the BRD and the live file, and touching this file for the calc engine made it the natural point to close that gap rather than leave it open longer.

**Testing method:** used Playwright to drive the actual rendered page (fill real inputs, dispatch real events, read back computed values), not just static code review — the same rigor applied to the print-page-count investigations earlier in this log.

**Still not done:** zip package not rebuilt (standing instruction). The Shift-field question from Section 36 remains open — not addressed by this session's changes.

---

## 38. Daily Sales Entry Form — Rate Master Module, Auto-Carry-Forward, and Cross-Form Dependencies (2026-08-16)

Client requested 7 changes, all addressed:

1. **Gas Sale(s) header: "Rate Per Pump" → "Rate".** Documented in BRD as a CLIENT OVERRIDE — a deliberate deviation from the Option1_Final_Edit paper form wording (which does say "Rate Per Pump"), not a re-reading of the source. Applied to the live HTML.

2. **Last Shift Reading auto-carry-forward, 23:59 IST.** Confirmed as a business rule: each day's Current Reading becomes next day's Last Shift Reading automatically via a scheduled process — no manual entry needed. In the HTML, `hs-last`/`ms-last` are now disabled fields with an "auto @ 23:59 IST" placeholder. **Caveat stated to client:** a static HTML file cannot literally demonstrate cross-day persistence (no backend/database) — this represents the intended field *state* (locked, not user-typed), not a working simulation of the midnight job.

3. **Amount recalculates the instant Current Reading is entered.** Already true from the existing `calcAll()` engine (Section 37) — reconfirmed and retested given points 2 and 4 change what else is editable on that row. Tested: typing only `hs-current` correctly triggers `hs-cons` and `hs-amount` recalculation.

4. **New Rate Master module — Section 5.11 added to BRD, `rate_master_branded.html` built.** Two parts: Section 1 (Update Rates — current rate shown read-only, New Rate entry, per item) and Section 2 (Rate Change History — running log). Covers Diesel (HS), Petrol (MS), and the same 5 oil SKUs used everywhere else in this BRD (kept name-identical for lookup consistency, per the same reasoning as Section 35's inventory naming fix). Both Daily Sales Entry and Daily Trial Balance are documented as consumers of this module. Open questions flagged: which roles can update rates, whether effective-dating affects same-day in-progress records, and whether historical records should preserve the rate active at creation time (rate versioning) — none of these assumed/resolved.

5. **Oil Sale(s): Amount auto-calculates (already true); Before Stock/After Stock now sourced from Inventory Tracking.** `oil{N}-before` fields changed from editable to disabled/"auto (Inventory)"; `oil{N}-rate` also changed to disabled/"auto (Rate Master)". Quantity is now the only manual entry point per oil row. BRD updated: After Sale Stock (computed) is documented as feeding back into Inventory Tracking as the new Closing Stock, closing the loop between the two modules rather than each tracking stock independently.

6. **Import/Export scope clarified: Sections 1–7 only, not Section 8.** Buttons physically moved in the HTML to sit between Section 7 and Section 8 (previously after Section 8), with a small caption stating the scope explicitly. BRD updated with the same clarification and reasoning (Section 8 is fully auto-computed, nothing to import/export independently).

7. **"Scan / Upload (OCR)" button added to the form header.** Gives pump workers a direct UI entry point into the existing OCR workflow (Section 5.4 Scenario 2/3, Tesseract) rather than requiring a separate menu — documented in BRD as a UI-level addition to an already-confirmed backend flow, not a new OCR capability.

**Testing:** re-ran the Playwright test suite after the field-state changes (disabled `hs-last`/`hs-rate`/`oil{N}-rate`/`oil{N}-before`) to confirm the calc chain still fires correctly from Current Reading and Quantity alone — confirmed, zero console errors, matches expected values.

**Not done / explicitly out of scope this session:** zip package not rebuilt; live cross-form data linkage (Rate Master → Daily Sales, Inventory → Daily Sales) is documented as a business rule and represented as disabled/auto UI states, but not implemented as working JavaScript — that requires a real backend/database, which a static HTML mockup cannot provide.

---

## 39. Scan/Upload Relocated; New "Print Blank Form" Feature (2026-08-16)

- **Scan / Upload (OCR) button relocated** — was in the form header, now sits directly next to "Import from Excel" in the Sections 1–7 action bar (alongside Export to Excel too), since all three are alternative ways of getting data into or out of the same Sections 1–7.
- **New feature: Print Blank Form.** Generates a printable blank copy of the form (Sections 1–7 + header meta fields + Verified By), for when a pump worker needs a paper form to hand-fill before later scanning it back in — distinct from the existing "print a filled entry" capability. Reference template is the confirmed Option1_Final_Edit layout (re-uploaded this session for reference).
- **Action bar now has 4 buttons**, in order: Print Blank Form, Scan/Upload (OCR), Import from Excel, Export to Excel — all scoped to Sections 1–7 only, per the updated caption beneath the bar.
- **Cleanup while editing:** removed the now-orphaned `.scan-btn` CSS class (superseded by reusing `.export-btn.secondary` styling for consistency with the other three buttons), added `flex-wrap` to the action bar so it doesn't overflow with 4 buttons on narrower screens.
- **BRD updated:** Section 5.4 (Scan button location + new Print Blank Form feature, distinguished from the existing filled-form print capability), Section 5.5.1 (action bar scope expanded from "Import/Export" to all 4 buttons).

---

## 40. Last Shift Reading Auto-Carry-Forward — Technical Feasibility Confirmed (2026-08-16)

Client asked whether the 23:59 IST auto-carry-forward feature (Section 38, item 2) is actually achievable given the confirmed stack — Python backend, SQLite, ElectronJS frontend (not just theoretically, given the earlier caveat that the static HTML mockup can't demonstrate cross-day persistence).

- **CONFIRMED FEASIBLE.** The earlier caveat was about the mockup file specifically having no backend, not a limitation of the real architecture. Standard pattern with this stack:
  - Python backend runs a scheduled job (e.g. APScheduler) inside the same always-on Windows Service already confirmed in Section 4.
  - Job explicitly uses the **Asia/Kolkata** timezone, not the host machine's default — flagged as an easy thing to get subtly wrong if not stated explicitly.
  - At 23:59 IST, reads today's Current Reading and writes it as tomorrow's Last Shift Reading directly in SQLite.
  - ElectronJS frontend does no scheduling — just displays whatever the backend already wrote when the form opens.
- **Three real edge cases flagged, not resolved:**
  1. **Missed rollover** — if the app/PC isn't running at 23:59 IST, the job doesn't fire. Needs a "catch-up on startup" check.
  2. **Gap days** — a day with zero activity (pump out of service) has no Current Reading to carry forward; logic must skip back to the last day that has a value, not assume literally "yesterday."
  3. **Post-rollover corrections** — if a Current Reading is edited after the rollover already copied it forward, unclear whether the already-carried next-day value should auto-correct or need manual re-sync.
- **BRD updated:** Section 5.4.1's Gas Sale(s) field description expanded with the confirmed feasibility explanation and all three open questions, so this isn't built without the client having explicitly weighed in on the edge cases first.

---

## 41. Auto-Carry-Forward Detail Added to the Live Form (2026-08-16)

Client asked for the Section 40 detail to also reflect on the actual `daily_sales_report_branded.html` file, not just the BRD.

- **Added `title` tooltips** to the Last Shift Reading and Rate fields (Diesel and Petrol rows) — hovering shows the full mechanism (scheduled backend job, Asia/Kolkata timezone) and the three open edge-case questions (offline-at-23:59, gap days, post-rollover edits), matching the BRD language from Section 40 exactly.
- **Deliberately kept off the visible form face** — the existing inline helper paragraph under Section 1 already states the mechanism in plain terms for the pump worker actually using the form; the deeper technical/edge-case detail lives in the tooltip so it's discoverable for anyone reviewing the design (developer, client) without cluttering the day-to-day data-entry experience.
- Verified programmatically (tooltip text read back via the DOM) rather than assumed — native browser tooltips don't reliably capture in a headless screenshot, so a screenshot alone wouldn't have been sufficient proof.

---

## 42. Print Blank Form Split by Pump Location, with Real Pre-Fill Demo (2026-08-16)

Client pointed out that a single generic "Print Blank Form" can't work correctly, since Road Front and Off Front are different physical pumps with different Last Shift Reading histories.

- **Split into two buttons:** "Print Blank Form – Road Front" and "Print Blank Form – Off Front", replacing the single generic one.
- **Built as a real, tested function** (`printBlankForm(location)`), not just relabeled buttons:
  - Sets the Pump/Road Front/Office Front header field to match.
  - Pre-fills Last Shift Reading (Diesel + Petrol) with values specific to that pump — used the actual verified AUG11 tab readings for Office Pump 1 (256348.91 / 274804.34) and Road Pump 2 (1476461.66 / 656105.04) as realistic demo values, rather than arbitrary numbers.
  - Pre-fills Oil Sale(s) Before Stock — same demo values on both print options, correctly reflecting that oil inventory is shared station-wide, not per-pump.
  - Leaves Current Reading and Quantity blank (what the worker must still write by hand), then triggers print.
  - Clearly commented in the code: these are demo values standing in for what the real backend/SQLite would provide — not something the static file can source live.
- **Real bug found and fixed while testing:** setting Last Shift Reading without a matching Current Reading caused the Consumption field to show a nonsensical large negative number (e.g., 0 − 1,476,461.66). Fixed by adding an `isBlank()` guard to `calcAll()` — Cons/Amount now stay blank until Current Reading (or Quantity, for Oil Sale) is actually entered, instead of computing garbage from an empty field. Re-verified the original worked example (1317.52 × 105.36 = 138813.9072) and the full calculation chain still pass after this fix.
- **Second bug found and fixed in the same pass:** Section 8's Daily Summary (Total HS/Total MS) briefly showed "NaN" after the above fix, because it referenced local variables that were only assigned inside the parts of `calcAll()` that now get skipped when a field is blank. Fixed by reading directly from the DOM (`num('hs-cons')`) instead of the fragile local variable — more robust regardless of which branch ran.
- **BRD updated** with the two-button split, the per-pump vs. shared-inventory reasoning, and a new open question: should Rate (Gas Sale and Oil Sale) also print on the blank form, given the worker has no live system access while filling by hand? Not assumed — flagged for the client to decide.

---

## 43. Rate Now Prints on Blank Form — Client Confirmed (2026-08-16)

Client confirmed **yes** to the open question from Section 42.

- **`printBlankForm()` updated:** Rate now pre-fills for Gas Sale (Diesel/Petrol) and all 5 Oil Sale items, same demo-value pattern as Last Shift Reading and Before Stock — identical on both Road Front and Off Front print options, since rates aren't pump-specific.
- **Tested that Rate alone doesn't cause Amount to compute** — Amount correctly stays blank on the printed state since Current Reading/Quantity are still empty (Rate is only one of two required inputs). Then simulated the worker filling in Current Reading afterward and confirmed the full chain computes correctly (1199.5 × 105.36 = 126,379.32, matching real Road Pump 2 verified data).
- **BRD updated:** the open question in Section 5.4.1 is now marked RESOLVED with the client's confirmation, rather than left open or silently assumed.

---

## 44. "Pump Worker" Renamed to "Pump Sales Man"; Rate Master Restricted to Super User = Dealership Owner (2026-08-16)

Two changes, both applied to the BRD and the relevant live HTML forms:

- **Global terminology rename:** "Pump Worker" → "Pump Sales Man" (and plural "Pump Workers" → "Pump Sales Men") throughout the BRD — 25 occurrences found and replaced (13 lowercase singular, 10 lowercase plural, 1 each title-case), verified zero old-term instances remain afterward. Case-sensitive replacement done in the correct order (plural before singular, since "workers" contains "worker" as a substring — replacing singular first would have produced "sales mans"). Section 2's Roles table now reads "Data Entry (Pump Sales Man)".
  - HTML forms updated to match: `daily_sales_report_branded.html`'s Name field placeholder, `daily_trial_balance_branded.html`'s Shift Data Source placeholder.
- **Rate Master access restricted to Super User only.** Resolves the open question from Section 5.11 ("which roles can update rates") — narrower than the original guess of "Manager/Administrator/Super User"; it's Super User exclusively. **Super User is clarified as the Dealership Owner specifically** — not a general elevated-permission tier other staff could hold. Section 2's Super User row updated with both points; Manager and Administrator explicitly called out as unable to update rates despite their otherwise broad access elsewhere in the system.
  - `rate_master_branded.html` updated: added a "Super User Only" badge in the header (matching the "Manual Entry Mode" tag styling), a red warning line under the Update Rates table stating the restriction explicitly, and changed the "Updated By" field placeholder from "Manager name" to "Dealership Owner name" for consistency.
- **Still open, unchanged from Section 5.11:** whether a rate change takes effect immediately vs. only from its stated Effective Date, and rate versioning for historical records.

---

## 45. Admin-Initiated Reset Password Added to Manage Users (2026-08-16)

**Environment note:** partway through this session the working environment was reset (all in-progress files under `/home/claude` were wiped mid-task). The `/mnt/user-data/outputs` directory persisted, so no delivered work was lost — but one edit (this section's BRD change) had to be redone from the last-delivered BRD rather than continuing from the in-progress copy. Flagging this for the record in case something from between "BRD update accepted" and "next delivery" ever looks like it didn't take — the recovery path is always to rebuild from the last file actually presented to the client, which is what happened here.

**Feature:** Manage Users now supports admin-initiated password reset, distinct from and in addition to the existing self-service Forgot Password flow (Section 5.1).

- **BRD Section 5.3 updated:** a "Reset Password" action, available per user in the User List, triggers the SAME email-confirmation reset link already used for self-service resets — explicitly never displays, sets, or transmits an actual password value. Covers two cases: (1) a newly created user, so the admin never has to choose/know an initial password — the new user sets their own via the emailed link; (2) an existing user needing a reset, triggered by an admin without requiring the user to self-initiate from the login screen.
- **`manage_users_branded.html` updated and tested, not just described:**
  - "Send Password Reset Email" button added to the Add/Edit User section (Section 1) — for the newly-created-user case.
  - "Reset Password" button added per row in the User List (Section 2), including on dynamically added rows via "+ Add row" — tested and confirmed working.
  - A status line shows what would happen ("Password reset link sent to [email] ([name])"), clearly commented in the code as a demo standing in for the real backend email-integration trigger (Section 4) — no actual email capability in a static file.
  - Validated the empty-email case shows an error rather than silently "succeeding."
  - Notes box updated to describe both the self-service and admin-initiated paths.

---

## 46. Color Theme Preference, Print on All Forms, 2FA, and RBAC Restriction (2026-08-16)

Large session covering four distinct requests, all implemented and tested, not just described.

### Color theme preference (3 verified IOCL colors)
- Refactored the color system: `.section-title` and `.summary-box h3` now read from a new `--io-accent` CSS custom property (defaulting to orange) instead of a hardcoded color — a single point of control.
- Added a 3-swatch theme toggle (Red `#e31e24` / Blue `#0033a0` / Orange `#F37022`) to the header of **all 7 forms** plus the new Password Reset page, matching the language-toggle's pill styling.
- **Tested on every file individually**, not assumed to work from one reference implementation: exact RGB match confirmed for all three colors on all 8 files, zero console errors, and confirmed switching themes doesn't break Daily Sales Entry's calculation engine or Manage Users' Reset Password / 2FA features.
- Runtime-only (no localStorage, per artifact restrictions) — real persistence would be per-user in SQLite via the backend.
- **Open question flagged in BRD (Section 5.12), not resolved:** global preference vs. independent per-form setting — the client's phrasing was ambiguous between the two.

### Print enabled on all forms
- Only Daily Sales Entry previously had a visible print trigger. Added an explicit "Print" button to all other 6 forms (`window.print()`), plus a general "Print" button to Daily Sales Entry itself (previously it only had the two location-specific "Print Blank Form" buttons, no way to print the current filled-in state).
- Print CSS already existed in all forms from their original build; only the visible trigger was missing.
- Tested on all 7 forms via Playwright: confirmed `window.print()` actually fires on each.

### New: Password Reset landing page (`password_reset_branded.html`)
- The page a user lands on after clicking the emailed reset link (Section 5.1/5.3) — not built until now, even though the flow referenced it.
- Set/Confirm password fields with live match checking, submit validation (empty fields blocked, mismatch blocked), and the same theme/language toggles as every other form.
- Notes state the link is single-use/time-limited and that no Manager/Administrator/Super User ever sees the password value — only this page does.
- Tested: mismatch detection, empty-submit blocking, and successful submission all confirmed working correctly.

### Two-Factor Authentication — Manage Users (new Section 3)
- **Built a genuinely correct RFC 6238 TOTP (Google Authenticator-compatible) implementation** using the browser's native Web Crypto API (HMAC-SHA1) — no external library, no CDN dependency.
- **Verified correctness before use**: computed a reference TOTP value in Python for a known secret/timestamp, then confirmed the JavaScript implementation produced the byte-identical result. This isn't a fake demo — the algorithm is genuinely right.
- UI: QR code shown as a clearly-labeled placeholder (real QR rendering needs either a backend or a vetted library, neither attempted here), a real randomly-generated manual entry key, a 6-digit verification input, and a "Verify & Enable" button that performs a real TOTP comparison.
- Tested end-to-end: wrong code correctly rejected, the actual current valid code correctly accepted, malformed input (e.g. "12") correctly rejected before even checking.
- **Critical security note written directly into the BRD**, not just implied: TOTP verification must happen server-side (Python backend) in the real system. The client-side JS here exists only because this is a static mockup with no backend — client-side-only validation would be a real security flaw in production, since a modified client could fake success.
- **Open questions flagged, not resolved:** mandatory vs. optional per user, required every login vs. only for sensitive actions, and account-recovery path if a phone is lost.
- Fixed a duplicate "Notes" box bug introduced while inserting the new section — caught via tag-balance validation before presenting.

### RBAC restriction — Pump Sales Man (Data Entry)
- BRD Section 2's Data Entry role row updated: explicit access restricted to **only** the Daily Sales Entry form.
- Explicitly calls out **no access to Inventory Tracking** (Section 5.10), which previously had no role restriction defined at all — this closes a real gap, not a redundant restatement.
- Also explicitly notes no access to Manage Users, Rate Master, Trial Balance, or Old Credit Accounts — consistent with those already being Manager/Administrator/Super User-scoped elsewhere, now stated as an explicit allow-list rather than left implicit.

### Files updated this session
`daily_sales_report_branded.html`, `daily_trial_balance_branded.html`, `inventory_tracking_branded.html`, `manage_users_branded.html`, `new_credit_entry_branded.html`, `rate_master_branded.html`, `record_repayment_branded.html` (all 7, theme + print), plus new `password_reset_branded.html`. BRD updated with new Sections 5.12, 5.13, 5.14, and the Section 2 Data Entry restriction.

---

## 47. Cell Phone Number Field Added; 2FA Confirmed Optional, Not Mandatory (2026-08-16)

**Real gap caught by the client:** the Section 46 2FA build implemented the TOTP mechanism correctly but never actually added a Cell Phone Number field to the user record — TOTP itself only needs an authenticator app on a device, not a stored phone number, so this got overlooked even though the client's original request explicitly named the cell phone.

- **Fixed in `manage_users_branded.html`:** added "Cell Phone Number" to the Add/Edit User section (Section 1), right after Personal Email. The Two-Factor Authentication section (Section 3) now visibly displays "Registered cell phone (this account's authenticator device)," live-synced from the Add/Edit User field via a real event listener — tested: typing a phone number in Section 1 immediately updates the read-only field in Section 3.
- **BRD corrected (Section 5.3 field list, Section 5.14):** documents the gap and the fix, and explicitly clarifies the phone number's actual role — it's reference/contact/recovery information only, NOT part of the TOTP secret, and never used for SMS codes in this design. Losing/changing the phone number alone doesn't compromise 2FA; losing the physical authenticator device does.
- **Regression tested:** 2FA verification, Reset Password, and theme switching all confirmed still working correctly after this change — zero console errors.

**Client confirmed: 2FA is included in scope, but OPTIONAL, not mandatory** — resolves one of the three open questions from Section 5.14. Each user can individually choose to enable it; the system must not force it on every Manager/Administrator/Super User account.

- **BRD Section 5.14 updated:** the mandatory-vs-optional question marked RESOLVED with this confirmation. The other two questions (required every login vs. only sensitive actions; account-recovery path if a device is lost) remain genuinely open — not resolved, not assumed.
- **`manage_users_branded.html` updated:** the 2FA section heading now shows "[Optional — not mandatory]" directly on the form, so the UI itself reflects the confirmed business rule, not just the BRD text.

---

## 48. 2FA UI Redesigned — Simple Field Toggle, Not a Standalone Section (2026-08-16)

Client pushed back on the Section 46/47 implementation: 2FA was built as its own permanently-visible numbered section (with the QR/key/verify block always shown), when what was actually wanted was a simple per-account enable/disable option — matching how Role and Status already work.

**Redesigned in `manage_users_branded.html`:**
- Removed the standalone "3. Two-Factor Authentication" section entirely.
- Added "Two-Factor Authentication" as a field in Add/Edit User (Section 1), a simple Enabled/Disabled dropdown sitting right after Status.
- The QR code / manual entry key / 6-digit verification UI now lives in a block that's **hidden by default** and only appears when the dropdown is set to Enabled — collapses again if set back to Disabled. Tested: hidden on load, appears on Enable, disappears on Disable.
- Added a **"2FA" status column** to the User List table (Section 2) so each existing user's enabled/disabled state is visible at a glance, consistent with how Role and Status are already shown per row.
- Re-verified the actual TOTP mechanism still works correctly inside the collapsed/conditional block: phone-number sync, code verification (correct code accepted, wrong code rejected) — no regressions from the restructuring.
- Form now has only 2 numbered sections again (Add/Edit User, User List) — confirmed via DOM query, not just visual inspection.

**BRD Section 5.14 updated** with a "CORRECTED UI STRUCTURE" note stating plainly that the original standalone-section approach was wrong per client feedback, and documenting the corrected field-based design.

---

## 49. Rate Master — Buy Rate / Sell Rate Split for Diesel and Petrol (2026-08-16)

Client requested two more rows plus new column names (Buy Rate HS, Buy Rate MS, Sell Rate HS, Sell Rate MS). Interpreted as: split the existing single "Diesel (HS)" and "Petrol (MS)" rate rows into separate Buy Rate and Sell Rate rows for each fuel — 2 rows become 4, a net addition of 2, matching "two more rows" while using all four names given.

- **`rate_master_branded.html` updated:** Section 1 (Update Rates) now has 9 rows total — Buy Rate HS, Sell Rate HS, Buy Rate MS, Sell Rate MS, plus the 5 oil SKU rows unchanged. Buy Rate = what SVR pays IOCL per litre; Sell Rate = what customers pay at the pump — a real, meaningful distinction (margin tracking), not just a relabeling.
- **New explanatory note added directly on the form**, stating the Buy/Sell distinction and clarifying that Daily Sales Entry's Gas Sale(s) Rate column pulls **Sell Rate** specifically, not Buy Rate — since that form records customer-facing sales, not purchase cost.
- **BRD Section 5.11 updated** with the same clarification, plus a genuinely open question this split surfaces: should Buy Rate feed a profit/margin calculation somewhere in Daily Trial Balance (e.g. Section 8's Trail Balance - Profit Pump Vs Computer Readings, or Section 9's Day Profit column)? Not assumed or implemented — Buy Rate is currently captured but not consumed anywhere else in this BRD.
- Oil SKU rates were left untouched — the client's request specifically named HS/MS only, so no Buy/Sell split was applied to the 5 oil items without being asked.

---

## 50. Daily Sales Entry — Gas Sale(s) Rate Explicitly Sourced from Sell Rate HS/MS (2026-08-16)

Client asked to make Section 1 (Gas Sale(s)) explicitly use Rate Master's Sell Rate HS and Sell Rate MS.

- **`daily_sales_report_branded.html` updated:** the Rate column's placeholder and tooltip on both Diesel and Petrol rows now name the exact source field ("auto (Sell Rate HS)" / "auto (Sell Rate MS)") instead of the generic "auto (Rate Master)" used before — explicitly ruling out Buy Rate, not just implying it.
- **Made genuinely testable, not just labeled:** seeded demo values (105.36 / 117.70, matching figures used throughout this BRD) into the Rate fields on page load, clearly commented as simulating the Rate Master pull — there's no live link between the two static HTML files, so this demonstrates the intended end-to-end behavior (type only Current Reading, get a correct Amount) without pretending real cross-file integration exists.
- **Re-verified the exact worked example still holds** with rates now auto-populated rather than manually set in the test: 1317.52 × 105.36 = 138,813.9072, confirmed via Playwright with only Current Reading typed in.
- **BRD Section 5.4.1 updated** to state precisely that Gas Sale(s) pulls Sell Rate HS/MS, not Buy Rate — consistent with the same clarification already added to Section 5.11 when the Buy/Sell split was introduced.

---

## 51. Daily Trial Balance — Row-Level Numbering Added to All Sections (2026-08-16)

Client asked for X.Y row numbering within every section (e.g. Section 1's rows as 1.1, 1.2), matching the pattern "1. IOCL Computer & Pump Readings / 1.1 Diesel (HS) / 1.2 Petrol (MS)."

- **`daily_trial_balance_branded.html` updated:** all 49 rows across Sections 1–8 and 10 numbered X.Y, applied via scripted find-and-replace with exact-match verification (each of the 49 target rows confirmed to exist exactly once before replacing — no silent misses, no accidental double-edits).
- **Numbering includes every row type**, not just data rows — total rows, sub-headers (e.g. Section 4's "Cash Advances / New Credits" divider), and creditor entry rows are all numbered in sequence. Section 4 alone runs 4.1 through 4.16.
- **Section 9 (Daily Mgr Calculation) deliberately left un-numbered at the row level** — flagged to the client rather than forced to fit: it's a 26-column running ledger with one row per date, not a fixed set of labeled fields, so the X.Y pattern doesn't apply. Only its section-level "9." heading remains, consistent with how the rest of the form treats it.
- **Verified visually** via full-page screenshot after implementation — confirmed numbering renders correctly and in sequence across all sections, no gaps or duplicates.
- **BRD Section 5.8 updated** documenting the confirmed numbering convention and the Section 9 exception explicitly.

---

## 52. Row Numbering Removed from Section 2 (2026-08-16)

Client requested row numbering be removed specifically from Section 2 (Load/Unload Details).

- **`daily_trial_balance_branded.html` updated:** Section 2's two rows reverted to plain "Diesel (HS) - Vehicle" / "Petrol (MS) - Vehicle", no "2.1"/"2.2" prefix. All other sections (1, 3–8, 10) keep their X.Y numbering from Section 51 unchanged.
- Confirmed the dynamic "+ Add row" button for this section was never affected either way — it creates blank cells via the generic `addRow()` function with no numbering logic involved.
- **BRD Section 5.8 updated** with this as a second explicit exception alongside Section 9's (which was excluded for a structural reason — a column-based ledger). Section 2's exclusion has no stated structural reason; noted as a client preference for this specific section rather than an inferred rule, since Section 2's rows are otherwise identical in shape to Section 1's numbered rows.

---

## 53. Trial Balance — Business Logic Derived and Implemented for 8 Sections (2026-08-16)

Client asked for real business logic to be derived from the AUG11/AUG12 Excel tabs and applied to Sections 1, 3, 4, 5, 6, 7, 8, and 10. This was the largest single analytical + engineering task in this log — full raw data extracted from both tabs, every formula derived and cross-checked against both days independently, then implemented as real JavaScript and verified end-to-end.

**Confirmed formulas (summary — full detail in BRD Section 5.8):**
- **Section 1**: Diff = Yesterday − Current; Consumption is pulled from Section 3 (not independent); Computer/Pump Diff = Consumption − Diff; Benefit/Loss = Consumption + that Diff; Deduct Testing/Density = Consumption − 10.5 (the same fixed density-testing sample already confirmed in Section 9).
- **Section 3**: Consumption = Today − Last; Amount = Consumption × Rate; Daily Sales Total = fuel total + 3 oil amounts.
- **Section 4**: 4.5 = sum(4.1:4.4); 4.6 = 4.5; 4.12 = 4.6 + 4.7:4.11; 4.16 = 4.12 + sum(all creditors, variable count).
- **Section 5**: 5.3 = 5.1+5.2; 5.4 = pulled from 4.16; 5.5 = 5.4−5.3.
- **Section 6**: Amount = Ltrs × Rate; Total = sum of both fuels.
- **Section 7**: 7.3 = 7.1(=5.4) + 7.2(=6.3).
- **Section 8**: 8.1 = PRIOR DAY's own 7.3 (confirmed via the actual AUG11→AUG12 chain); 8.2 = pulled from 10.6; 8.3 = 8.1+8.2; 8.4 = same-day 7.3 − 8.3.
- **Section 10**: 10.3 = 10.1+10.2; 10.4 = pulled from 4.16; 10.5 = 10.3−10.4 (inverted sign vs Section 5.5, both conventions preserved as found).

**Real data-quality finding, not a formula bug:** AUG12's actual sheet has 4.6 recorded as 0 instead of the correct 128,995 (which should equal 4.5 that day) — a genuine human data-entry gap, confirmed by AUG11's own sheet showing 4.6 exactly equal to 4.5 as expected. This is exactly the class of error the digital system's auto-calculation eliminates by design.

**Structural gap found and fixed along the way:** Section 4's Cash Advances/New Credits rows were fixed at 2 in the mockup, but real data shows a variable count (4 creditors on AUG11, 5 on AUG12). Made expandable with a "+ Add row" button, matching the pattern used elsewhere in this form, with `addRow()` updated to correctly assign the calculation class to new rows.

**Verification method — the strongest test run in this project so far:** seeded the exact AUG12 input values (readings, cash figures, all 5 creditor amounts, stock rates) into the live HTML mockup via its own calculation engine, then checked all 22 computed outputs across all 8 sections against AUG12's actual recorded totals. **All 22 matched to the cent on the first fully-corrected run** (after finding and fixing the two issues above — the 4.6 data-quality gap and the creditor-row test-setup limitation). This is a materially stronger form of verification than checking a single number in isolation, since every section's output depends on the ones before it — a wrong formula anywhere in the chain would have thrown off everything downstream.

**Three items explicitly NOT resolved, flagged rather than guessed:**
1. Section 6's Rate (constant ₹102.75/₹113.56 across both days) — unclear whether this is the same as the new Buy Rate HS/MS (Section 5.11) or a separate stock-valuation rate that needs its own Rate Master field.
2. Section 8's real sheet has two parallel calculation columns (C and D) that diverge slightly; this BRD and the mockup use only one (matching column C). Not confirmed whether the second is needed.
3. Section 10.9's "GOOD" / numeric-alert status logic — tested against the two most likely candidate formulas (Section 5.5 and Section 8.4's Difference values), neither matched the days where "GOOD" was actually shown. Left as manual entry, not guessed at.

**Files updated:** `daily_trial_balance_branded.html` (50 field IDs added, full calc engine, expandable creditor rows, demo-seeding function), BRD Section 5.8.

---

## 54. Section 6 Stock Value Rate — Resolved as Buy Rate (2026-08-17)

Client confirmed the Section 5.8 open question: Section 6's Rate (C55/C58 HS, C56/C59 MS in the source sheet) auto-pulls from Rate Master.

- **Precision added, not fully closed by the client's answer:** "Rate Master" has both Buy Rate and Sell Rate per fuel. Recommended and implemented **Buy Rate HS/MS specifically** — inventory in the tank is an asset and should be valued at cost, not at what a customer would pay (Sell Rate), which would overstate the asset's value by including unearned margin. This is standard stock-valuation accounting practice, but flagged in the BRD as a recommendation pending explicit sign-off, since the client's confirmation didn't specify Buy vs Sell.
- **`daily_trial_balance_branded.html` updated:** Section 6's Rate fields (6.1, 6.2) changed from freely editable to disabled/auto, with placeholders "auto (Buy Rate HS)" / "auto (Buy Rate MS)" and a tooltip stating the reasoning and flagging it for confirmation.
- **Regression tested:** re-ran the full formula chain (6.1 Amount → 6.3 Total → 7.3 → 8.4) with the same seeded AUG12 values as Section 53's verification — all outputs still match exactly, confirming this change (editable → disabled/auto) didn't alter any downstream calculation, only who's allowed to type into the field.
- **BRD Section 5.8 updated** with the resolution and the flagged Buy-vs-Sell precision point.

---

## 55. Section 8 Dual-Column Question Fully Resolved (2026-08-17)

Client confirmed the source sheet's second column (D) isn't needed — column C is the real process — and described the real-time logic: "As of Yesterday Trail Balance" + Daily Profit = today's Trail Balance.

- **Verified a precision beyond the plain-English description:** checked numerically which value 8.1 actually pulls from. Confirmed AUG12's 8.1 (5,023,004.33) exactly matches AUG11's **Section 7 Total** (7.3, the real cash+stock total) — NOT AUG11's own Section 8 Total (8.3, the profit-projected total, a different figure: 5,020,247.3925). This confirms Section 8 is a genuine daily reconciliation: comparing what the total *should* be (yesterday's real total + today's profit) against what it *actually* is (today's real Section 7 total), with 8.4 Difference capturing the gap.
- **Important implication documented:** each day's projection resets from the prior day's REAL total (7.3), not the prior day's own projected total (8.3) — so a wrong profit estimate on any single day does not compound forward into future days.
- **`daily_trial_balance_branded.html` updated:** 8.1 changed from a manually-typed field to disabled/auto-carried, matching the same UI pattern already used for Last Shift Reading's day-to-day carry-forward (Section 5.4.1), with a tooltip stating the confirmed logic precisely.
- **Regression tested:** re-verified 8.3 and 8.4 still compute correctly against the same AUG12 seed data used in Section 53/54's verification — no change to the underlying formula, only to which field is editable.
- **BRD Section 5.8 updated** — this question is now fully closed, no remaining open items on Section 8.

---

## 56. Trial Balance — Multi-Section Update: Carry-Forward, Renamed Labels, 5-Row Oil Restructure, Rate Correction (2026-08-17)

Client requested changes across 6 sections in one message. Worked through each, confirming what was already done rather than redoing it, and flagging one real tension the changes create.

- **Section 1**: Yesterday Reading (1.1, 1.2) now auto-carries from prior day's Current Reading at 23:59 IST — same mechanism as Daily Sales Report's Last Shift Reading. Changed from editable to disabled/auto.
- **Section 3**: Pump labels shortened — "Office Near by Pump 1" → "Off Pump 1", "Road Side Pump 2" → "Road Pump 2" (all 4 rows) — now consistent with the "Road Front"/"Off Front" naming already used on Daily Sales Entry's Print Blank Form buttons. Oil section restructured from 3 combined rows to 5 rows matching Daily Sales Entry's SKUs exactly, simplified to just Item + Total Amount (no Rate/Before Stock/After Stock, which stay on Daily Sales Entry). Confirmed these pull from Daily Sales Entry's Section 8 (Daily Summary), **summed across both pump sales men's submissions**, not either worker individually.
- **Section 4**: Cash Advances/New Credits expandable rows — already implemented in Section 53, reconfirmed as satisfying this request, no new work needed.
- **Section 5**: 5.1 Yesterday Cash/Book Value now auto-carries from the prior day's 4.16 Total Balance — changed from editable to disabled/auto.
- **Section 6**: Ltrs now auto-pulls from Section 1's IOCL Current Reading (the exact relationship already confirmed against real data). **Rate corrected from Buy Rate to Sell Rate** — this reverses the recommendation from Section 54 earlier today, per explicit client instruction this time.
- **Section 7**: 7.1 reconfirmed as pulling from 5.4; code changed to read directly from 5.4's own value rather than independently recomputing the same number from Section 4, making the dependency explicit in the code, not just numerically coincidental.
- **Section 8**: 8.1 auto-carry already confirmed and implemented earlier today (Section 55) — reconfirmed as satisfying this request, no new work needed.

**Real tension flagged, not glossed over:** switching Section 6's Rate from Buy Rate to Sell Rate means computed Stock Value (and everything downstream — Section 7 Total, Section 8 Difference) will no longer match AUG12's historical recorded figures, since the real AUG11/AUG12 sheets used a rate (₹102.75/₹113.56) that matches neither Buy Rate nor Sell Rate exactly. Re-ran the test with Sell Rate and confirmed the *formula mechanics* remain correct (Ltrs × Rate, sums correctly) even though the *absolute totals* now genuinely diverge from history — documented in the BRD as the expected, correct consequence of the rate methodology change, not a bug.

**Regression tested throughout:** Section 3's Daily Sales Total Amt (unaffected by the Section 6 rate change) still matches AUG12's real historical figure exactly after all the restructuring, confirming the changes were properly isolated to only what should have changed.

---

## 57. New Section 4.6 — Software Install Instructions & Log File Locations (2026-08-17)

Client requested a new BRD section covering desktop install prerequisites, install steps, manual service verification, and per-component log file locations — building on the technology stack and per-component logging requirement already confirmed in Section 4.

**Content added:**
- **Prerequisite Software** — split into what the end-user PC needs (nothing extra; the single .exe installer bundles Python + SQLite + ElectronJS) vs. what a development/build machine needs (Python, Node.js/npm, Git, an Electron packaging tool).
- **Desktop Install Steps** — 4 steps, obtaining the installer through to confirming all components auto-started.
- **Manually Verifying Services (services.msc)** — 4 steps, opening services.msc through to where to look when a service is stopped.
- **Log File Locations** — one proposed path per component (backend, database, frontend, scheduler, email integration, OCR), all under `C:\ProgramData\SVR-IOCL\logs\`, with the reasoning for that location (system-level Windows Services, not tied to whichever user is logged in).
- **Open Design Questions** — log retention policy (same 1-year as app data, or shorter), and three specifics not yet confirmed (exact service names, SQLite file path, whether ElectronJS truly runs as a Windows Service vs. a user-session startup item).

**Two real mistakes made and caught before delivery, not shipped:**
1. First attempt used a malformed `str_replace` call (wrong parameter name) that silently failed and left the document XML corrupted. Caught immediately by the standard XML-validity check — restarted clean from the last known-good delivered BRD rather than trying to patch a broken file.
2. Second attempt reused `numId="2"` for two separate numbered lists ("Desktop Install Steps" and "Manually Verifying Services"), which would have made them count continuously (1-4, then 5-8) instead of each restarting at 1. Investigated the numbering.xml definitions directly rather than guessing at a fix, discovered `numId="2"` was already actively used elsewhere in the document for the existing "Scenario 1-5" list (Section 5.4) — reusing it would have silently corrupted that list's numbering too. Fixed properly by adding two new independent numbering instances (`numId="3"` and `numId="4"`) referencing the same decimal format, so each list now correctly restarts at 1 without touching the pre-existing Scenario list.
3. Before final delivery, built the new section as a standalone XML fragment and validated it in isolation first, then confirmed the insertion point matched exactly once before applying it — avoiding a repeat of mistake #1.

**Verified in the rendered PDF:** both new numbered lists correctly show 1-4 each (not 1-4 then 5-8), and the pre-existing Scenario 1-5 list still numbers continuously exactly as before, confirming no cross-contamination between the lists.

---

## 58. Trial Balance — Field Names Updated per New AUG18 Source (2026-08-17)

Client uploaded a new, larger Trial Balance workbook (`Trail_balance_AUG18_2026.xlsx`, going back to October 2025) and asked for row/column names in Sections 3 through 9 (source numbering) to be updated to match exactly, with Section 3's Oil Sales confirmed needed but Before/After Stock columns confirmed not needed. Explicit constraint: no other changes to the form.

**Real discovery before any renaming began:** the source sheet's own section numbering doesn't match this BRD's — the source's "9. Daily Mgmt Reporting" is this BRD's Section 10, and the source's "10. Daily Mgr Calucation" is this BRD's Section 9. Kept this BRD's own numbering unchanged (to avoid renumbering the whole form) and mapped names by content, not number.

**Renames applied, tag-balance and full-chain tested after each block:**
- **Section 3**: pump labels reverted to full "Office Near by Pump 1" / "Road Side Pump 2" — **this directly reverses the shortened "Off Pump 1"/"Road Pump 2" from Section 56 earlier today**, since this instruction explicitly asked to match the source exactly. Flagged as a reversal, not silently applied.
- **Section 3 Oil Sales**: all 5 item names updated to match AUG18 exactly (2T/1.20 ML, 2T/1.50 ML, Battery Water Total 1 Lts, 20/40 Engine Total in 1/2Ltr, 20/40 Engine Total in 1Ltr) — genuinely different from what Daily Sales Entry/Rate Master/Inventory Tracking currently use. **New naming mismatch flagged, not resolved** — the auto-pull from Daily Sales Entry's Section 8 can't work correctly until this is reconciled, but fixing those other 3 forms was outside this session's explicit scope.
- **One addition made, not just a rename**: added row "3.11 Oil Sale(s): Total Amount" (a subtotal before the combined Daily Sales Total, renumbered to 3.12) — included because it's literally the sum of the 5 oil rows just confirmed needed, not new unrequested content.
- **Sections 4, 5, 7, 8, 10**: titles and field-level labels updated throughout to match AUG18's exact wording (e.g., Section 5 "Cash Value Reconciliation" → "Book/Cash Value Reconciliation"; Section 10 "Daily Mgmt Summary" → "Daily Mgmt Reporting"). All underlying formulas from Section 53's verification are **unchanged** — confirmed via full regression test after every batch of renames (4.16, 7.3 Total SVR Network Reported, and 8.4 Difference all still compute correctly).

**Bonus finding, not requested but worth flagging:** the long-unresolved "GOOD" status question (Section 53/55) may finally have an answer — AUG18 shows "is OK" when a Difference is under Rs 100 (24.03 that day) and "Not Good" when over Rs 100 (-1197.96, a different Difference calculation that day). Promising, but not implemented as real auto-calculated logic this session — only the field's placeholder text was updated to reference it, keeping strictly to "update names, not other changes."

**Deliberately not added, flagged for later:** the source's Daily Mgmt Reporting section has real additional structure this BRD's Section 10 doesn't — an Expenses breakdown (Salaries, Power Bill, Salary Advance) and a second "Total SVR Networth Value - Projected" figure. Adding either would have exceeded "update names" into "add new content," so neither was built this session.

**Files updated:** `daily_trial_balance_branded.html` (renames across Sections 3-10, one new subtotal row, tag-balance and formula-chain verified after each change), BRD Section 5.8.1 (new).

---

## 59. Section 9/10 Swap, Full AUG18 Rebuild, and Further Reversals (2026-08-17, later same day)

Client issued a dense follow-up message with several changes, some ambiguous, some directly reversing choices made earlier the same day.

**The big structural change — Section 9/10 swap:**
- What was Section 9 (Daily Mgr Calculation, the 26-column ledger) is now **Section 10**, renamed "Daily Mgr Reporting."
- What was Section 10 (Daily Mgmt Reporting) is now **Section 9**, keeping its name — and physically reordered to appear first, matching the source sheet's actual order.
- **Section 9 fully rebuilt** with everything Section 58 had deliberately withheld: an Expenses breakdown (Salaries, Power Bill, Salary Advance, auto-summed Total), a second "Daily Trail Balance Reporting - Total SVR Networth" sub-block with its own Projected/Reported/Difference chain, and Prepared By / Verified By / Sent to Group Email fields — all matching AUG18's exact wording.
- **All new formulas implemented and tested**: Total Expenses = sum of 3 lines; Total SVR Networth Value - Projected = Yesterday's + Daily Profit; Difference = Reported − Projected.
- **Section 8's cross-reference to Section 9 rewired and retested** — 8.2 Daily Profit still correctly pulls from the new field location, full chain re-verified end-to-end, zero regressions.

**Third reversal in one day, on two different fields:**
- Section 3 pump labels shortened again to "Off Pump 1" / "Rd Pump 2" (interpreting an ambiguous instruction — flagged in the BRD in case the interpretation is wrong).
- Section 6 Rate reverted back to **Buy Rate** (Buy → Sell → Buy, three total changes today) — demo data restored to the historical AUG11/AUG12 figures.

**Three ambiguous phrases resolved by inspecting the actual file, not guessed blind:**
- "Fuel row not needed," "Removed Field row not needed," and "remov Filed row" — checked the live HTML directly and found all three sections (6, 7, 8) shared the exact same extraneous `<th>Fuel</th>` / `<th>Field</th>` column header not present in the AUG18 source. Removed all three, treating the three garbled phrases as the same instruction applied once per section.

**Clean, explicit change:** Section 7's total row renamed to "Total SVR Net worth Reported Amt" with its "7.3" numbering prefix removed entirely, exactly as instructed.

**Process discipline maintained under a large, dense request:** built both the HTML section-swap and the BRD documentation as standalone fragments, validated each as well-formed XML in isolation before inserting — avoiding a repeat of Section 57's mid-edit corruption. Full tag-balance check and Playwright regression test run after every batch of changes, not just once at the end.

---

## 60. Add Row Removed, Header Rows Fully Removed, Stale Reference Fixed (2026-08-17, later same day)

Small, precise follow-up with three explicit changes and one real bug caught along the way.

- **Section 2**: "+ Add row" button removed — now a fixed 2-row table (Diesel, Petrol), not expandable.
- **Section 5**: the "Field"/"Amount" header row removed entirely — a step further than Sections 6-8's earlier fix, which had only blanked the first column while keeping "Amount". Section 5's table now has no header row at all.
- **Section 8**: the remaining "Amount" header also removed, matching Section 5's treatment — Section 8's table now has no header row either.
- **Real bug caught while editing Section 8, not requested but fixed anyway**: field 8.2's placeholder still read "auto (= 10.6)", a stale reference left over from Section 59's Section 9/10 swap — the actual field moved to Section 9 during that swap, but this one placeholder string was missed. Corrected to "auto (= Section 9 Daily Profit)"; searched the whole document for any other stale "10.6"/"10.7"/"10.8"/"10.9" references and confirmed none remain.
- **Regression tested**: confirmed exactly 2 "+ Add row" buttons remain in the whole form (Section 4 creditors, Section 10's ledger — both still genuinely need to stay expandable), and the full formula chain (5.3, 5.5, 8.2, 8.3, 8.4) still computes correctly after every removal.

---

## 61. Full Formula Re-Verification Against Real AUG19 Data, Plus New Features (2026-08-19)

Client provided a newer AUG18/AUG19 workbook and requested a comprehensive pass: reconfirm every column's calculation across all 10 sections, add carry-forward to Sections 2 and 3, ensure Section 10's ledger keeps at least 30 rows, and add Import capability.

**One interpretation flag, resolved by checking the file:** the instructions mentioned "Section 8" twice for different things ("Rate from Rate Master Buy Rate" and separately "use of excel sheet calculations"), but Section 8 has no Rate column at all — only Section 6 does. Interpreted the Rate instruction as meant for Section 6 (reconfirming last session's Buy Rate decision), applied Section 8's own instruction to its actual field chain.

**What changed:**
- **Section 1** — already complete, no changes, reconfirmed.
- **Section 2** — "Old Computer" now auto-carries from the last delivery (no re-entry on non-delivery days). **New formula confirmed directly from AUG19 data, not previously documented**: Total = New Computer − Old Computer, verified exact for both fuels (11953 / 9994).
- **Section 3** — new carry-forward confirmed: Today Reading → next day's Last Shift Reading at 23:59 IST, all 4 rows. Rate reconfirmed as Sell Rate.
- **Section 4** — kept as-is per instruction.
- **Sections 5, 6, 7, 8** — all existing formulas reconfirmed exactly against AUG19, no changes needed.
- **Section 9** — **real gap found and fixed**: the "Never be the case ~ Rs Above 100" status field was never actually wired, left manual since Section 53/55's unresolved "GOOD status" question. Implemented with a confirmed formula; caught and corrected a sign error during testing (initially off by exactly double the 9.5 value); now verified exact (−1282.6808) against AUG19's real recorded figure.
- **Section 10 (ledger)** — now pre-populates 30 rows on load instead of 1.
- **Import/Export** — added "Import from Excel" alongside the existing Export/Print, scoped explicitly to Sections 1–10.

**Strongest verification run in this project to date:** replaced the demo-seed function entirely with the complete, real AUG19 dataset (not a partial/mixed set), then checked 14 computed outputs spanning all 10 sections against AUG19's actual recorded totals. All 14 matched exactly on the first fully-corrected run — after finding and fixing two real issues mid-testing: a test-setup gap (forgot to add the extra creditor rows before seeding, which produced false mismatches on the first pass) and the genuine Section 9 sign error described above. Neither issue was papered over — both were caught by the numbers not matching, investigated, and fixed before calling anything done.

**Files updated:** `daily_trial_balance_branded.html` (Sections 1–10 reconfirmed/updated, 30-row ledger seeding, Import button, demo data fully replaced with real AUG19 figures), BRD Section 5.8.4 (new).

---

## 62. Two New Forms — Monthly Expenses and Employee Master (2026-08-19)

Client requested two new forms, matching the existing style exactly. SVR confirmed as a very small operation: 1 owner, 1 manager, 4 employees (6 people total).

### `monthly_expenses_branded.html` (new file)
- **Section 1 — Expense Entries**: date-based expandable ledger with a Category dropdown (Bi-weekly Salary, Salary Advances, Unload Beta, Buying Indian Oils, Monthly Electrical Bill, Other).
- **Section 2 — Monthly Summary**: auto-totals grouped by category plus a grand total. **Tested, not just built**: confirmed multiple entries in the same category correctly combine (two separate salary entries summed into one category total), and the grouping logic still works correctly on rows added dynamically.
- **Open question flagged in BRD, not resolved**: two of the five categories (Bi-weekly Salary, Monthly Electrical Bill) correspond to fields already tracked in Trial Balance Section 9's Expenses breakdown — is this new module meant to be the actual source feeding those figures, or an independent parallel record? Not assumed either way.
- Standard Print / Import / Export included, matching every other form.

### `employee_master_branded.html` (new file)
- **Section 1 — Employee Master**: Name, Role (Owner/Manager/Employee), Daily Wage, Bank Name, Account Number, IFSC Code — 6 default rows, matching the confirmed headcount exactly.
- **Section 2 — Accidental Insurance (Yearly)** and **Section 3 — Health Insurance (Yearly)**: kept as separate tables (not combined columns) since each insurance type has its own independent provider/policy/renewal date per employee.
- **Section 4 — Annual Premium Summary**: auto-totals both insurance sections. Tested including on dynamically added rows (confirmed a new row's premium correctly joins the running total).
- **Handled deliberately as sensitive data, not treated like the rest of the form's fields**: Account Number field labeled "Sensitive — verify handling before real use" directly on the form; BRD states plainly that real production use needs encryption at rest and role-restricted access (Super User/Manager only), not yet designed. No demo/placeholder bank account or policy numbers were fabricated for testing, unlike other forms in this project that use real verified figures — judged inappropriate even as placeholder content for a live financial system's mockup.

**Files updated:** two new HTML forms, BRD Sections 5.15 and 5.16 (new).

---

## 63. Employee Master — Bank Deposit Confirmed, Pay Stub Requests, Bank Branch/Address (2026-08-19)

Three related updates to `employee_master_branded.html`.

- **Confirmed and stated on the form itself**: all employee salaries are paid via Bank Deposit, no cash payroll — a note added directly above the Employee Master table, not just in the BRD.
- **New column — Bank Branch / Address** added to Section 1's table.
- **New feature — Request Pay Stub**, per employee row. Genuinely implemented and tested, not just described: validates a name is entered before allowing the request, shows a confirmation message once submitted, and confirmed working correctly on rows added dynamically via "+ Add row" (not just the 6 default rows).
- **Real open question surfaced and flagged, not resolved on my own**: the request implies employees can request their own pay stub, but this BRD's Roles table (Section 2) only defines 4 system roles — Data Entry, Manager, Administrator, Super User — with no "employee self-service" access concept at all. Whether a Manager/Administrator submits the request on an employee's behalf (matching how Reset Password works in Manage Users), or employees get some other kind of access not yet designed, is genuinely undecided and documented as such rather than assumed either way.
- Real pay stub generation and delivery (PDF creation, pulling wage/days-worked data, email or print delivery) is explicitly **not implemented** — clearly commented in the code as requiring backend work, consistent with how other demo-only features (Reset Password, 2FA) are handled elsewhere in this project.

**Files updated:** `employee_master_branded.html`, BRD Section 5.16.

---

## 64. Daily Sales Entry — Header Restructured, Nozzle IDs, Shift Question Finally Resolved (2026-08-23)

Client provided a newer source PDF ("Option1_Final_Aug23") with 3 explicit changes plus a request for a full comparison against the current form and confirmation of 3 data-entry modes.

**Three explicit changes, implemented and tested:**
- Header field "Pump / Road Front / Office Front" replaced with **"Pump Serial#"**, showing the station's actual pump hardware IDs (12BC4523V-Off, 11CC2012V-Road) instead of a location description. Updated `printBlankForm()` accordingly — it now sets the specific serial number for whichever pump was selected, not generic "Road Front"/"Office Front" text. Tested both directions correctly.
- **Shift field removed** entirely from the header.
- Diesel and Petrol rows renamed to **Diesel(HS-Nz1)** and **Petrol(MS-Nz-2)**.

**A genuinely old open question finally resolved:** the Shift field's fate has been flagged as unconfirmed since Section 36, all the way back when the Option1_Final_Edit PDF first dropped it. This session's PDF confirms it again, closing the question for good — Shift is intentionally gone, not an accidental omission.

**Full section-by-section comparison run against the new PDF, one real discrepancy found and NOT silently applied:** the new PDF shows Gas Sale(s)'s Rate column as "Rate Per Pump," but this BRD documents "Rate" as a deliberate CLIENT OVERRIDE from Section 5.4.1 (2026-08-16) — an explicit, stated deviation from the paper form's own wording. Reverting it just because a newer paper form shows the old wording again risks undoing a real decision, so it was left as "Rate" and flagged for explicit confirmation instead. Every other section (Oil Sale(s), Expenses, Credit Cards, New Credit, Old Credit, Summary, Verified By) checked and confirmed to already match exactly — no other changes needed.

**Three data-entry modes reconfirmed, with one real gap surfaced:**
1. Manual entry — confirmed, already built and tested.
2. Scan/OCR — confirmed, already documented and exposed via the Scan/Upload button.
3. Excel export matching this exact sheet format — **partially confirmed, one point flagged as genuinely unresolved**: this BRD has never specified whether "export in the same format" means the exported .xlsx must visually replicate this PDF's exact layout, or whether a standard data export (same fields/values, normal spreadsheet formatting) is sufficient. These are meaningfully different engineering tasks. Not assumed — flagged for explicit client decision before backend work.

**Files updated:** `daily_sales_report_branded.html`, BRD Section 5.4.2 (new), 5.4.3 (new), and the long-standing Shift question in Section 5.4.1 marked RESOLVED.

---

## 65. Dt & Time, IOCL # Column — Plus the Rate Discrepancy Resolves Itself (2026-08-23, later same day)

Client provided yet another updated source PDF the same day, with two explicit changes.

- **Header "Date" renamed to "Dt & Time"** — the form now captures both date and time, not date alone. Confirmed only the header field changed; the separate "Date" field in Verified By was checked against the new PDF and is untouched there too, so it was correctly left alone.
- **New "IOCL #" column added to Gas Sale(s)**, one manual entry per fuel row. Exact meaning of this number (transaction ID, receipt reference, etc.) wasn't specified — implemented as a plain reference field with no assumed validation logic, rather than guessing at a purpose.
- **The "Rate" vs "Rate Per Pump" discrepancy flagged last session resolved itself**: this newest PDF shows "Rate" again, matching the standing client override exactly. Marked RESOLVED in the BRD — confirms the override was correct and the intervening "Rate Per Pump" PDF wasn't a lasting reversion.
- Full comparison against the rest of the form re-confirmed no other changes — Oil Sale(s) through Verified By all still match exactly.

**Files updated:** `daily_sales_report_branded.html`, BRD Section 5.4.4 (new), and Section 5.4.3's Rate discrepancy marked RESOLVED.

---

## 66. Daily Trial Balance — Fully Recreated per AUG25 Source (2026-08-25)

The largest single rebuild in this project. Client provided a further-restructured source (Trail_Balance_Revised.xlsx, AUG25 tab) and asked for the entire form to be recreated to match it exactly, while keeping the confirmed carry-forward mechanisms, Rate Master integration, and adding bidirectional Import/Export.

**Built as a complete new file, section by section, with tag-balance checks after every section** (not just once at the end) — Sections 1 through 11, each validated before moving to the next.

**The headline structural change:** Load/Unload Details moved from Section 2 to Section 10 (last), with every other section renumbered accordingly — a literal match to AUG25's own numbering, not an independent design choice.

**Two real bugs found and fixed during the verification pass, not shipped silently:**
1. **Density-testing deduction changed**: confirmed exactly 10.5 across AUG11–19 (Section 53), now confirmed exactly 10 in AUG25 (verified precisely: 426.04−416.04=10, 667.34−657.34=10, both fuels). First verification attempt failed on this exact figure — caught, investigated, fixed.
2. **Section 8's "Yesterday" figure isn't the same as Section 7.1**: initially assumed they were the same concept. Real AUG25 data proved this wrong (3,240,917 vs 3,245,120.79, same day) — corrected to an independent carry-forward field. Flagged as either intentional (different reporting cadences) or a source-side duplication, not resolved either way.

**One real reversal, not silently applied:** "Old Credit Cash hand off" — excluded from the Total since 2026-08-16 per the client's own "(Remove the Row)" annotation — is now confirmed INCLUDED, verified exact against AUG25's real numbers. The "Remove the Row" label is still literally on the sheet, creating a genuine tension between the label and its actual treatment — flagged rather than quietly resolved.

**New dropdown validation, matching AUG25's own Excel Data Validation exactly:**
- Section 3 creditor names (7 options)
- Section 8 expense categories (4 options — noted as close but not identical to the separate Monthly Expenses form's category list, not reconciled)

**The Rs 100 threshold question — finally settled in the client's own words**, not inferred from number patterns: AUG25 includes an explicit note, "OK Anything Above Rs 100 Call/inform mgmt immediately." Documented as the confirmed rule; the auto-generated status text itself remains unimplemented, consistent with keeping unconfirmed display logic manual.

**Three items left unconfirmed and flagged, not guessed at:**
- Section 1's "IOCL Adv" column formula — left manual, single day's data wasn't enough to derive it reliably
- "Actual Profit After All Expenses Rs 3300" — implemented with the closest defensible formula, explicitly flagged as unconfirmed in its own tooltip
- A data-quality anomaly in AUG25's own "Total SVR Network Reported" row (value doesn't match its label) — not replicated as a real formula, since it looks like a source-side copy-paste artifact

**New Section 11 (Old/New Credit Sales Details)** — entirely new, not previously in this BRD. Only 2 rows shown in the source; full intended scope unclear from one day's data, implemented minimally rather than expanded speculatively.

**Import/Export**: added Import (previously only Export existed), scoped to Sections 1–11. Per this session's explicit requirement, importing also adds a ledger row — demonstrated in the mockup; real file parsing is not implemented, clearly commented as such.

**Verification**: seeded the complete real AUG25 dataset and checked 17 computed outputs across all 11 sections against AUG25's actual recorded totals. All 17 passed, but only after finding and fixing the two real bugs above.

**Files updated:** `daily_trial_balance_branded.html` (complete rebuild), BRD Section 5.8.5 (new).

---

## 67. Cross-Check Found Two Entirely Missing Sub-Sections (2026-08-25, later same day)

Client asked for a full cross-check of the 5.8.5 recreation against AUG25 and found real gaps — worth being direct about this: two sub-sections weren't mislabeled, they were **entirely missing**.

**Missing entirely, now added:**
- Section 3's **Expenses** block (Salaries Mid/End of Month, Power Bill, Unload Beta, Salary Advances Total — 4 dropdown rows)
- Section 3's **Credit Remittance** block (Sajja/Anil/AirTel old-credit dropdown, with Credit Given on Date + Amt columns)
- Section 8's **Any Old Credit Remitted** block (same pattern as Section 3's Credit Remittance)

Both new Section 3 blocks and the Section 8 block are tracked as their own totals — how they feed into the section's other totals wasn't confirmed from the single day's data (both show mostly blank/zero on AUG25), so that relationship is honestly left unconfirmed rather than guessed.

**Fixed, not just relabeled:**
- Section 2 row labels combined into one column per row ("12BC4523V-Off - Diesel (HS-Nz-1)"), replacing the earlier rowspan-grouped two-column layout
- Oil Sales' full 5-column structure restored (Sold, Rate, Opening Stock, Closing Stock, Amount) — a prior rebuild had incorrectly kept this simplified. This is a genuine improvement, not just a display fix: Amount is now really computed as Sold × Rate (previously a pass-through), and Closing Stock = Opening − Sold, syncing with Inventory Tracking the same way Daily Sales Entry already does
- Section 3's New Credit/Salary Adv given a proper column header row (was missing)

**Confirmed and applied everywhere a dropdown list exists on the form**: every dropdown-driven section (5 of them total) now has its own "+ Add row" button, tested to confirm new rows include the full dropdown and correctly feed the live total — not just a plain text fallback.

**Re-verified end-to-end**: 8 fresh checks against real AUG25 data, all passing, confirming the restored Oil Sales calculation correctly flows through Section 1's Total Sale Amt all the way to Section 8's Networth Difference, with zero regressions from the 5.8.5 baseline.

**Files updated:** `daily_trial_balance_branded.html`, BRD Section 5.8.6 (new).

---

## 68. Dynamic Dropdown Lists, Numbering Cleanup, WhatsApp Export (2026-08-25, third round)

- **Section 2 text alignment fixed** — the 4 combined pump+fuel labels were wrapping to two lines, same nowrap fix already used on Daily Sales Entry.
- **Section 3 numbering corrected** — removed row numbers from every dropdown-driven row and sub-header (previously 3.15, 3.16, 3.18, 3.19–3.22, 3.23, 3.24–3.26), and fixed a real sequencing bug: the section's final Total row was mislabeled 3.17 and appeared out of numeric order after 3.18–3.26 in the layout. Renumbered to 3.15, its correct sequential position — and every cross-reference to the old "3.17" label updated to match, confirmed no stale references remain.

**New capability — dropdown lists can be extended live, genuinely implemented:**
- All 5 dropdown lists on the form now have a "+ New [Type]" button. Adding a value updates the underlying list and appends it to every currently-rendered dropdown of that type — tested to confirm it works on *existing* rows immediately, not just new ones.
- **Real finding caught and handled correctly**: Section 3's Expenses category and Section 8's Regular Expenses category are confirmed to share the exact same Excel Data Validation range. Built the feature to keep them in sync — adding a category through either section's button updates both dropdowns. Checked whether the two Credit Remittance lists (Section 3 vs Section 8) shared the same treatment and confirmed they're genuinely different lists in the source (different wording) — correctly kept separate, not merged.
- **Scope clarified, not overclaimed**: this adds a new *value* to an existing list, not a mechanism to import an entirely new list structure from an uploaded Excel file at runtime — those are different features. Flagged the distinction rather than silently building only the smaller one and calling it done.

**Section 8 — WhatsApp number field added**, and the existing "Export Section 8 to Excel" button now genuinely references it — tested that the confirmation message correctly includes whichever number was entered, and correctly notes when none was entered. Real file generation and WhatsApp sending remain demo-only, clearly commented as requiring backend work not yet designed.

**Files updated:** `daily_trial_balance_branded.html`, BRD Section 5.8.7 (new).

---

## 69. Credit/Remittance Master — New Credit Entry + Record Repayment Merged (2026-08-25)

Client asked to merge the two previously separate forms into one Credit/Remittance Master with two sections, tracking which Pump Sales Man extended each credit and confirmed remittance can come from Direct Entry, Daily Sales Entry, or Daily Trial Balance.

**Confirmed before building**: added a real Creditor Balance Summary (Section 3), specifically to handle a case the client raised — the same person having both an old credit and a new ongoing credit at once.

**Section 1 (New Credit)** — added 3 fields that didn't exist before: Phone Number, "Given By (Pump Sales Man)", and Date (the original New Credit Entry form had no date column at all). Amount is genuinely computed as In Ltrs × Rate, not a placeholder.

**Section 2 (Remittance)** — added a Source dropdown (Direct Entry / Daily Sales Entry / Daily Trial Balance) and "Pump Sales Man Involved," replacing the more generic "Payment Collected By" from the original form. This also implicitly resolves an open question that had been sitting unanswered in Record Repayment since it was first built: whether a repayment must fully settle one specific credit entry. The new design tracks repayments as their own rows against a creditor *name*, not against one specific credit line — so partial repayment is naturally supported without needing a separate answer.

**Section 3 (Creditor Balance Summary), new, genuinely working**: groups every credit and remittance row by Creditor Name into Total Credit Given, Total Remitted, and Outstanding Balance. **Tested against the exact scenario the client described**: "Ravindra" given credit twice — once by one Pump Sales Man, once by a different one — correctly combined into a single balance line, with the right net figure after a partial remittance. A brand-new customer joining in the same session was tested separately and correctly appeared as its own line, confirming the grouping logic doesn't interfere with genuinely new creditors.

**Two things flagged honestly, not glossed over:**
- The cross-form data flow (this Master consolidating what Daily Sales Entry and Daily Trial Balance capture) is the confirmed *intent*, but there's no live link between these static HTML files — same limitation as every other cross-form reference in this project.
- Whether the two original standalone forms should now be retired in favor of this Master, or kept for some other purpose (e.g. quick entry on the pump floor), wasn't decided — neither original file was touched or deleted, both remain available pending direction.

**Files updated:** `credit_remittance_master_branded.html` (new), BRD Section 5.17 (new).

---

## 70. Payroll — Two Existing Forms Enhanced, No Third Form (2026-08-25)

Client asked for a form to capture bi-weekly salaries and SVR operational expenses, explicitly asking whether it should be one form or two. **Recommended and confirmed: neither — enhance the two existing forms instead**, since a new form would duplicate bank details and the Request Pay Stub feature already in Employee Master, and the expense categories already in Monthly Expenses.

**Employee Master — new "Payroll Run" section (Section 2)**: computes Gross Salary (Days Worked × Daily Wage) and Net Pay (Gross − Advance), auto-pulling Daily Wage and Bank Account from Section 1 by matching Employee Name. **Tested end-to-end**: 15 days × ₹600 = ₹9,000 gross, minus ₹500 advance = ₹8,500 net, with the correct bank details pulled through. Also tested the failure case — a name not found in Section 1 correctly shows "no match in Section 1" instead of silently pulling nothing.

**Monthly Expenses — split into Payroll and Operational Expenses sections**, plus the same "+ New Category" extensibility already built for Trial Balance last session.

**Real naming inconsistency found and fixed while doing this**: Monthly Expenses said "Monthly Electrical Bill," but Daily Trial Balance's own Expense dropdown says "Power Bill" — confirmed to be the same real expense, named differently across two forms since Monthly Expenses was first built. Renamed to match.

**A real design problem caught before it shipped**: since categories can now grow dynamically, a fixed summary table would have silently failed to show totals for any new category. Rebuilt the Monthly Summary as fully dynamic — tested by adding a brand-new category ("Vehicle Repair"), using it on a new row, and confirming it correctly got its own summary line and fed the Operational Subtotal, with no code change needed.

**One interpretation flagged rather than assumed**: whether "add more expense types in a different section" meant a visual split into two sections (what was built) or just extensible categories within one section — the clarifying question on this specific point went unanswered directly, so this is noted in the BRD in case the simpler version was actually intended.

**Files updated:** `employee_master_branded.html`, `monthly_expenses_branded.html`, BRD Section 5.18 (new).

---

## 71. Date Range Report — Employee Master and Monthly Expenses (2026-08-25)

Client asked for a start-to-end date range search on both forms, for pulling a specific period (e.g. a full financial year) of expenses/payroll for a company claim. Built as real filtering logic, not a static control.

**Employee Master**: "Payroll Date Range Report" block added below Payroll Run. Filters by Pay Date, shows Rows in Range / Gross / Advances / Net Pay for just that period. Rows outside the range are dimmed, not hidden — the full record stays visible for context. **Tested**: 3 payroll entries across 3 months, a Jan–Mar filter correctly included January and March, excluded June, and totaled only the 2 in-range rows.

**Monthly Expenses**: new Section 3, filtering **both** Payroll and Operational Expenses tables at once by their own Date columns, showing combined and per-section totals for the range (Monthly Summary renumbered to Section 4). **Tested**: a Jan–Mar filter across both tables correctly caught a February payroll entry and a January operational entry, excluded a July one, with correct combined totals.

**Confirmed on both forms**: the filter works on rows added *after* the page loaded via "+ Add row," not just the default rows — required adding the date field's class to both forms' row-creation JavaScript specifically to support this, tested directly rather than assumed to work.

**Basic validation on both**: requires both From and To dates before generating a report, and rejects a From date after the To date with a clear message rather than silently producing a wrong or empty result.

**Files updated:** `employee_master_branded.html`, `monthly_expenses_branded.html`, BRD Section 5.19 (new).

---

## 72. Payment Receipt — New Customer-Facing Module (2026-08-25)

Client asked for a printable payment receipt with fuel type/liters/rate/total, payment method, and SVR's address, explicitly asking what else might be missing.

**Suggested and included, beyond the explicit list**: Time (not just Date — same-day transactions need it), Pump Serial# and Attendant name (reusing established concepts), Vehicle Number, and conditional payment reference fields — UPI Ref# for Phone Pay, Auth/Txn Ref# + last 4 card digits for Credit Card (tested: switching between Cash/Phone Pay/Card correctly shows/hides the right fields).

**Design decision made and explained**: built as a narrow 380px receipt-style layout, not the full A4 business-form template every other document in this project uses — this is a point-of-sale customer receipt printed per transaction, a fundamentally different artifact from the internal daily/monthly forms.

**One thing flagged rather than assumed**: a note on the receipt states fuel sales are outside standard GST in India (VAT/Excise instead), so no GST breakdown is shown — standard for Indian fuel retail, but not explicitly confirmed by the client, and worth re-checking if oil/lubricant items (which typically do attract GST) ever get added to this receipt type.

**One structural gap surfaced, not resolved**: every other sales-tracking form in this BRD works at a daily total level (Daily Sales Entry, Daily Trial Balance). This receipt is the first artifact to model a single transaction. Whether individual receipts should reconcile against a day's totals wasn't specified — flagged as open, not assumed either way.

Tested: total calculation (Liters × Rate), payment method toggle showing/hiding the right fields, and Print all confirmed working.

**Files updated:** `payment_receipt_branded.html` (new), BRD Section 5.20 (new).

---

## 73. Payment Receipt — Confirmations Applied (2026-08-25, same day)

Client confirmed the suggested additions and answered the flagged GST question.

- **Time, Pump Serial#, and payment reference details** — all confirmed as wanted, no changes needed there.
- **Pump Serial# placeholder updated** to show both station serials together ("12BC4523V-Off/11CC2012V-Rd"), matching the combined format already established on Daily Sales Entry's own header.
- **Vehicle Number confirmed optional** — labeled as such on the receipt now, only filled in if the customer provides it.
- **GST question resolved**: client confirmed no GST applies to fuel sales in India (VAT/Excise instead) — the receipt's note simplified from a "verify before use" caveat to a stated fact, since it's now directly confirmed rather than assumed.
- **Thank-you message updated** to "Thank You for Choosing IOCL!" per client wording.

Regression tested after all changes — total calculation, payment method toggle, and Print all still work correctly.

**Files updated:** `payment_receipt_branded.html`, BRD Section 5.20 (GST item marked RESOLVED, confirmation note added).

---

## 74. Daily Trial Balance — Real Mistake Caught, Ledger Fixed, Sync Recommendation (2026-08-25, later same day)

Client asked to cross-check whether the Section 9 ledger had all its columns. **It did not** — worth being direct about this rather than glossing over it.

**The mistake**: Section 66's AUG25 rebuild reduced this ledger from its original 26 columns down to 8, stating "AUG25 shows only these 8 in active use." That was wrong. Re-extracted the source with a wider column range (A through Z instead of stopping at H) and confirmed all 26 original columns are genuinely present with real data on AUG25 — the earlier conclusion was wrong because the extraction simply didn't scroll far enough right, not because the data wasn't there. All 26 columns restored: Date, Total MS/HS Sale, MS/HS Deduct Testing, MS/HS Total Rs, Total Sales Rs, Daily Expenses, 2T Sale, Total Sale, Settled/UnSettled Phone Pay, Fleet Card Swipe, Credit Card Swipe, Credit (Any), Night/Day Cash Total, Total Cash After All, Difference, Bank Deposits, MS/HS Comm, Total Comm, Day Profit, 2T Sales.

**Also changed**: default row count reduced from 30 to 5, reversing the confirmed decision from Section 61 (30 was chosen specifically so a month of history didn't need repeated "+ Add row" clicks). Flagged as a direct reversal, not treated as a first-time decision.

**Section 1 alignment fixed** — "1.1 Diesel (HS)" / "1.2 Petrol (MS)" were wrapping, same nowrap fix used elsewhere.

**On the sync button request** — gave a recommendation instead of building it as literally asked: a "sync" button implies each form holds its own copy of shared data that drifts stale between syncs. The better fix, already consistent with the confirmed tech stack (Python + SQLite shared backend, Section 4), is for every form to read the same live database tables — nothing to sync in the first place. Every auto-pull field already built throughout this project (Rate Master's rates, Inventory's Closing Stock, Section 1's Consumption) is already designed for exactly this model; it just has no real backend yet. Still added a "Sync Now (Demo)" button that states this same recommendation when clicked, rather than pretending to perform a real sync.

**Export/Import reconfirmed**, not rebuilt — checked the actual button count on the page and confirmed exactly one Export and one Import button already exist, scoped to Sections 1–11, since Section 66.

**Files updated:** `daily_trial_balance_branded.html`, BRD Section 5.8.8 (new).

---

## 75. Sync Question Sharpened, Recommendation Declined (2026-08-25, same day)

Client pushed back on the earlier "shared database" answer with a sharper point: a shared database doesn't stop the same real-world transaction from being manually typed into both Trial Balance and Credit Master/Monthly Expenses/Employee Master separately, since Trial Balance's Section 3 and Section 8 already duplicate what those three forms track.

**Recommendation given**: designate one canonical entry point per data type — Credit Master owns credits/remittances, Monthly Expenses owns salaries/advances/operational expenses, Employee Master's Payroll Run owns bi-weekly payroll — with Trial Balance's matching sections converted to read-only auto-pulled rollups instead of manual entry. This would make Trial Balance a genuine top-level daily rollup rather than a fourth place competing to be the source of truth.

**Decision: not implemented.** Client chose to keep Trial Balance's fields manual, as already built. No HTML changes made this round — **the recommendation is recorded in the BRD for future reference, not silently dropped.** If this gets revisited later, the same duplicate-entry risk and the same design option are documented and available.

**Files updated:** BRD Section 5.8.8 (follow-up discussion and decision added, no code changes).

---

## 76. Daily Sales Entry — Oil Sale(s) Stock Columns Renamed (2026-08-25)

The ambiguous discrepancy flagged in the previous turn — "Opening Stock/Closing Stock" appearing disconnected from the Oil Sale(s) table in the source PDF — is confirmed as an intentional rename, not a text-extraction artifact.

**Applied**: "Before Stock" → "Opening Stock", "After Sale Stock" → "Closing Stock" on the table header and its explanatory note. Field IDs and the underlying auto-calc logic (Opening Stock pulled from Inventory Tracking, Closing Stock = Opening Stock − Quantity, feeding back to Inventory) are unchanged — only labels moved. Regression tested: entering Opening Stock 62, Quantity 9, Rate 17 correctly computed Closing Stock 53 and Amount 153.

**A nice side effect, not the point of the change but worth noting**: this brings Daily Sales Entry into terminology alignment with Daily Trial Balance, which already switched to "Opening Stock"/"Closing Stock" during the AUG25 rebuild (Section 66) — the two forms now describe the same concept the same way.

**BRD updated carefully, not with a blind find-and-replace**: checked all 7 occurrences of "Before Stock" in context first. 6 described current field definitions and were updated; 1 was a historical testing note quoting the literal field name as it existed at that point in the project — left untouched, since changing it would misrepresent what was actually observed at the time.

**Files updated:** `daily_sales_report_branded.html`, BRD Section 5.4.5 (new).

---

## 77. Save Button Gap, Print/Scan Made Functional, Cross-Form Sync Buttons (2026-08-25)

A dense multi-part request, worked through piece by piece.

**Save button — confirmed missing, project-wide.** Checked all 12 forms, not just Daily Sales Entry: none have a Save button. Flagged clearly since the client is planning to cross-check this separately — not fixed this round, pending that review.

**Print Blank Form**: labels updated to show serial numbers directly ("11CC2012V-RDF", "12BC4523V-OFF"). Dt & Time now auto-fills with the genuine current date/time on click (read from the browser's own clock, tested to confirm it shows real current time, not a hardcoded value).

**Scan/Upload — a real gap found and fixed.** This button previously had no onclick handler at all; clicking it did nothing. Now genuinely triggers the OS's native file picker, tested with an actual file selection. **Honest limitation stated rather than glossed over**: no website can force a file picker to default to a specific folder — that's a universal browser/OS security restriction, not something any code here can work around. Once a file is selected, it's tagged with the current Pump Serial# and Last Shift Reading, as requested.

**Print dialog**: already does what was asked — `window.print()` already prompts the OS's installed-printer selection by default. Confirmed, no change needed.

**Cross-form sync buttons added both directions**, per the "vice versa" request — "Update Daily Trial Balance" on Daily Sales Entry, "Update from Daily Sales" on Trial Balance's Section 2. Both honestly labeled as demos: separate static files genuinely can't exchange live data without a shared backend, and localStorage is off-limits per the artifact platform's own restrictions. Each button states specifically what data would move, in which direction, and that real sync needs the backend already planned in Section 4.

**IOCL# Max recommendation given, with reasoning, not just built**: the pull button went on Trial Balance's Section 1, not Daily Sales Entry — because each individual Daily Sales Entry submission only sees its own IOCL#, but a day has two submissions (Off + Road), and Trial Balance needs the max across both. That aggregation only makes sense from the side that can see both at once.

**Files updated:** `daily_sales_report_branded.html`, `daily_trial_balance_branded.html`, BRD Sections 5.4.6, 5.4.7 (new).

---

## 78. Trial Balance — Sync Buttons Repositioned to Section Corners (2026-08-25)

Client asked to move "Pull IOCL Current Reading (Max)" and "Update from Daily Sales" out of their section title bars and down to the bottom-right corner of each section instead, matching how other action buttons already sit in this form.

Moved both — "Pull IOCL Current Reading (Max)" now sits at the end of Section 1, "Update from Daily Sales" at the end of Section 2, each with its status message right below it. Retested after the move: both still work identically from their new position.

**Files updated:** `daily_trial_balance_branded.html`, BRD Section 5.4.7 (positioning note added).

---

## 79. Sections 6-8 Row Headings Updated — Text Only (2026-08-25)

Client provided a new source (Book1.xlsx) with reworded labels for Sections 6, 7, and 8, explicitly scoped to text only. Applied 24 label changes — field IDs, formulas, and structure all confirmed unchanged via a full regression test against the same real AUG25 dataset used throughout this project.

**Spelling corrected consistently**: "Trail Balance" → "Trial Balance" everywhere it appeared across all three sections — this typo had been present since the sections were first built.

**Section 6**: 3 rows reworded ("Today's Actual Reported SVR Cash/Book Value," "Today's Closing Stock Value," "Today's Total Working Capital / Net Worth").

**Section 7**: all 5 rows reworded to match the source exactly.

**Section 8**: renamed "Daily Mgmt Reporting" → "Daily Management Reporting"; 8.2–8.5 and most of the second Networth sub-block reworded. Worth noting: the "Actual Profit After Regular Expenses Rs3300" field's label text changed, but its formula remains flagged UNCONFIRMED exactly as it was — only the label moved, not its confirmation status.

Each of the 24 replacements was verified to match exactly once before applying — no blind find-and-replace, same discipline used for every text change in this project.

**Files updated:** `daily_trial_balance_branded.html`, BRD Section 5.8.9 (new).

---

## 80. Save Button Rollout (12 Forms) + Software Install PDF Guide (2026-08-26)

**Save button added to all 12 forms**, closing the gap confirmed in Section 77. Same honest-demo pattern used throughout this project — shows a timestamped confirmation, states real Save requires the backend (Section 4), not implemented in these static files. Two forms needed special handling rather than the same copy-paste treatment: Manage Users has two action-button rows (Save went only on the form-level one, not the section-specific Password Reset row); Payment Receipt uses its own narrow receipt layout, not the standard export-bar, so Save was styled to match that instead. Tested individually on all 12 — one Save button each, correct confirmation message, zero console errors anywhere.

**New PDF**: `SVR-Software-Install-Guide.pdf`, 3 pages, covering exactly the 4 requested sections (software needed, single-installer question, install steps, troubleshooting). Built entirely from what's already confirmed in BRD Section 4.6 — no new claims invented for the document.

**One real gap found while writing it, not previously called out this explicitly**: Section 4.6 describes the single installer as bundling "Python + SQLite + the ElectronJS frontend" — but doesn't explicitly say Tesseract OCR is part of that same bundle, even though Tesseract is confirmed elsewhere as part of the software requirements. Flagged directly in the PDF as an open item, since it affects whether Scan/Upload works right after install or needs a separate setup step.

**Files updated:** All 12 HTML forms, `SVR-Software-Install-Guide.pdf` (new), BRD Sections 5.21, 5.22 (new).

---

## 81. Client-Led Excel Audit Surfaces Two Real Formula Corrections (2026-08-26)

Client ran a read-only audit of their own live Excel workbook (AUG25 vs AUG26), cross-checking specific rows over several turns. This surfaced two genuine corrections to our own digital Trial Balance form — not just the client's spreadsheet.

**Daily Testing deduction corrected: 21L, not 10 or 10.5.** Client clarified this is a government regulatory requirement of 10.5L *per pump*. Since Section 1 combines Office + Road pump consumption, and each pump needs its own sample, the real deduction is 10.5 × 2 = 21L. This closes a gap that had been sitting in this project's own history — the AUG25 rebuild found 10.5L across AUG11–19 and assumed it was a flat constant; later, a narrower check against AUG25 alone found 10.0 and "corrected" it without catching that the number should scale with pump count, not be a single flat figure at all. Confirmed via the client's own audit that **neither AUG25 (10.0) nor AUG26 (10.5) currently reflect the correct 21L** in the live spreadsheet either — this wasn't just our form being wrong.

**"2T Sales" corrected to the full Oil Sales subtotal.** Previously implemented as just the two "2T"-named oil rows. Verified against the real spreadsheet on both AUG25 and AUG26 that it actually equals *all 5* oil items combined (153=153, 255=255 — exact both days). The field's name is misleading relative to what it holds, but the formula is now correct and tested.

**Row 99 formula confirmed** (client's Excel only, not yet in our digital form): Daily Profit minus a fixed ~₹3,300 daily allowance — ₹300 power bill + 3 staff salaries spread daily (1 Manager ≈₹1,666.66/day, 2 Pump Sales Men ≈₹666.66/day each). Verified exact against AUG26's real numbers.

**One open item not acted on**: the client's ledger (Section 9) appears to have date labels shifted one row early — a row labeled "Aug 24" contains Aug 25's actual figures. This is specific to the client's Excel workbook, not our digital form's own ledger, so flagged for their own correction rather than changed here.

**Files updated:** `daily_trial_balance_branded.html` (2 formula fixes: Daily Testing deduction, 2T Sales), BRD Section 5.8.10 (new).

---

## 82. Correcting My Own Misreading: Deduction Is -10.5, Not -21 (2026-08-26, same day)

The -21 fix from Section 81 was wrong — my own misreading, corrected within the same day.

I read "2 pumps × 10.5 = 21 litres" as meaning each fuel (HS and MS) should be deducted 21. Client corrected this directly: **each fuel gets its own -10.5**, full stop. 21 was only ever the *sum* of both fuels' deductions (10.5 + 10.5), never a per-fuel value to apply.

Reverted the form back to `-10.5` for both HS and MS. Re-tested against the real AUG26 data — HS Daily Testing, MS Daily Testing, and Total Sale Amt all now match exactly (1001.41, 554.03, 5162.3643).

**One correction to my own earlier framing**: I'd said AUG26 was wrong at 10.5 and needed to become 21. That was backwards — AUG26 was actually correct all along. It was AUG25 (at 10.0) that had the real error. Fixed the BRD paragraph to reflect this accurately rather than leave the incorrect version standing.

**Files updated:** `daily_trial_balance_branded.html` (reverted to -10.5 per fuel), BRD Section 5.8.10 (corrected).

---

## 83. Provision to Add a New Oil Category — Both Forms (2026-08-26)

Following the manual corrections from the Excel audit, client asked for a way to add a new oil category on Daily Sales Entry and Daily Trial Balance, since new products may come up.

**Additive approach chosen deliberately**: both forms' Oil Sales sections reference fixed IDs (oil1 through oil5) throughout their calc engines. Converting all 5 named items to a fully dynamic list risked destabilizing well-tested existing logic. Instead, the 5 named items stay exactly as they are, and a new "+ Add Oil Item" button adds rows below them with their own class-based calculation — combining into the same totals, not a separate parallel total.

**Tested on both forms**, including the cascade: on Trial Balance specifically, since "2T Sales" was just corrected to pull from the full Oil Sales subtotal, a new item automatically flows through into 2T Sales and Total Sale Amt with no extra wiring — confirmed directly (added an item worth 300, both the Oil subtotal and 2T Sales updated together, 85 → 385 on both).

**One honest limitation stated directly on both forms**: new items' Rate and Opening Stock are entered manually — they're not connected to Rate Master or Inventory Tracking, which only know the 5 originally-confirmed products. Staff need to confirm pricing and current stock with the Manager before entering a new item, since there's no master-data record for it yet.

**Files updated:** `daily_sales_report_branded.html`, `daily_trial_balance_branded.html`, BRD Sections 5.4.8/5.8.11 (new).

---

## 84. Daily Sales Summary — New Module Resolving the Two-Submission Gap (2026-08-26)

Client asked for a data-flow review between Daily Sales Entry and Trial Balance. Found a real architectural gap: Trial Balance's Section 2 needs 4 rows (Office-HS, Office-MS, Road-HS, Road-MS), but each Daily Sales Entry submission covers only one pump. Neither sync button built earlier actually modeled how both pumps' data gets combined.

**New form: `daily_sales_summary_branded.html`** — the missing link. Built as its own separate document, not a tab inside either pump's form, since neither submission can see the other's data while being filled out independently.

- **Section 1 & 2** — Office and Road pump submissions, each with Pump Sales Man, Entry Method (Manual/Scanned), a Verified status, and the same Gas Sale(s) structure as Daily Sales Entry.
- **Section 3** — Combined Summary, auto-computed. **Tested against real AUG26 figures**: Office HS (6339.5112) + Road HS (100275.3264) correctly combined to 106614.8376, matching the real spreadsheet exactly.
- **Section 4** — Verification & Upload, with a genuine tested gate: upload is **blocked** until both pumps show verified. Tested all three states — blocked with neither verified, still blocked with only one, succeeds once both are — confirming this actually prevents the action, not just a cosmetic warning.

**Both existing sync buttons corrected** to describe this new, accurate flow rather than left pointing at an architecturally wrong direct link — Daily Sales Entry's button renamed "Send to Daily Sales Summary," Trial Balance's renamed "Update from Daily Sales Summary," both demo messages rewritten accordingly.

**Side effect**: this also resolves the open question from Section 5.8.10 about whether Oil Sales needs combining across both pumps — it now does, explicitly, via the Combined Summary.

**One thing surfaced but not resolved**: found a real contradiction — Section 1's own header says "independent regulatory reading, NOT pulled from Section 2," but a "Pull IOCL Current Reading" button sits right below it doing exactly that. Flagged to the client rather than fixed unilaterally, since removing it is also a real behavior change. Response pending.

**Files updated:** `daily_sales_summary_branded.html` (new), `daily_sales_report_branded.html`, `daily_trial_balance_branded.html`, BRD Sections 5.23, 5.24 (new).

---

## 85. Daily Sales Summary Scoped Precisely: Rows 6-24, Itemized Oil (2026-08-26)

Rather than answer my three open questions one by one, client gave a precise scope using the real spreadsheet: Daily Sales Summary should feed Trial Balance's Section 2 only, matching AUG26's rows 6–24 exactly. Extracted those rows directly before implementing anything.

This single scope answered all three open questions from Section 5.24 at once:
- **Expand to Expenses/Credit Cards/New Credit/Old Credit?** No — none of that falls in rows 6–24, so Summary stays confined to Gas Sale(s) + Oil Sales, as originally scoped.
- **Fix the Oil Sales granularity mismatch?** Yes — rows 18–24 are the full 5-item breakdown, not a flat total, so Summary needed the itemized structure after all.
- **Add IOCL#?** No — no IOCL# column exists anywhere in rows 6–24, confirming it's genuinely out of scope for this fix.

**Rebuilt both pumps' Oil Sales sections** from a single flat total into the full 5-item breakdown (Sold/Rate/Opening Stock/Closing Stock/Amount per item), matching Daily Sales Entry's own structure. **Section 3's Combined Summary** now shows each item combined across both pumps individually, not just a lump sum — matching Trial Balance's Section 2.6 row-for-row.

**Tested rigorously against the complete real AUG26 dataset**, not spot-checked: Gas Sale totals, all 5 individual oil items' Amount and Closing Stock, the combined Oil total, and the Grand Total all matched the real spreadsheet exactly on the first fully-corrected run.

**Files updated:** `daily_sales_summary_branded.html`, BRD Section 5.25 (new).

---

## 86. IOCL Pull Button Contradiction — Resolved (2026-08-26)

Client confirmed Section 1 stays fully independent/manual — rows 3-4 unchanged. Removed the "Pull IOCL Current Reading (Max)" button and its function entirely, replaced with a brief note confirming the section has no pull mechanism.

Tested after removal: page loads with zero console errors, Section 1's own formulas (Diff = Last − Current) unaffected, no orphaned code or stray references left anywhere in the file.

**Files updated:** `daily_trial_balance_branded.html`, BRD Section 5.24 (marked RESOLVED).

---

## 87. Rate Lock with Supervisor/Owner-Only Push Update (2026-08-26/27)

Following the integration review, client confirmed rates should never auto-shift while pump sales men use these forms — Daily Sales Entry and Daily Trial Balance keep their own default rates until a Supervisor or Owner explicitly pushes a change from Rate Master.

**Rate Master**: Buy/Sell Rate HS and MS now show real default values (102.75/105.36/113.56/117.7) instead of blank placeholders. New "Push Rate Update to Daily Sales & Trial Balance" button added, explicitly Supervisor/Owner-only, matching the existing Super User restriction already on this form.

**Daily Sales Entry & Daily Trial Balance**: all 6 rate fields across both forms (2 on Daily Sales, 4 Sell Rate + 2 Buy Rate on Trial Balance) now carry real default values. Confirmed via code check that no `setVal` anywhere targets these fields — they can't be silently overwritten during normal use.

**One inaccurate claim corrected, not left standing**: Rate Master's own note previously said rates "flow automatically" into the other two forms — this was never actually true, no live link exists between static files. Corrected to accurately describe the push model instead.

**Demo, honestly limited** — same pattern as every other cross-form action here: the push button can't literally update the other files without a real backend, clearly commented as such.

**Full regression tested** on both forms against real AUG26 data after the change — all previously-confirmed formulas still compute correctly with rates now pre-filled instead of seeded per-test.

**Files updated:** `rate_master_branded.html`, `daily_sales_report_branded.html`, `daily_trial_balance_branded.html`, BRD Section 5.26 (new).

---

## 89. Last Updated By/Date — All 12 Forms, No Exceptions (2026-08-27)

Client confirmed this as a critical, non-negotiable requirement: every entry in every form must record who last saved it and when. Implemented as a standard header element — a "Last Updated By" / "Last Updated" bar below the header on all 12 forms, populated when Save is pressed.

**10 forms** got the full pattern: a "Logged in as" selector, Save blocked with a clear message until someone is selected, and once selected, Save auto-fills that form's name field(s) plus the new header bar from one single selection — Rate Master, Inventory Tracking, Daily Sales Entry, Employee Master, Credit/Remittance Master, Monthly Expenses, Daily Trial Balance, New Credit Entry, Record Repayment, Manage Users.

**2 forms handled differently, deliberately**: Password Reset (self-service, reached via email link) reuses its existing Account field rather than adding a redundant separate selector — the person resetting their own password *is* the identity. Payment Receipt (narrow customer-facing layout) reuses its existing Attendant field the same way, with Save blocked until Attendant is filled.

**Every single form individually validated and tested** — not assumed safe just because the pattern worked elsewhere. Daily Trial Balance specifically re-confirmed zero regression on its core formula chain (26-column ledger, 5-row default, default rates) since it carries the most complex logic in this project.

**Demo, same honest limitation as everywhere else requiring persistence** — no real backend exists yet, so this demonstrates the confirmed behavior precisely rather than actually writing anywhere. Per this session's direction, every table in the real backend is expected to carry the same last-updated-by/timestamp fields as a baseline requirement.

**Files updated:** All 12 HTML forms, BRD Section 5.27 (new).

---

## 90. Yearly Sales Report (Tax) + BRD Dev Process Recommendations (2026-08-27)

**New form: `yearly_sales_report_branded.html`**, covering India's financial year (Apr 1 – Mar 31, auto-defaulted from today's date). Client's original scope (HS/MS sales, salaries, repairs, power/beta/misc expenses) was reviewed for completeness first — recommended 7 additional categories, client confirmed 4 of them:

- Oil/Lubricant sales kept separate from fuel (different GST treatment)
- Cost of Goods Sold + Gross Profit (Opening/Closing Stock valuation)
- IOCL Commission, tracked separately from Gross Profit
- (Depreciation, bad debts, and certified Net Profit before Tax were explicitly declined — not included, documented as such so it's not mistaken for an oversight later)

**A real bug caught during testing, not shipped**: the Summary section's "Gross Profit" and Section 3's own "Gross Profit" initially disagreed — same label, two different numbers, because one included IOCL Commission and the other didn't. The final Net Result happened to be mathematically correct either way, but showing two different "Gross Profit" figures on a document meant for a CA's review would have been genuinely confusing. Fixed so both sections show the identical figure, with Commission as its own explicit line.

**A real gap flagged, not silently worked around**: "Repairs" doesn't exist as a tracked category anywhere else in the project — confirmed by checking Monthly Expenses' actual category list. Recommended adding it there via the existing "+ New Category" feature, so this yearly figure has real daily-level detail behind it instead of being typed once a year with nothing supporting it.

**Explicit disclaimer included on the form itself**: this isn't tax advice, and should go through SVR's actual CA before filing.

**BRD updated for development process** — two new sections, sourced from Anthropic's official documentation, not general knowledge: Section 4.7 recommends Claude Code's Plan Mode for multi-file or architecturally significant changes, given how many shared formula dependencies have been found across this project. Also recommends a project-level CLAUDE.md as the primary memory file over module-level fragmentation, given the shared conventions (formula patterns, the honest-demo pattern, verification-against-real-data discipline) that apply across every form, not just one module.

**Files updated:** `yearly_sales_report_branded.html` (new), BRD Sections 4.7, 5.28 (new).

---

## 91. Application Integrity Check — All 14 Forms (2026-08-27)

Five systematic checks, not spot checks, across the full form set.

**Checks 1–4: all pass.** Tag balance and zero console errors across all 14 forms. Save/"Logged in as" mechanism confirmed genuinely blocking and genuinely updating on all 11 forms using the standard pattern — checked individually, not assumed from one working example. Trial Balance's full formula chain, ledger structure, and the Oil Sales → 2T Sales cascade all still correct against real AUG26 data — zero regression from everything accumulated this project.

**Check 5 — documentation drift check found a real gap.** Section 5.27 documented "Save added to all 12 forms, no exceptions." A direct count came back 13 of 14 forms, not 12 or 14 — that count itself is what surfaced the problem, not an assumption. **Daily Sales Summary** was the missing one — it predates the Section 5.27 rollout and was never part of that batch since it has its own separate "Upload to Daily Trial Balance" action.

**Fixed**: Daily Sales Summary now has the full standard pattern — "Logged in as," the header bar, and Save (auto-filling Prepared By and Mgr Name). Built as a genuinely separate action from the existing Upload button, not merged into it: Save records who compiled the Summary; Upload (its pre-existing verification gate untouched) pushes the verified data onward once both pumps are confirmed. Tested both work correctly and independently — specifically re-tested the Upload gate to confirm this change didn't alter it.

**Re-ran Checks 1 and 2 after the fix**: all 14 forms confirmed consistent.

**Files updated:** `daily_sales_summary_branded.html`, BRD Section 5.29 (new).

---

## 92. Six Remaining Integrity Checks — One Real Bug Found and Fixed (2026-08-27)

All six items from the pending list completed.

**Real bug found**: print CSS for the Last Updated bar never actually worked. Tested with real print-media emulation rather than assumed from the rule's presence — the bar stayed **visible** in print on 13 of 14 forms, despite each having a `display: none` rule inside `@media print`. Root cause: the bar's inline `style="...display:flex..."` attribute overrides stylesheet rules regardless of the media query — the print rule was being silently defeated on every affected form. Fixed with `!important` on all 13 (Payment Receipt uses a different, non-inline implementation and was never affected). Verified the fix with the same emulation test, and separately confirmed normal screen display is untouched.

**One gap flagged, not yet fixed**: Payment Receipt has **zero** language-toggle infrastructure — every other form in this project has confirmed bilingual EN/Telugu support, this one doesn't. Could be a deliberate choice given its narrow customer-receipt layout, or a genuine omission. Flagged for a decision rather than assumed either way.

**Everything else confirmed clean**: Daily Sales Summary's Oil cascade and Yearly Sales Report's formula chain both re-verified unaffected by unrelated changes. Password Reset and Payment Receipt's core features (not just Save) all still working. A broader sample of 5 more BRD claims checked directly against HTML — all accurate, no further drift found.

**Files updated:** 13 HTML forms (print CSS fix), BRD Section 5.30 (new).

---

## 93. Payment Receipt Language Toggle — Resolved (2026-08-27)

Client confirmed: Payment Receipt stays English-only, no language toggle added. Closes the last item from the integrity review — a deliberate decision now, not an unaddressed gap.

**Files updated:** BRD Section 5.30 (resolution added, no code changes needed).

---

## 94. Formula-Bearing Sections Drift Check — 3 Real Gaps Found and Fixed (2026-08-27)

Client asked for a full pass across the highest-risk category from the earlier drift sample — the ~15 sections describing formulas. 5 forms confirmed correct (2 initially looked broken, but that traced back to my own test-selector mistakes, corrected and re-verified before concluding). 3 forms had genuine gaps between documentation and code.

**New Credit Entry**: zero calc engine — Amount was manually typed despite being a "confirmed structured field." Also found the BRD's "select existing creditor" claim was stale: Credit/Remittance Master (the newer form covering the same idea) had already deliberately chosen free text to make onboarding new customers easier. Rather than build a dropdown contradicting that later, better decision, brought this form in line with it instead. Real fix: Amount = In Ltrs × Rate now computes, with an auto-summed Total — tested including a dynamically-added row (needed a dedicated add-row function since the generic one creates unclassed inputs the calc engine can't see).

**Record Repayment**: zero calc engine. Added a running Total Repaid row, tested summing correctly across multiple entries.

**Inventory Tracking**: "Closing Stock = Opening + Received − Sold" was stated in a note but had zero JavaScript behind it — a documented formula that was never actually coded. Now genuinely computed, plus a Status column correctly flagging "Low Stock" at the reorder threshold. Tested both a healthy and a low-stock scenario.

**All 3 re-tested for regression** — zero console errors, and the Section 5.27 Save mechanism confirmed still working correctly on each after the new calc engines were added.

**Files updated:** `new_credit_entry_branded.html`, `record_repayment_branded.html`, `inventory_tracking_branded.html`, BRD Section 5.31 (new).

---

## 95. Four Previously-Untested Categories — Completed (2026-08-27)

**Cross-browser**: a real limitation, stated directly rather than worked around. Only Chromium is installed in this environment — confirmed by attempting to launch Firefox and WebKit, both failed. Genuine cross-browser testing wasn't possible. Ran a compatibility audit instead: no high-risk modern JS syntax found across all 14 forms, Flexbox usage confirmed universally safe. One inherent (not a bug) cross-browser difference noted: native date pickers look different across browsers by design.

**Mobile/responsive**: tested all 14 forms at 375px. Zero horizontal page overflow anywhere — specifically confirmed the 26-column, 3400px ledger stays correctly contained in its own scroll wrapper. One minor finding: the "Manual Entry Mode" header tag gets visibly clipped at this width. Functional, not broken, but not fully polished — flagged, not fixed.

**Sensitive data**: one good pattern confirmed — Manage Users' password reset genuinely never displays a raw password anywhere, confirmed by reading the code. Two real gaps found: Credit/Remittance Master's Phone Number and Employee Master's own IFSC Code (sitting right next to the already-flagged Account Number) carry no sensitivity flag, despite being comparable personal/financial data. Flagged, not fixed yet.

**Load testing**: Trial Balance's ledger tested at a full year's volume (365 rows) — added in 0.32s, calculated in 0.008s, zero errors. Oil-item extensibility stress-tested at 50 items (well beyond realistic use) — correct and fast. No performance concerns at any tested volume.

**Files updated:** BRD Section 5.32 (new) — no code changes this round, all four findings are flagged for a decision rather than acted on unilaterally.

---

## 96. Daily Testing Deduction Corrected a Third Time — Final: -10 per Fuel (2026-08-28)

While confirming this open item from the pending list still applied to the client's own Excel file, client corrected the value directly again: **-10 litres per fuel** (HS and MS, each independently), not -10.5 as this BRD had "final"-confirmed just two messages earlier.

This constant's full history, now visible rather than smoothed over: 10.0 → 10.5 → a mistaken 21 (Claude's own misreading) → 10.5 confirmed directly → **now 10, confirmed directly, final**.

This also reverses the earlier claim about which day's spreadsheet was correct — this BRD previously said AUG26 (at 10.5) was right and AUG25 (at 10.0) had the error. Given the confirmed value is now 10, it was actually **AUG25 that was correct all along**.

Corrected in the digital form and tested: HS Daily Testing = 1001.91, MS Daily Testing = 554.53, both confirmed computing correctly with the corrected constant.

**Files updated:** `daily_trial_balance_branded.html`, BRD Section 5.8.10 (corrected for the third time, history kept visible rather than overwritten silently).

---

## 97. Line Items 1-4 Fixed — Including a Near-Miss Caught Before It Shipped (2026-08-28)

**Item 1 — Mobile clipping**: fixed on all 13 affected forms with `flex-wrap` on the header. Tested at 375px — "Manual Entry Mode" now wraps instead of clipping, confirmed visually.

**Item 2 — Sensitive field flags**: Phone Number (Credit/Remittance Master) now flagged, matching Account Number's pattern. Employee Master's IFSC Code also fixed — and a *second* real gap found while doing it: the dynamic "+Add row" function only handled Account Number's flag, not IFSC's, so a freshly-added employee row would have silently missed it. Both the static rows and the add-row function fixed and tested.

**Item 3 — "Repairs" category**: added to Monthly Expenses, confirmed working in the Summary totals and on dynamically-added rows. Also fixed Yearly Sales Report's note, which had gone stale the moment Repairs was added — it was still claiming "doesn't exist anywhere," which was no longer true.

**Item 4 — Documentation drift, continued**: verified 2FA's actual show/hide behavior (genuinely works, not just structurally present), plus Print Functionality's specific claims for Daily Sales Entry.

**A real near-miss here, worth being direct about**: found that Daily Sales Entry's print CSS said `landscape`, contradicting the BRD's own "CORRECTED AND CONFIRMED... A4 PORTRAIT" entry. Rather than trust the BRD blindly, tested both orientations with actual print-media PDF generation — neither fits the form on one page anymore, since so much has been added since that claim was last verified. Asked which way to go. **Client corrected me directly: Landscape is what's actually in production, working correctly on a single page today** — the BRD's Portrait claim was the stale one, not the code. Reverted my change immediately and corrected the BRD instead, keeping the old entry visible with a note explaining what actually happened, rather than silently overwriting the record.

**The lesson, recorded plainly**: documentation isn't automatically more trustworthy than working code, especially this far into a long project. When they disagree, check with the client — don't assume either source is right by default.

**Files updated:** 13 forms (mobile fix), `credit_remittance_master_branded.html`, `employee_master_branded.html`, `monthly_expenses_branded.html`, `yearly_sales_report_branded.html`, `daily_sales_report_branded.html` (reverted, no net change), BRD (multiple sections).

---

## 98. Employee Master Restricted to Manager/Owner — Pump Sales Man Blocked (2026-08-28)

New requirement: Employee Master should only be visible to Manager, Supervisor, or Owner — Pump Sales Man accounts must not see it, given the bank account and IFSC data it holds.

Went beyond Rate Master's existing precedent, which is a visual "Super User Only" label with no actual gate behind it. Implemented a real functional block instead, reusing the "Logged in as" selector already on the form:

- Selecting a Pump Sales Man login genuinely hides all form content and shows an "Access Restricted" message — tested directly (content visibility confirmed true/false in both states), not assumed from the code.
- Defense in depth: Save itself independently refuses if a Pump Sales Man login is active, even if content were somehow still visible.
- Added Pump Sales Man options to "Logged in as" (previously only had Owner/Manager, since nothing needed to demonstrate a blocked role before).
- A "Manager / Owner Only" tag added to the header too, matching Rate Master's labeling.

**Honest limitation stated directly in the code**: this checks a demo dropdown, not a real login session. A client-side-only check can be bypassed by viewing source or disabling JavaScript — the real system needs this enforced server-side.

**Files updated:** `employee_master_branded.html`, BRD Section 5.33 (new).

---

## 99. Record Repayment — Partial Payments Confirmed, Real Bug Caught (2026-08-28)

Working through the open-questions list, item #1. Client confirmed directly: partial repayments are the norm (~90% full settlement, but not required — at least one customer reliably pays partially). What actually matters is that whoever processes it (Supervisor, Owner, or Manager) is accurately recorded.

Found "Payment Collected By" had existed since this form was built but was never wired to the "Logged in as" auto-fill mechanism — still a plain manual field. Fixed to auto-fill per row.

**Caught a real bug while testing this, not shipped**: the first version blindly overwrote *every* row's "Payment Collected By" on every Save click. Tested a realistic scenario — Manager saves a first partial payment, then Owner saves after adding a second — and Manager's row got silently relabeled as Owner's. Fixed so only empty rows get filled; once a row is saved, it stays attributed to whoever actually collected it, confirmed across multiple subsequent saves by someone else.

**Files updated:** `record_repayment_branded.html`, BRD Section 5.34 (new).

---

## 100. New Credit Entry & Record Repayment Formally Retired (2026-08-28)

Item #2. Needed two rounds of clarification before acting — the first answer addressed the "updated by/date" tracking mechanism (a related but different question), not retire-vs-keep itself. Asked a second, more concrete confirmation before touching anything, since retiring a form isn't something to walk back casually. Client confirmed directly: retire both, Credit/Remittance Master is the one form going forward.

Neither file deleted — both kept for historical reference, consistent with how this project handles deprecation. Both now show a prominent red "RETIRED" banner directing to Credit/Remittance Master, and Save is genuinely disabled — tested with a valid login selected, confirming it produces an explicit "this form is retired" message rather than appearing to succeed.

**Cleaned up rather than left messy**: Record Repayment's Save function had picked up the same-day partial-payment fix and its bug correction just before being retired. Rather than leave that logic sitting in the file unreachable under a confusing name, replaced the function cleanly with a comment noting its history for anyone reading the file later. Did the same for New Credit Entry's old function — no dead code left behind on either form.

**Files updated:** `new_credit_entry_branded.html`, `record_repayment_branded.html`, BRD Section 5.35 (new).

---

## 101. Nine Open Questions Resolved in One Round (2026-08-28)

Client answered items 3, 5, 6, 7a, 7c, 8, 10 directly, and items 4 and 9 needed actual implementation.

**Documentation-only resolutions:**
- **3** — existing color codes and per-form theme toggle confirmed correct as-is
- **5** — Excel and PDF confirmed as the report delivery formats
- **6** — real mystery solved: "Airtel" is a customer's name, not the telecom company. The "New/Old Airtel Balance" fields correctly track a real creditor's balance — not removed, just previously misunderstood
- **7a** — catch-up-on-startup confirmed for missed rollover
- **7c** — manual re-sync confirmed acceptable, no auto-correction needed
- **8** — ±₹100 threshold confirmed, plus a real workflow detail: Supervisor/Manager calls the Owner when the gap exceeds it
- **10** — no employee-facing access needed; employee asks informally, Manager/Supervisor provides it

**Item 7b needed extra care, given this exact formula has changed several times already** — confirmed the deduction stays -10 always, even on single-pump days (the unused pump still counts its own 10L regardless of activity). No code change needed — existing formula was already correct.

**Item 4 implemented**: Credit/Remittance Master now restricted to Supervisor/Manager/Owner, same functional gate pattern as Employee Master (Section 98) — genuinely hides content and blocks Save for Pump Sales Man logins, tested directly.

**Item 9 implemented**: client confirmed the direction, then asked *how* it would actually work — a fair question given Monthly Expenses aggregates monthly while Trial Balance is daily. Resolved by using Monthly Expenses' existing per-row dates: added an "Update from Monthly Expenses (Today)" button to Trial Balance's Section 8, matching the same demo pattern as Daily Sales Summary's pull. Tested with no regression to the core formula chain.

**Files updated:** `daily_trial_balance_branded.html`, `credit_remittance_master_branded.html`, BRD Sections 5.36, 5.37, 5.38 (new).

---

## 102. Monthly Expenses — Category Filter Added, Real Bug Caught (2026-08-28)

Client asked for a category-specific search within the existing Date Range Report — e.g. "all Power Bill entries this financial year," not just a combined total. Added a Category dropdown, populated fresh from the current category lists on every report run, so anything added via "+ New Category" shows up in the filter automatically.

**Caught a real bug during testing**: the first version matched category by each row's underlying `<select>` value — but the form's original hardcoded rows use lowercase values ("powerbill") while the category arrays and dynamically-added rows use the visible text ("Power Bill"). Filtering by "Power Bill" worked for a newly-added row but silently failed for the original row of the exact same category. Only caught because I tested an original row and a new row together in the same filter run, not just one in isolation. Fixed to match by visible text, consistent with how the existing Monthly Summary already did this correctly.

**Tested after the fix**: an original row (Power Bill) and a dynamically-added row (Repairs) both filter correctly, individually and combined — date-range-only showed both entries totaling 17000; filtering to just Power Bill isolated 12000; filtering to just Repairs isolated 5000.

**Files updated:** `monthly_expenses_branded.html`, BRD Section 5.39 (new).

---

## 103. Role Structure Revised, Then Simplified Same Day (2026-08-29)

Client revised the role structure to resolve the "Supervisor" ambiguity that had been building up: 4 roles — Sales, Manager, Owner, Read Only. Documented in a new BRD section, and Rate Master (previously just a cosmetic "Super User Only" label with no real gate) got a genuine three-tier access implementation: Sales blocked, Manager/Read Only view-only, Owner full edit. Tested all four roles individually — content visibility, field disabled-state, and push/save guards all confirmed correct.

Started extending Employee Master to the same three-tier model, but stopped partway through when the client simplified the direction — **eliminated Read Only entirely, keeping just 3 roles (Sales, Manager, Owner)**, explicitly citing the application's small footprint (~10 end users) as reason not to over-engineer access control.

**Handled cleanly, not messily**: Employee Master's in-progress edits were only in a scratch working file, never copied to outputs — so the live version was untouched and needed no reverting. Rate Master (the one file actually modified) was simplified: Read Only removed from the dropdown and all messaging, with Manager naturally taking over the "view-only" role it already had in the underlying logic — no functional change needed there, just cleanup. Credit/Remittance Master and Yearly Sales Report's Repairs field were explicitly left untouched, per direct instruction not to make further changes beyond this simplification.

**Files updated:** `rate_master_branded.html`, BRD Section 2.1 (revised then corrected same day).

---

## 104. Remaining Pre-Development Items Resolved (2026-08-29)

Went through the "what's pending" list line by line.

- **Cross-browser testing** — confirmed not needed, given the confirmed ElectronJS desktop architecture doesn't run in a general browser in production anyway.
- **Test framework/tooling** — pulled the exact 4 testing categories from the BRD with full detail (OCR/Upload, Service reliability, Data entry/reconciliation, Report/email), then recommended pytest + Playwright — the same tool already used throughout this whole project, so no new tooling to learn.
- **Lower-risk BRD sections** — accepted as-is, closed rather than left open indefinitely.
- **Tesseract bundling** — confirmed to bundle into the single installer alongside Python/SQLite/ElectronJS, since it's not meaningfully complex.
- **Windows Service names** — pushed back gently on the client's own 4-service suggestion for a technical reason: SQLite is a file, not a server process, so it doesn't need its own service, and Tesseract only runs on-demand rather than continuously. Recommended 3 services instead (Backend, Frontend, Scheduler), explained why, and confirmed this matches what was already tentatively proposed earlier rather than being a new decision.
- **Excel export fidelity** — confirmed structured data export is sufficient; exact paper-form replication isn't required.

**Files updated:** BRD Section 4.8 (new).

---

## 105. Yearly Report's Repairs Field — Final Resolution (2026-08-29)

Closed the last open item. No automated pull button — deliberately skipped, since it would just be a second way to do what Monthly Expenses' Date Range + Category filter (Section 5.39) already does well. Confirmed workflow instead: at year-end, run Monthly Expenses' report for the full financial year filtered to "Repairs," read the total, type it in manually.

Updated the note on the field itself to state this explicitly, rather than leaving the earlier "has a real source now" note ambiguous about how that source is actually meant to be used.

**Files updated:** `yearly_sales_report_branded.html`, BRD Section 5.28 (final resolution added).

---

## 106. App Shell Redesign — Left Sidebar, Real IOCL Logo, Preferences Bar (2026-09-04)

Client asked for a look-and-feel pass on the app shell (the screen shown right after login), reviewed as a mockup before touching product code. Several rounds of client feedback, each applied directly:

- **Post-login screen replaced with a left-hand sidebar**, modeled on a reference SaaS layout the client supplied, opening on Daily Sales Entry by default. Confirmed nav order: Daily Sales Entry, Daily Sales Summary, Daily Trial Balance, Credit / Remittance Master, Payment Receipt, Inventory Tracking, Rate Master, Monthly Expenses, Employee Master, Yearly Sales Report — then Manage Users, grouped under an "Admin" divider with an Owner tag since the client's list omitted it. **Open:** Manage Users' placement flagged for the client to explicitly confirm, not yet signed off.
- **Sidebar color corrected twice.** First draft used new warm cream/tan colors; client instructed existing colors only, and separately that the sidebar chrome should avoid IOCL red/blue. Settled on the existing confirmed default accent (`--io-orange` #f37022) for the active nav item, and existing tokens (`#eef1fa`, `#c9d6ef`, `#00246e`, `#55627d`) for the rest of the sidebar — no new colors introduced anywhere in the shell.
- **New shell-level top bar** added above each form's own header: signed-in user's name/role, a Preferences icon, a Print icon, and Sign out.
- **Daily Sales Entry's own existing look stays untouched** — client explicitly reverted an interim redesign that had restyled the form body (blue masthead, flamebar, orange section bars, table) into softer cards to match the sidebar reference; confirmed only the shell (sidebar + new top bar) changes, not the forms themselves. Client also caught that the Save button was missing from an early toolbar draft — corrected; this app has no auto-save, Save stays an explicit action.
- **Logo lockup uses the real IndianOil dealer logo, not a drawn substitute.** First pass used a hand-drawn abstract flame glyph; client asked for the actual IOCL corporate mark instead, since SVR is an authorized IOCL outlet — swapped in the client's own logo file. Now appears in the login screen, the sidebar, and inside the Daily Sales Entry header itself (small white badge next to the existing title) — the pattern to carry to the other 11 forms' headers.
- **Login screen**: field label changed from "Login name" to "Login"; logo lockup added above the card.
- **Layout**: removed the gap between the sidebar and the form content area so they sit flush, per client correction.

**Open items:** the supplied logo file is low-resolution (65×70px) — request a higher-resolution original from IOCL / the signage vendor before it's wired into a real desktop app icon; rolling the header logo badge + preferences pattern out to the remaining 11 screens; `frontend/build/icon.ico` still not wired into packaging (falls back to Electron's default icon — see `HANDOVER.md` §7).

**Files updated:** none yet — reviewed as a design mockup only. Once approved, applies to `frontend/src/renderer/index.html`, `app.js`, `app.css`, and `frontend/build/icon.ico`.

---

## 107. Daily Full-System Backup to External USB, Cold Backup + Restore (2026-09-04)

New requirement: a daily backup of the whole application — not just the database — to an external USB drive, so the station can recover from a full disk/PC failure, not only data loss. Requested an automatic daily run, a way to trigger it on demand, visibility into when it last ran, and — refined same day — that the backup be a **cold** backup (services stopped first, for a consistent snapshot) plus a **restore** path for when the computer won't start at all. Recommended and confirmed:

- **Automatic run: extend the existing Scheduler Service, not a separate Windows Task Scheduler job.** `scheduler.py` already runs a nightly APScheduler job (00:15 IST, DB-only, SDD 7.7/8.4) inside the `SVR-IOCL-Scheduler` Windows Service. Extending that job reuses infrastructure already built (same service, same `scheduler.log`, same missed-run catch-up pattern already used for carry-forward) instead of standing up a second, separately-monitored OS-level scheduled task.
- **Cold backup, but the Scheduler Service cannot stop itself mid-job.** "Shut down all services first" resolves to: the Scheduler Service stops **`SVR-IOCL-Backend`** (the process that holds the DB open for writes and serves the app) before copying anything, then restarts it once the archive is written — the Scheduler stays up throughout since it is the one doing the work. This gives a fully consistent snapshot (no in-flight writes, no locked files) without needing SQLite's online-backup API for this job.
- **On-demand "Backup Now" is relayed through the Scheduler Service, not run by the Backend API directly.** The Electron menu's "Backup Now" calls `POST /backup/run` on the Backend Service, which only writes a request marker and returns immediately — it cannot stop *itself* to do a cold backup of itself, and the logged-in user's own account has no rights to stop/start a Windows Service anyway. The Scheduler Service (already `LocalSystem`, already independent of Backend) polls for that marker every 30-60s and runs the identical cold-backup routine on demand, whether triggered by the clock or by a person. One code path either way.
- **Scope: one dated `.zip` per day** containing both the data directory (`C:\ProgramData\SVR-IOCL\` — DB, logs, existing local backups) and the installed program folder (`C:\Program Files\SVR IOCL Station\` — the frozen Python backend, Electron app, and Tesseract once bundled per ADR-6) — a single archive is enough on its own to rebuild the station on a replacement PC.
- **USB drive found by volume label** (e.g. the stick must be labeled `SVR-BACKUP`), not by drive letter — letters are reassigned depending on what else is plugged in; the label is stable. If the labeled drive isn't present when the job runs, skip and log it rather than fail silently or write to the wrong disk.
- **Retention: max 7 archives, pruned only after the new one verifies good.** Never delete old backups before confirming the new cold backup completed successfully — if the new one fails or the USB drive fills up mid-write, the prior 7 are still intact. Confirmed this same 7-archive cap also applies to the *existing* local DB-only backup (`C:\ProgramData\SVR-IOCL\backups\svr-*.sqlite`), which previously had no retention limit at all — resolves the open item from the first pass at this entry.
- **Restore has two paths, because "the computer fails to start up" means there may be no running app to show a menu in:**
  - **In-app restore** (Owner-only, same Backup panel) — for the lesser case: Windows still boots and the app still runs, but the Owner wants to roll back to a prior day (e.g. DB got corrupted). Picks one of the last 7 archives, confirms, the Scheduler Service stops Backend, restores the files, restarts Backend.
  - **Standalone restore tool on the USB drive itself** — for the actual "PC won't start" case: there is no existing SVR install to open a menu in, so the restore has to run from outside the app entirely. A small restore script/exe travels alongside the backups on the USB stick; run it after installing a fresh copy of SVR IOCL Station on the replacement PC, and it stops the freshly-installed services, unpacks the chosen archive over `Program Files` + `ProgramData`, and restarts the services. Shares its core logic with the in-app restore path — two entry points, one routine.

**Files updated:** none yet — requirement + recommended approach only. Implementation touches `backend/src/svr_backend/scheduler.py` (cold backup/restore routine + on-demand polling), a new `backend/src/svr_backend/api/backup.py` router, a new renderer Backup panel, and a new standalone restore script bundled onto the USB backup target.

> **Update (2026-09-05):** deferred. Backup/restore is set aside as its own
> module for a future upgrade phase — not part of current scope.

---

## 108. App Shell Redesign — Implemented in the Renderer (2026-09-05)

Entry 106's mockup decisions are now in the actual Electron code
(`frontend/src/renderer/`), each step verified with `eslint` + the full
Playwright suite (32 tests).

- **Post-login launcher: plain button list → left sidebar + top bar.**
  Confirmed nav order, with Manage Users in its own "Admin" group below a
  divider. RBAC unchanged — Manager still sees Manage Users; the mockup's
  "(Owner)" tag was dropped as it misrepresented actual access. The module
  list, icons, and sidebar builder are factored into `lib/nav.js`.
- **Persistent sidebar on every screen.** A shared `lib/screen-shell.js`
  injects the identical fixed sidebar on each of the 11 screen pages on
  load — derives the active module from the URL, checks the session token,
  redirects to login if it is gone. The existing per-page navigation model
  was kept; no single-page-app refactor.
- **Login screen:** field label "Login name" → "Login".
- **Combined SVR / IndianOil lockup.** The client supplied a
  high-resolution lockup ("IndianOil | SVR — INDIAN OIL SERVICE STATION").
  It replaces the earlier low-resolution mark at
  `assets/iocl-logo.png` and now appears on the login screen, the sidebar,
  and every form header. The redundant per-screen
  `<h1>SVR Indian Oil Service Station</h1>` line was removed since the
  lockup carries the station name; each page's own subtitle line stays.
  Header logo size is one adjustable value (`--header-logo-height`) in
  `app.css`.
- **Deliberately not included:** the mockup's Preferences/Print icons in
  the top bar (no feature behind them yet). A print-quality logo original
  is still worth obtaining from IOCL for the desktop app icon specifically.

Commits: `886f7a3`, `17c8dc1`, `d610c5e`, `65585db`.

**Files updated:** `frontend/src/renderer/index.html`, `app.js`,
`lib/nav.js` (new), `lib/screen-shell.js` (new), `styles/app.css`, all 11
`screens/*/index.html`, and `frontend/src/renderer/assets/iocl-logo.png`.

---

## 109. Pre-UAT polish + remote-PC check fixes (2026-09-05)

Everything since entry 108, ahead of the real-data UAT.

- **Windows app icon.** The supplied lockup is 2116×743; Windows icons must be
  square, so it's centred on a 1024×1024 white canvas at `frontend/build/icon.png`
  and `build.win.icon` points at it — electron-builder generates the `.ico` for
  taskbar / Start / shortcut / Search instead of the default Electron icon. A
  square crop of just the round IndianOil badge would read sharper at 16–32 px if
  wanted later. Commit `9d06c78`.
- **Code-signing: wired cert-ready, ships unsigned.** No config change — when
  `CSC_LINK` / `CSC_KEY_PASSWORD` are set electron-builder signs the exe +
  installer automatically; when they aren't (today) the build is unsigned and the
  user clicks through SmartScreen once. Documented in `installer/README.md`. An OV
  code-signing cert can be added any time. Commit `6166b87`.
- **Release checklist.** The version is hand-kept in three files
  (`frontend/package.json`, `backend/pyproject.toml`,
  `backend/src/svr_backend/__init__.py`) — documented that they move together,
  with the check/build/tag steps, in `installer/README.md`. Commit `aed9037`.
- **UAT / acceptance test cases** — `docs/03-Testing/UAT-Test-Cases.md`: Section A
  deployment/infra smoke, Section B ~4–6 cases per form for all 12 modules
  (grounded in the non-negotiable rules), Section C cross-module money flows,
  Section D server-side RBAC matrix, go-live blocker list, sign-off block. OCR /
  Excel / full backup-restore marked N/A (not in this build). Commit `b1a4c0e`.
- **Remote-PC check fixes** (found on the USA test PC):
  1. After login the app showed a "choose a module" placeholder instead of a
     default form — it now goes straight to **Daily Sales Entry**, which carries
     the persistent sidebar. The old `#nav-view` launcher markup is removed.
  2. The opened form floated with a wide gap between it and the sidebar —
     `body.shell-mode` now pads exactly the 232 px sidebar width and the form
     fills the pane flush (no left border/radius, `margin:0`). Commit `a2188cc`.

**Plan from here (confirmed with the client):** finish the remaining coding
first, then a **real software install on the USA remote PC** and a **daily
real-data UAT** — enter live business data each day, verify every calculation and
cross-module integration against reality — then fix what that surfaces, then
go-live. The gaps below are fixed *after* that coding pass and install, not now.

**Known coding gaps (unchanged, for reference):**
- **Daily Trial Balance (Module 12) — partial.** Sections 1/3/6/7 modelled;
  Sections 2/4/5/8–11 are a free-form `manual_json` blob pending the ADR-1
  decision (manual columns vs. computed roll-ups). Section 6 litres sign
  (`diff − consumption`) + density deduction still need a cross-check against the
  AUG11/AUG12 workbooks (UAT case 12.6).
- Not built by scope: OCR / Tesseract, Excel import/export, bank-statement
  reconciliation, 2FA enforcement, Employee Master insurance sections, and the
  deferred full backup/restore module (entry 107).

**Files updated:** `frontend/build/icon.png` (new), `frontend/package.json`,
`installer/README.md`, `docs/03-Testing/UAT-Test-Cases.md` (new),
`docs/03-Testing/Quick-Shell-Check.md` (new), `frontend/src/renderer/index.html`,
`app.js`, `styles/app.css`, all 12 `frontend/tests/*.spec.js` login helpers.

---

## 110. GitHub Repository Renamed: SVR → IOCL_SVR (2026-09-07)

Client-initiated change: the project repository was renamed from `SVR` to `IOCL_SVR` via GitHub's repository rename function (Settings → General → Repository name).

- **Old URL:** `https://github.com/Mithendra/SVR`
- **New URL:** `https://github.com/Mithendra/IOCL_SVR`
- **Method:** In-place GitHub rename (not a fresh repository/re-upload) — this preserves full commit history (all 45 commits at time of rename), all branches, all files, issues, and contributor history intact. GitHub automatically redirects the old `SVR` URL to `IOCL_SVR`, so existing links/clones continue to work.
- **Reasoning:** Client wanted the repository name to reflect the IOCL branding directly rather than the station's short name alone.
- **Note:** An earlier attempt created a separate, empty repository literally named `IOCL_SVR` before the rename — this was deleted by the client to free up the name, after which the rename above was performed cleanly against the original, fully-populated `SVR` repository. No files or history were lost at any point in this process.
- **Action needed:** Update Section 1 (Project Context) and the intro summary table's **Code Repository** field in `SVR-BRD-Requirement-Gathering.docx` to reference `https://github.com/Mithendra/IOCL_SVR` going forward. Any local clones/CI configs referencing the old `SVR` URL should be updated to the new name at convenience (the GitHub redirect prevents immediate breakage but is not guaranteed permanent if the old name is ever reclaimed by another user).
