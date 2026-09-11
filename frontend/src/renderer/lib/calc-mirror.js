// Thin renderer-side mirror of the calculation engine, for instant typing feedback
// ONLY. The backend's POST /daily-sales-entry/calc is authoritative on every
// refresh and every Save (SDD 6.4 / 7.3). Keep this in step with
// backend/src/svr_backend/calc/daily_sales_entry.py.

export function parseAmt(raw) {
  if (raw === undefined || raw === null) return 0;
  if (typeof raw === "number") return raw;
  let s = String(raw).trim();
  if (s === "") return 0;
  if (s.indexOf("=") !== -1) s = s.substring(s.lastIndexOf("=") + 1).trim();
  if (s.indexOf("+") !== -1) {
    return s.split("+").reduce((acc, part) => {
      const v = parseFloat(part);
      return acc + (isNaN(v) ? 0 : v);
    }, 0);
  }
  const n = parseFloat(s);
  return isNaN(n) ? 0 : n;
}

export function round4(n) {
  return Math.floor(n * 10000 + 0.5) / 10000;
}

const isBlank = (v) => v === undefined || v === null || String(v).trim() === "";

function gas(row) {
  if (isBlank(row.current)) return { cons: null, amount: null };
  const cons = parseAmt(row.current) - parseAmt(row.last);
  return { cons: round4(cons), amount: round4(cons * parseAmt(row.rate)) };
}

export function compute(p) {
  const hs = gas(p.hs || {});
  const ms = gas(p.ms || {});
  const gasTotal = (hs.amount || 0) + (ms.amount || 0);

  let oilTotal = 0;
  const oils = (p.oils || []).map((row) => {
    const opening = parseAmt(row.opening);
    if (isBlank(row.qty)) return { closing: round4(opening), amount: null };
    const qty = parseAmt(row.qty);
    const amount = qty * parseAmt(row.rate);
    oilTotal += amount;
    return { closing: round4(opening - qty), amount: round4(amount) };
  });

  const expensesTotal = (p.expenses || []).reduce((a, x) => a + parseAmt(x), 0);
  const cardsTotal = (p.credit_card_amounts || []).reduce((a, x) => a + parseAmt(x), 0);

  let newCreditsTotal = 0;
  const newCreditAmounts = (p.new_credits || []).map((nc) => {
    const amt = parseAmt(nc.ltrs) * parseAmt(nc.rate);
    newCreditsTotal += amt;
    return round4(amt);
  });

  const oldCreditTotal = (p.old_credit_amounts || []).reduce((a, x) => a + parseAmt(x), 0);
  const ppSettled = parseAmt(p.phone_pay_settled);
  const ppUnsettled = parseAmt(p.phone_pay_unsettled);
  const nightCash = parseAmt(p.night_cash);

  // Net Bal Hand off = Cash - Expenses + Phone Pay Settled + Phone Pay Not
  // Settled + New Credits + Card Swiping + Night Cash Hand Off
  // (client-corrected 2026-09-11 - keep in step with calc/daily_sales_entry.py)
  const netBal =
    gasTotal +
    oilTotal -
    expensesTotal +
    ppSettled +
    ppUnsettled +
    newCreditsTotal +
    cardsTotal +
    nightCash;

  return {
    hs,
    ms,
    gas_total: round4(gasTotal),
    oils,
    oil_total: round4(oilTotal),
    expenses_total: round4(expensesTotal),
    credit_cards_total: round4(cardsTotal),
    new_credit_amounts: newCreditAmounts,
    new_credits_total: round4(newCreditsTotal),
    old_credit_total: round4(oldCreditTotal),
    sum_cash: round4(gasTotal + oilTotal),
    sum_expenses: round4(expensesTotal),
    sum_new_credits: round4(newCreditsTotal),
    sum_credit_cards: round4(cardsTotal),
    net_bal_hand_off: round4(netBal),
    sum_old_credit: round4(oldCreditTotal),
    daily_summary: {
      hs: hs.cons,
      ms: ms.cons,
      oils: (p.oils || []).map((row) => (isBlank(row.qty) ? 0 : round4(parseAmt(row.qty)))),
    },
  };
}
