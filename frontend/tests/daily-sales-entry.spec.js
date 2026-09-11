"use strict";

const { test, expect, request } = require("@playwright/test");
const { apiBase } = require("./_helpers");

const SCREEN = `/screens/daily-sales-entry/index.html?apiBase=${encodeURIComponent(apiBase)}`;

async function login(page, user = "gsales") {
  await page.goto(`/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  await page.fill("#login-name", user);
  await page.fill("#password", "demo1234");
  await page.click("#login-form button[type=submit]");
  await expect(page.locator("#nav-links .nav-item").first()).toBeVisible();
}

test("Sales user reaches Daily Sales Entry from the nav", async ({ page }) => {
  await login(page);
  const link = page.locator('#nav-links a[data-module="daily-sales-entry"]');
  await expect(link).toBeVisible();
  // Sales must not see Manager/Owner modules.
  await expect(page.locator("#nav-links")).not.toContainText("Rate Master");
  await link.click();
  await expect(page.locator(".section-title").first()).toContainText("Gas Sale(s)");
});

test("prefill fills the locked Rate fields; Last Shift Reading is open when there's no carry data", async ({
  page,
}) => {
  // A pump/date with no earlier entry anywhere - nothing to carry (SDD 7.7), so
  // the very first reading has to be enterable by hand. Picked at the seeded
  // Rate Master's own effective_date (2026-08-11, migration 0001) so the Sell
  // Rate is actually in effect, and before every other date this suite uses.
  await login(page);
  await page.goto(SCREEN);
  await page.fill("#shift-date", "2026-08-11");
  await page.locator("#shift-date").dispatchEvent("change");

  await expect(page.locator("#hs-rate")).toHaveValue("105.36");
  await expect(page.locator("#ms-rate")).toHaveValue("117.7");
  await expect(page.locator("#hs-rate")).toBeDisabled();
  await expect(page.locator("#hs-last")).toBeEnabled();
  await expect(page.locator("#ms-last")).toBeEnabled();
});

test("Last Shift Reading locks once a prior day's reading exists (carry-forward)", async ({ page }) => {
  const PRIOR = "1999-06-01";
  const NEXT = "1999-06-02";
  const ctx = await request.newContext();
  const token = (
    await (
      await ctx.post(`${apiBase}/auth/login`, { data: { login_name: "gsales", password: "demo1234" } })
    ).json()
  ).token;
  await ctx.post(`${apiBase}/daily-sales-entry`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      pump_serial: "12BC4523V-RD", shift_date: PRIOR,
      hs: { current: "500" }, ms: { current: "300" },
    },
  });
  await ctx.dispose();

  await login(page);
  await page.goto(SCREEN);
  await page.fill("#shift-date", NEXT);
  await page.locator("#shift-date").dispatchEvent("change");

  await expect(page.locator("#hs-last")).toBeDisabled();
  await expect(page.locator("#hs-last")).toHaveValue("500");
  await expect(page.locator("#ms-last")).toHaveValue("300");
  await expect(page.locator("#carried-note")).toContainText(PRIOR);
});

test("typing Current Reading updates Amount via the backend /calc", async ({ page }) => {
  await login(page);
  await page.goto(SCREEN);
  await page.fill("#hs-current", "1317.52");
  // 1317.52 x 105.36, minus whatever Last Shift Reading prefill supplied.
  await expect(page.locator("#hs-cons")).not.toHaveValue("");
  await expect(page.locator("#hs-amount")).not.toHaveValue("");
  const amount = Number(await page.locator("#hs-amount").inputValue());
  const cons = Number(await page.locator("#hs-cons").inputValue());
  expect(amount).toBeCloseTo(cons * 105.36, 2);
});

test("Save persists the entry and stamps last-updated-by", async ({ page }) => {
  await login(page);
  await page.goto(SCREEN);
  await page.fill("#shift-date", "2026-08-20"); // isolated so no other test's row loads in
  await page.fill("#hs-current", "1317.52");
  await page.fill("#exp1", "500+100=600");
  await page.click("#save-btn");

  await expect(page.locator("#save-status")).toContainText(/(Saved|Updated) \(entry #/);
  await expect(page.locator("#last-updated-by")).toHaveText("gsales");
  // Save is for a new day only - once bound to a saved row, Update takes over.
  await expect(page.locator("#save-btn")).toBeDisabled();
  await expect(page.locator("#update-btn")).toBeEnabled();

  // Confirm the row is really in the backend.
  const ctx = await request.newContext();
  const loginRes = await ctx.post(`${apiBase}/auth/login`, {
    data: { login_name: "gsales", password: "demo1234" },
  });
  const token = (await loginRes.json()).token;
  const list = await ctx.get(
    `${apiBase}/daily-sales-entry?pump_serial=12BC4523V-RD&shift_date=2026-08-20`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  const rows = await list.json();
  expect(rows.length).toBe(1);
  expect(rows[0].sell_rate_hs).toBe(105.36);
  await ctx.dispose();
});

test("re-opening a saved day loads it for edit; Save updates the same row", async ({ page }) => {
  const DATE = "2026-07-15";
  await login(page);
  await page.goto(SCREEN);
  await page.fill("#shift-date", DATE);
  await page.fill("#hs-current", "2000.5");
  await page.click("#save-btn");
  await expect(page.locator("#save-status")).toContainText("Saved (entry #");

  // fresh screen, same pump + date -> it should load the saved entry
  await page.goto(SCREEN);
  await page.fill("#shift-date", DATE);
  await expect(page.locator("#editing-note")).toContainText("Editing saved entry #");
  await expect(page.locator("#hs-current")).toHaveValue("2000.5");
  // Save is disabled once bound to an existing row - Update is the only path in.
  await expect(page.locator("#save-btn")).toBeDisabled();
  await expect(page.locator("#update-btn")).toBeEnabled();

  await page.fill("#hs-current", "2100");
  await page.click("#update-btn");
  await expect(page.locator("#save-status")).toContainText("Updated (entry #");

  const ctx = await request.newContext();
  const token = (
    await (
      await ctx.post(`${apiBase}/auth/login`, {
        data: { login_name: "gsales", password: "demo1234" },
      })
    ).json()
  ).token;
  const rows = await (
    await ctx.get(
      `${apiBase}/daily-sales-entry?shift_date=${DATE}&pump_serial=12BC4523V-RD`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
  ).json();
  expect(rows.length).toBe(1); // updated in place, no duplicate
  expect(String(rows[0].payload.hs.current)).toBe("2100");
  await ctx.dispose();
});

async function seedEntry(shiftDate, pump = "12BC4523V-RD") {
  const ctx = await request.newContext();
  const token = (
    await (
      await ctx.post(`${apiBase}/auth/login`, { data: { login_name: "gsales", password: "demo1234" } })
    ).json()
  ).token;
  await ctx.post(`${apiBase}/daily-sales-entry`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { pump_serial: pump, shift_date: shiftDate, hs: { current: "1500" }, ms: { current: "0" } },
  });
  await ctx.dispose();
}

test("Oil Sale(s) Opening Stock is editable and a manual override survives Save + reopen", async ({
  page,
}) => {
  // Oil sales are handled by only one person on a given day (2026-09-11
  // short-term fix) - Opening Stock is prefilled from Inventory but the
  // submitter can correct it by hand.
  const DATE = "2026-07-19";
  await login(page);
  await page.goto(SCREEN);
  await page.fill("#shift-date", DATE);
  await expect(page.locator("#oil1-opening")).toBeEnabled();

  await page.fill("#oil1-qty", "4");
  await page.fill("#oil1-opening", "500");
  await page.click("#save-btn");
  await expect(page.locator("#save-status")).toContainText("Saved (entry #");

  await page.goto(SCREEN);
  await page.fill("#shift-date", DATE);
  await expect(page.locator("#editing-note")).toContainText("Editing saved entry #");
  await expect(page.locator("#oil1-opening")).toHaveValue("500");
  await expect(page.locator("#oil1-closing")).toHaveValue("496"); // 500 - 4
});

test("Delete button is hidden for Sales, even on their own saved entry", async ({ page }) => {
  const DATE = "2026-07-17";
  await seedEntry(DATE);
  await login(page, "gsales");
  await page.goto(SCREEN);
  await page.fill("#shift-date", DATE);
  await expect(page.locator("#editing-note")).toContainText("Editing saved entry #");
  await expect(page.locator("#delete-btn")).toBeHidden();
});

test("Manager can Delete a saved entry; the form clears and the row is gone", async ({ page }) => {
  const DATE = "2026-07-18";
  await seedEntry(DATE);
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await page.fill("#shift-date", DATE);
  await expect(page.locator("#editing-note")).toContainText("Editing saved entry #");
  await expect(page.locator("#delete-btn")).toBeVisible();

  page.once("dialog", (d) => d.accept());
  await page.click("#delete-btn");
  await expect(page.locator("#save-status")).toContainText(/Deleted \(entry #/);
  await expect(page.locator("#editing-note")).toBeHidden();
  await expect(page.locator("#hs-current")).toHaveValue(""); // form cleared
  await expect(page.locator("#save-btn")).toBeEnabled();
  await expect(page.locator("#update-btn")).toBeDisabled();

  const ctx = await request.newContext();
  const token = (
    await (
      await ctx.post(`${apiBase}/auth/login`, { data: { login_name: "mmanager", password: "demo1234" } })
    ).json()
  ).token;
  const rows = await (
    await ctx.get(`${apiBase}/daily-sales-entry?shift_date=${DATE}&pump_serial=12BC4523V-RD`, {
      headers: { Authorization: `Bearer ${token}` },
    })
  ).json();
  expect(rows.length).toBe(0); // gone
  await ctx.dispose();
});

test("Print Blank Form fills the right pump serial, blanks readings, and hides Section 8 for print", async ({
  page,
}) => {
  await login(page);
  await page.goto(SCREEN);
  // Stub window.print so the native OS dialog never blocks the test.
  await page.evaluate(() => {
    window.__printCalls = 0;
    window.print = () => {
      window.__printCalls += 1;
    };
  });

  await page.click('[data-blank="11CC2012V-OFF"]');
  await expect(page.locator("#pump-serial")).toHaveValue("11CC2012V-OFF");
  await expect(page.locator("#hs-current")).toHaveValue("");
  await expect(page.locator("#ms-current")).toHaveValue("");
  expect(await page.evaluate(() => window.__printCalls)).toBe(1);

  // Section 8 / operational banners aren't on the physical paper form - hidden
  // from the printed output (visible on-screen, hidden under print media).
  await expect(page.locator("#daily-summary-block")).toBeVisible();
  await page.emulateMedia({ media: "print" });
  await expect(page.locator("#daily-summary-block")).toBeHidden();
  await expect(page.locator("#toolbar-hint")).toBeHidden();
  await page.emulateMedia({ media: "screen" });
});

test("theme swatch changes --io-accent; language toggle switches headings", async ({ page }) => {
  await login(page);
  await page.goto(SCREEN);

  await page.click('.theme-toggle button[data-accent="blue"]');
  const accent = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue("--io-accent").trim()
  );
  expect(accent.toLowerCase()).toBe("#0033a0");

  await page.click('.lang-toggle button[data-lang="te"]');
  await expect(page.locator(".section-title").first()).toContainText("గ్యాస్ అమ్మకాలు");
});

test("Scan / Upload (OCR) returns a flagged draft (or reports the engine is absent)", async ({
  page,
}) => {
  const fs = require("fs");
  const path = require("path");
  const sample = path.join(
    __dirname,
    "..",
    "..",
    "docs",
    "01-BRD-Requirement-Gathering",
    "ocr-samples",
    "SVR-daily-sales-2026-09-08-road-scan.pdf",
  );
  await login(page);
  await page.goto(SCREEN);
  await page.fill("#shift-date", "2026-08-25"); // isolated - no existing row to bind to
  await page.setInputFiles('input[type="file"][accept*="pdf"]', {
    name: "scan.pdf",
    mimeType: "application/pdf",
    buffer: fs.readFileSync(sample),
  });
  // With the bundled Tesseract staged -> "OCR DRAFT ... Check EVERY value".
  // Without it (e.g. CI) -> "OCR engine not available". Either is a pass.
  // OCR of a full-page scan takes a few seconds, so allow generous time.
  await expect(page.locator("#save-status")).toContainText(
    /OCR DRAFT|Read \d+ field|OCR engine not available/,
    { timeout: 45000 },
  );
});

test("Export to Excel downloads an .xlsx for a saved entry", async ({ page }) => {
  await login(page);
  await page.goto(SCREEN);
  await page.fill("#shift-date", "2026-08-23");
  await page.fill("#hs-current", "1450.5");
  await page.click("#save-btn");
  await expect(page.locator("#save-status")).toContainText(/(Saved|Updated) \(entry #/);

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.click("#export-btn"),
  ]);
  expect(download.suggestedFilename()).toMatch(/^SVR-DSE-.*\.xlsx$/);
  await expect(page.locator("#save-status")).toContainText("Exported");
});

test("Export to Excel asks you to Save first on an unsaved form", async ({ page }) => {
  await login(page);
  await page.goto(SCREEN);
  await page.fill("#shift-date", "2026-06-30"); // a date with no saved entry
  await page.click("#export-btn");
  await expect(page.locator("#save-status")).toContainText("Save the entry first");
});

test("Import from Excel parses a workbook and populates the form", async ({ page }) => {
  await login(page);
  await page.goto(SCREEN);
  // Make an entry, export it via the API to get a real workbook, then import it.
  await page.fill("#shift-date", "2026-08-24");
  await page.fill("#hs-current", "1600.25");
  await page.fill("#exp1", "200+50=250");
  await page.click("#save-btn");
  await expect(page.locator("#save-status")).toContainText(/(Saved|Updated) \(entry #/);

  const ctx = await request.newContext();
  const token = (
    await (
      await ctx.post(`${apiBase}/auth/login`, {
        data: { login_name: "gsales", password: "demo1234" },
      })
    ).json()
  ).token;
  const list = await (
    await ctx.get(
      `${apiBase}/daily-sales-entry?pump_serial=12BC4523V-RD&shift_date=2026-08-24`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
  ).json();
  const id = list[0].id;
  const xlsx = await (
    await ctx.get(`${apiBase}/daily-sales-entry/${id}/export-excel`, {
      headers: { Authorization: `Bearer ${token}` },
    })
  ).body();
  await ctx.dispose();

  // Fresh screen, then import the workbook through the hidden Excel file input.
  await page.goto(SCREEN);
  await page.setInputFiles('input[type="file"][accept*="xlsx"]', {
    name: "day.xlsx",
    mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    buffer: xlsx,
  });
  await expect(page.locator("#save-status")).toContainText("Imported");
  await expect(page.locator("#hs-current")).toHaveValue("1600.25");
  await expect(page.locator("#exp1")).toHaveValue("200+50=250");
  // recompute ran: amount is populated
  await expect(page.locator("#hs-amount")).not.toHaveValue("");
});

test("Import from Excel never switches the pump/date - it flags a mismatch instead", async ({
  page,
}) => {
  // Identity (Pump Serial + Shift Date) always comes from what's selected on the
  // form, never from the imported file's own metadata (2026-09-11).
  await login(page);
  await page.goto(SCREEN);
  await page.fill("#shift-date", "2026-08-26");
  await page.selectOption("#pump-serial", "11CC2012V-OFF");
  await page.fill("#hs-current", "1700.5");
  await page.click("#save-btn");
  await expect(page.locator("#save-status")).toContainText(/(Saved|Updated) \(entry #/);

  const ctx = await request.newContext();
  const token = (
    await (
      await ctx.post(`${apiBase}/auth/login`, {
        data: { login_name: "gsales", password: "demo1234" },
      })
    ).json()
  ).token;
  const list = await (
    await ctx.get(
      `${apiBase}/daily-sales-entry?pump_serial=11CC2012V-OFF&shift_date=2026-08-26`,
      { headers: { Authorization: `Bearer ${token}` } }
    )
  ).json();
  const xlsx = await (
    await ctx.get(`${apiBase}/daily-sales-entry/${list[0].id}/export-excel`, {
      headers: { Authorization: `Bearer ${token}` },
    })
  ).body();
  await ctx.dispose();

  // Fresh screen, explicitly on a DIFFERENT pump + date than the exported file.
  await page.goto(SCREEN);
  await page.fill("#shift-date", "2026-08-27");
  await page.selectOption("#pump-serial", "12BC4523V-RD");
  await page.setInputFiles('input[type="file"][accept*="xlsx"]', {
    name: "other-day.xlsx",
    mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    buffer: xlsx,
  });

  // The selection on screen wins - not overridden by the file's own metadata.
  await expect(page.locator("#pump-serial")).toHaveValue("12BC4523V-RD");
  await expect(page.locator("#shift-date")).toHaveValue("2026-08-27");
  // ...but the operator is told about the mismatch, by name, on both counts.
  await expect(page.locator("#save-status")).toContainText("11CC2012V-OFF");
  await expect(page.locator("#save-status")).toContainText("2026-08-26");
  // The imported values still apply, to whichever pump/date is now selected.
  await expect(page.locator("#hs-current")).toHaveValue("1700.5");
});
