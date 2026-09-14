"""Daily Trial Balance calculation - SDD Section 9 formula register, Sections 1, 6
and 7. Section 3 is pulled read-only from Daily Sales Summary; Sections 2/4/5/8/9/
10/11 are not modelled here yet (SDD ADR-1 pending).

Every formula below is transcribed from SDD Section 9 and the BRD session log
(items 30, 53, 54).

Cross-checked 2026-09-06 against real filled workbooks (AUG11, AUG12, and the
SEP05/SEP06 tabs of the client's live Trial Balance workbook - SEP06 explicitly
client-validated). Two formulas did not match any real data and have been
corrected accordingly - see the inline notes on `stock_ltrs` and `benefit_loss`
in `_fuel()` below for the evidence. Everything else (`diff`, `computer_pump_diff`,
`deduct_testing`) matched real data exactly and needed no change.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from svr_backend.calc.amounts import Number, is_blank, parse_amt, round4


@dataclass
class Section1Input:
    hs_yesterday: Number = None
    hs_current: Number = None
    ms_yesterday: Number = None
    ms_current: Number = None


@dataclass
class TrialBalanceInput:
    s1: Section1Input = field(default_factory=Section1Input)
    # Section 3 combined pump consumption in litres, pulled from Daily Sales Summary.
    s3_hs_consumption: Number = None
    s3_ms_consumption: Number = None
    # Section 6 rate basis = Buy Rate HS/MS (SDD 9 row 6 / session log 54).
    buy_rate_hs: Number = None
    buy_rate_ms: Number = None
    # Section 1 density-testing deduction, per fuel, from system_parameter (=10).
    testing_deduction: float = 10.0
    # Section 5.4 -> 7.1: "Today's Actual Reported SVR Cash / Book Value".
    cash_book_value: Number = None


@dataclass
class FuelLine:
    diff: float | None = None
    consumption: float | None = None
    computer_pump_diff: float | None = None
    benefit_loss: float | None = None
    deduct_testing: float | None = None
    stock_ltrs: float | None = None
    stock_amount: float | None = None


def _fuel(yesterday: Number, current: Number, consumption: Number,
          buy_rate: Number, testing: float) -> FuelLine:
    line = FuelLine()
    if is_blank(current):
        return line

    # Section 6 Stock Value litres = today's current IOCL reading, taken verbatim -
    # NOT a diff/consumption calculation. Confirmed against every real filled
    # workbook checked (AUG11, AUG12, SEP05, SEP06 - client-validated on SEP06):
    # the Stock Value section's Ltrs cell is a plain `=C3`/`=C4` reference back to
    # the current reading at the top of Section 1. The previous formula here
    # (`diff - cons`, guessed from an ambiguous BRD session-log note) produced
    # negative litres against real numbers and has been replaced.
    #
    # It needs ONLY the current reading - not yesterday's, and not Section 3.
    # Both were previously required before this would compute at all: the
    # consumption gate was removed 2026-09-06, the yesterday gate 2026-09-11.
    # Either one silently reported no stock value on a part-filled day.
    line.stock_ltrs = round4(parse_amt(current))
    if not is_blank(buy_rate):
        line.stock_amount = round4(line.stock_ltrs * parse_amt(buy_rate))

    if is_blank(yesterday):
        return line
    diff = parse_amt(yesterday) - parse_amt(current)          # SDD 9 r1: Yesterday - Current
    line.diff = round4(diff)

    if is_blank(consumption):
        return line
    cons = parse_amt(consumption)                              # pulled from Section 3
    line.consumption = round4(cons)
    line.computer_pump_diff = round4(cons - diff)              # SDD 9 r1
    # Benefit/Loss = Consumption + Computer/Pump Diff. Confirmed against AUG11 and
    # AUG12 (G3 = E3 + F3 on both tabs). Previously coded as `cons + diff`, which
    # matched neither workbook.
    line.benefit_loss = round4(cons + line.computer_pump_diff)
    line.deduct_testing = round4(cons - testing)              # SDD 9 r1 (=10 per fuel)
    return line


@dataclass
class TrialBalanceResult:
    hs: FuelLine = field(default_factory=FuelLine)
    ms: FuelLine = field(default_factory=FuelLine)
    stock_value_total: float = 0.0        # Section 6 total
    trial_balance_7_1: float = 0.0        # = Section 5.4 cash/book value
    trial_balance_7_2: float = 0.0        # = Section 6 total
    trial_balance_7_3: float = 0.0        # 7.1 + 7.2

    def to_dict(self) -> dict:
        def fl(x: FuelLine) -> dict:
            return {
                "diff": x.diff,
                "consumption": x.consumption,
                "computer_pump_diff": x.computer_pump_diff,
                "benefit_loss": x.benefit_loss,
                "deduct_testing": x.deduct_testing,
                "stock_ltrs": x.stock_ltrs,
                "stock_amount": x.stock_amount,
            }

        return {
            "section1": {"hs": fl(self.hs), "ms": fl(self.ms)},
            "section6": {
                "hs_amount": self.hs.stock_amount,
                "ms_amount": self.ms.stock_amount,
                "total": self.stock_value_total,
            },
            "section7": {
                "7_1_cash_book_value": self.trial_balance_7_1,
                "7_2_stock_value": self.trial_balance_7_2,
                "7_3_total": self.trial_balance_7_3,
            },
        }


# --------------------------------------------------------------- manual rollups
#
# Sections 3, 4, 7, 8, 10 and Section 1's cross-fuel columns stay operator-entered
# (SDD ADR-1) - but the client's own sheet computes the TOTALS between those
# entries, and says so on its face: "Columns that are marked as an example for
# Data Entry, Rest should be calculated Automatically using Excel Formulas"
# (SEP12 tab, note at H9). Typing a total that the form can add up is how a
# reconciliation goes wrong quietly.
#
# So the manual block stores INPUTS only; every figure below is derived here, on
# the server, and returned read-only. Each formula is transcribed from the SEP12
# tab and verified against that tab's own numbers - see
# tests/test_trial_balance_sep12.py, which asserts the whole sheet end to end.


def _n(value: Number) -> float:
    return 0.0 if is_blank(value) else parse_amt(value)


def _rows_total(rows: object, field: str = "amount") -> float:
    if not isinstance(rows, list):
        return 0.0
    return round4(sum(_n((r or {}).get(field)) for r in rows if isinstance(r, dict)))


def derive_manual(
    manual: dict | None,
    net_worth: float,
    oil_total: Number,
    s1: dict | None = None,
    day_sales: dict | None = None,
) -> dict:
    """Derived figures for the operator-entered sections. Inputs in, totals out.

    ``net_worth`` is Section 6.3, *Today's Total Working Capital / Net Worth* -
    the engine's ``section7["7_3_total"]`` under the older SDD numbering, NOT
    ``section6["total"]`` (which is Section 5's Stock Value). The two numbering
    schemes collide on the word "section6", and passing the wrong one put 7.4
    out by the whole cash/book value - caught against the real SEP12 tab.
    """
    m = manual or {}

    def sec(key: str) -> dict:
        v = m.get(key)
        return v if isinstance(v, dict) else {}

    s3, s4, s7, s8, s10 = (sec(k) for k in
                           ("section3", "section4", "section7", "section8", "section10"))
    ctx = s1 or {}

    # --- Section 1. Every column here is a formula in the client's own sheet;
    # they were manual entry until the register was extracted from it
    # (skills/trial-balance-reconciliation/references/sep12-formula-register.md).
    #
    #   H3 = G3*2.61   Margin HS   = Daily Testing x margin rate
    #   L3 = F3*C67    IOCL Adv HS = Consump Diff  x BUY rate
    #   I4 = H3+H4 · J4 = F26 · K4 = I4+J4 · M4 = L3+L4
    hs_margin = round4(_n(ctx.get("hs_deduct_testing")) * _n(ctx.get("margin_rate_hs")))
    ms_margin = round4(_n(ctx.get("ms_deduct_testing")) * _n(ctx.get("margin_rate_ms")))
    hs_iocl_adv = round4(_n(ctx.get("hs_computer_pump_diff")) * _n(ctx.get("buy_rate_hs")))
    ms_iocl_adv = round4(_n(ctx.get("ms_computer_pump_diff")) * _n(ctx.get("buy_rate_ms")))
    margin_total = round4(hs_margin + ms_margin)
    two_t_sales = _n(oil_total)                       # J4 = Oil Sale(s) total (2.1)
    total_sale_amt = round4(margin_total + two_t_sales)
    iocl_profit = round4(hs_iocl_adv + ms_iocl_adv)

    # --- Section 3: 3.6 -> 3.7 -> 3.13 -> 3.15.
    s3_total6 = round4(
        _n(s3.get("onhand")) + _n(s3.get("night")) + _n(s3.get("morning"))
        + _n(s3.get("daytotal")) + _n(s3.get("oldcredit"))
    )
    s3_total13 = round4(
        s3_total6 + _n(s3.get("iocl")) + _n(s3.get("indianbank"))
        + _n(s3.get("yesbank")) + _n(s3.get("ppunsettled")) + _n(s3.get("ppsettled"))
    )
    s3_new_credits = _rows_total(s3.get("new_credits"))
    s3_total15 = round4(s3_total13 + s3_new_credits)

    # --- Section 4.2, "Total Today Sale Amount After Expenses (Beta, Testing and
    # Density)". The client's sheet leaves this hand-typed, and it is the only
    # opinion in a chain of facts: 4.1 carries forward, 4.4 is counted cash and
    # bank, 4.3 and 4.5 calculate. On SEP14 it was keyed as 100,436.251 where the
    # day's own figures give 100,432.781, and 4.5 read -3.48 - a difference the
    # station would otherwise go looking for in the till.
    #
    # So compute it: the day's total sales less the Beta/Density/Testing expense,
    # both read back from that day's Daily Sales Entries. The typed value is kept
    # as the fallback for a day with no entries (an imported or historical record)
    # and returned alongside, so the screen can show when the two disagree rather
    # than silently overriding what someone entered - ADR-5.
    ds = day_sales or {}
    sales_total = ds.get("sales_total")
    s4_todaysale_typed = _n(s4.get("todaysale"))
    s4_todaysale_computed = None
    if sales_total is not None:
        s4_todaysale_computed = round4(_n(sales_total) - _n(ds.get("beta_testing")))
    s4_todaysale = (
        s4_todaysale_computed if s4_todaysale_computed is not None else s4_todaysale_typed
    )

    # --- Section 4: Projected = Yesterday + Today's sale; Diff = Reported - Projected.
    s4_total3 = round4(_n(s4.get("yesterday")) + s4_todaysale)
    s4_diff = round4(_n(s4.get("reported")) - s4_total3)

    # --- Section 7: Projected = Yesterday's TB + Today's profit; the Actual
    #     Reported figure is Section 6's own total, never retyped.
    s7_total3 = round4(_n(s7.get("yesterday")) + total_sale_amt)
    s7_diff = round4(net_worth - s7_total3)

    # --- Section 8: the same five lines as Section 4 (the sheet says so outright:
    #     "Duplicate Section for mgmt Reporting 4.Cash Reconciliation"), plus the
    #     management summary block below it.
    s8_f3 = round4(_n(s8.get("f1")) + _n(s8.get("f2")))
    s8_f5 = round4(_n(s8.get("f4")) - s8_f3)
    s8_projected_networth = round4(_n(s8.get("mgmt_yesterday_tb")) + total_sale_amt)
    s8_networth_diff = round4(net_worth - s8_projected_networth)

    # --- Section 10: Total = New Computer - Old Reading; Lost = IOCL Load - Total.
    def load_line(prefix: str) -> dict:
        total = round4(_n(s10.get(f"{prefix}_new")) - _n(s10.get(f"{prefix}_old")))
        return {"total": total, "lost": round4(_n(s10.get(f"{prefix}_load")) - total)}

    return {
        "section1": {
            "hs_margin": hs_margin,
            "ms_margin": ms_margin,
            "hs_iocl_adv": hs_iocl_adv,
            "ms_iocl_adv": ms_iocl_adv,
            "margin_total": margin_total,
            "two_t_sales": two_t_sales,
            "total_sale_amt": total_sale_amt,
            "iocl_profit": iocl_profit,
        },
        "section3": {
            "total6": s3_total6,
            "total7": s3_total6,          # the sheet repeats 3.6 as 3.7
            "total13": s3_total13,
            "new_credits_total": s3_new_credits,
            "total15": s3_total15,
        },
        "section4": {
            "todaysale": s4_todaysale,
            "todaysale_computed": s4_todaysale_computed,
            "todaysale_typed": s4_todaysale_typed,
            "todaysale_source": "computed" if s4_todaysale_computed is not None else "typed",
            "total3": s4_total3,
            "diff": s4_diff,
            "expenses_total": _rows_total(s4.get("expenses")),
            "remittance_total": _rows_total(s4.get("remittance")),
            # The sheet's side panel: Difference Amount less the Yes Bank return.
            # SEP12: 8516.1478 - 8525.95 = -9.8022.
            "total_difference": round4(s4_diff - _n(s4.get("yesbank_return"))),
        },
        "section7": {
            # D77 = K4 - Today's Profit Including 2T Sales is section 1's own
            # Total Sale Amt, not a separately typed number.
            "profit": total_sale_amt,
            "total3": s7_total3,
            "diff": s7_diff,
            "total5": round4(net_worth),
        },
        "section8": {
            # D102 = D98 - 300 - 1666.66 - 666.66 - 666.66, the "Rs3300" in the
            # label. Today's Profit here is K4, the same figure section 7.2 uses.
            "mgmt_actual_profit": round4(total_sale_amt - _n(ctx.get("daily_expenses"))),
            "f3": s8_f3,
            "f5": s8_f5,
            "regular_expenses_total": _rows_total(s8.get("regular_expenses")),
            "old_credit_total": _rows_total(s8.get("old_credit_collections")),
            "mgmt_actual_networth": round4(net_worth),
            "mgmt_projected_networth": s8_projected_networth,
            "mgmt_networth_diff": s8_networth_diff,
        },
        "section10": {"hs": load_line("hs"), "ms": load_line("ms")},
    }


def compute(data: TrialBalanceInput) -> TrialBalanceResult:
    r = TrialBalanceResult()
    r.hs = _fuel(data.s1.hs_yesterday, data.s1.hs_current, data.s3_hs_consumption,
                 data.buy_rate_hs, data.testing_deduction)
    r.ms = _fuel(data.s1.ms_yesterday, data.s1.ms_current, data.s3_ms_consumption,
                 data.buy_rate_ms, data.testing_deduction)

    r.stock_value_total = round4((r.hs.stock_amount or 0.0) + (r.ms.stock_amount or 0.0))
    r.trial_balance_7_1 = round4(parse_amt(data.cash_book_value))
    r.trial_balance_7_2 = r.stock_value_total
    r.trial_balance_7_3 = round4(r.trial_balance_7_1 + r.trial_balance_7_2)
    return r
