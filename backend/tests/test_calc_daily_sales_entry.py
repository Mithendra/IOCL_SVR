"""Calculation engine - the tests that give it its worth.

The worked example and the full chain are cross-checked against the BRD/SDD, which
themselves verified against the real AUG11/AUG12 workbooks (docs/01-BRD-.../*.xlsx).
"""

from __future__ import annotations

import math

from svr_backend.calc.amounts import is_blank, parse_amt, round4, trunc2
from svr_backend.calc.daily_sales_entry import (
    DailySalesEntryInput,
    GasRow,
    NewCreditRow,
    OilRow,
    compute,
)


def test_worked_example_no_float_drift():
    """HS 1317.52 x 105.36 = 138813.9072 exactly - the SDD 9 worked example.

    The station's own forms cut every row amount at two decimals rather than
    rounding (client-confirmed 2026-09-11, see ``trunc2``), so what the app now
    reports for this example is **138813.90**. The point of the example is that
    the multiplication carries no float drift, and that still holds: the exact
    product is asserted below before truncation is applied.
    """
    data = DailySalesEntryInput(hs=GasRow(current="1317.52", last="0", rate="105.36"))
    result = compute(data)
    assert result.hs.cons == 1317.52
    # No drift in the underlying arithmetic - the SDD figure, to the last digit.
    assert math.isclose(1317.52 * 105.36, 138813.9072, rel_tol=0, abs_tol=1e-9)
    # What the form shows: truncated to paise, matching the paper.
    assert result.hs.amount == 138813.90
    assert result.gas_total == 138813.90


def test_gas_blank_guard():
    """No Current Reading -> cons/amount stay None, not a negative garbage value."""
    data = DailySalesEntryInput(hs=GasRow(current="", last="1476461.66", rate="105.36"))
    result = compute(data)
    assert result.hs.cons is None
    assert result.hs.amount is None
    assert result.gas_total == 0.0


def test_parse_amt_inline_expressions():
    # SDD 11.2 - pump sales men write scratch sums in the Amount cell.
    assert parse_amt("527+588+100=1215") == 1215.0
    assert parse_amt("527+588+100") == 1215.0
    assert parse_amt("") == 0.0
    assert parse_amt(None) == 0.0
    assert parse_amt("abc") == 0.0
    assert parse_amt("1317.52") == 1317.52


def test_is_blank_treats_the_paper_form_s_dash_as_blank():
    """Every real client sample uses a lone "-" as its "nothing to report"
    marker consistently across every optional field (2026-09-11) - treated the
    same as an empty cell, never as a real value."""
    assert is_blank("-") is True
    assert is_blank(" - ") is True  # whitespace-padded, as a cell often is
    assert is_blank("") is True
    assert is_blank(None) is True
    assert is_blank("0") is False
    assert is_blank(0) is False
    assert is_blank("-5") is False  # a real negative number, not the marker


def test_round4_truncates_to_four_places():
    assert round4(138813.90723456) == 138813.9072
    assert round4(1.000149999) == 1.0001
    assert round4(1.00019) == 1.0002  # clearly above the half - rounds up (not banker's)


def test_trunc2_cuts_at_paise_and_never_rounds_up():
    """The station's forms cut, they don't round - the two real cases that prove
    it, plus the float-noise guard."""
    assert trunc2(66323.0664) == 66323.06  # rounding would give .07
    assert trunc2(68435.488) == 68435.48  # rounding would give .49
    assert trunc2(68683.835) == 68683.83
    assert trunc2(138813.9072) == 138813.90
    # 0.29 is stored as 0.28999999999999998 - must still cut to 0.29, not 0.28.
    assert trunc2(0.29) == 0.29
    assert trunc2(170.0) == 170.0
    # Negatives cut toward zero (Net Bal can go negative on a heavy-expense day).
    assert trunc2(-1.559) == -1.55


def test_oil_rows_amount_and_closing_stock():
    data = DailySalesEntryInput(
        oils=[
            OilRow(label="2T/1.20 ML Total#", qty="4", rate="62", opening="20"),
            OilRow(label="2T/2.40 ML Total#", qty="", rate="118", opening="10"),
        ]
    )
    result = compute(data)
    assert result.oils[0].amount == 248.0
    assert result.oils[0].closing == 16.0
    # blank qty -> closing mirrors opening, no amount
    assert result.oils[1].amount is None
    assert result.oils[1].closing == 10.0
    assert result.oil_total == 248.0


def test_full_chain_net_bal_hand_off():
    data = DailySalesEntryInput(
        hs=GasRow(current="1317.52", last="0", rate="105.36"),
        ms=GasRow(current="1000", last="0", rate="117.70"),
        oils=[OilRow(label="2T/1.20 ML Total#", qty="4", rate="62", opening="20")],
        expenses=["500+100=600", "250"],
        credit_card_amounts=["1000", "500"],
        new_credits=[NewCreditRow(ltrs="10", rate="105.36")],
        old_credit_amounts=["300"],
        phone_pay_settled="150",
        phone_pay_unsettled="200",
        night_cash="5000",
    )
    result = compute(data)

    # Row amounts are truncated to paise before they are summed (trunc2), so the
    # HS row contributes 138813.90, not 138813.9072.
    gas = 138813.90 + 117700.0
    oil = 248.0
    expenses = 850.0
    new_credits = 1053.6
    cards = 1500.0
    # EVERY non-cash line is subtracted - Net Bal is the physical cash handed
    # over (client-confirmed 2026-09-11 against three real filled forms).
    net_bal = gas + oil - expenses - 150.0 - 200.0 - new_credits - cards - 5000.0

    assert result.gas_total == gas
    assert result.oil_total == oil
    assert result.expenses_total == expenses
    assert result.new_credits_total == new_credits
    assert result.credit_cards_total == cards
    assert result.sum_cash == gas + oil
    assert result.net_bal_hand_off == trunc2(net_bal)
    # Section 6 is excluded from today's total, reported separately.
    assert result.sum_old_credit == 300.0


def test_zero_row_sections_submit_clean():
    """All repeating sections empty - must compute without error (SDD 11.2)."""
    result = compute(DailySalesEntryInput())
    assert result.net_bal_hand_off == 0.0
    assert result.oil_total == 0.0
    assert result.credit_cards_total == 0.0
