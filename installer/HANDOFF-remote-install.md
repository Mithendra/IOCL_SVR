# HANDOFF — install build 0.1.2 on the remote PC and run the two-day test

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
against the station's own tabs, to the paisa. §3 is the actual work.

```
C:\Mithendra\SVR\installer\output\SVR-IOCL-Station-Setup-0.1.2.exe
```

- **Unsigned** — by decision (no cert; SmartScreen → *More info* → *Run anyway*
  once). Same as every build so far.
- **Not in git** (`installer/output/` is ignored). Transfer it the same way as
  last time (Google Drive).
- The previously installed build is **0.1.1**. Install 0.1.2 straight over it —
  no uninstall, the DB file is untouched and the new migrations are additive.

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
2. **8.10 Before Close & Sign Off** — the two rows the client asked for, sitting
   directly above Close & Sign Off: *Density Reports updated?* (Yes / No / N/A)
   and *Off Load Testing MS & HS performed by* (Sarath, Gopi, Sriharsha, Girish,
   with **+ New Name** to add a tester permanently). Migration `0034`.
3. **Section 9 keeps 7 days** — a purge button that deletes ledger rows older
   than 7 days, measured from the shift date on screen.
4. **Build-script guards** — see §5. Doesn't affect the station; explains why
   the version jumped.

Everything else carried over from 0.1.1: the posting engine (expenses and
credits post to their master forms at Close & Sign Off, and sign-off is blocked
until they do), the per-nozzle testing rule, the Rs 50 threshold, and the SEP15
rates and inventory.

---

## 2. Install

1. `git pull` this repo so the session has the current scripts and docs.
2. Right-click `SVR-IOCL-Station-Setup-0.1.2.exe` → **Run as administrator**.
   SmartScreen → *More info* → *Run anyway* (unsigned, expected).
3. Accept the defaults. On the last page `installer.nsh` runs `first-run.ps1`
   elevated — idempotent: re-applies config, runs the outstanding migrations,
   restarts both services. A message box means it hit a problem; note the exit
   code and go to §6.
4. Skip user creation — the existing accounts are already in the DB.
5. **Fully quit SVR IOCL Station before relaunching** (check Task Manager). If
   you skip this you are still looking at the old Electron files and none of the
   form changes above will appear. This has caught us before.

Then confirm the machine is actually up:

```powershell
Get-Service SVR-IOCL-Backend, SVR-IOCL-Scheduler     # both Running / Automatic
Invoke-RestMethod http://127.0.0.1:8756/health       # {status: ok, ...}
```

And confirm the new code is really on the box — open **Daily Trial Balance** and
look for **8.10 Before Close & Sign Off** above the Close & Sign Off block. If
it isn't there, the app didn't restart; go back to step 5.

---

## 3. The test — two days, end to end

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
client-mandated, not a bug. Answer the two 8.10 rows. Then Close & Sign Off, and
confirm the next day's draft was created with the carry-forward line.

**(e) Check the postings landed.** Open Monthly Expenses and Credit/Remittance
Master and confirm the rows are there, showing **Posted**. A credit that was
settled the same day should read **Paid**.

### What counts as a pass

Every headline figure matching the station's own tab, to the paisa, on both
days — and both days closed with the postings visible in the two master forms.
A green screen with figures that don't tie is a fail. If something doesn't
match, **capture it and report it — don't adjust the app to make it agree.**

---

## 4. Record the results

Add `### 5.13 Results (remote PC, 2026-09-16, build 0.1.2)` to `HANDOVER.md`:
the install checks from §2, then a row per day per figure — what the app gave,
what the tab says, and whether they match. Commit and push (branch → commit →
`git checkout main` → `git merge --ff-only` → push → delete branch).

On any failure, capture the exact error, the relevant lines from
`C:\ProgramData\SVR-IOCL\logs\*.log`, and the file/tab/cell you were comparing
against.

---

## 5. Ground rules (CLAUDE.md)

- **Commit/push only when asked.** Branch first if on `main`.
- Plan Mode for any change touching more than 2–3 files or a shared formula.
- This PC has no Python/Node, so you can't run the suites here. They are green
  on the build PC: backend **281 passed / 1 skipped**, ruff clean; frontend
  **82 passed**, eslint clean; and the freeze smoke ran `migrate` + `selfcheck`
  (full app graph imported inside the frozen exe).
- Don't commit `installer/vendor/`, `installer/output/`, or anything under
  `docs/01-BRD-Requirement-Gathering/ocr-samples/*/` that is a **bank or IOCL
  statement** — those are gitignored deliberately. **This repo is public.**

## 6. If the install breaks

| Symptom | Cause | Fix |
|---|---|---|
| `first-run.ps1` message box, non-zero exit | a service failed to install/start | `HANDOVER.md` §6; run `installer\smoke-services.ps1` elevated to isolate the service machinery, or `installer\first-run.ps1` by hand as admin for full output |
| Services won't start / backend uses a dev path | machine `SVR_*` env not inherited by the SCM | `HANDOVER.md` §6 items 1–2 |
| **8.10 rows missing from Trial Balance** | app not fully quit before relaunch, or migrations didn't run | quit via Task Manager and relaunch; then check `svr-backend.exe migrate` ran — the log is under `C:\ProgramData\SVR-IOCL\logs\` |
| Close & Sign Off refuses, citing unposted lines | **working as designed** — post the expenses and credits first | use the **Post** button; it lists exactly what is unposted |
| Close & Sign Off demands a reason for a large difference | check 4.9a/4.9b/4.9c are filled in — 4.10 is what's tested | if 4.10 is genuinely over Rs 50, that is a real discrepancy, not a UI problem |
| Win10 `DLL load failed` / missing `VCRUNTIME140` | frozen on Win11 | install the VC++ 2015–2022 x64 redist on the target |

## 7. Not in scope for this round

Bank-statement reconciliation (not built). The PhonePe settlement identity check
(*bank credit = today's settled + yesterday's unsettled*) — not built; the
figures are entered and trusted. Section 9's ledger remains a manual
cross-check. Code-signing (wired, dormant — no cert). OCR on handwriting — the
reliable paths are the typed Excel/PDF upload and manual entry, which is exactly
what this test exercises.
