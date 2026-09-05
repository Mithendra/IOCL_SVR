"use strict";

const { test, expect } = require("@playwright/test");
const { apiBase } = require("./_helpers");

const SCREEN = `/screens/manage-users/index.html?apiBase=${encodeURIComponent(apiBase)}`;

async function login(page, user) {
  await page.goto(`/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  await page.fill("#login-name", user);
  await page.fill("#password", "demo1234");
  await page.click("#login-form button[type=submit]");
  await expect(page.locator("#nav-links .nav-item").first()).toBeVisible();
}

test("Sales has no Manage Users nav link", async ({ page }) => {
  await login(page, "gsales");
  await expect(page.locator('#nav-links a[data-module="manage-users"]')).toHaveCount(0);
});

test("Manager creates a user; login name is derived; reset link is emailed", async ({ page }) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);

  await page.fill("#u-name", "Tester Onenine");
  await expect(page.locator("#u-login")).toHaveValue("tonenine");
  await page.fill("#u-email", "tonenine@example.test");
  await page.selectOption("#u-role", "Sales");
  await page.click("#save-btn");
  await expect(page.locator("#form-status")).toContainText("User saved");

  const row = page.locator("#user-rows tr").filter({ hasText: "tonenine" });
  await expect(row).toContainText("Tester Onenine");
  await expect(row).toContainText("Sales");

  await row.getByRole("button", { name: "Reset Password" }).click();
  await expect(page.locator("#form-status")).toContainText("link emailed");
});
