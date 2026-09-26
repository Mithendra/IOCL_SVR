// Daily Sales Summary screen (SDD 5.23-5.25). Pull-based: it reads the two pump
// submissions for a shift date, shows the combined totals, records per-pump
// verification, and gates the upload. All combined figures come from the backend.

import { api, getToken } from "../../lib/api.js";
import { fmt2 } from "../../lib/format.js";

const $ = (id) => document.getElementById(id);
// Every figure reads to exactly two decimals (client-required 2026-09-11).
const money = (n) => fmt2(n);
// Which physical pump each side is. The mockups had these two swapped
// (Office shown as 12BC4523V-Off, Road as 11CC2012V-Road); the app's own
// PUMP_SIDE map in backend/summary.py has always been right, and this is the
// same pairing spelled out on screen (client, 2026-09-12).
const SIDE_SERIAL = { off: "11CC2012V-OFF", road: "12BC4523V-RD" };

let me = null;
let current = null; // last summary payload

// Returns a message if this side's submission carries a serial that isn't the one
// belonging to it, else null. The backend only ever files an entry under the side
// its serial maps to, so this should never fire - it is here because the two
// serials were swapped in the mockups for months without anything catching it.
function checkSerial(side, data) {
  const expected = SIDE_SERIAL[side];
  if (!data.present || data.pump_serial === expected) return null;
  return `${side === "off" ? "Office" : "Road"} side shows ${data.pump_serial} — expected ${expected}.`;
}

function fillSide(side, data) {
  $(`${side}-serial`).value =
    data.pump_serial || `(no submission — expected ${SIDE_SERIAL[side]})`;
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
  // Litres as well as amounts. These two lines are the figures Daily Trial
  // Balance Section 3 actually consumes (s3_hs_consumption / s3_ms_consumption),
  // and until 2026-09-13 they were the only numbers in the whole chain that never
  // appeared on the form that forwards them - the Summary showed money only, so
  // there was nowhere to check the consumption the Trial Balance would receive.
  const rows = [
    ["Diesel (HS) — Ltrs", c.hs_liters],
    ["Petrol (MS) — Ltrs", c.ms_liters],
    ["Diesel (HS)", c.hs],
    ["Petrol (MS)", c.ms],
    ["Gas Total Amt", c.gas_total],
    ...c.oils.map((o) => [o.label, o]),
    ["Total Amt Oil(s)", c.oil_total],
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

  const serialIssues = [checkSerial("off", s.office), checkSerial("road", s.road)].filter(Boolean);
  const serialCheck = $("serial-check");
  serialCheck.className = serialIssues.length ? "status-line err" : "status-line ok";
  serialCheck.textContent = serialIssues.length
    ? `Pump Serial# mismatch — ${serialIssues.join(" ")}`
    : "Pump Serial# check: Office = 11CC2012V-OFF, Road = 12BC4523V-RD.";

  // A pump in the workshop still files - one dropdown and Save, with no readings
  // (migration 0026). But its submission is all zeros and looks identical to a
  // pump that simply sold nothing, so say which it is rather than leaving the
  // reader to guess (client, 2026-09-14).
  const STATUS_TEXT = {
    repair: "Repair / Offline — no readings expected",
    salesman_off: "Sales Man Off — pump worked, nobody on it",
  };
  for (const side of ["off", "road"]) {
    const el = $(`${side}-status`);
    if (!el) continue;
    const data = side === "off" ? s.office : s.road;
    const txt = data.present ? STATUS_TEXT[data.pump_status] || "" : "";
    el.textContent = txt;
    el.style.color = data.pump_status === "repair" ? "var(--io-red, #c00000)" : "";
  }

  const gate = $("gate-status");
  if (!s.both_present) {
    // Every day needs both pumps' Daily Sales Entry, full stop - even a
    // repaired/off-duty pump submits a zero-activity report rather than being
    // skipped (2026-09-11 client confirmation). Name which side is actually
    // missing rather than a generic "waiting" message.
    const missing = [];
    if (!s.office.present) missing.push("Office pump");
    if (!s.road.present) missing.push("Road pump");
    // A pump out of service still has to say so - set Pump Status to
    // Repair/Offline and Save. That is the submission; no readings are needed.
    gate.className = "status-line err";
    gate.textContent =
      `Missing the Daily Sales Entry for: ${missing.join(" and ")}. Both pumps ` +
      "must file, including one that is out of service — set its Pump Status to " +
      "Repair/Offline and Save, which needs no readings.";
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
  // The screen has just been repainted from the server, so nothing is pending.
  markDirty();
}

async function load() {
  const s = await api.get(`/daily-sales-summary/${$("shift-date").value}`);
  render(s);
}

const VERIFY_FIELDS = [
  "off-verified", "road-verified", "off-note", "road-note",
  "off-salesman", "road-salesman",
];

// What differs from what the server last sent. `current` is that snapshot.
function pendingCount() {
  if (!current) return 0;
  let n = 0;
  for (const side of ["off", "road"]) {
    const data = current[side === "off" ? "office" : "road"] || {};
    if ($(`${side}-verified`).disabled) continue;
    if (($(`${side}-verified`).value === "1") !== !!data.verified) n += 1;
    if (($(`${side}-note`).value || "") !== (data.verified_note || "")) n += 1;
    if (($(`${side}-salesman`).value || "") !== (data.salesman || "")) n += 1;
  }
  return n;
}

function markDirty() {
  const n = pendingCount();
  // Save before anything is stored, Update once the day is on file - the same
  // pair, and the same meaning, as the Daily Trial Balance form.
  const onFile = !!(current && current.status && current.status !== "draft");
  const save = $("save-sum-btn");
  const update = $("update-sum-btn");
  const undo = $("undo-sum-btn");
  if (!save) return;
  save.style.display = onFile ? "none" : "";
  update.style.display = onFile ? "" : "none";
  save.disabled = n === 0;
  update.disabled = n === 0;
  undo.disabled = n === 0;
  const label = n ? ` ${n} change${n === 1 ? "" : "s"}` : "";
  save.textContent = `Save${label}`;
  update.textContent = `Update${label}`;
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
  const st = $("save-sum-status");
  st.className = "status-line";
  st.textContent = "Saving…";
  try {
    render(await api.put(`/daily-sales-summary/${$("shift-date").value}`, body));
    st.className = "status-line ok";
    st.textContent = "Saved.";
  } catch (err) {
    st.className = "status-line err";
    st.textContent = err.message || String(err);
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
  // Editing MARKS the row; Save writes it. It used to write on `change`.
  for (const el of VERIFY_FIELDS) {
    $(el).addEventListener("change", markDirty);
    $(el).addEventListener("input", markDirty);
  }
  $("save-sum-btn").addEventListener("click", pushUpdate);
  $("update-sum-btn").addEventListener("click", pushUpdate);
  $("undo-sum-btn").addEventListener("click", () => {
    render(current);
    const st = $("save-sum-status");
    st.className = "status-line";
    st.textContent = "Edits discarded.";
  });
  $("upload-btn").addEventListener("click", upload);
  await load();
}

init();
