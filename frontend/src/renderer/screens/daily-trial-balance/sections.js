// Daily Trial Balance — the form definition, transcribed from the client's own
// SEP12 tab (docs/01-BRD-Requirement-Gathering/ocr-samples/Trail_balance_12-SEP-2026.xlsx).
//
// Two kinds of cell, and the difference matters:
//
//   input   — the operator types it. Stored in the record's `manual` block
//             (SDD ADR-1), addressed by a dotted path like "section3.onhand".
//   derived — the BACKEND computes it and returns it under `computed.derived`;
//             rendered read-only. The sheet says so on its own face: "Columns
//             that are marked as an example for Data Entry, Rest should be
//             calculated Automatically using Excel Formulas" (SEP12, note at H9).
//             Every one of these is asserted against the SEP12 figures in
//             backend/tests/test_trial_balance_sep12.py.
//
// Section numbering is the station's workbook numbering (1–11).

// --- dropdown lists ------------------------------------------------------------
// These are NOT hard-coded any more. They come from the server
// (GET /daily-trial-balance/options, migration 0021) so the station can add a
// value itself and have it stick for everyone - a new customer asking for credit,
// a new expense category. Each `optionList` below names the list to pull.
//
// `expenses` is one shared list: the SEP12 sheet points Section 4.6 and Section
// 8.6 at the same validation range, so a category added in either shows in both.

// Section 9, the 26-column running ledger (SEP12 row 107, columns A–Z).
export const MGR_CALC_COLUMNS = [
  ["date", "Date"],
  ["total_ms_sale", "Total MS Sale"],
  ["total_hs_sale", "Total HS Sale"],
  ["ms_deduct_testing", "MS Deduct Testing"],
  ["hs_deduct_testing", "HS Deduct Testing"],
  ["ms_total_rs", "MS Total Rs"],
  ["hs_total_rs", "HS Total Rs"],
  ["total_sales_rs", "Total Sales Rs"],
  ["daily_expenses", "Daily Expenses (Tiffins/Unloads)"],
  ["two_t_sale", "2T Sale"],
  ["total_sale", "Total Sale"],
  ["settled_phone_pay", "Settled Phone Pay"],
  ["unsettled_phone_pay", "UnSettled Phone Pay"],
  ["fleet_card_swipe", "Fleet Card Swipe"],
  ["credit_card_swipe", "Credit Card Swipe"],
  ["credit_any", "Credit (Any)"],
  ["night_cash_total", "Night Cash - Total"],
  ["day_cash_total", "Day Cash - Total"],
  ["total_cash_after_all", "Total Cash After All"],
  ["difference", "Difference"],
  ["bank_deposits", "Bank Deposits (Any)"],
  ["ms_comm", "MS Comm"],
  ["hs_comm", "HS Comm"],
  ["total_comm", "Total Comm"],
  ["day_profit", "Day Profit"],
  ["two_t_sales", "2T Sales"],
];

export const SECTIONS = [
  {
    n: "3",
    width: "wide",
    key: "section3",
    title: "Daily Cash &amp; Bank Balances",
    hint: "[IOCL Spana · Indian Bank · Yes Bank · Other Ongoing · New Credits]",
    blocks: [
      {
        type: "fields",
        fields: [
          ["3.1", "On Hand Old Cash", "onhand"],
          ["3.2", "Night Cash Hand off", "night"],
          ["3.3", "Morning Cash Hand off Total", "morning"],
          ["3.4", "Day Total", "daytotal"],
          ["3.5", "Old Credit Cash hand off", "oldcredit",
            "Included in the Total below (confirmed 2026-08-25, BRD 5.8.5)"],
          ["3.6", "Total", { derived: "section3.total6" }],
          ["3.7", "Old Cash + Current Day Total", { derived: "section3.total7" }],
          ["3.8", "IOCL Card End Balance (-)", "iocl",
            "Bank name and statement balance only - never an account number, " +
            "IFSC, UPI handle or PAN (client, 2026-09-16)"],
          ["3.9", "Indian Bank Statement Ending Balance", "indianbank", "@Fraud pending"],
          ["3.10", "Yes Bank Statement Ending Balance", "yesbank"],
          ["3.11", "Phone Pay UnSettled Amt", "ppunsettled"],
          ["3.12", "Phone Pay Settled Amt", "ppsettled",
            "Already reflects in the Indian Bank statement"],
          ["3.13", "Total Amt", { derived: "section3.total13" }],
        ],
        note: { key: "special_note" },
      },
      {
        type: "rows",
        key: "new_credits",
        title: "3.14 New Credit / Salary Advance",
        columns: [
          { key: "type", label: "Type", optionList: "creditors" },
          { key: "amount", label: "Amount" },
        ],
        total: "section3.new_credits_total",
        totalLabel: "Total New Credit / Salary Advance",
      },
      {
        type: "fields",
        // A continuation of the chain above, so no repeated "Line | Amount"
        // header - on its own it read as a mystery (client, 2026-09-12).
        noHead: true,
        fields: [["3.15", "Total Cash/Book Amount as of Today",
          { derived: "section3.total15" }]],
      },
    ],
  },

  {
    n: "4",
    width: "wide",
    key: "section4",
    title: "Cash/Book Value Reconciliation",
    blocks: [
      {
        type: "fields",
        fields: [
          ["4.1", "Yesterday SVR Cash/Book Value", "yesterday"],
          ["4.2", "Total Today Sale Amount After Expenses (Beta, Testing and Density)",
            { derived: "section4.todaysale" },
            "Computed from the day's Daily Sales Entries: sales less Beta/Density/Testing"],
          ["4.3", "Total - Projected", { derived: "section4.total3" }],
          ["4.4", "Today SVR Cash/Book Value Reported", "reported",
            "Carry this forward as tomorrow's 4.1"],
          ["4.5", "Diff Reported - Projected", { derived: "section4.diff" },
            "OK within ₹50 — above that, call/inform management immediately"],
        ],
        note: { key: "special_note" },
      },
      {
        type: "rows",
        key: "expenses",
        title: "4.6 Expenses",
        columns: [
          { key: "category", label: "Category", optionList: "expenses" },
          { key: "amount", label: "Amount" },
        ],
        total: "section4.expenses_total",
        totalLabel: "Total Expenses",
      },
      {
        type: "rows",
        key: "remittance",
        title: "4.7 Credit Remittance",
        columns: [
          { key: "type", label: "Type", optionList: "remittance" },
          { key: "given_on", label: "Credit Given on Date" },
          { key: "amount", label: "Amt" },
        ],
        total: "section4.remittance_total",
        totalLabel: "Total Credit Remittance",
      },
      {
        type: "fields",
        title: "Difference reconciliation",
        fields: [
          ["4.8", "Difference Amount", { derived: "section4.diff" }],
          ["4.9", "Yes Bank Return Amount", "yesbank_return"],
          // Added 2026-09-16 from the client's own SEP16 panel. Each is money
          // that left the business but has not landed in the counted cash or
          // bank balance yet, so each one adds back.
          ["4.9a", "SVR Staff Salaries", "staff_salaries"],
          ["4.9b", "RTGS / Bank Charges", "rtgs_charges"],
          ["4.9c", "Other Adjustment", "other_adjustment"],
          ["4.10", "Total Difference", { derived: "section4.total_difference" },
            "THIS is the real difference, not 4.5 - it is what Close & Sign Off checks"],
        ],
      },
    ],
  },

  {
    n: "7",
    width: "wide",
    key: "section7",
    title: "Trial Balance — Projected — Today",
    hint: "[more value depends on Consump Difference]",
    blocks: [
      {
        type: "fields",
        fields: [
          ["7.1", "Yesterday's Actual Reported Trial Balance", "yesterday"],
          ["7.2", "Today's Profit Including 2T Sales", "profit"],
          ["7.3", "Today's Projected Trial Balance", { derived: "section7.total3" }],
          ["7.4", "Difference — Actual Reported Minus Projected",
            { derived: "section7.diff" },
            "Report to management — a high figure points at a sensor issue"],
          ["7.5", "Today's Actual Reported Trial Balance", { derived: "section7.total5" }],
        ],
        note: { key: "special_note" },
      },
    ],
  },

  {
    n: "8",
    width: "wide",
    key: "section8",
    title: "Daily Management Reporting",
    blocks: [
      {
        type: "fields",
        fields: [
          ["8.1", "Yesterday's SVR Cash/Book Value", "f1"],
          ["8.2", "Today's Sales After Expenses, Testing and Density Adjustments", "f2"],
          ["8.3", "Projected SVR Cash/Book Value", { derived: "section8.f3" },
            "Duplicate of Section 4, for management reporting"],
          ["8.4", "Actual Reported SVR Cash/Book Value", "f4"],
          ["8.5", "Difference — Actual Reported Minus Projected", { derived: "section8.f5" },
            "OK within ₹50 — above that, call/inform management immediately"],
        ],
        note: { key: "special_note" },
      },
      {
        type: "rows",
        key: "regular_expenses",
        title: "8.6 Regular Expenses",
        note:
          "Monthly Expenses is the source for these figures (confirmed 2026-08-28) — " +
          "they should match today's dated rows there, not be a second record of the " +
          "same real-world expense.",
        columns: [
          { key: "category", label: "Category", optionList: "expenses" },
          { key: "amount", label: "Amount" },
        ],
        total: "section8.regular_expenses_total",
        totalLabel: "Total Regular Expenses",
      },
      {
        type: "rows",
        key: "old_credit_collections",
        title: "8.7 Old Credit Collections",
        columns: [
          { key: "type", label: "Type", optionList: "old_credit" },
          { key: "amount", label: "Amount" },
        ],
        total: "section8.old_credit_total",
        totalLabel: "Total Old Credit Collections",
      },
      {
        type: "fields",
        title: "Management Summary",
        note: { key: "mgmt_note" },
        fields: [
          ["8.8", "Cash Value Difference — escalate if above ₹50",
            { derived: "section8.f5" }],
          ["8.9", "Today's Actual Reported Trial Balance / SVR Net Worth",
            { derived: "section8.mgmt_actual_networth" }],
          ["8.10", "Yesterday's Actual Reported Trial Balance", "mgmt_yesterday_tb"],
          ["8.11", "Daily Profit Including 2T Sales", "mgmt_profit"],
          ["8.12", "Projected SVR Net Worth", { derived: "section8.mgmt_projected_networth" }],
          ["8.13", "Actual Reported SVR Net Worth", { derived: "section8.mgmt_actual_networth" }],
          ["8.14", "Difference — Actual Reported Minus Projected",
            { derived: "section8.mgmt_networth_diff" },
            "A positive number is good"],
          ["8.15", "Actual Profit after all Daily Expenses", "mgmt_actual_profit"],
        ],
      },
      {
        type: "signoff",
        title: "8.16 Sign-off",
        rows: [
          ["prepared_by", "Prepared by"],
          ["verified_by", "Verified by"],
          ["sent_by", "Sent to SVR and Bank Statement to Group Email"],
        ],
        optionList: "staff",
      },
      {
        // Client, 2026-09-16: two checks answered before Close & Sign Off.
        // Section 8 renders above the posting block and the sign-off controls,
        // so this is the last thing on the form before them.
        //
        // Numbered 8.17, not 8.10. The Management Summary above owns 8.8-8.15
        // from the client's own workbook, so both sign-off blocks sit after it.
        // This block first shipped as "8.10" and collided with 8.10 Yesterday's
        // Actual Reported Trial Balance - two different rows, same number, on a
        // form whose whole purpose is that every figure has one address. The
        // block below it had been colliding with 8.9 since before that.
        //
        // "Off Load Testing performed by" has its own list, not `staff`: staff
        // is who prepares and verifies the trial balance, which is a different
        // question with different people - Sarath is on this one and not that.
        // The "+ New Name" button writes to that list, as asked.
        type: "signoff",
        title: "8.17 Before Close & Sign Off",
        rows: [
          ["density_reports_updated", "Density Reports updated?", "yes_no"],
          ["offload_tested_by", "Off Load Testing MS & HS performed by",
            "offload_testers"],
        ],
        optionList: "offload_testers",
      },
    ],
  },

  {
    n: "9",
    width: "full",
    key: "section9",
    title: "Daily Mgr Calculation",
    hint: "[running ledger — scrolls horizontally]",
    blocks: [
      {
        type: "rows",
        key: "ledger",
        wide: true,
        // Client, 2026-09-15: keep 7 days. The ledger gains a row a day and was
        // never pruned - by SEP15 the client's own sheet carried three weeks of
        // them across 26 columns.
        keepDays: 7,
        columns: MGR_CALC_COLUMNS.map(([key, label]) => ({ key, label })),
      },
    ],
  },

  {
    n: "10",
    width: "wide",
    key: "section10",
    title: "Load/Unload Details",
    hint: "[applicable only when IOCL delivers the load]",
    blocks: [
      {
        type: "grid",
        rows: [["hs", "Diesel (HS) - Vehicle"], ["ms", "Petrol (MS) - Vehicle"]],
        columns: [
          ["afterunload", "After Unload Comp"],
          ["old", "Old Reading"],
          ["new", "New Computer"],
          ["load", "IOCL Load"],
          ["lost", "Lost", "derived"],
          ["total", "Total", "derived"],
        ],
        derivedFrom: "section10",
        note: "Total = New Computer − Old Reading. Lost = IOCL Load − Total.",
      },
    ],
  },

  {
    n: "11",
    width: "wide",
    key: "section11",
    title: "Old/New Credit Sales Details",
    hint: "[Credit Master Entry]",
    blocks: [
      {
        type: "fields",
        fields: [
          ["11.1", "NEW Airtel Balance", "new_airtel"],
          ["11.2", "Old Airtel Balance", "old_airtel"],
        ],
      },
    ],
  },
];
