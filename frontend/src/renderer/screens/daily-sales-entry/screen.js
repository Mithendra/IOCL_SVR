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

let entryId = null; // set after first Save -> subsequent saves PUT
let calcTimer = null;
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
          `<td><input id="${k}-opening" disabled placeholder="auto (Inventory)"></td>` +
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

  $("carried-note").textContent = p.carried_from
    ? `Last Shift Reading carried from ${p.carried_from} (auto @ 23:59 IST).`
    : "No prior reading for this pump — Last Shift Reading starts blank.";
  refresh();
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
    entryId = saved.id;
    applyResult(saved.result);
    $("last-updated-by").textContent = saved.last_updated_by;
    $("last-updated-time").textContent = new Date(saved.last_updated_at).toLocaleString();
    status.className = "status-line ok";
    status.textContent = `Saved (entry #${saved.id}). Net Bal Hand off ${saved.net_bal_hand_off}.`;
  } catch (err) {
    status.className = "status-line err";
    status.textContent = `Save failed — ${err.message || err}`;
  }
}

// ------------------------------------------------------------------- Excel import/export

function ensureRows(selector, adder, n) {
  while (document.querySelectorAll(selector).length < n) adder();
}

// Overlay the operator-editable fields from an imported payload. Last Shift
// Reading / Rate / Opening Stock are backend-locked, so they are NOT touched
// here - loadPrefill() owns them.
function populateInputs(payload, meta) {
  if (meta && meta.pump_serial) setVal("pump-serial", meta.pump_serial);
  if (meta && meta.shift_date) setVal("shift-date", meta.shift_date);

  setVal("hs-current", payload.hs && payload.hs.current);
  setVal("ms-current", payload.ms && payload.ms.current);

  (payload.oils || []).forEach((o, i) => {
    if (OIL_KEYS[i]) setVal(`${OIL_KEYS[i]}-qty`, o.qty);
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
    entryId = null; // an imported form is a new entry until saved
    if (res.meta && res.meta.pump_serial) setVal("pump-serial", res.meta.pump_serial);
    if (res.meta && res.meta.shift_date) setVal("shift-date", res.meta.shift_date);
    await loadPrefill(); // rebuild oil rows + lock rates/readings for this pump+date
    populateInputs(res.payload, res.meta); // then overlay the imported inputs
    refresh();
    const w = res.warnings || [];
    status.className = w.length ? "status-line" : "status-line ok";
    status.textContent = w.length
      ? `Imported with ${w.length} note(s): ${w.join(" | ")} — review, then Save.`
      : "Imported — review the values, then Save.";
  } catch (err) {
    status.className = "status-line err";
    status.textContent = `Import failed — ${err.message || err}`;
  }
}

// Scan / Upload (OCR) — draft-assist only. Stock Tesseract does not read the
// handwritten forms reliably, so the result is a starting point, not data.
async function importScan(file) {
  const status = $("save-status");
  status.className = "status-line";
  status.textContent = "Running OCR on the scan…";
  try {
    const res = await api.upload("/daily-sales-entry/ocr", file);
    entryId = null;
    await loadPrefill();
    populateInputs(res.payload, {});
    refresh();
    const filled = (res.fields || []).filter((f) => f.value !== null && f.value !== "").length;
    status.className = "status-line err"; // red on purpose — this needs checking
    status.textContent =
      `OCR DRAFT from "${file.name}" (${res.engine}). Handwriting is NOT read reliably — ` +
      `${filled} field(s) pre-filled as a guess. Check EVERY value against the scan before Save.`;
  } catch (err) {
    status.className = "status-line err";
    status.textContent =
      err.status === 503
        ? "OCR engine not available on this install."
        : `OCR failed — ${err.message || err}`;
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
    const me = await api.me();
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
  $("pump-serial").addEventListener("change", () => {
    entryId = null;
    loadPrefill();
  });
  $("shift-date").addEventListener("change", () => {
    entryId = null;
    loadPrefill();
  });
  document.querySelectorAll("[data-add]").forEach((btn) => {
    btn.addEventListener("click", () => {
      ({ cc: addCcRow, nc: addNcRow, oc: addOcRow })[btn.dataset.add]();
      refresh();
    });
  });

  $("save-btn").addEventListener("click", save);
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
}

init();
