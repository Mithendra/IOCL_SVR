"use strict";

const { test, expect } = require("@playwright/test");
const { apiBase } = require("./_helpers");

const SCREEN = `/screens/monthly-expenses/index.html?apiBase=${encodeURIComponent(apiBase)}`;

async function login(page, user) {
  await page.goto(`/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  await page.fill("#login-name", user);
  await page.fill("#password", "demo1234");
  await page.click("#login-form button[type=submit]");
  await expect(page.locator("#nav-links .nav-item").first()).toBeVisible();
}

test("Sales has no Monthly Expenses nav link", async ({ page }) => {
  await login(page, "gsales");
  await expect(page.locator('#nav-links a[data-module="monthly-expenses"]')).toHaveCount(0);
});

test("Manager adds payroll + operational expenses; summary subtotals and date filter work", async ({
  page,
}) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);

  // Operational expense on 2026-04-05.
  await page.fill("#e-date", "2026-04-05");
  await page.selectOption("#e-category", { label: "Ops — Power Bill" });
  await page.fill("#e-amount", "1200");
  await page.click("#add-expense");
  await expect(page.locator("#form-status")).toContainText("Expense added");

  // Payroll expense on 2026-04-20.
  await page.fill("#e-date", "2026-04-20");
  await page.selectOption("#e-category", { label: "Payroll — Bi-weekly Salary" });
  await page.fill("#e-amount", "9000");
  await page.click("#add-expense");

  // Filter to the whole of April 2026 -> both show, subtotals correct.
  await page.fill("#f-start", "2026-04-01");
  await page.fill("#f-end", "2026-04-30");
  await page.click("#apply-filter");
  await expect(page.locator("#expense-rows tr")).toHaveCount(2);
  await expect(page.locator("#s-ops")).toHaveText("1200");
  await expect(page.locator("#s-payroll")).toHaveText("9000");
  await expect(page.locator("#s-grand")).toHaveText("10200");

  // Narrow to the first half of April -> only the operational one.
  await page.fill("#f-end", "2026-04-10");
  await page.click("#apply-filter");
  await expect(page.locator("#expense-rows tr")).toHaveCount(1);
  await expect(page.locator("#expense-rows tr").first()).toContainText("Power Bill");
});
