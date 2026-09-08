// Manage Users screen (SDD 5.3). Manager + Owner. Create/edit users, assign role,
// toggle per-user 2FA. Passwords are never set here - the reset link (stubbed
// until email integration) is the only path.

import { api, getToken } from "../../lib/api.js";

const $ = (id) => document.getElementById(id);
let me = null;
let editingId = null;

function deriveLogin(name) {
  const toks = (name || "").trim().split(/\s+/).filter(Boolean);
  if (!toks.length) return "";
  const fi = toks[0][0].toLowerCase().replace(/[^a-z0-9]/g, "");
  const last = toks[toks.length - 1].toLowerCase().replace(/[^a-z0-9]/g, "");
  return fi + last;
}

function readForm() {
  // 2FA is not set here: users enable it themselves (Security page); admins only
  // CLEAR it, via the per-row "Clear 2FA" button (PUT { totp_enabled: false }).
  return {
    full_name: $("u-name").value.trim(),
    email: $("u-email").value.trim(),
    cell_phone: $("u-phone").value.trim() || null,
    role: $("u-role").value,
    status: $("u-status").value,
  };
}

function resetForm() {
  editingId = null;
  $("form-title").textContent = "Add User";
  $("save-btn").textContent = "Save User";
  $("cancel-edit-btn").style.display = "none";
  for (const id of ["u-name", "u-email", "u-phone", "u-login"]) $(id).value = "";
  $("u-role").value = "Sales";
  $("u-status").value = "Active";
  $("u-totp-state").textContent = "—";
}

function startEdit(u) {
  editingId = u.id;
  $("form-title").textContent = `Edit User — ${u.login_name}`;
  $("save-btn").textContent = "Update User";
  $("cancel-edit-btn").style.display = "inline-block";
  $("u-name").value = u.full_name;
  $("u-email").value = u.email;
  $("u-phone").value = u.cell_phone || "";
  $("u-login").value = u.login_name;
  $("u-role").value = u.role;
  $("u-status").value = u.status;
  $("u-totp-state").textContent = u.totp_enabled ? "On" : "Off";
}

function renderList(rows) {
  const body = $("user-rows");
  body.innerHTML = "";
  for (const u of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${u.full_name}</td><td>${u.email}</td><td>${u.login_name}</td>` +
      `<td>${u.role}</td><td>${u.status}</td><td>${u.totp_enabled ? "On" : "Off"}</td>` +
      `<td></td>`;
    const actions = tr.lastElementChild;
    const mkBtn = (label, fn) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "add-row-btn";
      b.style.margin = "0 4px 0 0";
      b.textContent = label;
      b.addEventListener("click", fn);
      return b;
    };
    actions.appendChild(mkBtn("Edit", () => startEdit(u)));
    actions.appendChild(mkBtn("Reset Password", () => resetPassword(u.id)));
    if (u.totp_enabled) actions.appendChild(mkBtn("Clear 2FA", () => clearTotp(u.id, u.login_name)));
    actions.appendChild(mkBtn("Delete", () => removeUser(u.id, u.login_name)));
    body.appendChild(tr);
  }
}

async function load() {
  renderList(await api.get("/users"));
}

async function save() {
  const st = $("form-status");
  const body = readForm();
  if (!body.full_name || !body.email) {
    st.className = "status-line err";
    st.textContent = "Name and Personal Email are required.";
    return;
  }
  st.className = "status-line";
  st.textContent = "Saving…";
  try {
    if (editingId) {
      await api.put(`/users/${editingId}`, body);
    } else {
      await api.post("/users", body);
    }
    resetForm();
    await load();
    st.className = "status-line ok";
    st.textContent = "User saved.";
  } catch (err) {
    st.className = "status-line err";
    st.textContent = `Save failed — ${err.message || err}`;
  }
}

async function resetPassword(id) {
  const st = $("form-status");
  try {
    const out = await api.post(`/users/${id}/reset-password`);
    st.className = "status-line ok";
    st.textContent = out.detail || "Password reset link emailed.";
    if (out.dev_reset_link) {
      st.textContent += `  (dev link: ${out.dev_reset_link})`;
    }
  } catch (err) {
    st.className = "status-line err";
    st.textContent = `Reset failed — ${err.message || err}`;
  }
}

async function clearTotp(id, login) {
  if (!window.confirm(`Turn OFF two-factor auth for ${login}? They'll sign in with just their password until they re-enable it.`)) return;
  const st = $("form-status");
  try {
    await api.put(`/users/${id}`, { totp_enabled: false });
    await load();
    st.className = "status-line ok";
    st.textContent = `2FA cleared for ${login}.`;
  } catch (err) {
    st.className = "status-line err";
    st.textContent = `Clear 2FA failed — ${err.message || err}`;
  }
}

async function removeUser(id, login) {
  if (!window.confirm(`Delete user ${login}?`)) return;
  const st = $("form-status");
  try {
    await api.del(`/users/${id}`);
    await load();
    st.className = "status-line ok";
    st.textContent = `Deleted ${login}.`;
  } catch (err) {
    st.className = "status-line err";
    st.textContent = `Delete failed — ${err.message || err}`;
  }
}

async function init() {
  if (!getToken()) {
    window.location.href = "../../index.html";
    return;
  }
  try {
    me = await api.me();
  } catch {
    window.location.href = "../../index.html";
    return;
  }
  $("who").textContent = `${me.full_name} (${me.role})`;
  $("u-name").addEventListener("input", () => {
    if (!editingId) $("u-login").value = deriveLogin($("u-name").value);
  });
  $("save-btn").addEventListener("click", save);
  $("cancel-edit-btn").addEventListener("click", resetForm);
  $("reset-pw-btn").addEventListener("click", () => {
    if (editingId) resetPassword(editingId);
    else {
      $("form-status").className = "status-line err";
      $("form-status").textContent = "Open a user (Edit) first, or use the per-row button.";
    }
  });
  await load();
}

init();
