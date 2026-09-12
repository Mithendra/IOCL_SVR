// Daily Trial Balance — the sections the backend does NOT compute.
//
// SDD ADR-1 (confirmed 2026-09-06) holds these as the record's free-form `manual`
// block rather than modelling them server-side. That decision stands; what changed
// on 2026-09-12 is how they are ENTERED. They used to be a single raw JSON
// textarea, which is not something anyone at a fuel station can fill in, so all
// seven sections were effectively missing from the form.
//
// This module is the form definition for them. Every field still lands in exactly
// the same `manual` dict, addressed by a dotted path ("section3.onhand"), so the
// storage contract is unchanged and an already-saved record round-trips untouched.
//
// Section numbering here is the STATION'S OWN workbook numbering (1-11), which is
// what the operator has in front of them — not the older SDD §9 numbering the
// backend's field names still use. See the note in index.html.
//
// Layout of the structures below:
//   { n, title, note?, blocks: [...] }
//   block "fields" — label/value rows, one input each
//   block "rows"   — a repeating table the user adds rows to (stored as an array)
//   block "grid"   — a fixed set of named rows x named columns

export const DROPDOWN_CREDITORS = [
  "Anil/Nani New Credit",
  "AirTel Hari New Credit",
  "Salary Advance Viaj",
  "Salary Advance Ashok",
  "Salary Advance Sriharsha",
  "Salary Advance Ravindra",
  "Sajja Function Hall - New Credit",
];

export const DROPDOWN_EXPENSES = [
  "Salaries Mid/End of Month - Total",
  "Power Bill",
  "Unload Beta",
  "Salary Advances Total",
];

export const DROPDOWN_REMITTANCE = [
  "Sajja Old Credit Remitted Amt",
  "Anil/Nani Old Credit Remitted Amt",
  "AirTel Hari Old Credit Remitted Amt",
  "AirTel New Credit Remitted Amt",
];

// The 26 columns of the Daily Mgr Calculation running ledger, in the workbook's
// own order (confirmed 2026-08-25 against the AUG25 tab).
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
    key: "section3",
    title: "Daily Cash &amp; Bank Balances",
    hint: "[IOCL Spana / Indian Bank / Yes Bank / Other Ongoing / New Credits]",
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
          ["3.6", "Total", "total6"],
          ["3.7", "Old Cash + Current Day Total", "total7"],
          ["3.8", "IOCL Card End Balance (-)", "iocl"],
          ["3.9", "Indian Bank Statement Ending Balance", "indianbank"],
          ["3.10", "Yes Bank Statement Ending Balance", "yesbank"],
          ["3.11", "Phone Pay Unsettled Amt", "ppunsettled"],
          ["3.12", "Phone Pay Settled Amt", "ppsettled",
            "Already reflects in the Indian Bank statement"],
          ["3.13", "Total Amt", "total13"],
        ],
      },
      {
        type: "rows",
        key: "new_credits",
        title: "3.14 New Credit / Salary Advance",
        columns: [
          { key: "type", label: "Type", options: DROPDOWN_CREDITORS },
          { key: "amount", label: "Amount" },
        ],
      },
      {
        type: "rows",
        key: "expenses",
        title: "3.14b Expenses",
        columns: [
          { key: "category", label: "Category", options: DROPDOWN_EXPENSES },
          { key: "amount", label: "Amount" },
        ],
      },
      {
        type: "rows",
        key: "remittance",
        title: "3.14c Credit Remittance",
        columns: [
          { key: "type", label: "Type", options: DROPDOWN_REMITTANCE },
          { key: "given_on", label: "Credit Given on Date" },
          { key: "amount", label: "Amt" },
        ],
      },
      {
        type: "fields",
        fields: [["3.15", "Total Cash/Book Amount as of Today", "total15"]],
      },
    ],
  },

  {
    n: "4",
    key: "section4",
    title: "Cash/Book Value Reconciliation",
    blocks: [
      {
        type: "fields",
        fields: [
          ["4.1", "Yesterday SVR Cash/Book Value", "yesterday"],
          ["4.2", "Total Today Sale Amount After Expenses (Beta, Testing and Density)", "todaysale"],
          ["4.3", "Total - Projected", "total3"],
          ["4.4", "Today SVR Cash/Book Value Reported", "reported"],
          ["4.5", "Diff Reported - Projected", "diff",
            "OK if within ₹100 — otherwise call/inform management immediately"],
        ],
      },
    ],
  },

  {
    n: "7",
    key: "section7",
    title: "Trial Balance - Projected - Today",
    hint: "[more value depends on Consump Difference]",
    blocks: [
      {
        type: "fields",
        fields: [
          ["7.1", "Yesterday's Actual Reported Trial Balance", "yesterday"],
          ["7.2", "Today's Profit Including 2T Sales", "profit"],
          ["7.3", "Today's Projected Trial Balance", "total3"],
          ["7.4", "Difference — Actual Reported Minus Projected", "diff"],
          ["7.5", "Today's Actual Reported Trial Balance", "total5"],
        ],
      },
    ],
  },

  {
    n: "8",
    key: "section8",
    title: "Daily Management Reporting",
    blocks: [
      {
        type: "fields",
        fields: [
          ["8.1", "Yesterday's SVR Cash/Book Value", "f1"],
          ["8.2", "Today's Sales After Expenses, Testing and Density Adjustments", "f2"],
          ["8.3", "Projected SVR Cash/Book Value", "f3", "Duplicate of Section 4, for mgmt reporting"],
          ["8.4", "Actual Reported SVR Cash/Book Value", "f4"],
          ["8.5", "Difference — Actual Reported Minus Projected", "f5"],
        ],
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
          { key: "category", label: "Category", options: DROPDOWN_EXPENSES },
          { key: "amount", label: "Amount" },
        ],
      },
    ],
  },

  {
    n: "9",
    key: "section9",
    title: "Daily Mgr Calculation",
    hint: "[running ledger — scrolls horizontally]",
    blocks: [
      {
        type: "rows",
        key: "ledger",
        wide: true,
        columns: MGR_CALC_COLUMNS.map(([key, label]) => ({ key, label })),
      },
    ],
  },

  {
    n: "10",
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
          ["lost", "Lost"],
          ["total", "Total"],
        ],
        note: "Total = New Computer − Old Reading (Lost is tracked separately).",
      },
    ],
  },

  {
    n: "11",
    key: "section11",
    title: "Old/New Credit Sales Details",
    hint: "[Credit Master Entry]",
    blocks: [
      {
        type: "fields",
        fields: [
          ["11.1", "New Airtel Balance", "new_airtel"],
          ["11.2", "Old Airtel Balance", "old_airtel"],
        ],
      },
    ],
  },
];
