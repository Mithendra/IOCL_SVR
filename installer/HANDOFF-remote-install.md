# HANDOFF — install build 0.1.5 on the remote PC and run the two-day test

**Written:** 2026-09-16 · **Repo:** `https://github.com/Mithendra/IOCL_SVR.git` ·
**Branch:** `main`

Paste this whole file as the first message of the Claude Code session on the
remote PC, then read (in order): this file → [`installer/RUNBOOK.md`](RUNBOOK.md)
→ [`HANDOVER.md`](../HANDOVER.md) §5 → [`CLAUDE.md`](../CLAUDE.md).

---

## 1. What this build is for

The client set the test themselves:

> "Remote PC build for testing to add two days of data upload using Excel Sheet
> DSR reports and perform Sales Summary and Trail balance manually"

So this is not an install-and-tick exercise. **The install is step zero.** The
test is whether two real days go in through the Excel DSR upload, come out
through Daily Sales Summary, and reconcile in Daily Trial Balance — by hand,
against the station's own tabs, to the paisa. §4 is the actual work.

```
C:\Mithendra\SVR\installer\output\SVR-IOCL-Station-Setup-0.1.5.exe
```

- **Unsigned** — by decision (no cert; SmartScreen → *More info* → *Run anyway*
  once). Same as every build so far.
- **Not in git** (`installer/output/` is ignored). Transfer it the same way as
  last time (Google Drive).
- The previously installed build is **0.1.1**. Install 0.1.5 straight over it —
  no uninstall needed. The installer leaves the database alone; §3 then replaces
  it deliberately, because this round starts from an empty database.

### What changed since 0.1.1

0.1.1 was cut before the last day of work. Two of these are the reason a new
build is needed at all, rather than nice-to-haves:

1. **The escalation check now reads 4.10 Total Difference, not the raw 4.5.**
   This one blocks the test. The client extended their difference panel this
   month, and on SEP16 the raw difference reads −37,578.64 while the true
   difference is −20.64 — the gap is staff salaries paid and an RTGS charge,
   both already explained on their own sheet at `F55`/`F56`. Under 0.1.1 the app
   would have **refused to close SEP16** and demanded a written reason for a day
   that actually balances inside the Rs 50 limit. Section 4 gained **4.9a Staff
   Salaries**, **4.9b RTGS / Bank Charges**, **4.9c Other Adjustment**, and 4.10
   switches on whenever any of them is filled.
2. **8.17 Before Close & Sign Off** — the two rows the client asked for, sitting
   directly above Close & Sign Off: *Density Reports updated?* (Yes / No / N/A)
   and *Off Load Testing MS & HS performed by* (Sarath, Gopi, Sriharsha, Girish,
   with **+ New Name** to add a tester permanently). Migration `0034`.

   Two defects in this were found and fixed on 2026-09-16, after the client
   asked whether it was really done. The **+** button returned
   `400 Unknown list 'offload_testers'` — the names were seeded but writes go
   through a separate allow-list that had not been updated, so the "add more
   names" half never worked. And three rows on the form were numbered 8.10:
   this block, *Send to Management*, and the Management Summary's *Yesterday's
   Actual Reported Trial Balance*. The client's workbook owns 8.8–8.15, so the
   app-side blocks are now **8.16 Sign-off**, **8.17 Before Close & Sign Off**
   and **8.18 Send to Management**.
3. **Section 9 keeps 7 days** — a purge button that deletes ledger rows older
   than 7 days, measured from the shift date on screen.
4. **Bank names, balances only.** The three banks were already named text with a
   statement balance (3.8 IOCL, 3.9 Indian Bank, 3.10 Yes Bank); migration
   `0035` seeds those names as a list, and a test now fails the build if an
   account number, IFSC code, UPI handle, PAN or MICR ever reaches a migration,
   seed or screen. Client, 2026-09-16: *"Do not want expose those details in
   the application JUST STATEMENT BALANCE ONLY."* Nothing to check during the
   test beyond: if you ever see an account number on screen, that is a defect.
5. **Build-script guards** — see §6. Doesn't affect the station; explains why
   the version jumped twice in one day.

Everything else carried over from 0.1.1: the posting engine (expenses and
credits post to their master forms at Close & Sign Off, and sign-off is blocked
until they do), the per-nozzle testing rule, the Rs 50 threshold, and the SEP15
rates and inventory.

---

## 1a. Where things stand (2026-09-16, end of day)

This session is starting cold, so here is the state you are inheriting. There is
no way to resume the build PC's conversation here — a Claude Code transcript is
local to its machine — so this section and the rest of this file *are* the
handover.

**Done and pushed to `main`:** the two pre-close rows and their fixes; the
escalation reading 4.10 rather than the raw 4.5; the Section 9 seven-day purge;
bank names as text with a test barring account numbers, IFSC codes, UPI handles
and PANs from the app; 4.1 now carrying forward at sign-off; and a rehearsal
(`backend/tests/test_sep15_sep16_rehearsal.py`) that walks SEP15 and SEP16 end
to end on a clean database — upload, Summary, Inventory, Trial Balance, post,
Close & Sign Off, postings checked on the master forms. Both days pass.

Backend **288 passed / 1 skipped**, ruff clean. Frontend **83 passed**, eslint
clean. Build **0.1.5**, SHA256 begins `5F48F5BB`.

**Two questions are open with the client. Do not decide either one here:**

1. **SEP16's 4.2.** The road DSR prints `O22` = **1,485.30**; the tab's
   hand-typed `D50` of 171,762.2496 implies **1,476.83**. The app follows the
   DSR, so 4.10 reads **-12.16** where the tab says -20.64. Both are inside the
   Rs 50 limit and the day closes either way. The client has been asked which
   figure should stand and has not answered.
2. **The SEP14/15/16 workbooks are not in the repo.** Pushing them was stopped
   because one Road DSR's credit-customer dropdown carries an Xtra Power fleet
   card number — a third party's account. It is already public via
   `SVR_DSR_13SEP26/SVR-DSR-12BC4523V-RD_12SEP26.xlsx`, so the client is
   deciding between pushing as-is, redacting that cell, or scrubbing history.
   **Until they say so, do not add those workbooks and do not force-push.**

**Known and not defects:** the SEP15→SEP16 oil stock jump (2T/2.40 closes at 5,
opens at 80) is a restock the client told us to ignore; Acid Water 64 → 0 is the
write-off they instructed; and sign-off refusing until expenses and credits are
posted is the gate they called mandatory.

---

## 2. Install

1. `git pull` this repo so the session has the current scripts and docs.
2. Right-click `SVR-IOCL-Station-Setup-0.1.5.exe` → **Run as administrator**.
   SmartScreen → *More info* → *Run anyway* (unsigned, expected).

   If it says **"SVR IOCL Station cannot be closed, please close it manually"**,
   leave the dialog open and, in an elevated PowerShell:

   ```powershell
   Stop-Process -Name "SVR IOCL Station" -Force; Stop-Service SVR-IOCL-Backend,SVR-IOCL-Scheduler
   ```

   then click **Retry**. Electron runs several processes under that one name, so
   closing the window is not enough. **Never click Ignore** — the install then
   proceeds over files still in use and leaves a half-updated app, which looks
   exactly like "the new build didn't work".
3. Accept the defaults. On the last page `installer.nsh` runs `first-run.ps1`
   elevated — idempotent: re-applies config, runs the outstanding migrations,
   restarts both services. A message box means it hit a problem; note the exit
   code and go to §7.
4. Skip the installer's user-creation page — §3 resets the database and makes
   the account; anything created here would be wiped by that reset.
5. **Fully quit SVR IOCL Station before relaunching** (check Task Manager). If
   you skip this you are still looking at the old Electron files and none of the
   form changes above will appear. This has caught us before.

Then confirm the machine is actually up:

```powershell
Get-Service SVR-IOCL-Backend, SVR-IOCL-Scheduler     # both Running / Automatic
Invoke-RestMethod http://127.0.0.1:8756/health       # {status: ok, ...}
```

And confirm the new code is really on the box — open **Daily Trial Balance** and
look for **8.17 Before Close & Sign Off** above the Close & Sign Off block. If
it reads 8.10, or isn't there at all, the app didn't restart — go back to
step 5. Press **+ New Name** too: it should open a box and accept a name. A
`400 Unknown list` there means the backend is still the old build.

---

## 3. Start from an empty database

The client asked for this explicitly: the database should hold **SEP15 and SEP16
and nothing else**, so what is on screen can be compared against the Excel tabs
without older test data confusing the picture.

A freshly migrated database is already clean. Every transactional table is empty
— daily sales entries, summaries, trial balances, postings, monthly expenses,
credit transactions and the audit log all sit at zero. What it does carry is
reference data that *should* be there: the seven oil items and their rates, the
seven expense categories, the dropdown lists, and the system parameters
(testing 5 litres per nozzle, escalation threshold Rs 50).

**The remote PC's existing database is not empty** — it still holds the Sep 9,
10 and 12 rounds. Replace it, with both services stopped:

```powershell
Stop-Service SVR-IOCL-Backend, SVR-IOCL-Scheduler

$db  = 'C:\ProgramData\SVR-IOCL\svr.sqlite'
$exe = 'C:\Program Files\SVR IOCL Station\resources\backend\svr-backend.exe'

Rename-Item $db 'svr.sqlite.before-sep15-test'   # keep it - do not delete
& $exe migrate --db $db
& $exe create-user --name owner --role Owner

Start-Service SVR-IOCL-Backend, SVR-IOCL-Scheduler
```

Rename, never delete. If the test goes sideways that file is the only record of
the earlier rounds.

The `create-user` line matters: a fresh database has **no users at all**, so
without it there is nothing to log in with. (Skip the installer's own
user-creation page in §2 — this reset would wipe whatever it made.)

### Three things to set before keying SEP15

These are the places where a clean database does *not* already match the sheet.
Each is a number to type, not a bug to report.

**1. Opening stock.** The shipped inventory is seeded at **SEP15's closing**
(with the Acid Water written off, as the client instructed). Neither day's
opening matches it, so set the opening on the Inventory screen before each day.
Manager or Owner can do it, and the field *replaces* rather than adds:

| Oil item | SEP15 opens | SEP16 opens |
|---|---|---|
| 2T/1.50 ML | 0 | 0 |
| **2T/2.40 ML** | **10** | **80** |
| **Acid Water 1 Lt** | **64** | **0** |
| Battery Water 1 Lt | 27 | 27 |
| Battery Water 5 Lts | 18 | 18 |
| 20/40 Engine 05 Lts | 38 | 38 |
| 20/40 Engine 1 Lt | 0 | 0 |

Read off the tabs themselves, column D (opening) against column E (closing),
rows 19-25. Two of these look wrong and are not:

- SEP15 closes 2T/2.40 at **5** but SEP16 opens it at **80**. That is the
  restock the client flagged — *"there is an Oil Sale(s) inventory gap between
  SEP15 and SEP16, please ignore it for today"* — not a carry-forward failure.
- Acid Water goes **64 → 0** because the stock was expired and written off on
  the client's instruction (migration `0033`).

**2. The SEP15 opening balance.** With an empty database there is no SEP14 to
carry forward from, so 4.1 has to be typed once: **2,217,954.86** (SEP14's
`D52`). SEP16's 4.1 then carries itself across from SEP15's close — 0.1.5 is
the first build that does this. Until now the operator retyped it every day,
which is the hand-typed cross-day reference ADR-2 was written to abolish; it was
found by rehearsing this very test. Check it lands on **2,305,795.10** without
being typed.

**3. Testing litres.** Both tabs read `=E3-5` and `=E4-5`, so on each day only
**one nozzle per fuel** drew testing. In the app that happens when the other
pump files Current = Last on both its nozzles. File movement on all four and the
app will deduct 10 per fuel and `K4` will not match — correctly so.

---

## 4. The test — two days, end to end

Source files are in `docs/01-BRD-Requirement-Gathering/ocr-samples/`.

### Day 1 and Day 2: upload, summarise, reconcile

For **each** of the two days, in this order:

**(a) Upload both DSRs.** Each day has two — Office (`11CC2012V-OFF`) and Road
(`12BC4523V-RD`). Daily Sales Entry → upload the Excel → **review before
saving**. The app recomputes every total and flags mismatches rather than
trusting the sheet (ADR-5); read what it flags, don't click past it.

**(b) Daily Sales Summary.** Both pumps should appear with the green Pump
Serial# check. Combined consumption per fuel is what Trial Balance Section 3
pulls, so if this is wrong, stop here — nothing downstream can be right.

**(c) Daily Trial Balance, by hand.** Key the day the way the station does, then
compare against their tab. The figures that matter:

| Where | What to check |
|---|---|
| Section 1 `G3`/`G4` | Testing: **5 litres per nozzle that moved**, per fuel. Both pumps running = 10 per fuel; one pump = 5. A nozzle whose Current equals Last draws nothing. |
| Section 1 `K4` | Total Sale Amt |
| **4.2** | Should compute, not need typing: **day's sales − the DSR's Beta/Density/Testing line (`O22`)**. The screen marks it *computed* vs *typed*. |
| **4.5** | The raw difference |
| **4.10** | **The one that decides sign-off.** Fill 4.9a/4.9b/4.9c where the station's panel has them, and 4.10 should land inside Rs 50. |
| `D69` / `D74` | Stock Value and Net Worth |

**(d) Post, then close.** Before Close & Sign Off, hit **Post** — expenses go to
Monthly Expenses, credits and remittances to the Credit/Remittance Master. The
app will not let the day close until they are posted; that is deliberate and
client-mandated, not a bug. Answer the two 8.17 rows. Then Close & Sign Off, and
confirm the next day's draft was created with the carry-forward line.

**(e) Check the postings landed.** Open Monthly Expenses and Credit/Remittance
Master and confirm the rows are there, showing **Posted**. A credit that was
settled the same day should read **Paid**.

### The figures, both days

Read off the client's own tabs. SEP15 is `SEP15/Trail_balance_15SEP2026.xlsx`;
SEP16 is `SEP16/Trail_balance_16SEP2026_Revised_oil_Sale(s)_stock.xlsx`.

| Cell | What it is | SEP15 | SEP16 |
|---|---|---|---|
| `G3` | HS after testing | 279.48 | 936.76 |
| `G4` | MS after testing | 496.68 | 622.98 |
| `K4` | Total Sale Amt | 2,870.6980 | 5,126.0808 |
| `D49` | 4.1 Yesterday | 2,217,954.86 *(typed)* | 2,305,795.10 *(carried)* |
| `D50` | 4.2 Today's Sale | 87,840.2488 | 171,762.2496 |
| `D52` | 4.4 Reported | 2,305,795.10 | 2,439,978.71 |
| `D53` | 4.5 raw difference | 0.00 | **-37,578.64** |
| `F57` | **4.10 true difference** | 0.00 | **-20.64** |
| `D69` | Stock Value | 1,009,926.14 | 846,697.80 |
| `D74` | Net Worth | 3,315,721.24 | 3,286,676.51 |

SEP16 is the interesting one. 4.5 reads -37,578.64 and 4.10 reads -20.64; the
difference between them is 37,500.00 of staff salaries (4.9a) and 58.00 of RTGS
charges (4.9b), the latter confirmed on the Indian Bank statement of 15 Sep.
Fill 4.9a and 4.9b and the day closes; leave them out and the app will stop you,
correctly, because on the figures it can see the day is 37,578 out.

SEP15 is the control: it balances to 0.00 with nothing in the panel at all.

**Expect 4.10 to read -12.16 on SEP16, not -20.64, and do not log it as a bug.**
This was rehearsed here before the build went out. The whole 8.47 sits in 4.2:
the road DSR prints `O22` = **1,485.30**, while the tab's hand-typed `D50` of
171,762.2496 implies 1,476.83. The app computes 4.2 from the DSR - the source
document - so it gets 173,239.0796 - 1,485.30 = **171,753.77** (truncated, as
the station's sheets truncate). SEP15 has no such gap, so it is one day's
typing rather than a formula. Both figures are well inside Rs 50 and the day
closes cleanly either way. Worth asking the client which they want to stand.

### What counts as a pass

Every headline figure matching the station's own tab, to the paisa, on both
days — and both days closed with the postings visible in the two master forms.
A green screen with figures that don't tie is a fail. If something doesn't
match, **capture it and report it — don't adjust the app to make it agree.**

---

## 5. Record the results

Add `### 5.13 Results (remote PC, 2026-09-16, build 0.1.5)` to `HANDOVER.md`:
the install checks from §2, then a row per day per figure — what the app gave,
what the tab says, and whether they match. Commit and push (branch → commit →
`git checkout main` → `git merge --ff-only` → push → delete branch).

On any failure, capture the exact error, the relevant lines from
`C:\ProgramData\SVR-IOCL\logs\*.log`, and the file/tab/cell you were comparing
against.

---

## 6. Ground rules (CLAUDE.md)

- **Commit/push only when asked.** Branch first if on `main`.
- Plan Mode for any change touching more than 2–3 files or a shared formula.
- This PC has no Python/Node, so you can't run the suites here. They are green
  on the build PC: backend **281 passed / 1 skipped**, ruff clean; frontend
  **82 passed**, eslint clean; and the freeze smoke ran `migrate` + `selfcheck`
  (full app graph imported inside the frozen exe).
- Don't commit `installer/vendor/`, `installer/output/`, or anything under
  `docs/01-BRD-Requirement-Gathering/ocr-samples/*/` that is a **bank or IOCL
  statement** — those are gitignored deliberately. **This repo is public.**

## 7. If the install breaks

| Symptom | Cause | Fix |
|---|---|---|
| `first-run.ps1` message box, non-zero exit | a service failed to install/start | `HANDOVER.md` §6; run `installer\smoke-services.ps1` elevated to isolate the service machinery, or `installer\first-run.ps1` by hand as admin for full output |
| Services won't start / backend uses a dev path | machine `SVR_*` env not inherited by the SCM | `HANDOVER.md` §6 items 1–2 |
| **8.17 rows missing from Trial Balance** | app not fully quit before relaunch, or migrations didn't run | quit via Task Manager and relaunch; then check `svr-backend.exe migrate` ran — the log is under `C:\ProgramData\SVR-IOCL\logs\` |
| Close & Sign Off refuses, citing unposted lines | **working as designed** — post the expenses and credits first | use the **Post** button; it lists exactly what is unposted |
| Close & Sign Off demands a reason for a large difference | check 4.9a/4.9b/4.9c are filled in — 4.10 is what's tested | if 4.10 is genuinely over Rs 50, that is a real discrepancy, not a UI problem |
| Win10 `DLL load failed` / missing `VCRUNTIME140` | frozen on Win11 | install the VC++ 2015–2022 x64 redist on the target |

## 8. Not in scope for this round

Bank-statement reconciliation (not built). The PhonePe settlement identity check
(*bank credit = today's settled + yesterday's unsettled*) — not built; the
figures are entered and trusted. Section 9's ledger remains a manual
cross-check. Code-signing (wired, dormant — no cert). OCR on handwriting — the
reliable paths are the typed Excel/PDF upload and manual entry, which is exactly
what this test exercises.
