"use strict";
const { test, expect } = require("@playwright/test");
const { apiBase } = require("./_helpers");
const SCREEN = `/screens/daily-sales-entry/index.html?apiBase=${encodeURIComponent(apiBase)}`;

// Client, 2026-09-23: "Define a small owner form where you can reset the last
// reading for both pumps ... to open that form you need to have a secret
// password", and then: "it should prompt for a password when the respective pump
// is selected and a password is MUST."
//
// Driven through the real screen rather than the API, because the gate IS the
// screen: an endpoint that refuses a bad passphrase proves nothing if the form
// never asks for one.
test("owner reset form: set, open, apply, and the prefill changes", async ({ page }) => {
  const { request } = require("@playwright/test");
  const ctx = await request.newContext();
  const token = (await (await ctx.post(`${apiBase}/auth/login`,
    { data: { login_name: "mmanager", password: "demo1234" } })).json()).token;
  await ctx.post(`${apiBase}/daily-sales-entry`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { pump_serial: "12BC4523V-RD", shift_date: "2026-11-20",
            hs: { current: "111.11", last: "100" }, ms: { current: "222.22", last: "200" } },
  });
  await ctx.dispose();

  await page.goto(`/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  await page.fill("#login-name", "oowner");
  await page.fill("#password", "demo1234");
  await page.click("#login-form button[type=submit]");
  await expect(page.locator("#nav-links .nav-item").first()).toBeVisible();
  await page.goto(SCREEN);
  await page.selectOption("#pump-serial", "12BC4523V-RD");
  await page.fill("#shift-date", "2026-11-21");
  await expect(page.locator("#hs-last")).toHaveValue("111.11");

  await expect(page.locator("#reset-open-btn")).toBeVisible();
  await page.click("#reset-open-btn");
  await expect(page.locator("#reset-panel")).toBeVisible();

  // First use: no passphrase yet.
  await expect(page.locator("#reset-setup")).toBeVisible();
  await page.fill("#reset-new-pass", "owner-secret-123");
  await page.click("#reset-set-btn");
  await expect(page.locator("#reset-gate")).toBeVisible();

  // Wrong passphrase is refused.
  await page.fill("#reset-pass", "not-it");
  await page.click("#reset-unlock-btn");
  await expect(page.locator("#reset-status")).toContainText("passphrase", { ignoreCase: true });
  await expect(page.locator("#reset-body")).toBeHidden();

  // Right one opens it.
  await page.fill("#reset-pass", "owner-secret-123");
  await page.click("#reset-unlock-btn");
  await expect(page.locator("#reset-body")).toBeVisible();

  await page.fill("#reset-date", "2026-11-20");
  await page.fill("#reset-hs", "1489759.27");
  await page.fill("#reset-ms", "663546.17");
  await page.fill("#reset-reason", "meter re-based after testing");
  await page.click("#reset-apply-btn");
  await expect(page.locator("#reset-status")).toContainText("Saved");
  await expect(page.locator("#reset-history-rows")).toContainText("meter re-based after testing");

  // The form behind it now carries the corrected reading.
  await expect(page.locator("#hs-last")).toHaveValue("1489759.27");
});

test("a Manager never sees the owner reset controls", async ({ page }) => {
  await page.goto(`/index.html?apiBase=${encodeURIComponent(apiBase)}`);
  await page.fill("#login-name", "mmanager");
  await page.fill("#password", "demo1234");
  await page.click("#login-form button[type=submit]");
  await expect(page.locator("#nav-links .nav-item").first()).toBeVisible();
  await page.goto(SCREEN);
  await page.selectOption("#pump-serial", "12BC4523V-RD");
  await page.fill("#shift-date", "2026-11-21");
  await expect(page.locator("#reset-open-btn")).toBeHidden();
  await expect(page.locator("#unlock-last-btn")).toBeHidden();
});
