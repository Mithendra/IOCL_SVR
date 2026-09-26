// Payment Receipt screen (SDD 5.20). Point-of-sale fuel receipt - Sales, Manager,
// Owner may issue; Manager/Owner may delete. Rate defaults server-side to the
// current Sell Rate; total = liters x rate.

import { api, getToken } from "../../lib/api.js";
import { fmt2 } from "../../lib/format.js";

const esc = (v) =>
  String(v == null ? "" : v).replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]
  );

const $ = (id) => document.getElementById(id);
const numOrNull = (v) => {
  const n = parseFloat(v);
  return isNaN(n) ? null : n;
};

let me = null;
let sellRates = {};   // { Diesel: 105.36, Petrol: 117.70 } from Rate Master
let station = {};     // name / address1 / address2 / phone, from station_profile

function syncModeRows() {
  const mode = $("r-mode").value;
  $("row-ref").style.display = mode === "Cash" ? "none" : "";
  $("row-card").style.display = mode === "Card" ? "" : "none";
}

// The Sell Rate for the fuel just picked, shown in the box rather than left to
// appear only on the issued receipt (client, 2026-09-25: "rate col should come
// from ... Sell Rate when Diesel(HS) or Petrol(MS) selected by default").
//
// It is a DEFAULT, not a lock: the box stays editable, and a rate typed over it
// is what gets sent. The backend applies the same Rate Master figure when the
// field is left empty, so the two cannot drift.
function applyDefaultRate({ force = false } = {}) {
  const fuel = $("r-fuel").value;
  const rate = sellRates[fuel];
  const note = $("r-rate-note");
  if (rate === undefined) {
    note.textContent = "No Rate Master sell rate on file — enter one.";
    return;
  }
  const box = $("r-rate");
  if (force || box.value.trim() === "" || box.dataset.auto === "1") {
    box.value = fmt2(rate);
    box.dataset.auto = "1";
  }
  note.textContent = `Sell Rate ${fmt2(rate)} — edit to override.`;
  preview();
}

function preview() {
  const l = numOrNull($("r-liters").value);
  const r = numOrNull($("r-rate").value);
  // Disabled preview cell, never typed into - safe to format.
  $("r-total").value = l !== null && r !== null ? fmt2(Math.round(l * r * 10000) / 10000) : "";
}

function renderList(rows) {
  $("receipt-rows").innerHTML = rows
    .map(
      (x) =>
        `<tr><td>${x.receipt_no || ""}</td><td>${x.receipt_date}</td><td>${x.fuel_type}</td>` +
        `<td>${fmt2(x.liters)}</td><td>${fmt2(x.rate)}</td><td>${fmt2(x.total)}</td>` +
        `<td>${x.payment_mode}</td>` +
        `<td>${me.role === "Sales" ? "" : `<button type="button" class="add-row-btn" style="margin:0" data-del="${x.id}">Delete</button>`}</td></tr>`
    )
    .join("");
  for (const b of document.querySelectorAll("[data-del]")) {
    b.addEventListener("click", () => del(b.dataset.del));
  }
}

function showIssued(r) {
  // The receipt a customer is handed. It used to be the generic summary-box -
  // a 16px logo in the page header, no address, dashed rules, and everything
  // right-aligned against a label (client, 2026-09-25: "Logo is very small and
  // look and feel is not good as well ... that should have SVR address on it").
  //
  // Built as its own document instead: the station's name and address at the
  // top, the sale as the one thing that stands out, and the total on its own
  // line. Address and phone come from station_profile, so the Owner can correct
  // them without a rebuild.
  const line = (k, v) =>
    `<div class="rc-row"><span class="rc-k">${k}</span><span class="rc-v">${v}</span></div>`;
  const paid =
    `${r.payment_mode}` +
    (r.ref_no ? ` · Ref ${r.ref_no}` : "") +
    (r.card_last4 ? ` · card ****${r.card_last4}` : "");

  $("issued-card").innerHTML = `
    <div class="rc">
      <div class="rc-head">
        <img class="rc-logo" src="../../assets/iocl-logo.png" alt="IndianOil" />
        <div class="rc-id">
          <div class="rc-name">${esc(station.name || "SVR IndianOil Service Station")}</div>
          <div class="rc-addr">${esc(station.address1 || "")}</div>
          <div class="rc-addr">${esc(station.address2 || "")}</div>
          ${station.phone ? `<div class="rc-addr">Tel ${esc(station.phone)}</div>` : ""}
        </div>
      </div>
      <div class="rc-title">Payment Receipt</div>
      <div class="rc-no">${esc(r.receipt_no)}</div>
      <div class="rc-grid">
        ${line("Date", esc(r.receipt_date))}
        ${line("Time", esc(r.receipt_time || "—"))}
        ${line("Pump", esc(r.pump_serial || "—"))}
        ${line("Attendant", esc(r.attendant || "—"))}
        ${line("Vehicle", esc(r.vehicle_no || "—"))}
      </div>
      <table class="rc-sale">
        <tr><th>Fuel</th><th>Litres</th><th>Rate ₹/L</th><th>Amount ₹</th></tr>
        <tr>
          <td>${esc(r.fuel_type)}</td>
          <td>${fmt2(r.liters)}</td>
          <td>${fmt2(r.rate)}</td>
          <td>${fmt2(r.total)}</td>
        </tr>
      </table>
      <div class="rc-total"><span>Total</span><span>₹ ${fmt2(r.total)}</span></div>
      <div class="rc-paid">Paid via ${esc(paid)}</div>
      <div class="rc-foot">Thank you — please drive safely.</div>
    </div>
    <div class="export-bar">
      <button type="button" class="export-btn secondary" id="print-receipt-btn">Print Receipt</button>
    </div>`;
  $("issued-card").style.display = "block";
  $("print-receipt-btn").addEventListener("click", printReceipt);
}

// Print the issued receipt.
//
// It was a bare window.print(). In Electron that opens the Windows dialog with
// "This app doesn't support print preview" in the pane, which is what the client
// photographed (2026-09-25) - no preview, and no way to see what would come out.
// The app already renders to a real PDF preview for the DSR form; a receipt uses
// the same route, and in colour, because a receipt handed to a customer is not
// the black-and-white form someone writes on.
function printReceipt() {
  const st = $("issue-status");
  document.body.classList.add("print-color", "receipt-print");
  const done = () => document.body.classList.remove("print-color", "receipt-print");
  const no = ($("ic-no").textContent || "receipt").replace(/[^A-Za-z0-9._-]/g, "");
  if (window.svr && typeof window.svr.printPreview === "function") {
    window.svr
      .printPreview(`SVR_Receipt_${no}`)
      .catch((err) => {
        st.className = "status-line err";
        st.textContent = `Print failed — ${err.message || err}`;
      })
      .finally(done);
    return;
  }
  window.print();      // browser tab - its own preview is fine
  done();
}

async function load() {
  renderList(await api.get("/receipts"));
}

async function del(id) {
  try {
    await api.del(`/receipts/${id}`);
    await load();
  } catch (err) {
    $("issue-status").className = "status-line err";
    $("issue-status").textContent = err.message || String(err);
  }
}

async function issue() {
  const st = $("issue-status");
  const liters = numOrNull($("r-liters").value);
  if (liters === null || liters <= 0) {
    st.className = "status-line err";
    st.textContent = "Enter liters.";
    return;
  }
  try {
    const r = await api.post("/receipts", {
      receipt_date: $("r-date").value || null,
      receipt_time: $("r-time").value || null,
      pump_serial: $("r-pump").value || null,
      attendant: $("r-attendant").value.trim() || null,
      vehicle_no: $("r-vehicle").value.trim() || null,
      fuel_type: $("r-fuel").value,
      liters,
      rate: numOrNull($("r-rate").value),
      payment_mode: $("r-mode").value,
      ref_no: $("r-ref").value.trim() || null,
      card_last4: $("r-card4").value.trim() || null,
    });
    showIssued(r);
    await load();
    st.className = "status-line ok";
    st.textContent = `Issued ${r.receipt_no} — ₹ ${fmt2(r.total)}.`;
    $("r-liters").value = "";
    $("r-total").value = "";
  } catch (err) {
    st.className = "status-line err";
    st.textContent = `Issue failed — ${err.message || err}`;
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
  const now = new Date();
  $("r-date").value = now.toISOString().slice(0, 10);
  $("r-time").value = now.toTimeString().slice(0, 5);
  $("r-mode").addEventListener("change", syncModeRows);
  $("r-liters").addEventListener("input", preview);
  $("r-rate").addEventListener("input", () => {
    $("r-rate").dataset.auto = "";   // typed over - stop replacing it
    preview();
  });
  $("r-fuel").addEventListener("change", () => applyDefaultRate({ force: true }));
  $("issue-btn").addEventListener("click", issue);
  syncModeRows();

  // Pump serials and sell rates from the one server-side source, so a receipt
  // cannot name a pump that does not exist.
  try {
    const opts = await api.get("/receipts/form-options");
    sellRates = opts.sell_rates || {};
    station = opts.station || {};
    $("r-pump").innerHTML =
      `<option value="">— select —</option>` +
      (opts.pumps || []).map((p) => `<option value="${p}">${p}</option>`).join("");
    applyDefaultRate({ force: true });
  } catch (err) {
    $("issue-status").className = "status-line err";
    $("issue-status").textContent = `Could not load pumps and rates — ${err.message || err}`;
  }
  await load();
}

init();
