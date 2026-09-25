"use strict";

const { test, expect } = require("@playwright/test");
const { apiBase } = require("./_helpers");

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

  // Reorder inputs are read-only for a Manager.
  await expect(page.locator("#stock-rows tr").first().locator(".reorder")).toBeDisabled();

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
  await login(page, "mmanager");
  await page.goto(SCREEN);
  const row = page.locator("#stock-rows tr").filter({ hasText: "2T/2.40 ML" });
  const onHand = row.locator(".on-hand");
  await expect(onHand).toBeEnabled();

  // Save is dead until something actually changes.
  await expect(page.locator("#save-inv-btn")).toBeDisabled();
  await onHand.fill("42");
  await expect(page.locator("#save-inv-btn")).toBeEnabled();
  await page.click("#save-inv-btn");
  await expect(page.locator("#restock-status")).toContainText("Saved:");

  // Zero is a real value, not "no value given".
  await row.locator(".on-hand").fill("0");
  await page.click("#save-inv-btn");
  const status = page.locator("#restock-status");
  await expect(status).toHaveClass(/ok/);
  await expect(status).toContainText("oil2 on hand → 0");
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
  await login(page, "oowner");
  await page.goto(SCREEN);
  const firstReorder = page.locator("#stock-rows tr").first().locator(".reorder");
  await expect(firstReorder).toBeEnabled();
  await firstReorder.fill("999");
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
  await login(page, "mmanager");
  await page.goto(SCREEN);
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
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await page.click("#oil-add-btn");
  await page.fill("#oil-new-label", "Brake Fluid Total 1 Lts");
  await page.fill("#oil-new-rate", "300");
  await page.click("#oil-new-save");
  await expect(page.locator("#oil-admin-status")).toContainText("Added");

  const row = page.locator("#oil-item-rows tr").filter({ hasText: "Brake Fluid Total 1 Lts" });
  await row.locator("button").click();
  // Retire, not delete: past days keep the row and keep their Oil Total.
  await expect(page.locator("#oil-admin-status")).toContainText("off the Daily Sales form");
  await expect(page.locator("#oil-admin-status")).toContainText("worth exactly what they were");
});

test("Sales cannot add or retire oil items", async ({ page }) => {
  await login(page, "gsales");
  await page.goto(SCREEN);
  // Sales has no access to Inventory Tracking at all, so the catalogue is out of
  // reach by the same gate as the rest of the screen.
  await expect(page.locator("#oil-add-btn")).toBeHidden();
});
