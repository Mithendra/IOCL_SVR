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
    if is_blank(yesterday) or is_blank(current):
        return line
    diff = parse_amt(yesterday) - parse_amt(current)          # SDD 9 r1: Yesterday - Current
    line.diff = round4(diff)

    # Section 6 Stock Value litres = today's current IOCL reading, taken verbatim -
    # NOT a diff/consumption calculation. Confirmed against every real filled
    # workbook checked (AUG11, AUG12, SEP05, SEP06 - client-validated on SEP06):
    # the Stock Value section's Ltrs cell is a plain `=C3`/`=C4` reference back to
    # the current reading at the top of Section 1. The previous formula here
    # (`diff - cons`, guessed from an ambiguous BRD session-log note) produced
    # negative litres against real numbers and has been replaced.
    line.stock_ltrs = round4(parse_amt(current))
    if not is_blank(buy_rate):
        line.stock_amount = round4(line.stock_ltrs * parse_amt(buy_rate))

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
