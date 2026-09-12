"use strict";

// The only bridge into the renderer. Exposes the backend base URL (from a
// --svr-api-base=... argument set in main.js) and nothing else.

const { contextBridge, ipcRenderer } = require("electron");

function readApiBase() {
  const arg = process.argv.find((a) => a.startsWith("--svr-api-base="));
  return arg ? arg.slice("--svr-api-base=".length) : "http://127.0.0.1:8756";
}

contextBridge.exposeInMainWorld("svr", {
  apiBase: readApiBase(),
  isElectron: true,
  // Renders the current page to an A4 PDF and opens it in a preview window.
  // Electron's bare window.print() shows no preview pane on Windows, so the
  // operator could not see page breaks before printing (client, 2026-09-11).
  printPreview: () => ipcRenderer.invoke("svr:print-preview"),
});
