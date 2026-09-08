"use strict";

const crypto = require("crypto");
const path = require("path");

// RFC 6238 TOTP (SHA-1, 30s, 6 digits) - so a Playwright test can produce the
// same code a real authenticator app would, from a base32 secret.
function base32Decode(secret) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  const clean = secret.replace(/=+$/, "").toUpperCase().replace(/\s+/g, "");
  let bits = "";
  for (const ch of clean) {
    const idx = alphabet.indexOf(ch);
    if (idx >= 0) bits += idx.toString(2).padStart(5, "0");
  }
  const bytes = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) bytes.push(parseInt(bits.slice(i, i + 8), 2));
  return Buffer.from(bytes);
}

function totpCode(secret, atMs = Date.now()) {
  const counter = Math.floor(atMs / 1000 / 30);
  const buf = Buffer.alloc(8);
  buf.writeBigInt64BE(BigInt(counter));
  const hmac = crypto.createHmac("sha1", base32Decode(secret)).update(buf).digest();
  const off = hmac[hmac.length - 1] & 0x0f;
  const bin =
    ((hmac[off] & 0x7f) << 24) |
    (hmac[off + 1] << 16) |
    (hmac[off + 2] << 8) |
    hmac[off + 3];
  return (bin % 1_000_000).toString().padStart(6, "0");
}

const BACKEND_PORT = 8799;
const STATIC_PORT = 5599;

const REPO_ROOT = path.resolve(__dirname, "..", "..");
const RENDERER_DIR = path.resolve(__dirname, "..", "src", "renderer");

// Backend console scripts from the dev venv; override with SVR_BACKEND_BIN in CI.
const BACKEND_BIN =
  process.env.SVR_BACKEND_BIN || path.join(REPO_ROOT, "backend", ".venv", "Scripts");

const backendExe = (name) => path.join(BACKEND_BIN, process.platform === "win32" ? `${name}.exe` : name);

module.exports = {
  BACKEND_PORT,
  STATIC_PORT,
  REPO_ROOT,
  RENDERER_DIR,
  BACKEND_BIN,
  backendExe,
  totpCode,
  apiBase: `http://127.0.0.1:${BACKEND_PORT}`,
  staticBase: `http://127.0.0.1:${STATIC_PORT}`,
};
