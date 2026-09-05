"use strict";

const { test, expect, request } = require("@playwright/test");
const { apiBase } = require("./_helpers");

const SCREEN = `/screens/yearly-sales-report/index.html?apiBase=${encodeURIComponent(apiBase)}`;
const FY = 2031; // isolated from other specs' data

// Seed once per worker (not per test) so a retry does not double-count revenue.
test.beforeAll(async () => {
  const ctx = await request.newContext();
  const token = (
    await (await ctx.post(`${apiBase}/auth/login`, {
      data: { login_name: "gsales", password: "demo1234" },
    })).json()
  ).token;
  // A pump serial no other spec touches -> no carried Last Reading, consumption = 100.
  await ctx.post(`${apiBase}/daily-sales-entry`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { pump_serial: "99ZZ0000V-OFF", shift_date: `${FY}-06-01`, hs: { current: "100" } },
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

async function openReport(page, user) {
  await login(page, user);
  await page.goto(SCREEN);
  await page.fill("#fy-year", String(FY));
  await page.click("#gen-btn");
  await expect(page.locator("#fy-tag")).toHaveText(`FY ${FY}-${String(FY + 1).slice(-2)}`);
}

test("Sales has no Yearly Sales Report nav link", async ({ page }) => {
  await login(page, "gsales");
  await expect(page.locator('#nav-links a[data-module="yearly-sales-report"]')).toHaveCount(0);
});

test("Manager sees the FY report read-only with the CA disclaimer", async ({ page }) => {
  await openReport(page, "mmanager");
  await expect(page.locator("#disclaimer")).toContainText("not tax advice");
  // The seeded 100-litre Diesel entry produces some positive fuel revenue.
  expect(Number(await page.locator("#v-hs").textContent())).toBeGreaterThan(0);
  await expect(page.locator("#m-open")).toBeDisabled();
  await expect(page.locator("#save-figs-btn")).toBeHidden();
});

test("Owner sets COGS / commission and the summary recalculates", async ({ page }) => {
  await openReport(page, "oowner");
  await expect(page.locator("#save-figs-btn")).toBeVisible();

  const revenue = Number(await page.locator("#v-revenue").textContent());

  await page.fill("#m-open", "1000");
  await page.fill("#m-purch", "50000");
  await page.fill("#m-close", "3000");
  await page.fill("#m-hscomm", "8000");
  await page.click("#save-figs-btn");

  await expect(page.locator("#d-cogs")).toHaveText("48000"); // 1000 + 50000 - 3000
  await expect(page.locator("#d-comm")).toHaveText("8000");
  // Gross Profit = Revenue - COGS, whatever the live revenue turned out to be.
  await expect(page.locator("#d-gross")).toHaveText(String(Math.round((revenue - 48000) * 10000) / 10000));
});
