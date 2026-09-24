/* Daily Sales Report - the station's own paper form, reproduced exactly.
 *
 * Client, 2026-09-23: "Keep the exact Excel forms ... uses the PDF document
 * SVR_DSR_EMPTY_12BC4523V-RD.pdf as SVR_DSR_<Serial-No>_<date>.pdf to hand fill
 * out on emergency basis", and "when a given pump reading is entered and then
 * Print, it should print exactly in the same format ... ALWAYS the same format."
 *
 * So there is ONE layout here and two uses of it: blank for hand-filling, and
 * filled from a day's entry. Printing the data-entry screen instead is what
 * produced the forms they rejected - that screen is built to be typed into, and
 * a layout that is good for typing is not the layout their operators have been
 * writing on for years.
 *
 * EVERY NUMBER BELOW IS MEASURED, not chosen. They come from
 * docs/01-BRD-Requirement-Gathering/ocr-samples/EMPTY_PRINTING_FORMS/
 * SVR_DSR_EMPTY_12BC4523V-RD.pdf, read out with PyMuPDF: text baselines, font
 * sizes, and the grid's own column edges. Units are PostScript points, the
 * page's own units (A4 = 595.3 x 841.9pt), so the output is positioned in the
 * same coordinate space as the original rather than converted and rounded.
 *
 * backend/tests + frontend/tests compare a rendered PDF's text positions against
 * the reference and fail on drift. "Looks about right" is how the last four
 * print attempts passed review.
 */

const PAGE = { w: 595.3, h: 841.9 };

// Column edges per section, straight off the reference's own grid.
const COLS = {
  header: [12.0, 69.1, 183.4, 440.5, 469.0, 583.3],
  gas: [12.0, 97.7, 211.9, 326.2, 411.9, 469.0, 554.7, 583.3],
  oil: [12.0, 211.9, 269.1, 326.2, 411.9, 497.6, 583.3],
  wide: [12.0, 411.9, 583.3], // Expenses, Summary
  cards: [12.0, 154.8, 240.5, 297.6, 469.0, 583.3],
  credits: [12.0, 154.8, 269.1, 326.2, 383.3, 497.6, 583.3],
  oldCredit: [12.0, 183.4, 297.6, 469.0, 583.3],
  verify: [12.0, 97.7, 240.5, 326.2, 440.5, 497.6, 583.3],
};

// Row bands: [y0, y1] exactly as the reference draws them.
const BANDS = {
  header: [32, 52],
  gasHead: [67, 85],
  gasRows: [[85, 106], [106, 127]],
  gasTotal: [127, 141],
  oilHead: [153, 171],
  oilRows: [[171, 184], [184, 197], [197, 210], [210, 223], [223, 236],
    [236, 249], [249, 262]],
  oilTotal: [262, 276],
  gasOilTotal: [276, 291],
  expHead: [303, 316],
  expRows: [[316, 334], [334, 352], [352, 370]],
  expTotal: [370, 384],
  cardHead: [396, 412],
  cardRows: [[412, 424], [424, 436], [436, 448], [448, 460], [460, 472],
    [472, 484]],
  cardTotal: [484, 498],
  creditHead: [510, 528],
  creditRows: [[528, 541], [541, 554], [554, 567]],
  creditTotal: [567, 581],
  oldHead: [593, 608],
  oldRows: [[608, 621], [621, 634], [634, 647]],
  summary: [[659, 673], [673, 687], [687, 701], [701, 723], [723, 737],
    [737, 751], [751, 774], [774, 796]],
  verify: [808, 826],
};

const OIL_ITEMS = [
  "2T/1.50 ML Total#", "2T/2.40 ML Total#", "Acid Water Total 1 Lts",
  "Battery Water Total 1 Lts", "Battery Water Total 5 Lts",
  "20/40 Engine Total in 05. Lts", "20/40 Engine Total in 1 Lts",
];

const EXPENSE_LABELS = [
  "Daily Diesel(5L) & Petrol(5L) + Density Testing + Beta = Total Amt",
  "Any Other Expenses",
  "Last Night Cash Hand-off Persons Name-Signature-Amount",
];

const SUMMARY_LABELS = [
  "Cash (Gas+ Oils) Total Amt",
  "Expenses Total Amt",
  "Phone Pay Settled Total Amt as of 6:30 AM",
  "Phone Pay Not Settled Total Amt As of today ___ AM\n(Attach a Separate Empty Sheet if needed)",
  "New Credits Total Amt",
  "Credit Cards Swiping Total Amt",
  "Net Bal Hand off [Cash - (Expenses + Phone Pay Settled +\nPhone Pay Not Settled + Today New Credits + Card Swiping)]",
  "Total Amt - Old Credit Amt/Given by Customer Name\n(Do NOT Include in Today's Total)",
];

function esc(v) {
  return String(v === undefined || v === null ? "" : v)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** Two decimals for a real figure; a blank stays blank so it can be written on. */
function money(v) {
  if (v === undefined || v === null || v === "") return "";
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(2) : String(v);
}

function box(x0, y0, x1, y1) {
  return `<div class="bx" style="left:${x0}pt;top:${y0}pt;` +
    `width:${x1 - x0}pt;height:${y1 - y0}pt"></div>`;
}

function label(x, y, text, size = 7.2, opts = {}) {
  const cls = ["tx", opts.bold ? "b" : "", opts.center ? "c" : "",
    opts.right ? "r" : ""].filter(Boolean).join(" ");
  const width = opts.width ? `width:${opts.width}pt;` : "";
  return `<div class="${cls}" style="left:${x}pt;top:${y}pt;${width}` +
    `font-size:${size}pt">${esc(text).replace(/\n/g, "<br>")}</div>`;
}

/** One grid row: the boxes, then a label in the first cell. */
function gridRow(cols, band, cells, size = 7.4, opts = {}) {
  const [y0, y1] = band;
  let html = "";
  for (let i = 0; i < cols.length - 1; i += 1) html += box(cols[i], y0, cols[i + 1], y1);
  cells.forEach((text, i) => {
    if (text === "" || text === null || text === undefined) return;
    const pad = 2.5;
    const isRight = opts.rightCols && opts.rightCols.includes(i);
    const isCentre = opts.centreCols && opts.centreCols.includes(i);
    const x = isRight ? cols[i] : cols[i] + pad;
    const w = cols[i + 1] - cols[i] - (isRight ? pad : pad * 2);
    html += label(x, y0 + (y1 - y0 - size * 1.15) / 2, text, size, {
      width: w, right: isRight, center: isCentre, bold: opts.bold,
    });
  });
  return html;
}

/**
 * Render the form. `data` null (or omitted) gives the blank for hand-filling;
 * pass a saved entry's payload + result to print the same layout filled in.
 */
export function renderDsrForm({ pumpSerial, pumpLabel, shiftDate, data } = {}) {
  const d = data || {};
  const p = d.payload || {};
  const r = d.result || {};
  const oils = p.oils || [];
  const cards = p.credit_card_amounts || [];
  const cardRows = p.credit_card_rows || [];
  const credits = p.new_credits || [];
  const ncAmts = r.new_credit_amounts || [];
  const olds = p.old_credit_amounts || [];
  const oldRows = p.old_credit_rows || [];
  const exp = p.expenses || [];

  let h = "";

  // Title - the only 12pt line on the page, centred by the reference at x=153.3.
  h += label(0, 16.8, "SVR Indian Oil Service Station - Daily Sales Report", 12,
    { width: PAGE.w, center: true, bold: true });

  // Header band: Dt&Time | Pump Serial | Name
  h += gridRow(COLS.header, BANDS.header, [
    "Dt&Time:",
    shiftDate ? `${shiftDate} & 09:30AM` : "",
    `Pump Serial# ${pumpSerial}${pumpLabel ? ` (${pumpLabel})` : ""}`,
    "Name", d.submitted_by || "",
  ], 7.2);

  // ---- 1. Gas Sale(s) ----
  h += label(15, 58.4, "Gas Sale(s)", 8.2, { bold: true });
  h += gridRow(COLS.gas, BANDS.gasHead,
    ["Pump", "Current Reading", "Last Shift Reading", "Cons\n[Last-Current]",
      "Rate", "Amount", "IOCL\n#"], 7.2, { centreCols: [0, 1, 2, 3, 4, 5, 6] });
  [["Diesel (HS-Nz1)", p.hs || {}, r.hs || {}],
    ["Petrol (MS-Nz-2)", p.ms || {}, r.ms || {}]].forEach(([name, side, res], i) => {
    h += gridRow(COLS.gas, BANDS.gasRows[i], [
      name, money(side.current), money(side.last), money(res.cons),
      money(side.rate), money(res.amount), "",
    ], 7.4, { rightCols: [1, 2, 3, 4, 5] });
  });
  h += gridRow([COLS.gas[0], COLS.gas[5], COLS.gas[7]], BANDS.gasTotal,
    ["Total Amt", money(r.gas_total)], 7.6, { bold: true, rightCols: [1] });

  // ---- 2. Oil Sale(s) ----
  h += label(15, 144.4, "Oil Sale(s)", 8.2, { bold: true });
  h += gridRow(COLS.oil, BANDS.oilHead,
    ["Item", "Quantity", "Rate", "Opening Stock", "Closing Stock", "Amount"],
    7.4, { centreCols: [0, 1, 2, 3, 4, 5] });
  OIL_ITEMS.forEach((item, i) => {
    const o = oils[i] || {};
    const chk = (r.oils || [])[i] || {};
    h += gridRow(COLS.oil, BANDS.oilRows[i], [
      o.label || item, o.qty ?? "", money(o.rate), o.opening ?? "",
      chk.closing ?? "", money(chk.amount),
    ], 7.6, { rightCols: [1, 2, 3, 4, 5] });
  });
  h += gridRow([COLS.oil[0], COLS.oil[5], COLS.oil[6]], BANDS.oilTotal,
    ["Total Amt Oil(s)", money(r.oil_total)], 7.6, { bold: true, rightCols: [1] });
  h += gridRow([COLS.oil[0], COLS.oil[5], COLS.oil[6]], BANDS.gasOilTotal,
    ["Total Gas & Oil Sales Amt",
      money(r.gas_total != null ? (r.gas_total || 0) + (r.oil_total || 0) : "")],
    7.6, { bold: true, rightCols: [1] });

  // ---- 3. Expenses ----
  h += label(15, 294.4, "Expenses", 8.2, { bold: true });
  h += gridRow(COLS.wide, BANDS.expHead, ["Description", "Amount"], 7.6,
    { centreCols: [0, 1] });
  EXPENSE_LABELS.forEach((text, i) => {
    h += gridRow(COLS.wide, BANDS.expRows[i],
      [(p.expense_labels || [])[i] || text, money(exp[i])], 7.2, { rightCols: [1] });
  });
  h += gridRow(COLS.wide, BANDS.expTotal,
    ["Total Amt Expenses", money(r.expenses_total)], 7.6,
    { bold: true, rightCols: [1] });

  // ---- 4. Credit Cards Swiping(s) ----
  h += label(15, 387.4, "Credit Cards Swiping(s)", 8.2, { bold: true });
  h += gridRow(COLS.cards, BANDS.cardHead,
    ["Card Holder / Terminal ID", "Card Type", "Rate", "Transaction/Receipt #",
      "Amount"], 7.2, { centreCols: [0, 1, 2, 3, 4] });
  BANDS.cardRows.forEach((band, i) => {
    const c = cardRows[i] || {};
    h += gridRow(COLS.cards, band,
      [c.holder || "", c.card_type || "", money(c.rate), c.receipt || "",
        money(cards[i])], 7.2, { rightCols: [4] });
  });
  h += gridRow([COLS.cards[0], COLS.cards[4], COLS.cards[5]], BANDS.cardTotal,
    ["Total Amt Credit Cards", money(r.credit_cards_total)], 7.6,
    { bold: true, rightCols: [1] });

  // ---- 5. Today New Credit(s) ----
  h += label(15, 501.4, "Today New Credit(s)", 8.2, { bold: true });
  h += gridRow(COLS.credits, BANDS.creditHead,
    ["Creditor Name", "Type\n(1. Diesel  2. Petrol)", "In Ltrs", "Rate",
      "Amount", "Signature"], 7.2, { centreCols: [0, 1, 2, 3, 4, 5] });
  BANDS.creditRows.forEach((band, i) => {
    const c = credits[i] || {};
    h += gridRow(COLS.credits, band,
      [c.name || "", c.fuel_type || "", c.ltrs ?? "", money(c.rate),
        money(ncAmts[i]), c.signature || ""], 7.2, { rightCols: [2, 3, 4] });
  });
  h += gridRow([COLS.credits[0], COLS.credits[4], COLS.credits[6]],
    BANDS.creditTotal,
    ["Total Amt New Credits Today", money(r.new_credits_total)], 7.6,
    { bold: true, rightCols: [1] });

  // ---- 6. Old/Pending Credit Received ----
  h += label(15, 584.4,
    "Old/Pending Credit Received [NOT part of today's Daily Sales Report]",
    8.2, { bold: true });
  h += gridRow(COLS.oldCredit, BANDS.oldHead,
    ["Customer Name", "Amount", "Old Credit Given Date", "Signature"], 7.4,
    { centreCols: [0, 1, 2, 3] });
  BANDS.oldRows.forEach((band, i) => {
    const o = oldRows[i] || {};
    h += gridRow(COLS.oldCredit, band,
      [o.customer || "", money(olds[i]), o.given_date || "", o.signature || ""],
      7.4, { rightCols: [1] });
  });

  // ---- 7. Summary - Cash Hand Off ----
  h += label(15, 650.4, "Summary - Cash Hand Off", 8.2, { bold: true });
  const sums = [
    r.sum_cash, r.expenses_total, p.phone_pay_settled, p.phone_pay_unsettled,
    r.new_credits_total, r.credit_cards_total, r.net_bal_hand_off,
    r.old_credit_total,
  ];
  SUMMARY_LABELS.forEach((text, i) => {
    h += gridRow(COLS.wide, BANDS.summary[i], [text, money(sums[i])], 7.6,
      { rightCols: [1], bold: i === 6 });
  });

  // ---- Verified by ----
  h += label(15, 799.4, "Verified by", 8.2, { bold: true });
  h += gridRow(COLS.verify, BANDS.verify,
    ["Mgr Name", d.mgr_name || "", "Signature", "", "Date", ""], 7.6);

  return `<div class="dsr-page">${h}</div>`;
}

export const DSR_CSS = `
.dsr-page{position:relative;width:${PAGE.w}pt;height:${PAGE.h}pt;
  background:#fff;color:#000;font-family:Arial,Helvetica,sans-serif;
  overflow:hidden}
.dsr-page .bx{position:absolute;border:0.6pt solid #000;box-sizing:border-box}
.dsr-page .tx{position:absolute;line-height:1.15;white-space:pre-wrap;
  box-sizing:border-box}
.dsr-page .b{font-weight:700}
.dsr-page .c{text-align:center}
.dsr-page .r{text-align:right}
@media print{
  @page{size:A4 portrait;margin:0}
  body{margin:0;background:#fff}
  .dsr-page{page-break-after:avoid}
}`;

export { PAGE, COLS, BANDS };
