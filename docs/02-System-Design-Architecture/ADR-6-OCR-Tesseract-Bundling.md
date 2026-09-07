# ADR-6 — OCR: Tesseract bundled inside the single installer

**Status:** ACCEPTED 2026-09-07. Decides only the **packaging** question — "does
Tesseract ship inside the one `.exe`, or does it need a separate install step?".
The OCR pipeline itself (image → parsed Daily Sales Entry → human review) is a
separate, not-yet-started module; `POST /daily-sales-entry/ocr` still returns
`501` until that module is built. This ADR removes the deployment blocker so that,
once the pipeline lands, **Scan / Upload works with zero extra setup on the
station PC**.
**Relates to:** SDD §14 (deployment), SDD ADR-2 (Tesseract gets no Windows
Service — "a library invoked on demand"), SDD ADR-5 (human review before save on
every non-manual entry path — the OCR pipeline must recompute and flag
mismatches, never silently trust the scan).

## Context

The Daily Sales Entry screen has a **Scan / Upload** action for turning a
photographed / scanned paper shift sheet into a draft entry. The recognition step
needs an OCR engine. SDD §3 fixed that engine as **Tesseract** and SDD ADR-2
already ruled it is not a service — it is a command-line binary the backend
shells out to when a scan is submitted.

The station PC is a single on-prem machine that:

- may have **no reliable internet** at install time (rural dealership; the whole
  point of the desktop app is that it runs offline),
- is installed by whoever deploys the machine, **not** by a developer — the
  install has to be one double-click, "Next, Next, Finish", elevated once,
- must come back up with **zero human action** after a reboot or power cut
  (confirmed with client 2026-09-06).

So the OCR engine has to be present and working the moment the pipeline module is
switched on, with nothing else for the operator to do.

Tesseract is **not** a Python package — it is a native `tesseract.exe` plus a
`tessdata/` folder of trained language models. That shapes where it can live.

## Decision

**Bundle a pinned, portable build of Tesseract 5.x inside the NSIS installer as
its own `extraResources` payload**, alongside (not inside) the frozen Python
backend.

Concretely:

1. **Layer.** Tesseract rides beside the backend, not within it. electron-builder
   `build.extraResources` gets a second entry:

   ```jsonc
   { "from": "../installer/vendor/tesseract", "to": "tesseract" }
   ```

   Installed layout on the target:

   ```
   <INSTDIR>\resources\backend\    svr-backend.exe, service exes  (PyInstaller freeze)
   <INSTDIR>\resources\tesseract\  tesseract.exe, *.dll,
                                   tessdata\eng.traineddata,
                                   tessdata\osd.traineddata,
                                   LICENSE  (Apache-2.0)
   ```

2. **Not in the PyInstaller freeze.** `backend/packaging/svr_backend.spec` stays
   Python-only. Freezing a 30 MB native binary + language data into every backend
   rebuild is the wrong layer: it bloats and slows every backend iteration,
   couples the OCR engine's version to the backend's, and muddies the
   redistribution story. The freeze already knows how to *not* own things that
   aren't Python (SQLite is a file; the services are hosts) — Tesseract is the
   same shape.

3. **Language data: `eng` + `osd` only.** The shift sheets are English column
   headings with Western-Arabic numerals (the Telugu heading toggle is a UI label
   swap only — the *data* on the page is `0-9`). `eng.traineddata` covers the
   digits and headings; `osd.traineddata` gives orientation / skew detection for
   phone photos. `tel.traineddata` is deliberately **not** shipped — revisit only
   if a form is ever hand-filled in Telugu numerals.

4. **The vendor payload is not committed to git.** `installer/vendor/tesseract/`
   is git-ignored. It is populated before a build by **`installer/fetch-tesseract.ps1`**,
   which downloads a **version-pinned** archive, verifies its **SHA-256**, and
   lays out only the files listed above. `installer/build-all.ps1` runs it as its
   first step and hard-fails if the folder is still empty; CI's `build` job
   caches the folder keyed on the pinned version. An operator with no network can
   pass a locally-downloaded archive via `-ZipPath`.

5. **Runtime wiring.** `installer/first-run.ps1` sets two **machine** environment
   variables (so the SCM-started backend service sees them):

   | var | value |
   |---|---|
   | `SVR_TESSERACT_CMD` | `<INSTDIR>\resources\tesseract\tesseract.exe` |
   | `SVR_TESSDATA_PREFIX` | `<INSTDIR>\resources\tesseract\tessdata` |

   `backend/src/svr_backend/core/config.py` reads both (`SVR_` prefix, as with
   every other setting). `svr_backend/ocr/runtime.py` resolves the command,
   exports `TESSDATA_PREFIX` for the child process, and exposes
   `is_available()` / `tesseract_version()`. `GET /daily-sales-entry/ocr/status`
   surfaces `{bundled, cmd, version}` so the post-install / clean-VM check can
   confirm OCR landed without needing a real scan.

6. **Uninstall.** `installer/uninstall.ps1` removes those two env vars (they point
   into the deleted `<INSTDIR>`). The data tree and `SVR_FIELD_KEY` are still kept
   per the existing policy.

## Alternatives rejected

- **Chain the UB Mannheim Tesseract installer from NSIS.** A second elevated
  sub-installer with its own UI, its own uninstall entry, and its own PATH
  mutation; leaves a half-configured machine if it is cancelled midway; makes the
  backend depend on `tesseract` being on `PATH` rather than a known path we
  control. More moving parts for the operator, not fewer.
- **Bundle inside the PyInstaller freeze.** Wrong layer (see Decision 2).
- **Download Tesseract at first-run.** Needs internet on a machine that may not
  have it, and turns a deterministic install into one that can fail at the
  customer site for reasons unrelated to the app.
- **`winget install tesseract` from first-run.** Same network dependency, plus a
  dependency on winget being present and the package staying available at a
  compatible version.

## Consequences

- Installer grows by **~30 MB** (`tesseract.exe` + runtime DLLs + `eng`/`osd`
  data). Acceptable for a once-per-station download.
- The Tesseract version is **pinned in `fetch-tesseract.ps1`** (URL + SHA-256).
  Upgrading it is a deliberate one-line change + a new hash, not an implicit
  "whatever the CA/mirror serves today".
- Apache-2.0 `LICENSE` for Tesseract ships in `resources\tesseract\` to satisfy
  redistribution terms.
- `pytesseract` + `Pillow` are **not** added as backend dependencies by this ADR
  — they land with the OCR pipeline module (as a `backend[ocr]` extra), and are
  not part of the frozen `[build,win]` set. `ocr/runtime.py` uses `subprocess`
  only, so the bundled binary is verifiable today with no new Python deps.
- Still out of scope, unchanged by this ADR: the OCR pipeline (pre-processing,
  field extraction, the recompute-and-flag review step per ADR-5), and Excel
  import/export.
