// Inventory Tracking screen (SDD 5.10). Manager + Owner only. Section 1 is the
// derived stock snapshot; Section 2 logs a delivery.
//
// Two different ways stock moves, and the difference matters (client, 2026-09-11):
//   * Restock ADDS - it is a receipt log ("30 more arrived today").
//   * Opening Stock SETS - it establishes the true count outright, including 0.
// Before this, only Restock was reachable from the UI, so entering a corrected
// figure added to the old one instead of replacing it and there was no way to
// establish an opening count at all. Both Manager and Owner can set it.

import { api, getToken } from "../../lib/api.js";
import { fmt2 } from "../../lib/format.js";

const $ = (id) => document.getElementById(id);
let me = null;
let items = [];

function isOwner() {
  return me && me.role === "Owner";
}

// Setting stock outright is Manager or Owner; Reorder Level stays Owner-only.
function canSetStock() {
  return me && (me.role === "Manager" || me.role === "Owner");
}

function renderStock(rows) {
  items = rows;
  const body = $("stock-rows");
  body.innerHTML = "";
  for (const r of rows) {
    const tr = document.createElement("tr");
    const low = r.status === "low";
    tr.innerHTML =
      `<td>${r.item_label}</td><td>${r.unit}</td>` +
      `<td><input class="on-hand" data-key="${r.item_key}" value="${fmt2(r.opening_stock)}" ` +
      `title="Sets the stock level outright - it does not add to it" ` +
      `${canSetStock() ? "" : "disabled"}></td>` +
      `<td>${fmt2(r.received_today)}</td>` +
      `<td>${fmt2(r.sold_today)}</td><td>${fmt2(r.closing_stock)}</td>` +
      `<td><input class="reorder" data-key="${r.item_key}" value="${fmt2(r.reorder_level)}" ${isOwner() ? "" : "disabled"}></td>` +
      `<td style="color:${low ? "var(--io-red)" : "#157347"};font-weight:700">${low ? "Low" : "OK"}</td>`;
    body.appendChild(tr);
  }
  if (isOwner()) {
    for (const el of document.querySelectorAll(".reorder")) {
      el.addEventListener("change", () => saveReorder(el.dataset.key, el.value));
    }
  }
  if (canSetStock()) {
    for (const el of document.querySelectorAll(".on-hand")) {
      el.addEventListener("change", () => saveOnHand(el.dataset.key, el.value));
    }
  }
}

// Replaces the tracked stock level with exactly what was typed - including 0.
async function saveOnHand(key, value) {
  const st = $("restock-status");
  const qty = Number(value);
  if (!Number.isFinite(qty) || qty < 0) {
    st.className = "status-line err";
    st.textContent = "Opening Stock must be 0 or more.";
    await load(); // put the old figure back
    return;
  }
  try {
    await api.put(`/inventory/${key}`, { on_hand: qty });
    await load();
    st.className = "status-line ok";
    st.textContent = `Opening Stock for ${key} set to ${fmt2(qty)} (replaced, not added).`;
  } catch (err) {
    st.className = "status-line err";
    st.textContent = `Failed — ${err.message || err}`;
    await load();
  }
}

function fillItemDropdown() {
  const sel = $("rs-item");
  sel.innerHTML = "";
  for (const r of items) {
    const o = document.createElement("option");
    o.value = r.item_key;
    o.textContent = r.item_label;
    sel.appendChild(o);
  }
}

async function load() {
  const rows = await api.get(`/inventory?as_of=${$("as-of").value}`);
  $("as-of-label").textContent = $("as-of").value;
  renderStock(rows);
  fillItemDropdown();
}

async function saveReorder(key, value) {
  const st = $("restock-status");
  try {
    await api.put(`/inventory/${key}`, { reorder_level: Number(value) });
    await load();
    st.className = "status-line ok";
    st.textContent = `Reorder level for ${key} set to ${value}.`;
  } catch (err) {
    st.className = "status-line err";
    st.textContent = `Failed — ${err.message || err}`;
  }
}

async function addRestock() {
  const st = $("restock-status");
  const qty = Number($("rs-qty").value);
  if (!qty || qty <= 0) {
    st.className = "status-line err";
    st.textContent = "Enter a quantity greater than 0.";
    return;
  }
  st.className = "status-line";
  st.textContent = "Saving…";
  try {
    await api.post("/inventory/restock", {
      item_key: $("rs-item").value,
      quantity: qty,
      supplier_ref: $("rs-ref").value || null,
      restock_date: $("rs-date").value || null,
    });
    $("rs-qty").value = "";
    $("rs-ref").value = "";
    await load();
    st.className = "status-line ok";
    st.textContent = "Restock recorded.";
  } catch (err) {
    st.className = "status-line err";
    st.textContent = `Restock failed — ${err.message || err}`;
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
  const today = new Date().toISOString().slice(0, 10);
  $("as-of").value = today;
  $("rs-date").value = today;
  $("as-of").addEventListener("change", load);
  $("restock-btn").addEventListener("click", addRestock);
  await load();
}

init();
