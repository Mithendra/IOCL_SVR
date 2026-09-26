// Daily Sales Entry screen. Ported from
// docs/01-BRD-Requirement-Gathering/daily_sales_report_branded.html, with the demo
// functions replaced by loopback-API calls. The backend's /calc result is
// authoritative; calc-mirror only fills the gap between keystroke and response.

import { api, getToken } from "../../lib/api.js";
import * as mirror from "../../lib/calc-mirror.js";
import { fmt2 } from "../../lib/format.js";
import { renderDsrForm } from "../../lib/dsr-form.js";

// Oil Sale(s) rows come from the server (/oil-items), not from a list kept here.
// The station decides what it sells (client, 2026-09-13), so a second copy in the
// renderer would be one more thing to drift. Loaded once per screen load.
//
// The order is NOT numeric key order: item_key identifies a product, so when the
// list was revised on 2026-09-12 the renamed products kept their keys - and their
// rate history and tracked stock - and only moved position.
let OIL_KEYS = [];
// Every label the station has ever used -> its product, from /oil-items/aliases.
// Reopening an entry saved under an old label must put each row back against the
// right item rather than against whatever now sits at that position.
let OIL_ALIASES = {};
// Client's own reference blank forms (SVR_DSR_EMPTY_<serial>.pdf) print this
// qualifier next to the serial - shown on screen too so it's clear which
// physical pump is selected before Save or Print (2026-09-11).
const PUMP_LABELS = { "12BC4523V-RD": "Road pump", "11CC2012V-OFF": "Office pump" };

const $ = (id) => document.getElementById(id);
const val = (id) => ($(id) ? $(id).value : "");
const setVal = (id, v) => {
  const el = $(id);
  if (el) el.value = v === null || v === undefined ? "" : v;
};
// For computed, read-only figures only - every one reads to exactly two decimals
// (2026-09-11). Never used for a field the operator types into: the inline
// scratch-sum syntax ("527+588+100=1215") has to survive untouched.
const setNum = (id, v) => setVal(id, fmt2(v));

let entryId = null; // set after first Save (or on loading an existing day) -> Update = PUT
let calcTimer = null;
let me = null;
let oilLabels = {};

// --------------------------------------------------------------------- build DOM

function blankRow(cells) {
  const tr = document.createElement("tr");
  tr.innerHTML = cells;
  return tr;
}

function buildOilRows() {
  const body = $("oil-rows");
  const ds = $("ds-oil-rows");
  body.innerHTML = "";
  ds.innerHTML = "";
  OIL_KEYS.forEach((k) => {
    body.appendChild(
      blankRow(
        `<td data-oil-label="${k}">${oilLabels[k]}</td>` +
          `<td><input id="${k}-qty" data-calc></td>` +
          // Rate is prefilled from Rate Master but editable, unlike the gas Sell
          // Rate which stays backend-locked: oil rates vary per delivery, the
          // paper sheet records the one that actually applied, and the backend
          // already honours a submitted oil rate over Rate Master. It is also
          // the only way to key a sale for an item whose rate the Owner has not
          // set yet (the two rows added 2026-09-12).
          `<td><input id="${k}-rate" data-calc placeholder="auto (Rate Master) - editable"></td>` +
          // Opening Stock: prefilled from Inventory Tracking but editable - oil
          // sales are handled by only one person a day, so on the OTHER
          // submission there's nothing to correct a stale figure from but a
          // manual entry (short-term fix, 2026-09-11; see IMPLEMENTATION-MAP.md).
          `<td><input id="${k}-opening" data-calc placeholder="auto (Inventory) - override if needed"></td>` +
          `<td><input id="${k}-closing" disabled placeholder="auto"></td>` +
          `<td><input id="${k}-amount" disabled placeholder="auto"></td>` +
          // Retire. Hidden for Sales; the column header is hidden with it so the
          // table does not show an empty trailing column.
          `<td class="oil-admin-cell" hidden>` +
          `<button type="button" class="btn-small secondary" data-retire="${k}" ` +
          `title="Take this item off the form. Days already recorded keep it.">&times;</button>` +
          `</td>`
      )
    );
    ds.appendChild(blankRow(`<td>${oilLabels[k]}</td><td><input id="ds-${k}" disabled></td>`));
  });
  showOilAdmin();
}

// ------------------------------------------------------------- the item list


// Item 2: adding and retiring products moved to Inventory Tracking, so the
// admin column stays hidden here for everyone. The cells are still rendered so a
// saved day that names a retired item keeps its row and its Oil Total.
function showOilAdmin() {
  ["oil-admin-head", "oil-admin-total", "oil-admin-total2"].forEach((id) => {
    if ($(id)) $(id).hidden = true;
  });
  document.querySelectorAll(".oil-admin-cell").forEach((td) => {
    td.hidden = true;
  });
}

async function loadOilItems() {
  const [items, aliases] = await Promise.all([
    api.get("/oil-items"),
    api.get("/oil-items/aliases").catch(() => ({})),
  ]);
  OIL_KEYS = items.map((i) => i.item_key);
  oilLabels = Object.fromEntries(items.map((i) => [i.item_key, i.label]));
  OIL_ALIASES = aliases || {};
}



// Put back a row for any item the saved day names that is no longer on the form -
// a product retired since. It is appended, read-only, and flagged as retired, so
// the day reads as what was actually recorded and its Oil Total still adds up.
function restoreRetiredRows(savedOils) {
  const body = $("oil-rows");
  const ds = $("ds-oil-rows");
  savedOils.forEach((o, i) => {
    const label = String((o && o.label) || "").trim();
    if (!label) return;
    const key = OIL_ALIASES[label] || oilKeyOf(o, i);
    if (!key || OIL_KEYS.includes(key)) return; // still on the form

    OIL_KEYS.push(key);
    oilLabels[key] = label;
    body.appendChild(
      blankRow(
        `<td data-oil-label="${key}">${label} <span class="oil-retired">retired</span></td>` +
          `<td><input id="${key}-qty" disabled></td>` +
          `<td><input id="${key}-rate" disabled></td>` +
          `<td><input id="${key}-opening" disabled></td>` +
          `<td><input id="${key}-closing" disabled></td>` +
          `<td><input id="${key}-amount" disabled></td>` +
          `<td class="oil-admin-cell" hidden></td>`
      )
    );
    ds.appendChild(blankRow(`<td>${label}</td><td><input id="ds-${key}" disabled></td>`));
  });
  showOilAdmin();
}

// Rebuild Oil Sale(s) after the catalogue changes, keeping what is typed in.
// Exported so a future caller (a reload after Inventory Tracking adds an item)
// can use it; nothing on this screen changes the catalogue any more.
export async function refreshOilSection() {
  const typed = Object.fromEntries(
    OIL_KEYS.map((k) => [k, { qty: val(`${k}-qty`), rate: val(`${k}-rate`),
      opening: val(`${k}-opening`) }]),
  );
  await loadOilItems();
  buildOilRows();
  // Prefill FIRST - a new item needs its rate and opening stock from the server -
  // then put the operator's own typing back over the top, or their edits would be
  // silently replaced by Rate Master's figures every time the list changed.
  await loadPrefill();
  for (const [k, v] of Object.entries(typed)) {
    if (!OIL_KEYS.includes(k)) continue;
    if (v.qty !== "") setVal(`${k}-qty`, v.qty);
    if (v.rate !== "") setVal(`${k}-rate`, v.rate);
    if (v.opening !== "") setVal(`${k}-opening`, v.opening);
  }
  refresh();
}

// Every box on these rows is now WIRED. They used to render as bare <input>
// elements with no class, which readForm() had no way to find - so the operator
// typed "Airtel Hari" into a card row, or "Anil/Nani" into a credit row, and the
// app saved the amount and silently dropped the name. It was not stored, not
// exported, not printed back (client, 2026-09-23, from the SEP15 import).
// The station's own dropdown lists, fetched once per load.
//
// Card Holder, Card Type, Creditor and Customer were free text. Typed by hand
// the same customer arrives as "Airtel Hari", "AirTel hari" and "airtel", and
// the Creditor Balance Summary - which groups by name - then reports three
// people each owing a third (client, 2026-09-25).
let optionLists = {};

async function loadOptionLists() {
  try {
    optionLists = await api.get("/daily-trial-balance/options");
  } catch {
    optionLists = {};          // a list that will not load must not stop entry
  }
}

// A <select> backed by a list, and nothing else in the cell: the "+" that used
// to hang under every one of these came off on 2026-09-25. Taking a new customer
// on is the row's "+ New" button now, not the dropdown's.
//
// Falls back to a plain text box if the list could not be fetched - never a
// dead control.
function listCell(cls, listKey, placeholder) {
  const values = optionLists[listKey];
  if (!Array.isArray(values)) {
    return `<td><input class="${cls}" placeholder="${placeholder}"></td>`;
  }
  return `<td><select class="${cls}" data-list="${listKey}">${listOptions(listKey)}</select></td>`;
}

// What a list is called when the strip asks for a new one.
const LIST_NOUN = {
  card_holders: "card holder",
  card_types: "card type",
  customers: "name",
  collectors: "name",
  payment_type: "payment type",
  payment_modes: "payment mode",
  yes_no: "value",
};

function listOptions(listKey, chosen) {
  return ['<option value="">— select —</option>']
    .concat((optionLists[listKey] || []).map(
      (v) => `<option${v === chosen ? " selected" : ""}>${escapeHtml(v)}</option>`))
    .join("");
}

// The one button a repeating row carries, in a column of its own at the end of
// it (client, 2026-09-25: "no more + symbols for sure at the end of each row
// +New"). Six loose "+" buttons under the dropdowns of a three-row section
// become three, in line.
const NEW_CELL = '<td class="rownew">' +
  '<button type="button" class="add-row-btn row-new" title="Add a value to this row’s list">+ New</button>' +
  '<button type="button" class="add-row-btn row-del" title="Remove the selected value from its list">− Delete</button>' +
  "</td>";

// Type: HS or MS, chosen not typed (client, 2026-09-26 - "less keyed-in values
// whenever and whereever possible"). Not one of the managed lists on purpose:
// the station has two nozzles, and a third value added here would carry no rate
// behind it, so applyRateFromFuel would silently leave Rate blank.
//
// "1" and "2" are what the form stored until today, so they are still accepted
// when an older day is opened - see fuelValue().
const FUEL_CELL = (cls) =>
  `<td><select class="${cls}">` +
  '<option value=""></option><option>HS</option><option>MS</option></select></td>';

// An older row holds "1", "2", "1.Diesel" or "Petrol". Map it onto the two
// options this dropdown has, so re-opening SEP15 does not show a blank Type and
// then save the blank back over what was there.
function fuelValue(raw) {
  const v = String(raw == null ? "" : raw).trim().toLowerCase();
  if (!v) return "";
  if (v.startsWith("1") || v.includes("diesel") || v.includes("hs")) return "HS";
  if (v.startsWith("2") || v.includes("petrol") || v.includes("ms")) return "MS";
  return "";
}

const escapeHtml = (v) =>
  String(v == null ? "" : v).replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]
  );

// Choosing "Add new ..." opens this strip on the row it was chosen on: ask for
// the value, save it to the list, select it. Inline because Electron never shows
// window.prompt(), and on the row because that is where the operator is looking.
//
// On a Credit Cards row it asks for the holder name AND the card type together,
// because that is what one new customer brings. Fill one box only to add only
// that one.
function openNewBox(tr) {
  if (tr.nextElementSibling && tr.nextElementSibling.classList.contains("dse-newrow")) return;
  const sel = tr.querySelector("select[data-list]");
  if (!sel) return;
  const listKey = sel.dataset.list;
  const body = tr.closest("tbody");
  const pair = body && body.id === "cc-rows";
  const span = tr.children.length;
  const boxes = pair
    ? '<label>Card holder name <input class="nb-a" placeholder="new name"></label>' +
      '<label>Card type <input class="nb-b" placeholder="new card type"></label>'
    : `<label>New ${LIST_NOUN[listKey] || "value"} <input class="nb-a"></label>`;
  tr.insertAdjacentHTML(
    "afterend",
    `<tr class="dse-newrow"><td colspan="${span}"><div class="dse-newbox">` +
      boxes +
      '<button type="button" class="add-row-btn nb-ok">Add</button>' +
      '<button type="button" class="add-row-btn nb-cancel">Cancel</button>' +
      "</div></td></tr>"
  );
  const row = tr.nextElementSibling;
  row.querySelector(".nb-a").focus();
  const close = () => row.remove();
  row.querySelector(".nb-cancel").addEventListener("click", close);
  row.querySelector(".nb-ok").addEventListener("click", async () => {
    const a = (row.querySelector(".nb-a").value || "").trim();
    const b = pair ? (row.querySelector(".nb-b").value || "").trim() : "";
    if (!a && !b) {
      close();
      return;
    }
    // On a card row the first box is always the holder, whichever dropdown was
    // used to open the strip.
    const jobs = pair
      ? [["card_holders", a], ["card_types", b]]
      : [[listKey, a]];
    for (const [key, value] of jobs) {
      if (!value) continue;
      // Already in the list is not a failure - the operator asked for it to be
      // there and it is there. Only a real error stops the rest of the strip:
      // typing a known customer beside a new card type is the ordinary case, and
      // it used to abort on the customer and never add the card type.
      try {
        await api.post("/daily-trial-balance/options", { list_key: key, value });
      } catch (err) {
        const msg = err && err.message ? String(err.message) : String(err);
        if (/already/i.test(msg)) continue;
        const st = $("save-status");
        st.className = "status-line err";
        st.textContent = `Could not add "${value}" — ${msg}`;
        return;
      }
    }
    await loadOptionLists();
    refreshLists();
    // Whatever the row had selected gives way to what was just added - the
    // operator opened this strip from that row, so that row is what they meant.
    if (a) (pair ? tr.querySelector(".cc-holder") : sel).value = a;
    if (b) tr.querySelector(".cc-type").value = b;
    close();
  });
}

// The column heading above a cell, so the Delete strip can say "Card Type"
// rather than "card_types".
function columnLabel(cell) {
  const table = cell.closest("table");
  const head = table && table.querySelector("tr");
  if (!head) return "this list";
  const th = head.children[cell.cellIndex];
  return th ? (th.textContent || "").trim() || "this list" : "this list";
}

// "- Delete" (client, 2026-09-26). A row can carry five dropdowns, so the button
// cannot guess which value is meant: it opens a strip naming every list on the
// row that has something selected, and the press that removes a value is the
// second press. That doubles as the confirmation - Electron never shows
// window.confirm(), so a destructive action has to be built out of two clicks.
//
// This removes an OPTION, not a RECORD. Saved entries keep the text that was
// chosen, so yesterday's credit still names the person who took it.
function openDeleteBox(tr) {
  if (tr.nextElementSibling && tr.nextElementSibling.classList.contains("dse-newrow")) return;
  const chosen = [...tr.querySelectorAll("select[data-list]")].filter((sel) => sel.value);
  const span = tr.children.length;
  if (!chosen.length) {
    tr.insertAdjacentHTML("afterend",
      `<tr class="dse-newrow"><td colspan="${span}"><div class="dse-newbox dse-delbox">` +
      "Nothing is selected on this row, so there is nothing to remove. Choose a value " +
      "first, then press &minus; Delete." +
      '<button type="button" class="add-row-btn nb-cancel">Close</button>' +
      "</div></td></tr>");
  } else {
    const buttons = chosen.map((sel, i) =>
      `<button type="button" class="add-row-btn del-one" data-i="${i}" ` +
      `data-key="${escapeHtml(sel.dataset.list)}" ` +
      `data-value="${escapeHtml(sel.value)}" ` +
      `data-label="${escapeHtml(columnLabel(sel.closest("td")))}">` +
      `Remove &ldquo;${escapeHtml(sel.value)}&rdquo; from ${escapeHtml(columnLabel(sel.closest("td")))}` +
      "</button>").join("");
    tr.insertAdjacentHTML("afterend",
      `<tr class="dse-newrow"><td colspan="${span}"><div class="dse-newbox dse-delbox">` +
      "<b>Remove which value?</b> It goes from the dropdown for everyone. Entries already " +
      "saved keep the name they were filed under." +
      buttons +
      '<button type="button" class="add-row-btn nb-cancel">Cancel</button>' +
      "</div></td></tr>");
  }
  const row = tr.nextElementSibling;
  const close = () => row.remove();
  row.querySelector(".nb-cancel").addEventListener("click", close);
  for (const btn of row.querySelectorAll(".del-one")) {
    btn.addEventListener("click", async () => {
      const listKey = btn.dataset.key;
      const value = btn.dataset.value;
      const label = btn.dataset.label;
      const st = $("save-status");
      try {
        await api.post("/daily-trial-balance/options/remove", { list_key: listKey, value });
      } catch (err) {
        st.className = "status-line err";
        st.textContent = `Could not remove "${value}" — ${err.message || err}`;
        return;
      }
      await loadOptionLists();
      // Any row that had the removed value selected now has nothing selected,
      // which is the truth: that value no longer exists.
      refreshLists();
      st.className = "status-line ok";
      st.textContent = `Removed "${value}" from ${label}.`;
      close();
    });
  }
}

// A value added anywhere joins every dropdown on that list, not just the one it
// was typed into - otherwise the same customer is entered twice and the Creditor
// Balance Summary, which groups by name, reports two people owing half each.
function refreshLists() {
  for (const sel of document.querySelectorAll("select[data-list]")) {
    const keep = sel.value;
    sel.innerHTML = listOptions(sel.dataset.list, keep);
    sel.value = keep;
  }
}

function addCcRow() {
  const tr = blankRow(
    listCell("cc-holder", "card_holders", "Card holder") +
      listCell("cc-type", "card_types", "Card type") +
      FUEL_CELL("cc-fuel") +
      '<td class="num"><input class="cc-ltrs" data-calc></td>' +
      '<td class="num"><input class="cc-rate"></td>' +
      '<td><input class="cc-receipt"></td>' +
      '<td class="num"><input class="cc-amount" data-calc></td>' +
      NEW_CELL +
      "<td></td>"
  );
  // Same rule as Section 5 (client, 2026-09-24): a swipe is fuel at the pump
  // price, so Rate follows the fuel type rather than being typed again.
  tr.querySelector(".cc-fuel").addEventListener("change", () => {
    applyRateFromFuel(tr, ".cc-fuel", ".cc-rate");
  });
  watchAmountOverride(tr, ".cc-amount");
  $("cc-rows").appendChild(tr);
  return tr;
}
// A row nobody has touched shows an empty Amount, not 0.00. "0.00" on a blank
// row reads as "this swipe was for nothing", which is a different claim from
// "there is no swipe here" - and on a form with spare rows at the bottom it is
// the claim being made on most of them.
function showComputedAmount(el, tr, ltrsSel, rateSel, value) {
  // Deliberately NOT skipped just because the box has focus. Clicking into
  // Amount to see what it says is the most natural thing to do while waiting for
  // it, and a focus guard meant that clicking there was exactly what stopped it
  // ever filling in. dataset.typed already protects real typing - it is set on
  // the first keystroke - so focus alone must not block the figure.
  if (el.dataset.typed === "1") return;
  const ltrs = (tr.querySelector(ltrsSel) || {}).value || "";
  const rate = (tr.querySelector(rateSel) || {}).value || "";
  const empty = ltrs.trim() === "" && rate.trim() === "";
  if (empty || value === undefined || value === null) {
    el.value = "";
    return;
  }
  el.value = fmt2(value);
}

// Clearing an overridden Amount hands it back to the calculation - otherwise
// "delete what I typed" would leave the row stuck on a blank override.
function watchAmountOverride(tr, sel = ".nc-amount") {
  const amt = tr.querySelector(sel);
  amt.addEventListener("input", () => {
    if (amt.value.trim() === "") delete amt.dataset.typed;
    else amt.dataset.typed = "1";
  });
}

function addNcRow() {
  const tr = blankRow(
    listCell("nc-name", "customers", "Creditor") +
      FUEL_CELL("nc-type") +
      '<td class="num"><input class="nc-ltrs" data-calc></td>' +
      '<td class="num"><input class="nc-rate" data-calc></td>' +
      '<td class="num"><input class="nc-amount" data-calc placeholder="auto"></td>' +
      NEW_CELL +
      "<td></td>"
  );
  // Client, 2026-09-24: "Rate should be 1. HS 2. MS by default, same as Section 1
  // Gas Sale(s) rates only." A credit is fuel sold on account - it is the same
  // litres at the same pump price, so the rate is not a free number and re-typing
  // it invites a figure that disagrees with the day's own sale.
  //
  // Typed, not locked: the operator can still override for the odd case, and a
  // rate they have deliberately changed is not overwritten.
  tr.querySelector(".nc-type").addEventListener("change", () => {
    applyCreditRate(tr);
  });
  watchAmountOverride(tr, ".nc-amount");
  $("nc-rows").appendChild(tr);
  return tr;
}

// "1", "1.Diesel", "Diesel" -> the HS rate; "2", "2.Petrol", "Petrol" -> MS.
// Shared by New Credits and Credit Cards so the two cannot drift apart.
// Fill in the Rate on any Section 4 or 5 row that has a Type but no rate yet -
// or whose rate this code put there itself, so a change of fuel still follows.
// A rate the operator typed by hand is never touched.
function applyRatesToWaitingRows() {
  for (const tr of document.querySelectorAll("#cc-rows tr")) {
    if (tr.querySelector(".cc-fuel")) applyRateFromFuel(tr, ".cc-fuel", ".cc-rate");
  }
  for (const tr of document.querySelectorAll("#nc-rows tr")) {
    if (tr.querySelector(".nc-type")) applyCreditRate(tr);
  }
}

function applyRateFromFuel(tr, typeSel, rateSel) {
  const raw = (tr.querySelector(typeSel).value || "").trim().toLowerCase();
  if (!raw) return;
  let rate = null;
  if (raw.startsWith("1") || raw.includes("diesel") || raw.includes("hs")) {
    rate = val("hs-rate");
  } else if (raw.startsWith("2") || raw.includes("petrol") || raw.includes("ms")) {
    rate = val("ms-rate");
  }
  if (rate === null || rate === "") return;
  const cell = tr.querySelector(rateSel);
  // Only fill a blank, or replace a rate this function put there itself - so a
  // deliberate override survives a change of mind about the fuel type.
  if (cell.value === "" || cell.dataset.fromType === "1") {
    cell.value = rate;
    cell.dataset.fromType = "1";
    refresh();
  }
}

function applyCreditRate(tr) {
  applyRateFromFuel(tr, ".nc-type", ".nc-rate");
}
// An extra Expenses row. Unlike the three printed ones its description is typed,
// so the row carries both a description input and an amount - and readForm()
// sends the descriptions alongside the amounts (client, 2026-09-13).
function addExpRow(desc = "", amount = "") {
  const tr = blankRow(
    '<td><input class="exp-desc" placeholder="What was this expense?"></td>' +
      '<td><input class="exp" data-calc></td>'
  );
  tr.querySelector(".exp-desc").value = desc;
  tr.querySelector(".exp").value = amount;
  $("exp-rows").appendChild(tr);
  return tr;
}

// --------------------------------------------------------------- dates (Option B)
//
// Old Credit Given Date reads 09/MAR/2026 rather than Windows' 03/09/2026
// (client, 2026-09-25). A native date input cannot do this - Chromium prints it
// in the host's own format and no page can override that - so the box is text
// and the calendar is the button beside it.
//
// Day first, always. 03/09 on a credit date is March or September depending on
// who is reading it, and that question comes up months later when somebody
// queries the credit; redisplaying every entry as DD/MMM/YYYY is what removes it.
// Whatever is stored and sent stays ISO - this is display only.
const MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];

function parseGivenDate(raw) {
  const text = String(raw == null ? "" : raw).trim();
  if (!text) return null;
  // ISO first: that is what the server sends back.
  const isoMatch = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (isoMatch) {
    return validDate(Number(isoMatch[1]), Number(isoMatch[2]) - 1, Number(isoMatch[3]));
  }
  const m = text.match(/^(\d{1,2})[\s/\-.]+([A-Za-z]{3,}|\d{1,2})[\s/\-.]+(\d{2}|\d{4})$/);
  if (!m) return null;
  const day = Number(m[1]);
  const month = /^\d+$/.test(m[2])
    ? Number(m[2]) - 1
    : MONTHS.indexOf(m[2].slice(0, 3).toUpperCase());
  let year = Number(m[3]);
  if (year < 100) year += 2000;
  return validDate(year, month, day);
}

// Rejects 31/FEB rather than rolling it forward to the 3rd of March.
function validDate(year, month, day) {
  if (month < 0 || month > 11 || day < 1) return null;
  const d = new Date(year, month, day);
  if (d.getFullYear() !== year || d.getMonth() !== month || d.getDate() !== day) return null;
  return d;
}

const showGivenDate = (d) =>
  `${String(d.getDate()).padStart(2, "0")}/${MONTHS[d.getMonth()]}/${d.getFullYear()}`;
const isoGivenDate = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-` +
  `${String(d.getDate()).padStart(2, "0")}`;

// On leaving the box: redisplay a date that parsed, flag one that did not.
// Flagged, never guessed - a date nobody can read is not turned into a date
// somebody made up.
function normaliseGivenDate(input) {
  const raw = input.value.trim();
  if (!raw) {
    input.classList.remove("bad");
    input.title = "";
    return;
  }
  const d = parseGivenDate(raw);
  if (!d) {
    input.classList.add("bad");
    input.title = "Not a date I can read. Try 09/MAR/2026, 9/3/26 or 09-03-2026.";
    return;
  }
  input.classList.remove("bad");
  input.title = "";
  input.value = showGivenDate(d);
}

// The calendar button borrows a real date input for its picker, then writes the
// result back in the station's own format.
function pickGivenDate(btn) {
  const input = btn.parentElement.querySelector(".dse-date");
  if (!input) return;
  const helper = document.createElement("input");
  helper.type = "date";
  helper.style.cssText =
    "position:absolute;opacity:0;pointer-events:none;width:1px;height:1px";
  const existing = parseGivenDate(input.value);
  if (existing) helper.value = isoGivenDate(existing);
  btn.parentElement.appendChild(helper);
  helper.addEventListener("change", () => {
    if (helper.value) {
      const [y, mo, da] = helper.value.split("-").map(Number);
      input.value = showGivenDate(new Date(y, mo - 1, da));
      input.classList.remove("bad");
      // Set programmatically, so tell the form the way a keystroke would - the
      // calc and the unsaved-changes tracker both listen for input.
      input.dispatchEvent(new window.Event("input", { bubbles: true }));
    }
    helper.remove();
  });
  helper.addEventListener("blur", () => setTimeout(() => helper.remove(), 200));
  if (helper.showPicker) {
    try {
      helper.showPicker();
    } catch {
      helper.focus();
    }
  } else {
    helper.focus();
  }
}

function addOcRow() {
  $("oc-rows").appendChild(
    blankRow(
      listCell("oc-customer", "customers", "Customer") +
        '<td class="num"><input class="oc-amount" data-calc></td>' +
        '<td><div class="dse-datecell">' +
          '<input class="oc-given dse-date" placeholder="DD/MMM/YYYY">' +
          '<button type="button" class="add-row-btn cal-btn" title="Pick a date">' +
          "&#128197;</button></div></td>" +
        // How the money came in (client, 2026-09-25). All four are lists, not
        // typed: "Cash" and "cash" and "CASH" are one payment mode, and the
        // moment they are typed they stop being one.
        listCell("oc-payment", "payment_type", "Full / Partial") +
        listCell("oc-remitted", "yes_no", "Remittance entered") +
        listCell("oc-collector", "collectors", "Collected by") +
        listCell("oc-mode", "payment_modes", "Payment mode") +
        NEW_CELL +
        "<td></td>"
    )
  );
}

// ------------------------------------------------------------------- form <-> API

const cellValue = (tr, sel) => {
  const el = tr.querySelector(sel);
  return el ? el.value : "";
};

const givenDateForSave = (raw) => {
  const text = String(raw == null ? "" : raw).trim();
  if (!text) return "";
  const d = parseGivenDate(text);
  return d ? isoGivenDate(d) : text;
};

function readForm() {
  const oils = OIL_KEYS.map((k) => ({
    label: oilLabels[k],
    qty: val(`${k}-qty`),
    rate: val(`${k}-rate`),
    opening: val(`${k}-opening`),
  }));
  return {
    pump_serial: val("pump-serial"),
    pump_status: val("pump-status") || "online",
    shift_date: val("shift-date"),
    entry_mode: entryMode,
    // Item 5: who verified the day and when. Typed into boxes that read back
    // nowhere until 2026-09-24.
    verified_signature: val("verify-signature"),
    verified_date: val("verify-date"),
    last_reading_override: lastReadingOverride,
    hs: { current: val("hs-current"), last: val("hs-last"), rate: val("hs-rate") },
    ms: { current: val("ms-current"), last: val("ms-last"), rate: val("ms-rate") },
    oils,
    expenses: [...document.querySelectorAll(".exp")].map((i) => i.value),
    // Aligned by index with `expenses`. The three printed rows contribute their
    // own fixed label; an added row contributes what was typed into it.
    expense_labels: expenseLabels(),
    credit_card_amounts: [...document.querySelectorAll(".cc-amount")].map(
      (el) => (el.dataset.typed === "1" ? el.value : "")),
    // Index-aligned with the amounts above, like expense_labels with expenses.
    credit_card_rows: [...document.querySelectorAll("#cc-rows tr")].map((tr) => ({
      holder: tr.querySelector(".cc-holder").value,
      card_type: tr.querySelector(".cc-type").value,
      fuel_type: tr.querySelector(".cc-fuel").value,
      ltrs: tr.querySelector(".cc-ltrs").value,
      rate: tr.querySelector(".cc-rate").value,
      receipt: tr.querySelector(".cc-receipt").value,
    })),
    new_credits: [...document.querySelectorAll("#nc-rows tr")].map((tr) => ({
      ltrs: tr.querySelector(".nc-ltrs").value,
      rate: tr.querySelector(".nc-rate").value,
      name: tr.querySelector(".nc-name").value,
      fuel_type: tr.querySelector(".nc-type").value,
      // Blank means "work it out from litres x rate"; a figure means the
      // operator has overridden it and that figure is what the customer owes.
      amount: (() => {
        const el = tr.querySelector(".nc-amount");
        return el.dataset.typed === "1" ? el.value : "";
      })(),
      // The Signature column came off the screen on 2026-09-25, but a signature
      // already on file is not the client's to lose because a column moved - so
      // it rides back out on the row that carried it in.
      signature: tr.dataset.signature || "",
    })),
    old_credit_amounts: [...document.querySelectorAll(".oc-amount")].map((i) => i.value),
    old_credit_rows: [...document.querySelectorAll("#oc-rows tr")].map((tr) => ({
      customer: tr.querySelector(".oc-customer").value,
      // Typed as 09/MAR/2026, stored as 2026-03-09. A date that will not parse
      // is sent as typed rather than dropped, so the server refuses it and the
      // operator is told - silently sending "" would file the credit with no
      // date at all.
      given_date: givenDateForSave(tr.querySelector(".oc-given").value),
      // Client, 2026-09-25. Blank is a real answer on all four - a credit
      // received before these columns existed has none of them, and inventing a
      // default would be inventing a fact about someone's money.
      payment: cellValue(tr, ".oc-payment"),
      remittance_entered: cellValue(tr, ".oc-remitted"),
      collected_by: cellValue(tr, ".oc-collector"),
      payment_mode: cellValue(tr, ".oc-mode"),
      signature: tr.dataset.signature || "",
    })),
    phone_pay_settled: val("pp-settled"),
    phone_pay_unsettled: val("pp-unsettled"),
  };
}

// Every Expenses row's description, in the same order as the amounts: the fixed
// printed text for the first three, the typed text for anything added after.
const isBlankish = (v) => v === null || v === undefined || String(v).trim() === "";

function expenseLabels() {
  const fixed = [...document.querySelectorAll("[data-exp-label]")].map((td) =>
    td.textContent.trim()
  );
  const typed = [...document.querySelectorAll(".exp-desc")].map((i) => i.value.trim());
  return [...fixed, ...typed];
}

// Which oil item a stored/computed row is, by its own label when it has one,
// else by position. Position alone is only safe for a payload the current form
// built - an entry saved before the 2026-09-12 row-order change has its five
// rows in a different sequence. Mirrors resolve_oil_key() in the engine.
function oilKeyOf(row, i) {
  const label = String((row && row.label) || "").trim();
  return (
    OIL_ALIASES[label] ||
    OIL_KEYS.find((k) => oilLabels[k] === label) ||
    OIL_KEYS[i]
  );
}

function applyResult(r) {
  setNum("hs-cons", r.hs.cons);
  setNum("hs-amount", r.hs.amount);
  setNum("ms-cons", r.ms.cons);
  setNum("ms-amount", r.ms.amount);
  setNum("gas-total", r.gas_total);

  r.oils.forEach((o, i) => {
    const k = oilKeyOf(o, i);
    if (!k) return;
    setNum(`${k}-closing`, o.closing);
    setNum(`${k}-amount`, o.amount);
    // Section 8's per-oil quantity is positionally aligned with r.oils, so it
    // rides the same resolution rather than its own index.
    const qty = (r.daily_summary && r.daily_summary.oils) || [];
    if (i < qty.length) setNum(`ds-${k}`, qty[i]);
  });
  setNum("oil-total", r.oil_total);
  setNum("gas-oil-total", r.gas_oil_total);

  setNum("exp-total", r.expenses_total);
  document.querySelectorAll("#cc-rows tr").forEach((tr, i) => {
    showComputedAmount(tr.querySelector(".cc-amount"), tr, ".cc-ltrs", ".cc-rate",
                       (r.credit_card_amounts || [])[i]);
  });
  setNum("cc-total", r.credit_cards_total);
  // Amount is editable now (client, 2026-09-26), so this can no longer simply
  // overwrite it. Two cases it must not tread on:
  //   - the box the operator is typing in, which would reformat "1500" to
  //     "1500.00" mid-keystroke and eat the inline-sum syntax;
  //   - a figure they have deliberately overridden, which the server echoes back
  //     unchanged anyway, so rewriting it only risks the formatting above.
  document.querySelectorAll("#nc-rows tr").forEach((tr, i) => {
    showComputedAmount(tr.querySelector(".nc-amount"), tr, ".nc-ltrs", ".nc-rate",
                       r.new_credit_amounts[i]);
  });
  setNum("nc-total", r.new_credits_total);

  setNum("sum-cash", r.sum_cash);
  setNum("sum-expenses", r.sum_expenses);
  setNum("sum-newcredits", r.sum_new_credits);
  setNum("sum-cc", r.sum_credit_cards);
  setNum("sum-netbal", r.net_bal_hand_off);
  setNum("sum-oldcredit", r.sum_old_credit);

  setNum("ds-hs", r.daily_summary.hs);
  setNum("ds-ms", r.daily_summary.ms);
}

// What /calc accepts is the FORM, not the record: no pump, no date, no entry
// mode. readForm() builds the whole save payload, so those extras have to come
// off before the authoritative recompute - CalcRequest forbids unknown fields
// (deliberately: a mistyped field name once silently dropped Rs 2,525).
//
// Until 2026-09-24 they were sent anyway and /calc answered 422 every time. The
// catch below swallowed it, so the screen quietly ran on the renderer mirror
// alone and nobody saw a thing. The mirror is meant to be a responsive stand-in
// until the engine answers (SDD 6.4/7.3), not the thing you are reading.
const CALC_ONLY_STRIP = [
  "pump_serial", "pump_status", "shift_date", "entry_mode",
  "last_reading_override", "verified_signature", "verified_date",
];

function calcPayload(payload) {
  const out = { ...payload };
  for (const k of CALC_ONLY_STRIP) delete out[k];
  return out;
}

function refresh() {
  const payload = readForm();
  applyResult(mirror.compute(payload)); // instant
  clearTimeout(calcTimer);
  calcTimer = setTimeout(async () => {
    try {
      applyResult(await api.post("/daily-sales-entry/calc", calcPayload(payload)));
      const ok = $("calc-note");
      if (ok) ok.hidden = true;
    } catch (err) {
      // Still not fatal - the mirror's figures are on screen - but no longer
      // invisible. A recompute that never succeeds means the totals you are
      // reading came from the renderer, and that is worth knowing.
      const note = $("calc-note");
      if (note) {
        note.hidden = false;
        note.textContent =
          `Showing locally-calculated totals — the server recompute failed ` +
          `(${err.message || err}). Save will use the server's figures.`;
      }
    }
  }, 250);
}


// Client, 2026-09-14: "we can avoid that pump data Entry only when the pump is
// 2.Repair/Offline. In other two cases, there will be data entry." So Sales Man
// Off still files a report - Current = Last on both nozzles, which is exactly
// how 11CC2012V-OFF was filed on 13 and 14 September.
//
// The state is not cosmetic: testing is 5 litres per nozzle and mandatory, but a
// pump in the workshop is not tested. Two pumps running is 10 litres per fuel,
// one in repair is 5 - the figure this project chased for three days.
const GAS_INPUTS = ["hs-current", "hs-last", "ms-current", "ms-last"];

// Where the numbers on the form came from. "manual" means the operator is typing
// the shift, and Last Shift Reading is the backend's to carry forward. "excel"
// means they came off a sheet the station already filled in, and every figure on
// that sheet is kept exactly as printed (client, 2026-09-18).
let entryMode = "manual";

// Owner-only: unlock the carried Last Shift Reading so it can be corrected.
// Client, 2026-09-23: "12BC4523V-RD does not let me change the last reading ...
// there should be a mechanism to change this number by owner only, or when there
// is a need to reset by owner." A wrong carried reading was otherwise permanent -
// the field is disabled and the backend ignored anything sent for it, so it
// propagated to every later day with no way to correct it from inside the app.
let lastReadingOverride = false;

// The out-of-today date the operator has already confirmed, so they are asked
// once per date rather than on every save.
// The saved day most recently loaded, so it can still be moved after the date
// field changes and entryId is cleared.
let movableEntry = null;

// Set by the first edit after a day is loaded - see offerMove().
let formTouchedSinceLoad = false;

// ---- Owner's reading-reset form ---------------------------------------------
// Client, 2026-09-23: "Define a small owner form where you can reset the last
// reading for both pumps. To open that form you need to have a secret password."
//
// The passphrase is checked SERVER-side, every time. Nothing here decides
// anything: this panel only collects it. A secret a renderer could verify on its
// own is a secret printed inside app.asar for anyone to read.

let resetPass = "";

function resetStatus(msg, kind = "") {
  const el = $("reset-status");
  if (!el) return;
  el.className = `status-line ${kind}`;
  el.textContent = msg;
}

async function openResetPanel() {
  const panel = $("reset-panel");
  panel.hidden = false;
  try {
    const st = await api.get("/owner-reset/status");
    $("reset-setup").hidden = st.configured;
    $("reset-gate").hidden = !st.configured;
  } catch (err) {
    resetStatus(`Could not check the passphrase — ${err.message || err}`, "err");
  }
}

async function setResetPassphrase() {
  const v = $("reset-new-pass").value;
  try {
    await api.post("/owner-reset/secret", { new_passphrase: v });
    $("reset-new-pass").value = "";
    $("reset-setup").hidden = true;
    $("reset-gate").hidden = false;
    resetStatus("Passphrase set. Enter it to open the form.", "ok");
  } catch (err) {
    resetStatus(`${err.message || err}`, "err");
  }
}

async function unlockResetForm() {
  const v = $("reset-pass").value;
  try {
    await api.post("/owner-reset/unlock", { passphrase: v });
    resetPass = v;
    $("reset-pass").value = "";
    $("reset-gate").hidden = true;
    $("reset-body").hidden = false;
    if (!$("reset-date").value) $("reset-date").value = val("shift-date");
    syncResetPump();
    resetStatus("");
    await loadResetHistory();
  } catch (err) {
    resetStatus(`${err.message || err}`, "err");
  }
}

// The reset always targets the pump selected on the form above. Kept in step so
// changing the dropdown while the panel is open cannot re-base the wrong pump.
function syncResetPump() {
  const pump = val("pump-serial");
  const hidden = $("reset-pump");
  const label = $("reset-pump-label");
  if (hidden) hidden.value = pump;
  if (label) label.textContent = `${pump}${PUMP_LABELS[pump] ? ` (${PUMP_LABELS[pump]})` : ""}`;
}

function closeResetForm() {
  // Forget the passphrase on close. Leaving it in memory so the panel "just
  // works" next time is how a second gate quietly becomes one.
  resetPass = "";
  $("reset-body").hidden = true;
  $("reset-gate").hidden = false;
  $("reset-panel").hidden = true;
}

async function loadResetHistory() {
  try {
    const rows = await api.get("/owner-reset/baselines");
    const body = $("reset-history-rows");
    body.innerHTML = "";
    // Built as text nodes, not an HTML string: the reason is free text typed by a
    // person, and it has no business being parsed as markup.
    rows.forEach((r) => {
      const tr = document.createElement("tr");
      [r.effective_date, r.pump_serial, r.hs_last ?? "", r.ms_last ?? "",
        r.reason || "", r.last_updated_by || ""].forEach((v) => {
        const td = document.createElement("td");
        td.textContent = String(v);
        tr.appendChild(td);
      });
      body.appendChild(tr);
    });
  } catch {
    /* the history is a convenience; a failure here must not block a reset */
  }
}

async function applyReset() {
  const body = {
    passphrase: resetPass,
    pump_serial: $("reset-pump").value,
    effective_date: $("reset-date").value,
    hs_last: $("reset-hs").value === "" ? null : Number($("reset-hs").value),
    ms_last: $("reset-ms").value === "" ? null : Number($("reset-ms").value),
    reason: $("reset-reason").value,
  };
  try {
    await api.post("/owner-reset", body);
    resetStatus(
      `Saved. From ${body.effective_date} on, ${body.pump_serial} carries this reading.`,
      "ok"
    );
    $("reset-hs").value = "";
    $("reset-ms").value = "";
    $("reset-reason").value = "";
    await loadResetHistory();
    await loadPrefill(); // the form behind the panel is now out of date
  } catch (err) {
    resetStatus(`${err.message || err}`, "err");
  }
}

function syncOverrideBtn(hasCarry) {
  const btn = $("unlock-last-btn");
  if (!btn) return;
  const isOwner = Boolean(me && me.role === "Owner");
  btn.hidden = !(hasCarry && isOwner);
  const opener = $("reset-open-btn");
  if (opener) opener.hidden = !isOwner;
  btn.textContent = lastReadingOverride ? "Re-lock" : "Unlock (Owner)";
}

function toggleLastReadingOverride() {
  lastReadingOverride = !lastReadingOverride;
  ["hs-last", "ms-last"].forEach((id) => {
    $(id).disabled = !lastReadingOverride;
    if (lastReadingOverride) $(id).placeholder = "Owner override - type the correct reading";
  });
  const status = $("save-status");
  status.className = "status-line";
  status.textContent = lastReadingOverride
    ? "Last Shift Reading unlocked. What you type is saved instead of the carried figure, and the change is recorded in the audit log."
    : "Last Shift Reading locked again - the carried figure will be used.";
  syncOverrideBtn(true);
}

function applyPumpStatus() {
  const status = val("pump-status") || "online";
  const offline = status === "repair";
  const note = $("pump-status-note");
  for (const id of GAS_INPUTS) {
    const el = $(id);
    if (!el) continue;
    // Never fight loadPrefill(), which owns whether Last Shift Reading is
    // editable; only the Current Reading cells are ours to lock.
    if (id.endsWith("-current")) el.disabled = offline;
  }
  for (const el of document.querySelectorAll(".oil-qty, .exp")) el.disabled = offline;
  if (note) {
    note.textContent = offline
      ? "Pump out of service - no readings needed for this pump today"
      : status === "salesman_off"
        ? "Pump works, nobody on it - still file the report, Current = Last"
        : "";
    note.style.color = offline ? "var(--io-red, #c00000)" : "var(--io-blue-dark)";
  }
}

async function loadPrefill() {
  const pump = val("pump-serial");
  $("pump-side-label").textContent = PUMP_LABELS[pump] ? `(${PUMP_LABELS[pump]})` : "";
  applyPumpStatus();
  const params = new URLSearchParams({
    pump_serial: pump,
    shift_date: val("shift-date"),
  });
  const p = await api.get(`/daily-sales-entry/prefill?${params.toString()}`);
  oilLabels = p.oil_labels || oilLabels;
  buildOilRows();

  setVal("hs-last", p.hs_last);
  setVal("ms-last", p.ms_last);
  setVal("hs-rate", p.sell_rate_hs);
  setVal("ms-rate", p.sell_rate_ms);
  // The day's rates arrive from the server, so a row whose Type was chosen
  // before they landed got nothing: applyRateFromFuel reads #hs-rate, finds it
  // empty and gives up, and nothing ever asks it again. Rate then stays blank,
  // Amount cannot compute, and the row looks like the calculation is broken.
  // Now that the rates are here, offer them to every row still waiting.
  applyRatesToWaitingRows();
  OIL_KEYS.forEach((k) => setVal(`${k}-rate`, p.oil_rates ? p.oil_rates[k] : ""));
  OIL_KEYS.forEach((k) => setVal(`${k}-opening`, p.oil_openings ? p.oil_openings[k] : ""));

  // Last Shift Reading is backend-owned (auto-carried) once there IS a prior
  // reading on file. The very first entry for a pump has nothing to carry, so
  // it's left open for manual entry instead of being stuck blank forever.
  const hasCarry = Boolean(p.carried_from);
  // A loaded day starts locked again - an override is a deliberate act each
  // time, not a mode the screen stays in.
  lastReadingOverride = false;
  // A new pump or date means the open reset panel was authorised for a different
  // one. Close it and ask again rather than carrying the unlock across.
  if ($("reset-body") && !$("reset-body").hidden) closeResetForm();
  syncResetPump();
  showShiftDateWarning();
  $("hs-last").disabled = hasCarry;
  $("ms-last").disabled = hasCarry;
  $("hs-last").placeholder = hasCarry ? "auto @ 23:59 IST" : "Enter Last Shift Reading (no prior reading on file)";
  $("ms-last").placeholder = $("hs-last").placeholder;
  syncOverrideBtn(hasCarry);

  // Item 9 (client, 2026-09-24). The carry used to happen silently, which is how
  // a wrong baseline went unnoticed for four days. It still fills the field -
  // re-keying a seven-digit meter reading every shift is exactly how a digit
  // gets dropped, and that error re-bases every later day without announcing
  // itself - but it now SAYS where the number came from, and offers itself as a
  // button so the operator can put it back after an Owner has edited it.
  //
  // The field itself stays locked for everyone but an Owner: client, 2026-09-24,
  // "Last Shift Reading always not editable except owner feature, that stays as
  // is."
  // Client, 2026-09-24: "Last Shift Reading carried from ... - NO NEED OF THIS
  // ONE and NOT REQUIRED." The field is greyed out and stays that way; when it
  // has to change, that is what the Owner reset is for. So the note only speaks
  // up in the one case the operator must act on - no prior reading at all, where
  // the field is open and they have to type it.
  $("carried-note").hidden = hasCarry;
  $("carried-note").textContent = hasCarry
    ? ""
    : "No prior reading for this pump — enter today's Last Shift Reading manually.";
  refresh();
}


// Save / Update / Delete are distinct toolbar actions (not one relabeled button):
// Save is only for a new day, Update only for one already bound to a saved row,
// Delete only for a bound row and only for Manager/Owner (the server already
// enforces this via RBAC on DELETE - this is a UI hint, not the real gate).
function syncButtonState() {
  $("save-btn").disabled = Boolean(entryId);
  $("update-btn").disabled = !entryId;
  const canDelete = Boolean(entryId) && me && (me.role === "Manager" || me.role === "Owner");
  $("delete-btn").hidden = !canDelete;
}

// If this pump + date already has a saved entry, bind to it so Save is a PUT
// (a correction edits that row, it does not stack a second one). With
// { populate: true } the form is filled from the saved record; otherwise the
// current form values are kept (used after an Excel import over an existing
// day).
async function loadExisting({ populate = false } = {}) {
  const pump = val("pump-serial");
  const dateStr = val("shift-date");
  const banner = $("editing-note");
  if (!pump || !dateStr) return;
  let rows;
  try {
    rows = await api.get(
      `/daily-sales-entry?shift_date=${encodeURIComponent(dateStr)}&pump_serial=${encodeURIComponent(pump)}`
    );
  } catch {
    return;
  }
  const row = rows.find((r) => me && r.submitted_by === me.login_name) || rows[0];
  if (!row) {
    entryId = null;
    if (banner) banner.hidden = true;
    // Item 7 (client, 2026-09-24): "Data Date was set to Sep 24th and not able
    // to update to Sep 14th - how to correct it?"
    //
    // Changing the date used to end here: the screen found nothing on the new
    // date, forgot the entry it was editing, and the next Save created a SECOND
    // day - leaving the mis-dated one behind. There was no way to move a day at
    // all. If we were just editing one on this pump, offer to move it.
    offerMove(pump, dateStr);
    syncButtonState();
    return;
  }
  movableEntry = { id: row.id, shift_date: row.shift_date, pump_serial: pump };
  formTouchedSinceLoad = false;
  hideMove();
  entryId = row.id;
  if (populate) {
    // Adopt the saved row's provenance. Re-opening an imported day and pressing
    // Save must not turn it into a manual entry and pull the carry-forward back
    // over the readings that came off the sheet.
    entryMode = row.entry_mode || "manual";
    // pump_status is a column, not part of the payload blob, so it restores here
    // rather than in populateInputs().
    const sel = $("pump-status");
    if (sel) sel.value = row.pump_status || "online";
    applyPumpStatus();
    populateInputs(row.payload);
    applyResult(row.result);
  }
  if (banner) {
    banner.hidden = false;
    banner.textContent =
      `Editing saved entry #${row.id} — by ${row.submitted_by}, last updated ` +
      `${new Date(row.last_updated_at).toLocaleString()}. Use Update to correct it.`;
  }
  syncButtonState();
  if (populate) refresh();
  return row;
}

// Query - retrieve the saved entry for the Shift Date + Pump Serial on screen.
// loadExisting() already does the fetch; this makes it an explicit action and,
// crucially, always says what happened. Silently doing nothing when a day has
// no saved entry is what made saved data look unreachable (client, 2026-09-11).
async function queryCurrent() {
  const status = $("save-status");
  const dateStr = val("shift-date");
  const pump = val("pump-serial");
  if (!dateStr || !pump) {
    status.className = "status-line err";
    status.textContent = "Pick a Shift Date and a Pump Serial# first.";
    return;
  }
  status.className = "status-line";
  status.textContent = "Looking for a saved entry…";
  await loadPrefill();
  const row = await loadExisting({ populate: true });
  if (row) {
    status.className = "status-line ok";
    status.textContent =
      `Loaded saved entry #${row.id} for ${dateStr} — ${pump}, submitted by ` +
      `${row.submitted_by}. Use Update to correct it.`;
  } else {
    status.className = "status-line err";
    status.textContent = `No saved entry for ${dateStr} — ${pump}. Enter it, then Save.`;
  }
}

// Browse saved entries over a date range / pump, so history can be found without
// already knowing the exact date.
async function searchEntries() {
  const status = $("q-status");
  const table = $("q-results");
  const body = $("q-rows");
  const qs = new URLSearchParams();
  if (val("q-from")) qs.set("date_from", val("q-from"));
  if (val("q-to")) qs.set("date_to", val("q-to"));
  if (val("q-pump")) qs.set("pump_serial", val("q-pump"));
  status.className = "status-line";
  status.textContent = "Searching…";
  let rows;
  try {
    rows = await api.get(`/daily-sales-entry?${qs.toString()}`);
  } catch (err) {
    status.className = "status-line err";
    status.textContent = `Search failed — ${err.message || err}`;
    return;
  }
  body.innerHTML = "";
  if (!rows.length) {
    table.hidden = true;
    status.className = "status-line err";
    status.textContent = "No saved entries match those filters.";
    return;
  }
  for (const r of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${r.shift_date}</td><td>${r.pump_serial}</td><td>${r.submitted_by}</td>` +
      `<td style="text-align:right">${fmt2(r.result && r.result.net_bal_hand_off)}</td>` +
      `<td><button type="button" class="export-btn secondary q-open">Open</button></td>`;
    tr.querySelector(".q-open").addEventListener("click", async () => {
      $("shift-date").value = r.shift_date;
      $("pump-serial").value = r.pump_serial;
      await queryCurrent();
    });
    body.appendChild(tr);
  }
  table.hidden = false;
  status.className = "status-line ok";
  status.textContent = `${rows.length} saved entr${rows.length === 1 ? "y" : "ies"} found.`;
}

// The starred fields, and what Save does about each. A star that never stops
// anything is decoration, so these are checked - but the two levels are different
// on purpose (client, 2026-09-13):
//
//   blocking  - a record cannot exist without a date and a pump. Both are always
//               populated on this form, so this can only fire if something has
//               gone wrong.
//   warning   - a reading that is missing is named, and the save still goes
//               through. A shift has to be submittable at the end of the day, and
//               refusing the save outright would just push people to invent a
//               number. Last Shift Reading is backend-owned once a prior day
//               exists (SDD 7.7), so the station's rule for an out-of-service
//               pump is to type that carried figure into Current - verified end
//               to end: the day then records 0 litres, 0 amount, still counts as
//               a submission, and Section 3 pulls the other pump's figures alone.
const REQUIRED_BLOCKING = [
  ["shift-date", "Shift Date"],
  ["pump-serial", "Pump Serial#"],
];
const REQUIRED_WARNING = [
  ["hs-current", "Diesel (HS) Current Reading"],
  ["ms-current", "Petrol (MS) Current Reading"],
  ["hs-last", "Diesel (HS) Last Shift Reading"],
  ["ms-last", "Petrol (MS) Last Shift Reading"],
];

function checkRequired() {
  const warn = $("req-warning");
  const missing = REQUIRED_BLOCKING.filter(([id]) => !String(val(id)).trim());
  if (missing.length) {
    return { blocked: `Cannot save — ${missing.map(([, l]) => l).join(" and ")} is required.` };
  }
  const gaps = REQUIRED_WARNING.filter(([id]) => !String(val(id)).trim()).map(([, l]) => l);
  if (warn) {
    warn.hidden = gaps.length === 0;
    warn.textContent = gaps.length
      ? `Saved with mandatory field(s) blank: ${gaps.join(", ")}. ` +
        "If the pump was out of service, type its Last Shift Reading into " +
        "Current Reading so the day records a zero."
      : "";
  }
  return { blocked: null };
}

// Item 6 (client, 2026-09-24). A day keyed for the 14th was filed under the
// 24th and only surfaced later as "Query cannot find the Sep 14th data". The
// date defaults to today and looks like every other field, so nothing draws the
// eye to the one value the whole day is filed under.
//
// This WARNS, visibly and permanently, rather than interrupting. It deliberately
// does not use window.confirm(): Electron blocks confirm() and prompt(), which
// is how the Trial Balance's "+ New Type" once silently did nothing. A modal
// that never appears is worse than no modal - the save just stops, for no
// visible reason.
function showShiftDateWarning() {
  const bar = $("date-warning");
  if (!bar) return;
  const chosen = val("shift-date");
  const today = new Date().toISOString().slice(0, 10);
  const off = Boolean(chosen) && chosen !== today;
  bar.hidden = !off;
  if (off) {
    bar.textContent =
      `This day will be filed under ${chosen} — not today (${today}). ` +
      `If that is wrong, change Shift Date before saving.`;
  }
}

// ---- Item 7: move a saved day to a different date ---------------------------

function hideMove() {
  const bar = $("move-entry-bar");
  if (bar) bar.hidden = true;
}

function offerMove(pump, newDate) {
  const bar = $("move-entry-bar");
  if (!bar) return;
  // Only when the loaded day's own figures are still on screen. Going back to
  // key a day that was MISSED is the common case (client, 2026-09-24: "if the
  // entry was NOT done for some reason on that day they should be able to go
  // back and do it") - and offering to re-file the previous day in the middle of
  // that is noise at best and a wrong click at worst. The first keystroke means
  // a new day is being entered, and the offer withdraws.
  const can =
    movableEntry && movableEntry.pump_serial === pump &&
    movableEntry.shift_date !== newDate && newDate && !formTouchedSinceLoad;
  bar.hidden = !can;
  if (can) {
    $("move-entry-text").textContent =
      `Entry #${movableEntry.id} is filed under ${movableEntry.shift_date}. ` +
      `Nothing is saved for ${newDate}.`;
    $("move-entry-btn").textContent = `Move it to ${newDate}`;
  }
}

async function moveEntryDate() {
  if (!movableEntry) return;
  const status = $("save-status");
  const target = val("shift-date");
  try {
    const payload = readForm();
    payload.shift_date = target;
    const saved = await api.put(`/daily-sales-entry/${movableEntry.id}`, payload);
    entryId = saved.id;
    movableEntry = { id: saved.id, shift_date: target, pump_serial: saved.pump_serial };
    hideMove();
    status.className = "status-line ok";
    status.textContent = `Moved entry #${saved.id} to ${target}.`;
    await loadExisting({ populate: true });
  } catch (err) {
    status.className = "status-line err";
    status.textContent = `Could not move it — ${err.message || err}`;
  }
}

async function save() {
  const status = $("save-status");
  const gate = checkRequired();
  if (gate.blocked) {
    status.className = "status-line err";
    status.textContent = gate.blocked;
    return;
  }
  const payload = readForm();
  status.className = "status-line";
  status.textContent = "Saving…";
  try {
    const saved = entryId
      ? await api.put(`/daily-sales-entry/${entryId}`, payload)
      : await api.post("/daily-sales-entry", payload);
    const wasEdit = Boolean(entryId);
    entryId = saved.id;
    lastSavedSnapshot = JSON.stringify(payload);
    applyResult(saved.result);
    $("last-updated-by").textContent = saved.last_updated_by;
    $("last-updated-time").textContent = new Date(saved.last_updated_at).toLocaleString();
    const banner = $("editing-note");
    if (banner) {
      banner.hidden = false;
      banner.textContent =
        `Editing saved entry #${saved.id} — last updated ` +
        `${new Date(saved.last_updated_at).toLocaleString()}. Use Update to correct it.`;
    }
    syncButtonState();
    status.className = "status-line ok";
    status.textContent =
      `${wasEdit ? "Updated" : "Saved"} (entry #${saved.id}). Net Bal Hand off ${saved.net_bal_hand_off}.` +
      (saved.summary_note ? ` — ${saved.summary_note}` : "");
  } catch (err) {
    status.className = "status-line err";
    status.textContent =
      err.status === 409
        ? `${err.message} Reload the page for this pump/date to edit it.`
        : `Save failed — ${err.message || err}`;
  }
}

// Clears the operator-entered fields back to a blank new-entry state (used after
// Delete). Last Shift Reading / Rate / Opening Stock stay owned by loadPrefill().
function clearOperatorFields() {
  setVal("hs-current", "");
  setVal("ms-current", "");
  OIL_KEYS.forEach((k) => {
    setVal(`${k}-qty`, "");
    setVal(`${k}-opening`, ""); // loadPrefill() (called right after) refills the default
  });
  ["exp1", "exp2", "exp3"].forEach((id) => setVal(id, ""));
  document.querySelectorAll(".exp-desc").forEach((el) => (el.value = ""));
  // Every cell in the repeating sections, by class rather than by name. Listing
  // them individually is how the card holder and creditor names survived a pump
  // change on 2026-09-24 - a cell added later is a cell this function does not
  // know about, and it carries the previous pump's data with it.
  const ROW_CELLS = [
    ".cc-holder", ".cc-type", ".cc-fuel", ".cc-ltrs", ".cc-rate",
    ".cc-receipt", ".cc-amount",
    ".nc-name", ".nc-type", ".nc-ltrs", ".nc-rate", ".nc-amount",
    ".oc-customer", ".oc-amount", ".oc-given",
    ".oc-payment", ".oc-remitted", ".oc-collector", ".oc-mode",
  ];
  document.querySelectorAll(ROW_CELLS.join(",")).forEach((el) => {
    el.value = "";
    el.classList.remove("bad");
    delete el.dataset.fromType;
    delete el.dataset.typed;
  });
  // Signature came off the screen but still rides on the row, so a pump change
  // must clear it too - otherwise the previous pump's signature is saved against
  // the new one, which is the same defect the list above was written for.
  document.querySelectorAll("#nc-rows tr, #oc-rows tr").forEach((tr) => {
    delete tr.dataset.signature;
  });
  setVal("pp-settled", "");
  setVal("pp-unsettled", "");
}

async function deleteEntry() {
  const status = $("save-status");
  if (!entryId) return;
  if (!window.confirm(`Delete Daily Sales entry #${entryId}? This cannot be undone.`)) return;
  const deletedId = entryId;
  try {
    await api.del(`/daily-sales-entry/${deletedId}`);
    entryId = null;
    entryMode = "manual";
    const banner = $("editing-note");
    if (banner) banner.hidden = true;
    clearOperatorFields();
    await loadPrefill();
    syncButtonState();
    status.className = "status-line ok";
    status.textContent = `Deleted (entry #${deletedId}).`;
  } catch (err) {
    status.className = "status-line err";
    status.textContent = `Delete failed — ${err.message || err}`;
  }
}

// ------------------------------------------------------------------- Excel import/export

function ensureRows(selector, adder, n) {
  while (document.querySelectorAll(selector).length < n) adder();
}

// Overlay the operator-editable fields from an imported payload. Last Shift
// Reading / Rate / Opening Stock are backend-locked, so they are NOT touched
// here - loadPrefill() owns them. Pump Serial / Shift Date are NOT touched
// either - identity always comes from whatever's selected on the form (2026-
// 09-11), never guessed or overridden from an imported document's own content;
// importExcel() surfaces a mismatch note instead of silently switching it.
// Put the Last Shift Readings on the form and leave them editable, in the order
// of authority the client set:
//
//   1. the sheet, if it printed one - it is the source document;
//   2. what the operator typed BEFORE importing - a deliberate act, and the way
//      they said they would work on the remote PC: "before, what I can do is I
//      can really key in the last shift reading, and then you can take the
//      current reading from the Excel" (2026-09-18);
//   3. whatever loadPrefill() left there - the carry-forward.
//
// Leaving this out meant an import silently discarded a reading the operator had
// just keyed in, which is the same class of bug as overwriting the sheet.
function unlockImportedReadings(payload, typed = {}) {
  [["hs-last", payload.hs && payload.hs.last, typed.hs],
    ["ms-last", payload.ms && payload.ms.last, typed.ms]].forEach(
    ([id, fromSheet, fromOperator]) => {
      const blank = (v) => v === undefined || v === null || v === "";
      const value = !blank(fromSheet) ? fromSheet : fromOperator;
      if (blank(value)) return; // nothing better than the carry-forward
      $(id).disabled = false;
      $(id).placeholder = !blank(fromSheet)
        ? "from the imported sheet"
        : "entered before import";
      setVal(id, value);
    }
  );
}

function populateInputs(payload) {
  setVal("hs-current", payload.hs && payload.hs.current);
  setVal("ms-current", payload.ms && payload.ms.current);
  // Last Shift Reading is normally backend-owned (loadPrefill() sets it) - but
  // when there's no carry data yet it's manual input, so a saved manual value
  // needs restoring here too, or reopening the day would show it blank again.
  if (!$("hs-last").disabled) setVal("hs-last", payload.hs && payload.hs.last);
  if (!$("ms-last").disabled) setVal("ms-last", payload.ms && payload.ms.last);

  // Extra Expenses rows are rebuilt from what was saved. The three printed rows
  // are always on the form; anything past them was added by hand and would
  // otherwise come back as a missing amount and a lost description.
  $("exp-rows").innerHTML = "";
  const expAmounts = payload.expenses || [];
  const expLabels = payload.expense_labels || [];
  const FIXED = 3;
  for (let i = FIXED; i < expAmounts.length; i += 1) {
    if (isBlankish(expAmounts[i]) && !String(expLabels[i] || "").trim()) continue;
    addExpRow(expLabels[i] || "", expAmounts[i] ?? "");
  }

  // A day recorded before an item was retired still has a row for it. Put that
  // row back on the form, marked retired, rather than dropping it: without this
  // the screen recomputes the day from the rows it can see and shows a SMALLER
  // Oil Total than the one actually stored - which is precisely the silent change
  // to a past day that retiring-instead-of-deleting exists to prevent.
  restoreRetiredRows(payload.oils || []);

  (payload.oils || []).forEach((o, i) => {
    const k = oilKeyOf(o, i);
    if (!k) return;
    setVal(`${k}-qty`, o.qty);
    // Rate: the sheet's own rate is authoritative for oils (client-confirmed
    // 2026-09-11), so an imported or saved rate overlays Rate Master's default
    // rather than being discarded. A payload with no rate at all leaves
    // loadPrefill()'s default in place.
    if (o.rate !== undefined && o.rate !== null && o.rate !== "") {
      setVal(`${k}-rate`, o.rate);
    }
    // Opening Stock is manually editable (short-term fix, 2026-09-11). A saved
    // entry always has a resolved value here (default or override) and it's
    // restored on reopen; an imported payload that doesn't carry one (OCR, the
    // paper-layout Excel fallback) leaves loadPrefill()'s live default in place
    // instead of wiping it blank.
    if (o.opening !== undefined && o.opening !== null) {
      setVal(`${k}-opening`, o.opening);
    }
  });

  const exp = payload.expenses || [];
  ["exp1", "exp2", "exp3"].forEach((id, i) => setVal(id, exp[i]));

  // `put` keeps a blank where the value is absent, so an older record with no
  // holder/name simply shows an empty box rather than the string "null".
  const put = (el, v) => {
    if (el) el.value = v === undefined || v === null ? "" : v;
  };

  const cards = payload.credit_card_amounts || [];
  const cardRows = payload.credit_card_rows || [];
  ensureRows(".cc-amount", addCcRow, Math.max(cards.length, cardRows.length));
  document.querySelectorAll("#cc-rows tr").forEach((tr, i) => {
    const ccAmt = tr.querySelector(".cc-amount");
    put(ccAmt, cards[i]);
    if (cards[i] !== undefined && cards[i] !== null && String(cards[i]).trim() !== "") {
      ccAmt.dataset.typed = "1";
    } else {
      delete ccAmt.dataset.typed;
    }
    const d = cardRows[i] || {};
    put(tr.querySelector(".cc-holder"), d.holder);
    put(tr.querySelector(".cc-type"), d.card_type);
    put(tr.querySelector(".cc-fuel"), fuelValue(d.fuel_type));
    put(tr.querySelector(".cc-ltrs"), d.ltrs);
    put(tr.querySelector(".cc-rate"), d.rate);
    put(tr.querySelector(".cc-receipt"), d.receipt);
  });

  const ncs = payload.new_credits || [];
  ensureRows("#nc-rows tr", addNcRow, ncs.length);
  document.querySelectorAll("#nc-rows tr").forEach((tr, i) => {
    const n = ncs[i] || {};
    put(tr.querySelector(".nc-ltrs"), n.ltrs);
    put(tr.querySelector(".nc-rate"), n.rate);
    put(tr.querySelector(".nc-name"), n.name);
    put(tr.querySelector(".nc-type"), fuelValue(n.fuel_type));
    const amt = tr.querySelector(".nc-amount");
    if (n.amount !== undefined && n.amount !== null && String(n.amount).trim() !== "") {
      amt.value = n.amount;
      amt.dataset.typed = "1";
    } else {
      delete amt.dataset.typed;
    }
    if (n.signature) tr.dataset.signature = n.signature;
    else delete tr.dataset.signature;
  });

  const ocs = payload.old_credit_amounts || [];
  const ocRows = payload.old_credit_rows || [];
  ensureRows(".oc-amount", addOcRow, Math.max(ocs.length, ocRows.length));
  document.querySelectorAll("#oc-rows tr").forEach((tr, i) => {
    put(tr.querySelector(".oc-amount"), ocs[i]);
    const d = ocRows[i] || {};
    put(tr.querySelector(".oc-customer"), d.customer);
    // Stored ISO, shown DD/MMM/YYYY. Anything that will not parse is shown as it
    // came rather than blanked, so a bad value on file is visible, not hidden.
    const given = parseGivenDate(d.given_date);
    put(tr.querySelector(".oc-given"), given ? showGivenDate(given) : d.given_date);
    put(tr.querySelector(".oc-payment"), d.payment);
    put(tr.querySelector(".oc-remitted"), d.remittance_entered);
    put(tr.querySelector(".oc-collector"), d.collected_by);
    put(tr.querySelector(".oc-mode"), d.payment_mode);
    if (d.signature) tr.dataset.signature = d.signature;
    else delete tr.dataset.signature;
  });

  setVal("verify-signature", payload.verified_signature);
  setVal("verify-date", payload.verified_date);
  setVal("pp-settled", payload.phone_pay_settled);
  setVal("pp-unsettled", payload.phone_pay_unsettled);
}

async function exportExcel() {
  const status = $("save-status");
  if (!entryId) {
    status.className = "status-line";
    status.textContent =
      "Save the entry first. For a readable copy of the day, use Export DSR (PDF).";
    return;
  }
  try {
    const name = await api.download(`/daily-sales-entry/${entryId}/export-excel`, "SVR-DSE.xlsx");
    status.className = "status-line ok";
    status.textContent = `Exported ${name}.`;
  } catch (err) {
    status.className = "status-line err";
    status.textContent = `Export failed — ${err.message || err}`;
  }
}

async function importExcel(file) {
  const status = $("save-status");
  status.className = "status-line";
  status.textContent = "Reading spreadsheet…";
  try {
    // Tells the backend which sheet to read if the workbook has more than one
    // (e.g. a single file with both a Road and an Office sheet) - it never
    // decides identity, only which sheet to look at (SDD, "everything is keyed
    // by Pump Serial Number" - confirmed 2026-09-11).
    const pumpQS = `?pump_serial=${encodeURIComponent(val("pump-serial"))}`;
    // Captured before loadPrefill() runs, because that is what overwrites them.
    const typedLast = { hs: val("hs-last"), ms: val("ms-last") };
    const res = await api.upload(`/daily-sales-entry/import-excel${pumpQS}`, file);
    entryId = null;

    // Identity (Pump Serial + Shift Date) always comes from what's selected on
    // the form right now - never guessed or switched from the file's own
    // metadata (matches how Scan/Upload already behaves). A keyed SVR export/
    // template still carries its own meta.pump_serial/shift_date, so flag a
    // mismatch instead of silently acting on it either way.
    const notes = [];
    if (res.meta && res.meta.pump_serial && res.meta.pump_serial !== val("pump-serial")) {
      notes.push(
        `this file was exported for pump ${res.meta.pump_serial} — importing into ` +
          `${val("pump-serial")} instead (change the dropdown first if that's wrong)`
      );
    }
    if (res.meta && res.meta.shift_date && res.meta.shift_date !== val("shift-date")) {
      notes.push(
        `this file was exported for ${res.meta.shift_date} — importing into ${val("shift-date")} instead`
      );
    }

    await loadPrefill(); // rebuild oil rows + lock rates/readings for the selected pump+date
    entryMode = "excel";
    populateInputs(res.payload); // then overlay the imported inputs (never identity)
    // The sheet is the source document, so its Last Shift Reading stands. Left to
    // itself loadPrefill() has just DISABLED these two fields and filled them with
    // the carry-forward, and populateInputs skips a disabled field - which is how
    // the SEP15 road sheet's 1,489,759.27 was replaced by 267,841.93 from an
    // unrelated day, turning 284.48 litres into 1,222,201.82 (remote PC,
    // 2026-09-18). Unlocked as well as filled, because ADR-5 says the operator
    // reviews an imported value before saving, and they cannot review a field
    // they cannot reach.
    unlockImportedReadings(res.payload, typedLast);
    await loadExisting(); // if that day already has an entry, Save updates it
    refresh();
    notes.push(...(res.warnings || []));
    status.className = notes.length ? "status-line" : "status-line ok";
    status.textContent = notes.length
      ? `Imported with ${notes.length} note(s): ${notes.join(" | ")} — review, then Save.`
      : "Imported — review the values, then Save.";
  } catch (err) {
    status.className = "status-line err";
    status.textContent = `Import failed — ${err.message || err}`;
  }
}

// Print. In the packaged Electron app this renders the page to an A4 PDF and
// opens a real preview window (Electron's window.print() shows no preview pane
// on Windows). In a plain browser - and in the Playwright page-mode tests -
// there is no bridge, so it falls back to window.print(), whose Chromium dialog
// has its own preview.
async function printSheet() {
  if (window.svr && typeof window.svr.printPreview === "function") {
    try {
      await window.svr.printPreview();
      return;
    } catch (err) {
      const status = $("save-status");
      status.className = "status-line err";
      status.textContent = `${err.message || err} — falling back to the system print dialog.`;
    }
  }
  window.print();
}

// Scan / Upload (OCR) was removed from this screen on 2026-09-11 at the client's
// request - stock Tesseract never read the station's handwriting reliably, and
// for a typed document Import from Excel reads every section while the OCR path
// only ever covered gas readings plus three summary lines. The backend
// /daily-sales-entry/ocr endpoint is left in place for now; retiring it also
// means unbundling Tesseract from the installer (~175 MB), which is its own
// change.

// --------------------------------------------------------------------------- init

function wireToggles() {
  document.querySelectorAll(".theme-toggle button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const map = { red: "#e31e24", blue: "#0033a0", orange: "#f37022" };
      document.documentElement.style.setProperty("--io-accent", map[btn.dataset.accent]);
      document.querySelectorAll(".theme-toggle button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
    });
  });
  document.querySelectorAll(".lang-toggle button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const lang = btn.dataset.lang;
      document.querySelectorAll(".tt").forEach((el) => {
        el.textContent = el.dataset[lang] || el.textContent;
      });
      document.querySelectorAll(".lang-toggle button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
    });
  });
}

// Print & Sync (Manager/Owner only, 2026-09-11): syncs Inventory Tracking's
// Oil Sale(s) Opening Stock from the most recent real Closing Stock recorded
// (station-wide, not per pump - see inventory.sync_from_daily_sales), then
// carries yesterday's Current Reading into today's Last Shift Reading as
// usual (loadPrefill), then prints a blank form for the given pump.
// ---- The station's own DSR form, blank or filled -----------------------------
// One layout for both (client, 2026-09-23: "always the same format"), drawn from
// their reference blank rather than by printing the data-entry screen. See
// lib/dsr-form.js - every coordinate in it is measured from that PDF.

function dsrFileName(pumpSerial, shiftDate) {
  return `SVR_DSR_${pumpSerial}_${shiftDate || "blank"}`;
}

// Has the form changed since it was last saved? Compared as the payload that
// would be sent, so a reformatted number does not count as an edit.
let lastSavedSnapshot = null;
function formIsDirty() {
  try {
    return JSON.stringify(readForm()) !== lastSavedSnapshot;
  } catch {
    return true; // if it cannot be compared, assume it needs saving
  }
}

async function showDsrForm(filled) {
  const status = $("save-status");
  const pump = val("pump-serial");
  const shiftDate = val("shift-date");
  let data = null;

  if (filled) {
    // Item 4 (client, 2026-09-24): "Print is not working as data entered."
    //
    // It printed only what was SAVED, on the reasoning that a printed form is a
    // record and a record that contradicts the database is worse than none. That
    // reasoning still holds - but the operator has just keyed a day, pressed
    // Print, and expects to see it. So save first, then print: the expected
    // result, and the form and the record can never disagree.
    if (!entryId || formIsDirty()) {
      await save();
      if (!entryId) return; // save refused - its own message is on screen
    }
    try {
      const rows = await api.get(
        `/daily-sales-entry?shift_date=${encodeURIComponent(shiftDate)}` +
          `&pump_serial=${encodeURIComponent(pump)}`
      );
      data = rows && rows[0];
      if (!data) {
        status.className = "status-line err";
        status.textContent =
          `Nothing saved for ${pump} on ${shiftDate} - save the day first, or use Print Blank DSR.`;
        return;
      }
    } catch (err) {
      status.className = "status-line err";
      status.textContent = `Could not read the day - ${err.message || err}`;
      return;
    }
  } else {
    // A blank still carries yesterday's Current Reading as Last Shift, so the
    // operator only writes today's - which is the whole point of printing it
    // from the system rather than photocopying a pad.
    data = {
      payload: {
        hs: { last: val("hs-last"), rate: val("hs-rate") },
        ms: { last: val("ms-last"), rate: val("ms-rate") },
        oils: OIL_KEYS.map((k) => ({
          label: oilLabels[k],
          rate: val(`${k}-rate`),
          opening: val(`${k}-opening`),
        })),
      },
      result: {},
    };
  }

  $("dsr-preview-body").innerHTML = renderDsrForm({
    pumpSerial: pump,
    pumpLabel: PUMP_LABELS[pump],
    shiftDate,
    data,
  });
  $("dsr-preview-title").textContent =
    `${filled ? "Filled" : "Blank"} - ${dsrFileName(pump, shiftDate)}.pdf`;
  $("dsr-preview").hidden = false;
  document.body.classList.add("dsr-mode");
  status.className = "status-line ok";
  status.textContent = "Check the form, then Print / Save PDF.";
}

function closeDsrPreview() {
  $("dsr-preview").hidden = true;
  document.body.classList.remove("dsr-mode");
}

async function printDsr() {
  // `dsr-mode` on <body> is what the print stylesheet keys off, so the page that
  // reaches the printer is the form alone - not the form plus the screen.
  const name = dsrFileName(val("pump-serial"), val("shift-date"));
  if (window.svr && typeof window.svr.printPreview === "function") {
    try {
      await window.svr.printPreview(name);
      return;
    } catch {
      /* fall through to the browser dialog */
    }
  }
  window.print();
}

async function syncAndPrint(pumpSerial) {
  const status = $("save-status");
  status.className = "status-line";
  status.textContent = "Syncing Inventory…";
  try {
    const qs = `?shift_date=${encodeURIComponent(val("shift-date"))}`;
    const summary = await api.post(`/daily-sales-entry/sync-inventory${qs}`);

    $("pump-serial").value = pumpSerial;
    setVal("hs-current", "");
    setVal("ms-current", "");
    await loadPrefill();

    const changes = Object.entries(summary);
    status.className = "status-line ok";
    status.textContent = changes.length
      ? `Synced Inventory from ${changes[0][1].source_date} (${changes
          .map(([key, c]) => `${key}: ${c.from} → ${c.to}`)
          .join(", ")}). Printing…`
      : "Inventory already up to date (nothing new to sync). Printing…";
    await printSheet();
  } catch (err) {
    status.className = "status-line err";
    status.textContent = `Sync failed — ${err.message || err}`;
  }
}

async function init() {
  if (!getToken()) {
    window.location.href = "../../index.html";
    return;
  }
  $("shift-date").value = new Date().toISOString().slice(0, 10);
  // BEFORE the first rows are built - listCell() renders a plain text box when
  // the list is not there yet, and those rows would keep it for the session.
  await loadOptionLists();
  addCcRow();
  addCcRow();
  addNcRow();
  addNcRow();
  addOcRow();
  addOcRow();

  try {
    me = await api.me();
    setVal("ds-name", me.full_name);
    setVal("mgr-name", me.full_name);
    setVal("verify-name", me.full_name);
  } catch {
    window.location.href = "../../index.html";
    return;
  }

  // Both of these have to be known before the oil rows are built: the list
  // supplies the rows, and the role decides whether the retire column exists.
  try {
    await loadOilItems();
  } catch {
    /* leave Oil Sale(s) empty rather than half-built; loadPrefill retries */
  }
  buildOilRows();

  // Print & Sync writes to Inventory Tracking (Manager/Owner only, same access
  // as that module itself) - a Sales user still has plain Print Blank.
  const canSync = me.role === "Manager" || me.role === "Owner";
  document.querySelectorAll("[data-sync]").forEach((btn) => {
    btn.hidden = !canSync;
  });

  wireToggles();

  document.body.addEventListener("input", (e) => {
    if (e.target.matches("[data-calc]")) refresh();
  });
  const reload = async () => {
    entryId = null;
    // Clear what the operator typed for the PREVIOUS pump/date first.
    //
    // Client, 2026-09-24: "when the second pump is selected to enter the data
    // the form data is not cleared ... had to clean up all rows and columns
    // manually." That is not only tedious - the Road pump's figures sat on the
    // Office pump's form, one Save away from being filed under the wrong pump,
    // and every total on screen was the wrong pump's until they were cleared.
    //
    // loadExisting({populate:true}) below puts a saved day back if there is one,
    // so nothing real is lost: this only discards an unsaved draft for a
    // pump/date the operator has just navigated away from.
    clearOperatorFields();
    await loadPrefill();
    await loadExisting({ populate: true }); // open the saved entry for this pump+date, if any
  };
  $("pump-serial").addEventListener("change", reload);
  $("pump-status").addEventListener("change", applyPumpStatus);
  $("shift-date").addEventListener("input", showShiftDateWarning);
  $("shift-date").addEventListener("change", reload);
  // Delegated: rows come and go, so binding per row would miss every later one.
  document.addEventListener("click", (e) => {
    const cal = e.target.closest(".cal-btn");
    if (cal) {
      pickGivenDate(cal);
      return;
    }
    const rowNew = e.target.closest(".row-new");
    if (rowNew) {
      openNewBox(rowNew.closest("tr"));
      return;
    }
    const rowDel = e.target.closest(".row-del");
    if (rowDel) openDeleteBox(rowDel.closest("tr"));
  });
  // Redisplay a typed date when the box is left. Capture phase: blur does not
  // bubble.
  document.addEventListener(
    "blur",
    (e) => {
      if (e.target.matches && e.target.matches(".dse-date")) normaliseGivenDate(e.target);
    },
    true
  );
  document.querySelectorAll("[data-add]").forEach((btn) => {
    btn.addEventListener("click", () => {
      ({ cc: addCcRow, nc: addNcRow, oc: addOcRow, exp: addExpRow })[btn.dataset.add]();
      refresh();
    });
  });

  $("query-btn").addEventListener("click", queryCurrent);
  $("browse-btn").addEventListener("click", () => {
    const panel = $("browse-panel");
    panel.hidden = !panel.hidden;
    if (!panel.hidden && !val("q-from")) {
      // Default the range to the month around the day on screen, so Search is
      // useful on the first click rather than returning everything.
      const d = val("shift-date") || new Date().toISOString().slice(0, 10);
      const from = new Date(d);
      from.setDate(from.getDate() - 30);
      $("q-from").value = from.toISOString().slice(0, 10);
      $("q-to").value = d;
    }
  });
  $("q-search-btn").addEventListener("click", searchEntries);

  $("save-btn").addEventListener("click", save);
  $("update-btn").addEventListener("click", save); // same request logic; buttons differ by when they're enabled
  $("delete-btn").addEventListener("click", deleteEntry);
  const unlockBtn = $("unlock-last-btn");
  if (unlockBtn) unlockBtn.addEventListener("click", toggleLastReadingOverride);
  const on = (id, fn) => {
    const el = $(id);
    if (el) el.addEventListener("click", fn);
  };
  on("reset-open-btn", openResetPanel);
  on("reset-set-btn", setResetPassphrase);
  on("reset-unlock-btn", unlockResetForm);
  on("reset-apply-btn", applyReset);
  on("reset-close-btn", closeResetForm);
  $("print-btn").addEventListener("click", printSheet);
  const onId = (id, fn) => {
    const el = $(id);
    if (el) el.addEventListener("click", fn);
  };
  onId("move-entry-btn", moveEntryDate);
  // Any edit to the day's own figures means a new day is being keyed, not the
  // loaded one re-filed.
  document.addEventListener("input", (e) => {
    const t = e.target;
    if (!t || t.id === "shift-date" || t.id === "pump-serial") return;
    if (t.closest && t.closest(".sheet")) {
      formTouchedSinceLoad = true;
      hideMove();
    }
  });
  onId("export-dsr-btn", () => showDsrForm(true));
  onId("dsr-blank-btn", () => showDsrForm(false));
  onId("dsr-filled-btn", () => showDsrForm(true));
  onId("dsr-print-btn", printDsr);
  onId("dsr-close-btn", closeDsrPreview);
  document.querySelectorAll("[data-blank]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      $("pump-serial").value = btn.dataset.blank;
      setVal("hs-current", "");
      setVal("ms-current", "");
      await loadPrefill();
      await printSheet();
    });
  });
  document.querySelectorAll("[data-sync]").forEach((btn) => {
    btn.addEventListener("click", () => syncAndPrint(btn.dataset.sync));
  });
  const xlsxInput = document.createElement("input");
  xlsxInput.type = "file";
  xlsxInput.accept =
    ".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
  xlsxInput.style.display = "none";
  document.body.appendChild(xlsxInput);
  xlsxInput.addEventListener("change", () => {
    if (xlsxInput.files[0]) importExcel(xlsxInput.files[0]);
    xlsxInput.value = "";
  });
  $("import-btn").addEventListener("click", () => xlsxInput.click());
  $("export-btn").addEventListener("click", exportExcel);

  await loadPrefill();
  await loadExisting({ populate: true });
}

init();
