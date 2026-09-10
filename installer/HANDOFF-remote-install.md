# HANDOFF — install the built installer on the remote PC & validate

**Written:** 2026-09-10 · **Repo:** `https://github.com/Mithendra/IOCL_SVR.git` ·
**Branch:** `main` · **HEAD:** `bc27d97`

Paste this whole file as the first message of the Claude Code session on the
remote PC, then read (in order): this file → [`installer/RUNBOOK.md`](RUNBOOK.md)
→ [`HANDOVER.md`](../HANDOVER.md) §5 → [`CLAUDE.md`](../CLAUDE.md).

---

## 1. State

**The installer is already built** on the build PC (2026-09-10, from `main` @
`bc27d97`):

```
C:\Mithendra\SVR\installer\output\SVR-IOCL-Station-Setup-0.1.0.exe   (177.7 MB)
```

- **Unsigned** — by decision (no cert; SmartScreen "Run anyway" once). The
  code-signing path is wired but dormant.
- Freeze smoke passed: `migrate` builds a DB, `serve --help`, and **`selfcheck`
  imported the full app graph inside the frozen exe — 20 routes** (openpyxl,
  pyotp, pymupdf all frozen clean).
- Bundles `resources\backend\` (3 frozen exes) + `resources\tesseract\` (the OCR
  engine, ~175 MB on disk, LZMA-compressed in the installer).
- It is **NOT in git** (`installer/output/` is ignored) — it must be transferred
  from the build PC (USB / network share / cloud).

### What's in this build (vs the last installed v0.1.0, 2026-09-04)

All 12 modules **plus**: `create-user` CLI (first-Owner bootstrap), Excel
import/export (module 1), 2FA/TOTP (module 5), Employee Master insurance
sections 3–5 (module 8), and the OCR draft-assist pipeline. Version string is
still `0.1.0` (not bumped).

### OCR reality — do not test against it as if it works

`POST /daily-sales-entry/ocr` is wired (not `501`) but is **draft-assist only**.
Stock Tesseract **cannot read the handwritten Daily Sales sheets** — measured
0/6 across three approaches on real scans, see
[`docs/01-BRD-Requirement-Gathering/OCR-findings-2026-09-09.md`](../docs/01-BRD-Requirement-Gathering/OCR-findings-2026-09-09.md).
Real-data testing runs on **manual entry + Excel import**. `ocr/status` should
still report `bundled: true` — that only proves the engine is present.

---

## 2. Your task, in order

### A. Get the installer onto this PC

Copy `SVR-IOCL-Station-Setup-0.1.0.exe` from the build PC. (This PC is meant to be
a clean target — **no Python / Node / VS Code**. Only Git + Claude Code + the
`.exe`, per `HANDOVER.md` §2.) `git clone` / `git pull` the repo so this session
can read the scripts, logs, and checklists — but the `.exe` comes separately.

### B. Install

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
3. **Create the first Owner** — `first-run.ps1` prints this line; run it from an
   **elevated** PowerShell:
   ```powershell
   & "C:\Program Files\SVR IOCL Station\resources\backend\svr-backend.exe" `
       create-user --role Owner --name "<Full Name>" --login <login>
   ```
   (prompts for the password). Production `migrate` seeds no accounts, so this is
   the only way in. `migrate --seed-demo` (`oowner`/`demo1234`) is for throwaway
   tests only.
4. Launch **SVR IOCL Station** → log in as that Owner.
5. **Rate Master → enter the real current IOCL Buy/Sell rates.** The seeded
   `rate_master` rows are placeholders; Daily Sales Entry locks whatever rate is
   effective when a record is created.

### C. Validate (record every result)

Run `HANDOVER.md` §5.2–5.7 in full. The items that are **new or were deferred**:

| Check | Expect |
|---|---|
| `Get-Service SVR-IOCL-Backend,SVR-IOCL-Scheduler` | both `Running` / `Automatic`; `sc.exe qc` ImagePath = the frozen `*-service.exe` |
| `Invoke-RestMethod http://127.0.0.1:8756/health` | `{status: ok, version: ...}` |
| `Invoke-RestMethod http://127.0.0.1:8756/daily-sales-entry/ocr/status` | `{"bundled": true, "version": "tesseract 5.3.3...", "pipeline": "draft-assist"}` |
| machine env `SVR_TESSERACT_CMD` / `SVR_TESSDATA_PREFIX` | point at real files under `...\resources\tesseract\` |
| `C:\ProgramData\SVR-IOCL\` | `svr.sqlite` migrated; `logs\` has 6 files; `backend-service.log` shows uvicorn startup, no repeated tracebacks |
| **Reboot** | without touching anything, both services `Running`; then Windows login → app auto-launches from the Startup shortcut and reaches the backend |
| **§5.7 uninstall — do it for real** (deferred on 2026-09-04) | Settings → Apps → uninstall → both services gone, Startup shortcut gone, `SVR_TESSERACT_CMD`/`SVR_TESSDATA_PREFIX` **cleared**, `C:\ProgramData\SVR-IOCL\` + `SVR_FIELD_KEY` **kept**. Reinstall on top → healthy, same DB. |

### D. Record results

Add `## 5.10 Results (remote PC, 2026-09-10)` to `HANDOVER.md` mirroring the §5.8
table. Note the actual `.exe` size/version. Commit + push (branch → `--ff-only`
→ push → delete branch). On any failure: capture the exact error + the relevant
`C:\ProgramData\SVR-IOCL\logs\*.log` lines and the §4 table below.

---

## 3. Ground rules (CLAUDE.md)

- Model **Claude Sonnet 5**. Plan Mode for any change > 2–3 files or a shared
  formula.
- **Commit/push only when asked.** Branch first if on `main`; pattern is feature
  branch → `git merge --ff-only` → push → delete branch. End commit messages with
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- This PC has no Python/Node, so you can't run the test suites here — that's fine,
  they're green on the build PC (backend `ruff` + **143 pytest**, frontend
  `eslint` + **39 Playwright**, `selfcheck` 20 routes).
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

## 5. Not in scope

Code-signing (wired, dormant — no cert). OCR accuracy (Tesseract can't read the
handwriting — see the findings doc; not a blocker, testing runs on manual +
Excel). Bank-statement reconciliation (not built). Windows auto-logon on the
station PC (a one-time Windows-account step for whoever deploys it — CLAUDE.md
open-items note — not something the app or `first-run.ps1` does).
