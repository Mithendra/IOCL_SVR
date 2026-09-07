// Daily Trial Balance screen (SDD 5.8 / 9). Sections 1/6/7 are computed by the
// backend engine; Section 3 consumption is pulled from Daily Sales Summary; the
// remaining sections (confirmed 2026-09-06 as the final design, SDD ADR-1) are a
// manual JSON block.
//
// RBAC (maker-checker, ADR-2, confirmed 2026-09-06): Sales is the maker - can
// view and save (GET/PUT), same as Manager/Owner. Close & Sign Off (finalize) is
// checker-only (Manager/Owner) - the fields and button for it are hidden entirely
// for Sales, mirroring the Rate Master screen's canEdit() pattern; the backend
// enforces this independently either way (SDD non-negotiable: server-side RBAC on
// every write).

import { api, getToken } from "../../lib/api.js";

const $ = (id) => document.getElementById(id);
const txt = (id, v) => {
  $(id).textContent = v === null || v === undefined ? "—" : v;
};

let me = null;

function canFinalize() {
  return me && (me.role === "Manager" || me.role === "Owner");
}

function render(view) {
  $("status-tag").textContent = view.status;
  const i = view.inputs;
  $("hs-y").value = i.s1_hs_yesterday ?? "";
  $("hs-c").value = i.s1_hs_current ?? "";
  $("ms-y").value = i.s1_ms_yesterday ?? "";
  $("ms-c").value = i.s1_ms_current ?? "";
  $("cash-bv").value = i.s54_cash_book_value ?? "";
  $("manual-json").value = JSON.stringify(view.manual, null, 2);

  for (const f of ["hs", "ms"]) {
    const s = view.computed.section1[f];
    txt(`${f}-diff`, s.diff);
    txt(`${f}-cons`, s.consumption);
    txt(`${f}-cpd`, s.computer_pump_diff);
    txt(`${f}-bl`, s.benefit_loss);
    txt(`${f}-dt`, s.deduct_testing);
    txt(`${f}-sl`, s.stock_ltrs);
    txt(`${f}-sa`, s.stock_amount);
  }
  txt("hs-br", view.pulled.buy_rate_hs);
  txt("ms-br", view.pulled.buy_rate_ms);
  txt("s6-total", view.computed.section6.total);
  txt("s7-2", view.computed.section7["7_2_stock_value"]);
  txt("s7-3", view.computed.section7["7_3_total"]);

  $("s3-src").textContent =
    view.pulled.s3_source === "daily_sales_summary"
      ? `Section 3 consumption pulled from Daily Sales Summary (HS ${view.pulled.s3_hs_consumption ?? "—"} / MS ${view.pulled.s3_ms_consumption ?? "—"} L).`
      : "No Daily Sales Summary for this date yet — Section 3 consumption is unavailable, so the derived columns stay blank.";

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
  for (const id of ["hs-y", "hs-c", "ms-y", "ms-c", "cash-bv", "manual-json"]) {
    $(id).disabled = locked;
  }
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
  let manual = {};
  try {
    manual = $("manual-json").value.trim() ? JSON.parse($("manual-json").value) : {};
  } catch {
    throw new Error("Manual JSON is not valid JSON.");
  }
  return {
    s1_hs_yesterday: num("hs-y"),
    s1_hs_current: num("hs-c"),
    s1_ms_yesterday: num("ms-y"),
    s1_ms_current: num("ms-c"),
    s54_cash_book_value: num("cash-bv"),
    manual,
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

  if (!canFinalize()) {
    $("role-tag").textContent = "Maker — entry & save only";
    $("finalize-block").style.display = "none";
    $("finalize-fields").style.display = "none";
    $("finalize-btn").style.display = "none";
  } else {
    $("role-tag").textContent = "Checker — can Close & Sign Off";
  }

  $("load-btn").addEventListener("click", load);
  $("save-btn").addEventListener("click", save);
  $("finalize-btn").addEventListener("click", finalize);
  await load();
}

init();
