"use strict";

const { test, expect, request } = require("@playwright/test");
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

test("Manager records accidental + health insurance; section 5 summary totals up", async ({ page }) => {
  // The e2e DB is shared and this suite has retries: 1 - start from a clean
  // insurance table so exact totals are deterministic.
  const ctx = await request.newContext();
  const token = (
    await (
      await ctx.post(`${apiBase}/auth/login`, {
        data: { login_name: "mmanager", password: "demo1234" },
      })
    ).json()
  ).token;
  const hdr = { Authorization: `Bearer ${token}` };
  for (const r of await (await ctx.get(`${apiBase}/employee-insurance`, { headers: hdr })).json()) {
    await ctx.delete(`${apiBase}/employee-insurance/${r.id}`, { headers: hdr });
  }
  await ctx.dispose();

  await login(page, "mmanager");
  await page.goto(SCREEN);

  await page.fill("#acc-name", "Insurance Tester");
  await page.fill("#acc-provider", "New India Assurance");
  await page.fill("#acc-policy", "ACC-77");
  await page.fill("#acc-premium", "1800");
  await page.click('[data-ins-add="accidental"]');
  await expect(page.locator("#acc-rows tr").filter({ hasText: "Insurance Tester" })).toContainText("1800");

  await page.fill("#hea-name", "Insurance Tester");
  await page.fill("#hea-provider", "Star Health");
  await page.fill("#hea-premium", "3200");
  await page.click('[data-ins-add="health"]');
  await expect(page.locator("#hea-rows tr").filter({ hasText: "Star Health" })).toContainText("3200");

  await expect(page.locator("#ins-acc-total")).toHaveText("1800");
  await expect(page.locator("#ins-hea-total")).toHaveText("3200");
  await expect(page.locator("#ins-grand")).toHaveText("5000");

  // delete the accidental row -> summary drops
  await page
    .locator("#acc-rows tr")
    .filter({ hasText: "Insurance Tester" })
    .getByRole("button", { name: "Delete" })
    .click();
  await expect(page.locator("#ins-acc-total")).toHaveText("0");
  await expect(page.locator("#ins-grand")).toHaveText("3200");
});
