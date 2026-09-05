"use strict";

const { test, expect, request } = require("@playwright/test");
const { apiBase } = require("./_helpers");

const DATE = "2026-07-15";
const OFF = "12BC4523V-OFF";
const ROAD = "11CC2012V-RDF";
const SCREEN = `/screens/daily-sales-summary/index.html?apiBase=${encodeURIComponent(apiBase)}`;

async function seedEntries() {
  const ctx = await request.newContext();
  const token = (
    await (await ctx.post(`${apiBase}/auth/login`, {
      data: { login_name: "gsales", password: "demo1234" },
    })).json()
  ).token;
  const headers = { Authorization: `Bearer ${token}` };
  for (const [pump, hs] of [[OFF, "1317.52"], [ROAD, "1000"]]) {
    await ctx.post(`${apiBase}/daily-sales-entry`, {
      headers,
      data: { pump_serial: pump, shift_date: DATE, hs: { current: hs }, ms: { current: "0" } },
    });
  }
  await ctx.dispose();
}

async function loginManager(page) {
  await page.goto(`/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  await page.fill("#login-name", "mmanager");
  await page.fill("#password", "demo1234");
  await page.click("#login-form button[type=submit]");
  await expect(page.locator("#nav-links .nav-item").first()).toBeVisible();
}

test("combine two submissions, verify both, then upload", async ({ page }) => {
  await seedEntries();
  await loginManager(page);
  await page.goto(SCREEN);
  await page.fill("#shift-date", DATE);
  await page.locator("#shift-date").dispatchEvent("change");

  // Combined grand total is populated from the backend.
  await expect(page.locator("#grand-total")).not.toHaveValue("");
  await expect(page.locator("#gate-status")).toContainText("must be verified");
  await expect(page.locator("#upload-btn")).toBeDisabled();

  // Verify both pumps.
  await page.selectOption("#off-verified", "1");
  await page.selectOption("#road-verified", "1");
  await expect(page.locator("#gate-status")).toContainText("ready to upload");
  await expect(page.locator("#upload-btn")).toBeEnabled();

  await page.click("#upload-btn");
  await expect(page.locator("#upload-status")).toContainText("Uploaded");
  await expect(page.locator("#status-tag")).toHaveText("uploaded");
});

test("Sales sees Daily Sales Summary in the nav", async ({ page }) => {
  await page.goto(`/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  await page.fill("#login-name", "gsales");
  await page.fill("#password", "demo1234");
  await page.click("#login-form button[type=submit]");
  await expect(
    page.locator('#nav-links a[data-module="daily-sales-summary"]')
  ).toBeVisible();
});
