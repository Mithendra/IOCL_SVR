// Daily Sales Summary screen (SDD 5.23-5.25). Pull-based: it reads the two pump
// submissions for a shift date, shows the combined totals, records per-pump
// verification, and gates the upload. All combined figures come from the backend.

import { api, getToken } from "../../lib/api.js";

const $ = (id) => document.getElementById(id);
const money = (n) => (n === null || n === undefined ? "" : String(n));

let me = null;
let current = null; // last summary payload

function fillSide(side, data) {
  $(`${side}-serial`).value = data.pump_serial || "(no submission)";
  $(`${side}-meta`).value = data.present
    ? `${data.submitted_by} / ${data.entry_mode}`
    : "—";
  $(`${side}-salesman`).value = data.salesman || "";
  $(`${side}-hs`).value = money(data.hs_amount);
  $(`${side}-ms`).value = money(data.ms_amount);
  $(`${side}-oil`).value = money(data.oil_total);
  $(`${side}-verified`).value = data.verified ? "1" : "0";
  $(`${side}-note`).value = data.verified_note || "";

  // A Sales user may only verify the pump they submitted (SDD 4.2).
  const mayVerify =
    me.role !== "Sales" || (data.present && data.submitted_by === me.login_name);
  $(`${side}-verified`).disabled = !mayVerify || !data.present;
  $(`${side}-note`).disabled = !mayVerify || !data.present;
  $(`${side}-salesman`).disabled = !mayVerify;
}

function fillCombined(c) {
  const body = $("combined-rows");
  body.innerHTML = "";
  const rows = [
    ["Diesel (HS)", c.hs],
    ["Petrol (MS)", c.ms],
    ...c.oils.map((o) => [o.label, o]),
    ["Oil Sale(s) Total", c.oil_total],
  ];
  for (const [label, line] of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${label}</td><td>${money(line.office)}</td>` +
      `<td>${money(line.road)}</td><td>${money(line.combined)}</td>`;
    body.appendChild(tr);
  }
  $("comb-grand").value = money(c.grand_total);
  $("grand-total").value = money(c.grand_total);
}

function render(s) {
  current = s;
  $("status-tag").textContent = s.status;
  $("prepared-by").textContent = s.prepared_by || "—";
  $("uploaded-at").textContent = s.uploaded_at
    ? new Date(s.uploaded_at).toLocaleString()
    : "—";
  fillSide("off", s.office);
  fillSide("road", s.road);
  fillCombined(s.combined);

  const gate = $("gate-status");
  if (!s.both_present) {
    // Every day needs both pumps' Daily Sales Entry, full stop - even a
    // repaired/off-duty pump submits a zero-activity report rather than being
    // skipped (2026-09-11 client confirmation). Name which side is actually
    // missing rather than a generic "waiting" message.
    const missing = [];
    if (!s.office.present) missing.push("Office pump");
    if (!s.road.present) missing.push("Road pump");
    gate.className = "status-line err";
    gate.textContent =
      `Missing the Daily Sales Entry for: ${missing.join(" and ")}. Both pump ` +
      "submissions are required before the Daily Sales Summary can be prepared.";
  } else if (!s.both_verified) {
    gate.className = "status-line err";
    gate.textContent = "Both pumps must be verified before upload.";
  } else if (s.status === "uploaded") {
    gate.className = "status-line ok";
    gate.textContent = `Uploaded by ${s.uploaded_by}.`;
  } else {
    gate.className = "status-line ok";
    gate.textContent = "Both pumps verified — ready to upload.";
  }

  const canUpload = s.can_upload && (me.role === "Manager" || me.role === "Owner");
  $("upload-btn").disabled = !canUpload;
  $("upload-btn").style.display =
    me.role === "Sales" ? "none" : "inline-block";
}

async function load() {
  const s = await api.get(`/daily-sales-summary/${$("shift-date").value}`);
  render(s);
}

async function pushUpdate() {
  // Only send a side's fields when its controls are enabled - a Sales user must
  // not even appear to touch the other pump (the backend would 403).
  const body = {};
  for (const side of ["off", "road"]) {
    if ($(`${side}-verified`).disabled) continue;
    body[`${side}_salesman`] = $(`${side}-salesman`).value || null;
    body[`${side}_verified`] = $(`${side}-verified`).value === "1";
    body[`${side}_verified_note`] = $(`${side}-note`).value || null;
  }
  try {
    render(await api.put(`/daily-sales-summary/${$("shift-date").value}`, body));
  } catch (err) {
    $("upload-status").className = "status-line err";
    $("upload-status").textContent = err.message || String(err);
    await load(); // resync to server truth
  }
}

async function upload() {
  const st = $("upload-status");
  st.className = "status-line";
  st.textContent = "Uploading…";
  try {
    render(await api.post(`/daily-sales-summary/${$("shift-date").value}/upload`));
    st.className = "status-line ok";
    st.textContent = `Uploaded. Grand Total ${current.combined.grand_total}.`;
  } catch (err) {
    st.className = "status-line err";
    st.textContent = `Upload failed — ${err.message || err}`;
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
  $("shift-date").value = new Date().toISOString().slice(0, 10);
  $("shift-date").addEventListener("change", load);
  for (const el of ["off-verified", "road-verified", "off-note", "road-note", "off-salesman", "road-salesman"]) {
    $(el).addEventListener("change", pushUpdate);
  }
  $("upload-btn").addEventListener("click", upload);
  await load();
}

init();
