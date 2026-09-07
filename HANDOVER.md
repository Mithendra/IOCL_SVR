# HANDOVER — SVR IOCL Station: packaging & deployment validation

**Written:** 2026-08-29 · **For:** a fresh Claude Code session on the dedicated
**testing PC** (a clean Windows 11 box with **no Python, no Node, no VS Code**).

Read this first, then [`CLAUDE.md`](CLAUDE.md) and
[`installer/README.md`](installer/README.md). The authoritative product spec is
`docs/02-System-Design-Architecture/`.

---

## 1. Where the project stands

- **All 12 modules are built** end-to-end (backend + Electron screen + tests).
  Backend `pytest` 87, frontend Playwright 32, `ruff`/`eslint` clean. Module 12
  (Daily Trial Balance) ships partial — see the README table.
- **Packaging is code-complete and builds cleanly** on a dev machine: a single
  NSIS installer (`SVR-IOCL-Station-Setup-<version>.exe`) that bundles a
  PyInstaller-frozen backend, so the target PC needs **no Python and no Node**.
- **Packaging IS validated on the testing PC** (updated 2026-09-04 — see §5.8
  below for the results). Reboot survives, services auto-start, the app
  auto-launches, forms load and save. §5.7 (uninstall) is deliberately
  **deferred, not skipped** — the testing PC stays installed for continued
  use; uninstall gets verified when that machine is actually decommissioned
  or at real deployment time.

### What the packaging session delivered (commit history around 2026-08-29)

| Area | Files |
|---|---|
| Frozen backend (PyInstaller one-dir, 3 exes) | `backend/packaging/svr_backend.spec`, `backend/packaging/entry_cli.py`, `backend/packaging/build-backend.ps1`, `[build]` extra in `backend/pyproject.toml` |
| Bundle into installer | `frontend/package.json` › `build` (`extraResources`, `extraFiles`, `nsis`), `frontend/build/installer.nsh` (elevated install/uninstall hooks) |
| First-run / teardown | `installer/first-run.ps1` (rewritten for frozen exes, machine-wide `SVR_*` config, one-time Fernet key, service register+start), `installer/uninstall.ps1` (new), `installer/build-all.ps1` (new one-shot local build) |
| Electron main process | `frontend/src/main/main.js` — splash + `/health` poll (≤20 s); if the backend service is down in a packaged build, falls back to spawning the bundled `svr-backend.exe serve` |
| CI | `.github/workflows/ci.yml` — `build` job freezes the backend before `npm run dist` |
| Docs | `installer/README.md`, `README.md`, `CLAUDE.md` |

---

## 2. This testing PC — what it needs

Its job is to mirror the real station PC, so keep it **clean of build tools**.

**Install:**

1. **Administrator rights** on the box (the installer registers Windows Services).
2. **Claude Code — native install** (`https://claude.ai/download`). Runs without
   Node or VS Code; this is how the next session runs here.
3. **Git** — to `git clone https://github.com/Mithendra/IOCL_SVR.git` so the session
   can read this file + the scripts + logs. (Or just copy the project folder over
   and skip Git.) Everything is on **`main`** — there is no PR to merge, just clone.
4. **The installer `.exe`** — see §3. It is **not** in the repo.

**Do NOT install:** Visual Studio, **VS Code**, **Python**, **Node**. None are
needed to run the installer, and any of them present makes this a less honest
"clean target" test. (No C/C++ toolchain is needed anywhere in this project.)

**OS:** target is Windows 11 (matches the build PC). If you ever test on Windows
10, use 64-bit 21H2/22H2 — see §6 item 5 for the one failure mode to watch.

### Two-machine model

| Machine | Role |
|---|---|
| **This testing PC** | Runs the acceptance test (§5). No Python/Node/VS. |
| **Build PC** (has Python 3.11+ & Node 20+) | Rebuilds only. If §5 finds a bug in `first-run.ps1` / the spec / `main.js`, fix + re-freeze + new `.exe` happens there (`installer\build-all.ps1`), then copy the new `.exe` back here and re-test. Still no Visual Studio. |

> The "symlink privilege / Developer Mode" issue from the build PC is a
> **build-time** electron-builder quirk only. It has **nothing to do with
> installing or running** the app. Ignore it on this PC.

---

## 3. Getting the installer onto this PC

`SVR-IOCL-Station-Setup-0.1.0.exe` is ~111 MB and **git-ignored** (`installer/output/`),
so it is never committed. Get it one of these ways:

- **From CI (preferred):** GitHub Actions › latest `CI` run on `main` › `build`
  job › artifact **`svr-iocl-station-installer`**. Download and unzip.
- **Manual copy:** on the build PC it is at
  `installer/output/SVR-IOCL-Station-Setup-0.1.0.exe` — copy via USB / network
  share / cloud.
- **Rebuild on a dev machine** (needs Python 3.11+ and Node 20+): `npm ci` in
  `frontend/`, then `installer\build-all.ps1`. Not possible on this testing PC.

---

## 4. Before you install — sanity checks (on this PC, no admin)

```powershell
# nothing from a previous attempt is lingering
Get-Service SVR-IOCL-Backend,SVR-IOCL-Scheduler -ErrorAction SilentlyContinue
Test-Path C:\ProgramData\SVR-IOCL
[Environment]::GetEnvironmentVariable('SVR_DATA_DIR','Machine')
Test-Path "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\SVR IOCL Station.lnk"
```

All should be empty / `False` / absent on a truly clean box. If not, a prior
install left residue — run `installer\uninstall.ps1` from an old copy or clean up
by hand first.

---

## 5. The acceptance test — run this and record every result

### 5.1 Install

1. Right-click `SVR-IOCL-Station-Setup-0.1.0.exe` → **Run as administrator**.
2. **SmartScreen will warn** ("Windows protected your PC") because the build is
   **unsigned** — click **More info → Run anyway**. (Code-signing is pending; see §7.)
3. Complete the assisted installer (it is `perMachine`, so it elevates and installs
   to `C:\Program Files\SVR IOCL Station` by default).
4. Watch for the post-install step: `installer.nsh` runs `first-run.ps1` elevated.
   If it fails it pops a message box with an exit code — note it.

### 5.2 Verify — services

```powershell
Get-Service SVR-IOCL-Backend,SVR-IOCL-Scheduler | Format-Table Name,Status,StartType
sc.exe qc SVR-IOCL-Backend      # BINARY_PATH_NAME must point at
                                #   ...\resources\backend\svr-backend-service.exe
                                # START_TYPE must be AUTO_START
sc.exe qc SVR-IOCL-Scheduler
```
**Expected:** both `Running` + `Automatic`, and each `BINARY_PATH_NAME` is the
frozen `*-service.exe` (NOT `python -m ...`).

### 5.3 Verify — data tree, config, DB

```powershell
Get-ChildItem C:\ProgramData\SVR-IOCL -Recurse -Depth 1
# expect: svr.sqlite ; logs\ with 6 files ; backups\ (may be empty until 00:15 IST)

[Environment]::GetEnvironmentVariable('SVR_DATA_DIR','Machine')   # C:\ProgramData\SVR-IOCL
[Environment]::GetEnvironmentVariable('SVR_DB_PATH','Machine')    # ...\svr.sqlite
[Environment]::GetEnvironmentVariable('SVR_LOG_DIR','Machine')    # ...\logs
[Environment]::GetEnvironmentVariable('SVR_FIELD_KEY','Machine')  # a long base64 string — MUST be set

Get-Content C:\ProgramData\SVR-IOCL\logs\backend-service.log -Tail 30
Get-Content C:\ProgramData\SVR-IOCL\logs\scheduler.log      -Tail 30
```
**Expected:** `svr.sqlite` exists and is non-trivial (migrations ran);
`backend-service.log` shows uvicorn "Application startup complete"; no repeated
tracebacks.

### 5.4 Verify — API is up

```powershell
Invoke-RestMethod http://127.0.0.1:8756/health   # {status: ok, version: ...}
```

### 5.5 Verify — the app

1. `C:\Program Files\SVR IOCL Station\SVR IOCL Station.exe` — launch it.
2. A brief "Starting SVR IOCL Station…" splash, then the **login screen**.
3. Log in. If the DB was seeded there are demo users `gsales` / `mmanager` /
   `oowner`, password `demo1234`; otherwise create an Owner via whatever
   first-run path the app provides. Confirm at least one screen loads real data.
4. Confirm the **Startup shortcut** exists:
   `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\SVR IOCL Station.lnk`.

### 5.6 Verify — reboot

Reboot the PC. **Without logging into the app**, check:
```powershell
Get-Service SVR-IOCL-Backend,SVR-IOCL-Scheduler   # both Running again
```
Then log in to Windows → the app should auto-launch from the Startup shortcut and
reach the backend.

### 5.7 Verify — uninstall

Uninstall via **Settings → Apps** (or `C:\Program Files\SVR IOCL Station\Uninstall SVR IOCL Station.exe`).
```powershell
Get-Service SVR-IOCL-Backend,SVR-IOCL-Scheduler -ErrorAction SilentlyContinue  # gone
Test-Path C:\ProgramData\SVR-IOCL    # STILL True — data is deliberately kept
Test-Path "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\SVR IOCL Station.lnk"  # False
```

### 5.8 Results (testing PC, 2026-09-04)

| Step | Result |
|---|---|
| 5.1 Install | ✅ Done (installed ~2026-08-31; unsigned SmartScreen click-through as expected) |
| 5.2 Services | ✅ `SVR-IOCL-Backend` + `SVR-IOCL-Scheduler` both `Running` |
| 5.3 Data tree / logs | ✅ `backend-service.log` has continuous real `uvicorn.access` entries spanning 2026-08-31 → 2026-09-04 (`/health`, `/auth/login`, `/auth/me`, `/daily-sales-entry/*`, `/daily-trial-balance/*`, all `200`) — confirms migrations ran, DB healthy, `SVR_LOG_DIR` machine env var reached the service |
| 5.4 `/health` | ✅ (implied by the log entries above) |
| 5.5 App + login | ✅ Logged in as `mmanager`; Daily Sales Entry + Daily Trial Balance forms load and save |
| 5.6 Reboot | ✅ **Confirmed 2026-09-04** — after restarting the testing PC, both services were up on their own and the app auto-launched from the Startup shortcut and reached the backend, no manual intervention |
| 5.7 Uninstall | ⏸ **Deferred on purpose (2026-09-04)** — the testing PC stays installed for continued use rather than being torn down now. Uninstall gets verified at actual deployment/decommission time, not before. |

**Net effect:** the biggest unverified risk from §6 (frozen service registration +
SCM start + Machine env-var inheritance) is now confirmed working end-to-end,
across a reboot. The earlier `log_config=None` fix (commits `abe737f`/`eac2a38`)
turned out not to be needed to reproduce this — logging worked without it on this
install — but it stays in the codebase as cheap defensive hygiene.

---

## 6. Assumptions that are UNVERIFIED — watch these closely

The packaging session could not test any of this (no admin service lifecycle on
the build box). If the acceptance test fails, it is most likely one of these.

> **Shortcut for items 1–4:** `installer\smoke-services.ps1` (run from an
> **elevated** PowerShell) does an isolated register → start → `/health` → stop →
> remove of both frozen services against a TEMP data dir, restoring everything
> afterwards. It touches neither `C:\ProgramData\SVR-IOCL` nor any real install,
> so it is safe to run **on the build PC** for the earliest possible signal —
> before the full §5 test on a clean box. Green here = the service machinery is
> sound and a §5 failure is elsewhere (installer, env, SmartScreen).

1. **Frozen service registration.** Does `svr-backend-service.exe --startup auto
   install` write the exe's own path as the service `ImagePath` (pywin32's
   frozen-exe path), and can the SCM actually start it (the bare-argv →
   `StartServiceCtrlDispatcher` branch in
   `backend/src/svr_backend/services/backend_service.py`)?
2. **Env-var inheritance.** `first-run.ps1` sets `SVR_*` as **Machine**
   environment variables *before* starting the services, so the SCM should hand
   them to the service processes. If the backend logs show it using a dev default
   path instead of `C:\ProgramData\SVR-IOCL`, this is why.
3. **Fernet key.** `SVR_FIELD_KEY` must be generated once and persisted Machine;
   employee bank fields are encrypted with it. If it is missing, the backend runs
   with an insecure dev key and logs a warning.
4. **First-run exit codes.** `first-run.ps1` exits `3` if a service failed to
   install/start; `installer.nsh` surfaces that in a message box.
5. **Frozen binary vs. OS runtime.** The `.exe` is built on Windows 11 x64. On
   Windows 11 this is a non-issue. If it ever fails on Windows 10 with
   `DLL load failed` / a missing `api-ms-win-*` or `VCRUNTIME140*.dll`, install
   the **VC++ 2015–2022 x64 redistributable** on the target, or re-freeze on
   Windows 10. `tzdata` (for `Asia/Kolkata`) *is* bundled — verified — so the
   scheduler's timezone is not a concern.

### If something fails — where to look

- `C:\ProgramData\SVR-IOCL\logs\*.log` (six per-component files).
- `services.msc` and `sc.exe qc <name>` / `Get-EventLog System -Source "Service Control Manager" -Newest 20`.
- Re-run the post-install step by hand to see full output:
  ```powershell
  powershell -ExecutionPolicy Bypass -File "C:\Program Files\SVR IOCL Station\installer\first-run.ps1" -InstallDir "C:\Program Files\SVR IOCL Station"
  ```
- Run the frozen backend in the foreground to see startup errors directly:
  ```powershell
  & "C:\Program Files\SVR IOCL Station\resources\backend\svr-backend.exe" serve
  ```

---

## 7. Pending work (after the acceptance test passes)

### Must do to be "deployable"
| Item | Note |
|---|---|
| **Acceptance test (§5)** | ✅ 5.1–5.6 confirmed on the testing PC (see §5.8), including a reboot. **5.7 uninstall deliberately deferred** to actual deployment/decommission time — not a blocker. |
| **Fix whatever §6 surfaces** | ✅ Nothing bad surfaced — service registration, SCM start, and Machine env-var inheritance all confirmed working. |
| **CI `build` job green** | ✅ Confirmed — every push from `0c61e9f` onward (through `ac020fa`) built successfully, artifact `svr-iocl-station-installer` present. |

### Should do for a real release
| Item | Note |
|---|---|
| **Code-signing (Authenticode)** | Removes the SmartScreen warning; needs an OV/EV cert or org PKI. Wire into `frontend/package.json` › `build.win` (`certificateFile`/`certificateSubjectName`). |
| **App + installer icon** | `frontend/build/icon.ico` (electron-builder currently logs "default Electron icon is used"). |
| **`author` field** in `frontend/package.json` | electron-builder warns; feeds NSIS publisher metadata. |
| **Version-sync / release steps** | `frontend/package.json`, `backend/pyproject.toml`, `svr_backend.__version__` are hand-kept at `0.1.0`. Document a bump+build+tag process. |

### Deferred by design (do NOT pre-build these)
| Item | Why it waits |
|---|---|
| **Tesseract OCR bundling** (SDD ADR-6, `SVR_TESSERACT_PATH`) | The OCR module isn't built — Daily Sales Entry OCR/Excel endpoints return `501`. Bundle it *with* that module, verified against a real scanned sheet. |
| **Auto-update** (electron-updater) | Needs (a) an update-feed host, (b) code-signing done first, (c) a design for updating the frozen backend + re-registering services. All three are open decisions. |

---

## 8. Test cases / QA status

- **Exists:** unit + integration tests — backend `pytest` (87), frontend
  Playwright (32). CI runs them on every push.
- **Does NOT exist:** a formal **acceptance / UAT test-case set** for the
  deployed product (installer, services, per-module business workflows against
  the AUG11/AUG12 workbook data, RBAC per role, carry-forward at 23:59 IST,
  backup/restore). §5 of this doc is a first manual pass, not that suite.
- **Plan:** start the UAT test-case suite **after** the deployable build is
  signed off (acceptance test green + §7 "must do" cleared). Likely scope: one
  test-case document per form (mirror `docs/02-System-Design-Architecture/module-spec-book.html`),
  plus cross-module formula chains and the deployment/DR checklist.

---

## 9. File map (packaging)

```
backend/packaging/
  svr_backend.spec       PyInstaller one-dir; MERGE → 3 shared exes:
                           svr-backend.exe            (migrate|serve|scheduler|gen-key)
                           svr-backend-service.exe    (SVR-IOCL-Backend service host)
                           svr-scheduler-service.exe  (SVR-IOCL-Scheduler service host)
  entry_cli.py           subcommand shim over svr_backend.cli
  build-backend.ps1      freeze + smoke; → backend/packaging/dist/svr-backend/

frontend/
  package.json  › build  extraResources (frozen backend → resources/backend/),
                         extraFiles (first-run.ps1 + uninstall.ps1 → installer/),
                         nsis (perMachine, assisted, elevation)
  build/installer.nsh    customInstall → first-run.ps1 ; customUnInstall → uninstall.ps1
  src/main/main.js       health-wait splash + bundled-backend fallback spawn

installer/
  first-run.ps1          migrations, Machine SVR_* config, one-time Fernet key,
                         register+start both services, per-user Startup shortcut
  uninstall.ps1          stop+delete services, remove shortcut, KEEP data tree
  smoke-services.ps1     ELEVATED, self-cleaning: isolated register/start/health/
                         stop/remove of the frozen services (see §6 shortcut box)
  build-all.ps1          one-shot: freeze backend → npm run dist
  README.md              current packaging reference
```

## 10. Rebuilding the installer (dev machine only)

```powershell
# needs Python 3.11+ and Node 20+
cd <repo>\frontend ; npm ci ; cd ..
installer\build-all.ps1
# → installer\output\SVR-IOCL-Station-Setup-<version>.exe
```
