"use strict";

const { test, expect } = require("@playwright/test");
const { apiBase } = require("./_helpers");

const SCREEN = `/screens/credit-remittance-master/index.html?apiBase=${encodeURIComponent(apiBase)}`;
const CREDITOR = "Playwright Creditor";

async function login(page, user) {
  await page.goto(`/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  await page.fill("#login-name", user);
  await page.fill("#password", "demo1234");
  await page.click("#login-form button[type=submit]");
  await expect(page.locator("#nav-links .nav-item").first()).toBeVisible();
}

test("Sales has no Credit / Remittance Master nav link", async ({ page }) => {
  await login(page, "gsales");
  await expect(
    page.locator('#nav-links a[data-module="credit-remittance-master"]')
  ).toHaveCount(0);
});

test("Manager adds a credit and a remittance; summary shows the outstanding balance", async ({ page }) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);

  await page.fill("#c-name", CREDITOR);
  await page.fill("#c-ltrs", "40");
  await page.fill("#c-rate", "125");
  await expect(page.locator("#c-amount")).toHaveValue("5000");
  await page.click("#add-credit");
  await expect(page.locator("#txn-status")).toContainText("Credit added");

  await page.fill("#r-name", CREDITOR);
  await page.fill("#r-amount", "2000");
  await page.click("#add-remittance");
  await expect(page.locator("#txn-status")).toContainText("Remittance added");

  const row = page.locator("#summary-rows tr").filter({ hasText: CREDITOR });
  await expect(row).toContainText("5000"); // total credit
  await expect(row).toContainText("2000"); // total remitted
  await expect(row.locator("td").nth(4)).toHaveText("3000"); // outstanding
});
