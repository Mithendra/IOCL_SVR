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
  // Only the Road pump records the oil sale, which is how the station works (one
  // submitter a day handles Oil Sale(s)); the Office entry leaves it blank and so
  // picks up Inventory's opening as a fallback. That pair is what proves Opening
  // Stock is a level and not something to add up across the two.
  await ctx.post(`${apiBase}/daily-sales-entry`, {
    headers: h,
    data: {
      pump_serial: PUMP_A,
      shift_date: DATE,
      hs: { current: "1030" },
      oils: [{ qty: "3", rate: "17", opening: "50" }],
    },
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

// ...and the two report differently ("Saved" vs "Updated; formulas recalculated."),
// so asserting on either one alone fails on whichever path that run took. The DB
// is rebuilt per run (global-setup.js), so this is about retries WITHIN a run.
const SAVED_OR_UPDATED = /Saved|Updated/;

// Close & Sign Off arms on the first press and fires on the second (2026-09-24).
// It used to ask through window.confirm(), which Electron never shows - so the
// button did nothing at all in the real app while these tests passed by
// accepting a dialog that only exists in a browser.
async function closeAndSignOff(page) {
  await page.click("#finalize-btn");
  await expect(page.locator("#finalize-btn")).toContainText("Confirm");
  await page.click("#finalize-btn");
}

// Open a date and WAIT for it to have landed. Load gives no signal, so
// `click("#load-btn")` followed by `fill(...)` is a race: when the GET resolves
// after the first fill, render() repaints the form from the stored record and
// silently discards what was just typed. It shows up as one field missing from
// the totals - a flake that looks exactly like a formula bug. Query reports into
// #tb-status either way, so that is the thing to wait on.
async function openDate(page, date) {
  await page.fill("#tb-date", date);
  await page.click("#query-btn");
  await expect(page.locator("#tb-status")).toHaveText(/Loaded|No Trial Balance saved/);
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
  // 4.4, 7.2 and 8.4 are DERIVED since 2026-09-24 - the station's sheet computes
  // them (SEP15!D52=D47, D77=K4, D85=D52) and typing them again is how the same
  // number came to disagree with itself. They are still on the form, read-only.
  // Two elements carry this now, and that is the point: 6.1 IS 4.4 (SEP15!D72 =
  // D52), so they read from the same derived figure instead of being two boxes
  // that can disagree.
  await expect(page.locator('[data-derived="section4.reported"]')).toHaveCount(2);
  await expect(page.locator('#cash-bv')).toBeDisabled();
  await expect(page.locator('[data-derived="section7.profit"]')).toBeVisible();
  await expect(page.locator('[data-derived="section8.f4"]')).toBeVisible();
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

  // Migration 0028, the client's restated lists. Credits are the three regular
  // customers only: the salary advances moved to Expenses (an advance to staff
  // is an expense, not fuel on credit) and "Anil New Credit" folded into
  // "Anil/Nani New Credit", Anil and Nani being one person.
  const creditor = page.locator('[data-rows="section3.new_credits"] tr').first().locator("select");
  await expect(creditor.locator("option")).toContainText([
    "— select —", "Anil/Nani New Credit", "AirTel Hari New Credit",
    "Sajja Function Hall - New Credit",
  ]);

  const expense = page.locator('[data-rows="section4.expenses"] tr').first().locator("select");
  await expect(expense.locator("option")).toContainText([
    "— select —",
    "Salaries Middle of the Month - Total", "Salaries End of the Month Total",
    "Power Bill", "Unload Beta",
    "Salary Advances Vijay", "Salary Advances Ravindra", "Salary Advances Ashok",
    "Other - If Any",
  ]);

  await expect(
    page.locator('[data-rows="section4.remittance"] tr').first().locator("select option")
  ).toContainText(["— select —", "Sajja Old Credit Remitted Amt"]);
  await expect(
    page.locator('[data-rows="section8.regular_expenses"] tr').first().locator("select option")
  ).toContainText(["Power Bill"]);
  // 8.7 no longer has a list of its own - it is carried from 4.7 (client,
  // 2026-09-24), so the only place a remittance is chosen is Section 4.
  await expect(page.locator('[data-rows="section8.old_credit_collections"]')).toHaveCount(0);

  // 8.9 sign-off: Prepared by / Verified by / Sent to, each a staff dropdown.
  for (const key of ["verified_by", "sent_by"]) {
    await expect(page.locator(`select[data-manual="section8.${key}"]`)).toHaveCount(1);
  }
  // Prepared by is in two places on purpose - the header ("who is doing this
  // Trial Balance") and 8.9 - bound to one stored field so they cannot disagree.
  const prepared = page.locator('select[data-manual="section8.prepared_by"]');
  await expect(prepared).toHaveCount(2);
  await prepared.first().selectOption("Girish");
  await expect(prepared.nth(1)).toHaveValue("Girish");
  await expect(page.locator('select[data-manual="section8.prepared_by"] option'))
    .toContainText(["Gopi", "Girish", "Sriharsha"]);

  // Every list-backed block offers "+ New ..." - a new customer asking for credit
  // has to be enterable the same day (client, 2026-09-12).
  //
  // "old_credit" is no longer among them. It backed 8.7, which is carried from
  // 4.7 now and has nothing to pick; and the two lists were seeded with the
  // SAME four values from the same client note, which is its own evidence that
  // one real-world remittance was being keyed in two places. 4.7's "remittance"
  // list is the one that remains, "+ New Type" and all.
  for (const list of ["creditors", "expenses", "remittance", "staff"]) {
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
  await openDate(page, CALC_DATE);

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
  await openDate(page, MANUAL_DATE);

  await page.fill('[data-manual="section3.onhand"]', "12345.67");
  // 4.4 is derived now; 4.1 is what the operator still types here.
  await page.fill('[data-manual="section11.new_airtel"]', "500");
  // Section 10 is a GRID block, not fields/rows - its own binding, and the only
  // section on the form built that way. Client, 2026-09-24: "10. Load/Unload
  // Details - Entered Details are missing."
  await page.fill('[data-manual="section10.hs_afterunload"]', "4321");
  await page.fill('[data-manual="section10.hs_old"]', "1000");
  await page.fill('[data-manual="section10.hs_new"]', "6000");
  await page.fill('[data-manual="section10.hs_load"]', "5100");
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
  // 4.4 comes back from 3.15, not from what was typed into it.
  await expect(page.locator('[data-derived="section4.reported"]').first()).toBeVisible();
  await expect(page.locator('[data-manual="section11.new_airtel"]')).toHaveValue("500.00");
  await expect(page.locator('[data-manual="section10.hs_afterunload"]')).toHaveValue("4321.00");
  await expect(page.locator('[data-manual="section10.hs_old"]')).toHaveValue("1000.00");
  await expect(page.locator('[data-manual="section10.hs_new"]')).toHaveValue("6000.00");
  await expect(page.locator('[data-manual="section10.hs_load"]')).toHaveValue("5100.00");
  // Total = New - Old = 5000; Lost = IOCL Load - Total = 100.
  await expect(page.locator('[data-derived="section10.hs.total"]')).toHaveValue("5000.00");
  await expect(page.locator('[data-derived="section10.hs.lost"]')).toHaveValue("100.00");
  await expect(creditRows.first().locator("select")).toHaveValue("AirTel Hari New Credit");
  await expect(creditRows.first().locator('[data-col="amount"]')).toHaveValue("2500.00");
});

// Client, 2026-09-24, restated after the first pass renamed the line but left
// the figures independent: "8.7 Old Credit Remittances is NOT Cary forward from
// 4.7 Credit Remittance."
test("8.7 Old Credit Remittances is carried from 4.7, not typed again", async ({
  page,
}) => {
  // Reuses the date the test above already created. ADR-2 refuses a NEW date
  // while an earlier one is open, and a fresh early date here would block every
  // test after it - which is exactly what it did the first time.
  const D = "2026-10-25";
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();
  await openDate(page, D);

  // 8.7 has no inputs and no "+ Add row" - there is nothing to key here.
  const mirror = page.locator('[data-mirror-rows="section8.old_credit_rows"]');
  await expect(mirror).toHaveCount(1);
  await expect(mirror.locator("input")).toHaveCount(0);
  await expect(mirror).toContainText("Nothing carried yet");

  // Enter a remittance in 4.7 and it appears in 8.7, with the total.
  const rem = page.locator('[data-rows="section4.remittance"] tr').first();
  await rem.locator("select").selectOption("Sajja Old Credit Remitted Amt");
  await rem.locator('[data-col="amount"]').fill("4500.25");
  await saveOrUpdate(page);
  await expect(page.locator("#save-status")).toContainText(SAVED_OR_UPDATED);

  await expect(mirror).toContainText("Sajja Old Credit Remitted Amt");
  await expect(mirror).toContainText("4500.25");
  await expect(
    page.locator('[data-derived="section8.old_credit_total"]')
  ).toHaveValue("4500.25");
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

  // Opening/Closing Stock is one tin's level, reported on both pumps' entries, so
  // it must NOT be added across them. Only the Road entry recorded this oil, with
  // an opening of 50; summing added the Office entry's Inventory fallback on top
  // and showed a stock the station never had - and disagreed with the Excel
  // export, which reads the sheet's own figure.
  const oil = page.locator("#s2-oil-rows tr", { hasText: "2T/1.50 ML" }).first();
  await expect(oil.locator("td").nth(1)).toHaveText("3.00"); // Sold - summed
  await expect(oil.locator("td").nth(3)).toHaveText("50.00"); // Opening - NOT summed
  await expect(oil.locator("td").nth(4)).toHaveText("47.00"); // Closing = 50 - 3

  // Two loads of the SAME date must not paint the pumps twice. Section 2 clears,
  // awaits, then appends, so overlapping runs used to leave 16 rows where 8
  // belong - every pump listed twice, with the totals below them unchanged. It
  // surfaced as an intermittent failure of the count above.
  await page.click("#query-btn");
  await page.click("#load-btn");
  await expect(page.locator("#s2-gas-rows tr")).toHaveCount(8);
  await expect(page.locator("#s2-combined-rows tr")).toHaveCount(2);
});

test("Section 2 keeps its whole shape on a day with nothing entered", async ({ page }) => {
  // It used to collapse to one line, which hid the section's entire structure.
  // The form opens on today, today usually has no Daily Sales Entry yet, and
  // Section 2 then looked like it had lost most of its rows and columns
  // (client, 2026-09-13: "I only see a few columns and few rows").
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();
  await openDate(page, "2026-07-04"); // no entry ever recorded here

  await expect(page.locator("#s2-gas-rows")).toContainText("Nothing pulled yet");
  // Heading + 2 fuels + subtotal, per pump, plus the note row.
  await expect(page.locator("#s2-gas-rows tr")).toHaveCount(9);
  await expect(page.locator("#s2-gas-rows")).toContainText(`${PUMP_A} (Road)`);
  await expect(page.locator("#s2-gas-rows")).toContainText(`${PUMP_B} (Office)`);
  await expect(page.locator("#s2-combined-rows tr")).toHaveCount(2);
  // Every item the station sells gets a row. NOT an exact count of seven any
  // more - the list is editable since 2026-09-13 - so this asserts the seven the
  // station seeds with are all present, which is the part that matters.
  for (const label of [
    "2T/1.50 ML Total#",
    "Acid Water Total 1 Lts",
    "Battery Water Total 1 Lts",
    "Battery Water Total 5 Lts",
    "20/40 Engine Total in 05. Lts",
    "20/40 Engine Total in 1 Lts",
  ]) {
    await expect(page.locator("#s2-oil-rows")).toContainText(label);
  }
  expect(await page.locator("#s2-oil-rows tr").count()).toBeGreaterThanOrEqual(7);

  // ...and the figures are BLANK, not 0.00. A pump that has not been entered has
  // an unknown total; printing zero would claim it sold nothing.
  await expect(page.locator("#s2-total-ltrs")).toHaveValue("");
  await expect(page.locator("#s2-daily-total")).toHaveValue("");
  await expect(
    page.locator("#s2-gas-rows tr", { hasText: `${PUMP_A} Total` }).locator("td").last(),
  ).toHaveText("");
});

test("the sheet is ruled into columns, not just rows", async ({ page }) => {
  // Row lines only meant the columns never read AS columns - and on a day with
  // nothing entered Section 2 was labels down the left and a void to the right
  // (client, raised twice: "column sections are missing").
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();

  const borderOf = (loc) =>
    loc.evaluate((el) => getComputedStyle(el).borderRightWidth);

  // A header cell and a body cell, both mid-row, carry a right-hand rule...
  expect(await borderOf(page.locator("#body th", { hasText: "Opening Stock" }))).not.toBe("0px");
  const row31 = page.locator("#sec-3 table tr").nth(1);
  expect(await borderOf(row31.locator("td").first())).not.toBe("0px");
  // ...and the last column does not, because the table's own border closes it.
  expect(await borderOf(row31.locator("td").last())).toBe("0px");
});

test("the Special Note sits in the middle of its section, not at the top", async ({ page }) => {
  // It was stretched top-to-bottom, so its heading sat against the orange bar.
  // The client wants it beside the middle rows - for Section 3, "somewhere in the
  // middle between 3.6 and 3.8" (2026-09-13).
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();

  const note = page.locator("#sec-3 .tb-notepanel .tb-note");
  const table = page.locator("#sec-3 .tb-blockrow > table");
  const nb = await note.boundingBox();
  const tb = await table.boundingBox();

  // Vertically centred on the table, within a row's height.
  const noteMid = nb.y + nb.height / 2;
  const tableMid = tb.y + tb.height / 2;
  expect(Math.abs(noteMid - tableMid)).toBeLessThan(20);
  // And well clear of the top, which is the thing that was wrong.
  expect(nb.y - tb.y).toBeGreaterThan(100);
  // A fixed box, not stretched to the table's height.
  expect(nb.height).toBeLessThan(tb.height / 2);
});

test("Section 6 lines up with the other sections", async ({ page }) => {
  // It was the one section built as a summary-box with its own 140px inputs, so
  // its value column sat ~127px right of everything else (client, 2026-09-13).
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();

  const rightEdge = async (sel) =>
    Math.round((await page.locator(sel).boundingBox()).x + (await page.locator(sel).boundingBox()).width);

  // Same markup as every other section - a table, not a box.
  const s6 = page.locator("#cash-bv").locator("xpath=ancestor::table[1]");
  await expect(s6).toHaveClass(/tb-fields/);
  // And it ends where its neighbours do.
  expect(await rightEdge("#cash-bv >> xpath=ancestor::table[1]")).toBe(
    await rightEdge("#s6-total >> xpath=ancestor::table[1]"),
  );
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
  // 6.1 is no longer typed - it derives from 4.4, which derives from 3.15. So
  // the day's cash comes in through Section 3, where the operator actually
  // counts it, rather than being keyed a second time here.
  await page.fill('[data-manual="section3.onhand"]', "500000");
  await saveOrUpdate(page);
  await expect(page.locator("#save-status")).toContainText("recalculated");

  await expect(page.locator("#hs-diff")).toHaveValue("40.00"); // 100 - 60
  await expect(page.locator("#hs-cons")).toHaveValue("50.00"); // pulled from Section 3
  // 50 - 10. Testing is 5 litres PER NOZZLE and follows how many pumps ran
  // (migrations 0026/0027), not a flat per-fuel constant. This spec files both
  // pumps and neither is in repair, so both are tested: 2 x 5 = 10.
  //
  // The flat 5 asserted here before was the ONE-pump case - correct only while a
  // pump was in the workshop, which nothing in the app recorded until Pump Status
  // existed. Sales Man Off is still tested: the pump runs and its meter moves.
  await expect(page.locator("#hs-dt")).toHaveValue("40.00");
  // 6.3 = 6.1 + 6.2. Compared numerically: both cells are formatted to two
  // decimals for display, so a string comparison would be comparing rounding.
  const s72 = Number(await page.locator("#s7-2").inputValue());
  const s73 = Number(await page.locator("#s7-3").inputValue());
  expect(s73).toBeCloseTo(500000 + s72, 2);

  await closeAndSignOff(page);
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

test("every line carries its section number, none left blank", async ({ page }) => {
  // Client, 2026-09-14: "All Sections especially must be numbered in Daily Trial
  // Balance". The eleven section headings always were; eleven LINES inside
  // sections 4 and 8 rendered with an empty number cell - the Difference
  // reconciliation panel (workbook E54:F56) and the Management Summary (D95:D102).
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();
  await page.fill("#tb-date", DATE);
  await page.click("#load-btn");
  await expect(page.locator("#s3-src")).toContainText("Daily Sales Summary");

  const body = page.locator("#body");
  // Section 4's side panel continues 4.1-4.7 rather than restarting.
  for (const n of ["4.8", "4.9", "4.10"]) {
    await expect(body).toContainText(n);
  }
  // Section 8's Management Summary, one number per line, workbook order.
  for (const n of ["8.8", "8.9", "8.10", "8.11", "8.12", "8.13", "8.14", "8.15"]) {
    await expect(body).toContainText(n);
  }
  // The block titles gave their numbers up to the lines beneath, so nothing is
  // numbered twice.
  await expect(body).not.toContainText("4.8 Difference reconciliation");
  await expect(body).not.toContainText("8.8 Management Summary");
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
  await expect(snap).toContainText("#OK Anything Above Rs 50 Call/inform mgmt immediately");
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

  // The DATE names the report, so it follows the day on screen - not today. This
  // was taken off the clock, which only looked right while every day was worked
  // on the day it happened; querying an old day showed it under today's date.
  await page.fill("#tb-date", "2026-03-07");
  await page.click("#query-btn");
  await expect(stamp).toHaveText(/^— 7 MAR, \d{1,2}:\d{2} (AM|PM) IST$/);
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

  // Exactly one of the two ever applies - that is the requirement, and stating it
  // this way also survives a Playwright retry, where attempt #1 already created
  // the row and Save is then correctly disabled.
  const saveLive = await page.locator("#save-btn").isEnabled();
  expect(saveLive).toBe(!(await page.locator("#update-btn").isEnabled()));

  await page.fill("#hs-c", "60");
  await saveOrUpdate(page);
  await expect(page.locator("#save-status")).toContainText(saveLive ? "Saved" : "Updated");

  // Once it is on file it is an Update from here, whichever way it started.
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
  await expect(page.locator("#hs-c")).toHaveValue("61.00");
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

  // A panel filling the space to the RIGHT of its own table, growing left to
  // right into it - the client sketched this on the Section 3 screenshot.
  const note = page.locator('textarea[data-manual="section3.special_note"]');
  const box = await note.boundingBox();
  const table = await page.locator('[data-derived="section3.total13"]')
    .locator("xpath=ancestor::table[1]").boundingBox();
  expect(box.x).toBeGreaterThan(table.x + table.width - 2);
  expect(box.width).toBeGreaterThan(200);

  // Still mid-section: alongside 3.1-3.13, before the 3.14 New Credit rows.
  const credits = await page.locator('[data-rows="section3.new_credits"]').boundingBox();
  expect(box.y).toBeLessThan(credits.y);
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

test("Query pulls up a given day and says what it found", async ({ page }) => {
  const D = "2026-01-03"; // earlier than every other saving test - see the note at the top
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();

  // A date with nothing saved says so, rather than quietly doing nothing - which
  // is what made saved data look unreachable on Daily Sales Entry in round 2.
  // Uses a date no test ever saves, so a Playwright retry cannot make it exist.
  const NEVER = "2099-01-01";
  await page.fill("#tb-date", NEVER);
  await page.click("#query-btn");
  await expect(page.locator("#tb-status")).toHaveClass(/err/);
  await expect(page.locator("#tb-status")).toContainText(`No Trial Balance saved for ${NEVER}`);

  // openDate, not fill-then-click: waiting for the load to land is the whole
  // point. Without it the 60 below is typed into a form that render() then
  // repaints from the stored record, so an EMPTY hs-c gets saved and the
  // assertion at the bottom fails - which is how this flaked.
  await openDate(page, D);
  await page.fill("#hs-c", "60");
  await saveOrUpdate(page);
  await expect(page.locator("#save-status")).toContainText(SAVED_OR_UPDATED);

  // And once saved, Query finds it and reports its state.
  await page.reload();
  await expect(page.locator("#body")).toBeVisible();
  await openDate(page, D);
  await expect(page.locator("#tb-status")).toHaveClass(/ok/);
  await expect(page.locator("#tb-status")).toContainText(`Loaded ${D}`);
  await expect(page.locator("#hs-c")).toHaveValue("60.00");
});

// Client, 2026-09-24: "snapshot whole sheet to clipboard instead save as PDF
// document to send via what's app." A clipboard PNG of eleven sections is one
// enormous strip WhatsApp re-compresses into mush, and it cannot be forwarded,
// filed or reopened. A document can.
test("the whole sheet goes out as a PDF document, not a clipboard picture", async ({
  page,
}) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();
  await expect(page.locator("#sheet-snapshot-btn")).toHaveCount(0);
  const btn = page.locator("#sheet-pdf-btn");
  await expect(btn).toBeVisible();
  await expect(btn).toContainText("PDF");

  // Page mode has no Electron bridge, so it must say so and point at the export.
  await btn.click();
  await expect(page.locator("#s8-send-status")).toHaveClass(/err/);
  await expect(page.locator("#s8-send-status")).toContainText("installed SVR app");
  await expect(page.locator("#s8-send-status")).toContainText("Export Trial Balance to Excel");
});


test("posting gates Close & Sign Off, and the list carries days forward", async ({ page }) => {
  // Client, 2026-09-14: "unless posted, do not allow Close & Sign Off." The
  // list deliberately spans days - an unpaid credit taken on Tuesday has to
  // still be in front of the operator on Thursday - so every assertion below is
  // scoped to THIS day's rows. Other specs leave their own lines in the view,
  // and that is correct behaviour, not interference.
  //
  // The date is earlier than every other in this file on purpose: ADR-2 refuses
  // to start a Trial Balance while any earlier one is still open.
  const DAY = "2026-01-02";
  const mine = page.locator(`#posting-rows tr:has-text("${DAY}")`);

  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();
  await openDate(page, DAY);

  const exp = page.locator('[data-rows="section4.expenses"] tr').first();
  await exp.locator("select").selectOption("Power Bill");
  await exp.locator('[data-col="amount"]').fill("8525.95");
  const cred = page.locator('[data-rows="section3.new_credits"] tr').first();
  await cred.locator("select").selectOption("AirTel Hari New Credit");
  await cred.locator('[data-col="amount"]').fill("11674");
  await saveOrUpdate(page);
  await expect(page.locator("#save-status")).toContainText("recalculated");

  // Both of this day's lines show as Not Posted, and sign-off is refused.
  await expect(mine).toHaveCount(2);
  await expect(mine.first()).toContainText("Not Posted");
  await closeAndSignOff(page);
  await expect(page.locator("#finalize-status")).toContainText("not posted");

  // Post them, and sign-off goes through.
  await page.click("#post-btn");
  await expect(page.locator("#post-status")).toContainText("Posted 2 line(s)");
  await expect(mine.filter({ hasText: "Not Posted" })).toHaveCount(0);
  await expect(mine.filter({ hasText: "Posted" })).toHaveCount(2);
  await closeAndSignOff(page);
  await expect(page.locator("#finalize-status")).toContainText(/Closed|Signed/i);

  // The posted expense can be cleared straight away (client: "if they post it to
  // expenses you can clear off those right away on the same day"); the unpaid
  // credit cannot, so it carries no tick box at all.
  await expect(mine.locator(".post-pick")).toHaveCount(1);
});


test("Section 9 keeps 7 days — older ledger rows can be deleted in one go", async ({ page }) => {
  // Client, 2026-09-15: "we will keep max of 7 days; if there is a button to
  // delete section 9 older than 7 days, that would be great." The ledger gains a
  // row a day and was never pruned - by SEP15 their own sheet carried three
  // weeks of them across 26 columns.
  const DAY = "2026-01-03";
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();
  await openDate(page, DAY);

  const rows = page.locator('[data-rows="section9.ledger"] tr');
  const addRow = page.locator('[data-add-row="section9.ledger"]');
  // The block already carries a blank row, and a row with no date is one still
  // being typed - it must survive. Add three dated ones: two well outside the
  // window, one inside it.
  const started = await rows.count();
  for (const d of ["2025-12-01", "2025-12-20", "2026-01-02"]) {
    await addRow.click();
    await rows.last().locator('[data-col="date"]').fill(d);
  }
  await expect(rows).toHaveCount(started + 3);

  page.once("dialog", (d) => d.accept());
  await page.locator('[data-purge="section9.ledger"]').click();

  // Measured from the SHIFT DATE on screen, not today - reopening an old day
  // must not wipe its ledger just because the calendar has moved on.
  await expect(rows).toHaveCount(started + 1);
  await expect(page.locator("#save-status")).toContainText("2 ledger row(s) removed");
  const dates = await rows.locator('[data-col="date"]').evaluateAll(
    (els) => els.map((e) => e.value).filter(Boolean));
  expect(dates).toEqual(["2026-01-02"]);
});

test("the two pre-close checks are on the form, with a + to add a tester", async ({ page }) => {
  // Client, 2026-09-16: "two rows above Close & Sign Off - 1. Density Reports
  // updated? 2. Off Load Testing MS & HS performed by, list of values Sarath,
  // Gopi, Sriharsha & Girish, also give + symbol to add more names."
  //
  // Asserted by LABEL, not by section number. The only existing test that
  // mentioned "8.10" was matching Section 8's Management Summary line of the
  // same number - which is how these two rows shipped numbered 8.10 as well,
  // colliding with it, and nothing failed. They are 8.16 and 8.17 now.
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();
  await page.fill("#tb-date", DATE);
  await page.click("#load-btn");

  const body = page.locator("#body");
  await expect(body).toContainText("Before Close & Sign Off");
  await expect(body).toContainText("Density Reports updated?");
  await expect(body).toContainText("Off Load Testing MS & HS performed by");

  // Both rows are dropdowns, each bound to its own list.
  const density = body.locator('select[data-manual="section8.density_reports_updated"]');
  const tester = body.locator('select[data-manual="section8.offload_tested_by"]');
  await expect(density).toHaveCount(1);
  await expect(tester).toHaveCount(1);
  await expect(density.locator("option")).toContainText(["Yes", "No", "N/A"]);
  for (const name of ["Sarath", "Gopi", "Sriharsha", "Girish"]) {
    await expect(tester.locator("option")).toContainText([name]);
  }

  // No number is used twice on the form - that is the whole point of numbering.
  const numbers = await body.locator(".tb-block-title, .tb-fields td:first-child")
    .allTextContents();
  const seen = new Map();
  for (const raw of numbers) {
    const m = /^(\d+\.\d+[a-z]?)\b/.exec(raw.trim());
    if (!m) continue;
    seen.set(m[1], (seen.get(m[1]) || 0) + 1);
  }
  const dupes = [...seen.entries()].filter(([, n]) => n > 1).map(([k]) => k);
  expect(dupes, `these numbers appear more than once: ${dupes.join(", ")}`)
    .toEqual([]);

  // The "+" writes to the tester list, not to staff.
  await body.locator('button[data-add-option="offload_testers"]').click();
  const box = body.locator('[data-newopt="offload_testers"]');
  await box.locator("[data-newopt-input]").fill("Ramesh");
  await box.locator("[data-newopt-save]").click();
  await expect(tester.locator("option")).toContainText(["Ramesh"]);
});
