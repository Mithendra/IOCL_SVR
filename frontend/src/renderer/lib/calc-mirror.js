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

// 2-dp truncation toward zero - what the station's own forms actually do (proven
// against the real filled sheets 2026-09-11; rounding fails on 629.49 x 105.36,
// printed 66323.06 not .07). Keep in step with calc/amounts.py trunc2. The inner
// round(...,6) absorbs binary-float noise before the cut.
export function trunc2(n) {
  return Math.trunc(Number((n * 100).toFixed(6))) / 100;
}

const isBlank = (v) => v === undefined || v === null || String(v).trim() === "";

function gas(row) {
  if (isBlank(row.current)) return { cons: null, amount: null };
  const cons = trunc2(parseAmt(row.current) - parseAmt(row.last));
  return { cons, amount: trunc2(cons * parseAmt(row.rate)) };
}

export function compute(p) {
  const hs = gas(p.hs || {});
  const ms = gas(p.ms || {});
  const gasTotal = (hs.amount || 0) + (ms.amount || 0);

  let oilTotal = 0;
  const oils = (p.oils || []).map((row) => {
    const opening = parseAmt(row.opening);
    if (isBlank(row.qty)) return { closing: trunc2(opening), amount: null };
    const qty = parseAmt(row.qty);
    const amount = trunc2(qty * parseAmt(row.rate));
    oilTotal += amount;
    return { closing: trunc2(opening - qty), amount };
  });

  const expensesTotal = (p.expenses || []).reduce((a, x) => a + trunc2(parseAmt(x)), 0);
  const cardsTotal = (p.credit_card_amounts || []).reduce((a, x) => a + trunc2(parseAmt(x)), 0);

  let newCreditsTotal = 0;
  const newCreditAmounts = (p.new_credits || []).map((nc) => {
    const amt = trunc2(parseAmt(nc.ltrs) * parseAmt(nc.rate));
    newCreditsTotal += amt;
    return amt;
  });

  const oldCreditTotal = (p.old_credit_amounts || []).reduce((a, x) => a + trunc2(parseAmt(x)), 0);
  const ppSettled = trunc2(parseAmt(p.phone_pay_settled));
  const ppUnsettled = trunc2(parseAmt(p.phone_pay_unsettled));
  const nightCash = trunc2(parseAmt(p.night_cash));

  // Net Bal Hand off = Cash - Expenses - Phone Pay Settled - Phone Pay Not
  // Settled - New Credits - Card Swiping - Night Cash Hand Off.
  // EVERY non-cash line is SUBTRACTED: Net Bal is the physical cash handed over,
  // so anything collected electronically, given on credit, or already handed off
  // is not in the drawer. Client-confirmed 2026-09-11 against three real filled
  // sheets. Keep in step with calc/daily_sales_entry.py.
  const netBal =
    gasTotal +
    oilTotal -
    expensesTotal -
    ppSettled -
    ppUnsettled -
    newCreditsTotal -
    cardsTotal -
    nightCash;

  return {
    hs,
    ms,
    gas_total: trunc2(gasTotal),
    oils,
    oil_total: trunc2(oilTotal),
    expenses_total: trunc2(expensesTotal),
    credit_cards_total: trunc2(cardsTotal),
    new_credit_amounts: newCreditAmounts,
    new_credits_total: trunc2(newCreditsTotal),
    old_credit_total: trunc2(oldCreditTotal),
    sum_cash: trunc2(gasTotal + oilTotal),
    sum_expenses: trunc2(expensesTotal),
    sum_new_credits: trunc2(newCreditsTotal),
    sum_credit_cards: trunc2(cardsTotal),
    net_bal_hand_off: trunc2(netBal),
    sum_old_credit: trunc2(oldCreditTotal),
    daily_summary: {
      hs: hs.cons,
      ms: ms.cons,
      oils: (p.oils || []).map((row) => (isBlank(row.qty) ? 0 : trunc2(parseAmt(row.qty)))),
    },
  };
}
