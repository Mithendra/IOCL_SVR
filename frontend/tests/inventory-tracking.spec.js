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

test("Manager sees the 5 SKUs and can record a restock", async ({ page }) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await page.fill("#as-of", DATE);
  await page.locator("#as-of").dispatchEvent("change");

  await expect(page.locator("#stock-rows tr")).toHaveCount(5);

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

test("Manager can set Opening Stock outright, including to zero", async ({ page }) => {
  // Restock adds; Opening Stock replaces. Before 2026-09-11 only the additive
  // path was reachable, so a correction stacked on top of the old figure.
  await login(page, "mmanager");
  await page.goto(SCREEN);
  const oil2Row = page.locator("#stock-rows tr").filter({ hasText: "2T/2.40 ML" });
  const onHand = oil2Row.locator(".on-hand");
  await expect(onHand).toBeEnabled();

  await onHand.fill("42");
  await onHand.dispatchEvent("change");
  await expect(page.locator("#restock-status")).toContainText("replaced, not added");

  // Zero is a real value, not "no value given". Asserted on the success of the
  // write rather than on the field afterwards: Print & Sync in the Daily Sales
  // Entry spec rewrites every oil's on_hand, so the stored number is shared
  // state across specs, while whether the server accepted 0 is not.
  const row = page.locator("#stock-rows tr").filter({ hasText: "2T/2.40 ML" });
  await row.locator(".on-hand").fill("0");
  await row.locator(".on-hand").dispatchEvent("change");
  const status = page.locator("#restock-status");
  await expect(status).toHaveClass(/ok/);
  await expect(status).toContainText(/Opening Stock for oil2 set to .* \(replaced, not added\)/);
});

test("Owner can edit a Reorder Level inline", async ({ page }) => {
  await login(page, "oowner");
  await page.goto(SCREEN);
  const firstReorder = page.locator("#stock-rows tr").first().locator(".reorder");
  await expect(firstReorder).toBeEnabled();
  await firstReorder.fill("999");
  await firstReorder.dispatchEvent("change");
  await expect(page.locator("#restock-status")).toContainText("set to 999");
});
