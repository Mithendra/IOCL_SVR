"use strict";

const { test, expect, request } = require("@playwright/test");
const { apiBase } = require("./_helpers");

// The Inventory Master shares the Owner passphrase with the reading reset - one
// secret, one place. Set once; "already set" on a later run is fine, the suite
// shares a database and the value never changes.
const SECRET = "stock-lock-2026";
let secretReady = false;

// Stock editing is behind a button that asks for the passphrase (client,
// 2026-09-25). Inline, not window.prompt() - Electron never shows that dialog.
async function unlockStock(page) {
  await page.click("#inv-unlock-btn");
  await page.fill("#inv-secret", SECRET);
  await page.click("#inv-unlock-ok");
  await expect(page.locator("#inv-unlock-state")).toContainText("Unlocked");
}

async function setOwnerSecret() {
  if (secretReady) return;
  const ctx = await request.newContext();
  const token = (
    await (await ctx.post(`${apiBase}/auth/login`, {
      data: { login_name: "oowner", password: "demo1234" },
    })).json()
  ).token;
  await ctx.post(`${apiBase}/owner-reset/secret`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { new_passphrase: SECRET },
  });
  secretReady = true;
}

const SCREEN = `/screens/inventory-tracking/index.html?apiBase=${encodeURIComponent(apiBase)}`;
const DATE = "2026-06-10";

async function login(page, user) {
  await page.goto(`/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  await page.fill("#login-name", user);
  await page.fill("#password", "demo1234");
  await page.click("#login-form button[type=submit]");
  await expect(page.locator("#nav-links .nav-item").first()).toBeVisible();
}

test("Sales has no Inventory Tracking nav link", async ({ page }) => {
  await login(page, "gsales");
  await expect(page.locator('#nav-links a[data-module="inventory-tracking"]')).toHaveCount(0);
});

test("Manager sees the 7 SKUs and can record a restock", async ({ page }) => {
  await setOwnerSecret();
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await page.fill("#as-of", DATE);
  await page.locator("#as-of").dispatchEvent("change");

  // The seven the station seeds with (migration 0017). NOT an exact row count any
  // more: the Owner can add oil items since 2026-09-13, and retiring one leaves
  // its inventory row alone on purpose - tins already on the shelf are still
  // stock, whether or not the product is still sold.
  for (const sku of [
    "2T/1.50 ML Total#",
    "2T/2.40 ML Total#",
    "Acid Water Total 1 Lts",
    "Battery Water Total 1 Lts",
    "Battery Water Total 5 Lts",
    "20/40 Engine Total in 05. Lts",
    "20/40 Engine Total in 1 Lts",
  ]) {
    await expect(page.locator("#stock-rows")).toContainText(sku);
  }

  // Reorder Level is editable by a Manager now - one rule for the whole form
  // (client, 2026-09-25: "Manager can be updated but secert password is need
  // from the owner"). The password is the gate, not the role, so the field is
  // enabled and Save is what refuses without it.
  await expect(page.locator("#stock-rows tr").first().locator(".reorder")).toBeEnabled();

  // Restock is gated too now - the WHOLE form is (client, 2026-09-25).
  await unlockStock(page);
  await page.fill("#rs-date", DATE);
  await page.selectOption("#rs-item", "oil3");
  await page.fill("#rs-qty", "25");
  await page.fill("#rs-ref", "INV-777");
  await page.click("#restock-btn");
  await expect(page.locator("#restock-status")).toContainText("Restock recorded");

  // oil3 row now shows Received (Today) including the 25 just logged. Figures
  // read to two decimals (2026-09-11); on a retry the restock can stack, so
  // assert the format and the floor rather than an exact one-shot value.
  const oil3Row = page
    .locator("#stock-rows tr")
    .filter({ hasText: "Acid Water Total 1 Lts" });
  const received = oil3Row.locator("td").nth(3);
  await expect(received).toHaveText(/^\d+\.\d{2}$/);
  expect(Number(await received.textContent())).toBeGreaterThanOrEqual(25);
});

test("Manager sets Opening Stock, and nothing is written until Save", async ({ page }) => {
  // Restock adds; Opening Stock replaces. Before 2026-09-11 only the additive
  // path was reachable, so a correction stacked on top of the old figure.
  //
  // And since 2026-09-24 the write waits for Save (client: "there is no Save
  // button which is needed"). It used to fire on `change`, so a number reached
  // the database the moment the cell lost focus - no confirmation, no undo, and
  // clicking away mid-edit committed whatever was in the box. On Hand is the
  // opening stock every later day is measured from; it should take a press.
  // Owner, not Manager, since 2026-09-25 - and behind the Owner passphrase.
  await setOwnerSecret();
  await login(page, "oowner");
  await page.goto(SCREEN);
  const row = page.locator("#stock-rows tr").filter({ hasText: "2T/2.40 ML" });
  const onHand = row.locator(".on-hand");
  await expect(onHand).toBeEnabled();

  // Save is dead until something actually changes.
  await expect(page.locator("#save-inv-btn")).toBeDisabled();
  await onHand.fill("42");
  await expect(page.locator("#save-inv-btn")).toBeEnabled();

  // ...and until it is unlocked, Save says so rather than writing.
  await page.click("#save-inv-btn");
  await expect(page.locator("#restock-status")).toContainText("Unlock stock editing");
  await page.click("#inv-unlock-cancel");
  await unlockStock(page);
  await page.click("#save-inv-btn");
  await expect(page.locator("#restock-status")).toContainText("Saved:");

  // Zero is a real value, not "no value given".
  await row.locator(".on-hand").fill("0");
  await page.click("#save-inv-btn");
  const status = page.locator("#restock-status");
  await expect(status).toHaveClass(/ok/);
  await expect(status).toContainText("oil2 on hand → 0");
});

// Client, 2026-09-25: "Inventory Tracking Master should have Secert Password to
// make an update only owner role and it should have Secret password to update."
test("a Manager may edit, but only with the Owner passphrase", async ({ page }) => {
  // Client settled this on 2026-09-25: "Manager can be updated but secert
  // password is need from the owner". The password is the authority, the role is
  // who is at the keyboard, and Updated By records which of them it was.
  await setOwnerSecret();
  await login(page, "mmanager");
  await page.goto(SCREEN);
  const row = page.locator("#stock-rows tr").filter({ hasText: "2T/2.40 ML" });

  await row.locator(".on-hand").fill("33");
  await page.click("#save-inv-btn");
  await expect(page.locator("#restock-status")).toContainText("Unlock stock editing");

  await unlockStock(page);
  await page.click("#save-inv-btn");
  await expect(page.locator("#restock-status")).toContainText("Saved:");
});

test("every row shows who changed it and when", async ({ page }) => {
  await setOwnerSecret();
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#stock-rows tr").first()).toBeVisible();
  // Buy Rate, Sell Rate, Updated By, Updated On (client, 2026-09-25).
  for (const heading of ["Buy Rate", "Sell Rate", "Updated By", "Updated On"]) {
    await expect(page.locator("table").first()).toContainText(heading);
  }
});

test("Undo puts an edit back without writing it", async ({ page }) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);
  const row = page.locator("#stock-rows tr").filter({ hasText: "2T/2.40 ML" });
  const before = await row.locator(".on-hand").inputValue();

  await row.locator(".on-hand").fill("777");
  await expect(page.locator("#save-inv-btn")).toBeEnabled();
  await page.click("#undo-inv-btn");

  await expect(page.locator("#restock-status")).toContainText("Edits discarded");
  await expect(row.locator(".on-hand")).toHaveValue(before);
  await expect(page.locator("#save-inv-btn")).toBeDisabled();
});

test("Owner edits a Reorder Level and saves it", async ({ page }) => {
  await setOwnerSecret();
  await login(page, "oowner");
  await page.goto(SCREEN);
  const firstReorder = page.locator("#stock-rows tr").first().locator(".reorder");
  await expect(firstReorder).toBeEnabled();
  await firstReorder.fill("999");
  await unlockStock(page);
  await page.click("#save-inv-btn");
  await expect(page.locator("#restock-status")).toContainText("reorder level → 999");
});

test("the oil catalogue lives here, not on the daily form", async ({ page }) => {
  // Client, 2026-09-24: "New Oil Item is not needed on the Daily Sales form,
  // which should be there in Inv Master only."
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#oil-add-btn")).toBeVisible();
  await expect(page.locator("#oil-item-rows")).toContainText("2T/2.40 ML");
  // Retire is offered per item, and says plainly what it does.
  await expect(page.locator("#oil-item-rows tr").first()).toContainText("Retire");
});


test("Manager adds an oil item here and it appears on the Daily Sales form", async ({
  page,
}) => {
  // Moved from daily-sales-entry.spec.js on 2026-09-24 with the controls
  // themselves (client: "+ New Oil Item ... should be there in Inv Master only").
  await setOwnerSecret();
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await unlockStock(page);
  await page.click("#oil-add-btn");
  await page.fill("#oil-new-label", "Gear Oil Total 1 Lts");
  await page.fill("#oil-new-rate", "190");
  await page.fill("#oil-new-stock", "25");
  await page.click("#oil-new-save");
  await expect(page.locator("#oil-admin-status")).toContainText("Added");
  await expect(page.locator("#oil-item-rows")).toContainText("Gear Oil Total 1 Lts");

  // It is a real product now: it reaches the daily form's Oil Sale(s) rows.
  await page.goto(`/screens/daily-sales-entry/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  await expect(page.locator("#oil-rows")).toContainText("Gear Oil Total 1 Lts");
});

test("retiring an item takes it off the daily form, and says what that means", async ({
  page,
}) => {
  await setOwnerSecret();
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await unlockStock(page);
  await page.click("#oil-add-btn");
  await page.fill("#oil-new-label", "Brake Fluid Total 1 Lts");
  await page.fill("#oil-new-rate", "300");
  await page.click("#oil-new-save");
  await expect(page.locator("#oil-admin-status")).toContainText("Added");

  const row = page.locator("#oil-item-rows tr").filter({ hasText: "Brake Fluid Total 1 Lts" });
  await expect(row).toContainText("On the daily form");

  // Two presses. One click used to do it, with nothing in this list changing
  // afterwards - five items went in four seconds on 2026-09-25 because pressing
  // again looked like the only thing that could work.
  await row.getByRole("button", { name: "Retire" }).click();
  await expect(page.locator("#oil-admin-status")).toContainText("Press again to confirm");
  await expect(row).toContainText("On the daily form");   // nothing has happened yet

  await row.getByRole("button", { name: "Confirm retire" }).click();
  // Retire, not delete: past days keep the row and keep their Oil Total.
  await expect(page.locator("#oil-admin-status")).toContainText("off the Daily Sales form");
  await expect(page.locator("#oil-admin-status")).toContainText("worth exactly what they were");

  // It is still LISTED, marked retired - not vanished with no way back.
  await expect(row).toContainText("Retired");

  // ...and Restore puts it back.
  await row.getByRole("button", { name: "Restore" }).click();
  await expect(page.locator("#oil-admin-status")).toContainText("back on the Daily Sales form");
  await expect(row).toContainText("On the daily form");
});

test("the last item on the daily form cannot be retired", async ({ page }) => {
  // Oil Sale(s) with no rows at all is a broken form, not an empty one, and
  // there would be no way back through the UI.
  await setOwnerSecret();
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await unlockStock(page);

  const active = page.locator("#oil-item-rows tr").filter({ hasText: "On the daily form" });
  const count = await active.count();
  expect(count).toBeGreaterThan(0);
  if (count > 1) {
    // With more than one active, Retire is offered.
    await expect(active.first().getByRole("button", { name: "Retire" })).toBeEnabled();
  } else {
    await expect(active.first().getByRole("button", { name: "Retire" })).toBeDisabled();
  }
});

test("Sales cannot add or retire oil items", async ({ page }) => {
  await login(page, "gsales");
  await page.goto(SCREEN);
  // Sales has no access to Inventory Tracking at all, so the catalogue is out of
  // reach by the same gate as the rest of the screen.
  await expect(page.locator("#oil-add-btn")).toBeHidden();
});

// Client, 2026-09-25: "this form should have a capability to upload the Stock
// Purchase document uploaded like invoice in pdf, jpg any other supported format
// so that we can see what we bought to keep track forever."
test("a stock purchase invoice can be uploaded and read back", async ({ page }) => {
  // Every edit on this form needs the Owner passphrase, upload included
  // (client, 2026-09-25). A Manager may make the change; the password is the
  // authority.
  await setOwnerSecret();
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#sp-table")).toBeVisible();
  await unlockStock(page);

  await page.fill("#sp-date", "2026-06-05");
  await page.fill("#sp-supplier", "Bharat Oils");
  await page.fill("#sp-amount", "18400.50");
  await page.setInputFiles("#sp-file", {
    name: "invoice 4471.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4 scanned invoice"),
  });
  await page.click("#sp-upload-btn");

  await expect(page.locator("#sp-status")).toHaveClass(/ok/);
  await expect(page.locator("#sp-status")).toContainText("Stored");

  // It is listed, with the supplier and amount it was filed under.
  const row = page.locator("#sp-rows tr").first();
  await expect(row).toContainText("2026-06-05");
  await expect(row).toContainText("Bharat Oils");
  await expect(row).toContainText("18400.50");
  await expect(row).toContainText("invoice");
});

test("an unsupported file is refused, with a reason", async ({ page }) => {
  await setOwnerSecret();
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await unlockStock(page);
  await page.setInputFiles("#sp-file", {
    name: "payload.exe",
    mimeType: "application/x-msdownload",
    buffer: Buffer.from("MZ"),
  });
  await page.click("#sp-upload-btn");
  await expect(page.locator("#sp-status")).toHaveClass(/err/);
  await expect(page.locator("#sp-status")).toContainText("not accepted");
});
