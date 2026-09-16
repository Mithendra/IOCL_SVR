"""SEP15 reconciled end to end - the first day the app was never tuned against.

Every earlier reconciliation in this repo was written after looking at the tab it
reconciles to. SEP15 arrived on 2026-09-15 with the rates and the inventory
already sorted out by the station, and the engine reproduced all seven headline
figures first time, with no adjustment. That is the difference between a formula
that fits and a formula that works.

Figures are read off the client's own files and cited so they can be checked:

  Trail_balance_15SEP2026.xlsx, tab SEP15
      B3/C3 4251 / 3978     IOCL diesel last / current
      B4/C4 5787 / 5294     IOCL petrol last / current
      D15   284.48          combined diesel consumption (road pump only)
      D16   501.68          combined petrol consumption
      G3    279.48          = E3 - 5     one diesel nozzle ran
      G4    496.68          = E4 - 5     one petrol nozzle ran
      K4    2,870.6980      Total Sale Amt
      D49   2,217,954.86    = 'SEP14'!D52
      D50   87,840.24       typed: the day's sales less Beta/Density/Testing
      D52   2,305,795.10    counted cash and bank
      D53   0.00            the day balances exactly
      D69   1,009,926.14    Stock Value
      D74   3,315,721.24    Net Worth

  SVR_DSR_EMPTY_12BC4523V-RD_15Sept2026.xlsx, tab 'Daily Sales Report'
      O22   1,265.30        Daily Diesel(5L) & Petrol(5L) + Density Testing + Beta

The office pump filed Current = Last on both nozzles, so only the road pump's two
nozzles drew testing - 5 litres off each fuel, which is what G3 and G4 show.
"""

from __future__ import annotations

from svr_backend.calc.daily_trial_balance import (
    Section1Input,
    TrialBalanceInput,
    compute,
    derive_manual,
)

DAY = "2026-09-15"
HS_CONS, MS_CONS = 284.4799999999814, 501.6799999999348
SALES_TOTAL = 89105.54879999037       # SEP15!E27
BETA_TESTING = 1265.30                # Road DSR O22
YESTERDAY = 2217954.86                # SEP15!D49 = 'SEP14'!D52
REPORTED = 2305795.0999999996         # SEP15!D52
BUY_HS, BUY_MS = 102.75, 113.56
MARGIN_HS, MARGIN_MS = 2.61, 4.14
OIL_TOTAL = 85                        # SEP15!F26, 5 of 2T/2.40 at 17


def _run(testing_hs=5.0, testing_ms=5.0):
    data = TrialBalanceInput(
        s1=Section1Input(hs_yesterday=4251, hs_current=3978,
                         ms_yesterday=5787, ms_current=5294),
        s3_hs_consumption=HS_CONS, s3_ms_consumption=MS_CONS,
        buy_rate_hs=BUY_HS, buy_rate_ms=BUY_MS,
        testing_deduction=10.0,
        testing_deduction_hs=testing_hs, testing_deduction_ms=testing_ms,
        cash_book_value=REPORTED,
    )
    res = compute(data)
    der = derive_manual(
        {"section4": {"yesterday": YESTERDAY, "reported": REPORTED}},
        res.trial_balance_7_3, OIL_TOTAL,
        {"hs_deduct_testing": res.hs.deduct_testing,
         "ms_deduct_testing": res.ms.deduct_testing,
         "hs_computer_pump_diff": res.hs.computer_pump_diff,
         "ms_computer_pump_diff": res.ms.computer_pump_diff,
         "margin_rate_hs": MARGIN_HS, "margin_rate_ms": MARGIN_MS,
         "buy_rate_hs": BUY_HS, "buy_rate_ms": BUY_MS, "daily_expenses": 3299.98},
        {"sales_total": SALES_TOTAL, "beta_testing": BETA_TESTING},
    )
    return res, der


def test_section1_reproduces_the_sep15_tab():
    res, der = _run()
    assert round(res.hs.deduct_testing, 4) == round(279.4799999999814, 4)   # G3
    assert round(res.ms.deduct_testing, 4) == round(496.6799999999348, 4)   # G4
    assert round(der["section1"]["total_sale_amt"], 4) == round(2870.69799999968, 4)  # K4


def test_4_2_is_computed_and_lands_on_what_the_station_typed():
    """The strongest result here. 4.2 was hand-typed as 87,840.24; the engine
    derives 87,840.2488 from the day's own sales less the DSR's Beta/Testing
    line, and the counted gain (D52 - D49) is 87,840.24 as well. Three
    independent routes to the same figure.
    """
    _, der = _run()
    assert round(der["section4"]["todaysale_computed"], 4) == round(87840.24879999037, 4)
    assert der["section4"]["todaysale_source"] == "computed"
    assert round(REPORTED - YESTERDAY, 2) == 87840.24
    # 4.5 lands inside a paisa of the tab's own zero.
    assert abs(der["section4"]["diff"]) < 0.01


def test_stock_value_and_net_worth_match():
    res, _ = _run()
    assert round(res.stock_value_total, 2) == 1009926.14          # D69
    assert round(res.trial_balance_7_3, 2) == 3315721.24          # D74


def test_only_the_nozzles_that_ran_draw_testing():
    """The office pump filed Current = Last on both nozzles, so it drew nothing.
    Had the rule counted pumps rather than nozzles, or ignored the readings, this
    day would deduct 10 per fuel and K4 would be 33.75 lower."""
    _, der_one = _run(testing_hs=5.0, testing_ms=5.0)
    _, der_two = _run(testing_hs=10.0, testing_ms=10.0)
    assert round(der_one["section1"]["total_sale_amt"], 4) == round(2870.69799999968, 4)
    assert round(der_one["section1"]["total_sale_amt"]
                 - der_two["section1"]["total_sale_amt"], 2) == 33.75


# --- SEP16's difference panel -------------------------------------------------


def test_sep16_panel_reduces_a_37578_difference_to_2064():
    """The client's own SEP16 figures. Their side panel grew two lines this
    month, and the raw difference stopped meaning anything on its own:

        F54  =D53               -37,578.64   the raw difference
        F55  SVR Staff Salaries  37,500.00   paid, not yet counted
        F56  RTGS Charges            58.00   confirmed on the Indian Bank
                                             statement, 15 Sep: "Txn Amt
                                             16,88,000.00 Charges 58.00 /RTGS/"
        F57  =SUM(F54:F56)          -20.64   THE TRUE DIFFERENCE

    I read D53, called the day 37,578 out, and argued with the client's own
    20.64 before finding the panel that already explained it.
    """
    from svr_backend.calc.daily_trial_balance import derive_manual

    d = derive_manual(
        {"section4": {
            "yesterday": 2305795.0999999996,
            "todaysale": 171762.2496,
            "reported": 2439978.7099999995,
            "staff_salaries": 37500,
            "rtgs_charges": 58,
        }},
        0.0, 102, None, {"sales_total": None},
    )["section4"]
    assert round(d["diff"], 2) == -37578.64            # 4.5, the raw figure
    assert round(d["total_difference"], 2) == -20.64   # 4.10, the truth
    assert abs(d["total_difference"]) < 50             # inside the escalation limit


def test_the_panel_still_handles_a_bank_return_on_its_own():
    """SEP12's case must keep working: 4.5 read 8,516.15 where the truth was
    -9.80, because Yes Bank had returned 8,525.95."""
    from svr_backend.calc.daily_trial_balance import derive_manual

    d = derive_manual(
        {"section4": {"yesterday": 1861869.74, "todaysale": 125594.5722,
                      "reported": 1995980.46, "yesbank_return": 8525.95}},
        0.0, 416, None, {"sales_total": None},
    )["section4"]
    assert round(d["diff"], 2) == 8516.15
    assert round(d["total_difference"], 2) == -9.80
