# Quick shell / logo / icon check — remote PC

**~15–20 minutes.** A visual + click-through smoke of everything that changed
since you last looked at the remote PC. **Not** the full UAT (that's
[`UAT-Test-Cases.md`](UAT-Test-Cases.md), a 2–3 day job).

## What changed (frontend only)

- New **left sidebar** navigation (replaces the plain button list), now shown on
  **every** screen — not just the post-login page.
- The **SVR / IndianOil lockup** on the login screen, the sidebar, and inside
  every form's header. The old duplicate "SVR Indian Oil Service Station" text
  line in form headers is gone.
- Login field relabelled **"Login"** (was "Login name").
- A real **Windows app icon** (the lockup) — taskbar / Start / shortcut / Search,
  instead of the generic Electron icon.

Backend, database, services, and all business logic are **unchanged** this round —
don't re-run the Section A infrastructure checks.

## 1. Get the new build

The remote PC's current install is older than all of the above. Grab the latest:

1. Browser → **https://github.com/Mithendra/SVR/actions/runs/33981401466**
   (latest green `main` build, commit `6166b87`).
2. Scroll to **Artifacts** → download **`svr-iocl-station-installer`** (a ~115 MB zip).
3. Unzip → you get `SVR-IOCL-Station-Setup-0.1.0.exe`.

## 2. Install over the old one

1. Run the `.exe` **as Administrator**.
2. SmartScreen: **More info → Run anyway** (still unsigned — expected).
3. Let it reinstall. Your data in `C:\ProgramData\SVR-IOCL\` (DB, logs) is kept.
4. If it asks to close the running app, allow it.

## 3. Check list

| # | Check | Pass? |
|---|---|---|
| 1 | **Desktop icon** — Start menu → type "SVR". The result shows the **SVR / IndianOil lockup**, not the grey Electron atom. Same on the taskbar once it's running. | |
| 2 | **Login screen** — the lockup sits above the login card; the first field is labelled **"Login"**. | |
| 3 | **After login** — a left **sidebar** with icons; order top-to-bottom: Daily Sales Entry, Daily Sales Summary, Daily Trial Balance, Credit / Remittance Master, Payment Receipt, Inventory Tracking, Rate Master, Monthly Expenses, Employee Master, Yearly Sales Report, then a divider + **"ADMIN"** + Manage Users. | |
| 4 | **Open Daily Sales Entry** — the sidebar is **still there on the left**; the lockup is in the form's blue header; there is **no** separate "SVR Indian Oil Service Station" heading text next to it. | |
| 5 | **Open 3–4 more forms** from the sidebar (Rate Master, Inventory, Monthly Expenses, Daily Trial Balance) — each loads, the sidebar persists, the active item is highlighted. | |
| 6 | **Sign out** — the button at the bottom of the sidebar returns you to the login screen. | |
| 7 | **Role check** — sign in as your **Sales** account: the sidebar shows **only** Daily Sales Entry, Daily Sales Summary, Payment Receipt. Sign in as **Manager** / **Owner**: everything shows. | |
| 8 | **Nothing broken** — enter and **Save** one Daily Sales Entry; confirm it saves and "Last Updated By" shows your account. | |

## 4. Report back

Note any row that fails, and **screenshot** anything that looks wrong (icon, layout
overlap, missing sidebar, a form that won't load). Bring that back here.

If all 8 pass, the shell redesign is good to fold into the production build, and
you can start the full `UAT-Test-Cases.md` run whenever you're ready.
