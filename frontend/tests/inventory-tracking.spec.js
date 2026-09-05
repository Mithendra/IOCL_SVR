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

  // oil3 row now shows Received (Today) = 25.
  const oil3Row = page
    .locator("#stock-rows tr")
    .filter({ hasText: "Acid Water Total 1 Lts" });
  await expect(oil3Row.locator("td").nth(3)).toHaveText("25");
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
