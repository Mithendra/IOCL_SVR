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

  // ADR-2: finalizing auto-creates and seeds tomorrow's draft from today's
  // Reported (not Projected) values, with the carry-forward link shown.
  const tomorrow = new Date(DATE + "T00:00:00Z");
  tomorrow.setUTCDate(tomorrow.getUTCDate() + 1);
  await page.fill("#tb-date", tomorrow.toISOString().slice(0, 10));
  await page.click("#load-btn");
  await expect(page.locator("#carry-info")).toContainText(`Carried forward from ${DATE}`);
});
