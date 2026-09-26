"use strict";

const fs = require("fs");
const path = require("path");
const { test, expect, _electron: electron } = require("@playwright/test");
const { apiBase } = require("./_helpers");

test("Electron app launches and renders the shell", async () => {
  // Some shells export ELECTRON_RUN_AS_NODE=1, which makes electron.exe behave as
  // plain Node and reject Chromium flags ("bad option: --remote-debugging-port").
  // Strip it so the real Electron runtime starts.
  const env = { ...process.env, SVR_API_BASE: apiBase };
  delete env.ELECTRON_RUN_AS_NODE;

  const app = await electron.launch({
    args: [path.join(__dirname, "..", "src", "main", "main.js")],
    env,
  });
  const window = await app.firstWindow();
  await expect(window.locator("#login-view")).toBeVisible();
  await expect(window).toHaveTitle(/SVR/);

  // The preload bridge is the only thing exposed to the renderer.
  const base = await window.evaluate(() => window.svr && window.svr.apiBase);
  expect(base).toBe(apiBase);

  await app.close();
});

// The whole Trial Balance leaves the station as a PDF document (client,
// 2026-09-24), and printToPDF only exists in the real Electron main process -
// page mode can only ever prove the button says so. This proves a file with PDF
// bytes in it actually lands on disk.
test("the whole sheet really renders to a PDF file", async () => {
  const env = { ...process.env, SVR_API_BASE: apiBase };
  delete env.ELECTRON_RUN_AS_NODE;

  const app = await electron.launch({
    args: [path.join(__dirname, "..", "src", "main", "main.js")],
    env,
  });
  const window = await app.firstWindow();
  await expect(window.locator("#login-view")).toBeVisible();

  const name = `SVR-TrialBalance-smoke-${Date.now()}`;
  const out = await window.evaluate(
    (fileName) => window.svr.savePdf({ fileName, landscape: true, open: false }),
    name
  );
  expect(out.file).toContain(name);
  const bytes = fs.readFileSync(out.file);
  expect(bytes.subarray(0, 5).toString()).toBe("%PDF-");
  expect(bytes.length).toBeGreaterThan(1000);
  if (!process.env.SVR_KEEP_PDF) fs.unlinkSync(out.file); else console.log("KEPT:" + out.file);

  await app.close();
});

// And the real thing: signed in, on the Trial Balance, with a day loaded. The
// mechanism test above renders the login screen; this one renders the sheet
// that actually goes to management, and checks the page it lands on is A4
// LANDSCAPE - app.css pins @page to A4 portrait for the printed DSR form, which
// is right there and would slice this sheet down the middle.
test("the Trial Balance renders to an A4 landscape PDF, signed in", async () => {
  const env = { ...process.env, SVR_API_BASE: apiBase };
  delete env.ELECTRON_RUN_AS_NODE;

  const app = await electron.launch({
    args: [path.join(__dirname, "..", "src", "main", "main.js")],
    env,
  });
  const window = await app.firstWindow();
  await window.waitForSelector("#login-view");
  await window.fill("#login-name", "mmanager");
  await window.fill("#password", "demo1234");
  await window.click("#login-form button[type=submit]");
  await window.waitForSelector("#nav-links .nav-item", { timeout: 20000 });
  await window.evaluate(() => {
    window.location.href = "../../screens/daily-trial-balance/index.html";
  });
  await window.waitForSelector("#body", { state: "visible", timeout: 20000 });
  // A date other specs have already saved, so the sheet has figures on it.
  await window.fill("#tb-date", "2026-10-25");
  await window.click("#load-btn");
  await expect(window.locator("#status-tag")).toBeVisible();

  const name = `SVR-TrialBalance-e2e-${Date.now()}`;
  // Exactly what the button does - MIRROR exportSheetPdf() in the Trial Balance
  // screen, including both body classes and the injected @page rule.
  //
  // "pdf-export" hides the on-screen controls; "print-color" is what keeps the
  // form's colours, because the paper-form print rules flatten everything to
  // black and white. This test carried only the first for a while and so
  // produced a black-and-white PDF while the real button produced a colour one -
  // it was testing a path the app does not take.
  const out = await window.evaluate((fileName) => {
    document.body.classList.add("pdf-export", "print-color");
    const rule = document.createElement("style");
    rule.textContent = "@page { size: A4 landscape; margin: 8mm; }";
    document.head.appendChild(rule);
    return window.svr
      .savePdf({ fileName, landscape: true, cssPageSize: true, open: false })
      .finally(() => rule.remove());
  }, name);

  const raw = fs.readFileSync(out.file);
  expect(raw.subarray(0, 5).toString()).toBe("%PDF-");
  const box = /\/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)/.exec(raw.toString("latin1"));
  expect(box).not.toBeNull();
  const [w, h] = [Number(box[1]), Number(box[2])];
  expect(w).toBeGreaterThan(h);                 // landscape, not the form's portrait
  expect(Math.round(w)).toBe(842);              // A4 long edge, 841.89pt
  expect(Math.round(h)).toBe(595);              // A4 short edge, 595.28pt
  if (!process.env.SVR_KEEP_PDF) fs.unlinkSync(out.file); else console.log("KEPT:" + out.file);

  await app.close();
});
