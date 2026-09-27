// Credit / Remittance Master (BRD 5.17). Rebuilt 2026-09-27 with Daily Sales
// Entry Sections 5/6's own columns, plus what only this screen needs: Given/
// Paid On dates, who submitted the Daily Sales Entry a row was pulled from,
// Notes, and a Status badge showing how the row got here.
//
// Most rows arrive already filled in - posted the day a Daily Trial Balance
// carrying them is saved (route confirmed 2026-09-27: Daily Sales Entry ->
// Daily Trial Balance -> here, not through Daily Sales Summary). "+ Add row"
// is still here for the rare manual entry: a backfilled day, a correction.

import { api, getToken } from "../../lib/api.js";
import { fmt2 } from "../../lib/format.js";
import {
  createListRowKit, ROW_ACTION_CELL, escapeHtml,
  watchAmountOverride, showComputedAmount,
  parseGivenDate, showGivenDate, givenDateForSave, normaliseGivenDate, pickGivenDate,
} from "../../lib/list-rows.js";

const $ = (id) => document.getElementById(id);
let me = null;

const kit = createListRowKit({
  nouns: {
    customers: "name", collectors: "name",
    credit_payment_modes: "payment mode", payment_modes: "payment mode",
    payment_type: "payment type", yes_no: "value",
  },
  statusEl: () => $("txn-status"),
});

// Type: HS or MS, chosen not typed - the same rule Daily Sales Entry's own
// Section 5 already applies, for the same reason (a fuel credit is litres at
// the pump price, and a third value here would carry no rate behind it).
const fuelCell = (cls, chosen) =>
  `<td><select class="${cls}">` +
  `<option value=""${chosen ? "" : " selected"}></option>` +
  `<option${chosen === "HS" ? " selected" : ""}>HS</option>` +
  `<option${chosen === "MS" ? " selected" : ""}>MS</option></select></td>`;

const dateCell = (cls, value) =>
  `<td><div class="datecell">` +
  `<input class="${cls} dse-date" placeholder="DD/MMM/YYYY" value="${escapeHtml(value || "")}">` +
  `<button type="button" class="add-row-btn cal-btn" title="Pick a date">&#128197;</button>` +
  `</div></td>`;

const STATUS_BADGE = {
  posted_dt: '<span class="cm-badge dt">Posted by DT</span>',
  paid: '<span class="cm-badge paid">Paid</span>',
  cleared: '<span class="cm-badge cleared">Cleared</span>',
  manual: '<span class="cm-badge manual">Manual</span>',
};

// A row already locked (posted, paid, or cleared) never has its own facts
// retyped - the master ledger is the one place left to correct any of them.
const LOCKED_STATUSES = new Set(["posted_dt", "paid", "cleared"]);

function statusCell(cls, d) {
  const badge = STATUS_BADGE[d.status] || STATUS_BADGE.manual;
  // Only a credit that has actually settled offers Clear - an outstanding
  // one is exactly what this screen exists to keep showing (client,
  // 2026-09-27: "once the Payment is entered... it should show Posted as
  // Paid and then should be able to clear").
  const clearBtn = d.status === "paid" && d.id
    ? `<button type="button" class="cm-clear-btn" data-clear="${d.id}">Clear</button>`
    : "";
  return `<td class="${cls}"><div class="cm-status-cell">${badge}${clearBtn}</div></td>`;
}

// An ISO timestamp as the station reads it, in IST (same convention as
// Inventory Tracking's own "Updated On" column).
function stampOf(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return escapeHtml(iso);
  return d.toLocaleString("en-GB", {
    timeZone: "Asia/Kolkata",
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

const updatedCells = (d) =>
  `<td class="cm-upd-on" style="font-size:11px;white-space:nowrap">${stampOf(d.last_updated_at)}</td>` +
  `<td class="cm-upd-by" style="font-size:11px">${escapeHtml(d.last_updated_by || "—")}</td>`;

// After a save, the row's Status/Updated On/By cells have to reflect what
// the server actually recorded (who saved it, when) - a static render from
// data() at page-load time only, with nothing refreshing it afterward,
// would show "—" until the next full reload even though the save itself
// succeeded (client, 2026-09-27: "CM must have Updated On Updated By").
function refreshTrailingCells(tr, statusCls, saved) {
  const statusTd = tr.querySelector(`.${statusCls}`);
  if (statusTd) statusTd.outerHTML = statusCell(statusCls, saved);
  const onTd = tr.querySelector(".cm-upd-on");
  if (onTd) onTd.textContent = stampOf(saved.last_updated_at);
  const byTd = tr.querySelector(".cm-upd-by");
  if (byTd) byTd.textContent = saved.last_updated_by || "—";
}

const trunc2 = (n) => Math.trunc((Number(n) || 0) * 100) / 100;

// ------------------------------------------------------------- Section 1 rows

function creditRowHtml(d = {}) {
  return (
    // "customers" (bare names, e.g. "AirTel Hari") - NOT the "creditors" list,
    // which stores whole phrases ("AirTel Hari New Credit") for Daily Trial
    // Balance's own 3.13 dropdown. This screen, the creditor table, and
    // posting.post_line() all key on the bare name, matching Daily Sales
    // Entry Section 5's own "nc-name" dropdown.
    kit.cell("c-name", "customers", "Creditor") +
    fuelCell("c-type", d.fuel_type) +
    `<td class="num"><input class="c-ltrs" data-calc value="${escapeHtml(d.ltrs ?? "")}"></td>` +
    `<td class="num"><input class="c-rate" data-calc value="${escapeHtml(d.rate ?? "")}"></td>` +
    `<td class="num"><input class="c-amount" data-calc value="${escapeHtml(d.amount ?? "")}"></td>` +
    kit.cell("c-mode", "credit_payment_modes", "Payment mode") +
    dateCell("c-given", d.txn_date ? showGivenDate(parseGivenDate(d.txn_date) || new Date(d.txn_date)) : "") +
    `<td><input class="c-psm" value="${escapeHtml(d.pump_sales_man ?? "")}" ` +
      `${d.status === "posted_dt" ? "disabled" : ""}></td>` +
    `<td><input class="c-note" value="${escapeHtml(d.note ?? "")}" placeholder="optional"></td>` +
    statusCell("c-status", d) +
    updatedCells(d) +
    ROW_ACTION_CELL
  );
}

function addCreditRow(d = {}) {
  const tr = document.createElement("tr");
  tr.dataset.id = d.id || "";
  tr.innerHTML = creditRowHtml(d);
  if (LOCKED_STATUSES.has(d.status)) {
    for (const sel of [".c-name", ".c-type", ".c-ltrs", ".c-rate", ".c-mode", ".c-given"]) {
      const el = tr.querySelector(sel);
      if (el) el.disabled = true;
    }
  }
  const holder = tr.querySelector(".c-name");
  if (holder && d.creditor_name) holder.value = d.creditor_name;
  const amt = tr.querySelector(".c-amount");
  if (d.amount != null && d.amount !== "") amt.dataset.typed = "1";
  watchAmountOverride(amt);
  $("credit-rows").appendChild(tr);
  recalcCredits();
  return tr;
}

function recalcCredits() {
  let total = 0;
  for (const tr of document.querySelectorAll("#credit-rows tr")) {
    const ltrs = tr.querySelector(".c-ltrs");
    const rate = tr.querySelector(".c-rate");
    const amt = tr.querySelector(".c-amount");
    if (!amt.dataset.typed && ltrs && rate && ltrs.value.trim() && rate.value.trim()) {
      amt.value = trunc2(Number(ltrs.value) * Number(rate.value)).toFixed(2);
    }
    showComputedAmount(amt, tr, [".c-ltrs", ".c-rate"], amt.value === "" ? null : Number(amt.value));
    total += trunc2(Number(amt.value) || 0);
  }
  $("credit-total").value = total ? total.toFixed(2) : "";
}

// ----------------------------------------------------------- Section 2 rows

function remittanceRowHtml(d = {}) {
  return (
    kit.cell("r-name", "customers", "Customer") +
    `<td class="num"><input class="r-amount" value="${escapeHtml(d.amount ?? "")}"></td>` +
    dateCell("r-given", d.given_on_date ? showGivenDate(parseGivenDate(d.given_on_date) || new Date(d.given_on_date)) : "") +
    kit.cell("r-payment", "payment_type", "Payment") +
    kit.cell("r-entered", "yes_no", "Remittance entered") +
    kit.cell("r-collector", "collectors", "Collected by") +
    kit.cell("r-mode", "payment_modes", "Payment mode") +
    dateCell("r-paid", d.txn_date ? showGivenDate(parseGivenDate(d.txn_date) || new Date(d.txn_date)) : "") +
    `<td><input class="r-psm" value="${escapeHtml(d.pump_sales_man ?? "")}" ` +
      `${d.status === "posted_dt" ? "disabled" : ""}></td>` +
    `<td><input class="r-note" value="${escapeHtml(d.note ?? "")}" placeholder="optional"></td>` +
    statusCell("r-status", d) +
    updatedCells(d) +
    ROW_ACTION_CELL
  );
}

function addRemittanceRow(d = {}) {
  const tr = document.createElement("tr");
  tr.dataset.id = d.id || "";
  tr.innerHTML = remittanceRowHtml(d);
  if (LOCKED_STATUSES.has(d.status)) {
    for (const sel of [".r-name", ".r-amount", ".r-given", ".r-payment",
                        ".r-entered", ".r-collector", ".r-mode", ".r-paid"]) {
      const el = tr.querySelector(sel);
      if (el) el.disabled = true;
    }
  }
  const name = tr.querySelector(".r-name");
  if (name && d.creditor_name) name.value = d.creditor_name;
  const payment = tr.querySelector(".r-payment");
  if (payment && d.payment) payment.value = d.payment;
  const entered = tr.querySelector(".r-entered");
  if (entered && d.remittance_entered) entered.value = d.remittance_entered;
  const collector = tr.querySelector(".r-collector");
  if (collector && d.collected_by) collector.value = d.collected_by;
  const mode = tr.querySelector(".r-mode");
  if (mode && d.payment_mode) mode.value = d.payment_mode;
  $("remittance-rows").appendChild(tr);
  recalcRemittances();
  return tr;
}

function recalcRemittances() {
  let total = 0;
  for (const tr of document.querySelectorAll("#remittance-rows tr")) {
    const amt = tr.querySelector(".r-amount");
    total += trunc2(Number(amt.value) || 0);
  }
  $("remittance-total").value = total ? total.toFixed(2) : "";
}

// -------------------------------------------------------------- save a row

async function saveCreditRow(tr) {
  const id = tr.dataset.id;
  const body = {
    creditor_name: tr.querySelector(".c-name").value,
    fuel_type: tr.querySelector(".c-type").value || null,
    ltrs: tr.querySelector(".c-ltrs").value || null,
    rate: tr.querySelector(".c-rate").value || null,
    amount: tr.querySelector(".c-amount").value || null,
    payment_mode: tr.querySelector(".c-mode").value || null,
    txn_date: givenDateForSave(tr.querySelector(".c-given").value) || null,
    given_by: tr.querySelector(".c-psm").value || null,
    note: tr.querySelector(".c-note").value || null,
  };
  if (!body.creditor_name) {
    setStatus("err", "Creditor Name is required.");
    return;
  }
  try {
    const saved = id
      ? await api.patch(`/credit-master/transactions/${id}`, { note: body.note })
      : await api.post("/credit-master/credit", body);
    tr.dataset.id = saved.id;
    refreshTrailingCells(tr, "c-status", saved);
    setStatus("ok", "Saved.");
  } catch (err) {
    setStatus("err", `Could not save — ${err.message || err}`);
  }
}

async function saveRemittanceRow(tr) {
  const id = tr.dataset.id;
  const body = {
    creditor_name: tr.querySelector(".r-name").value,
    amount: tr.querySelector(".r-amount").value || null,
    given_on_date: givenDateForSave(tr.querySelector(".r-given").value) || null,
    payment: tr.querySelector(".r-payment").value || null,
    remittance_entered: tr.querySelector(".r-entered").value || null,
    collected_by: tr.querySelector(".r-collector").value || null,
    payment_mode: tr.querySelector(".r-mode").value || null,
    txn_date: givenDateForSave(tr.querySelector(".r-paid").value) || null,
    pump_sales_man: tr.querySelector(".r-psm").value || null,
    note: tr.querySelector(".r-note").value || null,
  };
  if (!body.creditor_name || !body.amount) {
    setStatus("err", "Customer Name and Amount are required.");
    return;
  }
  try {
    const saved = id
      ? await api.patch(`/credit-master/transactions/${id}`, { note: body.note })
      : await api.post("/credit-master/remittance", body);
    tr.dataset.id = saved.id;
    refreshTrailingCells(tr, "r-status", saved);
    setStatus("ok", "Saved.");
    if (!id) {
      // A brand-new remittance may have just settled a matching credit -
      // reload Section 1 so a Paid badge (and Section 3's Outstanding)
      // shows immediately, not only on the next full page load.
      await loadTransactions();
      await loadSummary();
    }
  } catch (err) {
    setStatus("err", `Could not save — ${err.message || err}`);
  }
}

async function clearCreditRow(id) {
  try {
    await api.post("/credit-master/transactions/clear", { ids: [Number(id)] });
    setStatus("ok", "Cleared.");
    await loadTransactions();
  } catch (err) {
    setStatus("err", `Could not clear — ${err.message || err}`);
  }
}

function setStatus(cls, text) {
  const el = $("txn-status");
  el.className = `status-line ${cls}`;
  el.textContent = text;
}

// ------------------------------------------------------------------ loading

async function loadTransactions() {
  $("credit-rows").innerHTML = "";
  $("remittance-rows").innerHTML = "";
  const [credits, remittances] = await Promise.all([
    api.get("/credit-master/transactions?kind=credit"),
    api.get("/credit-master/transactions?kind=remittance"),
  ]);
  for (const row of credits) addCreditRow(row);
  for (const row of remittances) addRemittanceRow(row);
  if (!credits.length) addCreditRow();
  if (!remittances.length) addRemittanceRow();
}

// ------------------------------------------------------------- Section 3

let currentDocsCreditor = null;

async function loadSummary() {
  const params = new URLSearchParams();
  if ($("cs-from").value) params.set("date_from", $("cs-from").value);
  if ($("cs-to").value) params.set("date_to", $("cs-to").value);
  const name = $("cs-name").value.trim();
  const rows = await api.get(`/credit-master/summary?${params.toString()}`);
  const filtered = name
    ? rows.filter((r) => r.creditor_name.toLowerCase().includes(name.toLowerCase()))
    : rows;
  const body = $("summary-rows");
  body.innerHTML = "";
  for (const r of filtered) {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${escapeHtml(r.creditor_name)}</td>` +
      `<td><select class="cs-type" data-name="${escapeHtml(r.creditor_name)}">` +
        `<option value="new"${r.credit_type === "new" ? " selected" : ""}>New</option>` +
        `<option value="old"${r.credit_type === "old" ? " selected" : ""}>Old</option>` +
      `</select></td>` +
      `<td class="num"><input value="${fmt2(r.total_credit)}" disabled></td>` +
      `<td class="num"><input value="${fmt2(r.total_remitted)}" disabled></td>` +
      `<td class="num"><input value="${fmt2(r.outstanding)}" disabled></td>` +
      `<td><input class="cs-note" data-name="${escapeHtml(r.creditor_name)}" ` +
        `value="${escapeHtml(r.note ?? "")}" placeholder="optional"></td>` +
      `<td><button type="button" class="add-row-btn cs-docs-btn" ` +
        `data-name="${escapeHtml(r.creditor_name)}">Documents</button></td>` +
      updatedCells(r) +
      `<td></td>`;
    body.appendChild(tr);
  }
  if (!filtered.length) {
    body.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--io-blue-dark)">' +
      "No creditors match.</td></tr>";
  }
}

async function openDocsPanel(name) {
  currentDocsCreditor = name;
  $("docs-panel-title").textContent = `Documents — ${name}`;
  $("docs-panel").hidden = false;
  $("doc-status").textContent = "";
  await refreshDocs();
}

async function refreshDocs() {
  if (!currentDocsCreditor) return;
  const rows = await api.get(
    `/credit-master/creditors/${encodeURIComponent(currentDocsCreditor)}/documents`
  );
  const body = $("doc-rows");
  body.innerHTML = rows.map((d) =>
    `<tr><td>${escapeHtml((d.uploaded_at || "").slice(0, 10))}</td>` +
    `<td><span class="cm-filepill">${escapeHtml(d.original_name)}</span></td>` +
    `<td>${escapeHtml(d.note || "")}</td><td>${escapeHtml(d.uploaded_by)}</td>` +
    `<td><a href="#" class="doc-view" data-id="${d.id}" ` +
    `data-name="${escapeHtml(d.original_name)}">View</a></td></tr>`
  ).join("") || '<tr><td colspan="5" style="text-align:center">No documents yet.</td></tr>';
}

async function uploadDoc() {
  const file = $("doc-file").files[0];
  if (!file || !currentDocsCreditor) {
    $("doc-status").textContent = "Choose a file first.";
    return;
  }
  $("doc-status").className = "status-line";
  $("doc-status").textContent = "Uploading…";
  try {
    await api.upload(
      `/credit-master/creditors/${encodeURIComponent(currentDocsCreditor)}/documents`,
      file,
      { note: $("doc-note").value || "" },
    );
    $("doc-status").className = "status-line ok";
    $("doc-status").textContent = "Uploaded.";
    $("doc-file").value = "";
    $("doc-note").value = "";
    await refreshDocs();
  } catch (err) {
    $("doc-status").className = "status-line err";
    $("doc-status").textContent = `Upload failed — ${err.message || err}`;
  }
}

// --------------------------------------------------------------------- init

async function init() {
  if (!getToken()) {
    window.location.href = "../../index.html";
    return;
  }
  try {
    me = await api.me();
    $("who").textContent = `${me.full_name} (${me.role})`;
  } catch {
    window.location.href = "../../index.html";
    return;
  }

  // Wired BEFORE the awaited loads below, not after - a click landing while
  // kit.loadLists()/loadTransactions()/loadSummary() are still in flight used
  // to be silently swallowed (the button existed but had no listener yet),
  // which only showed up as a flake under a slow/loaded backend.
  document.getElementById("add-credit-row").addEventListener("click", () => addCreditRow());
  document.getElementById("add-remittance-row").addEventListener("click", () => addRemittanceRow());

  document.body.addEventListener("input", (e) => {
    if (e.target.closest("#credit-rows") && e.target.matches("[data-calc]")) recalcCredits();
    if (e.target.closest("#remittance-rows") && e.target.matches(".r-amount")) recalcRemittances();
  });

  document.body.addEventListener(
    "blur",
    (e) => {
      if (e.target.matches(".dse-date")) normaliseGivenDate(e.target);
      const creditTr = e.target.closest("#credit-rows tr");
      if (creditTr && e.target.matches("input, select")) saveCreditRow(creditTr);
      const remTr = e.target.closest("#remittance-rows tr");
      if (remTr && e.target.matches("input, select")) saveRemittanceRow(remTr);
      if (e.target.matches(".cs-note")) {
        // Creditor-level note - PATCH the creditor record, not a transaction.
        api.patch(`/credit-master/creditors/${encodeURIComponent(e.target.dataset.name)}`,
          { note: e.target.value || null }).catch(() => {});
      }
    },
    true
  );
  document.body.addEventListener("change", (e) => {
    if (e.target.matches(".cs-type")) {
      api.patch(`/credit-master/creditors/${encodeURIComponent(e.target.dataset.name)}`,
        { credit_type: e.target.value }).catch(() => {});
    }
  });

  document.addEventListener("click", (e) => {
    const cal = e.target.closest(".cal-btn");
    if (cal) { pickGivenDate(cal); return; }
    const rowNew = e.target.closest(".row-new");
    if (rowNew) { kit.openNewBox(rowNew.closest("tr")); return; }
    const rowDel = e.target.closest(".row-del");
    if (rowDel) { kit.openDeleteBox(rowDel.closest("tr")); return; }
    const clearBtn = e.target.closest("[data-clear]");
    if (clearBtn) { clearCreditRow(clearBtn.dataset.clear); return; }
    const docsBtn = e.target.closest(".cs-docs-btn");
    if (docsBtn) { openDocsPanel(docsBtn.dataset.name); return; }
    const view = e.target.closest(".doc-view");
    if (view) {
      e.preventDefault();
      api.download(
        `/credit-master/creditors/${encodeURIComponent(currentDocsCreditor)}` +
        `/documents/${view.dataset.id}/file`,
        view.dataset.name,
      );
    }
  });

  $("cs-search-btn").addEventListener("click", loadSummary);
  $("cs-clear-btn").addEventListener("click", () => {
    $("cs-from").value = "";
    $("cs-to").value = "";
    $("cs-name").value = "";
    loadSummary();
  });
  $("cs-add-btn").addEventListener("click", () => { $("cs-newbox").hidden = false; });
  $("cs-new-cancel").addEventListener("click", () => { $("cs-newbox").hidden = true; });
  $("cs-new-save").addEventListener("click", async () => {
    const name = $("cs-new-name").value.trim();
    if (!name) return;
    try {
      await api.post("/credit-master/creditors", {
        name, credit_type: $("cs-new-type").value, note: $("cs-new-note").value || null,
      });
      $("cs-newbox").hidden = true;
      $("cs-new-name").value = "";
      $("cs-new-note").value = "";
      await loadSummary();
    } catch (err) {
      setStatus("err", `Could not add creditor — ${err.message || err}`);
    }
  });
  $("docs-panel-close").addEventListener("click", () => { $("docs-panel").hidden = true; });
  $("doc-upload-btn").addEventListener("click", uploadDoc);

  await kit.loadLists();
  await loadTransactions();
  await loadSummary();
}

init();
