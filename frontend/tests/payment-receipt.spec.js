"use strict";

const { test, expect } = require("@playwright/test");
const { apiBase } = require("./_helpers");

const SCREEN = `/screens/payment-receipt/index.html?apiBase=${encodeURIComponent(apiBase)}`;

async function login(page, user) {
  await page.goto(`/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  await page.fill("#login-name", user);
  await page.fill("#password", "demo1234");
  await page.click("#login-form button[type=submit]");
  await expect(page.locator("#nav-links .nav-item").first()).toBeVisible();
}

test("Sales can reach Payment Receipt (point of sale)", async ({ page }) => {
  await login(page, "gsales");
  await expect(page.locator('#nav-links a[data-module="payment-receipt"]')).toBeVisible();
});

test("Sales issues a Diesel receipt; rate + total come from Rate Master", async ({ page }) => {
  await login(page, "gsales");
  await page.goto(SCREEN);

  await page.fill("#r-pump", "12BC4523V-OFF");
  await page.fill("#r-attendant", "Gopi");
  await page.selectOption("#r-fuel", "Diesel");
  await page.fill("#r-liters", "10");
  await page.click("#issue-btn");

  await expect(page.locator("#issue-status")).toContainText("Issued SVR-");
  await expect(page.locator("#issued-card")).toBeVisible();
  await expect(page.locator("#ic-body")).toContainText("10 × 105.36");
  await expect(page.locator("#ic-body")).toContainText("₹ 1053.6");

  // The new receipt shows in the recent list; a Sales user gets no Delete button.
  const row = page.locator("#receipt-rows tr").first();
  await expect(row).toContainText("Diesel");
  await expect(row.getByRole("button", { name: "Delete" })).toHaveCount(0);
});
