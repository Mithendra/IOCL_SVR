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
      `<td><input class="on-hand" data-key="${r.item_key}" ` +
      `data-original="${fmt2(r.opening_stock)}" value="${fmt2(r.opening_stock)}" ` +
      `title="Sets the stock level outright - it does not add to it" ` +
      `${canSetStock() ? "" : "disabled"}></td>` +
      `<td>${fmt2(r.received_today)}</td>` +
      `<td>${fmt2(r.sold_today)}</td><td>${fmt2(r.closing_stock)}</td>` +
      `<td><input class="reorder" data-key="${r.item_key}" ` +
      `data-original="${fmt2(r.reorder_level)}" value="${fmt2(r.reorder_level)}" ` +
      `${isOwner() ? "" : "disabled"}></td>` +
      `<td style="color:${low ? "var(--io-red)" : "#157347"};font-weight:700">${low ? "Low" : "OK"}</td>`;
    body.appendChild(tr);
  }
  // Item 1 (client, 2026-09-24): "updated inventory master and there is no Save
  // button which is needed."
  //
  // Both figures used to write to the database on `change` - silently, the
  // moment the cell lost focus. No confirmation, no undo, and clicking away
  // mid-edit committed whatever happened to be in the box. On Hand is the
  // opening stock every later day is measured from, so that is the wrong way
  // round: it should take a deliberate press.
  //
  // Editing now only marks the row; Save writes. The rows that changed are
  // highlighted so it is obvious what is about to be written.
  for (const el of document.querySelectorAll(".on-hand, .reorder")) {
    el.addEventListener("input", () => {
      el.closest("tr").style.background = "#fff4e5";
      markDirty();
    });
  }
  markDirty();
}

// Which rows differ from what was loaded.
function pendingEdits() {
  const out = [];
  for (const el of document.querySelectorAll(".on-hand, .reorder")) {
    const original = el.dataset.original ?? "";
    if (String(el.value) !== String(original)) {
      out.push({ key: el.dataset.key, field: el.classList.contains("on-hand") ? "on_hand" : "reorder_level", value: el.value });
    }
  }
  return out;
}

function markDirty() {
  const n = pendingEdits().length;
  const btn = $("save-inv-btn");
  const undo = $("undo-inv-btn");
  if (btn) {
    btn.disabled = n === 0;
    btn.textContent = n ? `Save ${n} change${n === 1 ? "" : "s"}` : "Save";
  }
  if (undo) undo.disabled = n === 0;
}

async function saveInventory() {
  const st = $("restock-status");
  const edits = pendingEdits();
  if (!edits.length) return;
  st.className = "status-line";
  st.textContent = `Saving ${edits.length} change(s)…`;
  const done = [];
  try {
    for (const e of edits) {
      const n = Number(e.value);
      if (!Number.isFinite(n) || n < 0) {
        st.className = "status-line err";
        st.textContent =
          `${e.key}: ${e.field.replace("_", " ")} must be 0 or more — nothing saved for that row.`;
        return;
      }
      const body = e.field === "on_hand" ? { on_hand: n } : { reorder_level: n };
      await api.put(`/inventory/${e.key}`, body);
      done.push(`${e.key} ${e.field.replace("_", " ")} → ${e.value}`);
    }
    st.className = "status-line ok";
    st.textContent = `Saved: ${done.join(", ")}.`;
    await load();
  } catch (err) {
    st.className = "status-line err";
    st.textContent =
      `Saved ${done.length} of ${edits.length} — then failed: ${err.message || err}. ` +
      `Reload to see what is stored.`;
  }
}

// Item 1, the other half: undo the edits on screen before they are written.
// "Delete" on a stock figure is ambiguous - it could mean zero the stock or
// retire the item - so this does the unambiguous thing and puts the row back.
async function undoInventoryEdits() {
  await load();
  $("restock-status").className = "status-line";
  $("restock-status").textContent = "Edits discarded — showing what is stored.";
}

// ---- Item 2: the oil catalogue, moved here from Daily Sales Entry -----------
// Owner/Manager only, the same gate it had on the other screen. Retiring is a
// retire, never a delete: a day recorded before an item went away still shows
// its row and still adds up to what was actually banked.

function renderOilItems() {
  const body = $("oil-item-rows");
  if (!body) return;
  body.innerHTML = "";
  const allowed = canSetStock();
  for (const r of items) {
    const tr = document.createElement("tr");
    const name = document.createElement("td");
    name.textContent = r.item_label;
    const act = document.createElement("td");
    if (allowed) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "btn-small secondary";
      b.textContent = "Retire";
      b.addEventListener("click", () => retireOilItem(r.item_key, r.item_label));
      act.appendChild(b);
    }
    tr.appendChild(name);
    tr.appendChild(act);
    body.appendChild(tr);
  }
  const add = $("oil-add-btn");
  if (add) add.hidden = !allowed;
}

async function addOilItem() {
  const st = $("oil-admin-status");
  const label = ($("oil-new-label").value || "").trim();
  if (!label) {
    st.className = "status-line err";
    st.textContent = "Give the item a name first.";
    return;
  }
  st.className = "status-line";
  st.textContent = "Adding…";
  try {
    // Rate and Opening Stock go in with it: an oil row is unusable without both,
    // and the alternative is an operator finding a blank row and no way to price
    // it. Either can be corrected here or in Rate Master afterwards.
    await api.post("/oil-items", {
      label,
      rate: Number($("oil-new-rate").value) || 0,
      opening_stock: Number($("oil-new-stock").value) || 0,
    });
    $("oil-new").hidden = true;
    ["oil-new-label", "oil-new-rate", "oil-new-stock"].forEach((id) => {
      $(id).value = "";
    });
    await load();
    st.className = "status-line ok";
    st.textContent = `Added "${label}". It is on every Oil Sale(s) row from now on.`;
  } catch (err) {
    st.className = "status-line err";
    st.textContent = err.message || String(err);
  }
}

async function retireOilItem(key, label) {
  const st = $("oil-admin-status");
  st.className = "status-line";
  st.textContent = `Retiring "${label}"…`;
  try {
    await api.del(`/oil-items/${key}`);
    await load();
    st.className = "status-line ok";
    st.textContent =
      `"${label}" is off the Daily Sales form. Days already recorded still show ` +
      `it and are worth exactly what they were — add it again by name to bring ` +
      `it back.`;
  } catch (err) {
    st.className = "status-line err";
    st.textContent = err.message || String(err);
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
  renderOilItems();
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
  $("save-inv-btn").addEventListener("click", saveInventory);
  $("oil-add-btn").addEventListener("click", () => {
    $("oil-new").hidden = !$("oil-new").hidden;
  });
  $("oil-new-save").addEventListener("click", addOilItem);
  $("oil-new-cancel").addEventListener("click", () => {
    $("oil-new").hidden = true;
  });
  $("undo-inv-btn").addEventListener("click", undoInventoryEdits);
  await load();
}

init();
