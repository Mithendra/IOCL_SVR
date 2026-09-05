"use strict";

const { test, expect, request } = require("@playwright/test");
const { apiBase } = require("./_helpers");

const SCREEN = `/screens/daily-sales-entry/index.html?apiBase=${encodeURIComponent(apiBase)}`;

async function login(page) {
  await page.goto(`/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  await page.fill("#login-name", "gsales");
  await page.fill("#password", "demo1234");
  await page.click("#login-form button[type=submit]");
  await expect(page.locator("#nav-links .nav-item").first()).toBeVisible();
}

test("Sales user reaches Daily Sales Entry from the nav", async ({ page }) => {
  await login(page);
  const link = page.locator('#nav-links a[data-module="daily-sales-entry"]');
  await expect(link).toBeVisible();
  // Sales must not see Manager/Owner modules.
  await expect(page.locator("#nav-links")).not.toContainText("Rate Master");
  await link.click();
  await expect(page.locator(".section-title").first()).toContainText("Gas Sale(s)");
});

test("prefill fills the locked Last Shift Reading and Rate fields", async ({ page }) => {
  await login(page);
  await page.goto(SCREEN);
  await expect(page.locator("#hs-rate")).toHaveValue("105.36");
  await expect(page.locator("#ms-rate")).toHaveValue("117.7");
  await expect(page.locator("#hs-last")).toBeDisabled();
  await expect(page.locator("#hs-rate")).toBeDisabled();
});

test("typing Current Reading updates Amount via the backend /calc", async ({ page }) => {
  await login(page);
  await page.goto(SCREEN);
  await page.fill("#hs-current", "1317.52");
  // 1317.52 x 105.36, minus whatever Last Shift Reading prefill supplied.
  await expect(page.locator("#hs-cons")).not.toHaveValue("");
  await expect(page.locator("#hs-amount")).not.toHaveValue("");
  const amount = Number(await page.locator("#hs-amount").inputValue());
  const cons = Number(await page.locator("#hs-cons").inputValue());
  expect(amount).toBeCloseTo(cons * 105.36, 2);
});

test("Save persists the entry and stamps last-updated-by", async ({ page }) => {
  await login(page);
  await page.goto(SCREEN);
  await page.fill("#hs-current", "1317.52");
  await page.fill("#exp1", "500+100=600");
  await page.click("#save-btn");

  await expect(page.locator("#save-status")).toContainText("Saved (entry #");
  await expect(page.locator("#last-updated-by")).toHaveText("gsales");

  // Confirm the row is really in the backend.
  const ctx = await request.newContext();
  const loginRes = await ctx.post(`${apiBase}/auth/login`, {
    data: { login_name: "gsales", password: "demo1234" },
  });
  const token = (await loginRes.json()).token;
  const list = await ctx.get(`${apiBase}/daily-sales-entry?pump_serial=12BC4523V-OFF`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const rows = await list.json();
  expect(rows.length).toBeGreaterThan(0);
  expect(rows[0].sell_rate_hs).toBe(105.36);
  await ctx.dispose();
});

test("theme swatch changes --io-accent; language toggle switches headings", async ({ page }) => {
  await login(page);
  await page.goto(SCREEN);

  await page.click('.theme-toggle button[data-accent="blue"]');
  const accent = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue("--io-accent").trim()
  );
  expect(accent.toLowerCase()).toBe("#0033a0");

  await page.click('.lang-toggle button[data-lang="te"]');
  await expect(page.locator(".section-title").first()).toContainText("గ్యాస్ అమ్మకాలు");
});

test("OCR / Import buttons surface a 'not yet available' message", async ({ page }) => {
  await login(page);
  await page.goto(SCREEN);
  await page.click("#scan-btn");
  await expect(page.locator("#save-status")).toContainText("not yet available");
});
