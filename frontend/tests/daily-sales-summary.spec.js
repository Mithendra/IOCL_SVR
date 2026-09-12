"use strict";

const { test, expect, request } = require("@playwright/test");
const { apiBase } = require("./_helpers");

const DATE = "2026-07-15";
const OFF = "11CC2012V-OFF"; // office pump (client-confirmed serial swap, 2026-09-11)
const ROAD = "12BC4523V-RD"; // road pump
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

test("each side is tagged with its own pump serial, and the pairing is checked", async ({
  page,
}) => {
  await seedEntries();
  await loginManager(page);
  await page.goto(SCREEN);
  await page.fill("#shift-date", DATE);
  await page.locator("#shift-date").dispatchEvent("change");

  // The mockups had these two the wrong way round for months (Office labelled
  // 12BC4523V-Off, Road labelled 11CC2012V-Road). Office is 11CC2012V-OFF.
  await expect(page.locator(".section-title").nth(0)).toContainText(`Office Pump (${OFF})`);
  await expect(page.locator(".section-title").nth(1)).toContainText(`Road Pump (${ROAD})`);
  await expect(page.locator("#off-serial")).toHaveValue(OFF);
  await expect(page.locator("#road-serial")).toHaveValue(ROAD);

  await expect(page.locator("#serial-check")).toHaveClass(/ok/);
  await expect(page.locator("#serial-check")).toContainText(`Office = ${OFF}`);
  await expect(page.locator("#serial-check")).toContainText(`Road = ${ROAD}`);

  // The combined table carries the seven oil rows and both closing totals, and
  // every figure reads to two decimals.
  const labels = await page.locator("#combined-rows tr td:first-child").allTextContents();
  expect(labels).toContain("Gas Total Amt");
  expect(labels).toContain("Battery Water Total 1 Lts");
  expect(labels).toContain("20/40 Engine Total in 05. Lts");
  expect(labels).toContain("Total Amt Oil(s)");
  await expect(page.locator("#comb-grand")).toHaveValue(/^-?\d+\.\d{2}$/);
});

test("names which pump's Daily Sales Entry is missing", async ({ page }) => {
  const DATE2 = "2026-07-16"; // isolated - only the Office pump submits here
  const ctx = await request.newContext();
  const token = (
    await (await ctx.post(`${apiBase}/auth/login`, {
      data: { login_name: "gsales", password: "demo1234" },
    })).json()
  ).token;
  await ctx.post(`${apiBase}/daily-sales-entry`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { pump_serial: OFF, shift_date: DATE2, hs: { current: "500" } },
  });
  await ctx.dispose();

  await loginManager(page);
  await page.goto(SCREEN);
  await page.fill("#shift-date", DATE2);
  await page.locator("#shift-date").dispatchEvent("change");

  await expect(page.locator("#gate-status")).toContainText("Road pump");
  await expect(page.locator("#gate-status")).not.toContainText("Office pump");
  await expect(page.locator("#upload-btn")).toBeDisabled();
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
