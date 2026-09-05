"use strict";

const { test, expect } = require("@playwright/test");
const { apiBase } = require("./_helpers");

const SCREEN = `/screens/employee-master/index.html?apiBase=${encodeURIComponent(apiBase)}`;
const ACCT = "123456789012";

async function login(page, user) {
  await page.goto(`/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  await page.fill("#login-name", user);
  await page.fill("#password", "demo1234");
  await page.click("#login-form button[type=submit]");
  await expect(page.locator("#nav-links .nav-item").first()).toBeVisible();
}

test("Sales has no Employee Master nav link", async ({ page }) => {
  await login(page, "gsales");
  await expect(page.locator('#nav-links a[data-module="employee-master"]')).toHaveCount(0);
});

test("Manager adds an employee (bank data masked in list, revealed on edit) and runs payroll", async ({
  page,
}) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);

  await page.fill("#e-name", "Payroll Tester");
  await page.fill("#e-designation", "Attendant");
  await page.fill("#e-wage", "600");
  await page.fill("#e-bank", "Indian Bank");
  await page.fill("#e-account", ACCT);
  await page.fill("#e-ifsc", "IDIB000P123");
  await page.click("#save-btn");
  await expect(page.locator("#form-status")).toContainText("Employee saved");

  const row = page.locator("#emp-rows tr").filter({ hasText: "Payroll Tester" });
  const acctCell = row.locator("td").nth(4);
  await expect(acctCell).toContainText("9012");
  await expect(acctCell).not.toHaveText(ACCT); // masked in the list

  await row.getByRole("button", { name: "Edit" }).click();
  await expect(page.locator("#e-account")).toHaveValue(ACCT); // full value on edit

  // Run payroll for this employee: 12 days x 600 = 7200 gross.
  await page.fill("#pr-start", "2026-08-01");
  await page.fill("#pr-end", "2026-08-14");
  const prRow = page.locator("#pr-input-rows tr").filter({ hasText: "Payroll Tester" });
  await prRow.locator(".pr-days").fill("12");
  await prRow.locator(".pr-adv").fill("500");
  await page.click("#run-btn");

  await expect(page.locator("#run-status")).toContainText("recorded");
  await expect(page.locator("#r-net")).toContainText("6700"); // 7200 - 500
});
