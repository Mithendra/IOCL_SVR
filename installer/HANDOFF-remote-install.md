# HANDOFF — install the updated build on the remote PC & re-validate

**Written:** 2026-09-12 · **Repo:** `https://github.com/Mithendra/IOCL_SVR.git` ·
**Branch:** `main` · **HEAD:** `1125e7d`

Paste this whole file as the first message of the Claude Code session on the
remote PC, then read (in order): this file → [`installer/RUNBOOK.md`](RUNBOOK.md)
→ [`HANDOVER.md`](../HANDOVER.md) §5 → [`CLAUDE.md`](../CLAUDE.md).

---

## 1. State

**This is a big build — do not treat it as a small follow-up.** The remote PC is
running the `2a19705` install from 2026-09-11 16:33, which is **five commits and
four migrations behind**. Everything the client reported in round-2 testing, plus
the 2026-09-12 form revision, landed after that installer was cut. Until this
build goes on, that machine is testing against bugs that are already fixed.

```
C:\Mithendra\SVR\installer\output\SVR-IOCL-Station-Setup-0.1.0.exe   (177.8 MB)
built 2026-09-12 (evening) from 1125e7d
```

- **Unsigned** — by decision (no cert; SmartScreen "Run anyway" once), same as
  every build so far.
- Freeze smoke passed: `migrate` applied **all 20 migrations**, `serve --help`,
  and **`selfcheck` imported the full app graph inside the frozen exe — 20
  routes**.
- Gate at build time: backend **211 pytest passed** (1 environment-dependent
  skip, unrelated), ruff clean. Frontend **64 Playwright passed**, eslint clean.
- It is **NOT in git** (`installer/output/` is ignored) — transfer it the same
  way as last time (you used Google Drive).

### What's new since `2a19705` (the build currently installed there)

**`a803860` — round-2 fixes, nine client-reported items.** The money ones:

1. **Net Bal Hand Off had the wrong sign on every non-cash line.** It was
   *adding* Phone Pay, credits and card swipes instead of subtracting them.
   Net Bal is the *physical cash* handed over, so anything collected
   electronically or given on credit comes off. Verified against three real
   filled client forms, which reproduce exactly only under subtraction.
2. **Oil Rate now comes from the sheet**, and Rate Master's oil rates were stale
   placeholders never replaced with the station's real figures (migration
   `0015`: 2T/1.20 62→30, 2T/2.40 118→17, Acid 1L 30→20, Acid 5L 130→120,
   20/40 280→130). On the real Sep 9 sheet those seeds turned an oil total of
   290 into 1,310.
3. **Truncation, not rounding.** The station's forms cut every row amount at
   paise: `629.49 × 105.36 = 66323.0664` prints `66323.06`, not `.07`.
4. Print preview (Electron had none) and a **one-page A4 portrait** form —
   it was printing across three pages.
5. **Query / Browse saved entries** — saved data was effectively unreachable
   unless you landed on its exact date.
6. **Inventory: Opening is editable and *replaces*, not adds** (Manager/Owner).
7. Two-decimal display everywhere.
8. **Scan/Upload removed from the UI** (client request; Tesseract is still
   bundled — unbundling it is its own change).

**`b869f4b`** — both Trial Balance audit findings closed.

**`4d76742` — Buy Rates were wrong** (migration `0016`): HS 101.50→**102.75**,
MS 112.30→**113.56**, proven off SEP06's own whole-litre figures. This feeds
Trial Balance Section 6 Stock Value → the Section 7 grand total. Section 6 also
now computes from the current reading alone instead of silently reporting
nothing on a part-filled day.

**`bed60b8` — the 2026-09-12 form revision:**

- **Oil Sale(s): 5 rows → 7** (migration `0017`) — 2T/1.50 ML, 2T/2.40 ML,
  Acid Water 1 Lts, Battery Water 1 Lts, Battery Water 5 Lts, 20/40 Engine
  05. Lts, 20/40 Engine 1 Lts.
- **Total Gas & Oil Sales Amt** row closing section 2.
- **Night Cash Hand Off removed** — the Expenses row "Last Night Cash Hand-off…"
  already carried that money, so the two double-counted it.
- Net Bal label now reads `Cash − (Expenses + Phone Pay Settled + Phone Pay Not
  Settled + Today New Credits + Card Swiping)`.
- Expenses Amount column widened to hold `9999999999999999` (it's written into
  by hand on the printed form).
- **Pump serials validated.** The mockups had Office and Road the wrong way
  round; the app never did. Daily Sales Summary now prints each side's serial
  in its heading and column header and re-checks the pairing on every render.

**`51bab24`** — oil rates carried through the relabel (migration `0018`).

### Schema DOES change this time

Migrations `0015`–`0020` run on install. **Entries already saved on that PC keep
working**: the Oil Sale(s) row *order* changed, so anything that reads a stored
record resolves each row by its own saved label rather than by position
(`oils_by_key` in the engine, mirrored on the screen). That was built for
exactly this upgrade. Pump serials are unchanged.

### Also in this build — Daily Trial Balance, rebuilt in full

**`f7ab0fa` / `a9bd61d`.** The screen rendered four sections and put the other
seven behind a raw JSON textarea, so in live testing it looked like it had three
sections. It is now the client's **SEP12 tab** end to end
(`docs/01-BRD-Requirement-Gathering/ocr-samples/Trail_balance_12-SEP-2026.xlsx`):

- **All 11 sections**, in the station's own workbook numbering (1–11). It used to
  show the SDD §9 numbering, so the screen said "6. Stock Value" where the
  workbook says **5**.
- **Totals are calculated, not typed** — 3.6, 3.7, 3.13, 3.15, 4.3, 4.5, 7.3,
  7.4, 7.5, 8.3, 8.5, the management summary, Section 10's Total/Lost, and
  Section 1's cross-fuel columns. The sheet says so itself at H9.
- **Section 2 Day Sales Report** is pulled live from the day's Daily Sales
  Entries — per-pump blocks with subtotals, the combined block, and 2.1 Oil Sales
  with Opening/Closing Stock and the Indent column.
- **All six of the sheet's dropdown lists**, verbatim, plus 8.9 Prepared by /
  Verified by / Sent to.
- Oil rates re-read off SEP12 (three of the six inferred in `0018` were wrong),
  and the testing/density deduction is **5.5**, not 10 — effective-dated, so
  earlier Trial Balances keep the 10.0 that applied on their own date.

### Known — a one-paisa difference, by design

Daily Sales **truncates** every row amount at paise, because the client's own
Daily Sales Report forms do (proven 4/4 against filled sheets: `629.49 × 105.36`
prints `66323.06`, not `.07`). The Trial Balance **workbook** does not truncate —
it carries full Excel precision. On SEP12 that puts three figures one paisa apart:

| | App | SEP12 tab |
|---|---|---|
| Road Petrol amount | 62,236.22 | 62,236.23 |
| Road subtotal | 124,595.64 | 124,595.65 |
| Gas Total / Daily Sales Total | 126,655.39 / 127,071.39 | 126,655.40 / 127,071.40 |

This is the client's two documents disagreeing with each other, not an app bug.
Truncation is locked by the Daily Sales reconciliations (23,298.77 / 38,993.84 /
1,601.20) and is not to be "fixed" without the client changing that decision.
**Do not log it as an install failure.**

---

## 2. Your task, in order

### A. Get the installer onto this PC

Copy the new `SVR-IOCL-Station-Setup-0.1.0.exe` from the build PC (same
Google-Drive transfer as before) and `git pull` this repo so the session has
the current scripts/docs.

### B. Install over the existing `2a19705` install — no uninstall needed

Pump serials and the DB *file* are unchanged; the four new migrations are
additive and run automatically. Run the new installer directly over the existing
install (same version `0.1.0`, NSIS handles the overwrite). Your Sep 9/10 test
data in `C:\ProgramData\SVR-IOCL\svr.sqlite` is untouched.

1. Right-click the `.exe` → **Run as administrator**. SmartScreen → *More info →
   Run anyway* (unsigned, expected).
2. Accept defaults. On the last page `installer.nsh` runs `first-run.ps1`
   elevated (idempotent — re-applies config, runs migrations `0015`–`0020`,
   restarts both services). A message box means it hit a problem — note the
   exit code.
3. Skip user creation — your existing accounts are already in the DB.
4. **Fully quit SVR IOCL Station** (check Task Manager) before relaunching, or
   you'll still be looking at the old Electron files — the form changes won't
   appear.

### C. Re-validate

The gate is the money, not a green screen. Re-key or re-import the client's own
sheets from `docs/01-BRD-Requirement-Gathering/ocr-samples/`:

| Check | Expect |
|---|---|
| Sep 9 Office (`SVR_DSR_11CC2012V-OFF_09Sep2026_A4.xlsx`) | Net Bal **23,298.77**, Oil total **290.00** |
| Sep 10 Office (`10Sep2026_11CC2012V-OFF.xlsx`) | Net Bal **38,993.84**, Oil total **235.00**, HS amount **66,323.06** (not `.07`) |
| Sep 10 Road (`10Sep2026_12BC4523V-RD.xlsx`) | Net Bal **1,601.20**, Oil total **0.00** |
| Daily Sales Entry, section 2 | **Seven** oil rows in the order above, plus **Total Gas & Oil Sales Amt** |
| Daily Sales Entry, section 7 | **No** Night Cash Hand Off row; label reads `Cash − (Expenses + …)` |
| Print Blank — either serial | Preview opens; **one** A4 portrait page |
| Query button | Loads a saved day and *says* what it found (or that there's nothing) |
| Daily Sales Summary | Headings read "Office Pump (11CC2012V-OFF)" / "Road Pump (12BC4523V-RD)"; green Pump Serial# check line |
| Daily Trial Balance, Section 6 | Buy Rate **102.75** / **113.56** |

Also worth one quick check after any install: `Get-Service
SVR-IOCL-Backend,SVR-IOCL-Scheduler` both `Running`/`Automatic`, and
`Invoke-RestMethod http://127.0.0.1:8756/health` → `{status: ok, ...}`.

### D. Record results

Add `### 5.12 Results (remote PC, 2026-09-12, build 51bab24)` to
`HANDOVER.md` — the checks above plus the service/health check. Commit + push
(branch → `--ff-only` → push → delete branch). On any failure: capture the exact
error + the relevant `C:\ProgramData\SVR-IOCL\logs\*.log` lines and the §4
table below.

---

## 3. Ground rules (CLAUDE.md)

- Model **Claude Sonnet 5**. Plan Mode for any change > 2–3 files or a shared
  formula.
- **Commit/push only when asked.** Branch first if on `main`; pattern is feature
  branch → `git merge --ff-only` → push → delete branch.
- This PC has no Python/Node, so you can't run the test suites here — that's
  fine, they're green on the build PC (backend `ruff` + **211 pytest**, frontend
  `eslint` + **64 Playwright**, `selfcheck` 20 routes, 20 migrations).
- Don't commit `installer/vendor/` or the `.exe` (both git-ignored), or the stray
  `Claude outputs/` · `files.zip` · `releases/` · `Last_update_SVR_Sep7.txt`.

## 4. If the install breaks — likely causes

| Symptom | Cause | Fix |
|---|---|---|
| `first-run.ps1` message box, non-zero exit | a service failed to install/start | `HANDOVER.md` §6; `installer\smoke-services.ps1` (elevated) isolates the service machinery; re-run `installer\first-run.ps1` by hand as admin to see full output |
| Services won't start / backend uses a dev path | machine `SVR_*` env not inherited by the SCM | `HANDOVER.md` §6 items 1–2 |
| Oil rows look wrong on a day saved *before* this build | should not happen — rows resolve by stored label | capture the entry id and its `payload`/`result` JSON before changing anything |
| `ocr/status` → `"bundled": false` | a Tesseract DLL missing, or `SVR_TESSERACT_CMD` wrong | check `...\resources\tesseract\` has the `*.dll`s + `tessdata\`; run `tesseract.exe --version` by hand |
| Win10 `DLL load failed` / missing `VCRUNTIME140` | frozen on Win11 | install VC++ 2015–2022 x64 redist on the target |
| Old UI still shows after install (5 oil rows, Night Cash row, 3-page print) | app wasn't fully quit before/after reinstall | quit **SVR IOCL Station** completely (Task Manager) and relaunch from the Start Menu shortcut |

## 5. Not in scope

Daily Trial Balance Sections 2/4/5/8/9/10/11 as real fields, and the section
numbering mismatch (see §1 — open client decision). Dropping Tesseract/PDF-Scan
(the button is gone from the UI; unbundling the ~175 MB engine is its own
change). Code-signing (wired, dormant — no cert). OCR accuracy on genuine
handwriting (not a blocker — typed PDF/Excel + manual entry are the reliable
paths). Bank-statement reconciliation (not built).
