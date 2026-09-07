# installer/

Packaging + first-run setup for the SVR IOCL Station desktop app. The output is a
single NSIS `.exe` that needs **no Python and no Node** on the target PC, and
**no separate OCR install** — Tesseract rides inside it (SDD ADR-6).

## Build

```powershell
# from the repo root, after `npm ci` in frontend/  (7-Zip also required)
installer\build-all.ps1
```

That runs three steps:

1. **`installer/fetch-tesseract.ps1`** — stages the portable Tesseract payload
   into `installer/vendor/tesseract/` (git-ignored; ~30 MB; version + SHA-256
   pinned in the script). No-op once staged. Air-gapped: `-SourcePath` a
   pre-downloaded setup exe, or hand-place `tesseract.exe` + `tessdata/eng` +
   `tessdata/osd` + `LICENSE` there. See **OCR / Tesseract** below.

2. **`backend/packaging/build-backend.ps1`** — PyInstaller one-dir freeze →
   `backend/packaging/dist/svr-backend/`, containing three console exes that share
   one runtime (`MERGE` in `svr_backend.spec`):

   | exe | role |
   |---|---|
   | `svr-backend.exe` | CLI: `migrate` / `serve` / `scheduler` / `gen-key` |
   | `svr-backend-service.exe` | `SVR-IOCL-Backend` Windows Service host |
   | `svr-scheduler-service.exe` | `SVR-IOCL-Scheduler` Windows Service host |

3. **`npm run dist`** (electron-builder, NSIS) — bundles the frozen backend as
   `resources/backend/` and the staged Tesseract as `resources/tesseract/`
   (`extraResources`), ships `first-run.ps1` + `uninstall.ps1` to
   `<INSTDIR>\installer\` (`extraFiles`), and wires the install/uninstall hooks
   from `frontend/build/installer.nsh`. Output:
   `installer/output/SVR-IOCL-Station-Setup-*.exe`.

CI's `build` job (`.github/workflows/ci.yml`) runs the same steps (with
`installer/vendor/` restored from an `actions/cache` keyed on the pinned version)
and uploads the `.exe` artifact.

**First build + test-VM install: follow [`RUNBOOK.md`](RUNBOOK.md)** — step-by-step
with a pass/fail checklist (services, reboot, `ocr/status`, uninstall) and the
known first-build risks.

## Releasing a new version

The version number is kept by hand in three places — bump all three together:

| File | Field |
|---|---|
| `frontend/package.json` | `"version"` |
| `backend/pyproject.toml` | `[project] version` |
| `backend/src/svr_backend/__init__.py` | `__version__` |

Then:

```powershell
cd backend; .venv\Scripts\python -m ruff check .; .venv\Scripts\python -m pytest -q; cd ..
cd frontend; npm run lint; npx playwright test; cd ..
installer\build-all.ps1
git add -A && git commit -m "release: vX.Y.Z"
git tag vX.Y.Z && git push --tags
```

The installer filename tracks `frontend/package.json`'s version
(`SVR-IOCL-Station-Setup-<version>.exe`). `/health` returns
`backend/__init__.py`'s `__version__`, so keeping the three in step is what makes
the running backend, the API, and the installer all report the same number.

## Code-signing (wired, dormant — no cert yet)

The whole signing path is built and **no-ops until a cert is configured**, so
today's build ships **unsigned**: on a fresh PC SmartScreen shows "Unknown
publisher" and the user clicks *More info → Run anyway* once; the app installs
and runs normally.

**How it's wired.** One switch — `installer/sign.ps1` — signs both the Electron
side (via the `frontend/build/sign-hook.js` hook that electron-builder's
`win.sign` calls per file) and the **3 frozen backend exes** (from
`build-backend.ps1`, since electron-builder never sees inside `extraResources`).
`tesseract.exe` is left as its publisher signed it. `installer/verify-signatures.ps1`
(run at the end of `build-all.ps1` and in CI) reports Authenticode status.

**Turn it on** by setting `SVR_SIGN_METHOD` (+ the matching vars) before
`installer\build-all.ps1`. Timestamp URL: `SVR_SIGN_TIMESTAMP_URL`
(default `http://timestamp.digicert.com`).

| `SVR_SIGN_METHOD` | Needs | Notes |
|---|---|---|
| `none` *(default)* | — | leaves everything unsigned, exits 0 |
| `pfx` | `CSC_LINK` = path to `.pfx`, `CSC_KEY_PASSWORD` | legacy `.pfx` on disk; most CAs no longer issue these (June 2023 key-storage rules) |
| `store` | `SVR_SIGN_CERT_SHA1` (thumbprint) *or* `SVR_SIGN_CERT_SUBJECT`; `SVR_SIGN_CERT_USER_STORE=1` if in `CurrentUser\My` | cert already in the Windows store — a **hardware token** (DigiCert/Sectigo/SSL.com OV/EV, ~$200–600/yr, must be plugged in) **or a self-signed cert** |
| `azure-trusted-signing` | `SVR_ATS_DLIB` (path to the trusted-signing dlib), `SVR_ATS_ENDPOINT`, `SVR_ATS_ACCOUNT`, `SVR_ATS_CERT_PROFILE`, `AZURE_TENANT_ID` / `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` | Microsoft's managed service, ~$10/mo, no token, CI-friendly; needs an Azure subscription + one-time identity validation |

CI (`.github/workflows/ci.yml` `build` job) passes all of these through from repo
**secrets** — unset ⇒ unsigned. For `pfx` in CI, base64 a secret and decode it to
a file first (commented step in the workflow).

### Self-signed (the $0 option for this deployment)

Because the deployer controls every station PC, a self-signed cert trusted on
those machines removes the "Unknown publisher" prompt at no cost (no SmartScreen
reputation; useless off-network). Fully scripted:

```powershell
installer\new-selfsigned-cert.ps1        # creates the cert, exports .cer/.pfx, prints the rest
```

It prints the exact build env vars and the elevated `certutil -addstore Root` /
`-addstore TrustedPublisher` commands to run on each station PC. `*.pfx` / `*.cer`
are git-ignored — **never commit a private key**.

### Verify

```powershell
installer\verify-signatures.ps1              # informational
installer\verify-signatures.ps1 -RequireSigned   # exit 1 if anything is unsigned (release gate)
```

## What the installer does on the target

`perMachine` + assisted (not one-click), so it runs elevated. On install,
`installer.nsh` → `customInstall` runs **`first-run.ps1`**:

1. Creates the data + per-component log tree under `C:\ProgramData\SVR-IOCL`
   (SDD 14.3).
2. Persists `SVR_DATA_DIR` / `SVR_DB_PATH` / `SVR_LOG_DIR` as **machine**
   environment variables (so the SCM-started services see them), generates
   `SVR_FIELD_KEY` (Fernet, SDD 13.3) once if unset, and points
   `SVR_TESSERACT_CMD` / `SVR_TESSDATA_PREFIX` at the bundled
   `resources\tesseract\` (SDD ADR-6).
3. Applies SQLite migrations (`svr-backend.exe migrate`).
4. Registers **both Windows Services** `--startup auto` and starts them.
5. Adds the Electron frontend as a per-user Startup-folder shortcut (SDD 19
   item 23 — not a service).

On uninstall, `customUnInstall` runs **`uninstall.ps1`**: stops + deletes both
services, removes the Startup shortcut, and clears
`SVR_TESSERACT_CMD` / `SVR_TESSDATA_PREFIX` (they point into the deleted
`<INSTDIR>`). It deliberately **keeps `C:\ProgramData\SVR-IOCL`** (DB, nightly
backups, logs) and the data-tree env vars (incl. `SVR_FIELD_KEY`) so a reinstall
resumes cleanly.

## Service model (SDD §7.1 / ADR-2)

| Service | Runs | Startup |
|---|---|---|
| `SVR-IOCL-Backend` | uvicorn loopback API + calc engine + RBAC + audit | Automatic |
| `SVR-IOCL-Scheduler` | APScheduler 23:59 IST carry-forward + daily SQLite backup | Automatic |

SQLite gets no service (a file, opened in-process). Tesseract gets no service (a
binary shelled out to on demand — SDD ADR-2 / ADR-6).

## OCR / Tesseract (bundled — SDD ADR-6)

The OCR **engine** ships inside the installer; the OCR **pipeline** (scan →
parsed entry → human review) is a separate module, not yet built, so
`POST /daily-sales-entry/ocr` still returns `501`. What is wired now:

| Piece | Where |
|---|---|
| Staging script | `installer/fetch-tesseract.ps1` — pinned version + SHA-256; `-SourcePath` / hand-place for air-gapped |
| Staged payload | `installer/vendor/tesseract/` — `tesseract.exe` + `*.dll` + `tessdata/{eng,osd}.traineddata` + `LICENSE`; git-ignored |
| Bundled into | `<INSTDIR>\resources\tesseract\` via `frontend/package.json` → `build.extraResources` |
| Runtime pointers | `SVR_TESSERACT_CMD`, `SVR_TESSDATA_PREFIX` — machine env, set by `first-run.ps1`, cleared by `uninstall.ps1` |
| Backend resolver | `svr_backend/core/config.py` (`resolved_tesseract_cmd()`) + `svr_backend/ocr/runtime.py` (`is_available()`, `tesseract_version()`) |
| Health check | `GET /daily-sales-entry/ocr/status` → `{bundled, cmd, version}` — use it in clean-VM validation |

Language data is **`eng` + `osd` only** — the shift sheets are English headings
with Western-Arabic digits (the Telugu toggle is a UI label swap). `tel` is not
shipped; revisit only if a form is hand-filled in Telugu numerals.

## Still follow-on (not in this packaging pass)

1. **Obtain a code-signing cert** and flip `SVR_SIGN_METHOD` on (the path is
   wired — see "Code-signing" above). Also: auto-update.
2. **Clean-VM validation** — install on a fresh Windows 11 VM: both services
   `Automatic` + `Running` in `services.msc`; `C:\ProgramData\SVR-IOCL\logs\`
   populated; `svr.sqlite` migrated; `GET /daily-sales-entry/ocr/status` reports
   `bundled: true`; the Startup shortcut opens the app and it reaches the
   backend; reboot re-launches everything; uninstall removes the services +
   Tesseract env vars but keeps the data tree.
