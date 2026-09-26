"use strict";

// SVR-IOCL Frontend - Electron main process. One window, loads the renderer shell.
// The backend base URL is passed to the renderer through the context-isolated
// preload bridge; the renderer never gets Node access (SDD 4.3 / 6).
//
// On a deployed machine the backend runs as the SVR-IOCL-Backend Windows Service,
// so /health answers immediately. If it does not (service still starting, or
// stopped), and this is a packaged build, fall back to spawning the bundled
// resources/backend/svr-backend.exe. In dev (`npm start`) there is no bundled exe;
// a dev backend on :8756 is assumed and the renderer loads regardless.

const { app, BrowserWindow, Menu, clipboard, ipcMain, shell } = require("electron");
const path = require("path");
const http = require("http");
const fs = require("fs");
const os = require("os");
const { spawn } = require("child_process");

const API_BASE = process.env.SVR_API_BASE || "http://127.0.0.1:8756";
const HEALTH_URL = `${API_BASE}/health`;
const STARTUP_TIMEOUT_MS = 20000;
const POLL_INTERVAL_MS = 500;

let backendProc = null;

function pingHealth() {
  return new Promise((resolve) => {
    const req = http.get(HEALTH_URL, { timeout: 2000 }, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on("error", () => resolve(false));
    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });
  });
}

function bundledBackendExe() {
  // Packaged layout: <app>/resources/backend/svr-backend.exe (extraResources).
  const exe = path.join(process.resourcesPath, "backend", "svr-backend.exe");
  return fs.existsSync(exe) ? exe : null;
}

function startBundledBackend() {
  const exe = bundledBackendExe();
  if (!exe || backendProc) return;
  backendProc = spawn(exe, ["serve"], { stdio: "ignore", windowsHide: true });
  backendProc.on("exit", () => {
    backendProc = null;
  });
}

function stopBundledBackend() {
  if (!backendProc) return;
  try {
    backendProc.kill();
  } catch {
    // process already gone
  }
  backendProc = null;
}

async function waitForBackend() {
  const deadline = Date.now() + STARTUP_TIMEOUT_MS;
  let triedSpawn = false;
  while (Date.now() < deadline) {
    if (await pingHealth()) return true;
    if (!triedSpawn) {
      triedSpawn = true;
      startBundledBackend(); // no-op in dev / when already running
    }
    await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
  }
  return pingHealth();
}

const SPLASH_HTML = `<!doctype html><meta charset="utf-8">
<style>
  html,body{height:100%;margin:0}
  body{display:flex;align-items:center;justify-content:center;
       font:14px 'Segoe UI',Arial,sans-serif;background:#f4f6fb;color:#00246e}
  .box{text-align:center}
  .dot{display:inline-block;width:8px;height:8px;margin:0 2px;border-radius:50%;
       background:#0033a0;animation:b 1s infinite alternate}
  .dot:nth-child(2){animation-delay:.2s}.dot:nth-child(3){animation-delay:.4s}
  @keyframes b{to{opacity:.2}}
</style>
<div class="box">
  <div style="font-weight:700;margin-bottom:10px">SVR IOCL Station</div>
  <div>Starting&nbsp;<span class="dot"></span><span class="dot"></span><span class="dot"></span></div>
</div>`;

// Print preview. Electron's bare window.print() goes straight to the Windows
// print dialog with no preview pane, and a form printed blind is a form printed
// wrong - the client reported both no preview and a one-page report spilling
// over three pages (2026-09-11). Rendering to an A4 PDF first and opening it in
// a window gives a true preview of the page breaks, and Chromium's built-in PDF
// viewer supplies Print and Save buttons for free.
async function showPrintPreview(sourceWebContents, fileName) {
  const pdf = await sourceWebContents.printToPDF({
    pageSize: "A4",
    landscape: false,
    printBackground: true,
    preferCSSPageSize: true, // honour the @page rule in app.css
  });
  // The station files these by pump and date, so the file is named the way they
  // name them: SVR_DSR_<serial>_<date>.pdf (client, 2026-09-23). A timestamp
  // tells whoever opens the Downloads folder nothing at all.
  const safe = String(fileName || "").replace(/[^A-Za-z0-9._-]/g, "");
  const file = path.join(os.tmpdir(), safe ? `${safe}.pdf` : `svr-print-${Date.now()}.pdf`);
  await fs.promises.writeFile(file, pdf);

  const preview = new BrowserWindow({
    width: 900,
    height: 1100,
    title: "Print preview — SVR IOCL Station",
    autoHideMenuBar: true,
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  });
  await preview.loadURL(`file://${file.replace(/\\/g, "/")}`);
  preview.on("closed", () => {
    fs.promises.unlink(file).catch(() => {}); // best-effort temp cleanup
  });
  return true;
}

// Section 8 snapshot for WhatsApp.
//
// The station has no WhatsApp Business account and will not be getting one, so
// nothing can post a message programmatically. What actually happens is: someone
// opens WhatsApp on the PC or the phone and sends it (client, 2026-09-12). The
// thing management wants is the Section 8 block as it looks on screen - colours
// and all - not a spreadsheet they have to open on a phone.
//
// So: capture that block as a PNG, put it straight on the CLIPBOARD, and also
// drop a copy on disk. In WhatsApp it is then one Ctrl+V. That is as close to a
// one-button send as is possible without an API, and nothing about it pretends
// to have sent anything.
//
// capturePage() is used rather than an HTML-to-canvas library because it takes
// the real rendered pixels - the snapshot cannot drift from what the operator is
// looking at, which is the whole point of sending a picture of it.
async function captureSection(sourceWebContents, rect) {
  const round = (n) => Math.max(0, Math.round(n));
  const image = await sourceWebContents.capturePage({
    x: round(rect.x),
    y: round(rect.y),
    width: round(rect.width),
    height: round(rect.height),
  });
  if (image.isEmpty()) throw new Error("Nothing to capture - scroll Section 8 into view first.");

  clipboard.writeImage(image);
  const file = path.join(
    app.getPath("downloads"),
    `SVR-Section8-${rect.label || "snapshot"}.png`
  );
  await fs.promises.writeFile(file, image.toPNG());
  return { file, copied: true };
}

// When the renderer files on disk were last changed.
//
// Three rounds of testing were spent on changes that were already live, because
// a screenshot of a window opened before a restart is indistinguishable from a
// screenshot of a fix that did not work. There is now a stamp on every screen:
// if it does not match what was just built, the window is stale - reload it.
//
// Taken from the newest mtime under src/renderer, so it moves whenever anything
// the operator can see changes, without a build step to remember.
function rendererBuildStamp() {
  const root = path.join(__dirname, "..", "renderer");
  let newest = 0;
  const walk = (dir) => {
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      const full = path.join(dir, e.name);
      if (e.isDirectory()) {
        walk(full);
      } else {
        try {
          const m = fs.statSync(full).mtimeMs;
          if (m > newest) newest = m;
        } catch {
          /* a file that vanished mid-walk is not a build stamp problem */
        }
      }
    }
  };
  walk(root);
  if (!newest) return "";
  const d = new Date(newest);
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getDate())} ${d.toLocaleString("en-GB", { month: "short" })} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

ipcMain.handle("svr:build-stamp", () => rendererBuildStamp());

// The whole sheet as a PDF, saved where it can be attached.
//
// It used to be a clipboard PNG, the same route as the Section 8 snapshot, and
// that is right for Section 8 - a short block someone pastes into a chat. It is
// wrong for the whole Trial Balance: it is a long, wide sheet, the PNG came out
// as one enormous strip that WhatsApp re-compresses into something unreadable,
// and a clipboard image cannot be forwarded, filed or opened again later. The
// client asked for a document instead (2026-09-24), and a PDF is what a phone
// opens without anything installed.
//
// Orientation is settled by CSS, not by this option.
//
// app.css pins `@page { size: A4 portrait }` for the DSR form - correct there,
// and it would slice this sheet down the middle. Passing landscape:true here
// with preferCSSPageSize:false was NOT enough: Chromium still laid the page out
// portrait (measured - the MediaBox came back 595.92 x 842.88). So the caller
// injects a later, winning `@page { size: A4 landscape }` rule for the duration
// of the export and asks for cssPageSize, which is what actually turns the
// page. `landscape` is still passed for the non-CSS path.
async function saveSheetPdf(sourceWebContents, opts) {
  const o = opts || {};
  const pdf = await sourceWebContents.printToPDF({
    pageSize: "A4",
    landscape: o.landscape !== false,
    printBackground: true,
    preferCSSPageSize: o.cssPageSize === true,
    margins: { top: 0.2, bottom: 0.2, left: 0.2, right: 0.2 },
  });
  const safe = String(o.fileName || "").replace(/[^A-Za-z0-9._-]/g, "");
  const file = path.join(
    app.getPath("downloads"),
    `${safe || `SVR-Sheet-${Date.now()}`}.pdf`
  );
  await fs.promises.writeFile(file, pdf);
  // Open it so the operator sees what they are about to send before they send
  // it; the file stays on disk either way, unlike the print preview's temp copy.
  // `open: false` is for the smoke test, which checks the bytes on disk and has
  // no business launching the machine's PDF viewer.
  if (o.open !== false) shell.openPath(file).catch(() => {});
  return { file };
}

ipcMain.handle("svr:save-pdf", (event, opts) =>
  saveSheetPdf(event.sender, opts || {}).catch((err) => {
    throw new Error(err && err.message ? err.message : String(err));
  })
);

ipcMain.handle("svr:capture-section", (event, rect) =>
  captureSection(event.sender, rect || {}).catch((err) => {
    throw new Error(err && err.message ? err.message : String(err));
  })
);

ipcMain.handle("svr:print-preview", (event, fileName) =>
  showPrintPreview(event.sender, fileName).catch((err) => {
    // Surfaced to the renderer as a rejected promise so the screen can show it
    // in its own status line rather than failing silently.
    throw new Error(`Print preview failed: ${err.message}`);
  })
);

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 900,
    title: "SVR IOCL Station",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      additionalArguments: [`--svr-api-base=${API_BASE}`],
    },
  });

  Menu.setApplicationMenu(
    Menu.buildFromTemplate([
      { role: "fileMenu" },
      { role: "editMenu" },
      { role: "viewMenu" },
      { role: "windowMenu" },
    ])
  );

  win.loadURL("data:text/html;charset=utf-8," + encodeURIComponent(SPLASH_HTML));

  waitForBackend().then(() => {
    // Load the app either way - if the backend never came up the renderer shows
    // its own connection error, which is clearer than a blank splash.
    if (!win.isDestroyed()) {
      win.loadFile(path.join(__dirname, "..", "renderer", "index.html"));
    }
  });

  return win;
}

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  stopBundledBackend();
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", stopBundledBackend);
