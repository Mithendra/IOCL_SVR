"""Reconcile the Daily Trial Balance against the client's own SEP12 tab.

Source: docs/01-BRD-Requirement-Gathering/ocr-samples/Trail_balance_12-SEP-2026.xlsx,
sheet ``SEP12`` - the most recent filled Trial Balance on file (2026-09-12).

This is the gate the client set on 2026-09-11: a module is not verified until its
final figures reproduce a real filled form to the paisa. "The fields render" is
not verification. Every number below is transcribed from that tab, and every
formula asserted here is one the tab itself computes.
"""

from __future__ import annotations

from svr_backend.calc.daily_trial_balance import (
    Section1Input,
    TrialBalanceInput,
    compute,
    derive_manual,
)

# --- Section 1, rows 3-4 --------------------------------------------------------
HS_IOCL_LAST, HS_IOCL_CURRENT = 5514, 4937
MS_IOCL_LAST, MS_IOCL_CURRENT = 7584, 7043
HS_ACTUAL_CONSUMP = 591.8699999998789
MS_ACTUAL_CONSUMP = 546.2700000000186
HS_MARGIN = 1530.425699999684
MS_MARGIN = 2238.787800000077
HS_IOCL_ADV = 1527.8924999875599
MS_IOCL_ADV = 598.4612000021152

# --- Section 2.1 Oil Sales (row 25) and 5 / 6 / 7 -------------------------------
OIL_TOTAL = 416
BUY_RATE_HS, BUY_RATE_MS = 102.75, 113.56
STOCK_VALUE_TOTAL = 1307079.83
CASH_BOOK_VALUE = 1995980.46
NET_WORTH = 3303060.29

TESTING_DEDUCTION = 5.5  # SEP12: "Daily Testing" = "Actual Consump" - 5.5


def _computed():
    return compute(
        TrialBalanceInput(
            s1=Section1Input(
                hs_yesterday=HS_IOCL_LAST, hs_current=HS_IOCL_CURRENT,
                ms_yesterday=MS_IOCL_LAST, ms_current=MS_IOCL_CURRENT,
            ),
            s3_hs_consumption=HS_ACTUAL_CONSUMP,
            s3_ms_consumption=MS_ACTUAL_CONSUMP,
            buy_rate_hs=BUY_RATE_HS,
            buy_rate_ms=BUY_RATE_MS,
            testing_deduction=TESTING_DEDUCTION,
            cash_book_value=CASH_BOOK_VALUE,
        )
    )


def test_section1_columns_reproduce_the_sheet():
    r = _computed()
    # D = IOCL Last - IOCL Current
    assert r.hs.diff == 577
    assert r.ms.diff == 541
    # F Consump Diff = Actual Consump - [Last-Current]
    assert round(r.hs.computer_pump_diff, 4) == round(14.869999999878928, 4)
    assert round(r.ms.computer_pump_diff, 4) == round(5.2700000000186265, 4)
    # G Daily Testing = Actual Consump - 5.5
    assert round(r.hs.deduct_testing, 4) == round(586.3699999998789, 4)
    assert round(r.ms.deduct_testing, 4) == round(540.7700000000186, 4)


def test_section5_stock_value_reproduces_the_sheet():
    """5.1/5.2 Ltrs are the IOCL CURRENT readings, priced at Buy Rate."""
    r = _computed()
    assert r.hs.stock_ltrs == HS_IOCL_CURRENT
    assert r.ms.stock_ltrs == MS_IOCL_CURRENT
    assert r.hs.stock_amount == 507276.75      # 4937 x 102.75
    assert r.ms.stock_amount == 799803.08      # 7043 x 113.56
    assert r.stock_value_total == STOCK_VALUE_TOTAL


def test_section6_total_working_capital_reproduces_the_sheet():
    r = _computed()
    assert r.trial_balance_7_1 == CASH_BOOK_VALUE     # 6.1
    assert r.trial_balance_7_2 == STOCK_VALUE_TOTAL   # 6.2
    assert r.trial_balance_7_3 == NET_WORTH           # 6.3 = 3,303,060.29


# --- the operator-entered sections, whose totals the sheet also computes --------

MANUAL = {
    "section1": {
        "hs_margin": HS_MARGIN, "ms_margin": MS_MARGIN,
        "hs_iocl_adv": HS_IOCL_ADV, "ms_iocl_adv": MS_IOCL_ADV,
    },
    "section3": {
        "onhand": 76096.51, "night": 40000, "morning": 15680.5, "daytotal": 0,
        "oldcredit": 14750.4,
        "iocl": 499485.08, "indianbank": 1311580.42, "yesbank": 11634.55,
        "ppunsettled": 3579, "ppsettled": None,
        "new_credits": [
            {"type": "AirTel Hari New Credit", "amount": 11674},
            {"type": "Salary Advance Ravindra", "amount": 10000},
            {"type": "Sajja Function Hall - New Credit", "amount": 0},
            {"type": "Anil New Credit", "amount": 1500},
        ],
    },
    "section4": {
        "yesterday": 1861869.74, "todaysale": 125594.5722, "reported": CASH_BOOK_VALUE,
        "yesbank_return": 8525.95,
    },
    "section7": {"yesterday": 3289672.2800000003, "profit": 4185.213499999761},
    "section8": {
        "f1": 1861869.74, "f2": 125594.5722, "f4": CASH_BOOK_VALUE,
        "mgmt_yesterday_tb": 3289672.2800000003, "mgmt_profit": 4185.213499999761,
        # SEP12 rows 102-104, the sign-off block.
        "prepared_by": "Gopi",
        "verified_by": "Girish/Sriharsha",
        "sent_by": "Gopi & Girish",
    },
    "section10": {
        "hs_afterunload": 12207, "hs_old": 2207, "hs_new": 12079, "hs_load": 10000,
        "ms_afterunload": 13344, "ms_old": 3344, "ms_new": 13303, "ms_load": 10000,
    },
}


def _derived():
    # The second argument is 6.3 Net Worth, not Section 5's Stock Value. Passing
    # the wrong one is exactly the bug this file caught: the unit maths was right
    # while the API wired `section6["total"]` (Stock Value) into it, which put 7.4
    # out by the entire cash/book value. `test_the_whole_sheet_through_the_api`
    # below is what actually pins the wiring.
    return derive_manual(MANUAL, NET_WORTH, OIL_TOTAL)


def test_the_whole_sheet_through_the_api(client, auth_headers, conn):
    """SEP12 end to end through the real HTTP path - the gate that matters.

    The per-function tests above exercise the formulas in isolation and all passed
    while the running application was wrong, because the API handed `derive_manual`
    Section 5's Stock Value where 6.3 Net Worth was wanted. Only driving the actual
    endpoint with the actual sheet exposed it.
    """
    h = auth_headers("Manager")
    conn.execute(
        "INSERT INTO system_parameter (name, value, effective_date, updated_by) "
        "VALUES ('testing_density_deduction', 5.5, '2026-09-01', 'test')"
    )
    conn.commit()

    body = {
        "s1_hs_yesterday": HS_IOCL_LAST, "s1_hs_current": HS_IOCL_CURRENT,
        "s1_ms_yesterday": MS_IOCL_LAST, "s1_ms_current": MS_IOCL_CURRENT,
        "s54_cash_book_value": CASH_BOOK_VALUE,
        "manual": MANUAL,
    }
    r = client.put("/daily-trial-balance/2026-09-02", json=body, headers=h)
    assert r.status_code == 200, r.text
    c = r.json()["computed"]
    d = c["derived"]

    assert c["section6"]["total"] == STOCK_VALUE_TOTAL      # 5.3 Stock Value
    assert c["section7"]["7_3_total"] == NET_WORTH          # 6.3 Net Worth
    assert d["section3"]["total15"] == CASH_BOOK_VALUE      # 3.15
    assert round(d["section4"]["total3"], 4) == round(1987464.3122, 4)   # 4.3
    assert round(d["section4"]["diff"], 4) == round(8516.147799999919, 4)  # 4.5
    assert round(d["section7"]["total3"], 4) == round(3293857.4935, 4)   # 7.3
    # 7.4 = 6.3 Net Worth - 7.3 Projected. This is the assertion that fails if the
    # wrong total is wired in: it reported -1,986,777.66 against the sheet's
    # 9,202.80 when `section6["total"]` was passed instead of the net worth.
    assert round(d["section7"]["diff"], 4) == round(9202.796500000171, 4)
    assert d["section7"]["total5"] == NET_WORTH                          # 7.5
    assert round(d["section8"]["mgmt_networth_diff"], 4) == round(9202.796500000171, 4)
    assert d["section10"]["hs"]["total"] == 9872 and d["section10"]["hs"]["lost"] == 128


def test_section1_cross_fuel_columns():
    d = _derived()["section1"]
    assert round(d["margin_total"], 4) == round(3769.2134999997606, 4)   # I4
    assert d["two_t_sales"] == OIL_TOTAL                                  # J4, pulled
    assert round(d["total_sale_amt"], 4) == round(4185.213499999761, 4)  # K4 = I + J
    assert round(d["iocl_profit"], 4) == round(2126.353699989675, 4)     # M4


def test_section3_cash_and_bank_chain():
    d = _derived()["section3"]
    assert d["total6"] == 146527.41       # 3.6  = 3.1+3.2+3.3+3.4+3.5
    assert d["total7"] == 146527.41       # 3.7
    assert d["total13"] == 1972806.46     # 3.13 = 3.7+3.8+3.9+3.10+3.11+3.12
    assert d["new_credits_total"] == 23174
    assert d["total15"] == CASH_BOOK_VALUE  # 3.15 = 1,995,980.46, and 4.4 and 6.1


def test_section4_reconciliation():
    d = _derived()["section4"]
    assert round(d["total3"], 4) == round(1987464.3122, 4)            # 4.3
    assert round(d["diff"], 4) == round(8516.147799999919, 4)         # 4.5
    # The sheet's side panel: Difference Amount less the Yes Bank return.
    assert round(d["total_difference"], 4) == round(-9.802200000081939, 4)


def test_section7_projected_trial_balance():
    d = _derived()["section7"]
    assert round(d["total3"], 4) == round(3293857.4935, 4)            # 7.3
    assert round(d["diff"], 4) == round(9202.796500000171, 4)         # 7.4
    assert d["total5"] == NET_WORTH                                   # 7.5 = 6.3


def test_section8_mirrors_section4_and_the_mgmt_summary():
    d = _derived()["section8"]
    assert round(d["f3"], 4) == round(1987464.3122, 4)                # 8.3 = 4.3
    assert round(d["f5"], 4) == round(8516.147799999919, 4)           # 8.5 = 4.5
    assert d["mgmt_actual_networth"] == NET_WORTH
    assert round(d["mgmt_projected_networth"], 4) == round(3293857.4935, 4)
    assert round(d["mgmt_networth_diff"], 4) == round(9202.796500000171, 4)


def test_section10_load_unload():
    d = _derived()["section10"]
    assert d["hs"]["total"] == 9872   # 12079 - 2207
    assert d["hs"]["lost"] == 128     # 10000 - 9872
    assert d["ms"]["total"] == 9959   # 13303 - 3344
    assert d["ms"]["lost"] == 41


def test_the_sep12_oil_rates_are_in_rate_master(conn):
    """Section 2.1 prices every oil row directly. Migration 0017/0018 had to infer
    these from the old five-row list and got three of six wrong - these come off
    the client's own sheet instead."""
    from svr_backend.rates import latest_effective_rates

    rates = latest_effective_rates(conn, "2026-09-12")
    assert rates["oil1"]["sell_rate"] == 17.00    # 2T/1.50 ML
    assert rates["oil4"]["sell_rate"] == 120.00   # Battery Water Total 5 Lts
    assert rates["oil6"]["sell_rate"] == 20.00    # Battery Water Total 1 Lts
    assert rates["oil3"]["sell_rate"] == 30.00    # Acid Water Total 1 Lts
    assert rates["oil7"]["sell_rate"] == 140.00   # 20/40 Engine Total in 05. Lts
    assert rates["oil5"]["sell_rate"] == 270.00   # 20/40 Engine Total in 1 Lts


def test_the_testing_deduction_is_effective_dated_not_replaced(conn):
    """5.5 from 2026-09-12; every earlier Trial Balance keeps the 10.0 that was in
    force on its own date, so no historical record moves."""
    from svr_backend.params import get_param

    assert get_param(conn, "testing_density_deduction", 0.0, as_of="2026-09-12") == 5.5
    # The seed itself is effective 2026-08-28, so pick a date after that and
    # before the change - AUG11/AUG12 predate the parameter entirely.
    assert get_param(conn, "testing_density_deduction", 0.0, as_of="2026-09-01") == 10.0


# --- Section 8 leaves the station on its own (BRD; client 2026-09-12) ----------


def test_section8_exports_to_excel_with_its_own_figures(client, auth_headers):
    """Section 8 goes to management daily, so it exports alone - not as part of a
    whole-form dump. The file must carry the SEP12 figures, not empty cells."""
    import io

    from openpyxl import load_workbook

    h = auth_headers("Manager")
    client.put("/daily-trial-balance/2026-09-03", json={
        "s1_hs_yesterday": HS_IOCL_LAST, "s1_hs_current": HS_IOCL_CURRENT,
        "s1_ms_yesterday": MS_IOCL_LAST, "s1_ms_current": MS_IOCL_CURRENT,
        "s54_cash_book_value": CASH_BOOK_VALUE, "manual": MANUAL,
    }, headers=h)

    r = client.get("/daily-trial-balance/2026-09-03/export-section8", headers=h)
    assert r.status_code == 200
    assert "SVR-Section8-2026-09-03.xlsx" in r.headers["content-disposition"]

    ws = load_workbook(io.BytesIO(r.content)).active
    cells = {row[0]: row[1] for row in ws.iter_rows(min_row=5, max_col=2, values_only=True)}
    assert cells["8.1 Yesterday's SVR Cash/Book Value"] == 1861869.74
    assert round(cells["8.3 Projected SVR Cash/Book Value"], 4) == round(1987464.3122, 4)
    assert round(cells["8.5 Difference - Actual Reported Minus Projected"], 4) == round(
        8516.147799999919, 4
    )
    assert cells["Prepared by"] == "Gopi"          # 8.9 sign-off rides along
    assert cells["8.4 Actual Reported SVR Cash/Book Value"] == CASH_BOOK_VALUE


def test_section8_whatsapp_message_carries_the_same_numbers(client, auth_headers):
    """A phone on the road will not open a spreadsheet, and the station has always
    sent these as a message - so the same figures go out as plain text."""
    h = auth_headers("Manager")
    client.put("/daily-trial-balance/2026-09-04", json={
        "s1_hs_current": HS_IOCL_CURRENT, "s1_ms_current": MS_IOCL_CURRENT,
        "s54_cash_book_value": CASH_BOOK_VALUE, "manual": MANUAL,
    }, headers=h)

    text = client.get(
        "/daily-trial-balance/2026-09-04/section8-message", headers=h
    ).json()["text"]
    assert "Daily Management Reporting - 2026-09-04" in text
    assert "1,861,869.74" in text     # 8.1
    assert "1,987,464.31" in text     # 8.3, derived
    assert "8,516.15" in text         # 8.5, derived
    assert "Prepared by: Gopi" in text


def test_sales_can_export_section8_too(client, auth_headers):
    """The maker prepares it; blocking the export behind Manager would just push
    the figures back onto paper."""
    assert client.get(
        "/daily-trial-balance/2026-09-05/export-section8", headers=auth_headers("Sales")
    ).status_code == 200
