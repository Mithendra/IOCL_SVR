// Daily Sales Entry screen. Ported from
// docs/01-BRD-Requirement-Gathering/daily_sales_report_branded.html, with the demo
// functions replaced by loopback-API calls. The backend's /calc result is
// authoritative; calc-mirror only fills the gap between keystroke and response.

import { api, getToken } from "../../lib/api.js";
import * as mirror from "../../lib/calc-mirror.js";

const OIL_KEYS = ["oil1", "oil2", "oil3", "oil4", "oil5"];

const $ = (id) => document.getElementById(id);
const val = (id) => ($(id) ? $(id).value : "");
const setVal = (id, v) => {
  const el = $(id);
  if (el) el.value = v === null || v === undefined ? "" : v;
};

let entryId = null; // set after first Save (or on loading an existing day) -> Update = PUT
let calcTimer = null;
let me = null;
let oilLabels = { ...Object.fromEntries(OIL_KEYS.map((k) => [k, k])) };

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
          `<td><input id="${k}-rate" disabled placeholder="auto (Rate Master)"></td>` +
          // Opening Stock: prefilled from Inventory Tracking but editable - oil
          // sales are handled by only one person a day, so on the OTHER
          // submission there's nothing to correct a stale figure from but a
          // manual entry (short-term fix, 2026-09-11; see IMPLEMENTATION-MAP.md).
          `<td><input id="${k}-opening" data-calc placeholder="auto (Inventory) - override if needed"></td>` +
          `<td><input id="${k}-closing" disabled placeholder="auto"></td>` +
          `<td><input id="${k}-amount" disabled placeholder="auto"></td>`
      )
    );
    ds.appendChild(blankRow(`<td>${oilLabels[k]}</td><td><input id="ds-${k}" disabled></td>`));
  });
}

function addCcRow() {
  $("cc-rows").appendChild(
    blankRow(
      "<td><input></td><td><input></td><td><input></td><td><input></td>" +
        '<td><input class="cc-amount" data-calc></td>'
    )
  );
}
function addNcRow() {
  $("nc-rows").appendChild(
    blankRow(
      "<td><input></td><td><input></td>" +
        '<td><input class="nc-ltrs" data-calc></td>' +
        '<td><input class="nc-rate" data-calc></td>' +
        '<td><input class="nc-amount" disabled placeholder="auto"></td>' +
        "<td><input></td>"
    )
  );
}
function addOcRow() {
  $("oc-rows").appendChild(
    blankRow('<td><input></td><td><input class="oc-amount" data-calc></td><td><input></td><td><input></td>')
  );
}

// ------------------------------------------------------------------- form <-> API

function readForm() {
  const oils = OIL_KEYS.map((k) => ({
    label: oilLabels[k],
    qty: val(`${k}-qty`),
    rate: val(`${k}-rate`),
    opening: val(`${k}-opening`),
  }));
  return {
    pump_serial: val("pump-serial"),
    shift_date: val("shift-date"),
    hs: { current: val("hs-current"), last: val("hs-last"), rate: val("hs-rate") },
    ms: { current: val("ms-current"), last: val("ms-last"), rate: val("ms-rate") },
    oils,
    expenses: [...document.querySelectorAll(".exp")].map((i) => i.value),
    credit_card_amounts: [...document.querySelectorAll(".cc-amount")].map((i) => i.value),
    new_credits: [...document.querySelectorAll("#nc-rows tr")].map((tr) => ({
      ltrs: tr.querySelector(".nc-ltrs").value,
      rate: tr.querySelector(".nc-rate").value,
    })),
    old_credit_amounts: [...document.querySelectorAll(".oc-amount")].map((i) => i.value),
    phone_pay_settled: val("pp-settled"),
    phone_pay_unsettled: val("pp-unsettled"),
    night_cash: val("night-cash"),
  };
}

function applyResult(r) {
  setVal("hs-cons", r.hs.cons);
  setVal("hs-amount", r.hs.amount);
  setVal("ms-cons", r.ms.cons);
  setVal("ms-amount", r.ms.amount);
  setVal("gas-total", r.gas_total);

  r.oils.forEach((o, i) => {
    const k = OIL_KEYS[i];
    if (!k) return;
    setVal(`${k}-closing`, o.closing);
    setVal(`${k}-amount`, o.amount);
  });
  setVal("oil-total", r.oil_total);

  setVal("exp-total", r.expenses_total);
  setVal("cc-total", r.credit_cards_total);
  document.querySelectorAll(".nc-amount").forEach((el, i) => {
    el.value = r.new_credit_amounts[i] ?? "";
  });
  setVal("nc-total", r.new_credits_total);

  setVal("sum-cash", r.sum_cash);
  setVal("sum-expenses", r.sum_expenses);
  setVal("sum-newcredits", r.sum_new_credits);
  setVal("sum-cc", r.sum_credit_cards);
  setVal("sum-netbal", r.net_bal_hand_off);
  setVal("sum-oldcredit", r.sum_old_credit);

  setVal("ds-hs", r.daily_summary.hs);
  setVal("ds-ms", r.daily_summary.ms);
  (r.daily_summary.oils || []).forEach((q, i) => setVal(`ds-${OIL_KEYS[i]}`, q));
}

function refresh() {
  const payload = readForm();
  applyResult(mirror.compute(payload)); // instant
  clearTimeout(calcTimer);
  calcTimer = setTimeout(async () => {
    try {
      applyResult(await api.post("/daily-sales-entry/calc", payload)); // authoritative
    } catch {
      /* keep the mirror result on transient failure */
    }
  }, 250);
}

async function loadPrefill() {
  const params = new URLSearchParams({
    pump_serial: val("pump-serial"),
    shift_date: val("shift-date"),
  });
  const p = await api.get(`/daily-sales-entry/prefill?${params.toString()}`);
  oilLabels = p.oil_labels || oilLabels;
  buildOilRows();

  setVal("hs-last", p.hs_last);
  setVal("ms-last", p.ms_last);
  setVal("hs-rate", p.sell_rate_hs);
  setVal("ms-rate", p.sell_rate_ms);
  OIL_KEYS.forEach((k) => setVal(`${k}-rate`, p.oil_rates ? p.oil_rates[k] : ""));
  OIL_KEYS.forEach((k) => setVal(`${k}-opening`, p.oil_openings ? p.oil_openings[k] : ""));

  // Last Shift Reading is backend-owned (auto-carried) once there IS a prior
  // reading on file. The very first entry for a pump has nothing to carry, so
  // it's left open for manual entry instead of being stuck blank forever.
  const hasCarry = Boolean(p.carried_from);
  $("hs-last").disabled = hasCarry;
  $("ms-last").disabled = hasCarry;
  $("hs-last").placeholder = hasCarry ? "auto @ 23:59 IST" : "Enter Last Shift Reading (no prior reading on file)";
  $("ms-last").placeholder = $("hs-last").placeholder;

  $("carried-note").textContent = hasCarry
    ? `Last Shift Reading carried from ${p.carried_from} (auto @ 23:59 IST).`
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
// current form values are kept (used after an Excel/scan import over an
// existing day).
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
    syncButtonState();
    return;
  }
  entryId = row.id;
  if (populate) {
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
}

async function save() {
  const status = $("save-status");
  const payload = readForm();
  status.className = "status-line";
  status.textContent = "Saving…";
  try {
    const saved = entryId
      ? await api.put(`/daily-sales-entry/${entryId}`, payload)
      : await api.post("/daily-sales-entry", payload);
    const wasEdit = Boolean(entryId);
    entryId = saved.id;
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
  document.querySelectorAll(".cc-amount").forEach((el) => (el.value = ""));
  document.querySelectorAll("#nc-rows tr").forEach((tr) => {
    tr.querySelector(".nc-ltrs").value = "";
    tr.querySelector(".nc-rate").value = "";
  });
  document.querySelectorAll(".oc-amount").forEach((el) => (el.value = ""));
  setVal("pp-settled", "");
  setVal("pp-unsettled", "");
  setVal("night-cash", "");
}

async function deleteEntry() {
  const status = $("save-status");
  if (!entryId) return;
  if (!window.confirm(`Delete Daily Sales entry #${entryId}? This cannot be undone.`)) return;
  const deletedId = entryId;
  try {
    await api.del(`/daily-sales-entry/${deletedId}`);
    entryId = null;
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
function populateInputs(payload) {
  setVal("hs-current", payload.hs && payload.hs.current);
  setVal("ms-current", payload.ms && payload.ms.current);
  // Last Shift Reading is normally backend-owned (loadPrefill() sets it) - but
  // when there's no carry data yet it's manual input, so a saved manual value
  // needs restoring here too, or reopening the day would show it blank again.
  if (!$("hs-last").disabled) setVal("hs-last", payload.hs && payload.hs.last);
  if (!$("ms-last").disabled) setVal("ms-last", payload.ms && payload.ms.last);

  (payload.oils || []).forEach((o, i) => {
    if (!OIL_KEYS[i]) return;
    setVal(`${OIL_KEYS[i]}-qty`, o.qty);
    // Opening Stock is manually editable (short-term fix, 2026-09-11). A saved
    // entry always has a resolved value here (default or override) and it's
    // restored on reopen; an imported payload that doesn't carry one (OCR, the
    // paper-layout Excel fallback) leaves loadPrefill()'s live default in place
    // instead of wiping it blank.
    if (o.opening !== undefined && o.opening !== null) {
      setVal(`${OIL_KEYS[i]}-opening`, o.opening);
    }
  });

  const exp = payload.expenses || [];
  ["exp1", "exp2", "exp3"].forEach((id, i) => setVal(id, exp[i]));

  const cards = payload.credit_card_amounts || [];
  ensureRows(".cc-amount", addCcRow, cards.length);
  document.querySelectorAll(".cc-amount").forEach((el, i) => {
    el.value = cards[i] === undefined || cards[i] === null ? "" : cards[i];
  });

  const ncs = payload.new_credits || [];
  ensureRows("#nc-rows tr", addNcRow, ncs.length);
  document.querySelectorAll("#nc-rows tr").forEach((tr, i) => {
    tr.querySelector(".nc-ltrs").value = ncs[i] && ncs[i].ltrs != null ? ncs[i].ltrs : "";
    tr.querySelector(".nc-rate").value = ncs[i] && ncs[i].rate != null ? ncs[i].rate : "";
  });

  const ocs = payload.old_credit_amounts || [];
  ensureRows(".oc-amount", addOcRow, ocs.length);
  document.querySelectorAll(".oc-amount").forEach((el, i) => {
    el.value = ocs[i] === undefined || ocs[i] === null ? "" : ocs[i];
  });

  setVal("pp-settled", payload.phone_pay_settled);
  setVal("pp-unsettled", payload.phone_pay_unsettled);
  setVal("night-cash", payload.night_cash);
}

async function exportExcel() {
  const status = $("save-status");
  if (!entryId) {
    status.className = "status-line";
    status.textContent = "Save the entry first, then Export to Excel.";
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
    const res = await api.upload("/daily-sales-entry/import-excel", file);
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
    populateInputs(res.payload); // then overlay the imported inputs (never identity)
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

// Scan / Upload. A typed / machine-generated PDF is read from its text layer
// (reliable); a scan/photo goes through OCR (handwriting is a rough guess only).
async function importScan(file) {
  const status = $("save-status");
  status.className = "status-line";
  status.textContent = "Reading the upload…";
  try {
    const res = await api.upload("/daily-sales-entry/ocr", file);
    entryId = null;
    await loadPrefill();
    populateInputs(res.payload);
    await loadExisting(); // if that day already has an entry, Save updates it
    refresh();
    const filled = (res.fields || []).filter((f) => f.value !== null && f.value !== "").length;
    const fromTextLayer = res.engine === "PDF text layer";
    status.className = fromTextLayer ? "status-line ok" : "status-line err";
    status.textContent = fromTextLayer
      ? `Read ${filled} field(s) from "${file.name}" (PDF text layer). Check each value + the pump/date, then Save.`
      : `OCR DRAFT from "${file.name}" (${res.engine}). Handwriting is NOT read reliably — ` +
        `${filled} field(s) are guesses. Check EVERY value against the scan before Save.`;
  } catch (err) {
    status.className = "status-line err";
    status.textContent =
      err.status === 503
        ? "This file needs OCR and the engine isn't available on this install."
        : `Upload failed — ${err.message || err}`;
  }
}

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

async function init() {
  if (!getToken()) {
    window.location.href = "../../index.html";
    return;
  }
  $("shift-date").value = new Date().toISOString().slice(0, 10);
  buildOilRows();
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

  wireToggles();

  document.body.addEventListener("input", (e) => {
    if (e.target.matches("[data-calc]")) refresh();
  });
  const reload = async () => {
    entryId = null;
    await loadPrefill();
    await loadExisting({ populate: true }); // open the saved entry for this pump+date, if any
  };
  $("pump-serial").addEventListener("change", reload);
  $("shift-date").addEventListener("change", reload);
  document.querySelectorAll("[data-add]").forEach((btn) => {
    btn.addEventListener("click", () => {
      ({ cc: addCcRow, nc: addNcRow, oc: addOcRow })[btn.dataset.add]();
      refresh();
    });
  });

  $("save-btn").addEventListener("click", save);
  $("update-btn").addEventListener("click", save); // same request logic; buttons differ by when they're enabled
  $("delete-btn").addEventListener("click", deleteEntry);
  $("print-btn").addEventListener("click", () => window.print());
  document.querySelectorAll("[data-blank]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      $("pump-serial").value = btn.dataset.blank;
      setVal("hs-current", "");
      setVal("ms-current", "");
      await loadPrefill();
      window.print();
    });
  });
  const scanInput = document.createElement("input");
  scanInput.type = "file";
  scanInput.accept = ".pdf,.png,.jpg,.jpeg,application/pdf,image/*";
  scanInput.style.display = "none";
  document.body.appendChild(scanInput);
  scanInput.addEventListener("change", () => {
    if (scanInput.files[0]) importScan(scanInput.files[0]);
    scanInput.value = "";
  });
  $("scan-btn").addEventListener("click", () => scanInput.click());

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
