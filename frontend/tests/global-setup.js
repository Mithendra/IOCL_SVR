"use strict";

// Boots a throwaway backend (seeded SQLite + svr-backend) and a static file server
// for the renderer, then returns a teardown function. Playwright runs the returned
// function after the whole suite.

const { execFileSync, spawn } = require("child_process");
const fs = require("fs");
const http = require("http");
const path = require("path");

const { BACKEND_PORT, STATIC_PORT, RENDERER_DIR, REPO_ROOT, backendExe } = require("./_helpers");

const WORK_DIR = path.join(__dirname, "..", "test-results", "backend");
const DB_PATH = path.join(WORK_DIR, "e2e.sqlite");

const MIME = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
};

function waitForHttp(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    const tick = () => {
      const req = http.get(url, (res) => {
        res.resume();
        if (res.statusCode && res.statusCode < 500) return resolve();
        retry();
      });
      req.on("error", retry);
      req.setTimeout(1000, () => req.destroy());
    };
    const retry = () => {
      if (Date.now() > deadline) return reject(new Error(`timed out waiting for ${url}`));
      setTimeout(tick, 300);
    };
    tick();
  });
}

function startStaticServer() {
  const server = http.createServer((req, res) => {
    const urlPath = decodeURIComponent((req.url || "/").split("?")[0]);
    const rel = urlPath === "/" ? "/index.html" : urlPath;
    const filePath = path.join(RENDERER_DIR, path.normalize(rel));
    if (!filePath.startsWith(RENDERER_DIR)) {
      res.writeHead(403).end("forbidden");
      return;
    }
    fs.readFile(filePath, (err, buf) => {
      if (err) {
        res.writeHead(404).end("not found");
        return;
      }
      res.writeHead(200, { "Content-Type": MIME[path.extname(filePath)] || "application/octet-stream" });
      res.end(buf);
    });
  });
  return new Promise((resolve) => server.listen(STATIC_PORT, "127.0.0.1", () => resolve(server)));
}

module.exports = async () => {
  fs.rmSync(WORK_DIR, { recursive: true, force: true });
  fs.mkdirSync(WORK_DIR, { recursive: true });

  const env = {
    ...process.env,
    SVR_DB_PATH: DB_PATH,
    SVR_API_PORT: String(BACKEND_PORT),
    // the reset link must point at a URL a browser can open - the backend serves
    // /password-reset.html itself
    SVR_APP_BASE_URL: `http://127.0.0.1:${BACKEND_PORT}`,
  };

  // Point the test backend at the bundled Tesseract if it has been staged
  // (installer/fetch-tesseract.ps1). Absent -> the OCR spec skips its live case.
  const tess = path.join(REPO_ROOT, "installer", "vendor", "tesseract", "tesseract.exe");
  if (fs.existsSync(tess)) {
    env.SVR_TESSERACT_CMD = tess;
    env.SVR_TESSDATA_PREFIX = path.join(REPO_ROOT, "installer", "vendor", "tesseract", "tessdata");
  }

  execFileSync(backendExe("svr-migrate"), ["--seed-demo"], { env, stdio: "inherit" });

  const backend = spawn(backendExe("svr-backend"), ["--port", String(BACKEND_PORT)], {
    env,
    stdio: "inherit",
  });

  await waitForHttp(`http://127.0.0.1:${BACKEND_PORT}/health`, 30000);
  const staticServer = await startStaticServer();

  return async () => {
    staticServer.close();
    backend.kill();
  };
};
