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

const escHtml = (v) =>
  String(v == null ? "" : v).replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]
  );

const $ = (id) => document.getElementById(id);
let me = null;
let items = [];

// One rule for the whole form since 2026-09-25: Manager or Owner may edit, and
// every edit carries the Owner passphrase. Reorder Level used to be Owner-only
// and stock levels briefly were too; both now follow the same rule, so there is
// one answer to "may I change this" instead of three.
function canEdit() {
  return me && (me.role === "Manager" || me.role === "Owner");
}

// A rate that has never been set shows EMPTY, not 0.00 - "no buy rate on file"
// and "this costs nothing" are different facts, and every oil item currently has
// a null buy rate.
// An ISO timestamp as the station reads it, in IST - the column is "Updated On",
// not "Updated On, in UTC, if you convert it yourself".
function stampOf(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return escHtml(iso);
  return d.toLocaleString("en-GB", {
    timeZone: "Asia/Kolkata",
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

const rateVal = (v) => (v === null || v === undefined || v === "" ? "" : fmt2(v));

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
      `${canEdit() ? "" : "disabled"}></td>` +
      `<td>${fmt2(r.received_today)}</td>` +
      `<td>${fmt2(r.sold_today)}</td><td>${fmt2(r.closing_stock)}</td>` +
      `<td><input class="reorder" data-key="${r.item_key}" ` +
      `data-original="${fmt2(r.reorder_level)}" value="${fmt2(r.reorder_level)}" ` +
      `${canEdit() ? "" : "disabled"}></td>` +
      // Buy/Sell Rate: Owner only, behind the passphrase, stored in Rate Master
      // and dated from today (client, 2026-09-25).
      `<td><input class="buy-rate" data-key="${r.item_key}" ` +
      `data-original="${rateVal(r.buy_rate)}" value="${rateVal(r.buy_rate)}" ` +
      `title="Owner only - written to Rate Master, effective today" ` +
      `${canEdit() ? "" : "disabled"}></td>` +
      `<td><input class="sell-rate" data-key="${r.item_key}" ` +
      `data-original="${rateVal(r.sell_rate)}" value="${rateVal(r.sell_rate)}" ` +
      `title="Owner only - written to Rate Master, effective today" ` +
      `${canEdit() ? "" : "disabled"}></td>` +
      `<td style="color:${low ? "var(--io-red)" : "#157347"};font-weight:700">${low ? "Low" : "OK"}</td>` +
      `<td style="font-size:11px">${escHtml(r.last_updated_by) || "—"}</td>` +
      `<td style="font-size:11px;white-space:nowrap">${stampOf(r.last_updated_at)}</td>`;
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
  for (const el of document.querySelectorAll(".on-hand, .reorder, .buy-rate, .sell-rate")) {
    el.addEventListener("input", () => {
      el.closest("tr").style.background = "#fff4e5";
      markDirty();
    });
  }
  markDirty();
}

// Which rows differ from what was loaded.
const FIELD_OF = {
  "on-hand": "on_hand",
  reorder: "reorder_level",
  "buy-rate": "buy_rate",
  "sell-rate": "sell_rate",
};

function pendingEdits() {
  const out = [];
  for (const el of document.querySelectorAll(".on-hand, .reorder, .buy-rate, .sell-rate")) {
    const original = el.dataset.original ?? "";
    if (String(el.value) === String(original)) continue;
    const cls = Object.keys(FIELD_OF).find((c) => el.classList.contains(c));
    out.push({ key: el.dataset.key, field: FIELD_OF[cls], value: el.value });
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

// Unlocking stock editing.
//
// A button that asks for the passphrase, as the client asked (2026-09-25) - but
// the asking is inline. Electron never shows window.prompt(), so a prompt here
// would return nothing and Unlock would look like it did nothing at all; that
// exact mistake has already been found three times in this app.
//
// The passphrase is checked against the server before anything is enabled, and
// it is still sent with every row that gets written: an unlocked screen left
// open is not by itself permission to change a stock level.
let unlockedSecret = null;

// Every write on this form goes through here. Client, 2026-09-25: "This form Can
// only be edited by Owner with his Secert password and none allowed" - so
// Restock, the oil catalogue and the invoice upload are gated exactly like a
// stock level, not just the figures that looked dangerous.
function requireUnlocked(statusEl) {
  if (unlockedSecret) return unlockedSecret;
  statusEl.className = "status-line err";
  statusEl.textContent =
    "Press Unlock stock editing and enter the Owner passphrase first — this form " +
    "is Owner-only.";
  openUnlock();
  return null;
}

function openUnlock() {
  $("inv-secret-ask").hidden = false;
  $("inv-secret").value = "";
  $("inv-secret").focus();
}

function closeUnlock() {
  $("inv-secret-ask").hidden = true;
  $("inv-secret").value = "";
}

async function tryUnlock() {
  const state = $("inv-unlock-state");
  const secret = ($("inv-secret").value || "").trim();
  if (!secret) {
    state.textContent = "Enter the passphrase.";
    return;
  }
  try {
    // This form's own check, not /owner-reset/unlock - that one is Owner-only
    // and belongs to the reading-reset form, so a Manager could never open this.
    await api.post("/inventory/unlock", { passphrase: secret });
  } catch (err) {
    state.style.color = "var(--io-red, #c00000)";
    state.textContent = err.status === 403 ? "Wrong passphrase." : err.message || String(err);
    return;
  }
  unlockedSecret = secret;
  closeUnlock();
  state.style.color = "var(--io-green, #1f7a3d)";
  state.textContent = "Unlocked — stock levels can be saved.";
  $("inv-unlock-btn").textContent = "Stock editing unlocked";
  $("inv-unlock-btn").disabled = true;
}

// ---- Stock Purchase documents ---------------------------------------------

async function loadStockPurchases() {
  const body = $("sp-rows");
  if (!body) return;
  try {
    const rows = await api.get("/stock-purchases");
    body.innerHTML = rows.length
      ? rows
          .map(
            (d) =>
              `<tr><td>${d.purchase_date}</td><td>${d.item_key || "—"}</td>` +
              `<td>${escHtml(d.supplier)}</td>` +
              `<td style="text-align:right">${d.amount == null ? "—" : fmt2(d.amount)}</td>` +
              `<td><button type="button" class="add-row-btn" style="margin:0" ` +
              `data-doc="${d.id}" data-name="${escHtml(d.original_name)}">` +
              `${escHtml(d.original_name)}</button> ` +
              `<span style="font-size:10px;color:#666">${Math.round(d.size_bytes / 1024)} KB</span></td>` +
              `<td>${escHtml(d.uploaded_by)}</td></tr>`
          )
          .join("")
      : '<tr><td colspan="6" style="color:var(--io-blue-dark)">No purchase documents yet.</td></tr>';
    for (const b of body.querySelectorAll("[data-doc]")) {
      b.addEventListener("click", () =>
        api.download(`/stock-purchases/${b.dataset.doc}/file`, b.dataset.name)
      );
    }
  } catch {
    // Manager/Owner only; a Sales session simply does not show the block.
    const t = $("sp-table");
    if (t) t.hidden = true;
  }
}

async function uploadStockPurchase() {
  const st = $("sp-status");
  const picked = $("sp-file").files && $("sp-file").files[0];
  if (!picked) {
    st.className = "status-line err";
    st.textContent = "Choose the invoice file first (PDF or a photo).";
    return;
  }
  const secret = requireUnlocked(st);
  if (!secret) return;
  st.className = "status-line";
  st.textContent = `Uploading ${picked.name}…`;
  try {
    const doc = await api.upload("/stock-purchases", picked, {
      purchase_date: $("sp-date").value,
      item_key: $("sp-item").value,
      supplier: $("sp-supplier").value.trim(),
      amount: $("sp-amount").value.trim(),
      note: $("sp-note").value.trim(),
      passphrase: secret,
    });
    st.className = "status-line ok";
    st.textContent = `Stored ${doc.original_name} against ${doc.purchase_date}.`;
    $("sp-file").value = "";
    $("sp-supplier").value = "";
    $("sp-amount").value = "";
    $("sp-note").value = "";
    await loadStockPurchases();
  } catch (err) {
    st.className = "status-line err";
    st.textContent = `Upload failed — ${err.message || err}`;
  }
}

async function saveInventory() {
  const st = $("restock-status");
  const edits = pendingEdits();
  if (!edits.length) return;
  // Sent with every row, not just to unlock the screen: an unlocked page left
  // open is not by itself permission to change a stock level.
  const secret = requireUnlocked(st);
  if (!secret) return;
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
      // Rates go to Rate Master, stock figures to the item itself. Two routes
      // because they are two different records: a rate is effective-dated and
      // appended, so a past day keeps the price it was sold at.
      if (e.field === "buy_rate" || e.field === "sell_rate") {
        await api.put(`/inventory/${e.key}/rates`, { [e.field]: n, passphrase: secret });
      } else {
        const body = e.field === "on_hand" ? { on_hand: n } : { reorder_level: n };
        body.passphrase = secret;
        await api.put(`/inventory/${e.key}`, body);
      }
      done.push(`${e.key} ${e.field.replace("_", " ")} → ${e.value}`);
    }
    // Reload BEFORE saying "Saved", not after. The message used to appear while
    // load() was still in flight, so anything typed the moment it showed was
    // wiped by the re-render that followed - the screen said the write was
    // finished while it was still redrawing.
    await load();
    st.className = "status-line ok";
    st.textContent = `Saved: ${done.join(", ")}.`;
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

// The oil catalogue: what the Daily Sales form's Oil Sale(s) rows are built
// from. Retired items are listed too, greyed, with Restore beside them.
//
// This used to iterate the INVENTORY rows, which stay whether an item is retired
// or not - so a retired product still showed with a Retire button and nothing
// said it was already gone. Pressing it again looked like nothing happening,
// and five items were retired in four seconds on 2026-09-25 while the Daily
// Sales form quietly dropped to two rows.
let catalogue = [];
let retireArmed = null;

async function loadOilCatalogue() {
  try {
    catalogue = await api.get("/oil-items?include_retired=true");
  } catch {
    catalogue = [];
  }
  renderOilItems();
}

function renderOilItems() {
  const body = $("oil-item-rows");
  if (!body) return;
  body.innerHTML = "";
  const allowed = canEdit();
  const active = catalogue.filter((r) => r.active).length;
  for (const r of catalogue) {
    const tr = document.createElement("tr");
    const name = document.createElement("td");
    name.textContent = r.label;
    if (!r.active) {
      name.style.color = "#8a8f98";
      name.style.fontStyle = "italic";
    }
    const state = document.createElement("td");
    state.textContent = r.active ? "On the daily form" : "Retired";
    state.style.fontSize = "11px";
    state.style.color = r.active ? "#157347" : "#8a8f98";

    const act = document.createElement("td");
    if (allowed) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "btn-small secondary";
      if (!r.active) {
        b.textContent = "Restore";
        b.addEventListener("click", () => restoreOilItem(r.item_key, r.label));
      } else if (active <= 1) {
        // The last one cannot go: Oil Sale(s) with no rows is a broken form.
        b.textContent = "Retire";
        b.disabled = true;
        b.title = "The last item on the daily form cannot be retired";
      } else {
        b.textContent = retireArmed === r.item_key ? "Confirm retire" : "Retire";
        if (retireArmed === r.item_key) b.classList.add("armed");
        b.addEventListener("click", () => {
          // Two presses. One click used to take an item off the daily form with
          // no confirmation and no visible change in this list.
          if (retireArmed !== r.item_key) {
            retireArmed = r.item_key;
            renderOilItems();
            const st = $("oil-admin-status");
            st.className = "status-line err";
            st.textContent =
              `"${r.label}" will come off the Daily Sales form. Past days keep it ` +
              `and are worth exactly what they were. Press again to confirm.`;
            setTimeout(() => {
              if (retireArmed === r.item_key) {
                retireArmed = null;
                renderOilItems();
              }
            }, 8000);
            return;
          }
          retireArmed = null;
          retireOilItem(r.item_key, r.label);
        });
      }
      act.appendChild(b);
    }
    tr.appendChild(name);
    tr.appendChild(state);
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
  const secret = requireUnlocked(st);
  if (!secret) return;
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
      passphrase: secret,
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

async function restoreOilItem(key, label) {
  const st = $("oil-admin-status");
  const secret = requireUnlocked(st);
  if (!secret) return;
  st.className = "status-line";
  st.textContent = `Restoring "${label}"…`;
  try {
    await api.patch(`/oil-items/${key}`, { active: true, passphrase: secret });
    await load();
    st.className = "status-line ok";
    st.textContent = `"${label}" is back on the Daily Sales form.`;
  } catch (err) {
    st.className = "status-line err";
    st.textContent = err.message || String(err);
  }
}

async function retireOilItem(key, label) {
  const st = $("oil-admin-status");
  const secret = requireUnlocked(st);
  if (!secret) return;
  st.className = "status-line";
  st.textContent = `Retiring "${label}"…`;
  try {
    await api.post(`/oil-items/${key}/retire`, { passphrase: secret });
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
  await loadOilCatalogue();
}


async function addRestock() {
  const st = $("restock-status");
  const qty = Number($("rs-qty").value);
  if (!qty || qty <= 0) {
    st.className = "status-line err";
    st.textContent = "Enter a quantity greater than 0.";
    return;
  }
  const secret = requireUnlocked(st);
  if (!secret) return;
  st.className = "status-line";
  st.textContent = "Saving…";
  try {
    await api.post("/inventory/restock", {
      item_key: $("rs-item").value,
      quantity: qty,
      supplier_ref: $("rs-ref").value || null,
      restock_date: $("rs-date").value || null,
      passphrase: secret,
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
  // Gate on the ROLE first, before any fetch. The oil-catalogue controls were
  // hidden inside the render that draws the catalogue - and for Sales the screen
  // never gets that far, because GET /inventory 403s and init throws, leaving
  // "+ New Oil Item" showing in its default state. Server-side RBAC still
  // refuses the write; this is about not offering it.
  if (me.role === "Sales") {
    for (const id of ["oil-add-btn", "save-inv-btn", "undo-inv-btn", "restock-btn"]) {
      const el = $(id);
      if (el) el.hidden = true;
    }
  }
  const today = new Date().toISOString().slice(0, 10);
  $("as-of").value = today;
  $("rs-date").value = today;
  $("as-of").addEventListener("change", load);
  $("restock-btn").addEventListener("click", addRestock);
  $("save-inv-btn").addEventListener("click", saveInventory);
  $("sp-upload-btn").addEventListener("click", uploadStockPurchase);
  $("sp-date").value = new Date().toISOString().slice(0, 10);
  try {
    const items = await api.get("/oil-items");
    $("sp-item").innerHTML =
      '<option value="">— any / mixed —</option>' +
      items.map((i) => `<option value="${i.item_key}">${escHtml(i.label)}</option>`).join("");
  } catch {
    // The dropdown is a convenience; an invoice can be filed without an item.
  }
  await loadStockPurchases();
  // Only an Owner may change a stock level now (client, 2026-09-25), so only an
  // Owner is shown the box - and everyone else is told why, rather than finding
  // out from a 403 after typing a correction.
  // Manager or Owner may edit, with the Owner's passphrase (client,
  // 2026-09-25). So both are offered the Unlock button - it was Owner-only for
  // a few hours, which left a Manager with a disabled Save and no way in.
  if (me && (me.role === "Owner" || me.role === "Manager")) {
    $("inv-secret-row").hidden = false;
    $("inv-lock-note").textContent =
      "Every change on this form needs the Owner passphrase — the same one as the " +
      "reading reset on Daily Sales Entry. Updated By records who made it.";
    $("inv-unlock-btn").addEventListener("click", openUnlock);
    $("inv-unlock-ok").addEventListener("click", tryUnlock);
    $("inv-unlock-cancel").addEventListener("click", closeUnlock);
    $("inv-secret").addEventListener("keydown", (e) => {
      if (e.key === "Enter") tryUnlock();
    });
  } else {
    $("inv-lock-note").textContent =
      "This form is read-only for your role.";
    $("save-inv-btn").disabled = true;
    $("save-inv-btn").title = "Owner only";
  }
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
