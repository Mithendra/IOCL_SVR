"use strict";

const { test, expect, request } = require("@playwright/test");
const { apiBase } = require("./_helpers");

const SCREEN = `/screens/daily-trial-balance/index.html?apiBase=${encodeURIComponent(apiBase)}`;
const DATE = "2026-10-20";

test.beforeAll(async () => {
  // Two pump submissions on DATE -> combined HS consumption 50 L.
  const ctx = await request.newContext();
  const token = (
    await (await ctx.post(`${apiBase}/auth/login`, {
      data: { login_name: "gsales", password: "demo1234" },
    })).json()
  ).token;
  const h = { Authorization: `Bearer ${token}` };
  // Pump serials no other spec touches -> no carried Last Reading, so consumption
  // is exactly the Current Reading (30 + 20 = 50 combined).
  await ctx.post(`${apiBase}/daily-sales-entry`, {
    headers: h,
    data: { pump_serial: "98AA0000V-OFF", shift_date: DATE, hs: { current: "30" } },
  });
  await ctx.post(`${apiBase}/daily-sales-entry`, {
    headers: h,
    data: { pump_serial: "98BB0000V-RDF", shift_date: DATE, hs: { current: "20" } },
  });
  await ctx.dispose();
});

async function login(page, user) {
  await page.goto(`/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  await page.fill("#login-name", user);
  await page.fill("#password", "demo1234");
  await page.click("#login-form button[type=submit]");
  await expect(page.locator("#nav-links .nav-item").first()).toBeVisible();
}

test("Sales has no Daily Trial Balance nav link", async ({ page }) => {
  await login(page, "gsales");
  await expect(page.locator('#nav-links a[data-module="daily-trial-balance"]')).toHaveCount(0);
});

test("Manager enters Section 1, sees computed columns + pulled Section 3, then finalizes", async ({
  page,
}) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#body")).toBeVisible();

  await page.fill("#tb-date", DATE);
  await page.click("#load-btn");
  // Wait until the DATE load has actually rendered (its own Section 3 message).
  await expect(page.locator("#s3-src")).toContainText("Daily Sales Summary");

  await page.fill("#hs-y", "100");
  await page.fill("#hs-c", "60");
  await page.fill("#cash-bv", "500000");
  await page.click("#save-btn");
  await expect(page.locator("#save-status")).toContainText("recalculated");

  await expect(page.locator("#hs-diff")).toHaveText("40"); // 100 - 60
  await expect(page.locator("#hs-cons")).toHaveText("50"); // pulled from Section 3
  await expect(page.locator("#hs-dt")).toHaveText("40"); // 50 - 10
  // 7.3 = 500000 + stock value total
  const s72 = Number(await page.locator("#s7-2").textContent());
  await expect(page.locator("#s7-3")).toHaveText(String(Math.round((500000 + s72) * 10000) / 10000));

  page.once("dialog", (d) => d.accept());
  await page.click("#finalize-btn");
  await expect(page.locator("#status-tag")).toHaveText("finalized");
  await expect(page.locator("#hs-c")).toBeDisabled();
  await expect(page.locator("#save-btn")).toBeDisabled();
});
