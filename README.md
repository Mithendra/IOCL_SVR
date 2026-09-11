# SVR Indian Oil Service Station — Daily Operations System

Digitizes the paper-based daily operations of Sri Venkata Ramana Indian Oil Service
Station, Ponnur (an IOCL dealer outlet). Desktop application: ElectronJS frontend +
Python loopback backend + SQLite, packaged as a single Windows installer.

The full requirement history and the authoritative design live in
[`docs/`](docs/) — the 20-section System Design & Architecture Document
(`docs/02-System-Design-Architecture/`) is the spec; see [`CLAUDE.md`](CLAUDE.md)
for the load-bearing conventions.

**[`docs/02-System-Design-Architecture/IMPLEMENTATION-MAP.md`](docs/02-System-Design-Architecture/IMPLEMENTATION-MAP.md)**
maps each of the 12 forms to its exact module files (router, calc engine,
migration, screen, tests) — the place to look when a specific form has an issue.
Its print‑to‑PDF companion is
[`module-spec-book.html`](docs/02-System-Design-Architecture/module-spec-book.html)
(one page per form; open in a browser → Print → Save as PDF).

## Status

**Foundation + all 12 modules built end-to-end** (backend + Electron screen +
pytest/Playwright), each following the Daily Sales Entry reference pattern.
Backend `pytest` **87**; frontend Playwright **32**; `ruff` + `eslint` clean.
Module 12 (Daily Trial Balance) ships **partial** — see its row.

| Area | State |
|---|---|
| Foundation: migrations, auth/session, RBAC, audit, calc engine, 23:59 IST carry-forward, APScheduler, Windows Services, per-component logging, field encryption at rest, email (memory/file/SMTP) | done |
| **1. Daily Sales Entry** — per-pump/shift entry; locked Sell-rate + inventory-opening snapshot; carried-reading auto-locks once a prior day exists, open for manual entry on a pump's very first day; calc engine; **Save / Update / Delete are distinct toolbar actions** (Update only once a day is saved, Delete Manager/Owner-only; a correction edits the same row, no duplicate, and re-opens the day's Summary side for re-verification); **Excel import/export** (round-trips, recompute-and-flag; a natural non-SVR workbook falls back to a paper-layout parser); **Scan/Upload** — typed PDFs/AI-transcribed documents read from the text layer (reliable), handwriting via Tesseract draft-only (`OCR-findings-2026-09-09.md`); **Print/Print Blank** match the physical form (Sections 1-7 only). All non-manual paths: never save, ADR-5 review. | done |
| **2. Daily Sales Summary** — combines both pump submissions; per-pump verification; both-verified gate on upload to Trial Balance | done |
| **3. Rate Master** — Owner-only append-only Buy/Sell rate versioning + change-log; Manager view-only | done |
| **4. Inventory Tracking** — 5 oil SKUs; restock log; low-stock status; feeds Daily Sales Entry opening stock | done |
| **5. Manage Users** — user CRUD, role assignment, last-Owner guards; **2FA (TOTP)**: self-enrollment on the Security screen, two-step login challenge, admin "Clear 2FA" for a locked-out user (secret Fernet-encrypted at rest) | done |
| **6. Credit / Remittance Master** — credits + remittances in one ledger; grouped Creditor Balance Summary (outstanding, pending first) | done |
| **7. Monthly Expenses** — payroll + operational ledger; extensible categories; date-range/category filtered reporting + grouped summary | done |
| **8. Employee Master + Payroll Run** — HR record with Fernet-encrypted bank fields (masked in lists); bi-weekly payroll run (gross/net); **insurance registers** (accidental + health yearly premiums) + computed Annual Premium Summary | done |
| **9. Payment Receipt** — point-of-sale fuel receipt; rate defaults from Rate Master; Sales may issue, Manager/Owner may delete | done |
| **10. Yearly Sales Report** — FY (Apr–Mar) summary; revenue/salaries/opex computed live; Owner-entered COGS + IOCL commission; CA disclaimer | done |
| **11. Password Reset + email** — single-use emailed link (self-service + admin-initiated); backend-served reset page; SMTP/file/memory backends | done |
| **12. Daily Trial Balance** — **partial.** Sections 1/3/6/7 modelled (SDD §9 formulas; Section 3 pulled read-only from Daily Sales Summary; finalize lock). Sections 2/4/5/8/9/10/11 stored as a `manual_json` blob pending SDD ADR-1. Formula sign of Section 6 litres + density deduction still need a workbook cross-check. | partial |
| CI (`.github/workflows/ci.yml`), Windows installer (`installer/`) | done — PyInstaller-frozen backend + portable Tesseract (ADR-6) bundled into the NSIS installer; services registered/started on install, removed on uninstall. Code-signing path wired (`installer/sign.ps1`, `SVR_SIGN_METHOD`) but **dormant — no cert yet**; clean-VM validation is follow-on |
| External bank-statement reconciliation | not started (needs the client's statement format). OCR pipeline is **built as draft-assist** (module 1) but stock Tesseract can't read the handwritten forms — `OCR-findings-2026-09-09.md`. Excel import/export (module 1), 2FA/TOTP (module 5), Employee Master insurance (module 8) are **done**. |

## Layout

```
backend/    Python — FastAPI loopback API (127.0.0.1), calc engine, RBAC, audit, SQL migrations, scheduler
frontend/   ElectronJS — main + preload bridge, renderer screens, Playwright tests
installer/  electron-builder + first-run.ps1 (service registration, log tree, migrations)
skills/     Agent Skills — daily-sales-entry/
docs/       BRD, SDD, 14 branded mockups, architecture diagrams, sample workbooks
```

## Backend — dev setup

```bash
cd backend
py -m venv .venv
.venv/Scripts/pip install -e ".[dev]"      # add [win] on the deployment target for pywin32

.venv/Scripts/svr-migrate --seed-demo      # fresh SQLite + one user per role (password: demo1234)
.venv/Scripts/svr-backend                   # loopback API on http://127.0.0.1:8756
.venv/Scripts/svr-scheduler                 # 23:59 IST carry-forward + daily backup

.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m pytest -q
```

Config is env-driven (`SVR_` prefix): `SVR_DB_PATH`, `SVR_API_PORT`,
`SVR_DATA_DIR`, `SVR_LOG_DIR`, `SVR_SCHEDULER_TIMEZONE` (default `Asia/Kolkata`).

Demo users: `gsales` / `mmanager` / `oowner`, all password `demo1234`.

## Frontend — dev setup

```bash
cd frontend
npm ci
node node_modules/electron/install.js       # if npm's postinstall was blocked

npm start                                    # Electron app (expects a backend on :8756; override with SVR_API_BASE)
npm run lint
npx playwright install chromium && npm test  # Playwright: boots a seeded backend from ../backend/.venv, runs the suite
```

> If your shell exports `ELECTRON_RUN_AS_NODE=1`, unset it before `npm start` /
> Electron tests — it makes `electron.exe` run as plain Node.

## CI

`.github/workflows/ci.yml` on `windows-latest`: `backend` (ruff + pytest),
`frontend` (eslint + Playwright), `build` (electron-builder `.exe` artifact +
console-script smoke).

## Deployment (target PC)

Build the installer with `installer\build-all.ps1` (PyInstaller freeze →
electron-builder NSIS; needs no Python/Node on the target). Run the resulting
`installer/output/SVR-IOCL-Station-Setup-*.exe` as Administrator: `first-run.ps1`
applies migrations, creates `C:\ProgramData\SVR-IOCL\` (DB + logs + backups),
persists `SVR_*` config machine-wide (generating `SVR_FIELD_KEY` once), registers
+ starts `SVR-IOCL-Backend` and `SVR-IOCL-Scheduler` (`Automatic`), and adds the
frontend as a per-user Startup shortcut. Uninstall removes the services but keeps
the data tree. See [`installer/README.md`](installer/README.md).
