// Yearly Sales Report screen (SDD 5.28). Manager views; Owner edits the manual
// figures (stock-value COGS + IOCL commission) that come from Daily Trial Balance.
// Revenue / salaries / operational expenses are computed live by the backend.

import { api, getToken } from "../../lib/api.js";
import { fmt2 } from "../../lib/format.js";

const $ = (id) => document.getElementById(id);
let me = null;
let fyYear = null;

function fill(report) {
  fyYear = report.fy_start_year;
  $("fy-tag").textContent = report.fy_label;
  $("disclaimer").textContent = report.disclaimer;

  const L = report.live;
  $("v-hs").textContent = fmt2(L.hs_sales);
  $("v-ms").textContent = fmt2(L.ms_sales);
  $("v-fuel").textContent = fmt2(L.fuel_sales_total);
  $("v-oil").textContent = fmt2(L.oil_sales);
  $("v-revenue").textContent = fmt2(L.total_revenue);
  $("v-salaries").textContent = fmt2(L.salaries_total);
  $("v-opex").textContent =
    L.operational_expenses_total +
    (L.operational_expenses.length
      ? " (" + L.operational_expenses.map((o) => `${o.category} ${fmt2(o.total)}`).join(", ") + ")"
      : "");

  const m = report.manual;
  $("m-open").value = m.cogs_opening;
  $("m-purch").value = m.cogs_purchases;
  $("m-close").value = m.cogs_closing;
  $("m-hscomm").value = m.hs_commission;
  $("m-mscomm").value = m.ms_commission;
  $("m-notes").value = m.notes || "";

  $("d-cogs").textContent = fmt2(report.cogs);
  $("d-gross").textContent = fmt2(report.gross_profit);
  $("d-comm").textContent = fmt2(report.total_commission);
  $("d-opcost").textContent = fmt2(report.total_operating_costs);
  $("d-net").textContent = fmt2(report.net_profit);

  $("month-rows").innerHTML = L.by_month
    .map((r) => `<tr><td>${r.month}</td><td>${r.fuel_sales}</td><td>${r.oil_sales}</td></tr>`)
    .join("");

  const owner = me.role === "Owner";
  for (const id of ["m-open", "m-purch", "m-close", "m-hscomm", "m-mscomm", "m-notes"]) {
    $(id).disabled = !owner;
  }
  $("save-figs-btn").style.display = owner ? "inline-block" : "none";
  $("report").style.display = "block";
}

async function generate() {
  const yr = parseInt($("fy-year").value, 10);
  if (!yr || yr < 2000 || yr > 2100) {
    $("report-status").className = "status-line err";
    $("report-status").textContent = "Enter a valid FY start year.";
    return;
  }
  try {
    fill(await api.get(`/reports/yearly/${yr}`));
    $("report-status").className = "status-line ok";
    $("report-status").textContent = "";
  } catch (err) {
    $("report-status").className = "status-line err";
    $("report-status").textContent = err.message || String(err);
  }
}

async function saveFigures() {
  const st = $("report-status");
  try {
    fill(
      await api.put(`/reports/yearly/${fyYear}`, {
        cogs_opening: parseFloat($("m-open").value) || 0,
        cogs_purchases: parseFloat($("m-purch").value) || 0,
        cogs_closing: parseFloat($("m-close").value) || 0,
        hs_commission: parseFloat($("m-hscomm").value) || 0,
        ms_commission: parseFloat($("m-mscomm").value) || 0,
        notes: $("m-notes").value.trim() || null,
      })
    );
    st.className = "status-line ok";
    st.textContent = "Figures saved; summary recalculated.";
  } catch (err) {
    st.className = "status-line err";
    st.textContent = `Save failed — ${err.message || err}`;
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
  // Default to the current financial year's start year.
  const now = new Date();
  $("fy-year").value = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
  $("gen-btn").addEventListener("click", generate);
  $("save-figs-btn").addEventListener("click", saveFigures);
}

init();
