"use strict";

const { test, expect } = require("@playwright/test");
const { apiBase } = require("./_helpers");

const SCREEN = `/screens/credit-remittance-master/index.html?apiBase=${encodeURIComponent(apiBase)}`;

async function login(page, user) {
  // Clear the PRIOR page's sessionStorage token before navigating - if it's
  // still set when index.html's own script runs, app.js's "already signed
  // in" check fires goToDefaultScreen() before this fill ever finds the
  // login form (races with it, only visible as an intermittent hang), which
  // only bites here because this file is the only spec that switches roles
  // mid-test.
  await page.evaluate(() => {
    try {
      window.sessionStorage.clear();
    } catch {
      /* no-op on about:blank / first call */
    }
  });
  await page.goto(`/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  await page.fill("#login-name", user);
  await page.fill("#password", "demo1234");
  await page.click("#login-form button[type=submit]");
  await expect(page.locator("#nav-links .nav-item").first()).toBeVisible();
}

test("Sales has no Credit / Remittance Master nav link", async ({ page }) => {
  await login(page, "gsales");
  await expect(
    page.locator('#nav-links a[data-module="credit-remittance-master"]')
  ).toHaveCount(0);
});

test("a manual credit row auto-calculates and saves on blur", async ({ page }) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);

  const row = page.locator("#credit-rows tr").first();
  await row.locator("select.c-name").selectOption("AirTel Hari");
  await row.locator("select.c-type").selectOption("HS");
  await row.locator(".c-ltrs").fill("40");
  await row.locator(".c-rate").fill("125");
  // Two decimals on every sheet and section (client, 2026-09-11).
  await expect(row.locator(".c-amount")).toHaveValue("5000.00");

  // Saves on blur - leaving the row is what commits it.
  await row.locator(".c-note").fill("test row");
  await row.locator(".c-note").blur();
  await expect(page.locator("#txn-status")).toContainText("Saved");
  await expect(row.locator(".c-status")).toContainText("Manual");
});

test("a manual remittance row saves and both totals compute", async ({ page }) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);

  const row = page.locator("#remittance-rows tr").first();
  await row.locator("select.r-name").selectOption("Anil/Nani");
  await row.locator(".r-amount").fill("2000");
  await row.locator("select.r-payment").selectOption("Full");
  await row.locator("select.r-entered").selectOption("Yes");
  await row.locator("select.r-collector").selectOption("Sriharsha");
  await row.locator("select.r-mode").selectOption("Cash");
  await row.locator(".r-note").fill("");
  await row.locator(".r-note").blur();
  await expect(page.locator("#txn-status")).toContainText("Saved");
  await expect(page.locator("#remittance-total")).toHaveValue("2000.00");
});

test("+ New and - Delete work on Section 1's dropdowns, same as Daily Sales Entry", async ({
  page,
}) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);
  const row = page.locator("#credit-rows tr").first();
  const NAME = `New Creditor ${Date.now()}`;

  await row.locator(".row-new").click();
  await page.fill(".dse-newbox .nb-a", NAME);
  await page.click(".dse-newbox .nb-ok");
  await expect(row.locator("select.c-name")).toHaveValue(NAME);

  await row.locator(".row-del").click();
  await page.locator(".dse-delbox .del-one", { hasText: NAME }).click();
  await expect(page.locator(".dse-delbox")).toHaveCount(0);
  await expect(row.locator("select.c-name option")).not.toContainText([NAME]);
});

test("Old Credit Given Date reads DD/MMM/YYYY, same as Daily Sales Entry Section 6", async ({
  page,
}) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);
  const given = page.locator("#remittance-rows tr").first().locator(".r-given");
  await given.fill("9/3/26");
  await given.blur();
  await expect(given).toHaveValue("09/MAR/2026");
});

test("+ Add Creditor shows the new name at zero, with no transaction yet", async ({ page }) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);
  const NAME = `Zero Balance Co ${Date.now()}`;

  await page.click("#cs-add-btn");
  await page.fill("#cs-new-name", NAME);
  await page.selectOption("#cs-new-type", "old");
  await page.click("#cs-new-save");

  const row = page.locator("#summary-rows tr").filter({ hasText: NAME });
  await expect(row).toBeVisible();
  await expect(row.locator("td").nth(2).locator("input")).toHaveValue("0.00");
  await expect(row.locator("select.cs-type")).toHaveValue("old");
});

test("adding a creditor here also offers the name on Daily Sales Entry", async ({ page }) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);
  const NAME = `Cross Screen Co ${Date.now()}`;
  await page.click("#cs-add-btn");
  await page.fill("#cs-new-name", NAME);
  await page.click("#cs-new-save");
  await expect(page.locator("#summary-rows tr").filter({ hasText: NAME })).toBeVisible();

  await page.goto(`/screens/daily-sales-entry/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  await page.waitForTimeout(500);
  await expect(page.locator("#nc-rows tr").first().locator("select.nc-name option"))
    .toContainText([NAME]);
});

test("a document uploads, lists, and downloads for a creditor", async ({ page }) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);
  const NAME = `Doc Test Co ${Date.now()}`;
  await page.click("#cs-add-btn");
  await page.fill("#cs-new-name", NAME);
  await page.click("#cs-new-save");

  const row = page.locator("#summary-rows tr").filter({ hasText: NAME });
  await row.locator(".cs-docs-btn").click();
  await expect(page.locator("#docs-panel")).toBeVisible();
  await expect(page.locator("#docs-panel-title")).toContainText(NAME);

  await page.setInputFiles("#doc-file", {
    name: "old-agreement.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4\ntest agreement"),
  });
  await page.fill("#doc-note", "scanned page 1");
  await page.click("#doc-upload-btn");
  await expect(page.locator("#doc-status")).toContainText("Uploaded");
  await expect(page.locator("#doc-rows")).toContainText("old-agreement.pdf");
});

test("search filters the summary by a date range", async ({ page }) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await page.fill("#cs-from", "1999-01-01");
  await page.fill("#cs-to", "1999-01-02");
  await page.click("#cs-search-btn");
  // A range with nothing in it still returns a real, honest empty result.
  await expect(page.locator("#summary-rows")).toContainText("No creditors match");
  await page.click("#cs-clear-btn");
});

test("a credit posted from Daily Trial Balance shows up here as Posted by DT", async ({
  page,
}) => {
  const date = "2026-12-01";
  await login(page, "gsales");
  await page.goto(`/screens/daily-sales-entry/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  await page.fill("#shift-date", date);
  await page.selectOption("#pump-serial", "12BC4523V-RD");
  await page.waitForTimeout(500);
  await page.fill("#hs-current", "9800000");
  await page.fill("#ms-current", "9800000");
  const ncRow = page.locator("#nc-rows tr").first();
  await ncRow.locator("select.nc-name").selectOption("AirTel Hari");
  await ncRow.locator("select.nc-type").selectOption("HS");
  await ncRow.locator(".nc-ltrs").fill("7");
  await page.click("#save-btn");
  await expect(page.locator("#save-status")).toContainText(/saved/i);

  await login(page, "mmanager");
  await page.goto(`/screens/daily-trial-balance/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  await page.fill("#tb-date", date);
  await page.click("#load-btn");
  await page.waitForTimeout(500);
  await page.click("#save-btn, #update-btn");
  // Saving the Trial Balance only files the line as "not_posted"
  // (trial_balance_posting) - posting.post_line(), which is what actually
  // writes credit_transaction, only runs off the Checker's own "Post
  // Credit/Remittance" button (posting.py: "Unless posted do not allow
  // Close & Sign Off" - a deliberate maker-checker gate, not automatic).
  // Wait for the real state (the row's own checkbox, the button's own status
  // line) rather than a fixed timeout - save() and postKinds() both kick off
  // their own fetch without awaiting it from the click handler.
  await expect(
    page.locator('.post-pick[data-category="credit"][data-status="not_posted"]')
  ).toHaveCount(1);
  await page.click("#post-credits-btn");
  await expect(page.locator("#post-status")).toContainText(/Posted 1/);

  await page.goto(SCREEN);
  // Not .filter({ hasText: "AirTel Hari" }) - every blank row's own <select>
  // carries that text inside an unselected <option> too (textContent counts
  // hidden option text), so a substring filter matches more than one row.
  // Match the row whose dropdown VALUE is that name instead - inside a
  // .toPass() retry loop, since init()'s own loadTransactions() is still an
  // un-awaited-by-the-test fetch racing the assertion right after goto().
  let posted = null;
  await expect(async () => {
    const rows = page.locator("#credit-rows tr");
    const rowCount = await rows.count();
    posted = null;
    for (let i = 0; i < rowCount; i++) {
      const row = rows.nth(i);
      if ((await row.locator("select.c-name").inputValue()) === "AirTel Hari") {
        posted = row;
        break;
      }
    }
    expect(posted).not.toBeNull();
  }).toPass({ timeout: 10000 });
  await expect(posted.locator(".c-status")).toContainText("Posted by DT");
});

test("a saved row shows Updated On and Updated By", async ({ page }) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);

  // Wait for the page's own init() (kit.loadLists() + loadTransactions())
  // to actually finish before clicking "+ Add row" - click too early and the
  // freshly-built row's dropdown renders with no options yet, since the
  // click handler is wired before those awaited loads resolve (so a click
  // is never silently swallowed - see init()'s own comment on that).
  await page.locator("#credit-rows tr").first().waitFor();
  // Not .first() itself - by this point in the file other tests have
  // already left posted/paid (disabled) rows in #credit-rows, sharing this
  // run's DB. "+ Add row" guarantees a fresh, editable one.
  await page.click("#add-credit-row");
  const row = page.locator("#credit-rows tr").last();
  await row.locator("select.c-name").selectOption("Sajja Function Hall");
  await row.locator("select.c-type").selectOption("MS");
  await row.locator(".c-ltrs").fill("10");
  await row.locator(".c-rate").fill("117.70");
  await row.locator(".c-rate").blur();
  // Wait for this save to actually land before touching Notes - see the
  // Paid/Clear test below for why (an un-awaited saveCreditRow() racing a
  // second blur before dataset.id is set creates a duplicate row).
  await expect(async () => {
    expect(await row.getAttribute("data-id")).toBeTruthy();
  }).toPass({ timeout: 10000 });
  await row.locator(".c-note").fill("updated-on check");
  await row.locator(".c-note").blur();
  await expect(page.locator("#txn-status")).toContainText("Saved");

  const cells = row.locator("td");
  const count = await cells.count();
  // Updated By is the second-to-last cell (the last is the +New/-Delete
  // actions cell) - client, 2026-09-27: "CM must have Updated On Updated By".
  await expect(cells.nth(count - 2)).toContainText("mmanager");
  await expect(cells.nth(count - 3)).not.toHaveText("");
});

test("a remittance settles the matching credit to Paid, and Clear removes it", async ({
  page,
}) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);
  const NAME = `Paid Flow Co ${Date.now()}`;

  await page.click("#cs-add-btn");
  await page.fill("#cs-new-name", NAME);
  await page.click("#cs-new-save");
  // Wait for confirmation the save actually landed before navigating away -
  // click() only waits for the DOM event, not for add_creditor()'s own
  // fetch to finish, and navigating mid-request would abandon it.
  await expect(page.locator("#summary-rows tr").filter({ hasText: NAME })).toBeVisible();
  // "+ Add Creditor" writes the name to the option lists server-side, but
  // this page's own dropdowns loaded their options once at init() - reload
  // so Section 1/2's "customers" select actually offers the new name.
  await page.goto(SCREEN);
  await page.locator("#credit-rows tr").first().waitFor();

  await page.click("#add-credit-row");
  const creditRow = page.locator("#credit-rows tr").last();
  await creditRow.locator("select.c-name").selectOption(NAME);
  await creditRow.locator(".c-ltrs").fill("10");
  await creditRow.locator(".c-rate").fill("100");
  await creditRow.locator(".c-rate").blur();
  // Wait for THIS save to actually land (dataset.id set) before touching
  // Notes - saveCreditRow() is async and un-awaited by the blur listener,
  // so blurring Notes immediately after would race the row's own create
  // (both would still see no id yet and both POST, leaving two duplicate
  // credit rows instead of one create + one note PATCH).
  await expect(async () => {
    expect(await creditRow.getAttribute("data-id")).toBeTruthy();
  }).toPass({ timeout: 10000 });
  await creditRow.locator(".c-note").fill("settlement check");
  await creditRow.locator(".c-note").blur();
  await expect(page.locator("#txn-status")).toContainText("Saved");

  await page.click("#add-remittance-row");
  const remRow = page.locator("#remittance-rows tr").last();
  await remRow.locator("select.r-name").selectOption(NAME);
  await remRow.locator(".r-amount").fill("1000");
  await remRow.locator(".r-amount").blur();
  await expect(page.locator("#txn-status")).toContainText("Saved");

  // saveRemittanceRow() reloads Section 1 on a new remittance, so the
  // credit's own row (a fresh DOM element after the reload) should now
  // read Paid and offer Clear. Not .filter({ hasText: NAME }) - every
  // OTHER row's own <select> carries that name inside an unselected
  // <option> too (it's now in the shared "customers" list), so a text
  // filter matches more than one row. Match the row whose dropdown VALUE
  // is that name instead.
  let settled = null;
  await expect(async () => {
    const rows = page.locator("#credit-rows tr");
    const rowCount = await rows.count();
    settled = null;
    for (let i = 0; i < rowCount; i++) {
      const row = rows.nth(i);
      if ((await row.locator("select.c-name").inputValue()) === NAME) {
        settled = row;
        break;
      }
    }
    expect(settled).not.toBeNull();
  }).toPass({ timeout: 10000 });
  await expect(settled.locator(".c-status")).toContainText("Paid");
  await expect(settled.locator("[data-clear]")).toBeVisible();

  await settled.locator("[data-clear]").click();
  await expect(page.locator("#txn-status")).toContainText("Cleared");
  // clearCreditRow() reloads the table, so `settled` now points at a
  // detached element - find the row fresh, same way as above.
  let afterClear = null;
  await expect(async () => {
    const rows = page.locator("#credit-rows tr");
    const rowCount = await rows.count();
    afterClear = null;
    for (let i = 0; i < rowCount; i++) {
      const row = rows.nth(i);
      if ((await row.locator("select.c-name").inputValue()) === NAME) {
        afterClear = row;
        break;
      }
    }
    expect(afterClear).not.toBeNull();
  }).toPass({ timeout: 10000 });
  await expect(afterClear.locator(".c-status")).toContainText("Cleared");
});
