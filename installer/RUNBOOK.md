# Installer runbook — first build & VM install

The goal of this pass is to **prove the deployment path**, not to test on the real
station PC. Two machines:

- **Dev machine** (this repo, Windows) — builds the `.exe`.
- **Test VM** — a throwaway Windows 10/11 VM (Hyper-V / VirtualBox / spare box)
  with a local admin account. Take a snapshot before installing so you can roll
  back and re-test the installer repeatedly.

Claude cannot run either step — both are you, on Windows, with admin rights.
Everything below is wired and lint/parse-clean; what it has **not** had is a real
PyInstaller freeze + NSIS build + elevated install, which is exactly what this
runbook shakes out.

---

## Step 1 — Build the installer (dev machine)

### 1.0 Prereqs (once)

| Need | Check | Get it |
|---|---|---|
| Python 3.12 + `backend/.venv` | `backend\.venv\Scripts\python --version` | `py -m venv backend\.venv; backend\.venv\Scripts\pip install -e "backend[dev,build,win]"` |
| Node 20+ + `frontend/node_modules` | `node -v` | `winget install OpenJS.NodeJS.LTS`; then `cd frontend; npm ci` |
| 7-Zip on PATH | `7z` | `winget install 7zip.7zip` |
| Internet (first run only) | — | for the one-time Tesseract download |

### 1.1 Pin the Tesseract hash (one-time, ~5 min)

```powershell
installer\fetch-tesseract.ps1 -SkipHashCheck
```

It downloads the UB Mannheim build, stages `installer\vendor\tesseract\`, and
**prints the actual SHA-256**. Open `installer\fetch-tesseract.ps1`, replace
`$SetupSha256 = "REPLACE_WITH_PINNED_SHA256"` with that hash, save. From now on
the script (and CI) verify the download and you can drop `-SkipHashCheck`.

Commit that one-line change.

### 1.2 Build

```powershell
installer\build-all.ps1
```

Three stages, each fails loud:

1. **Stage Tesseract** — no-op now that `installer\vendor\tesseract\` is populated.
2. **Freeze backend** (`backend\packaging\build-backend.ps1`) — PyInstaller
   one-dir → `backend\packaging\dist\svr-backend\`. Smoke-tests the frozen exe:
   `migrate` builds a fresh DB, `serve --help`, and **`selfcheck`** (imports the
   whole app graph inside the frozen exe — this is the check that catches a
   missing PyInstaller hidden-import here instead of on the station PC).
3. **Package** (`npm run dist`) — electron-builder NSIS →
   `installer\output\SVR-IOCL-Station-Setup-<version>.exe`.

### 1.3 Step 1 pass criteria

- [ ] `build-all.ps1` exits 0.
- [ ] `installer\output\SVR-IOCL-Station-Setup-*.exe` exists; size is roughly
      **backend freeze (~40–70 MB) + Tesseract (~30 MB) + Electron (~90 MB)**.
      A wildly smaller file means `extraResources` didn't pick something up.
- [ ] Unzip-peek the installer (`7z l ...exe`) or just note: `resources\backend\`
      and `resources\tesseract\` both present with content.

If the **freeze** step fails on an `ImportError` / `ModuleNotFoundError` during
`selfcheck`: add the named module to `_hiddenimports` in
`backend\packaging\svr_backend.spec`, rebuild. That's the normal PyInstaller
tightening loop.

---

## Step 2 — Install on the test VM

Copy `SVR-IOCL-Station-Setup-*.exe` to the VM. **Snapshot the VM first.**

### 2.1 Install

Run the `.exe`. It is *assisted* + *perMachine*, so it prompts for elevation and
lets you pick the install dir. Accept defaults. On the last page it runs
`first-run.ps1` elevated (migrations, config, service registration, Startup
shortcut).

If SmartScreen blocks it ("Unknown publisher") — expected, it's unsigned →
*More info → Run anyway*.

### 2.2 Step 2 checklist

**Services**

- [ ] `services.msc` shows **SVR-IOCL-Backend** — *Running*, *Automatic*.
- [ ] `services.msc` shows **SVR-IOCL-Scheduler** — *Running*, *Automatic*.
- [ ] `Get-Service SVR-IOCL-*` from an admin PowerShell agrees.

**Data + config**

- [ ] `C:\ProgramData\SVR-IOCL\svr.sqlite` exists.
- [ ] `C:\ProgramData\SVR-IOCL\logs\` has the six `*.log` files, and
      `backend-service.log` shows uvicorn started on `127.0.0.1:8756`.
- [ ] `[Environment]::GetEnvironmentVariable("SVR_FIELD_KEY","Machine")` is set
      (44-char base64).
- [ ] `SVR_TESSERACT_CMD` / `SVR_TESSDATA_PREFIX` point at real files under
      `...\resources\tesseract\`.

**Backend reachable**

- [ ] `curl http://127.0.0.1:8756/health` → 200 with a version.
- [ ] `curl http://127.0.0.1:8756/daily-sales-entry/ocr/status` →
      `{"bundled": true, "version": "tesseract 5.x...", ...}`.
      **This is the out-of-the-box OCR-engine proof (SDD ADR-6).**

**Frontend**

- [ ] A `SVR IOCL Station` shortcut is in the current user's Startup folder
      (`shell:startup`).
- [ ] Launching it opens the app; it reaches the backend (login screen, no
      "cannot connect").
- [ ] Log in as an owner you create (or seed demo users — see note) and click
      into Daily Sales Entry; totals compute.

**Reboot (the real requirement — SDD §19 item 23 / CLAUDE.md)**

- [ ] Reboot the VM. Without logging in and touching anything, both services are
      *Running* again.
- [ ] Log in → the Electron app comes up on its own from the Startup shortcut and
      reaches the backend.

**Uninstall (§5.7)**

- [ ] Uninstall via *Apps & features*. `uninstall.ps1` runs.
- [ ] Both services are **gone** (`Get-Service SVR-IOCL-*` → nothing).
- [ ] Startup shortcut is gone.
- [ ] `SVR_TESSERACT_CMD` / `SVR_TESSDATA_PREFIX` are cleared.
- [ ] `C:\ProgramData\SVR-IOCL\` (DB, backups, logs) and `SVR_FIELD_KEY` are
      **kept** (by design — a reinstall must resume cleanly).
- [ ] Reinstall on top → still healthy, same DB.

> **First login:** production `migrate` seeds no accounts. Create the first
> Owner from an elevated PowerShell on the VM:
> `& "C:\Program Files\SVR IOCL Station\resources\backend\svr-backend.exe" create-user --role Owner --name "<Full Name>" --login <login>`
> (prompts for the password). `first-run.ps1` prints this same line on a fresh
> install. For a throwaway smoke test, `migrate --seed-demo` still works
> (`oowner` / `demo1234`).
>
> **Before real-data testing:** log in as the Owner and enter the current IOCL
> Buy/Sell rates in **Rate Master** — the seeded `rate_master` rows are
> placeholders, and Daily Sales Entry locks whatever rate is effective when a
> record is created.

---

## Known risks to watch (first build)

| Risk | Symptom | Fallback |
|---|---|---|
| **Frozen pywin32 service registration** | `svr-backend-service.exe --startup auto install` errors, or the service installs but won't start | `first-run.ps1` already falls back to `python -m svr_backend.services.*` when the frozen exe is absent — but here it's present. If the frozen host misbehaves, the fix is usually adding `_exe_name_ = sys.executable` to the two `ServiceFramework` classes; do that as a follow-up commit once you can reproduce it. |
| **`importlib.resources` in the freeze** | `migrate` fails to find `NNNN_*.sql` | `build-backend.ps1` runs `migrate` in its smoke, so this fails at build time, not install time. If it does: switch `_discover()` to a `sys._MEIPASS`-aware path. |
| **Tesseract DLLs missing** | `ocr/status` → `bundled: false` on the VM though the folder shipped | `fetch-tesseract.ps1` copies every `*.dll` next to `tesseract.exe`; if one is still missing, add it to the copy list. |
| **electron-builder can't find `extraResources`** | tiny installer, or `resources\tesseract\` empty | the `from:` paths are relative to `frontend\`; confirm `installer\vendor\tesseract\` and `backend\packaging\dist\svr-backend\` both exist before `npm run dist`. |

---

## Not covered here — the real station PC

After Step 2 passes on the VM, the remaining install work is on the **actual
dealership PC** and needs the client:

1. Windows auto-logon / passwordless local account (so the session starts
   unattended after a power cut — a Windows-account step, not an app step; see
   `CLAUDE.md` open items).
2. Real SMTP host/creds if `SVR_EMAIL_BACKEND=smtp` is wanted (else it stays
   `memory`/`file`).
3. Code-signing (removes the SmartScreen prompt — separate task).
4. **Real-data UAT** — enter live daily sales for a stretch of days and
   cross-check every calculation (Trial Balance, Stock Value, Cash Recon,
   carry-forward) against reality. Do the Trial Balance §6 formula workbook
   cross-check *before* this.
