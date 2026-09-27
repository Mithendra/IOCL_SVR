// Shared building blocks for a repeating row backed by a server-side option
// list - a dropdown, "+ New" to take on a value the list doesn't have yet,
// "− Delete" to remove one, and the DD/MMM/YYYY date convention. First built
// for Daily Sales Entry's Sections 4/5/6 (client, 2026-09-25/26); this is the
// second screen that needs it (Credit/Remittance Master, 2026-09-27), so it
// lives here instead of being copied a second time.
//
// Daily Sales Entry keeps its own copy of this logic rather than being
// migrated onto this module - it is already built, tested and working, and
// touching it for the sake of not repeating code would be risk with no
// benefit to anyone using the app. Every screen after this one should import
// from here instead of writing its own.

import { api } from "./api.js";
import { fmt2 } from "./format.js";

export const escapeHtml = (v) =>
  String(v == null ? "" : v).replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]
  );

// One button in a column of its own at the end of a row - the pattern Daily
// Sales Entry settled on after "the '+ +' symbols make the form look ugly"
// (client, 2026-09-25): one "+ New" and one "− Delete" per row, not a "+"
// hanging under every dropdown.
export const ROW_ACTION_CELL =
  '<td class="rownew">' +
  '<button type="button" class="add-row-btn row-new" ' +
  'title="Add a value to this row’s list">+ New</button>' +
  '<button type="button" class="add-row-btn row-del" ' +
  'title="Remove the selected value from its list">− Delete</button>' +
  "</td>";

/**
 * A kit of functions closed over one screen's own option-list cache and
 * status line. Each screen calls this once and uses what it returns - the
 * option lists are the server's own global lists either way
 * (GET /daily-trial-balance/options), so there is nothing screen-specific
 * about the DATA, only about where its status messages appear and what a
 * list is called when "+ New" asks for one.
 *
 * `nouns`: { [listKey]: "what to call one of these" } - e.g. { customers:
 * "name" } - used in the "+ New" strip's label and in error messages.
 * `statusEl`: () => the element to write save/remove confirmations into.
 */
export function createListRowKit({ nouns = {}, statusEl }) {
  let lists = {};

  async function loadLists() {
    try {
      lists = await api.get("/daily-trial-balance/options");
    } catch {
      lists = {}; // a list that will not load must not stop entry
    }
  }

  function options(listKey, chosen) {
    return ['<option value="">— select —</option>']
      .concat((lists[listKey] || []).map(
        (v) => `<option${v === chosen ? " selected" : ""}>${escapeHtml(v)}</option>`
      ))
      .join("");
  }

  // A <select> backed by a list, and nothing else in the cell - no "+" beside
  // it. Falls back to a plain text box if the list has not loaded yet, never
  // a dead control.
  function cell(cls, listKey, placeholder) {
    if (!Array.isArray(lists[listKey])) {
      return `<td><input class="${cls}" placeholder="${escapeHtml(placeholder)}"></td>`;
    }
    return `<td><select class="${cls}" data-list="${escapeHtml(listKey)}">` +
      `${options(listKey)}</select></td>`;
  }

  // A value added or removed anywhere joins/leaves every dropdown on that
  // list, not just the one that changed - otherwise the same name is entered
  // twice and a summary that groups by name reports two people owing half
  // each.
  function refreshAllSelects() {
    for (const sel of document.querySelectorAll("select[data-list]")) {
      const keep = sel.value;
      sel.innerHTML = options(sel.dataset.list, keep);
      sel.value = keep;
    }
  }

  function closeOpenStrip(tr) {
    const next = tr.nextElementSibling;
    if (next && next.classList.contains("dse-newrow")) next.remove();
  }

  function say(cls, text) {
    const el = statusEl && statusEl();
    if (!el) return;
    el.className = `status-line ${cls}`;
    el.textContent = text;
  }

  // Choosing "+ New" opens this strip on the row it was pressed on: ask for
  // the value, save it to the list, select it. Inline because Electron never
  // shows window.prompt().
  //
  // `pair`, optional: { selector, listKey, label } for a second field that
  // belongs with the first (Daily Sales Entry's card-swipe rows take a
  // holder name AND a card type together, because that is what one new
  // customer brings). Omit it for the ordinary one-field case.
  function openNewBox(tr, { pair } = {}) {
    closeOpenStrip(tr);
    const sel = tr.querySelector("select[data-list]");
    if (!sel) return;
    const listKey = sel.dataset.list;
    const span = tr.children.length;
    const boxes = pair
      ? `<label>${escapeHtml(nouns[listKey] || "Value")} ` +
        `<input class="nb-a" placeholder="new ${escapeHtml(nouns[listKey] || "value")}"></label>` +
        `<label>${escapeHtml(pair.label)} ` +
        `<input class="nb-b" placeholder="new ${escapeHtml(pair.label.toLowerCase())}"></label>`
      : `<label>New ${escapeHtml(nouns[listKey] || "value")} <input class="nb-a"></label>`;
    tr.insertAdjacentHTML(
      "afterend",
      `<tr class="dse-newrow"><td colspan="${span}"><div class="dse-newbox">` +
        boxes +
        '<button type="button" class="add-row-btn nb-ok">Add</button>' +
        '<button type="button" class="add-row-btn nb-cancel">Cancel</button>' +
        "</div></td></tr>"
    );
    const row = tr.nextElementSibling;
    row.querySelector(".nb-a").focus();
    const close = () => row.remove();
    row.querySelector(".nb-cancel").addEventListener("click", close);
    row.querySelector(".nb-ok").addEventListener("click", async () => {
      const a = (row.querySelector(".nb-a").value || "").trim();
      const b = pair ? (row.querySelector(".nb-b").value || "").trim() : "";
      if (!a && !b) {
        close();
        return;
      }
      const jobs = pair ? [[listKey, a], [pair.listKey, b]] : [[listKey, a]];
      for (const [key, value] of jobs) {
        if (!value) continue;
        // Already in the list is not a failure - only a real error stops the
        // rest of the strip, so typing a known value beside a genuinely new
        // one still adds the new one.
        try {
          await api.post("/daily-trial-balance/options", { list_key: key, value });
        } catch (err) {
          const msg = err && err.message ? String(err.message) : String(err);
          if (/already/i.test(msg)) continue;
          say("err", `Could not add "${value}" — ${msg}`);
          return;
        }
      }
      await loadLists();
      refreshAllSelects();
      // Whatever the row had selected gives way to what was just added.
      if (a) sel.value = a;
      if (b && pair) {
        const pairSel = tr.querySelector(pair.selector);
        if (pairSel) pairSel.value = b;
      }
      close();
    });
  }

  // The column heading above a cell, so the Delete strip can say "Card Type"
  // rather than "card_types".
  function columnLabel(cellEl) {
    const table = cellEl.closest("table");
    const head = table && table.querySelector("tr");
    if (!head) return "this list";
    const th = head.children[cellEl.cellIndex];
    return th ? (th.textContent || "").trim() || "this list" : "this list";
  }

  // "− Delete": a row can carry several dropdowns, so the button cannot
  // guess which value is meant - it opens a strip naming every list on the
  // row that has something selected, and the press that removes a value is
  // the second press, which doubles as the confirmation Electron cannot show
  // as a dialog. This removes an OPTION, never a RECORD: a saved entry keeps
  // the text it was filed under.
  function openDeleteBox(tr) {
    closeOpenStrip(tr);
    const chosen = [...tr.querySelectorAll("select[data-list]")].filter((s) => s.value);
    const span = tr.children.length;
    if (!chosen.length) {
      tr.insertAdjacentHTML("afterend",
        `<tr class="dse-newrow"><td colspan="${span}"><div class="dse-newbox dse-delbox">` +
        "Nothing is selected on this row, so there is nothing to remove. Choose a " +
        "value first, then press &minus; Delete." +
        '<button type="button" class="add-row-btn nb-cancel">Close</button>' +
        "</div></td></tr>");
    } else {
      const buttons = chosen.map((sel, i) =>
        `<button type="button" class="add-row-btn del-one" data-i="${i}" ` +
        `data-key="${escapeHtml(sel.dataset.list)}" ` +
        `data-value="${escapeHtml(sel.value)}" ` +
        `data-label="${escapeHtml(columnLabel(sel.closest("td")))}">` +
        `Remove &ldquo;${escapeHtml(sel.value)}&rdquo; from ` +
        `${escapeHtml(columnLabel(sel.closest("td")))}</button>`
      ).join("");
      tr.insertAdjacentHTML("afterend",
        `<tr class="dse-newrow"><td colspan="${span}"><div class="dse-newbox dse-delbox">` +
        "<b>Remove which value?</b> It goes from the dropdown for everyone. Entries " +
        "already saved keep the name they were filed under." +
        buttons +
        '<button type="button" class="add-row-btn nb-cancel">Cancel</button>' +
        "</div></td></tr>");
    }
    const row = tr.nextElementSibling;
    const close = () => row.remove();
    row.querySelector(".nb-cancel").addEventListener("click", close);
    for (const btn of row.querySelectorAll(".del-one")) {
      btn.addEventListener("click", async () => {
        const listKey = btn.dataset.key;
        const value = btn.dataset.value;
        const label = btn.dataset.label;
        try {
          await api.post("/daily-trial-balance/options/remove", { list_key: listKey, value });
        } catch (err) {
          say("err", `Could not remove "${value}" — ${err.message || err}`);
          return;
        }
        await loadLists();
        refreshAllSelects();
        say("ok", `Removed "${value}" from ${label}.`);
        // The screen's own status line sits far from this row - say it again
        // right here, briefly, before the strip closes.
        const box = row.querySelector(".dse-newbox");
        if (box) {
          box.innerHTML =
            `<b style="color:var(--io-blue)">&#10003; Removed &ldquo;${escapeHtml(value)}` +
            `&rdquo; from ${escapeHtml(label)}.</b>`;
          setTimeout(close, 1400);
        } else {
          close();
        }
      });
    }
  }

  return {
    loadLists,
    options,
    cell,
    refreshAllSelects,
    closeOpenStrip,
    openNewBox,
    openDeleteBox,
    columnLabel,
    get lists() { return lists; },
  };
}

// Amount fills itself in from litres x rate (or whatever the row's own
// formula is), but a figure the operator has actually typed always wins -
// clearing it hands the row back to the calculation. `dataset.typed` is the
// flag; call this once per Amount box when the row is built.
export function watchAmountOverride(input) {
  input.addEventListener("input", () => {
    if (input.value.trim() === "") delete input.dataset.typed;
    else input.dataset.typed = "1";
  });
}

// Shows a computed Amount, except: a figure the operator typed (dataset.typed)
// always wins, and a row nobody has touched yet shows blank rather than 0.00 -
// "0.00" on an empty row claims the row was for nothing, which is a different
// claim from "there is nothing here yet". Deliberately NOT skipped just
// because the box has focus: clicking into Amount to watch for the figure is
// the natural thing to do while waiting for it, and a focus guard is exactly
// what stops it arriving.
export function showComputedAmount(el, tr, emptyCheckSelectors, value) {
  if (el.dataset.typed === "1") return;
  const empty = emptyCheckSelectors.every((sel) => {
    const field = tr.querySelector(sel);
    return !field || field.value.trim() === "";
  });
  if (empty || value === undefined || value === null) {
    el.value = "";
    return;
  }
  el.value = fmt2(value);
}

// --------------------------------------------------------------- dates (Option B)
//
// A date field reads DD/MMM/YYYY - 09/MAR/2026 - never the host's own
// format, because 03/09 is March or September depending on who is reading it,
// and that question comes up months after the fact (client, 2026-09-25/26).
// Day first, always. What is stored and sent stays ISO; this is display only.
const MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];

export function parseGivenDate(raw) {
  const text = String(raw == null ? "" : raw).trim();
  if (!text) return null;
  const isoMatch = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (isoMatch) {
    return validDate(Number(isoMatch[1]), Number(isoMatch[2]) - 1, Number(isoMatch[3]));
  }
  const m = text.match(/^(\d{1,2})[\s/\-.]+([A-Za-z]{3,}|\d{1,2})[\s/\-.]+(\d{2}|\d{4})$/);
  if (!m) return null;
  const day = Number(m[1]);
  const month = /^\d+$/.test(m[2])
    ? Number(m[2]) - 1
    : MONTHS.indexOf(m[2].slice(0, 3).toUpperCase());
  let year = Number(m[3]);
  if (year < 100) year += 2000;
  return validDate(year, month, day);
}

// Rejects 31/FEB rather than rolling it forward to the 3rd of March.
function validDate(year, month, day) {
  if (month < 0 || month > 11 || day < 1) return null;
  const d = new Date(year, month, day);
  if (d.getFullYear() !== year || d.getMonth() !== month || d.getDate() !== day) return null;
  return d;
}

export const showGivenDate = (d) =>
  `${String(d.getDate()).padStart(2, "0")}/${MONTHS[d.getMonth()]}/${d.getFullYear()}`;
export const isoGivenDate = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-` +
  `${String(d.getDate()).padStart(2, "0")}`;

export const givenDateForSave = (raw) => {
  const text = String(raw == null ? "" : raw).trim();
  if (!text) return "";
  const d = parseGivenDate(text);
  return d ? isoGivenDate(d) : text;
};

// On leaving the box: redisplay a date that parsed, flag one that did not.
// Flagged, never guessed - a date nobody can read is not turned into a date
// somebody made up.
export function normaliseGivenDate(input) {
  const raw = input.value.trim();
  if (!raw) {
    input.classList.remove("bad");
    input.title = "";
    return;
  }
  const d = parseGivenDate(raw);
  if (!d) {
    input.classList.add("bad");
    input.title = "Not a date I can read. Try 09/MAR/2026, 9/3/26 or 09-03-2026.";
    return;
  }
  input.classList.remove("bad");
  input.title = "";
  input.value = showGivenDate(d);
}

// The calendar button borrows a real date input for its picker, then writes
// the result back in the station's own format. Expects the visible field to
// carry class "dse-date", the shared convention every date field uses.
export function pickGivenDate(btn) {
  const input = btn.parentElement.querySelector(".dse-date");
  if (!input) return;
  const helper = document.createElement("input");
  helper.type = "date";
  helper.style.cssText =
    "position:absolute;opacity:0;pointer-events:none;width:1px;height:1px";
  const existing = parseGivenDate(input.value);
  if (existing) helper.value = isoGivenDate(existing);
  btn.parentElement.appendChild(helper);
  helper.addEventListener("change", () => {
    if (helper.value) {
      const [y, mo, da] = helper.value.split("-").map(Number);
      input.value = showGivenDate(new Date(y, mo - 1, da));
      input.classList.remove("bad");
      input.dispatchEvent(new window.Event("input", { bubbles: true }));
    }
    helper.remove();
  });
  helper.addEventListener("blur", () => setTimeout(() => helper.remove(), 200));
  if (helper.showPicker) {
    try {
      helper.showPicker();
    } catch {
      helper.focus();
    }
  } else {
    helper.focus();
  }
}
