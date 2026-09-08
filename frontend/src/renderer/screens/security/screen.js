// Security / 2FA — self-service TOTP enrollment for the signed-in user.
// Backend: /auth/2fa/{status,setup,activate,disable}. The secret is generated
// and stored server-side (encrypted); this screen only shows it once during
// setup so it can be added to an authenticator app.

import { api, getToken } from "../../lib/api.js";

const $ = (id) => document.getElementById(id);
const panels = ["panel-off", "panel-setup", "panel-on"];

function show(which) {
  panels.forEach((p) => ($(p).hidden = p !== which));
}

function setStatus(msg, kind) {
  const el = $("sec-status");
  el.className = kind ? `status-line ${kind}` : "status-line";
  el.textContent = msg || "";
}

async function refresh() {
  const s = await api.get("/auth/2fa/status");
  $("state").textContent = s.enabled ? "on" : "off";
  show(s.enabled ? "panel-on" : "panel-off");
}

async function startSetup() {
  setStatus("");
  try {
    const out = await api.post("/auth/2fa/setup");
    $("secret").textContent = out.secret;
    $("uri").textContent = out.otpauth_uri;
    $("activate-code").value = "";
    show("panel-setup");
  } catch (err) {
    setStatus(err.message || String(err), "err");
  }
}

async function activate() {
  setStatus("");
  try {
    await api.post("/auth/2fa/activate", { code: $("activate-code").value.trim() });
    setStatus("2FA is now on. You'll be asked for a code next time you sign in.", "ok");
    await refresh();
  } catch (err) {
    setStatus(
      err.status === 401 ? "That code didn't match — check your app's clock and try again." : err.message,
      "err"
    );
  }
}

async function disable() {
  setStatus("");
  try {
    await api.post("/auth/2fa/disable", { code: $("disable-code").value.trim() });
    setStatus("2FA is now off.", "ok");
    await refresh();
  } catch (err) {
    setStatus(err.status === 401 ? "That code was wrong or expired." : err.message, "err");
  }
}

async function init() {
  if (!getToken()) {
    window.location.href = "../../index.html";
    return;
  }
  try {
    $("who").textContent = (await api.me()).full_name;
  } catch {
    window.location.href = "../../index.html";
    return;
  }
  $("start-btn").addEventListener("click", startSetup);
  $("activate-btn").addEventListener("click", activate);
  $("cancel-btn").addEventListener("click", refresh);
  $("disable-btn").addEventListener("click", disable);
  await refresh();
}

init();
