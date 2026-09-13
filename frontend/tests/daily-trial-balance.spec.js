"use strict";

const { test, expect, request } = require("@playwright/test");
const { apiBase } = require("./_helpers");

const SCREEN = `/screens/daily-trial-balance/index.html?apiBase=${encodeURIComponent(apiBase)}`;
// classify_pump (needed for Section 3's "both submitted" gate) only recognizes
// the station's two real serials (2026-09-11) - unlike a made-up serial, these
// are used by other specs too, so Last Shift Reading can't be assumed blank.
// A known prior day is seeded instead, and today's readings are offset from it
// by a known amount, so combined consumption is deterministic either way.
const PUMP_A = "12BC4523V-RD";
const PUMP_B = "11CC2012V-OFF";
// ADR-2 blocks CREATING a Trial Balance date while any EARLIER one is still
// open, and every test in this file shares one database. So each test that
// creates a new date must use one EARLIER than every test before it - or reuse a
// date already on file, which skips the gate entirely. Three separate failures
// in this file have come from ignoring that; the dates below run downhill on
// purpose. Add a new saving test at a date earlier than 2026-01-05.
const PRIOR_DATE = "2026-10-19";
const DATE = "2026-10-20";

test.beforeAll(async () => {
  const ctx = await request.newContext();
  const token = (
    await (await ctx.post(`${apiBase}/auth/login`, {
      data: { login_name: "gsales", password: "demo1234" },
    })).json()
  ).token;
  const h = { Authorization: `Bearer ${token}` };
  await ctx.post(`${apiBase}/daily-sales-entry`, {
    headers: h,
    data: { pump_serial: PUMP_A, shift_date: PRIOR_DATE, hs: { current: "1000" } },
  });
  await ctx.post(`${apiBase}/daily-sales-entry`, {
    headers: h,
    data: { pump_serial: PUMP_B, shift_date: PRIOR_DATE, hs: { current: "2000" } },
  });
  // +30 / +20 over the known prior day -> combined HS consumption 50 regardless
  // of anything else ever recorded for these pumps before PRIOR_DATE.
  await ctx.post(`${apiBase}/daily-sales-entry`, {
    headers: h,
    data: { pump_serial: PUMP_A, shift_date: DATE, hs: { current: "1030" } },
  });
  await ctx.post(`${apiBase}/daily-sales-entry`, {
    headers: h,
    data: { pump_serial: PUMP_B, shift_date: DATE, hs: { current: "2020" } },
  });
  await ctx.dispose();
});

// Save is live for a new date, Update for one already on file. A retry re-runs
// against a date attempt #1 created, so click whichever applies - the same choice
// the operator faces.
async function saveOrUpdate(page) {
  const save = page.locator("#save-btn");
  await ((await save.isEnabled()) ? save : page.locator("#update-btn")).click();
}

async function login(page, user) {
  await page.goto(`/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  await page.fill("#login-name", user);
  await page.fill("#password", "demo1234");
  await page.click("#login-form button[type=submit]");
  await expect(page.locator("#nav-links .nav-item").first()).toBeVisible();
}

test("Sales sees the Daily Trial Balance nav link (maker) but not the Close & Sign Off controls", async ({
  page,
}) => {
  await login(page, "gsales");
  // ADR-2, confirmed 2026-09-06: Sales is the maker - the module is visible to
  // them now, unlike the pre-ADR-2 design this test used to assert.
  await expect(page.locator('#nav-links a[data-module="daily-trial-balance"]')).toHaveCount(1);

  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();
  await expect(page.locator("#role-tag")).toHaveText("Maker — entry & save only");
  await expect(page.locator("#finalize-block")).toBeHidden();
  await expect(page.locator("#finalize-fields")).toBeHidden();
  await expect(page.locator("#finalize-btn")).toBeHidden();
  // Save (the maker's own action) stays available.
  await expect(page.locator("#save-btn")).toBeVisible();
});

test("all eleven workbook sections are on the form, not just the computed ones", async ({
  page,
}) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();

  // Until 2026-09-12 only 1/5/6 were rendered and the other seven sections were a
  // single raw JSON textarea - which is why the form looked like it had three
  // sections. Numbering here is the station's own workbook numbering.
  for (const title of [
    "1. IOCL Stock Readings",
    "2. Day Sales Report",
    "3. Daily Cash & Bank Balances",
    "4. Cash/Book Value Reconciliation",
    "5. Stock Value",
    "6. Trial Balance — Actual Reported — Today",
    "7. Trial Balance — Projected — Today",
    "8. Daily Management Reporting",
    "9. Daily Mgr Calculation",
    "10. Load/Unload Details",
    "11. Old/New Credit Sales Details",
  ]) {
    await expect(page.locator(".section-title, .summary-box h3").filter({ hasText: title }))
      .toHaveCount(1);
  }

  // The raw JSON box is gone.
  await expect(page.locator("#manual-json")).toHaveCount(0);
  // Representative INPUTS from the sections that used to be JSON-only.
  await expect(page.locator('[data-manual="section3.onhand"]')).toBeVisible();
  await expect(page.locator('[data-manual="section4.reported"]')).toBeVisible();
  await expect(page.locator('[data-manual="section7.profit"]')).toBeVisible();
  await expect(page.locator('[data-manual="section8.f4"]')).toBeVisible();
  await expect(page.locator('[data-manual="section10.hs_new"]')).toBeVisible();
  await expect(page.locator('[data-manual="section11.new_airtel"]')).toBeVisible();
  // ...and the totals between them are CALCULATED, not typed - so there is no
  // input for them at all, only a read-only cell. A total you can type over is a
  // total that can silently disagree with its own inputs.
  for (const path of [
    "section3.total6", "section3.total13", "section3.total15",
    "section4.total3", "section4.diff",
    "section7.total3", "section7.diff", "section7.total5",
    "section8.f3", "section8.f5",
    "section10.hs.total", "section10.hs.lost",
    "section1.margin_total", "section1.total_sale_amt", "section1.iocl_profit",
  ]) {
    // Some figures appear more than once - the sheet itself repeats 4.5 as the
    // Difference Amount and again as 8.5 - so assert "present", not "exactly one".
    await expect(page.locator(`[data-derived="${path}"]`).first()).toBeVisible();
    await expect(page.locator(`[data-manual="${path}"]`)).toHaveCount(0);
  }
  // Section 9's running ledger keeps all 26 workbook columns.
  await expect(page.locator('[data-rows="section9.ledger"]')).toHaveCount(1);
  await expect(page.locator('[data-rows="section9.ledger"] tr').first().locator("[data-col]"))
    .toHaveCount(26);
});

test("the SEP12 dropdown lists are on the form, and a new value can be added", async ({
  page,
}) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();

  const creditor = page.locator('[data-rows="section3.new_credits"] tr').first().locator("select");
  await expect(creditor.locator("option")).toContainText([
    "— select —", "Anil/Nani New Credit", "Anil New Credit", "AirTel Hari New Credit",
    "Salary Advance Viaj", "Salary Advance Ashok", "Salary Advance Sriharsha",
    "Salary Advance Ravindra", "Sajja Function Hall - New Credit",
  ]);

  const expense = page.locator('[data-rows="section4.expenses"] tr').first().locator("select");
  await expect(expense.locator("option")).toContainText([
    "— select —", "Salaries Mid/End of Month - Total", "Power Bill", "Unload Beta",
    "Salary Advances Total",
  ]);

  await expect(
    page.locator('[data-rows="section4.remittance"] tr').first().locator("select option")
  ).toContainText(["— select —", "Sajja Old Credit Remitted Amt"]);
  await expect(
    page.locator('[data-rows="section8.regular_expenses"] tr').first().locator("select option")
  ).toContainText(["Power Bill"]);
  await expect(
    page.locator('[data-rows="section8.old_credit_collections"] tr').first().locator("select option")
  ).toContainText(["Anil Old Credit Remitted"]);

  // 8.9 sign-off: Prepared by / Verified by / Sent to, each a staff dropdown.
  for (const key of ["prepared_by", "verified_by", "sent_by"]) {
    await expect(page.locator(`select[data-manual="section8.${key}"]`)).toHaveCount(1);
  }
  await expect(page.locator('select[data-manual="section8.prepared_by"] option'))
    .toContainText(["Gopi", "Girish", "Sriharsha"]);

  // Every list-backed block offers "+ New ..." - a new customer asking for credit
  // has to be enterable the same day (client, 2026-09-12).
  for (const list of ["creditors", "expenses", "remittance", "old_credit", "staff"]) {
    await expect(page.locator(`[data-add-option="${list}"]`).first()).toBeVisible();
  }

  // Adding one is saved server-side, so it survives a reload - not a value that
  // only exists in this browser session.
  const NEW = `Test Creditor ${Date.now()}`;
  await page.locator('[data-add-option="creditors"]').first().click();
  const box = page.locator('[data-newopt="creditors"]').first();
  await expect(box).toBeVisible();
  await box.locator("[data-newopt-input]").fill(NEW);
  await box.locator("[data-newopt-save]").click();
  await expect(page.locator("#save-status")).toContainText("added");
  await expect(box).toBeHidden();
  await expect(
    page.locator('[data-rows="section3.new_credits"] tr').first().locator("select option")
  ).toContainText([NEW]);

  await page.reload();
  await expect(page.locator("#body")).toBeVisible();
  await expect(
    page.locator('[data-rows="section3.new_credits"] tr').first().locator("select option")
  ).toContainText([NEW]);
});

test("a category added in 4.6 Expenses also appears in 8.6 Regular Expenses", async ({
  page,
}) => {
  // The SEP12 sheet points both at the same Excel validation range.
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();

  const NEW = `Test Category ${Date.now()}`;
  const bar = page.locator('[data-rows="section4.expenses"]')
    .locator("xpath=ancestor::table[1]/following-sibling::div[@class='tb-actions'][1]");
  await bar.locator('[data-add-option="expenses"]').click();
  await bar.locator("[data-newopt-input]").fill(NEW);
  await bar.locator("[data-newopt-save]").click();
  await expect(page.locator("#save-status")).toContainText("added");

  for (const block of ["section4.expenses", "section8.regular_expenses"]) {
    await expect(
      page.locator(`[data-rows="${block}"] tr`).first().locator("select option")
    ).toContainText([NEW]);
  }
});

test("Section 2.1 Oil Sales has no Indent column", async ({ page }) => {
  // Removed on the client's instruction, 2026-09-12 - it was not needed.
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();
  await page.fill("#tb-date", DATE);
  await page.click("#load-btn");
  await expect(page.locator("#s3-src")).toContainText("Daily Sales Summary");

  await expect(page.locator("#s2-oil-rows input")).toHaveCount(0);
  await expect(page.locator('[data-manual^="section2.indent"]')).toHaveCount(0);
  // The column header goes too - it lives in index.html, not the row builder, so
  // removing only the cells left a stray "Indent (oil's)" heading behind.
  const oilTable = page.locator("#s2-oil-rows").locator("xpath=ancestor::table[1]");
  await expect(oilTable).not.toContainText("Indent");
  await expect(oilTable.locator("tr").first().locator("th")).toHaveCount(6);
});

test("calculated cells render as boxed read-only inputs, like every other form", async ({
  page,
}) => {
  // They used to be bare text in a <td>, which read as a hole in the grid.
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();

  const derived = page.locator('[data-derived="section3.total6"]');
  await expect(derived).toHaveJSProperty("tagName", "INPUT");
  await expect(derived).toBeDisabled();
});

test("cross-section totals are calculated from what you type, to the SEP12 formulas", async ({
  page,
}) => {
  const CALC_DATE = "2026-10-26";
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();
  await page.fill("#tb-date", CALC_DATE);
  await page.click("#load-btn");

  // The SEP12 Section 3 chain, with that sheet's own figures.
  await page.fill('[data-manual="section3.onhand"]', "76096.51");
  await page.fill('[data-manual="section3.night"]', "40000");
  await page.fill('[data-manual="section3.morning"]', "15680.5");
  await page.fill('[data-manual="section3.oldcredit"]', "14750.4");
  await page.fill('[data-manual="section3.iocl"]', "499485.08");
  await page.fill('[data-manual="section3.indianbank"]', "1311580.42");
  await page.fill('[data-manual="section3.yesbank"]', "11634.55");
  await page.fill('[data-manual="section3.ppunsettled"]', "3579");
  const credit = page.locator('[data-rows="section3.new_credits"] tr').first();
  await credit.locator("select").selectOption("AirTel Hari New Credit");
  await credit.locator('[data-col="amount"]').fill("11674");

  // Section 10: Total = New - Old, Lost = IOCL Load - Total.
  await page.fill('[data-manual="section10.hs_old"]', "2207");
  await page.fill('[data-manual="section10.hs_new"]', "12079");
  await page.fill('[data-manual="section10.hs_load"]', "10000");

  await saveOrUpdate(page);
  await expect(page.locator("#save-status")).toContainText("recalculated");

  await expect(page.locator('[data-derived="section3.total6"]')).toHaveValue("146527.41");
  await expect(page.locator('[data-derived="section3.total7"]')).toHaveValue("146527.41");
  await expect(page.locator('[data-derived="section3.total13"]')).toHaveValue("1972806.46");
  await expect(page.locator('[data-derived="section3.total15"]')).toHaveValue("1984480.46");
  await expect(page.locator('[data-derived="section10.hs.total"]')).toHaveValue("9872.00");
  await expect(page.locator('[data-derived="section10.hs.lost"]')).toHaveValue("128.00");
});

test("manual sections save into the record's manual block and survive a reload", async ({
  page,
}) => {
  const MANUAL_DATE = "2026-10-25";
  await login(page, "mmanager");
  await page.goto(SCREEN);
  // Wait for init() to finish before touching the date: it sets #tb-date to today
  // itself, so filling too early is silently overwritten and the Save lands on
  // TODAY's Trial Balance - which then blocks every later date via the ADR-2 gate.
  await expect(page.locator("#body")).toBeVisible();
  await page.fill("#tb-date", MANUAL_DATE);
  await page.click("#load-btn");

  await page.fill('[data-manual="section3.onhand"]', "12345.67");
  await page.fill('[data-manual="section4.reported"]', "98765.43");
  await page.fill('[data-manual="section11.new_airtel"]', "500");
  // A repeating row, including its dropdown.
  const creditRows = page.locator('[data-rows="section3.new_credits"] tr');
  await creditRows.first().locator("select").selectOption("AirTel Hari New Credit");
  await creditRows.first().locator('[data-col="amount"]').fill("2500");

  await saveOrUpdate(page);
  await expect(page.locator("#save-status")).toContainText("recalculated");

  await page.reload();
  await expect(page.locator("#body")).toBeVisible();
  await page.fill("#tb-date", MANUAL_DATE);
  await page.click("#load-btn");
  await expect(page.locator('[data-manual="section3.onhand"]')).toHaveValue("12345.67");
  await expect(page.locator('[data-manual="section4.reported"]')).toHaveValue("98765.43");
  await expect(page.locator('[data-manual="section11.new_airtel"]')).toHaveValue("500.00");
  await expect(creditRows.first().locator("select")).toHaveValue("AirTel Hari New Credit");
  await expect(creditRows.first().locator('[data-col="amount"]')).toHaveValue("2500.00");
});

test("Section 2 shows the day's real per-pump figures, pulled not typed", async ({ page }) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible(); // init() owns #tb-date until then
  await page.fill("#tb-date", DATE);
  await page.click("#load-btn");
  await expect(page.locator("#s3-src")).toContainText("Daily Sales Summary");

  // Per-pump blocks in the sheet's own shape: a serial header, its two fuel rows
  // and its subtotal, for each of the two pumps.
  await expect(page.locator("#s2-gas-rows tr")).toHaveCount(8);
  await expect(page.locator("#s2-gas-rows")).toContainText(`${PUMP_B} (Office)`);
  await expect(page.locator("#s2-gas-rows")).toContainText(`${PUMP_A} (Road)`);
  await expect(page.locator("#s2-gas-rows")).toContainText(`${PUMP_A} Total`);
  // The combined block below it carries both fuels, side by side.
  await expect(page.locator("#s2-combined-rows tr")).toHaveCount(2);
  await expect(page.locator("#s2-total-ltrs")).toHaveValue(/^\d+\.\d{2}$/);
  // Nothing in the pulled rows is typeable.
  await expect(page.locator("#s2-gas-rows input")).toHaveCount(0);
  await expect(page.locator("#s2-combined-rows input")).toHaveCount(0);
});

test("Manager enters Section 1, sees computed columns + pulled Section 3, then finalizes", async ({
  page,
}) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();
  await expect(page.locator("#role-tag")).toHaveText("Checker — can Close & Sign Off");
  await expect(page.locator("#finalize-block")).toBeVisible();

  await page.fill("#tb-date", DATE);
  await page.click("#load-btn");
  // Wait until the DATE load has actually rendered (its own Section 3 message).
  await expect(page.locator("#s3-src")).toContainText("Daily Sales Summary");

  await page.fill("#hs-y", "100");
  await page.fill("#hs-c", "60");
  await page.fill("#cash-bv", "500000");
  await saveOrUpdate(page);
  await expect(page.locator("#save-status")).toContainText("recalculated");

  await expect(page.locator("#hs-diff")).toHaveValue("40.00"); // 100 - 60
  await expect(page.locator("#hs-cons")).toHaveValue("50.00"); // pulled from Section 3
  // 50 - 5.5: the testing/density deduction is 5.5 from 2026-09-12 (SEP12 tab),
  // effective-dated, so earlier Trial Balances still compute with the old 10.0.
  await expect(page.locator("#hs-dt")).toHaveValue("44.50");
  // 6.3 = 6.1 + 6.2. Compared numerically: both cells are formatted to two
  // decimals for display, so a string comparison would be comparing rounding.
  const s72 = Number(await page.locator("#s7-2").inputValue());
  const s73 = Number(await page.locator("#s7-3").inputValue());
  expect(s73).toBeCloseTo(500000 + s72, 2);

  page.once("dialog", (d) => d.accept());
  await page.click("#finalize-btn");
  await expect(page.locator("#status-tag")).toHaveText("finalized");
  await expect(page.locator("#hs-c")).toBeDisabled();
  await expect(page.locator("#save-btn")).toBeDisabled();

  // ADR-2: finalizing auto-creates and seeds tomorrow's draft from today's
  // Reported (not Projected) values, with the carry-forward link shown.
  const tomorrow = new Date(DATE + "T00:00:00Z");
  tomorrow.setUTCDate(tomorrow.getUTCDate() + 1);
  await page.fill("#tb-date", tomorrow.toISOString().slice(0, 10));
  await page.click("#load-btn");
  await expect(page.locator("#carry-info")).toContainText(`Carried forward from ${DATE}`);
});

test("Section 8 can be exported on its own and sent to management", async ({ page }) => {
  // It is the part that leaves the station daily (BRD; client 2026-09-12).
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();

  const download = page.waitForEvent("download");
  await page.click("#s8-export-btn");
  expect((await download).suggestedFilename()).toMatch(/^SVR-Section8-\d{4}-\d{2}-\d{2}\.xlsx$/);
  await expect(page.locator("#s8-send-status")).toContainText("Exported");

  // The WhatsApp number field and Send button were removed (client, 2026-09-12):
  // the snapshot is the thing that goes out, pasted into the chat by hand.
  await expect(page.locator("#s8-whatsapp")).toHaveCount(0);
  await expect(page.locator("#s8-whatsapp-btn")).toHaveCount(0);
});

test("every figure on the form reads to two decimals, never more", async ({ page }) => {
  // 1530.425699999684 was reaching the screen raw (client, 2026-09-12).
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();
  await page.fill("#tb-date", DATE);
  await page.click("#load-btn");
  await expect(page.locator("#s3-src")).toContainText("Daily Sales Summary");

  // Section 1's computed columns are boxed inputs like everything else, not bare
  // text - that inconsistency is what made them look like a different kind of cell.
  for (const id of ["hs-diff", "hs-cons", "hs-cpd", "hs-dt", "hs-sl2", "hs-br", "hs-sa"]) {
    const el = page.locator(`#${id}`);
    await expect(el).toHaveJSProperty("tagName", "INPUT");
    await expect(el).toBeDisabled();
  }

  const twoDp = /^-?[\d,]*\.\d{2}$/;
  for (const id of ["hs-diff", "hs-cons", "hs-dt", "hs-sl2", "s6-total", "s7-3"]) {
    await expect(page.locator(`#${id}`)).toHaveValue(twoDp);
  }
});

test("Section 8 snapshot says plainly it needs the installed app", async ({ page }) => {
  // The capture uses Electron's own capturePage through the preload bridge, so in
  // a browser tab there is nothing to call. It must say so rather than appear to
  // work - page-mode has no window.svr.
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();

  await page.fill("#tb-date", DATE);
  await page.click("#load-btn");
  await expect(page.locator("#s3-src")).toContainText("Daily Sales Summary");

  await page.click("#s8-snapshot-btn");
  // The snapshot itself renders either way - what needs the app is copying it to
  // the clipboard, and it says so rather than appearing to have worked.
  await expect(page.locator("#s8-snapshot-view")).toBeVisible();
  await expect(page.locator("#s8-send-status")).toHaveClass(/err/);
  await expect(page.locator("#s8-send-status")).toContainText("installed SVR app");

  // It is management's layout, not the app's: green bands, red figures, their
  // own wording, and the Difference / Yes Bank / Total panel printed twice.
  const snap = page.locator("#s8-snapshot-view");
  await expect(snap).toContainText("8. Daily Management Reporting");
  await expect(snap).toContainText("8.5 Difference — Actual Reported Minus Projected");
  await expect(snap).toContainText("#OK Anything Above Rs 100 Call/inform mgmt immediately");
  await expect(snap).toContainText("Cash Value Difference");
  await expect(snap).toContainText("Sent to SVR and Bank Statement to Group Email BY");
  await expect(snap.locator("table.snap-panel")).toHaveCount(2);
  await expect(snap.locator("table.snap-panel").first()).toContainText("Yes Bank Return Amount");
  // Figures carry Indian digit grouping, as on the sheet management receives.
  await expect(snap.locator(".snap-val").first()).toHaveText(/^[\d,]*\.\d{2}$|^$/);
});

test("Special Note is available where the sheet has commentary", async ({ page }) => {
  // The sheet has no field for it, so operators type commentary into the labels
  // (SEP10 A36: "Indian bank Statement Ending Balance @Fraud Pending -Rs 13367").
  const NOTE_DATE = "2026-02-10"; // see the ADR-2 note at the top of this file
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();
  await page.fill("#tb-date", NOTE_DATE);
  await page.click("#load-btn");

  // 3, 4, 7 get one each; 8 gets two (8.5's and the management summary's), as the
  // sheet has them - and they sit in a right-hand column, not stranded underneath.
  for (const sec of ["section3", "section4", "section7", "section8"]) {
    await expect(page.locator(`textarea[data-manual="${sec}.special_note"]`)).toBeVisible();
  }
  await expect(page.locator('textarea[data-manual="section8.mgmt_note"]')).toBeVisible();
  await expect(page.locator("#sec-8 textarea.tb-note")).toHaveCount(2);
  // Geometry is asserted by "Special Note runs left to right..." below.

  await page.fill('textarea[data-manual="section3.special_note"]', "Yes Bank returned 8,525.95");
  await saveOrUpdate(page);
  await expect(page.locator("#save-status")).toContainText("recalculated");

  await page.reload();
  await expect(page.locator("#body")).toBeVisible();
  await page.fill("#tb-date", NOTE_DATE);
  await page.click("#load-btn");
  await expect(page.locator('textarea[data-manual="section3.special_note"]')).toHaveValue(
    "Yes Bank returned 8,525.95"
  );
});

test("buttons sit under their own block, not floated to the far right", async ({ page }) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();

  for (const id of ["sec-3", "sec-4", "sec-7", "sec-8", "sec-10", "sec-11"]) {
    await expect(page.locator(`#${id}`)).toHaveAttribute("data-w", /std|half|wide|full/);
  }

  const actions = page.locator('[data-rows="section3.new_credits"]')
    .locator("xpath=ancestor::table[1]/following-sibling::div[@class='tb-actions'][1]");
  const bar = await actions.boundingBox();
  const table = await page.locator('[data-rows="section3.new_credits"]')
    .locator("xpath=ancestor::table[1]").boundingBox();
  expect(bar.x).toBeLessThanOrEqual(table.x + 4);
});

test("Section 1's cross-fuel columns are marked n/a on the Diesel row", async ({ page }) => {
  // They are blank there because the sheet prints them once, on the Petrol row.
  // Empty cells with no control just looked broken (client, 2026-09-12).
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();
  const diesel = page.locator("#hs-y").locator("xpath=ancestor::tr[1]");
  await expect(diesel.locator('input[placeholder="n/a"]')).toHaveCount(4);
  await expect(diesel.locator("td")).toHaveCount(13); // Fuel + 12 columns
});

test("Section 8 is stamped with the system date and time in IST, uneditable", async ({ page }) => {
  // A report that says when it was produced is only useful if nobody can edit it,
  // so it is generated into the heading - there is no field for it at all.
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();

  const stamp = page.locator("#s8-stamp");
  await expect(stamp).toHaveText(/^— \d{1,2} [A-Z]{3,4}, \d{1,2}:\d{2} (AM|PM) IST$/);
  await expect(stamp.locator("input, textarea, select")).toHaveCount(0);
  await expect(page.locator("#sec-8 .section-title")).toContainText("IST");
});

test("Section 1 shows all thirteen columns without scrolling", async ({ page }) => {
  // Total Sale Amt, IOCL Adv and IOCL Profit were being clipped off the right.
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();

  const table = page.locator("table.tb-s1");
  await expect(table.locator("tr").first().locator("th")).toHaveCount(13);
  for (const heading of ["Margin Total", "2T Sales", "Total Sale Amt", "IOCL Adv", "IOCL Profit"]) {
    await expect(table.locator("th").filter({ hasText: heading }).first()).toBeVisible();
  }
  // Fits its section rather than overflowing it.
  const t = await table.boundingBox();
  const sec = await page.locator("#body .tb-sec").first().boundingBox();
  expect(t.width).toBeLessThanOrEqual(sec.width + 2);

  // Margin and IOCL Adv are formulas now (SEP12 H3=G3*2.61, L3=F3*C67), so they
  // are calculated cells - not something anyone types over.
  for (const p of ["section1.hs_margin", "section1.ms_margin",
                   "section1.hs_iocl_adv", "section1.ms_iocl_adv"]) {
    await expect(page.locator(`[data-derived="${p}"]`)).toBeDisabled();
    await expect(page.locator(`[data-manual="${p}"]`)).toHaveCount(0);
  }
});

test("Save and Update are distinct, and a saved date can be found by browsing", async ({
  page,
}) => {
  const D = "2026-01-05"; // earlier than every other saving test - see the note at the top
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();
  await page.fill("#tb-date", D);
  await page.click("#load-btn");

  // Nothing on file for this date yet: Save is the action, Update is not.
  await expect(page.locator("#save-btn")).toBeEnabled();
  await expect(page.locator("#update-btn")).toBeDisabled();

  await page.fill("#hs-c", "60");
  await page.click("#save-btn");
  await expect(page.locator("#save-status")).toContainText("Saved");

  // Now it is on file, so it is an Update from here.
  await expect(page.locator("#update-btn")).toBeEnabled();
  await expect(page.locator("#save-btn")).toBeDisabled();
  await page.fill("#hs-c", "61");
  await page.click("#update-btn");
  await expect(page.locator("#save-status")).toContainText("Updated");

  // And it can be found without knowing the date.
  await page.click("#browse-btn");
  await page.fill("#q-from", "2026-01-01");
  await page.fill("#q-to", "2026-01-31");
  await page.click("#q-search-btn");
  await expect(page.locator("#q-status")).toContainText("found");
  const row = page.locator("#q-rows tr").filter({ hasText: D });
  await expect(row).toHaveCount(1);
  await row.locator(".q-open").click();
  await expect(page.locator("#tb-date")).toHaveValue(D);
  await expect(page.locator("#hs-c")).toHaveValue("61");
});

test("the whole Trial Balance exports to Excel", async ({ page }) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();
  const download = page.waitForEvent("download");
  await page.click("#export-btn");
  expect((await download).suggestedFilename()).toMatch(
    /^SVR-TrialBalance-\d{4}-\d{2}-\d{2}\.xlsx$/
  );
  await expect(page.locator("#save-status")).toContainText("Exported");
});

test("Special Note runs left to right, and Section 3's sits mid-section", async ({ page }) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();

  // A wide row, not a tall narrow column: wider than it is tall, and starting at
  // the left edge of its own table (client, 2026-09-12).
  const note = page.locator('textarea[data-manual="section3.special_note"]');
  const box = await note.boundingBox();
  expect(box.width).toBeGreaterThan(box.height * 3);

  // Mid-section: after 3.13, before the 3.14 New Credit rows.
  const noteY = box.y;
  const total13 = await page.locator('[data-derived="section3.total13"]').boundingBox();
  const credits = await page.locator('[data-rows="section3.new_credits"]').boundingBox();
  expect(noteY).toBeGreaterThan(total13.y);
  expect(noteY).toBeLessThan(credits.y);
});

test("every section heading bar runs the full width of the form", async ({ page }) => {
  // One complete block per section - Close & Sign Off is the reference. The
  // tables inside keep their own narrower widths.
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();

  const ref = await page.locator("#finalize-block").boundingBox();
  for (const id of ["sec-3", "sec-4", "sec-7", "sec-8", "sec-10", "sec-11"]) {
    const bar = await page.locator(`#${id} .section-title`).first().boundingBox();
    expect(Math.abs(bar.width - ref.width)).toBeLessThanOrEqual(2);
  }
});

test("Section 1's Petrol row shows Margin Total, 2T Sales, Total Sale Amt and IOCL Profit", async ({
  page,
}) => {
  // These were bare <td>s, so the renderer wrote .value into a table cell and
  // nothing ever appeared - the figures were computed the whole time.
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();
  await page.fill("#tb-date", DATE);
  await page.click("#load-btn");
  await expect(page.locator("#s3-src")).toContainText("Daily Sales Summary");

  for (const path of ["section1.margin_total", "section1.two_t_sales",
                      "section1.total_sale_amt", "section1.iocl_profit"]) {
    const cell = page.locator(`[data-derived="${path}"]`);
    await expect(cell).toHaveJSProperty("tagName", "INPUT");
    await expect(cell).toHaveValue(/^-?[\d,]*\.\d{2}$/);
  }
});
