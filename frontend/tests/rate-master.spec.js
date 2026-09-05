"use strict";

const { test, expect } = require("@playwright/test");
const { apiBase } = require("./_helpers");

const SCREEN = `/screens/rate-master/index.html?apiBase=${encodeURIComponent(apiBase)}`;

async function login(page, user) {
  await page.goto(`/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  await page.fill("#login-name", user);
  await page.fill("#password", "demo1234");
  await page.click("#login-form button[type=submit]");
  await expect(page.locator("#nav-links .nav-item").first()).toBeVisible();
}

test("Sales has no Rate Master nav link", async ({ page }) => {
  await login(page, "gsales");
  await expect(page.locator('#nav-links a[data-module="rate-master"]')).toHaveCount(0);
});

test("Manager sees Rate Master read-only", async ({ page }) => {
  await login(page, "mmanager");
  await page.goto(SCREEN);
  await expect(page.locator("#role-tag")).toHaveText("View Only");
  await expect(page.locator("#push-btn")).toBeHidden();
  await expect(page.locator("#rate-rows tr")).not.toHaveCount(0);
  await expect(page.locator("#history-rows tr")).not.toHaveCount(0);
  await expect(page.locator("#rate-rows tr").first().locator(".new-sell")).toBeDisabled();
});

test("Owner pushes a new HS sell rate and it lands in the history log", async ({ page }) => {
  await login(page, "oowner");
  await page.goto(SCREEN);
  await expect(page.locator("#push-btn")).toBeVisible();

  const hsRow = page.locator('#rate-rows tr[data-item-key="HS"]');
  await hsRow.locator(".new-sell").fill("111.11");
  await page.click("#push-btn");

  await expect(page.locator("#push-status")).toContainText("Pushed 1");
  // Newest history row is HS -> 111.11.
  const firstHist = page.locator("#history-rows tr").first();
  await expect(firstHist).toContainText("111.11");
});
