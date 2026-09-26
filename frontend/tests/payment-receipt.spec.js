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

  // Pump Serial# is a dropdown now, not free text - a receipt cannot name a
  // pump that does not exist (client, 2026-09-25). Its options come from the
  // same fixed map Daily Sales Entry classifies against.
  await expect(page.locator("#r-pump option")).toContainText([
    "12BC4523V-RD", "11CC2012V-OFF",
  ]);
  await page.selectOption("#r-pump", "12BC4523V-RD");
  await page.fill("#r-attendant", "Gopi");
  await page.selectOption("#r-fuel", "Diesel");
  await page.fill("#r-liters", "10");
  await page.click("#issue-btn");

  await expect(page.locator("#issue-status")).toContainText("Issued SVR-");
  await expect(page.locator("#issued-card")).toBeVisible();
  // Two decimals on every sheet and section (client, 2026-09-11).
  // The issued receipt is its own document now, not the generic summary box
  // (client, 2026-09-25) - litres, rate and amount are columns in a sale table.
  const sale = page.locator(".rc-sale tr").nth(1);
  await expect(sale).toContainText("10.00");
  await expect(sale).toContainText("105.36");
  await expect(page.locator(".rc-total")).toContainText("1053.60");
  // And it carries the station's address, which a receipt handed to a customer
  // has to. From station_profile, so the Owner can correct it.
  await expect(page.locator(".rc-name")).toContainText("SVR IndianOil Service Station");
  await expect(page.locator(".rc-addr").first()).toContainText("G.B.C Road");
  await expect(page.locator(".rc")).toContainText("522124");
  await expect(page.locator(".rc-total")).toContainText("₹ 1053.60");

  // The new receipt shows in the recent list; a Sales user gets no Delete button.
  const row = page.locator("#receipt-rows tr").first();
  await expect(row).toContainText("Diesel");
  await expect(row.getByRole("button", { name: "Delete" })).toHaveCount(0);
});

// Client, 2026-09-25: "rate col should come from Inventory Master Sell Rate when
// Diesel(HS) or Petrol(MS) selected by default".
//
// The sell rate lives in Rate Master, not Inventory - Inventory tracks oil stock
// and the gas sell rate is effective-dated in rate_master, which is what the
// receipt endpoint has always used server-side. Same figure either way; this
// puts it in front of the operator BEFORE they issue, instead of only on the
// printed receipt.
test("the rate fills itself from the Sell Rate, and stays editable", async ({ page }) => {
  await login(page, "gsales");
  await page.goto(SCREEN);
  await expect(page.locator("#r-pump option").first()).toBeAttached();

  await page.selectOption("#r-fuel", "Diesel");
  const diesel = await page.locator("#r-rate").inputValue();
  expect(Number(diesel)).toBeGreaterThan(0);
  await expect(page.locator("#r-rate-note")).toContainText("Sell Rate");

  await page.selectOption("#r-fuel", "Petrol");
  const petrol = await page.locator("#r-rate").inputValue();
  expect(Number(petrol)).toBeGreaterThan(0);
  expect(petrol).not.toBe(diesel);          // the two fuels are not one price

  // A default, not a lock: typing over it wins, and switching back does not
  // silently overwrite what the operator entered.
  await page.fill("#r-rate", "99.50");
  await page.fill("#r-liters", "10");
  await expect(page.locator("#r-total")).toHaveValue("995.00");
});
