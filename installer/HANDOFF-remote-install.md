# HANDOFF — install the updated build on the remote PC & re-validate

**Written:** 2026-09-11 · **Repo:** `https://github.com/Mithendra/IOCL_SVR.git` ·
**Branch:** `main` · **HEAD:** `2a19705`

Paste this whole file as the first message of the Claude Code session on the
remote PC, then read (in order): this file → [`installer/RUNBOOK.md`](RUNBOOK.md)
→ [`HANDOVER.md`](../HANDOVER.md) §5 → [`CLAUDE.md`](../CLAUDE.md).

---

## 1. State

**This is a small, targeted follow-up build** — the remote PC is already running
the `aa32bc2` install and mid-testing with real September 9/10 data. Testing
surfaced three concrete bugs; all three are fixed in this build and this build
only carries those three fixes (plus one from just before them). Nothing else
changed — no schema migration, no pump serial change, no new feature.

```
C:\Mithendra\SVR\installer\output\SVR-IOCL-Station-Setup-0.1.0.exe   (177.8 MB)
```

- **Unsigned** — by decision (no cert; SmartScreen "Run anyway" once), same as
  every build so far.
- Freeze smoke passed: `migrate` applied all 14 migrations, `serve --help`, and
  **`selfcheck` imported the full app graph inside the frozen exe — 20 routes**.
- Backend gate at build time: **179 pytest passed** (1 environment-dependent
  skip, unrelated), ruff clean. Frontend: **51 Playwright passed**, eslint clean.
- It is **NOT in git** (`installer/output/` is ignored) — transfer it the same
  way as last time (you used Google Drive).

### What's new since `aa32bc2` (the build currently installed there)

1. **Excel import — real-world label tolerance.** The paper-layout (natural
   workbook) parser matched labels by exact substring only, so a real sheet
   worded slightly differently from our reference wording (a hyphen instead of
   a slash, a missing space, "Amount" instead of "Total Amt") could silently
   drop a field. Now tolerant of punctuation/spacing differences.
2. **Excel import — Oil Sale(s) Opening Stock wasn't being read at all.** The
   paper-layout parser only ever read Quantity from the Oil Sale(s) table -
   Opening Stock (the field made manually overridable in the last build) was
   never read from a natural/paper-shaped workbook, so an override typed into
   the sheet was silently discarded on import. Fixed - both columns are now
   read independently per row. (Oil Rate is still not read from the sheet on
   purpose - the backend always locks it from Rate Master on save regardless
   of import, same as Gas Rate.)
3. **Net Bal Hand Off formula was missing Phone Pay Settled.** Client-confirmed
   this was a real gap in the original mockup formula, not intentional. Fixed
   in the backend calc engine (authoritative), the renderer's UX-mirror copy,
   the on-screen formula label, and the formula-register doc - all four now
   read `Cash − Expenses + Phone Pay Settled + Phone Pay Not Settled + New
   Credits + Card Swiping + Night Cash`.
4. **Print Blank was printing A4 landscape for every module, not just Daily
   Sales Entry.** The client's own reference blank forms (`SVR_DSR_EMPTY_
   <serial>.pdf`) are single-page A4 **portrait** - the forced landscape
   fought that badly enough that one pump's form wasn't printing at all.
   Switched the shared print stylesheet to portrait; added a rule so a table
   row/section heading can't be split across a page break.

**Not changed in this build** (still true from `aa32bc2`, no need to re-test
from scratch, but fine to spot-check): pump serials (`12BC4523V-RD` /
`11CC2012V-OFF`), Print & Sync, Save/Update/Delete buttons, first-entry manual
Last Shift Reading, Excel multi-sheet pump selection, the "-" blank convention,
Daily Sales Summary's missing-entry message. See the previous handoff (git
history of this file, commit `eeee50a`) if you need the full description of
any of those.

### Deferred, not in this build

Client asked to drop Tesseract/PDF-Scan entirely (item 4 of the same report) -
explicitly deferred to a later build, not touched here. Scan/Upload still
works exactly as before; keep testing via **Import from Excel** or **manual
entry** as the two reliable non-OCR paths (OCR itself never read Oil Sale(s) or
Expenses at all - a pre-existing scope limit, not a regression - and its
Summary-line reading is a known, already-documented gap; both are unrelated to
the three fixes above).

---

## 2. Your task, in order

### A. Get the installer onto this PC

Copy the new `SVR-IOCL-Station-Setup-0.1.0.exe` from the build PC (same
Google-Drive transfer as before) and `git pull` this repo so the session has
the current scripts/docs.

### B. Install over the existing `aa32bc2` install - no uninstall needed this time

Unlike the last build, **nothing here changes the pump serials, the DB schema,
or anything cached client-side that would need a clean slate** - it's safe to
run the new installer directly over the existing install (same version
`0.1.0`, NSIS handles the overwrite). Your in-progress Sep 9/10 test data in
`C:\ProgramData\SVR-IOCL\svr.sqlite` is untouched either way.

1. Right-click the `.exe` → **Run as administrator**. SmartScreen → *More info →
   Run anyway* (unsigned, expected).
2. Accept defaults. On the last page `installer.nsh` runs `first-run.ps1`
   elevated again (idempotent - re-applies config, re-runs migrations
   (no-ops, already applied), restarts both services). A message box means it
   hit a problem - note the exit code.
3. Skip user creation - your existing accounts are already in the DB.
4. Relaunch **SVR IOCL Station** (fully quit it first if it was already open,
   so it picks up the new Electron files) → log in.

If you'd rather be extra cautious, a full uninstall-then-install (per the
previous handoff's §2.B) still works and is not wrong - just not required this
time.

### C. Re-validate the three specific fixes

You don't need to redo the full validation pass from the last handoff - just
confirm these three, using a real sheet if you have one, or the client's own
blank templates in `docs/01-BRD-Requirement-Gathering/ocr-samples/
SVR_DSR_Empty_<serial>_A4.xlsx` filled in with a couple of sample rows:

| Check | Expect |
|---|---|
| Import an Excel sheet with Oil Sale(s) Opening Stock filled in (paper-layout / natural workbook, not our own export) | Opening Stock populates per oil row, not just Quantity |
| A day with Phone Pay Settled filled in | Net Bal Hand Off includes it (formula shown next to the field also now says "... + Phone Pay Settled + Phone Pay Not Settled + ...") |
| Print Blank - either pump serial | Prints/previews as A4 **portrait**, matching `SVR_DSR_EMPTY_<serial>.pdf`; both serials print (not just one) |

Also worth one quick general check after any install: `Get-Service
SVR-IOCL-Backend,SVR-IOCL-Scheduler` both `Running`/`Automatic`, and
`Invoke-RestMethod http://127.0.0.1:8756/health` → `{status: ok, ...}`.

### D. Record results

Add `### 5.11 Results (remote PC, 2026-09-11, build 2a19705)` to
`HANDOVER.md` - just the three fix checks above plus the service/health
check. Commit + push (branch → `--ff-only` → push → delete branch). On any
failure: capture the exact error + the relevant
`C:\ProgramData\SVR-IOCL\logs\*.log` lines and the §4 table below.

---

## 3. Ground rules (CLAUDE.md)

- Model **Claude Sonnet 5**. Plan Mode for any change > 2–3 files or a shared
  formula.
- **Commit/push only when asked.** Branch first if on `main`; pattern is feature
  branch → `git merge --ff-only` → push → delete branch. End commit messages with
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- This PC has no Python/Node, so you can't run the test suites here - that's fine,
  they're green on the build PC (backend `ruff` + **179 pytest**, frontend
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
| Old Electron UI still shows after install (e.g. old print orientation) | app wasn't fully quit before/after reinstall | quit **SVR IOCL Station** completely (check Task Manager) and relaunch from the Start Menu shortcut |

## 5. Not in scope

Dropping Tesseract/PDF-Scan (client asked for this, explicitly deferred - see
§1). Code-signing (wired, dormant — no cert). OCR accuracy on genuine
handwriting (not a blocker — typed PDF/Excel + manual entry are the reliable
paths). Bank-statement reconciliation (not built).
