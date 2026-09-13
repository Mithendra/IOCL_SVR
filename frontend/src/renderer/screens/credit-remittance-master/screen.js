// Credit / Remittance Master screen (SDD 5.17). Manager + Owner. Sections 1 & 2
// append credit_transaction rows; Section 3 is the grouped balance summary from
// GET /credit-master/summary (pending first).

import { api, getToken } from "../../lib/api.js";
import { fmt2 } from "../../lib/format.js";

const $ = (id) => document.getElementById(id);
const num = (v) => {
  const n = parseFloat(v);
  return isNaN(n) ? null : n;
};

function creditPreview() {
  const l = num($("c-ltrs").value);
  const r = num($("c-rate").value);
  // Disabled preview cell, never typed into - safe to format.
  $("c-amount").value = l !== null && r !== null ? fmt2(Math.round(l * r * 10000) / 10000) : "";
}

function renderCredits(rows) {
  $("credit-rows").innerHTML = rows
    .map(
      (t) =>
        `<tr><td>${t.txn_date}</td><td>${t.creditor_name}</td><td>${t.fuel_type || ""}</td>` +
        `<td>${fmt2(t.ltrs)}</td><td>${fmt2(t.rate)}</td><td>${fmt2(t.amount)}</td>` +
        `<td><button type="button" class="add-row-btn" style="margin:0" data-del="${t.id}">Delete</button></td></tr>`
    )
    .join("");
}

function renderRemittances(rows) {
  $("remittance-rows").innerHTML = rows
    .map(
      (t) =>
        `<tr><td>${t.txn_date}</td><td>${t.creditor_name}</td><td>${fmt2(t.amount)}</td>` +
        `<td>${t.source || ""}</td>` +
        `<td><button type="button" class="add-row-btn" style="margin:0" data-del="${t.id}">Delete</button></td></tr>`
    )
    .join("");
}

function renderSummary(rows) {
  $("summary-rows").innerHTML = rows
    .map((s) => {
      const owed = s.outstanding > 0;
      return (
        `<tr><td>${s.creditor_name}</td><td>${s.phone || ""}</td>` +
        `<td>${fmt2(s.total_credit)}</td><td>${fmt2(s.total_remitted)}</td>` +
        `<td style="color:${owed ? "var(--io-red)" : "#157347"};font-weight:700">${fmt2(s.outstanding)}</td></tr>`
      );
    })
    .join("");
}

async function load() {
  const [credits, remittances, summary] = await Promise.all([
    api.get("/credit-master/transactions?kind=credit"),
    api.get("/credit-master/transactions?kind=remittance"),
    api.get("/credit-master/summary"),
  ]);
  renderCredits(credits);
  renderRemittances(remittances);
  renderSummary(summary);
  for (const b of document.querySelectorAll("[data-del]")) {
    b.addEventListener("click", () => del(b.dataset.del));
  }
}

async function del(id) {
  try {
    await api.del(`/credit-master/transactions/${id}`);
    await load();
  } catch (err) {
    $("txn-status").className = "status-line err";
    $("txn-status").textContent = err.message || String(err);
  }
}

function status(ok, msg) {
  $("txn-status").className = `status-line ${ok ? "ok" : "err"}`;
  $("txn-status").textContent = msg;
}

async function addCredit() {
  const name = $("c-name").value.trim();
  if (!name) return status(false, "Creditor Name is required.");
  const l = num($("c-ltrs").value);
  const r = num($("c-rate").value);
  const body = { creditor_name: name, phone: $("c-phone").value.trim() || null, fuel_type: $("c-type").value.trim() || null };
  if (l !== null && r !== null) {
    body.ltrs = l;
    body.rate = r;
  } else {
    const a = num($("c-amount").value) || num($("c-rate").value);
    if (a === null) return status(false, "Enter Ltrs + Rate, or an Amount.");
    body.amount = a;
  }
  try {
    await api.post("/credit-master/credit", body);
    for (const id of ["c-name", "c-phone", "c-type", "c-ltrs", "c-rate", "c-amount"]) $(id).value = "";
    await load();
    status(true, "Credit added.");
  } catch (err) {
    status(false, `Add failed — ${err.message || err}`);
  }
}

async function addRemittance() {
  const name = $("r-name").value.trim();
  const amount = num($("r-amount").value);
  if (!name || amount === null || amount <= 0) return status(false, "Creditor Name and a positive Amount are required.");
  try {
    await api.post("/credit-master/remittance", {
      creditor_name: name,
      amount,
      txn_date: $("r-date").value || null,
      source: $("r-source").value.trim() || null,
      pump_sales_man: $("r-psm").value.trim() || null,
    });
    for (const id of ["r-name", "r-amount", "r-source", "r-psm"]) $(id).value = "";
    await load();
    status(true, "Remittance added.");
  } catch (err) {
    status(false, `Add failed — ${err.message || err}`);
  }
}

async function init() {
  if (!getToken()) {
    window.location.href = "../../index.html";
    return;
  }
  let me;
  try {
    me = await api.me();
  } catch {
    window.location.href = "../../index.html";
    return;
  }
  $("who").textContent = `${me.full_name} (${me.role})`;
  $("r-date").value = new Date().toISOString().slice(0, 10);
  $("c-ltrs").addEventListener("input", creditPreview);
  $("c-rate").addEventListener("input", creditPreview);
  $("add-credit").addEventListener("click", addCredit);
  $("add-remittance").addEventListener("click", addRemittance);
  await load();
}

init();
