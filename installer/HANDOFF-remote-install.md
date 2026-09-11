# HANDOFF — install the built installer on the remote PC & validate

**Written:** 2026-09-11 · **Repo:** `https://github.com/Mithendra/IOCL_SVR.git` ·
**Branch:** `main` · **HEAD:** `aa32bc2`

Paste this whole file as the first message of the Claude Code session on the
remote PC, then read (in order): this file → [`installer/RUNBOOK.md`](RUNBOOK.md)
→ [`HANDOVER.md`](../HANDOVER.md) §5 → [`CLAUDE.md`](../CLAUDE.md).

---

## 1. State

**The installer is already built** on the build PC (2026-09-11, from `main` @
`aa32bc2`):

```
C:\Mithendra\SVR\installer\output\SVR-IOCL-Station-Setup-0.1.0.exe   (177.8 MB)
```

- **Unsigned** — by decision (no cert; SmartScreen "Run anyway" once). The
  code-signing path is wired but dormant.
- Freeze smoke passed: `migrate` builds a DB, `serve --help`, and **`selfcheck`
  imported the full app graph inside the frozen exe — 20 routes**.
- Bundles `resources\backend\` (3 frozen exes) + `resources\tesseract\` (the OCR
  engine, ~175 MB on disk, LZMA-compressed in the installer).
- It is **NOT in git** (`installer/output/` is ignored) — it must be transferred
  from the build PC (USB / network share / cloud).
- Backend gate at build time: **178 pytest passed** (1 environment-dependent
  skip, unrelated), ruff clean. Frontend: **51 Playwright passed**, eslint clean.

### What's new since the last install (`bc27d97`, 2026-09-10) — this is a lot

The remote PC's current install predates **all** of the following. In rough
order:

- **The station's pump serials were corrected**: `12BC4523V-RD` (Road) and
  `11CC2012V-OFF` (Office) — both the values and which side each belongs to
  changed from what was installed before. `summary.classify_pump` now maps
  office/road from an explicit lookup, not a substring guess. **Test with the
  new serials, not the old ones.**
- **Print Blank** now shows "(Road pump)"/"(Office pump)" next to the serial
  (matches the client's own reference blank forms) and correctly covers only
  Sections 1–7 + Verified-by (Section 8 and operational banners no longer leak
  into the printed output).
- **Print & Sync** (new) — two buttons, Manager/Owner only, next to Print
  Blank. Syncs Inventory Tracking's oil stock from the most recent day that
  item had a *real* recorded sale, then carries forward Last Shift Reading as
  usual, then prints. See `IMPLEMENTATION-MAP.md`'s "Print & Sync" row.
- **Save / Update / Delete** are now three distinct toolbar buttons (was one
  relabeled Save). Delete is Manager/Owner-only. Every confirmation/error
  message across every module screen is now bold.
- **First entry for a pump** (no prior reading to carry) now allows a manual
  Last Shift Reading instead of being stuck on "Auto @ 23:59 IST".
- **Oil Sale(s) Opening Stock** is now manually editable (short-term fix,
  client-confirmed) — was locked to the Inventory Tracking value with no way
  to correct it.
- **Excel import** now accepts a natural, non-templated workbook (e.g. a
  handwritten form typed up via an AI tool) via a paper-layout fallback
  parser, and correctly picks the right sheet out of a multi-sheet workbook
  (one real client file has a Road sheet and an Office sheet in one file).
  Import identity (Pump Serial + Shift Date) always comes from the form's own
  selection now, never from the imported file's metadata.
- **The paper form's "-" convention** (its universal "nothing to report"
  marker) is now treated as blank everywhere it's read, not as a literal
  dash.
- **Daily Sales Summary** now names which pump's Daily Sales Entry is missing
  ("Missing the Daily Sales Entry for: Road pump...") instead of a generic
  "waiting" message — both pumps are required every day going forward (even a
  repaired/off-duty pump submits a zero-activity report rather than being
  skipped).
- All of the above verified end-to-end against real September 9/10 client
  files, including the three specific workflows below.

### Three workflows re-verified before this build (2026-09-11)

All confirmed working end-to-end against real files
(`backend/tests/test_pre_install_readiness_2026_09_11.py`):

1. **Daily Sales import** — Scan/Upload (PDF) and Import from Excel, for
   2026-09-09 and 2026-09-10, both pumps.
2. **Daily Sales Summary → Daily Trial Balance** — Section 3 pulls
   automatically once both pumps have submitted; the remaining sections
   (Section 1 IOCL tank readings, cash/book value, the ADR-1 manual blob) are
   entered by hand, per day. **One by-design rule to know before testing**: a
   new Trial Balance date can't be started while an earlier one is still
   open (ADR-2 maker-checker) — Close & Sign Off each day in order.
3. **Inventory Tracking** — accepts real restock/on-hand data from
   2026-09-10 onward with no date-ordering constraint.

### OCR reality — do not test handwriting against it as if it works

`POST /daily-sales-entry/ocr` is **draft-assist only** for a genuine
handwriting scan/photo — stock Tesseract still cannot read handwritten Daily
Sales sheets (measured 0/6 across three approaches on real scans). **Two
paths ARE reliable now**, confirmed on real client files: a **typed PDF**
(e.g. an AI-transcribed form) reads from the PDF's own text layer — no OCR
involved at all — and a **typed Excel sheet** reads via the paper-layout
import fallback. See
[`docs/01-BRD-Requirement-Gathering/OCR-findings-2026-09-09.md`](../docs/01-BRD-Requirement-Gathering/OCR-findings-2026-09-09.md)
for the full history.

---

## 2. Your task, in order

### A. Get the installer onto this PC

Copy `SVR-IOCL-Station-Setup-0.1.0.exe` from the build PC. (This PC is meant to be
a clean target — **no Python / Node / VS Code**. Only Git + Claude Code + the
`.exe`, per `HANDOVER.md` §2.) `git clone` / `git pull` the repo so this session
can read the scripts, logs, and checklists — but the `.exe` comes separately.

### B. Uninstall the old build first, then install fresh

Given how much changed (including the pump serials), don't install on top —
uninstall the existing `bc27d97` install first (Settings → Apps → SVR IOCL
Station → Uninstall), confirm both services and the Startup shortcut are
gone, **then** install the new `.exe`. `C:\ProgramData\SVR-IOCL\` and its DB
are kept by the uninstaller by design — the existing data survives.

Full checklist: `installer/RUNBOOK.md` §2 and `HANDOVER.md` §5.

1. Right-click the `.exe` → **Run as administrator**. SmartScreen → *More info →
   Run anyway* (unsigned, expected).
2. Assisted installer (`perMachine`), accept defaults →
   `C:\Program Files\SVR IOCL Station`. On the last page `installer.nsh` runs
   **`first-run.ps1`** elevated: data + log tree under `C:\ProgramData\SVR-IOCL`,
   machine `SVR_*` config (incl. `SVR_FIELD_KEY`, `SVR_TESSERACT_CMD`,
   `SVR_TESSDATA_PREFIX`), migrations, both Windows Services registered
   `Automatic` + started, per-user Startup shortcut. A message box means it hit a
   problem — note the exit code.
3. If this is genuinely a fresh DB (no prior install's data survived), **create
   the first Owner**:
   ```powershell
   & "C:\Program Files\SVR IOCL Station\resources\backend\svr-backend.exe" `
       create-user --role Owner --name "<Full Name>" --login <login>
   ```
   If the prior install's `C:\ProgramData\SVR-IOCL\svr.sqlite` survived (the
   normal case per the uninstall-keeps-data design), your existing accounts
   are already there — skip this step and just log in as before.
4. Launch **SVR IOCL Station** → log in.
5. **Rate Master** — confirm the real current IOCL Buy/Sell rates are still
   correct (they carry over with the DB; only check this if starting fresh).

### C. Validate (record every result)

Run `HANDOVER.md` §5.2–5.7 in full, **plus** the three workflows above using
the real September 9/10 files (already in
`docs/01-BRD-Requirement-Gathering/ocr-samples/` if you `git pull`ed). The
checks that are new or worth re-confirming on real hardware:

| Check | Expect |
|---|---|
| Pump Serial dropdown on Daily Sales Entry | `12BC4523V-RD` and `11CC2012V-OFF` only — old serials gone |
| Print Blank — either serial | Shows "(Road pump)"/"(Office pump)" in the header; native print dialog shows a live preview (Chromium default, nothing custom to configure) |
| Print & Sync — either serial (as Manager/Owner) | Status line names exactly what changed in Inventory, then the print dialog opens |
| Import a real Sep 9/10 PDF or Excel file | Reads correctly; Save succeeds |
| Daily Sales Summary with only one pump submitted | Names the missing side explicitly |
| Daily Trial Balance for two consecutive real dates | Section 3 pulls automatically; second date blocked until the first is Closed & Signed Off |
| `Get-Service SVR-IOCL-Backend,SVR-IOCL-Scheduler` | both `Running` / `Automatic` |
| `Invoke-RestMethod http://127.0.0.1:8756/health` | `{status: ok, version: ...}` |
| `Invoke-RestMethod http://127.0.0.1:8756/daily-sales-entry/ocr/status` | `{"bundled": true, "pipeline": "draft-assist", ...}` |
| **Reboot** | both services `Running`; app auto-launches from the Startup shortcut |

### D. Record results

Add `### 5.10 Results (remote PC, 2026-09-11)` to `HANDOVER.md` mirroring the
§5.8/§5.9 tables. Note the actual `.exe` size, and the results of the three
workflow checks above. Commit + push (branch → `--ff-only` → push → delete
branch). On any failure: capture the exact error + the relevant
`C:\ProgramData\SVR-IOCL\logs\*.log` lines and the §4 table below.

---

## 3. Ground rules (CLAUDE.md)

- Model **Claude Sonnet 5**. Plan Mode for any change > 2–3 files or a shared
  formula.
- **Commit/push only when asked.** Branch first if on `main`; pattern is feature
  branch → `git merge --ff-only` → push → delete branch. End commit messages with
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- This PC has no Python/Node, so you can't run the test suites here — that's fine,
  they're green on the build PC (backend `ruff` + **178 pytest**, frontend
  `eslint` + **51 Playwright**, `selfcheck` 20 routes).
- Don't commit `installer/vendor/` or the `.exe` (both git-ignored), or the stray
  `Claude outputs/` · `files.zip` · `releases/` · `Last_update_SVR_Sep7.txt`.

## 4. If the install breaks — likely causes

| Symptom | Cause | Fix |
|---|---|---|
| `first-run.ps1` message box, non-zero exit | a service failed to install/start | `HANDOVER.md` §6; `installer\smoke-services.ps1` (elevated) isolates the service machinery; re-run `installer\first-run.ps1` by hand as admin to see full output |
| Services won't start / backend uses a dev path | machine `SVR_*` env not inherited by the SCM | `HANDOVER.md` §6 items 1–2 |
| `ocr/status` → `"bundled": false` | a Tesseract DLL missing, or `SVR_TESSERACT_CMD` wrong | check `...\resources\tesseract\` has the `*.dll`s + `tessdata\`; run `tesseract.exe --version` by hand |
| Win10 `DLL load failed` / missing `VCRUNTIME140` | frozen on Win11 | install VC++ 2015–2022 x64 redist on the target |
| Frozen `svr-backend-service.exe install` misbehaves | frozen pywin32 service registration | was proven working on v0.1.0 (2026-09-04); if it regressed, add `_exe_name_ = sys.executable` to the two `ServiceFramework` classes and rebuild on the build PC |
| Pump Serial dropdown still shows old serials after install | browser/renderer cache from the old install wasn't cleared, or the uninstall didn't fully remove the old app files | fully uninstall first (§2.B), confirm `C:\Program Files\SVR IOCL Station` is gone before reinstalling |

## 5. Not in scope

Code-signing (wired, dormant — no cert). OCR accuracy on genuine handwriting
(Tesseract can't read it — see the findings doc; not a blocker, typed
PDF/Excel + manual entry are the reliable paths). Bank-statement
reconciliation (not built). Windows auto-logon on the station PC (a one-time
Windows-account step for whoever deploys it — CLAUDE.md open-items note —
not something the app or `first-run.ps1` does).
