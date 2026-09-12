# Daily Sales Entry — formula register (sections 1–8)

Extracted from SDD §9 and `daily_sales_report_branded.html`'s `calcAll()`. Verified
against the real AUG11/AUG12 workbooks in `docs/01-BRD-Requirement-Gathering/`.

## Shared parsing (`amounts.py`)

- `parse_amt("527+588+100=1215")` → `1215` (text after the last `=`).
- `parse_amt("527+588+100")` → `1215` (sum the `+`-separated parts).
- `parse_amt("")` / `None` / unparseable → `0`.
- `round4(n)` = `floor(n * 10000 + 0.5) / 10000` — matches JS `Math.round`, **not**
  Python's banker's rounding.

## 1. Gas Sale(s) — per fuel (HS, MS)

- Blank `current` → `cons = None`, `amount = None`.
- `cons = current − last`   (`last` auto-carried at 23:59 IST)
- `amount = cons × sell_rate`   (**Sell** Rate HS/MS, locked at create time)
- `gas_total = hs.amount + ms.amount` (missing amount counts as 0)

## 2. Oil Sale(s) — 5 fixed SKUs + operator-added rows

- Blank `qty` → `closing = opening` (unchanged), `amount = None`.
- `amount = qty × rate`   (rate from Rate Master; `opening` from Inventory — pull
  deferred, currently blank)
- `closing = opening − qty`
- `oil_total = Σ amount`

## 3. Expenses

- `expenses_total = Σ parse_amt(row)` — each row may be an inline expression.

## 4. Credit Cards Swiping(s)

- `credit_cards_total = Σ parse_amt(row.amount)` (variable row count, ≥ 0)

## 5. Today New Credit(s)

- per row: `amount = in_ltrs × rate`
- `new_credits_total = Σ amount`

## 6. Old/Pending Credit Received

- `old_credit_total = Σ parse_amt(row.amount)` — **excluded** from today's total,
  reported separately as `sum_old_credit`.

## 7. Summary — Cash Hand Off

- `sum_cash = gas_total + oil_total`
- `sum_expenses = expenses_total`
- `sum_new_credits = new_credits_total`
- `sum_credit_cards = credit_cards_total`
- **`net_bal_hand_off = (gas_total + oil_total) − expenses_total
   − phone_pay_settled − phone_pay_not_settled − new_credits_total
   − credit_cards_total − night_cash`**

  **Every non-cash line is subtracted.** Net Bal is the *physical cash* handed
  over, so money collected electronically (phone pay, card swipes), given on
  credit, or already handed off at night is not in the drawer.

  Client-confirmed 2026-09-11 against three real filled forms, which reproduce
  exactly only under subtraction: **23,298.77** (Sep 9 Office), **38,993.84**
  (Sep 10 Office, incl. card swiping), **1,601.20** (Sep 10 Road). The mockup's
  `calcAll()` added every line, and the paper form's own printed label still
  reads "+" — both are wrong and contradict the form's own arithmetic.
  `new_credits_total` and `night_cash` are blank on all three samples, so their
  sign follows the same logic rather than direct evidence.
  Locked in by `backend/tests/test_client_reconciliation_2026_09_11.py`.

## Rounding — truncate, don't round

Every row amount is **truncated** to 2 decimals (`calc/amounts.py` `trunc2`),
then totals are the sum of the truncated rows. This is what the station's forms
do: `629.49 × 105.36 = 66323.0664` prints as `66323.06`, not `.07`. Verified
4/4 on sampled gas rows where rounding failed 2/4. `round4` is retained in
`amounts.py` for any caller that genuinely wants 4-dp, but Daily Sales Entry no
longer uses it.

## 8. Daily Summary (auto-pulled from 1 & 2)

- `daily_summary.hs = hs.cons`, `daily_summary.ms = ms.cons`
- `daily_summary.oils[i] = oil[i].qty` (0 when blank)

## Worked example (pinned by tests)

`HS 1317.52 × 105.36 = 138813.9072` exactly — no float drift (SDD §9).
