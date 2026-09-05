"use strict";

const { test, expect, request } = require("@playwright/test");
const { apiBase } = require("./_helpers");

const NEW_PW = "reset-flow-pw-1";

async function managerToken(ctx) {
  const res = await ctx.post(`${apiBase}/auth/login`, {
    data: { login_name: "mmanager", password: "demo1234" },
  });
  return (await res.json()).token;
}

test("Forgot-password on the login screen shows a non-committal confirmation", async ({ page }) => {
  await page.goto(`/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  page.once("dialog", (d) => d.accept("does-not-exist@nowhere.test"));
  await page.click("#forgot-link");
  await expect(page.locator("#forgot-status")).toContainText("If that account exists");
});

test("admin reset link -> set a new password -> the user can sign in", async ({ page }) => {
  const ctx = await request.newContext();
  const token = await managerToken(ctx);
  const headers = { Authorization: `Bearer ${token}` };

  const user = await (
    await ctx.post(`${apiBase}/users`, {
      headers,
      data: { full_name: "Reset Flow", email: "resetflow@example.test", role: "Sales" },
    })
  ).json();

  const reset = await (
    await ctx.post(`${apiBase}/users/${user.id}/reset-password`, { headers })
  ).json();
  expect(reset.dev_reset_link).toContain("/password-reset.html?token=");
  await ctx.dispose();

  // The emailed link opens the backend-served page in a plain browser.
  await page.goto(reset.dev_reset_link);
  await expect(page.locator("h1")).toHaveText("Set a New Password");
  await page.fill("#p1", NEW_PW);
  await page.fill("#p2", NEW_PW);
  await page.click("#btn");
  await expect(page.locator("#msg")).toContainText("Password updated");

  // The new user can now sign in from the app.
  await page.goto(`/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  await page.fill("#login-name", user.login_name);
  await page.fill("#password", NEW_PW);
  await page.click("#login-form button[type=submit]");
  await expect(page.locator("#nav-links .nav-item").first()).toBeVisible();
  await expect(page).toHaveURL(/daily-sales-entry/);
});
