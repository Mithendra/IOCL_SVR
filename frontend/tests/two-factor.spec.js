"use strict";

const { test, expect, request } = require("@playwright/test");
const { apiBase, totpCode } = require("./_helpers");

const LOGIN = `/index.html?apiBase=${encodeURIComponent(apiBase)}`;
const SECURITY = `/screens/security/index.html?apiBase=${encodeURIComponent(apiBase)}`;
const USERS = `/screens/manage-users/index.html?apiBase=${encodeURIComponent(apiBase)}`;

async function ctxFor(login) {
  const ctx = await request.newContext();
  const res = await ctx.post(`${apiBase}/auth/login`, {
    data: { login_name: login, password: "demo1234" },
  });
  const body = await res.json();
  return { ctx, token: body.token, hdr: { Authorization: `Bearer ${body.token}` } };
}

// Enable 2FA for `login` via the API; returns the secret. Also used to clean up.
async function enable2fa(login) {
  const { ctx, hdr } = await ctxFor(login);
  const setup = await (await ctx.post(`${apiBase}/auth/2fa/setup`, { headers: hdr })).json();
  const act = await ctx.post(`${apiBase}/auth/2fa/activate`, {
    headers: hdr,
    data: { code: totpCode(setup.secret) },
  });
  expect(act.status()).toBe(204);
  await ctx.dispose();
  return setup.secret;
}

async function clearGsales2fa() {
  const { ctx, hdr } = await ctxFor("oowner");
  const users = await (await ctx.get(`${apiBase}/users`, { headers: hdr })).json();
  const g = users.find((u) => u.login_name === "gsales");
  if (g && g.totp_enabled) {
    await ctx.put(`${apiBase}/users/${g.id}`, { headers: hdr, data: { totp_enabled: false } });
  }
  await ctx.dispose();
}

test.afterEach(clearGsales2fa);

test("a 2FA account is prompted for a code after the password step", async ({ page }) => {
  const secret = await enable2fa("gsales");

  await page.goto(LOGIN);
  await page.fill("#login-name", "gsales");
  await page.fill("#password", "demo1234");
  await page.click("#login-form button[type=submit]");

  // password form gives way to the code form
  await expect(page.locator("#totp-form")).toBeVisible();
  await expect(page.locator("#login-form")).toBeHidden();

  await page.fill("#totp-code", "000000");
  await page.click("#totp-form button[type=submit]");
  await expect(page.locator("#totp-error")).toContainText(/wrong or expired/i);

  await page.fill("#totp-code", totpCode(secret));
  await page.click("#totp-form button[type=submit]");
  await expect(page.locator("#nav-links .nav-item").first()).toBeVisible();
});

test("Security screen: self-enroll then turn 2FA off", async ({ page }) => {
  await page.goto(LOGIN);
  await page.fill("#login-name", "gsales");
  await page.fill("#password", "demo1234");
  await page.click("#login-form button[type=submit]");
  await expect(page.locator("#nav-links .nav-item").first()).toBeVisible();

  await page.goto(SECURITY);
  await expect(page.locator("#state")).toHaveText("off");
  await page.click("#start-btn");
  await expect(page.locator("#panel-setup")).toBeVisible();
  await expect(page.locator("#secret")).not.toBeEmpty();
  const secret = (await page.locator("#secret").textContent()).trim();

  await page.fill("#activate-code", totpCode(secret));
  await page.click("#activate-btn");
  await expect(page.locator("#sec-status")).not.toHaveClass(/err/);
  await expect(page.locator("#state")).toHaveText("on");

  await page.fill("#disable-code", totpCode(secret));
  await page.click("#disable-btn");
  await expect(page.locator("#state")).toHaveText("off");
});

test("Manage Users: an admin can Clear 2FA for a locked-out user", async ({ page }) => {
  await enable2fa("gsales");
  page.on("dialog", (d) => d.accept());

  await page.goto(LOGIN);
  await page.fill("#login-name", "mmanager");
  await page.fill("#password", "demo1234");
  await page.click("#login-form button[type=submit]");
  await expect(page.locator("#nav-links .nav-item").first()).toBeVisible();

  await page.goto(USERS);
  const row = page.locator("#user-rows tr", { hasText: "gsales" });
  await expect(row).toContainText("On");
  await row.getByRole("button", { name: "Clear 2FA" }).click();
  await expect(page.locator("#form-status")).toContainText("2FA cleared");

  // gsales now logs in with just a password
  const res = await (await request.newContext()).post(`${apiBase}/auth/login`, {
    data: { login_name: "gsales", password: "demo1234" },
  });
  expect((await res.json()).totp_required).toBeFalsy();
});
