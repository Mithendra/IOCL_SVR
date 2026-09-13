// Payment Receipt screen (SDD 5.20). Point-of-sale fuel receipt - Sales, Manager,
// Owner may issue; Manager/Owner may delete. Rate defaults server-side to the
// current Sell Rate; total = liters x rate.

import { api, getToken } from "../../lib/api.js";
import { fmt2 } from "../../lib/format.js";

const $ = (id) => document.getElementById(id);
const numOrNull = (v) => {
  const n = parseFloat(v);
  return isNaN(n) ? null : n;
};

let me = null;

function syncModeRows() {
  const mode = $("r-mode").value;
  $("row-ref").style.display = mode === "Cash" ? "none" : "";
  $("row-card").style.display = mode === "Card" ? "" : "none";
}

function preview() {
  const l = numOrNull($("r-liters").value);
  const r = numOrNull($("r-rate").value);
  // Disabled preview cell, never typed into - safe to format.
  $("r-total").value = l !== null && r !== null ? fmt2(Math.round(l * r * 10000) / 10000) : "";
}

function renderList(rows) {
  $("receipt-rows").innerHTML = rows
    .map(
      (x) =>
        `<tr><td>${x.receipt_no || ""}</td><td>${x.receipt_date}</td><td>${x.fuel_type}</td>` +
        `<td>${fmt2(x.liters)}</td><td>${fmt2(x.rate)}</td><td>${fmt2(x.total)}</td>` +
        `<td>${x.payment_mode}</td>` +
        `<td>${me.role === "Sales" ? "" : `<button type="button" class="add-row-btn" style="margin:0" data-del="${x.id}">Delete</button>`}</td></tr>`
    )
    .join("");
  for (const b of document.querySelectorAll("[data-del]")) {
    b.addEventListener("click", () => del(b.dataset.del));
  }
}

function showIssued(r) {
  $("ic-no").textContent = r.receipt_no;
  $("ic-body").innerHTML = [
    ["Date / Time", `${r.receipt_date} ${r.receipt_time || ""}`],
    ["Pump", r.pump_serial || ""],
    ["Attendant", r.attendant || ""],
    ["Vehicle", r.vehicle_no || "—"],
    ["Fuel", r.fuel_type],
    ["Liters × Rate", `${fmt2(r.liters)} × ${fmt2(r.rate)}`],
    ["Total", `₹ ${fmt2(r.total)}`],
    ["Paid via", `${r.payment_mode}${r.ref_no ? " · " + r.ref_no : ""}${r.card_last4 ? " · ****" + r.card_last4 : ""}`],
  ]
    .map(([k, v]) => `<div class="summary-row"><span>${k}</span><span>${v}</span></div>`)
    .join("");
  $("issued-card").style.display = "block";
}

async function load() {
  renderList(await api.get("/receipts"));
}

async function del(id) {
  try {
    await api.del(`/receipts/${id}`);
    await load();
  } catch (err) {
    $("issue-status").className = "status-line err";
    $("issue-status").textContent = err.message || String(err);
  }
}

async function issue() {
  const st = $("issue-status");
  const liters = numOrNull($("r-liters").value);
  if (liters === null || liters <= 0) {
    st.className = "status-line err";
    st.textContent = "Enter liters.";
    return;
  }
  try {
    const r = await api.post("/receipts", {
      receipt_date: $("r-date").value || null,
      receipt_time: $("r-time").value || null,
      pump_serial: $("r-pump").value.trim() || null,
      attendant: $("r-attendant").value.trim() || null,
      vehicle_no: $("r-vehicle").value.trim() || null,
      fuel_type: $("r-fuel").value,
      liters,
      rate: numOrNull($("r-rate").value),
      payment_mode: $("r-mode").value,
      ref_no: $("r-ref").value.trim() || null,
      card_last4: $("r-card4").value.trim() || null,
    });
    showIssued(r);
    await load();
    st.className = "status-line ok";
    st.textContent = `Issued ${r.receipt_no} — ₹ ${fmt2(r.total)}.`;
    $("r-liters").value = "";
    $("r-total").value = "";
  } catch (err) {
    st.className = "status-line err";
    st.textContent = `Issue failed — ${err.message || err}`;
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
  const now = new Date();
  $("r-date").value = now.toISOString().slice(0, 10);
  $("r-time").value = now.toTimeString().slice(0, 5);
  $("r-mode").addEventListener("change", syncModeRows);
  $("r-liters").addEventListener("input", preview);
  $("r-rate").addEventListener("input", preview);
  $("issue-btn").addEventListener("click", issue);
  syncModeRows();
  await load();
}

init();
