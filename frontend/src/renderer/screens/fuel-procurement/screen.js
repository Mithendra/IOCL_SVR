// Fuel Procurement (client, 2026-09-30). Tracks the commercial side of HS/MS
// loads bought from IOCL - there is no invoice, so the rate is typed by hand
// off the IOCL bank-debit statement. Separate from Daily Trial Balance's own
// "10. Load/Unload Details", which stays exactly as it is (sensor/IOCL-load
// litres reconciliation, not the cost side).
//
// A load is almost always two rows sharing a date and vehicle reference (HS +
// MS, ~95% of the time) - Section 1 enters both at once; every other row on
// screen stands alone once saved, since each fuel posts to its own Monthly
// Expenses category.

import { api, getToken } from "../../lib/api.js";

const $ = (id) => document.getElementById(id);
let me = null;
let allLoads = []; // every row on file, refreshed after every mutation

const rupee = (n) =>
  "₹" + Number(n || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const litres = (n) => Number(n || 0).toLocaleString("en-IN");

function setFormStatus(msg, isErr) {
  const el = $("form-status");
  el.textContent = msg || "";
  el.className = "status-line" + (isErr ? " err" : msg ? " ok" : "");
}

function setHistStatus(msg, isErr) {
  const el = $("hist-status");
  el.textContent = msg || "";
  el.className = "status-line" + (isErr ? " err" : msg ? " ok" : "");
}

// --------------------------------------------------------------- Section 1

function recomputeForm() {
  ["hs", "ms"].forEach((fuel) => {
    const load = parseFloat($(`f-${fuel}-load`).value) || 0;
    const recv = parseFloat($(`f-${fuel}-recv`).value) || 0;
    const rate = parseFloat($(`f-${fuel}-rate`).value) || 0;
    $(`f-${fuel}-lost`).value = load || recv ? litres(load - recv) : "";
    $(`f-${fuel}-amt`).value = load && rate ? rupee(load * rate) : "";
  });
  const hsLoad = parseFloat($("f-hs-load").value) || 0;
  const hsRate = parseFloat($("f-hs-rate").value) || 0;
  const msLoad = parseFloat($("f-ms-load").value) || 0;
  const msRate = parseFloat($("f-ms-rate").value) || 0;
  const total = hsLoad * hsRate + msLoad * msRate;
  $("f-total").value = total ? rupee(total) : "";
}

async function addLoad(alsoPost) {
  const shiftDate = $("f-date").value;
  if (!shiftDate) {
    setFormStatus("Pick a date first.", true);
    return;
  }
  const ref = $("f-ref").value || null;
  const jobs = [];
  ["hs", "ms"].forEach((fuel) => {
    const load = parseFloat($(`f-${fuel}-load`).value) || 0;
    if (!load) return; // the rare single-fuel load - skip the blank fuel
    jobs.push(
      api.post("/fuel-procurement", {
        shift_date: shiftDate,
        fuel_type: fuel.toUpperCase(),
        iocl_load_litres: load,
        received_litres: parseFloat($(`f-${fuel}-recv`).value) || 0,
        rate: parseFloat($(`f-${fuel}-rate`).value) || 0,
        vehicle_ref: ref,
      })
    );
  });
  if (!jobs.length) {
    setFormStatus("Enter at least one fuel's IOCL Load litres.", true);
    return;
  }
  try {
    const created = await Promise.all(jobs);
    let msg = `Added ${jobs.length} row(s) for ${shiftDate}`;
    if (alsoPost) {
      // Straight through, no Save-first step - for when nothing needs
      // correcting (client, 2026-09-30: "post it to expense master" right
      // from here). Still fully editable/postable individually afterwards
      // in Section 3 if this was the wrong call.
      await Promise.all(created.map((row) => api.post(`/fuel-procurement/${row.id}/post`, {})));
      msg += " and posted to Monthly Expenses.";
    } else {
      msg += " — not yet posted.";
    }
    setFormStatus(msg);
    ["f-hs-load", "f-hs-recv", "f-hs-rate", "f-ms-load", "f-ms-recv", "f-ms-rate", "f-ref"].forEach(
      (id) => { $(id).value = ""; }
    );
    recomputeForm();
    await reload();
  } catch (err) {
    setFormStatus(`Could not add the load — ${err.message || err}`, true);
  }
}

// --------------------------------------------------------------- Section 3

function filteredRows() {
  const start = $("s-start").value;
  const end = $("s-end").value;
  const fuel = $("s-fuel").value;
  const status = $("s-status").value;
  return allLoads.filter((r) => {
    if (start && r.shift_date < start) return false;
    if (end && r.shift_date > end) return false;
    if (fuel && r.fuel_type !== fuel) return false;
    if (status && r.status !== status) return false;
    return true;
  });
}

function renderHistory() {
  const rows = filteredRows();
  const body = $("hist-rows");
  body.innerHTML = "";
  let totalHs = 0, totalMs = 0, costHs = 0, costMs = 0, totalLost = 0, unposted = 0;

  rows.forEach((r) => {
    if (r.fuel_type === "HS") { totalHs += r.iocl_load_litres; costHs += r.amount; }
    else { totalMs += r.iocl_load_litres; costMs += r.amount; }
    totalLost += r.lost_litres;
    if (r.status !== "posted") unposted++;

    const posted = r.status === "posted";
    const tr = document.createElement("tr");
    if (posted) tr.className = "fp-row-posted";
    const lostCls = r.lost_litres > 0 ? " class=\"fp-lost\"" : "";
    tr.innerHTML =
      `<td>${r.shift_date}</td>` +
      `<td class="fp-fuel">${r.fuel_type}</td>` +
      `<td><input class="row-load" value="${r.iocl_load_litres}" ${posted ? "disabled" : ""}></td>` +
      `<td><input class="row-recv" value="${r.received_litres}" ${posted ? "disabled" : ""}></td>` +
      `<td class="num"${lostCls}>${litres(r.lost_litres)}</td>` +
      `<td><input class="row-rate" value="${r.rate}" ${posted ? "disabled" : ""}></td>` +
      `<td class="num">${rupee(r.amount)}</td>` +
      `<td>${r.vehicle_ref || ""}</td>` +
      `<td>${posted
        ? '<span class="cm-badge dt">Posted</span>'
        : '<span class="cm-badge manual">Not Posted</span>'}</td>` +
      `<td>${posted ? "" : '<button type="button" class="add-row-btn save-btn" style="margin:0">Save</button>'}</td>` +
      `<td>${posted ? "" : '<button type="button" class="add-row-btn post-btn" style="margin:0">Post</button>'}</td>`;
    tr.dataset.id = r.id;
    body.appendChild(tr);
  });

  $("sum-hs").textContent = litres(totalHs) + " L";
  $("sum-ms").textContent = litres(totalMs) + " L";
  $("sum-cost-hs").textContent = rupee(costHs);
  $("sum-cost-ms").textContent = rupee(costMs);
  $("sum-lost").textContent = litres(totalLost) + " L";
  $("sum-unposted").textContent = `${unposted} of ${rows.length} rows`;
  $("sum-total").textContent = rupee(costHs + costMs);

  body.querySelectorAll(".save-btn").forEach((btn) => {
    btn.addEventListener("click", () => saveRow(btn.closest("tr")));
  });
  body.querySelectorAll(".post-btn").forEach((btn) => {
    btn.addEventListener("click", () => postRow(btn.closest("tr")));
  });
}

async function saveRow(tr) {
  const id = tr.dataset.id;
  try {
    await api.put(`/fuel-procurement/${id}`, {
      iocl_load_litres: parseFloat(tr.querySelector(".row-load").value) || 0,
      received_litres: parseFloat(tr.querySelector(".row-recv").value) || 0,
      rate: parseFloat(tr.querySelector(".row-rate").value) || 0,
    });
    setHistStatus("Saved.");
    await reload();
  } catch (err) {
    setHistStatus(`Could not save — ${err.message || err}`, true);
  }
}

async function postRow(tr) {
  const id = tr.dataset.id;
  const row = allLoads.find((r) => String(r.id) === String(id));
  try {
    await api.post(`/fuel-procurement/${id}/post`, {});
    setHistStatus(
      `Posted ${row ? row.fuel_type : ""} load (${row ? row.shift_date : ""}) to Monthly Expenses — ` +
      `Fuel Load - ${row ? row.fuel_type : ""}.`
    );
    await reload();
  } catch (err) {
    setHistStatus(`Could not post — ${err.message || err}`, true);
  }
}

// --------------------------------------------------------------- Section 4

function renderMonths() {
  const byMonth = {};
  allLoads.forEach((r) => {
    const key = r.shift_date.slice(0, 7);
    if (!byMonth[key]) byMonth[key] = { dates: new Set(), hs: 0, ms: 0, lostHs: 0, lostMs: 0, costHs: 0, costMs: 0 };
    const m = byMonth[key];
    m.dates.add(r.shift_date);
    if (r.fuel_type === "HS") { m.hs += r.iocl_load_litres; m.lostHs += r.lost_litres; m.costHs += r.amount; }
    else { m.ms += r.iocl_load_litres; m.lostMs += r.lost_litres; m.costMs += r.amount; }
  });
  const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const body = $("month-rows");
  body.innerHTML = "";
  Object.keys(byMonth).sort().forEach((key) => {
    const m = byMonth[key];
    const [y, mo] = key.split("-");
    const label = `${monthNames[Number(mo) - 1]} ${y}`;
    const total = m.costHs + m.costMs;
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${label}</td>` +
      `<td class="num">${m.dates.size}</td>` +
      `<td class="num">${litres(m.hs)}</td>` +
      `<td class="num">${litres(m.ms)}</td>` +
      `<td class="num">${litres(m.lostHs)}</td>` +
      `<td class="num">${litres(m.lostMs)}</td>` +
      `<td class="num">${rupee(m.costHs)}</td>` +
      `<td class="num">${rupee(m.costMs)}</td>` +
      `<td class="num" style="font-weight:700">${rupee(total)}</td>`;
    body.appendChild(tr);
  });
}

// ------------------------------------------------------------------ export

async function exportExcel() {
  const params = new URLSearchParams();
  if ($("s-start").value) params.set("start", $("s-start").value);
  if ($("s-end").value) params.set("end", $("s-end").value);
  if ($("s-fuel").value) params.set("fuel_type", $("s-fuel").value);
  if ($("s-status").value) params.set("status", $("s-status").value);
  try {
    await api.download(`/fuel-procurement/export-excel?${params}`, "SVR-FuelProcurement.xlsx");
  } catch (err) {
    setHistStatus(`Export failed — ${err.message || err}`, true);
  }
}

async function exportMonthlyExcel() {
  try {
    await api.download("/fuel-procurement/export-monthly-excel", "SVR-FuelProcurement-MonthSummary.xlsx");
  } catch (err) {
    setHistStatus(`Export failed — ${err.message || err}`, true);
  }
}

// --------------------------------------------------------------------- init

async function reload() {
  allLoads = await api.get("/fuel-procurement");
  renderHistory();
  renderMonths();
}

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

  const today = new Date().toISOString().slice(0, 10);
  $("f-date").value = today;
  const monthStart = today.slice(0, 8) + "01";
  $("s-start").value = monthStart;
  $("s-end").value = today;

  // Plain event listeners, not passed as the handler directly - addLoad()
  // takes a boolean, and the click Event these would otherwise receive is
  // truthy, which quietly turned "Add This Load" into "Add & Post" too.
  $("add-load-btn").addEventListener("click", () => addLoad(false));
  $("add-post-load-btn").addEventListener("click", () => addLoad(true));
  $("search-btn").addEventListener("click", renderHistory);
  $("clear-btn").addEventListener("click", () => {
    $("s-start").value = "";
    $("s-end").value = "";
    $("s-fuel").value = "";
    $("s-status").value = "";
    renderHistory();
  });
  $("export-btn").addEventListener("click", exportExcel);
  $("export-month-btn").addEventListener("click", exportMonthlyExcel);

  ["f-hs-load", "f-hs-recv", "f-hs-rate", "f-ms-load", "f-ms-recv", "f-ms-rate"].forEach((id) => {
    $(id).addEventListener("input", recomputeForm);
  });

  await reload();
}

init();
