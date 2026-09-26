// Monthly Expenses screen (SDD 5.15 / 5.19). Manager + Owner. Add payroll /
// operational expenses against an extensible category list; filter by inclusive
// date range + category; Section 3 is the grouped summary for the current range.

import { api, getToken } from "../../lib/api.js";
import { fmt2 } from "../../lib/format.js";

const $ = (id) => document.getElementById(id);
let me = null;
let categories = [];

function fillCategorySelects() {
  const opts = categories
    .map((c) => `<option value="${c.id}">${c.kind === "payroll" ? "Payroll" : "Ops"} — ${c.name}</option>`)
    .join("");
  $("e-category").innerHTML = opts;
  $("f-category").innerHTML = `<option value="">— All —</option>${opts}`;
}

function filterQuery() {
  const p = new URLSearchParams();
  if ($("f-start").value) p.set("start", $("f-start").value);
  if ($("f-end").value) p.set("end", $("f-end").value);
  if ($("f-category").value) p.set("category_id", $("f-category").value);
  return p.toString();
}

function renderList(items) {
  // Date, amount and description are editable in place. A posted expense that
  // went in with the wrong figure had no correction path at all - only Delete,
  // which loses the audit trail with it (client, 2026-09-25: "save and update
  // buttons as well"). Category stays read-only: a line posted from the Trial
  // Balance is filed under its own wording, and re-pointing it here would put
  // the two out of step.
  $("expense-rows").innerHTML = items
    .map(
      (e) =>
        `<tr data-row="${e.id}">` +
        `<td><input type="date" data-f="expense_date" value="${e.expense_date}"></td>` +
        `<td>${e.category}</td><td>${e.kind}</td>` +
        `<td><input data-f="description" value="${(e.description || "").replace(/"/g, "&quot;")}"></td>` +
        `<td><input data-f="amount" style="text-align:right" value="${fmt2(e.amount)}"></td>` +
        `<td style="white-space:nowrap">` +
        `<button type="button" class="add-row-btn" style="margin:0" data-upd="${e.id}">Update</button> ` +
        `<button type="button" class="add-row-btn" style="margin:0" data-del="${e.id}">Delete</button>` +
        `</td></tr>`
    )
    .join("");
  for (const b of document.querySelectorAll("[data-del]")) {
    b.addEventListener("click", () => del(b.dataset.del));
  }
  for (const b of document.querySelectorAll("[data-upd]")) {
    b.addEventListener("click", () => update(b.dataset.upd));
  }
}

async function update(id) {
  const st = $("form-status");
  const tr = document.querySelector(`tr[data-row="${id}"]`);
  const get = (f) => tr.querySelector(`[data-f="${f}"]`).value.trim();
  const amount = parseFloat(get("amount"));
  if (isNaN(amount)) {
    st.className = "status-line err";
    st.textContent = "Amount must be a number.";
    return;
  }
  try {
    await api.put(`/expenses/${id}`, {
      expense_date: get("expense_date") || null,
      description: get("description") || null,
      amount,
    });
    st.className = "status-line ok";
    st.textContent = "Updated.";
    await load();
  } catch (err) {
    st.className = "status-line err";
    st.textContent = `Update failed — ${err.message || err}`;
  }
}

function renderSummary(s) {
  $("summary-cats").innerHTML = s.by_category
    .map(
      (c) =>
        `<div class="summary-row"><span>${c.kind === "payroll" ? "Payroll" : "Ops"} — ${c.category}</span><span>${fmt2(c.total)}</span></div>`
    )
    .join("");
  $("s-payroll").textContent = fmt2(s.payroll_subtotal);
  $("s-ops").textContent = fmt2(s.operational_subtotal);
  $("s-grand").textContent = fmt2(s.grand_total);
}

function rangeQuery() {
  const p = new URLSearchParams();
  if ($("f-start").value) p.set("start", $("f-start").value);
  if ($("f-end").value) p.set("end", $("f-end").value);
  const s = p.toString();
  return s ? "?" + s : "";
}

async function load() {
  const q = filterQuery();
  const [list, summary] = await Promise.all([
    api.get(`/expenses${q ? "?" + q : ""}`),
    api.get(`/expenses/summary${rangeQuery()}`),
  ]);
  renderList(list.items);
  renderSummary(summary);
}

async function del(id) {
  try {
    await api.del(`/expenses/${id}`);
    await load();
  } catch (err) {
    $("form-status").className = "status-line err";
    $("form-status").textContent = err.message || String(err);
  }
}

async function addExpense() {
  const st = $("form-status");
  const amount = parseFloat($("e-amount").value);
  if (!($("e-category").value && amount > 0)) {
    st.className = "status-line err";
    st.textContent = "Pick a category and enter a positive amount.";
    return;
  }
  try {
    await api.post("/expenses", {
      category_id: Number($("e-category").value),
      amount,
      expense_date: $("e-date").value || null,
      description: $("e-desc").value.trim() || null,
    });
    $("e-amount").value = "";
    $("e-desc").value = "";
    await load();
    st.className = "status-line ok";
    st.textContent = "Expense added.";
  } catch (err) {
    st.className = "status-line err";
    st.textContent = `Add failed — ${err.message || err}`;
  }
}

async function newCategory() {
  if (me.role !== "Owner") {
    $("form-status").className = "status-line err";
    $("form-status").textContent = "Only the Owner can add a category.";
    return;
  }
  const name = window.prompt("New category name:");
  if (!name) return;
  const kind = window.prompt("Kind — type 'payroll' or 'operational':", "operational");
  if (kind !== "payroll" && kind !== "operational") return;
  try {
    await api.post("/expenses/categories", { name: name.trim(), kind });
    categories = await api.get("/expenses/categories");
    fillCategorySelects();
    $("form-status").className = "status-line ok";
    $("form-status").textContent = `Category "${name}" added.`;
  } catch (err) {
    $("form-status").className = "status-line err";
    $("form-status").textContent = `Failed — ${err.message || err}`;
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
  $("e-date").value = new Date().toISOString().slice(0, 10);
  categories = await api.get("/expenses/categories");
  fillCategorySelects();

  $("add-expense").addEventListener("click", addExpense);
  $("new-cat-btn").addEventListener("click", newCategory);
  $("apply-filter").addEventListener("click", load);
  $("clear-filter").addEventListener("click", () => {
    $("f-start").value = "";
    $("f-end").value = "";
    $("f-category").value = "";
    load();
  });
  await load();
}

init();
