// Loopback API client. Base URL resolution order:
//   1. window.svr.apiBase  (Electron preload bridge)
//   2. ?apiBase=...         (Playwright page-mode / dev)
//   3. http://127.0.0.1:8756 (default from SDD config)

function resolveBase() {
  if (window.svr && window.svr.apiBase) return window.svr.apiBase;
  const q = new URLSearchParams(window.location.search).get("apiBase");
  return q || "http://127.0.0.1:8756";
}

export const apiBase = resolveBase();

// Session token lives in sessionStorage: scoped to this window, cleared when the
// app closes, and shared across the shell -> screen page navigation. Not
// localStorage - nothing about a login should outlive the window (SDD 13.1).
const TOKEN_KEY = "svr.session.token";
let sessionToken = null;
try {
  sessionToken = window.sessionStorage.getItem(TOKEN_KEY);
} catch {
  sessionToken = null;
}

export function setToken(token) {
  sessionToken = token;
  try {
    if (token) window.sessionStorage.setItem(TOKEN_KEY, token);
    else window.sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* sessionStorage unavailable - in-memory only */
  }
}

export function getToken() {
  return sessionToken;
}

function authHeaders(extra) {
  const headers = extra ? { ...extra } : {};
  if (sessionToken) headers.Authorization = `Bearer ${sessionToken}`;
  return headers;
}

function httpError(method, path, status, detail) {
  const err = new Error(`${method} ${path} -> ${status}: ${detail}`);
  err.status = status;
  return err;
}

async function request(method, path, body) {
  const res = await fetch(apiBase + path, {
    method,
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const err = httpError(method, path, res.status, (data && data.detail) || res.statusText);
    err.data = data;
    throw err;
  }
  return data;
}

// Multipart upload (Excel/OCR import). Returns parsed JSON.
async function upload(path, file) {
  const fd = new FormData();
  fd.append("file", file, file.name || "upload");
  const res = await fetch(apiBase + path, { method: "POST", headers: authHeaders(), body: fd });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const err = httpError("POST", path, res.status, (data && data.detail) || res.statusText);
    err.data = data;
    throw err;
  }
  return data;
}

// GET a file and hand it to the browser as a download (Electron renderer).
async function download(path, fallbackName) {
  const res = await fetch(apiBase + path, { headers: authHeaders() });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = JSON.parse(await res.text());
      detail = j.detail || detail;
    } catch {
      /* non-JSON error body */
    }
    throw httpError("GET", path, res.status, detail);
  }
  const blob = await res.blob();
  const cd = res.headers.get("content-disposition") || "";
  const m = cd.match(/filename="?([^"]+)"?/);
  const name = (m && m[1]) || fallbackName || "download";
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return name;
}

export const api = {
  get: (p) => request("GET", p),
  post: (p, b) => request("POST", p, b),
  put: (p, b) => request("PUT", p, b),
  del: (p) => request("DELETE", p),
  upload,
  download,

  async login(loginName, password) {
    const out = await request("POST", "/auth/login", {
      login_name: loginName,
      password,
    });
    setToken(out.token);
    return out;
  },
  me: () => request("GET", "/auth/me"),
};
