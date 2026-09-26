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
  // The note is gone (client, 2026-09-24: "NO NEED OF THIS ONE"). What has to
  // hold is that the field is LOCKED and looks it - if it must change, that is
  // the Owner reset's job.
  await expect(page.locator("#carried-note")).toBeHidden();
  await expect(page.locator("#hs-last")).toBeDisabled();
  await expect(page.locator("#ms-last")).toBeDisabled();
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
  // Row amounts are truncated to paise, so the figure sits within one paisa
  // below the raw product - never above it (trunc2, 2026-09-11).
  const exact = cons * 105.36;
  expect(amount).toBeLessThanOrEqual(exact + 1e-9);
  expect(amount).toBeGreaterThan(exact - 0.01 - 1e-9);
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
  // Computed figures read to exactly two decimals (2026-09-11).
  await expect(page.locator("#oil1-closing")).toHaveValue("496.00"); // 500 - 4
});

test("computed figures show exactly two decimals and Net Bal subtracts non-cash lines", async ({
  page,
}) => {
  await login(page);
  await page.goto(SCREEN);
  await page.fill("#shift-date", "2026-06-11");
  await page.fill("#hs-current", "900000");
  await page.fill("#pp-settled", "1000");
  await page.fill("#pp-unsettled", "500");
  await page.locator("#pp-unsettled").blur();

  // Every displayed figure carries exactly two decimals (client, 2026-09-11).
  const twoDp = /^-?\d+\.\d{2}$/;
  await expect(page.locator("#hs-amount")).toHaveValue(twoDp);
  await expect(page.locator("#sum-cash")).toHaveValue(twoDp);
  await expect(page.locator("#gas-oil-total")).toHaveValue(twoDp);
  await expect(page.locator("#sum-netbal")).toHaveValue(twoDp);

  // Net Bal takes every non-cash line OFF the cash figure. Derived from what's
  // on screen so the carried Last Shift Reading can't make this brittle.
  const cash = Number(await page.locator("#sum-cash").inputValue());
  const netBal = Number(await page.locator("#sum-netbal").inputValue());
  expect(netBal).toBeCloseTo(cash - (1000 + 500), 2);

  // Section 2's closing row is the same figure as section 7's Cash line.
  expect(Number(await page.locator("#gas-oil-total").inputValue())).toBeCloseTo(cash, 2);
});

test("the revised Oil Sale(s) list, and Night Cash Hand Off gone from the Summary", async ({
  page,
}) => {
  await login(page);
  await page.goto(SCREEN);
  await expect(page.locator("#oil-rows tr")).toHaveCount(7);

  // The client's own row order (2026-09-12). The ids are keys, not positions:
  // oil6/oil4/oil7/oil5 sit in that sequence because a key identifies a product.
  await expect(page.locator("#oil-rows td[data-oil-label]")).toHaveText([
    "2T/1.50 ML Total#",
    "2T/2.40 ML Total#",
    "Acid Water Total 1 Lts",
    "Battery Water Total 1 Lts",
    "Battery Water Total 5 Lts",
    "20/40 Engine Total in 05. Lts",
    "20/40 Engine Total in 1 Lts",
  ]);

  // Rate is editable for oils (unlike the backend-locked gas Sell Rate) - the
  // sheet's rate is authoritative, and two rows have no Rate Master figure yet.
  await expect(page.locator("#oil1-rate")).toBeEnabled();
  await expect(page.locator("#hs-rate")).toBeDisabled();

  await expect(page.locator("#night-cash")).toHaveCount(0);
  await expect(page.locator(".summary-box")).not.toContainText("Night Cash Hand Off");
  await expect(page.locator(".summary-row.net")).toContainText(
    "Net Bal Hand off [Cash - (Expenses + Phone Pay Settled + Phone Pay Not Settled + " +
      "Today New Credits + Card Swiping)]"
  );
});

test("mandatory fields carry a star, and Save acts on them", async ({ page }) => {
  // Client, 2026-09-13: the mandatory columns should be marked with a star. A
  // star that never stops anything is decoration, so Save checks them too.
  await login(page);
  await page.goto(SCREEN);

  // Marked on the form itself - date, pump, and both reading columns.
  await expect(page.locator("#req-legend")).toContainText("Mandatory");
  await expect(page.locator('label[for="shift-date"] .req')).toHaveText("*");
  await expect(page.locator('label[for="pump-serial"] .req')).toHaveText("*");
  await expect(page.locator("th", { hasText: "Current Reading" }).locator(".req")).toHaveText("*");
  await expect(
    page.locator("th", { hasText: "Last Shift Reading" }).locator(".req"),
  ).toHaveText("*");

  // Blocking: no date, no record. Nothing is sent.
  await page.fill("#shift-date", "");
  await page.click("#save-btn");
  await expect(page.locator("#save-status")).toHaveClass(/err/);
  await expect(page.locator("#save-status")).toContainText("Shift Date is required");

  // Warning: a missing reading is NAMED but the save goes through - a shift has
  // to be submittable, and the station's rule for an out-of-service pump is to
  // enter equal readings so the day records a zero.
  // A date no other test touches. 2026-06-30 was in use here and is the date the
  // Export test relies on having NO saved entry - saving to it made that test's
  // form auto-load a record and the "Save the entry first" prompt never appeared.
  await page.fill("#shift-date", "2026-05-17");
  await page.fill("#hs-current", "100");
  await page.click("#save-btn");
  await expect(page.locator("#save-status")).toContainText("Saved (entry #");
  await expect(page.locator("#req-warning")).toBeVisible();
  await expect(page.locator("#req-warning")).toContainText("Petrol (MS) Current Reading");
  await expect(page.locator("#req-warning")).toContainText("out of service");
  await expect(page.locator("#req-legend")).toContainText(
    "type its Last Shift Reading into Current Reading",
  );
});

test("Expenses takes extra rows, and an added row keeps its description", async ({ page }) => {
  // Client, 2026-09-13: "in section three expenses you should be able to add more
  // rows if needed." The three printed rows have fixed labels; an added row types
  // its own, and that text has to be saved with the amount or the figure comes
  // back with no name against it.
  const DATE = "2026-04-19";
  await login(page);
  await page.goto(SCREEN);
  await page.fill("#shift-date", DATE);
  await page.fill("#hs-current", "999999");
  await page.fill("#exp1", "500");

  await page.click('[data-add="exp"]');
  await page.click('[data-add="exp"]');
  const extra = page.locator("#exp-rows tr");
  await expect(extra).toHaveCount(2);
  await extra.nth(0).locator(".exp-desc").fill("Tyre puncture - auto");
  await extra.nth(0).locator(".exp").fill("250");
  await extra.nth(1).locator(".exp-desc").fill("Water cans");
  await extra.nth(1).locator(".exp").fill("120");

  // The added rows count towards the total like any other.
  await expect(page.locator("#exp-total")).toHaveValue("870.00"); // 500 + 250 + 120
  await page.click("#save-btn");
  await expect(page.locator("#save-status")).toContainText("Saved (entry #");

  // Reopen: both the amounts AND their descriptions come back.
  await page.goto(SCREEN);
  await page.fill("#shift-date", DATE);
  await expect(page.locator("#editing-note")).toContainText("Editing saved entry #");
  const back = page.locator("#exp-rows tr");
  await expect(back).toHaveCount(2);
  await expect(back.nth(0).locator(".exp-desc")).toHaveValue("Tyre puncture - auto");
  await expect(back.nth(0).locator(".exp")).toHaveValue("250");
  await expect(back.nth(1).locator(".exp-desc")).toHaveValue("Water cans");
  await expect(page.locator("#exp-total")).toHaveValue("870.00");
});

test("an oil sale keyed with the sheet's own Rate survives Save and reopen", async ({ page }) => {
  const DATE = "2026-06-14";
  await login(page);
  await page.goto(SCREEN);
  await page.fill("#shift-date", DATE);
  await page.fill("#hs-current", "900100");
  // oil7 (20/40 Engine 0.5 Lts) has no Rate Master figure yet - typing the paper
  // sheet's own rate is the only way to record the sale, and it must stick.
  await page.fill("#oil7-qty", "2");
  await page.fill("#oil7-rate", "65");
  await page.locator("#oil7-rate").blur();
  await expect(page.locator("#oil7-amount")).toHaveValue("130.00");

  await page.click("#save-btn");
  await expect(page.locator("#save-status")).toHaveClass(/ok/);

  await page.reload();
  await page.fill("#shift-date", DATE);
  await page.click("#query-btn");
  await expect(page.locator("#save-status")).toHaveClass(/ok/);
  await expect(page.locator("#oil7-rate")).toHaveValue("65");
  await expect(page.locator("#oil7-amount")).toHaveValue("130.00");
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

test("Print Blank DSR draws the station's own form with the carried reading", async ({
  page,
}) => {
  // Client, 2026-09-23: one set of print controls, and both must produce the
  // station's own form - not the data-entry screen, which is what they rejected.
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await page.selectOption("#pump-serial", "12BC4523V-RD");
  await page.fill("#shift-date", "2026-11-28");

  await page.click("#dsr-blank-btn");
  await expect(page.locator("#dsr-preview")).toBeVisible();
  // The preview is the real form: its own A4 page, its own grid.
  await expect(page.locator("#dsr-preview .dsr-page")).toHaveCount(1);
  await expect(page.locator("#dsr-preview")).toContainText(
    "SVR Indian Oil Service Station - Daily Sales Report"
  );
  await expect(page.locator("#dsr-preview")).toContainText("Old/Pending Credit Received");
  // Named the way the station files it.
  await expect(page.locator("#dsr-preview-title")).toContainText(
    "SVR_DSR_12BC4523V-RD_2026-11-28.pdf"
  );

  await page.click("#dsr-close-btn");
  await expect(page.locator("#dsr-preview")).toBeHidden();
});

test("Print Filled DSR says so when the day has not been saved", async ({ page }) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await page.selectOption("#pump-serial", "12BC4523V-RD");
  await page.fill("#shift-date", "2026-11-29");
  await page.click("#dsr-filled-btn");
  // Item 4: it saves first rather than printing a form the database cannot
  // account for - and an empty form has nothing to save, so it refuses.
  await expect(page.locator("#save-status")).toContainText(/Current Reading|save/i);
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

test("a blank form prints on a single A4 portrait page", async ({ page, browserName }) => {
  // The client reported a one-page report spilling across three (2026-09-11).
  // page.pdf() applies the same print CSS the packaged app's preview does, so
  // this measures the real thing rather than trusting the stylesheet by eye.
  test.skip(browserName !== "chromium", "page.pdf() is Chromium-only");
  await login(page);
  await page.goto(SCREEN);
  await page.fill("#shift-date", "2026-06-14");
  const pdf = await page.pdf({ printBackground: true, preferCSSPageSize: true });
  const pages = (pdf.toString("latin1").match(/\/Type\s*\/Page[^s]/g) || []).length;
  expect(pages).toBe(1);
});

test("Scan / Upload (OCR) is gone from the screen", async ({ page }) => {
  // Removed 2026-09-11 at the client's request: stock Tesseract never read the
  // station's handwriting, and for a typed document Import from Excel reads
  // every section while OCR only ever covered gas readings + 3 summary lines.
  await login(page);
  await page.goto(SCREEN);
  await expect(page.locator("#scan-btn")).toHaveCount(0);
  await expect(page.locator('input[type="file"][accept*="pdf"]')).toHaveCount(0);
  await expect(page.locator("#toolbar-hint")).not.toContainText("Scan");
  // The paths that replaced it are still there.
  await expect(page.locator("#import-btn")).toBeVisible();
});

test("Query retrieves a saved day and says so when there is nothing saved", async ({ page }) => {
  await login(page);
  await page.goto(SCREEN);
  await page.fill("#shift-date", "2026-06-12"); // nothing saved on this day
  await page.click("#query-btn");
  await expect(page.locator("#save-status")).toContainText("No saved entry for 2026-06-12");

  // Save a day, then prove Query brings it back rather than leaving a blank form.
  await page.fill("#hs-current", "1600.25");
  await page.click("#save-btn");
  await expect(page.locator("#save-status")).toContainText(/Saved \(entry #\d+\)/);

  await page.reload();
  await page.fill("#shift-date", "2026-06-12");
  await page.click("#query-btn");
  await expect(page.locator("#save-status")).toContainText(/Loaded saved entry #\d+/);
  await expect(page.locator("#hs-current")).toHaveValue("1600.25");
});

test("Browse finds saved entries across a date range", async ({ page }) => {
  await login(page);
  await page.goto(SCREEN);
  await page.fill("#shift-date", "2026-06-13");
  await page.fill("#hs-current", "1700");
  await page.click("#save-btn");
  await expect(page.locator("#save-status")).toContainText(/Saved \(entry #\d+\)/);

  await page.click("#browse-btn");
  await page.fill("#q-from", "2026-06-01");
  await page.fill("#q-to", "2026-06-30");
  await page.click("#q-search-btn");
  await expect(page.locator("#q-status")).toContainText(/saved entr(y|ies) found/);
  await expect(page.locator("#q-rows tr").first()).toBeVisible();
  await expect(page.locator("#q-rows")).toContainText("2026-06-13");
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

test("Import from Excel reads the sheet for whichever pump is selected (multi-pump workbook)", async ({
  page,
}) => {
  // Real client file (2026-09-11): one workbook, a "Road 12BC4523V-RD" sheet
  // and an "Office 11CC2012V-OFF" sheet for the same day.
  const fs = require("fs");
  const path = require("path");
  const sample = path.join(
    __dirname, "..", "..", "docs", "01-BRD-Requirement-Gathering", "ocr-samples",
    "SVR_Daily_Sales_10Sep2026_12BC4523V-RD.xlsx",
  );
  const buffer = fs.readFileSync(sample);

  await login(page);
  await page.goto(SCREEN);
  await page.fill("#shift-date", "2026-09-10");
  await page.selectOption("#pump-serial", "12BC4523V-RD");
  await page.setInputFiles('input[type="file"][accept*="xlsx"]', {
    name: "road-office.xlsx", mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    buffer,
  });
  await expect(page.locator("#save-status")).not.toContainText("could not match");
  await expect(page.locator("#hs-current")).toHaveValue("267859.1");

  await page.selectOption("#pump-serial", "11CC2012V-OFF");
  await page.setInputFiles('input[type="file"][accept*="xlsx"]', {
    name: "road-office.xlsx", mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    buffer,
  });
  await expect(page.locator("#save-status")).not.toContainText("could not match");
  await expect(page.locator("#hs-current")).toHaveValue("1488457.6");
});

test("an import keeps a Last Shift Reading the operator keyed in first", async ({ page }) => {
  // Client, 2026-09-18, describing how they intend to work on the remote PC:
  // "before, what I can do is I can really key in the last shift reading, and
  // then you can take the current reading from the Excel."
  //
  // Order of authority: the sheet's own figure, then what the operator typed
  // before importing, then the carry-forward. Before this, loadPrefill() ran as
  // part of the import and silently discarded a just-keyed reading.
  const fs = require("fs");
  const path = require("path");
  const sheet = path.join(
    __dirname, "..", "..", "docs", "01-BRD-Requirement-Gathering", "ocr-samples",
    "SVR_DSR_Empty_12BC4523V-RD_A4 .xlsx"
  );
  test.skip(!fs.existsSync(sheet), "blank template not present in this checkout");

  await login(page, "mmanager");
  await page.goto(SCREEN);
  await page.selectOption("#pump-serial", "12BC4523V-RD");
  await page.fill("#shift-date", "2026-11-03");   // a day with nothing on file

  // The operator keys the reading in first.
  await page.fill("#hs-last", "1489759.27");
  await page.fill("#ms-last", "663546.17");

  // Then imports a BLANK form - it carries no Last Shift Reading of its own.
  await page.setInputFiles('input[type="file"][accept*="xlsx"]', {
    name: "blank.xlsx",
    mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    buffer: fs.readFileSync(sheet),
  });
  await expect(page.locator("#save-status")).toContainText("Imported");

  // What was typed survives.
  await expect(page.locator("#hs-last")).toHaveValue("1489759.27");
  await expect(page.locator("#ms-last")).toHaveValue("663546.17");
});

test("Print Blank carries yesterday's Current Reading into Last Shift Reading", async ({
  page,
}) => {
  // Client, 2026-09-18: "when they click on print, given pump, it should
  // actually put the yesterday's current reading as the last shift reading, and
  // then print it, so that they simply enter the current reading."
  //
  // The form the client printed showed an empty Last Shift box - but that was a
  // database with nothing on file for the pump, not a missing feature. This
  // pins the behaviour so the next empty-looking blank can be told apart from a
  // broken one.
  const { request } = require("@playwright/test");
  const ctx = await request.newContext();
  const token = (
    await (
      await ctx.post(`${apiBase}/auth/login`, {
        data: { login_name: "mmanager", password: "demo1234" },
      })
    ).json()
  ).token;
  // Yesterday, for a pump/date pair nothing else in the suite touches.
  await ctx.post(`${apiBase}/daily-sales-entry`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      pump_serial: "11CC2012V-OFF",
      shift_date: "2026-12-01",
      hs: { current: "500123.45", last: "500000" },
      ms: { current: "600222.75", last: "600000" },
    },
  });
  await ctx.dispose();

  await login(page, "mmanager");
  await page.goto(SCREEN);
  // Case 2: choosing the pump and the next day prefills Last Shift on its own.
  await page.selectOption("#pump-serial", "11CC2012V-OFF");
  await page.fill("#shift-date", "2026-12-02");
  await expect(page.locator("#hs-last")).toHaveValue("500123.45");
  await expect(page.locator("#ms-last")).toHaveValue("600222.75");
  await expect(page.locator("#hs-last")).toBeDisabled();

  // Case 1: the printed blank carries that reading, and leaves Current Reading
  // empty for the operator's pen. Read off the rendered form, since the DSR
  // print no longer works by blanking the data-entry screen.
  await page.click("#dsr-blank-btn");
  await expect(page.locator("#dsr-preview .dsr-page")).toContainText("500123.45");
  await expect(page.locator("#dsr-preview .dsr-page")).toContainText("600222.75");
});

// Client, 2026-09-25: Card Type, Card Holder Name, Creditor and Customer should
// be dropdowns with a "+ Add", "instead of Manully adding and writing the text".
//
// Typed by hand the same customer arrives as "Airtel Hari", "AirTel hari" and
// "airtel", and the Creditor Balance Summary groups by name - so one customer
// becomes three, each owing a third.
test("card and credit names are picked from a list, not typed", async ({ page }) => {
  await login(page, "gsales");
  await page.goto(SCREEN);
  await expect(page.locator("#cc-rows tr").first()).toBeVisible();

  const holder = page.locator("#cc-rows tr").first().locator("select.cc-holder");
  const cardType = page.locator("#cc-rows tr").first().locator("select.cc-type");
  const creditor = page.locator("#nc-rows tr").first().locator("select.nc-name");
  const customer = page.locator("#oc-rows tr").first().locator("select.oc-customer");

  await expect(holder.locator("option")).toContainText(["AirTel Hari", "I.O.C.L", "B.S.N.L"]);
  await expect(cardType.locator("option")).toContainText(["Xtra Power", "Visa", "Master"]);
  await expect(creditor.locator("option")).toContainText(["Anil/Nani"]);
  await expect(customer.locator("option")).toContainText(["Anil/Nani"]);

  // The header says what the column is now: a name, not a terminal id.
  await expect(page.locator("#cc-rows").locator("xpath=ancestor::table"))
    .toContainText("Card Holder Name");
});

test("a new customer is taken on from the row's own + New button", async ({ page }) => {
  // The "+" beside every dropdown came off on 2026-09-25 ("No more + symbols
  // ... for sure at the end of each row +New"). The job it did has to survive
  // the change: a new customer is still taken on at the pump.
  await login(page, "gsales");
  await page.goto(SCREEN);
  await page.click('[data-add="cc"]');          // a second row, to prove both update
  const rows = page.locator("#cc-rows tr");
  const first = rows.first();

  // Not a single "+" left inside any of the three tables.
  for (const body of ["#cc-rows", "#nc-rows", "#oc-rows"]) {
    await expect(page.locator(`${body} [data-list-add]`)).toHaveCount(0);
  }

  const HOLDER = `Sri Chaithanya ${Date.now()}`;
  const CARD = `RuPay ${Date.now()}`;
  // One button per row, at the end of it - not one under each dropdown.
  await expect(first.locator("td.rownew .row-new")).toHaveCount(1);
  await first.locator(".row-new").click();
  await page.fill(".dse-newbox .nb-a", HOLDER);
  await page.fill(".dse-newbox .nb-b", CARD);
  await page.click(".dse-newbox .nb-ok");

  // Both land, on the row that asked for them...
  await expect(first.locator("select.cc-holder")).toHaveValue(HOLDER);
  await expect(first.locator("select.cc-type")).toHaveValue(CARD);
  // ...and are offered on every other row of the same list, not just that one.
  await expect(rows.last().locator("select.cc-type option")).toContainText([CARD]);
  await expect(rows.last().locator("select.cc-holder option")).toContainText([HOLDER]);
  // The strip closes behind itself.
  await expect(page.locator(".dse-newrow")).toHaveCount(0);

  // And it survives a reload: saved server-side, not just in this page.
  await page.reload();
  await expect(page.locator("#cc-rows tr").first().locator("select.cc-type option"))
    .toContainText([CARD]);
});

test("Signature is off Sections 5 and 6, and the columns are sized to the money", async ({ page }) => {
  await login(page, "gsales");
  await page.goto(SCREEN);
  await expect(page.locator("#nc-rows .nc-sign")).toHaveCount(0);
  await expect(page.locator("#oc-rows .oc-sign")).toHaveCount(0);
  // Amount must hold 999999999.99 without clipping - the reason the column was
  // widened in the first place.
  const amount = page.locator("#oc-rows tr").first().locator(".oc-amount");
  await amount.fill("999999999.99");
  const fits = await amount.evaluate((el) => el.scrollWidth <= el.clientWidth + 1);
  expect(fits).toBe(true);
});

test("Type is HS or MS from a dropdown, and an old 1/2 entry still reads back", async ({ page }) => {
  // Client, 2026-09-26: "Type instead of 1 & 2 replace with HS or MS ... the
  // idea is less keyed-in values whenever and whereever possible".
  await login(page, "gsales");
  await page.goto(SCREEN);
  for (const sel of ["#cc-rows tr >> nth=0 >> select.cc-fuel", "#nc-rows tr >> nth=0 >> select.nc-type"]) {
    await expect(page.locator(sel)).toHaveCount(1);
    await expect(page.locator(sel).locator("option")).toContainText(["HS", "MS"]);
  }
  // Choosing HS still pulls the day's own Diesel rate onto the row. #hs-rate is
  // locked from Rate Master, so read it rather than typing over it.
  const hsRate = await page.locator("#hs-rate").inputValue();
  expect(hsRate).not.toBe("");
  await page.locator("#nc-rows tr").first().locator("select.nc-type").selectOption("HS");
  await expect(page.locator("#nc-rows tr").first().locator(".nc-rate")).toHaveValue(hsRate);
});

test("no format captions are printed under any heading", async ({ page }) => {
  // Client, 2026-09-26: "Remove the sub-headings like format spec across all
  // fields in this form which is not needed and never requested for it".
  await login(page, "gsales");
  await page.goto(SCREEN);
  await expect(page.locator(".maxhint")).toHaveCount(0);
  for (const text of ["999999.99", "999999.999", "999999999.99", "1 / 2"]) {
    await expect(page.locator(".sheet")).not.toContainText(text);
  }
});

test("Section 5 Amount computes itself but can be overridden", async ({ page }) => {
  // Client, 2026-09-26: "Amount col is greyed out Auto Cal is fine also should
  // be editable".
  await login(page, "gsales");
  await page.goto(SCREEN);
  const row = page.locator("#nc-rows tr").first();
  const amount = row.locator(".nc-amount");
  await expect(amount).toBeEnabled();

  await row.locator(".nc-ltrs").fill("10");
  await row.locator(".nc-rate").fill("105.36");
  await expect(amount).toHaveValue("1053.60");

  // A typed figure is not recomputed away on the next keystroke elsewhere.
  await amount.fill("1000");
  await row.locator(".nc-ltrs").fill("11");
  await expect(amount).toHaveValue("1000");
  // Clearing it hands the row back to the calculation.
  await amount.fill("");
  await row.locator(".nc-ltrs").fill("12");
  await expect(amount).toHaveValue("1264.32");
});

test("a value can be removed from a dropdown, and it goes everywhere", async ({ page }) => {
  // Client, 2026-09-26: "In addition to +New also -Delete option is needed".
  await login(page, "gsales");
  await page.goto(SCREEN);
  const first = page.locator("#cc-rows tr").first();

  const CARD = `Scratch ${Date.now()}`;
  await first.locator(".row-new").click();
  await page.fill(".dse-newbox .nb-b", CARD);
  await page.click(".dse-newbox .nb-ok");
  await expect(first.locator("select.cc-type")).toHaveValue(CARD);

  // Delete names what it is about to remove rather than guessing - two presses,
  // which is also the confirmation Electron cannot show as a dialog.
  await first.locator(".row-del").click();
  const strip = page.locator(".dse-delbox");
  await expect(strip).toContainText(CARD);
  await strip.locator(".del-one", { hasText: CARD }).click();

  await expect(page.locator(".dse-delbox")).toHaveCount(0);
  await expect(first.locator("select.cc-type option")).not.toContainText([CARD]);
  // Gone for good, not just in this page.
  await page.reload();
  await expect(page.locator("#cc-rows tr").first().locator("select.cc-type option"))
    .not.toContainText([CARD]);
});

test("Delete works on a row where several dropdowns are selected", async ({ page }) => {
  // Client, 2026-09-26: "Drop down values are not getting deleted when two cols
  // are selected". The strip indexed back into the live row, which had already
  // been re-rendered by the time the button was pressed.
  await login(page, "gsales");
  await page.goto(SCREEN);
  const row = page.locator("#cc-rows tr").first();

  const HOLDER = `Holder ${Date.now()}`;
  const CARD = `Card ${Date.now()}`;
  await row.locator(".row-new").click();
  await page.fill(".dse-newbox .nb-a", HOLDER);
  await page.fill(".dse-newbox .nb-b", CARD);
  await page.click(".dse-newbox .nb-ok");
  // BOTH selected on the row - this is the case that failed.
  await expect(row.locator("select.cc-holder")).toHaveValue(HOLDER);
  await expect(row.locator("select.cc-type")).toHaveValue(CARD);

  await row.locator(".row-del").click();
  await expect(page.locator(".dse-delbox .del-one")).toHaveCount(2);
  await page.locator(".dse-delbox .del-one", { hasText: CARD }).click();
  await expect(page.locator(".dse-delbox")).toHaveCount(0);
  await expect(row.locator("select.cc-type option")).not.toContainText([CARD]);
  // The other one is untouched - only the value that was named goes.
  await expect(row.locator("select.cc-holder option")).toContainText([HOLDER]);
});

test("+ New still adds the new value when the other box is already on the list", async ({
  page,
}) => {
  // Client, 2026-09-26: "Not able to add new Values not working". Typing a known
  // customer beside a brand new card type aborted on the customer's 409 and
  // never reached the card type - which is the commonest case there is.
  await login(page, "gsales");
  await page.goto(SCREEN);
  const row = page.locator("#cc-rows tr").first();
  const EXISTING = await row.locator("select.cc-holder option").nth(1).textContent();
  const CARD = `Fresh ${Date.now()}`;

  await row.locator(".row-new").click();
  await page.fill(".dse-newbox .nb-a", EXISTING.trim());
  await page.fill(".dse-newbox .nb-b", CARD);
  await page.click(".dse-newbox .nb-ok");

  await expect(page.locator(".dse-newbox")).toHaveCount(0);
  await expect(row.locator("select.cc-holder")).toHaveValue(EXISTING.trim());
  await expect(row.locator("select.cc-type")).toHaveValue(CARD);
});

test("+ New and - Delete work in Sections 5 and 6 too", async ({ page }) => {
  // Client, 2026-09-26: "This is happening across all sections 4,5 and 6 cross
  // check it".
  await login(page, "gsales");
  await page.goto(SCREEN);
  for (const [body, select] of [["#nc-rows", "select.nc-name"], ["#oc-rows", "select.oc-customer"]]) {
    const row = page.locator(`${body} tr`).first();
    const NAME = `Person ${body} ${Date.now()}`;
    await row.locator(".row-new").click();
    await page.fill(".dse-newbox .nb-a", NAME);
    await page.click(".dse-newbox .nb-ok");
    await expect(row.locator(select)).toHaveValue(NAME);

    await row.locator(".row-del").click();
    await page.locator(".dse-delbox .del-one", { hasText: NAME }).click();
    await expect(page.locator(".dse-delbox")).toHaveCount(0);
    await expect(row.locator(`${select} option`)).not.toContainText([NAME]);
  }
});

test("Section 4 Amount computes from Ltrs x Rate, and can still be overridden", async ({
  page,
}) => {
  // Client, 2026-09-26: "When entered Type, lts, Amt Auto Calc is not working".
  // Section 4 collected litres and a rate from 2026-09-24 and then never used
  // them - the Amount was only ever whatever was typed into it.
  await login(page, "gsales");
  await page.goto(SCREEN);
  const row = page.locator("#cc-rows tr").first();
  await row.locator("select.cc-fuel").selectOption("HS");
  await row.locator(".cc-ltrs").fill("10");
  // The rate arrives with the prefill, which is a round trip - wait for it
  // rather than reading whatever happens to be there.
  await expect(row.locator(".cc-rate")).not.toHaveValue("");
  const rate = await row.locator(".cc-rate").inputValue();
  await expect(row.locator(".cc-amount")).toHaveValue(
    (10 * Number(rate)).toFixed(2));
  await expect(page.locator("#cc-total")).toHaveValue((10 * Number(rate)).toFixed(2));

  await row.locator(".cc-amount").fill("999");
  await row.locator(".cc-ltrs").fill("11");
  await expect(row.locator(".cc-amount")).toHaveValue("999");
});

test("Amount fills in even while the operator is sitting in the box", async ({ page }) => {
  // From the client's own screenshot, 2026-09-26: Type MS, Ltrs 1, Rate 105.36,
  // Amount empty with the cursor in it. Clicking into Amount to watch for the
  // figure was the very thing stopping it arriving.
  await login(page, "gsales");
  await page.goto(SCREEN);
  const row = page.locator("#cc-rows tr").first();
  await expect(page.locator("#hs-rate")).not.toHaveValue("");

  await row.locator("select.cc-fuel").selectOption("HS");
  await row.locator(".cc-amount").click();          // cursor parked in Amount
  await row.locator(".cc-ltrs").fill("10");
  await row.locator(".cc-amount").click();          // and back into it again
  const hsRate = await page.locator("#hs-rate").inputValue();
  await expect(row.locator(".cc-amount")).toHaveValue((10 * Number(hsRate)).toFixed(2));
});

test("changing Type from HS to MS moves the Rate with it", async ({ page }) => {
  // The screenshot showed Type MS sitting beside 105.36, which is the Diesel
  // rate - so the switch has to carry the rate across, not leave the old one.
  await login(page, "gsales");
  await page.goto(SCREEN);
  await expect(page.locator("#ms-rate")).not.toHaveValue("");
  const hsRate = await page.locator("#hs-rate").inputValue();
  const msRate = await page.locator("#ms-rate").inputValue();
  expect(hsRate).not.toBe(msRate);

  for (const [body, typeSel, rateSel] of [
    ["#cc-rows", "select.cc-fuel", ".cc-rate"],
    ["#nc-rows", "select.nc-type", ".nc-rate"],
  ]) {
    const row = page.locator(`${body} tr`).first();
    await row.locator(typeSel).selectOption("HS");
    await expect(row.locator(rateSel)).toHaveValue(hsRate);
    await row.locator(typeSel).selectOption("MS");
    await expect(row.locator(rateSel)).toHaveValue(msRate);
  }
});

test("- Delete removes a value in Sections 4, 5 and 6 alike", async ({ page }) => {
  // The client asked for this to be confirmed section by section rather than
  // taken on trust, 2026-09-26.
  await login(page, "gsales");
  await page.goto(SCREEN);
  const cases = [
    ["#cc-rows", "select.cc-holder"],
    ["#nc-rows", "select.nc-name"],
    ["#oc-rows", "select.oc-customer"],
  ];
  const used = [];
  for (const [body, select] of cases) {
    const row = page.locator(`${body} tr`).first();
    const NAME = `Del ${body.slice(1, 3)} ${Date.now()}`;
    used.push([select, NAME]);
    await row.locator(".row-new").click();
    await page.fill(".dse-newbox .nb-a", NAME);
    await page.click(".dse-newbox .nb-ok");
    await expect(row.locator(select)).toHaveValue(NAME);

    await row.locator(".row-del").click();
    await page.locator(".dse-delbox .del-one", { hasText: NAME }).click();
    await expect(page.locator(".dse-delbox")).toHaveCount(0);
    await expect(row.locator(`${select} option`)).not.toContainText([NAME]);
  }
  // and it stuck - not just hidden in this page. Checked by exact name: a
  // prefix would also match anything a previously failed run left behind, which
  // is how this assertion goes green or red for the wrong reason.
  await page.reload();
  await expect(page.locator("#cc-rows select.cc-holder option").first()).toBeAttached();
  for (const [select, name] of used) {
    await expect(page.locator(`${select} option`, { hasText: name })).toHaveCount(0);
  }
});

test("Section 4's own instant preview computes Amount, not just the server round trip", async ({
  page,
}) => {
  // The renderer's local mirror never learned Section 4's Amount = Ltrs x
  // Rate, so every keystroke blanked it and only the ~250ms debounced server
  // call ever filled it in - a visible flash that reads as broken even though
  // it settles correctly (client, 2026-09-26).
  await login(page, "gsales");
  await page.goto(SCREEN);
  const row = page.locator("#cc-rows tr").first();
  await row.locator("select.cc-fuel").selectOption("HS");
  // Wait for the auto-filled Rate itself before reading it, so the value this
  // test compares against is the real one, not "" caught mid-fill.
  await expect(row.locator(".cc-rate")).not.toHaveValue("");
  const rate = await row.locator(".cc-rate").inputValue();
  await row.locator(".cc-ltrs").fill("1");
  // No expect()-driven retry here on purpose: read the value on the very next
  // tick, before the debounced server call could possibly have returned.
  await page.waitForTimeout(20);
  await expect(row.locator(".cc-amount")).toHaveValue(Number(rate).toFixed(2));
});

test("removing a value shows its own confirmation right at the row", async ({ page }) => {
  // Client, 2026-09-26: a working delete read as "not working" because the
  // only confirmation was #save-status, far below the section it happened in.
  await login(page, "gsales");
  await page.goto(SCREEN);
  const row = page.locator("#cc-rows tr").first();
  const CARD = `Confirm ${Date.now()}`;
  await row.locator(".row-new").click();
  await page.fill(".dse-newbox .nb-b", CARD);
  await page.click(".dse-newbox .nb-ok");

  await row.locator(".row-del").click();
  await page.locator(".dse-delbox .del-one", { hasText: CARD }).click();
  await expect(page.locator(".dse-newbox")).toContainText(`Removed “${CARD}”`);
});

test("Section 5 and Section 6 have their OWN Payment Mode lists, not one shared list", async ({
  page,
}) => {
  // Client, 2026-09-26, both corrections in one message: Section 5 "it's a
  // credit so I don't need cash in phone pay and credit card ... I don't have
  // to see those three list of values", and Section 6 "you don't have to show
  // the credit CR within the brackets. I don't need that drop down list of
  // value." One shared list put the wrong three options in front of each.
  await login(page, "gsales");
  await page.goto(SCREEN);

  const nc = page.locator("#nc-rows tr").first().locator("select.nc-mode");
  await expect(nc.locator("option")).toContainText(["Credit (CR)"]);
  for (const missing of ["Cash", "Phone Pay", "Credit Card"]) {
    await expect(nc.locator("option")).not.toContainText([missing]);
  }

  const oc = page.locator("#oc-rows tr").first().locator("select.oc-mode");
  await expect(oc.locator("option")).toContainText(["Cash", "Phone Pay", "Credit Card"]);
  await expect(oc.locator("option")).not.toContainText(["Credit (CR)"]);
});

test("Collected by lists people, never the two-name pairings", async ({ page }) => {
  // Client, 2026-09-26: "No Combinations names". The pairings stay in the
  // 'staff' list, which the Trial Balance's 8.16 sign-off still needs.
  await login(page, "gsales");
  await page.goto(SCREEN);
  const collector = page.locator("#oc-rows tr").first().locator("select.oc-collector");
  await expect(collector.locator("option"))
    .toContainText(["Sriharsha", "Girish", "Ravindra", "Ashok", "Vijay"]);
  for (const pair of ["Gopi & Girish", "Girish/Sriharsha"]) {
    await expect(collector.locator("option")).not.toContainText([pair]);
  }
});

test("Old Credit Given Date reads back as 09/MAR/2026, whatever is typed", async ({ page }) => {
  // Client, 2026-09-25. Windows' own date box can only ever print 03/09/2026,
  // which is March or September depending on who reads it.
  await login(page, "gsales");
  await page.goto(SCREEN);
  const given = page.locator("#oc-rows tr").first().locator(".oc-given");

  for (const typed of ["9/3/26", "09-03-2026", "9 mar 26", "09/MAR/2026"]) {
    await given.fill(typed);
    await given.blur();
    await expect(given).toHaveValue("09/MAR/2026");
  }

  // A date nobody can read is flagged, never guessed at.
  await given.fill("31/2/26");
  await given.blur();
  await expect(given).toHaveValue("31/2/26");
  await expect(given).toHaveClass(/bad/);
});
