"use strict";

const { test, expect } = require("@playwright/test");
const { apiBase } = require("./_helpers");

const SCREEN = `/screens/fuel-procurement/index.html?apiBase=${encodeURIComponent(apiBase)}`;

async function login(page, user) {
  await page.goto(`/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  await page.fill("#login-name", user);
  await page.fill("#password", "demo1234");
  await page.click("#login-form button[type=submit]");
  await expect(page.locator("#nav-links .nav-item").first()).toBeVisible();
}

test("Sales has no Fuel Procurement nav link", async ({ page }) => {
  await login(page, "gsales");
  await expect(page.locator('#nav-links a[data-module="fuel-procurement"]')).toHaveCount(0);
});

test("Manager adds a two-fuel load; Lost computes; Save, Post and the month summary all work", async ({
  page,
}) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);

  await page.fill("#f-date", "2026-09-29");
  await page.fill("#f-ref", "AP-16-TB-4519");
  await page.fill("#f-hs-load", "12000");
  await page.fill("#f-hs-recv", "11970");
  await page.fill("#f-hs-rate", "92.50");
  await page.fill("#f-ms-load", "8000");
  await page.fill("#f-ms-recv", "7982");
  await page.fill("#f-ms-rate", "101.60");

  // Lost computes live, before the load is even added.
  await expect(page.locator("#f-hs-lost")).toHaveValue("30");
  await expect(page.locator("#f-ms-lost")).toHaveValue("18");
  // HS 12000x92.50 + MS 8000x101.60 = 1,110,000 + 812,800 = 1,922,800
  await expect(page.locator("#f-total")).toHaveValue(/19,22,800\.00/);

  await page.click("#add-load-btn");
  await expect(page.locator("#form-status")).toContainText("Added 2 row(s)");

  await page.fill("#s-start", "2026-09-01");
  await page.fill("#s-end", "2026-09-30");
  await page.click("#search-btn");
  const rows = page.locator("#hist-rows tr");
  await expect(rows).toHaveCount(2);

  // Correct the HS row's Received count after a recount - Save, not Post.
  const hsRow = rows.filter({ hasText: "HS" }).first();
  await expect(hsRow).toContainText("30"); // Lost column, before the edit below
  await hsRow.locator(".row-recv").fill("11950");
  await hsRow.locator(".save-btn").click();
  await expect(page.locator("#hist-status")).toContainText("Saved");
  await expect(hsRow.locator(".row-recv")).toHaveValue("11950");

  // Post the MS row - it locks, and the badge flips.
  const msRow = rows.filter({ hasText: "MS" }).first();
  await msRow.locator(".post-btn").click();
  await expect(page.locator("#hist-status")).toContainText("Fuel Load - MS");
  await expect(msRow.locator(".cm-badge.dt")).toHaveText("Posted");
  await expect(msRow.locator(".row-load")).toBeDisabled();
  await expect(msRow.locator(".post-btn")).toHaveCount(0);

  // Confirm it actually landed in Monthly Expenses.
  await page.goto(`/screens/monthly-expenses/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  await page.fill("#f-start", "2026-09-29");
  await page.fill("#f-end", "2026-09-29");
  await page.click("#apply-filter");
  await expect(page.locator("#expense-rows")).toContainText("Fuel Load - MS");

  // Back to Fuel Procurement - the month summary reflects the full data on
  // file, not just the search range.
  await page.goto(SCREEN);
  await expect(page.locator("#month-rows")).toContainText("Sep 2026");
});

test("Export to Excel downloads an .xlsx of the filtered rows", async ({ page }) => {
  await login(page, "oowner");
  await page.goto(SCREEN);

  await page.fill("#f-date", "2026-09-14");
  await page.fill("#f-hs-load", "10000");
  await page.fill("#f-hs-recv", "9975");
  await page.fill("#f-hs-rate", "91.85");
  await page.click("#add-load-btn");
  await expect(page.locator("#form-status")).toContainText("Added");

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.click("#export-btn"),
  ]);
  expect(download.suggestedFilename()).toMatch(/^SVR-FuelProcurement.*\.xlsx$/);
});

test("Add & Post skips the draft step; Load Summary exports on its own", async ({ page }) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);

  await page.fill("#f-date", "2026-09-20");
  await page.fill("#f-hs-load", "10000");
  await page.fill("#f-hs-recv", "9980");
  await page.fill("#f-hs-rate", "92.10");
  await page.click("#add-post-load-btn");
  await expect(page.locator("#form-status")).toContainText("posted to Monthly Expenses");

  await page.fill("#s-start", "2026-09-01");
  await page.fill("#s-end", "2026-09-30");
  await page.click("#search-btn");
  const row = page.locator("#hist-rows tr").filter({ hasText: "2026-09-20" });
  await expect(row.locator(".cm-badge.dt")).toHaveText("Posted");
  await expect(row.locator(".post-btn")).toHaveCount(0);

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.click("#export-month-btn"),
  ]);
  expect(download.suggestedFilename()).toBe("SVR-FuelProcurement-MonthSummary.xlsx");
});
