// Login page. On success (or an existing session) the app goes straight to the
// default form — Daily Sales Entry — which carries the persistent sidebar
// (lib/screen-shell.js). There is no separate "choose a module" landing screen.

import { api, apiBase, getToken, setToken } from "./lib/api.js";

const DEFAULT_SCREEN = "screens/daily-sales-entry/index.html";
const loginError = document.getElementById("login-error");

function goToDefaultScreen() {
  window.location.href = `${DEFAULT_SCREEN}?apiBase=${encodeURIComponent(apiBase)}`;
}

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  loginError.textContent = "";
  try {
    await api.login(
      document.getElementById("login-name").value.trim(),
      document.getElementById("password").value
    );
    goToDefaultScreen();
  } catch (err) {
    loginError.textContent = err.status === 401 ? "Invalid login name or password." : String(err.message || err);
  }
});

document.getElementById("forgot-link").addEventListener("click", async (e) => {
  e.preventDefault();
  const status = document.getElementById("forgot-status");
  const id = window.prompt("Enter your login name or email:");
  if (!id) return;
  try {
    const out = await api.post("/auth/password-reset/request", { identifier: id.trim() });
    status.style.color = "#157347";
    status.textContent = out.detail || "If that account exists, a reset link has been emailed.";
    // Dev email backends echo the link so you can complete the flow without a mailbox.
    if (out.dev_reset_link) window.location.href = out.dev_reset_link;
  } catch (err) {
    status.style.color = "";
    status.textContent = err.message || String(err);
  }
});

// Already signed in (token set by a prior login in this window)? Go straight in.
if (getToken()) {
  api.me().then(goToDefaultScreen).catch(() => setToken(null));
}
