// Daily Trial Balance screen (SDD 5.8 / 9), laid out to match the client's own
// SEP12 tab (docs/01-BRD-Requirement-Gathering/ocr-samples/Trail_balance_12-SEP-2026.xlsx).
//
// Three kinds of cell:
//   * computed by the engine  - Sections 1, 5, 6 (SDD §9 formulas)
//   * pulled                  - Section 2, live from the day's Daily Sales Entries
//   * entered + derived       - Sections 3, 4, 7, 8, 10, 11: the operator types the
//                               INPUTS, the backend adds up the totals between them
//                               and returns them under `computed.derived`
//
// The manual inputs are stored in the record's `manual` block (SDD ADR-1) by a
// dotted path - "section3.onhand" - so the storage contract is unchanged and an
// already-saved record round-trips. No total is ever stored: the client's own
// sheet says "Rest should be calculated Automatically using Excel Formulas", and
// a stored total is a total that can silently disagree with its own inputs.
//
// Section numbering is the STATION'S workbook numbering (1-11). The backend keeps
// the older SDD §9 field names; the two are mapped at the boundary below.
//
// RBAC (maker-checker, ADR-2): Sales is the maker (GET/PUT). Close & Sign Off is
// checker-only (Manager/Owner); its controls are hidden for Sales and the backend
// enforces it independently either way.

import { api, getToken } from "../../lib/api.js";
import { fmt2 } from "../../lib/format.js";
import { SECTIONS } from "./sections.js";

const $ = (id) => document.getElementById(id);
const txt = (id, v) => {
  const el = $(id);
  if (!el) return;
  // Two decimals, never more (client, 2026-09-12). The engine keeps 4 dp
  // internally; what reaches the screen is money, so it reads as money.
  const out = v === null || v === undefined ? "" : fmt2(v);
  if (el.tagName === "INPUT") el.value = out;
  else el.textContent = out || "—";
};

const PUMP_LABELS = { "11CC2012V-OFF": "Office", "12BC4523V-RD": "Road" };
const SIDE_SERIAL = { road: "12BC4523V-RD", office: "11CC2012V-OFF" };

let me = null;
let currentStatus = "draft";
// Dropdown values, from GET /daily-trial-balance/options (migration 0021). Held
// here so "+ New ..." can refresh every rendered <select> at once - Section 4.6
// and 8.6 share the `expenses` list, so a category added in one appears in both.
let OPTIONS = {};
let lastView = null;

function canFinalize() {
  return me && (me.role === "Manager" || me.role === "Owner");
}

const esc = (s) => String(s).replace(/"/g, "&quot;");
const listValues = (key) => OPTIONS[key] || [];

// Two decimals for a figure; anything that is not a number (a name, a date)
// passes through untouched. Blank stays blank.
function money(v) {
  if (v === null || v === undefined || v === "") return "";
  const n = Number(String(v).trim());
  return Number.isFinite(n) ? n.toFixed(2) : String(v);
}

function optionMarkup(key, selected) {
  return ["", ...listValues(key)]
    .map(
      (o) =>
        `<option value="${esc(o)}"${o === selected ? " selected" : ""}>` +
        `${o || "— select —"}</option>`
    )
    .join("");
}

// Add a value to one of the dropdowns. Saved server-side, so it is there
// tomorrow and for everyone - not just this browser session.
async function addOption(listKey, label) {
  const raw = window.prompt(`Add a new ${label}:`);
  if (raw === null || !raw.trim()) return;
  const status = $("save-status");
  try {
    OPTIONS = await api.post("/daily-trial-balance/options", {
      list_key: listKey,
      value: raw.trim(),
    });
    refreshSelects(listKey);
    status.className = "status-line ok";
    status.textContent =
      `"${raw.trim()}" added — on every row from now on, for everyone.`;
  } catch (err) {
    status.className = "status-line err";
    status.textContent = `Could not add it — ${err.message || err}`;
  }
}

// Re-render every <select> bound to a list, keeping what each one had selected.
function refreshSelects(listKey) {
  document.querySelectorAll(`select[data-list="${listKey}"]`).forEach((sel) => {
    const keep = sel.value;
    sel.innerHTML = optionMarkup(listKey, keep);
    sel.value = keep;
  });
}
const hintHtml = (h) =>
  h ? ` <span style="font-weight:400;font-size:10px;color:var(--io-blue-dark)">${h}</span>` : "";

// ------------------------------------------------------- manual-section rendering

function cellFor(sectionKey, spec) {
  // A string is an input the operator fills in; { derived } is calculated and
  // rendered read-only, so a total can never be typed over.
  if (typeof spec === "string") {
    return `<td><input data-manual="${esc(`${sectionKey}.${spec}`)}" style="text-align:right"></td>`;
  }
  return `<td><input data-derived="${esc(spec.derived)}" disabled placeholder="auto"></td>`;
}

function fieldsBlock(sectionKey, block) {
  const title = block.title
    ? `<div style="font-weight:700;font-size:12px;margin:10px 0 4px">${block.title}</div>`
    : "";
  const rows = block.fields
    .map(([no, label, spec, hint]) =>
      `<tr><td>${no ? `${no} ` : ""}${label}${hintHtml(hint)}</td>${cellFor(sectionKey, spec)}</tr>`
    )
    .join("");
  return `${title}<table class="tb-fields"><tr><th>Line</th><th>Amount</th></tr>${rows}</table>`;
}

function rowsBlock(sectionKey, block) {
  const path = `${sectionKey}.${block.key}`;
  const head = block.columns.map((c) => `<th>${c.label}</th>`).join("");
  const listed = block.columns.find((c) => c.optionList);
  const addNew = listed
    ? ` <button type="button" class="add-row-btn tb-inline-btn" ` +
      `data-add-option="${esc(listed.optionList)}" ` +
      `data-add-label="${esc(listed.label.toLowerCase())}">+ New ${listed.label}</button>`
    : "";
  const title = block.title
    ? `<div class="tb-block-title">${block.title}${addNew}</div>`
    : "";
  const note = block.note
    ? `<p style="font-size:11px;color:var(--io-blue-dark);margin:4px 0 0">${block.note}</p>`
    : "";
  const totalRow = block.total
    ? `<tr class="total-row"><td colspan="${block.columns.length - 1}">${block.totalLabel}</td>` +
      `<td><input data-derived="${esc(block.total)}" disabled placeholder="auto"></td><td></td></tr>`
    : "";
  const width = block.wide ? "" : ` tb-rows-${block.columns.length}`;
  const table =
    `<table class="tb-rows${width}"${block.wide ? ' style="min-width:2600px"' : ""}>` +
    `<tr>${head}<th style="width:1%"></th></tr>` +
    `<tbody data-rows="${esc(path)}"></tbody>${totalRow}</table>`;
  return (
    title +
    (block.wide ? `<div style="overflow-x:auto">${table}</div>` : table) +
    `<button type="button" class="add-row-btn" data-add-row="${esc(path)}">+ Add row</button>` +
    note
  );
}

function gridBlock(sectionKey, block) {
  const head = block.columns.map(([, label]) => `<th>${label}</th>`).join("");
  const body = block.rows
    .map(
      ([rowKey, rowLabel]) =>
        `<tr><td>${rowLabel}</td>` +
        block.columns
          .map(([colKey, , kind]) =>
            kind === "derived"
              ? `<td><input data-derived="${esc(`${block.derivedFrom}.${rowKey}.${colKey}`)}" ` +
                `disabled placeholder="auto"></td>`
              : `<td><input data-manual="${esc(`${sectionKey}.${rowKey}_${colKey}`)}" ` +
                `style="text-align:right"></td>`
          )
          .join("") +
        `</tr>`
    )
    .join("");
  const note = block.note
    ? `<p style="font-size:11px;color:var(--io-blue-dark);margin:4px 0 0">${block.note}</p>`
    : "";
  return `<table class="tb-grid"><tr><th></th>${head}</tr>${body}</table>${note}`;
}

function signoffBlock(sectionKey, block) {
  const rows = block.rows
    .map(
      ([key, label]) =>
        `<tr><td>${label}</td><td>` +
        `<select data-manual="${esc(`${sectionKey}.${key}`)}" data-list="${esc(block.optionList)}">` +
        `${optionMarkup(block.optionList, null)}</select></td></tr>`
    )
    .join("");
  const addNew =
    ` <button type="button" class="add-row-btn tb-inline-btn" ` +
    `data-add-option="${esc(block.optionList)}" data-add-label="name">+ New Name</button>`;
  return (
    `<div class="tb-block-title">${block.title}${addNew}</div>` +
    `<table class="tb-fields"><tr><th>Role</th><th>Name</th></tr>${rows}</table>`
  );
}

function buildManualSections() {
  for (const section of SECTIONS) {
    const host = $(`sec-${section.n}`);
    if (!host) continue;
    const hint = section.hint
      ? ` <span style="font-weight:400;font-size:11px">${section.hint}</span>`
      : "";
    let html = `<div class="section-title">${section.n}. ${section.title}${hint}</div>`;
    for (const block of section.blocks) {
      if (block.type === "fields") html += fieldsBlock(section.key, block);
      else if (block.type === "rows") html += rowsBlock(section.key, block);
      else if (block.type === "grid") html += gridBlock(section.key, block);
      else if (block.type === "signoff") html += signoffBlock(section.key, block);
    }
    host.innerHTML = html;
  }
  document.querySelectorAll("[data-add-row]").forEach((btn) => {
    btn.addEventListener("click", () => addRow(btn.dataset.addRow));
  });
  document.querySelectorAll("[data-add-option]").forEach((btn) => {
    btn.addEventListener("click", () =>
      addOption(btn.dataset.addOption, btn.dataset.addLabel)
    );
  });
}

function blockFor(path) {
  for (const section of SECTIONS) {
    for (const block of section.blocks) {
      if (block.type === "rows" && `${section.key}.${block.key}` === path) return block;
    }
  }
  return null;
}

function addRow(path, values = {}) {
  const block = blockFor(path);
  const body = document.querySelector(`[data-rows="${path}"]`);
  if (!block || !body) return;
  const tr = document.createElement("tr");
  tr.innerHTML =
    block.columns
      .map((col) => {
        const v = values[col.key];
        if (col.optionList) {
          return (
            `<td><select data-col="${esc(col.key)}" data-list="${esc(col.optionList)}">` +
            `${optionMarkup(col.optionList, v)}</select></td>`
          );
        }
        const shown = col.key === "given_on" || col.key === "date" ? v : money(v);
        return `<td><input data-col="${esc(col.key)}" value="${shown == null ? "" : esc(shown)}"></td>`;
      })
      .join("") +
    `<td><button type="button" class="add-row-btn" data-del-row style="padding:2px 6px">×</button></td>`;
  tr.querySelector("[data-del-row]").addEventListener("click", () => tr.remove());
  body.appendChild(tr);
  if (currentStatus === "finalized") lockManualInputs(true);
}

function fillManual(manual) {
  const data = manual || {};
  document.querySelectorAll("[data-manual]").forEach((el) => {
    const [sectionKey, fieldKey] = el.dataset.manual.split(".");
    const v = (data[sectionKey] || {})[fieldKey];
    el.value = el.tagName === "SELECT" ? (v == null ? "" : v) : money(v);
  });
  document.querySelectorAll("[data-rows]").forEach((body) => {
    const [sectionKey, blockKey] = body.dataset.rows.split(".");
    body.innerHTML = "";
    const saved = (data[sectionKey] || {})[blockKey];
    const list = Array.isArray(saved) ? saved : [];
    for (const values of list) addRow(body.dataset.rows, values || {});
    // Always leave one empty row to type into, so an untouched block still looks
    // like a form rather than an empty box.
    if (!list.length) addRow(body.dataset.rows);
  });
}

function fillDerived(derived) {
  const dig = (path) =>
    path.split(".").reduce((acc, part) => (acc == null ? acc : acc[part]), derived || {});
  document.querySelectorAll("[data-derived]").forEach((el) => {
    el.value = fmt2(dig(el.dataset.derived));
  });
}

function readManual() {
  const out = {};
  const bucket = (key) => (out[key] = out[key] || {});
  document.querySelectorAll("[data-manual]").forEach((el) => {
    const [sectionKey, fieldKey] = el.dataset.manual.split(".");
    const v = el.value.trim();
    if (v !== "") bucket(sectionKey)[fieldKey] = v;
  });
  document.querySelectorAll("[data-rows]").forEach((body) => {
    const [sectionKey, blockKey] = body.dataset.rows.split(".");
    const rows = [...body.querySelectorAll("tr")]
      .map((tr) => {
        const row = {};
        tr.querySelectorAll("[data-col]").forEach((cell) => {
          const v = cell.value.trim();
          if (v !== "") row[cell.dataset.col] = v;
        });
        return row;
      })
      .filter((row) => Object.keys(row).length > 0); // drop the blank starter rows
    if (rows.length) bucket(sectionKey)[blockKey] = rows;
  });
  return out;
}

function lockManualInputs(locked) {
  document.querySelectorAll("[data-manual], [data-col]").forEach((el) => {
    el.disabled = locked;
  });
  document.querySelectorAll("[data-add-row], [data-del-row]").forEach((btn) => {
    btn.disabled = locked;
  });
}

// ------------------------------------------------------------ Section 2 (pulled)

async function loadDaySales(dateStr) {
  const gas = $("s2-gas-rows");
  const combined = $("s2-combined-rows");
  const oils = $("s2-oil-rows");
  [gas, combined, oils].forEach((el) => (el.innerHTML = ""));
  ["s2-total-ltrs", "s2-oil-subtotal", "s2-daily-total"].forEach((id) => txt(id, null));

  let entries;
  try {
    entries = await api.get(`/daily-sales-entry?shift_date=${encodeURIComponent(dateStr)}`);
  } catch {
    return;
  }
  if (!entries.length) {
    gas.innerHTML =
      '<tr><td colspan="6">No Daily Sales Entry recorded for this date yet.</td></tr>';
    return;
  }

  // Per-pump blocks, in the sheet's order: Road first, then Office, each with its
  // own subtotal - then the combined block. The sheet's own combined header has
  // the two serials the wrong way round (it labels the Road column
  // "11CC2012V-Road"); the pairing here is the confirmed one.
  const bySide = {};
  for (const e of entries) bySide[PUMP_LABELS[e.pump_serial]] = e;

  let grandAmount = 0;
  const perSide = {};
  for (const side of ["Road", "Office"]) {
    const e = bySide[side];
    if (!e) continue;
    const serial = SIDE_SERIAL[side.toLowerCase()];
    gas.appendChild(headerRow(`${serial} (${side})`));
    let subtotal = 0;
    perSide[side] = {};
    for (const fuel of ["hs", "ms"]) {
      const inp = (e.payload || {})[fuel] || {};
      const res = (e.result || {})[fuel] || {};
      const name = fuel === "hs" ? "Diesel (HS-Nz-1)" : "Petrol (MS-Nz-2)";
      subtotal += res.amount || 0;
      perSide[side][fuel] = { cons: res.cons || 0, rate: inp.rate, amount: res.amount || 0 };
      const tr = document.createElement("tr");
      tr.innerHTML =
        `<td>${name}</td><td>${fmt2(inp.current)}</td><td>${fmt2(inp.last)}</td>` +
        `<td>${fmt2(res.cons)}</td><td>${fmt2(inp.rate)}</td><td>${fmt2(res.amount)}</td>`;
      gas.appendChild(tr);
    }
    const sub = document.createElement("tr");
    sub.className = "total-row";
    sub.innerHTML = `<td colspan="5">${serial} Total</td><td>${fmt2(subtotal)}</td>`;
    gas.appendChild(sub);
    grandAmount += subtotal;
  }

  for (const [fuel, label] of [["hs", "Diesel (HS)"], ["ms", "Petrol (MS)"]]) {
    const road = (perSide.Road || {})[fuel] || {};
    const office = (perSide.Office || {})[fuel] || {};
    const total = (road.cons || 0) + (office.cons || 0);
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${label}</td><td>${fmt2(road.cons)}</td><td>${fmt2(office.cons)}</td>` +
      `<td>${fmt2(total)}</td><td>${fmt2(road.rate || office.rate)}</td>` +
      `<td>${fmt2((road.amount || 0) + (office.amount || 0))}</td>`;
    combined.appendChild(tr);
  }

  // Oil rows summed across both pumps, matched on the row's own stored label -
  // the row ORDER changed on 2026-09-12, so position is not safe (oils_by_key).
  const oilTotals = new Map();
  let oilGrand = 0;
  for (const e of entries) {
    const inOils = (e.payload || {}).oils || [];
    ((e.result || {}).oils || []).forEach((o, i) => {
      const label = o.label || (inOils[i] || {}).label;
      if (!label) return;
      const prev = oilTotals.get(label) || { qty: 0, rate: null, open: 0, close: 0, amount: 0 };
      const num = (x) => (isNaN(parseFloat(x)) ? 0 : parseFloat(x));
      prev.qty += num((inOils[i] || {}).qty);
      const rate = num((inOils[i] || {}).rate);
      if (rate) prev.rate = rate;
      prev.open += num((inOils[i] || {}).opening);
      prev.close += num(o.closing);
      prev.amount += o.amount || 0;
      oilTotals.set(label, prev);
    });
    oilGrand += e.oil_total || 0;
  }

  let k = 0;
  for (const [label, o] of oilTotals) {
    k += 1;
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>2.1.${k} ${label}</td><td>${fmt2(o.qty)}</td><td>${fmt2(o.rate)}</td>` +
      `<td>${fmt2(o.open)}</td><td>${fmt2(o.close)}</td><td>${fmt2(o.amount)}</td>`;
    oils.appendChild(tr);
  }
  txt("s2-total-ltrs", fmt2(grandAmount));
  txt("s2-oil-subtotal", fmt2(oilGrand));
  txt("s2-daily-total", fmt2(grandAmount + oilGrand));
}

function headerRow(label) {
  const tr = document.createElement("tr");
  tr.className = "total-row";
  tr.innerHTML = `<td colspan="6">${label}</td>`;
  return tr;
}

// ------------------------------------------------- Section 8: send to management

// Section 8 is the part that leaves the station daily. Two ways out, both real:
// the .xlsx for the record, and a WhatsApp message for the phone.
async function exportSection8() {
  const st = $("s8-send-status");
  st.className = "status-line";
  st.textContent = "Building the file…";
  try {
    const name = await api.download(
      `/daily-trial-balance/${$("tb-date").value}/export-section8`,
      `SVR-Section8-${$("tb-date").value}.xlsx`
    );
    st.className = "status-line ok";
    st.textContent = `Exported ${name}.`;
  } catch (err) {
    st.className = "status-line err";
    st.textContent = `Export failed — ${err.message || err}`;
  }
}

// Opens WhatsApp with the Section 8 figures already typed into the message. It
// does NOT send by itself: there is no WhatsApp Business API account wired up,
// and a button that silently posted nothing would be worse than one that opens
// the real chat for you to press send. The .xlsx is attached by hand if wanted.
async function sendSection8Whatsapp() {
  const st = $("s8-send-status");
  const raw = $("s8-whatsapp").value.trim();
  const number = raw.replace(/[^\d]/g, "");
  if (!number) {
    st.className = "status-line err";
    st.textContent = "Enter the WhatsApp number to send to.";
    return;
  }
  try {
    const res = await api.get(`/daily-trial-balance/${$("tb-date").value}/section8-message`);
    window.open(`https://wa.me/${number}?text=${encodeURIComponent(res.text)}`, "_blank");
    st.className = "status-line ok";
    st.textContent =
      "WhatsApp opened with the Section 8 figures — press send there. " +
      "Attach the Excel export too if management wants the detail.";
  } catch (err) {
    st.className = "status-line err";
    st.textContent = `Could not prepare the message — ${err.message || err}`;
  }
}

// The management snapshot.
//
// This is NOT the on-screen Section 8. Management has been receiving the same
// picture every day for years - green header bands, figures in red, the notes
// beside the lines they belong to, and the Difference / Yes Bank Return / Total
// panel on the right (client sent today's, 2026-09-12). Sending them the app's
// own orange-and-input-boxes version would be sending them something they have
// to re-learn, so the snapshot is rendered in THEIR layout, from the live
// figures, and that is what gets captured.
const inr = (v) => {
  const n = Number(v);
  // en-US grouping on purpose: the sheet management has always received prints
  // 1,861,869.74, not the Indian 18,61,869.74. Match the sheet, not the locale.
  return Number.isFinite(n)
    ? n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : "";
};

function snapLine(label, value, note, opts = {}) {
  const cls = [opts.band ? "snap-band" : "", opts.redLabel ? "snap-red" : ""].join(" ").trim();
  return (
    `<tr class="${cls}"><td>${label}</td>` +
    `<td class="snap-mid">${opts.mid || ""}</td>` +
    `<td class="snap-val">${value === undefined || value === null ? "" : value}</td>` +
    `<td class="snap-note">${note || ""}</td></tr>`
  );
}

function buildSnapshot(view) {
  const manual = view.manual || {};
  const s8 = manual.section8 || {};
  const s4 = manual.section4 || {};
  const d = ((view.computed || {}).derived || {}).section8 || {};
  const d4 = ((view.computed || {}).derived || {}).section4 || {};

  const OVER100 = "#OK Anything Above Rs 100 Call/inform mgmt immediately";
  // "SEPT 12, 12:00 PM IST" - the date it covers plus the time it went out,
  // which is how management reads it. IST explicitly, never the host timezone.
  const day = new Date(`${view.shift_date}T00:00:00`)
    .toLocaleDateString("en-GB", { day: "numeric", month: "short" })
    .toUpperCase();
  const time = new Date().toLocaleTimeString("en-US", {
    timeZone: "Asia/Kolkata", hour: "numeric", minute: "2-digit",
  });
  const stamp = `${day}, ${time} IST`;

  // The right-hand reconciliation panel, printed twice on the real snapshot.
  const panel =
    `<table class="snap-panel">` +
    `<tr><td>Difference Amount</td><td>${inr(d.f5)}</td></tr>` +
    `<tr><td>Yes Bank Return Amount</td><td>${inr(s4.yesbank_return)}</td></tr>` +
    `<tr><td>Total difference</td><td>${inr(d4.total_difference)}</td></tr>` +
    `</table>`;

  let rows = snapLine(
    `8. Daily Management Reporting — ${stamp}`, "", "", { band: true }
  );
  rows += snapLine("8.1 Yesterday's SVR Cash/Book Value", inr(s8.f1));
  rows += snapLine(
    "8.2 Today's Sales After Expenses, Testing and Density Adjustments", inr(s8.f2)
  );
  rows += snapLine("8.3 Projected SVR Cash/Book Value", inr(d.f3),
    "# Duplicate Section for mgmt Reporting 4.Cash Reconcilation");
  rows += snapLine("8.4 Actual Reported SVR Cash/Book Value", inr(s8.f4));
  rows += snapLine("8.5 Difference — Actual Reported Minus Projected", inr(d.f5), OVER100);

  rows += snapLine("Regular Expenses", "", "", { band: true });
  for (const r of s8.regular_expenses || []) {
    rows += snapLine(r.category || "", inr(r.amount));
  }
  rows += snapLine("Total Regular Expenses", inr(d.regular_expenses_total), "", { band: true });

  rows += snapLine("Old Credit Collections [Remove/Update the row above]", "", "", { band: true });
  for (const r of s8.old_credit_collections || []) {
    rows += snapLine(r.type || "", inr(r.amount), "", { mid: "Write to the nxt Col" });
  }

  rows += snapLine(
    "Cash Value Difference — Escalate if Absolute Difference Exceeds ₹100",
    inr(d.f5), OVER100, { redLabel: true }
  );
  rows += snapLine("Today's Actual Reported Trial Balance / SVR Net Worth",
    inr(d.mgmt_actual_networth));
  rows += snapLine("Yesterday's Actual Reported Trial Balance", inr(s8.mgmt_yesterday_tb));
  rows += snapLine("Daily Profit Including 2T Sales", inr(s8.mgmt_profit));
  rows += snapLine("Projected SVR Net Worth", inr(d.mgmt_projected_networth));
  rows += snapLine("Actual Reported SVR Net Worth", inr(d.mgmt_actual_networth));
  rows += snapLine("Difference — Actual Reported Minus Projected", inr(d.mgmt_networth_diff),
    "#Possitive Number is Good could be related to Consump Difference");
  rows += snapLine("Actual Profit all Daily Expenses Rs3300", inr(s8.mgmt_actual_profit), "",
    { redLabel: true });

  for (const [label, key] of [
    ["Prepared by", "prepared_by"],
    ["Verified by", "verified_by"],
    ["Sent to SVR and Bank Statement to Group Email BY", "sent_by"],
  ]) {
    rows += snapLine(
      label,
      `<b class="snap-name">${(s8[key] || "").toUpperCase()}</b>`,
      "",
      { mid: (listValues("staff") || []).slice(0, 3).join("/") }
    );
  }

  return (
    `<div class="snap-wrap"><table class="snap">${rows}</table>` +
    `<div class="snap-side">${panel}${panel}</div></div>`
  );
}

// Snapshot of Section 8 as a picture, copied to the clipboard.
//
// This is the one management actually wants: the block as it looks on screen,
// colours and all, pasted into a WhatsApp chat. There is no WhatsApp Business
// account behind the app and there will not be one, so nothing can post a
// message by itself - what happens in real life is a person opens WhatsApp and
// sends it. Putting the image on the clipboard makes that one Ctrl+V.
//
// A picture, not the .xlsx, because a phone will not open a spreadsheet on the
// road; and captured from the live pixels, not re-drawn, so it cannot disagree
// with what the operator is looking at.
async function snapshotSection8() {
  const st = $("s8-send-status");
  const block = $("s8-snapshot-view");
  if (!lastView) {
    st.className = "status-line err";
    st.textContent = "Load a date first.";
    return;
  }
  // Build management's own layout and show it, so what is captured is what they
  // can see they are about to send.
  block.innerHTML = buildSnapshot(lastView);
  block.hidden = false;

  if (!window.svr || typeof window.svr.captureSection !== "function") {
    st.className = "status-line err";
    st.textContent =
      "Snapshot is shown below. Copying it to the clipboard needs the installed " +
      "SVR app — from a browser tab, screenshot it or use Export Section 8 to Excel.";
    return;
  }
  st.className = "status-line";
  st.textContent = "Capturing…";
  block.scrollIntoView({ block: "start" });
  await new Promise((r) => setTimeout(r, 150)); // let the scroll settle before the capture
  const r = block.getBoundingClientRect();
  try {
    const out = await window.svr.captureSection({
      x: r.left,
      y: r.top,
      width: r.width,
      height: r.height,
      label: $("tb-date").value,
    });
    st.className = "status-line ok";
    st.textContent =
      `Copied to the clipboard — open WhatsApp, pick the chat, press Ctrl+V, send. ` +
      `A copy is saved at ${out.file}.`;
  } catch (err) {
    st.className = "status-line err";
    st.textContent = `Snapshot failed — ${err.message || err}`;
  }
}

// ------------------------------------------------------------------ main render

let lastManual = {};

function render(view) {
  currentStatus = view.status;
  lastView = view;
  lastManual = view.manual || {};
  $("status-tag").textContent = view.status;
  const i = view.inputs;
  $("hs-y").value = i.s1_hs_yesterday ?? "";
  $("hs-c").value = i.s1_hs_current ?? "";
  $("ms-y").value = i.s1_ms_yesterday ?? "";
  $("ms-c").value = i.s1_ms_current ?? "";
  $("cash-bv").value = i.s54_cash_book_value ?? "";
  fillManual(lastManual);
  fillDerived(view.computed.derived);

  for (const f of ["hs", "ms"]) {
    const s = view.computed.section1[f];
    txt(`${f}-diff`, s.diff);
    txt(`${f}-cons`, s.consumption);
    txt(`${f}-cpd`, s.computer_pump_diff);
    txt(`${f}-bl`, s.benefit_loss);
    txt(`${f}-dt`, s.deduct_testing);
    txt(`${f}-sl`, s.stock_ltrs);
    txt(`${f}-sl2`, s.stock_ltrs); // same figure, shown again in Section 5
    txt(`${f}-sa`, s.stock_amount);
  }
  txt("hs-br", view.pulled.buy_rate_hs);
  txt("ms-br", view.pulled.buy_rate_ms);
  txt("s6-total", view.computed.section6.total);
  txt("s7-2", view.computed.section7["7_2_stock_value"]);
  txt("s7-3", view.computed.section7["7_3_total"]);

  // Section 1's Actual Consump is both pumps combined, so the two serials are
  // named here: the mockup's Section 2 had them the wrong way round (Office
  // labelled 12BC4523V-Off, Road labelled 11CC2012V-Road) and nothing on this
  // screen said otherwise. Office is 11CC2012V-OFF, Road is 12BC4523V-RD.
  $("s3-src").textContent =
    view.pulled.s3_source === "daily_sales_summary"
      ? `Section 1's Actual Consump and 2T Sales are pulled from Daily Sales Summary — ` +
        `both pumps combined, 11CC2012V-OFF (Office) + 12BC4523V-RD (Road): ` +
        `HS ${view.pulled.s3_hs_consumption ?? "—"} / MS ${view.pulled.s3_ms_consumption ?? "—"} L.`
      : "No Daily Sales Summary for this date yet — Section 1's Actual Consump is unavailable, so the derived columns stay blank.";

  // ADR-2: this day's system-generated carry-forward link, and the variance/
  // escalation outcome recorded at Close & Sign Off (blank until finalized).
  const carryParts = [];
  if (view.carried_from) carryParts.push(`Carried forward from ${view.carried_from}.`);
  if (view.variance_amount !== null && view.variance_amount !== undefined) {
    carryParts.push(`Difference — Actual Reported Minus Projected: ${view.variance_amount}.`);
  }
  if (view.variance_reason) carryParts.push(`Reason: ${view.variance_reason}`);
  $("carry-info").textContent = carryParts.join(" ");

  const locked = view.status === "finalized";
  for (const id of ["hs-y", "hs-c", "ms-y", "ms-c", "cash-bv"]) {
    $(id).disabled = locked;
  }
  lockManualInputs(locked);
  $("save-btn").disabled = locked;
  if (canFinalize()) {
    $("finalize-btn").disabled = locked;
    $("projected-total").disabled = locked;
    $("finalize-reason").disabled = locked;
  }
  $("body").style.display = "block";
}

function payload() {
  const num = (id) => {
    const n = parseFloat($(id).value);
    return isNaN(n) ? null : n;
  };
  return {
    s1_hs_yesterday: num("hs-y"),
    s1_hs_current: num("hs-c"),
    s1_ms_yesterday: num("ms-y"),
    s1_ms_current: num("ms-c"),
    s54_cash_book_value: num("cash-bv"),
    manual: readManual(),
  };
}

async function load() {
  const st = $("tb-status");
  const wanted = $("tb-date").value;
  try {
    const view = await api.get(`/daily-trial-balance/${wanted}`);
    // Ignore a slow response if the user has since changed the date.
    if ($("tb-date").value !== wanted) return;
    render(view);
    st.textContent = "";
    await loadDaySales(wanted);
  } catch (err) {
    st.className = "status-line err";
    st.textContent = err.message || String(err);
  }
}

async function save() {
  const st = $("save-status");
  try {
    render(await api.put(`/daily-trial-balance/${$("tb-date").value}`, payload()));
    st.className = "status-line ok";
    st.textContent = "Saved; formulas recalculated.";
  } catch (err) {
    st.className = "status-line err";
    st.textContent = `Save failed — ${err.message || err}`;
  }
}

async function finalize() {
  const st = $("finalize-status");
  if (!window.confirm("Close & Sign Off this date's Trial Balance? It cannot be edited afterwards.")) return;
  const projectedRaw = $("projected-total").value.trim();
  const reasonRaw = $("finalize-reason").value.trim();
  const body = {
    projected_total: projectedRaw ? Number(projectedRaw) : null,
    reason: reasonRaw || null,
  };
  try {
    render(await api.post(`/daily-trial-balance/${$("tb-date").value}/finalize`, body));
    st.className = "status-line ok";
    st.textContent = "Closed & Signed Off. Tomorrow's entry has been created and seeded.";
  } catch (err) {
    st.className = "status-line err";
    // A 422 here means the +/-Rs100 threshold was breached with no reason entered
    // (ADR-2 Decision step 1) - err.message already carries the backend's exact
    // variance figure, so the maker/checker can read it and fill in Reason above.
    st.textContent = `Close & Sign Off failed — ${err.message || err}`;
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
  $("tb-date").value = new Date().toISOString().slice(0, 10);
  try {
    OPTIONS = await api.get("/daily-trial-balance/options");
  } catch {
    OPTIONS = {}; // dropdowns render empty rather than the screen failing to load
  }
  buildManualSections();

  if (!canFinalize()) {
    $("role-tag").textContent = "Maker — entry & save only";
    $("finalize-block").style.display = "none";
    $("finalize-fields").style.display = "none";
    $("finalize-btn").style.display = "none";
  } else {
    $("role-tag").textContent = "Checker — can Close & Sign Off";
    $("finalize-btn").addEventListener("click", finalize);
  }

  $("load-btn").addEventListener("click", load);
  $("tb-date").addEventListener("change", load);
  $("save-btn").addEventListener("click", save);
  $("s8-export-btn").addEventListener("click", exportSection8);
  $("s8-whatsapp-btn").addEventListener("click", sendSection8Whatsapp);
  $("s8-snapshot-btn").addEventListener("click", snapshotSection8);
  await load();
}

init();
