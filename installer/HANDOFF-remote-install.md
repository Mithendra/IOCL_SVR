# HANDOFF — remote-PC installer rebuild & re-validation (Tesseract)

**Written:** 2026-09-07 · **Repo:** `https://github.com/Mithendra/IOCL_SVR.git` ·
**Branch:** `main` · **HEAD at handoff:** `442affb`

Paste this whole file as the first message of a fresh Claude Code session on the
remote PC, then let it read (in this order): this file → [`HANDOVER.md`](../HANDOVER.md)
→ [`installer/RUNBOOK.md`](RUNBOOK.md) → [`CLAUDE.md`](../CLAUDE.md).

---

## 1. Why this session exists

The single-`.exe` installer was **already built and validated end-to-end** on the
dedicated testing PC on **2026-09-04** (see `HANDOVER.md` §5.8): install → both
Windows Services `Running`/`Automatic` → migrations ran → `/health` OK → app
login → **reboot survived, services + app came back with zero human action**.
That version was **v0.1.0** and did **not** contain the OCR engine.

Since then `main` has moved on. The part that matters for packaging:

| Commit | What changed | Needs re-validation? |
|---|---|---|
| `3c4cd42` | **Tesseract OCR engine bundled inside the installer** (ADR-6) — new `extraResources` payload, `SVR_TESSERACT_CMD` / `SVR_TESSDATA_PREFIX` machine env vars, `GET /daily-sales-entry/ocr/status`, `uninstall.ps1` now clears those vars | **Yes — this is the delta** |
| `442affb` | Freeze hardening — `svr-backend selfcheck` (imports full app graph in the frozen exe; run in the freeze smoke), defensive PyInstaller hidden-imports (anyio, python-multipart, argon2, pywin32 DLL modules), `installer/RUNBOOK.md` | Yes — new hidden-imports could in principle bloat or break the freeze |
| earlier (`d6a8d57`, `cacfa9c`, `96e26d8`) | Trial Balance ADR-1/ADR-2 work, repo rename SVR→IOCL_SVR, docs | No packaging impact |

**So the frozen-pywin32-service risk is already retired** (proven on 2026-09-04).
The new unknowns are narrow: (a) does Tesseract actually land in the built `.exe`
and resolve on the target, and (b) does the freeze still build clean with the
extra hidden-imports.

---

## 2. Your task, in order

### A. Pin the Tesseract download hash (build PC, ~5 min, one-time)

```powershell
installer\fetch-tesseract.ps1 -SkipHashCheck
```

It downloads the pinned UB Mannheim Tesseract build, stages
`installer\vendor\tesseract\`, and **prints the actual SHA-256**. Edit
`installer\fetch-tesseract.ps1` → replace
`$SetupSha256 = "REPLACE_WITH_PINNED_SHA256"` with that hash → save.
Commit just that line: `git commit -am "Pin Tesseract SHA-256"` → `git push`.

If the build PC has no internet: download
`tesseract-ocr-w64-setup-5.3.3.20231005.exe` elsewhere, then
`installer\fetch-tesseract.ps1 -SourcePath <path-to-that-exe> -SkipHashCheck`
(7-Zip still required), and pin the hash it prints.

### B. (Recommended) bump the version 0.1.0 → 0.1.1

So the new installer is distinguishable from the 2026-09-04 one. Three files, in
step (see `installer/README.md` "Releasing a new version"):
`frontend/package.json` `"version"`, `backend/pyproject.toml` `[project] version`,
`backend/src/svr_backend/__init__.py` `__version__`. Commit + push.

### C. Build the installer (build PC)

Prereqs: Python 3.12 + `backend\.venv` (`pip install -e "backend[dev,build,win]"`),
Node 20+ + `cd frontend; npm ci`, **7-Zip on PATH**.

```powershell
installer\build-all.ps1
```

Watch the **freeze smoke** — it now runs `svr-backend selfcheck`. If that fails
with `ModuleNotFoundError: X`, add `X` to `_hiddenimports` in
`backend\packaging\svr_backend.spec` and rebuild. That's the expected tightening
loop; commit any additions.

**Step-C pass:** `installer\output\SVR-IOCL-Station-Setup-<version>.exe` exists;
size ≈ **v0.1.0's ~111 MB + ~30 MB Tesseract ≈ 140 MB**. `7z l` the exe (or check
a test extraction) shows both `resources\backend\` and `resources\tesseract\`
(with `tesseract.exe`, `*.dll`, `tessdata\eng.traineddata`, `tessdata\osd.traineddata`).

### D. Install + re-validate (clean testing PC — or a throwaway VM snapshot)

Full checklist is `installer/RUNBOOK.md` §2 and `HANDOVER.md` §5. Run all of it,
but these are the items that are **new or previously deferred** — do not skip:

1. **`GET http://127.0.0.1:8756/daily-sales-entry/ocr/status`** →
   `{"bundled": true, "cmd": "...\\resources\\tesseract\\tesseract.exe",
   "version": "tesseract 5.3.3", "pipeline": "not-implemented"}`.
   This is the whole point of the rebuild — OCR engine present & runnable
   out-of-the-box.
2. `SVR_TESSERACT_CMD` / `SVR_TESSDATA_PREFIX` machine env vars point at real
   files under the install dir.
3. `/health` still 200; both services still `Running`/`Automatic`; reboot still
   brings everything back unattended (re-confirm — the extra hidden-imports
   shouldn't matter, but confirm).
4. **§5.7 uninstall — do it for real this time** (it was deferred on 2026-09-04):
   uninstall → both services gone, Startup shortcut gone,
   `SVR_TESSERACT_CMD` / `SVR_TESSDATA_PREFIX` **cleared**,
   `C:\ProgramData\SVR-IOCL\` + `SVR_FIELD_KEY` **kept**. Then reinstall on top →
   still healthy, same DB.

### E. Record results

Add a `## 5.9 Results (remote PC, 2026-09-…)` section to `HANDOVER.md` mirroring
the §5.8 table, plus an OCR row. Commit + push. If anything failed, capture the
exact error + the relevant `C:\ProgramData\SVR-IOCL\logs\*.log` lines.

---

## 3. Ground rules (from CLAUDE.md — keep these)

- Model: **Claude Sonnet 5**. Plan Mode for any change touching >2–3 files or a
  shared formula.
- **Commit/push only when asked.** Branch first if on `main`; the established
  pattern here is: feature branch → `git merge --ff-only` to `main` → push →
  delete branch. End commit messages with
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- Backend gate before any push: `cd backend; .venv\Scripts\python -m ruff check .;
  .venv\Scripts\python -m pytest -q` (expect **101 passed**). Frontend:
  `cd frontend; npm run lint` (Playwright needs a built backend venv — see README).
- Don't commit `installer/vendor/` (git-ignored), the `.exe` (git-ignored), or the
  stray `Claude outputs/` · `files.zip` · `releases/` in the working tree — they
  are not part of this work.

## 4. If the freeze or install breaks — likely causes

| Symptom | Cause | Fix |
|---|---|---|
| `selfcheck` fails in the freeze smoke, `ModuleNotFoundError` | PyInstaller missed a dynamic import | add the module to `_hiddenimports` in `svr_backend.spec`, rebuild |
| Installer much smaller than ~140 MB | `extraResources` didn't pick up Tesseract | `installer\vendor\tesseract\` must exist *before* `npm run dist`; `from:` paths are relative to `frontend\` |
| `ocr/status` → `"bundled": false` on the target | `tesseract.exe` ran but a DLL is missing, or the env var is wrong | check `...\resources\tesseract\` has the `*.dll`s; check `SVR_TESSERACT_CMD`; run that exe `--version` by hand on the target |
| Services won't start / use a dev path | Machine env vars not inherited by SCM | `HANDOVER.md` §6 items 1–2; `installer\smoke-services.ps1` (elevated) isolates this |
| Win10 `DLL load failed` / missing `VCRUNTIME140` | frozen on Win11 | install VC++ 2015–2022 x64 redist on the target, or re-freeze on Win10 (`HANDOVER.md` §6 item 5) |

---

## 5. What is NOT in scope here

The OCR **pipeline** (scan image → parsed entry → human review) is not built —
`POST /daily-sales-entry/ocr` still returns `501`. This session only proves the
**engine** ships and resolves. Also out of scope: code-signing, real-data multi-day
UAT, and the first-real-Owner-account bootstrap (there's no admin bootstrap flow
yet — for testing, seed with
`svr-backend.exe migrate --seed-demo` then log in as `oowner` / `demo1234`).
