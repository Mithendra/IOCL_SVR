// Employee Master + Payroll Run screen (SDD 5.16 / 5.19). Manager + Owner.
// Bank fields are masked in the list; Edit fetches the full (decrypted) record.

import { api, getToken } from "../../lib/api.js";

const $ = (id) => document.getElementById(id);
let editingId = null;
let employees = [];

function resetForm() {
  editingId = null;
  $("form-title").textContent = "Add Employee";
  $("save-btn").textContent = "Save Employee";
  $("cancel-btn").style.display = "none";
  for (const id of ["e-name", "e-designation", "e-wage", "e-bank", "e-account", "e-ifsc", "e-branch"]) {
    $(id).value = "";
  }
  $("e-status").value = "Active";
}

function readForm() {
  return {
    name: $("e-name").value.trim(),
    designation: $("e-designation").value.trim() || null,
    daily_wage: parseFloat($("e-wage").value) || 0,
    bank_name: $("e-bank").value.trim() || null,
    account_number: $("e-account").value.trim() || null,
    ifsc: $("e-ifsc").value.trim() || null,
    bank_branch: $("e-branch").value.trim() || null,
    status: $("e-status").value,
  };
}

async function startEdit(id) {
  const e = await api.get(`/employees/${id}`); // decrypted
  editingId = id;
  $("form-title").textContent = `Edit Employee — ${e.name}`;
  $("save-btn").textContent = "Update Employee";
  $("cancel-btn").style.display = "inline-block";
  $("e-name").value = e.name;
  $("e-designation").value = e.designation || "";
  $("e-wage").value = e.daily_wage;
  $("e-bank").value = e.bank_name || "";
  $("e-account").value = e.account_number || "";
  $("e-ifsc").value = e.ifsc || "";
  $("e-branch").value = e.bank_branch || "";
  $("e-status").value = e.status;
}

function renderList(rows) {
  employees = rows;
  $("emp-rows").innerHTML = rows
    .map(
      (e) =>
        `<tr><td>${e.name}</td><td>${e.designation || ""}</td><td>${e.daily_wage}</td>` +
        `<td>${e.bank_name || ""}</td><td>${e.account_number || ""}</td><td>${e.ifsc || ""}</td>` +
        `<td>${e.status}</td>` +
        `<td><button type="button" class="add-row-btn" style="margin:0 4px 0 0" data-edit="${e.id}">Edit</button>` +
        `<button type="button" class="add-row-btn" style="margin:0" data-del="${e.id}">Delete</button></td></tr>`
    )
    .join("");
  for (const b of document.querySelectorAll("[data-edit]")) {
    b.addEventListener("click", () => startEdit(Number(b.dataset.edit)));
  }
  for (const b of document.querySelectorAll("[data-del]")) {
    b.addEventListener("click", () => removeEmployee(Number(b.dataset.del)));
  }
  renderPayrollInputs();
}

function renderPayrollInputs() {
  $("pr-input-rows").innerHTML = employees
    .filter((e) => e.status === "Active")
    .map(
      (e) =>
        `<tr data-emp="${e.id}"><td>${e.name}</td><td>${e.daily_wage}</td>` +
        `<td><input class="pr-days" value="12" style="width:80px"></td>` +
        `<td><input class="pr-adv" value="0" style="width:100px"></td></tr>`
    )
    .join("");
}

async function load() {
  renderList(await api.get("/employees"));
}

async function save() {
  const st = $("form-status");
  const body = readForm();
  if (!body.name) {
    st.className = "status-line err";
    st.textContent = "Name is required.";
    return;
  }
  try {
    if (editingId) await api.put(`/employees/${editingId}`, body);
    else await api.post("/employees", body);
    resetForm();
    await load();
    st.className = "status-line ok";
    st.textContent = "Employee saved.";
  } catch (err) {
    st.className = "status-line err";
    st.textContent = `Save failed — ${err.message || err}`;
  }
}

async function removeEmployee(id) {
  if (!window.confirm("Delete this employee?")) return;
  try {
    await api.del(`/employees/${id}`);
    await load();
  } catch (err) {
    $("form-status").className = "status-line err";
    $("form-status").textContent = err.message || String(err);
  }
}

function renderRun(run) {
  $("run-lines").innerHTML = run.lines
    .map(
      (l) =>
        `<div class="summary-row"><span>${l.employee_name} — ${l.days_worked}d × ${l.daily_wage}</span>` +
        `<span>gross ${l.gross_salary} / net ${l.net_pay}</span></div>`
    )
    .join("");
  $("r-gross").textContent = run.gross_total;
  $("r-advance").textContent = run.advance_total;
  $("r-net").textContent = run.net_total;
}

async function runPayroll() {
  const st = $("run-status");
  if (!$("pr-start").value || !$("pr-end").value) {
    st.className = "status-line err";
    st.textContent = "Set the pay period.";
    return;
  }
  const lines = [...document.querySelectorAll("#pr-input-rows tr")]
    .map((tr) => ({
      employee_id: Number(tr.dataset.emp),
      days_worked: parseFloat(tr.querySelector(".pr-days").value) || 0,
      advance_deduction: parseFloat(tr.querySelector(".pr-adv").value) || 0,
    }))
    .filter((l) => l.days_worked > 0);
  if (!lines.length) {
    st.className = "status-line err";
    st.textContent = "No employees with days worked.";
    return;
  }
  try {
    const run = await api.post("/payroll-runs", {
      period_start: $("pr-start").value,
      period_end: $("pr-end").value,
      pay_date: $("pr-paydate").value || null,
      lines,
    });
    renderRun(run);
    st.className = "status-line ok";
    st.textContent = `Payroll run #${run.id} recorded (net ${run.net_total}).`;
  } catch (err) {
    st.className = "status-line err";
    st.textContent = `Run failed — ${err.message || err}`;
  }
}

// --------------------------------------------------------------- insurance (3-5)

const INS = {
  accidental: { rows: "acc-rows", name: "acc-name", provider: "acc-provider",
                policy: "acc-policy", premium: "acc-premium", renewal: "acc-renewal" },
  health: { rows: "hea-rows", name: "hea-name", provider: "hea-provider",
            policy: "hea-policy", premium: "hea-premium", renewal: "hea-renewal" },
};

function insStatus(msg, kind) {
  const el = $("ins-status");
  el.className = kind ? `status-line ${kind}` : "status-line";
  el.textContent = msg || "";
}

function renderInsRows(kind, list) {
  const body = $(INS[kind].rows);
  body.innerHTML = "";
  for (const r of list) {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${r.employee_name}</td><td>${r.provider || ""}</td><td>${r.policy_number || ""}</td>` +
      `<td>${r.yearly_premium}</td><td>${r.renewal_date || ""}</td><td></td>`;
    const del = document.createElement("button");
    del.type = "button";
    del.className = "add-row-btn";
    del.style.margin = "0";
    del.textContent = "Delete";
    del.addEventListener("click", () => removeIns(r.id));
    tr.lastElementChild.appendChild(del);
    body.appendChild(tr);
  }
}

async function loadInsurance() {
  const [acc, hea, summary] = await Promise.all([
    api.get("/employee-insurance?kind=accidental"),
    api.get("/employee-insurance?kind=health"),
    api.get("/employee-insurance/summary"),
  ]);
  renderInsRows("accidental", acc);
  renderInsRows("health", hea);
  $("ins-acc-total").textContent = summary.accidental_total;
  $("ins-hea-total").textContent = summary.health_total;
  $("ins-grand").textContent = summary.grand_total;
}

async function addIns(kind) {
  const f = INS[kind];
  const body = {
    kind,
    employee_name: $(f.name).value.trim(),
    provider: $(f.provider).value.trim() || null,
    policy_number: $(f.policy).value.trim() || null,
    yearly_premium: Number($(f.premium).value || 0),
    renewal_date: $(f.renewal).value || null,
  };
  if (!body.employee_name) {
    insStatus("Employee Name is required.", "err");
    return;
  }
  try {
    await api.post("/employee-insurance", body);
    for (const k of ["name", "provider", "policy", "premium", "renewal"]) $(f[k]).value = "";
    await loadInsurance();
    insStatus("Insurance row added.", "ok");
  } catch (err) {
    insStatus(`Add failed — ${err.message || err}`, "err");
  }
}

async function removeIns(id) {
  try {
    await api.del(`/employee-insurance/${id}`);
    await loadInsurance();
    insStatus("Removed.", "ok");
  } catch (err) {
    insStatus(`Delete failed — ${err.message || err}`, "err");
  }
}

async function init() {
  if (!getToken()) {
    window.location.href = "../../index.html";
    return;
  }
  let me;
  try {
    me = await api.me();
  } catch {
    window.location.href = "../../index.html";
    return;
  }
  $("who").textContent = `${me.full_name} (${me.role})`;
  const today = new Date().toISOString().slice(0, 10);
  $("pr-paydate").value = today;
  $("save-btn").addEventListener("click", save);
  $("cancel-btn").addEventListener("click", resetForm);
  $("run-btn").addEventListener("click", runPayroll);
  document.querySelectorAll("[data-ins-add]").forEach((b) => {
    b.addEventListener("click", () => addIns(b.dataset.insAdd));
  });
  await load();
  await loadInsurance();
}

init();
