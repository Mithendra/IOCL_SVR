"""Daily Sales Entry calculation chain.

Port of ``calcAll()`` from ``docs/01-BRD-Requirement-Gathering/daily_sales_report_branded.html``
(sections 1-8). Pure functions over typed input; no I/O, no framework types.

Blank-guard rule (SDD 6.4): a Consumption / Amount / Closing Stock field stays
``None`` until its required input is actually entered - it must never compute a
garbage value from an empty field defaulting to 0.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from svr_backend.calc.amounts import Number, is_blank, parse_amt, trunc2

# Fixed oil SKUs, in form order (SDD session log 34/35). Extra operator-added items
# follow these with manually entered rate/opening stock.
OIL_KEYS: tuple[str, ...] = ("oil1", "oil2", "oil3", "oil4", "oil5")
OIL_LABELS: dict[str, str] = {
    "oil1": "2T/1.20 ML Total#",
    "oil2": "2T/2.40 ML Total#",
    "oil3": "Acid Water Total 1 Lts",
    "oil4": "Acid Water Total 5 Lts",
    "oil5": "20/40 Engine Total in Lts",
}


# --------------------------------------------------------------------------- input


@dataclass
class GasRow:
    """One fuel row of section 1. ``rate`` is the locked Sell Rate (never Buy)."""

    current: Number = None
    last: Number = None
    rate: Number = None


@dataclass
class OilRow:
    """One row of section 2. ``opening`` is the Inventory Closing Stock pulled in."""

    label: str
    qty: Number = None
    rate: Number = None
    opening: Number = None


@dataclass
class NewCreditRow:
    ltrs: Number = None
    rate: Number = None


@dataclass
class DailySalesEntryInput:
    hs: GasRow = field(default_factory=GasRow)
    ms: GasRow = field(default_factory=GasRow)
    oils: list[OilRow] = field(default_factory=list)
    # Section 3 - free-text expressions allowed per row (parse_amt handles them).
    expenses: list[Number] = field(default_factory=list)
    # Section 4 - one Amount per swipe row.
    credit_card_amounts: list[Number] = field(default_factory=list)
    # Section 5 - Amount computed per row as ltrs * rate.
    new_credits: list[NewCreditRow] = field(default_factory=list)
    # Section 6 - not part of today's total; summed for reference only.
    old_credit_amounts: list[Number] = field(default_factory=list)
    # Section 7 manual inputs.
    phone_pay_settled: Number = None
    phone_pay_unsettled: Number = None
    night_cash: Number = None

    @classmethod
    def from_payload(cls, payload: dict) -> DailySalesEntryInput:
        """Build from the loosely-typed dict the API / OCR / Excel paths produce."""
        oils_in = payload.get("oils") or []
        oils: list[OilRow] = []
        for i, row in enumerate(oils_in):
            key = OIL_KEYS[i] if i < len(OIL_KEYS) else f"oil{i + 1}"
            oils.append(
                OilRow(
                    label=row.get("label") or OIL_LABELS.get(key, key),
                    qty=row.get("qty"),
                    rate=row.get("rate"),
                    opening=row.get("opening"),
                )
            )
        return cls(
            hs=GasRow(**{k: (payload.get("hs") or {}).get(k) for k in ("current", "last", "rate")}),
            ms=GasRow(**{k: (payload.get("ms") or {}).get(k) for k in ("current", "last", "rate")}),
            oils=oils,
            expenses=list(payload.get("expenses") or []),
            credit_card_amounts=list(payload.get("credit_card_amounts") or []),
            new_credits=[
                NewCreditRow(ltrs=r.get("ltrs"), rate=r.get("rate"))
                for r in (payload.get("new_credits") or [])
            ],
            old_credit_amounts=list(payload.get("old_credit_amounts") or []),
            phone_pay_settled=payload.get("phone_pay_settled"),
            phone_pay_unsettled=payload.get("phone_pay_unsettled"),
            night_cash=payload.get("night_cash"),
        )


# -------------------------------------------------------------------------- output


@dataclass
class GasResult:
    cons: float | None = None
    amount: float | None = None


@dataclass
class OilResult:
    label: str = ""
    closing: float | None = None
    amount: float | None = None


@dataclass
class DailySalesEntryResult:
    hs: GasResult = field(default_factory=GasResult)
    ms: GasResult = field(default_factory=GasResult)
    gas_total: float = 0.0

    oils: list[OilResult] = field(default_factory=list)
    oil_total: float = 0.0

    expenses_total: float = 0.0
    credit_cards_total: float = 0.0
    new_credit_amounts: list[float] = field(default_factory=list)
    new_credits_total: float = 0.0
    old_credit_total: float = 0.0

    # Section 7 - Summary / Cash Hand Off.
    sum_cash: float = 0.0
    sum_expenses: float = 0.0
    sum_new_credits: float = 0.0
    sum_credit_cards: float = 0.0
    net_bal_hand_off: float = 0.0
    sum_old_credit: float = 0.0

    # Section 8 - Daily Summary (auto-pulled from sections 1 & 2).
    daily_summary_hs: float | None = None
    daily_summary_ms: float | None = None
    daily_summary_oils: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "hs": {"cons": self.hs.cons, "amount": self.hs.amount},
            "ms": {"cons": self.ms.cons, "amount": self.ms.amount},
            "gas_total": self.gas_total,
            "oils": [
                {"label": o.label, "closing": o.closing, "amount": o.amount} for o in self.oils
            ],
            "oil_total": self.oil_total,
            "expenses_total": self.expenses_total,
            "credit_cards_total": self.credit_cards_total,
            "new_credit_amounts": self.new_credit_amounts,
            "new_credits_total": self.new_credits_total,
            "old_credit_total": self.old_credit_total,
            "sum_cash": self.sum_cash,
            "sum_expenses": self.sum_expenses,
            "sum_new_credits": self.sum_new_credits,
            "sum_credit_cards": self.sum_credit_cards,
            "net_bal_hand_off": self.net_bal_hand_off,
            "sum_old_credit": self.sum_old_credit,
            "daily_summary": {
                "hs": self.daily_summary_hs,
                "ms": self.daily_summary_ms,
                "oils": self.daily_summary_oils,
            },
        }


# ------------------------------------------------------------------------- compute


def _gas(row: GasRow) -> GasResult:
    if is_blank(row.current):
        return GasResult(cons=None, amount=None)
    cons = trunc2(parse_amt(row.current) - parse_amt(row.last))
    amount = trunc2(cons * parse_amt(row.rate))
    return GasResult(cons=cons, amount=amount)


def _oil(row: OilRow) -> tuple[OilResult, float]:
    opening = parse_amt(row.opening)
    if is_blank(row.qty):
        # Closing mirrors opening unchanged; no amount yet.
        return OilResult(label=row.label, closing=trunc2(opening), amount=None), 0.0
    qty = parse_amt(row.qty)
    amount = trunc2(qty * parse_amt(row.rate))
    return (
        OilResult(label=row.label, closing=trunc2(opening - qty), amount=amount),
        amount,
    )


def compute(data: DailySalesEntryInput) -> DailySalesEntryResult:
    result = DailySalesEntryResult()

    # 1. Gas Sale(s)
    result.hs = _gas(data.hs)
    result.ms = _gas(data.ms)
    # Totals are the sum of the already-truncated row amounts, never a truncation
    # of the raw sum - that row-by-row order is what reproduces the paper forms.
    gas_total = (result.hs.amount or 0.0) + (result.ms.amount or 0.0)
    result.gas_total = trunc2(gas_total)

    # 2. Oil Sale(s) - 5 fixed rows + any operator-added rows
    oil_total = 0.0
    for row in data.oils:
        oil_res, amount = _oil(row)
        result.oils.append(oil_res)
        oil_total += amount
    result.oil_total = trunc2(oil_total)

    # 3. Expenses (each cell may be a "a+b+c=total" expression)
    expenses_total = sum(trunc2(parse_amt(x)) for x in data.expenses)
    result.expenses_total = trunc2(expenses_total)

    # 4. Credit Cards Swiping(s)
    credit_cards_total = sum(trunc2(parse_amt(x)) for x in data.credit_card_amounts)
    result.credit_cards_total = trunc2(credit_cards_total)

    # 5. Today New Credit(s) - Amount = In Ltrs * Rate per row
    new_credits_total = 0.0
    for nc in data.new_credits:
        amt = trunc2(parse_amt(nc.ltrs) * parse_amt(nc.rate))
        result.new_credit_amounts.append(amt)
        new_credits_total += amt
    result.new_credits_total = trunc2(new_credits_total)

    # 6. Old/Pending Credit Received - reference only, excluded from today's total
    old_credit_total = sum(trunc2(parse_amt(x)) for x in data.old_credit_amounts)
    result.old_credit_total = trunc2(old_credit_total)

    # 7. Summary - Cash Hand Off
    pp_settled = trunc2(parse_amt(data.phone_pay_settled))
    pp_unsettled = trunc2(parse_amt(data.phone_pay_unsettled))
    night_cash = trunc2(parse_amt(data.night_cash))
    result.sum_cash = trunc2(gas_total + oil_total)
    result.sum_expenses = result.expenses_total
    result.sum_new_credits = result.new_credits_total
    result.sum_credit_cards = result.credit_cards_total
    # Net Bal Hand off = Cash - Expenses - Phone Pay Settled - Phone Pay Not
    #                    Settled - New Credits - Card Swiping - Night Cash.
    #
    # EVERY non-cash line is SUBTRACTED (client-confirmed 2026-09-11). Net Bal is
    # the *physical cash* handed over, so anything collected electronically
    # (phone pay, card swipes), given on credit, or already handed off at night
    # is money that is not in the drawer and comes off the total.
    #
    # This reverses the mockup's original all-additions formula. The paper form's
    # own printed label still reads "+" and contradicts its own arithmetic -
    # verified against three real filled sheets, which reproduce exactly only
    # under subtraction: 23298.77 (Sep 9 OFF), 38993.84 (Sep 10 OFF, incl. card
    # swiping), 1601.20 (Sep 10 RD). See tests/test_client_reconciliation_*.py.
    #
    # New Credits and Night Cash are blank on all three sample forms, so their
    # sign follows the same "not received as cash" logic rather than direct
    # evidence - revisit if a filled sample ever contradicts it.
    net_bal = (
        (gas_total + oil_total)
        - expenses_total
        - pp_settled
        - pp_unsettled
        - new_credits_total
        - credit_cards_total
        - night_cash
    )
    result.net_bal_hand_off = trunc2(net_bal)
    result.sum_old_credit = result.old_credit_total

    # 8. Daily Summary - HS/MS consumption and each oil quantity, pulled from 1 & 2
    result.daily_summary_hs = result.hs.cons
    result.daily_summary_ms = result.ms.cons
    result.daily_summary_oils = [
        trunc2(parse_amt(row.qty)) if not is_blank(row.qty) else 0.0 for row in data.oils
    ]

    return result


def compute_payload(payload: dict) -> dict:
    """Convenience for the API / import paths: dict in, dict out."""
    return compute(DailySalesEntryInput.from_payload(payload)).to_dict()
