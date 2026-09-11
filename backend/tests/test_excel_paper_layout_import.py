"""Excel import fallback: a natural, paper-shaped workbook (no SVR field keys).

This is what a person gets from asking an AI chat tool (or anyone else) to type up
a photographed handwritten Daily Sales Report into a spreadsheet - labels next to
values, shaped like the physical form, not our own keyed export/template. See
docs/01-BRD-Requirement-Gathering/OCR-findings-2026-09-09.md and the 2026-09-10
client report for the real-world case this covers.

The first fixture below is a from-scratch reconstruction of that layout (it was
written before the real client file could be read - it arrived corrupted the
first time it was sent). The second test reads the real file, now in
docs/01-BRD-Requirement-Gathering/ocr-samples/SVR_Daily_Sales_FILLED_SEP10_BLACK_WHITE.xlsx,
confirming the label-matching holds against an actual AI-transcribed sheet, not
just a hand-built approximation of one.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from openpyxl import Workbook

from svr_backend.calc.daily_sales_entry import compute_payload
from svr_backend.excel import blank_template, parse_workbook

_REAL_SAMPLE = (
    Path(__file__).resolve().parents[2]
    / "docs" / "01-BRD-Requirement-Gathering" / "ocr-samples"
    / "SVR_Daily_Sales_FILLED_SEP10_BLACK_WHITE.xlsx"
)
# One real workbook with two sheets - the station's Road and Office data for the
# same day, side by side (2026-09-11 client sample). Everything is keyed by Pump
# Serial Number, so importing this file must read the sheet for whichever pump
# is selected, never just whatever sheet happens to be "active".
_REAL_MULTI_SHEET = (
    Path(__file__).resolve().parents[2]
    / "docs" / "01-BRD-Requirement-Gathering" / "ocr-samples"
    / "SVR_Daily_Sales_10Sep2026_12BC4523V-RD.xlsx"
)


def _natural_workbook() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    rows = [
        ["SVR Indian Oil Service Station - Daily Sales Report"],
        ["Dt&Time:", "09/09/26", "Pump Serial# 12BC4523V-Off/11CC2012V-Road", None, "Name"],
        ["Gas Sale(s)"],
        ["Pump", "Current Reading", "Last Shift Reading", "Cons[Last-Current]",
         "Rate", "Amount", "IOCL #"],
        ["Diesel (HS-Nz1)", 1317.52, 1300, None, 105.36, None, None],
        ["Petrol (MS-Nz-2)", 1000, 900, None, 117.70, None, None],
        ["Total Amt", None, None, None, None, None, None],
        ["Oil Sale(s)"],
        ["Item", "Quantity", "Rate", "Opening Stock", "Closing Stock", "Amount"],
        ["2T/1.20 ML Total#", 4, 60, 100, 96, None],
        ["2T/2.40 ML Total#", None, 65, 50, 50, None],
        ["Acid Water Total 1 Lts", 2, 20, 28, 26, None],
        ["Acid Water Total 5 Lts", None, 120, 19, 19, None],
        ["20/40 Engine Total in Lts", 3, 130, 42, 39, None],
        ["Total Amt Oil(s)", None, None, None, None, None],
        ["Expenses"],
        ["Description", "Amount"],
        ["Daily Diesel(5L) & Petrol(5L) + Density Testing + Beta = Total Amt", 600],
        ["Any Other Expenses", 75],
        ["Last Night Cash Hand-off Persons Name-Signature-Amount", 5000],
        ["Total Amt Expenses", None],
        ["Credit Cards Swiping(s)"],
        ["Card Holder / Terminal ID", "Card Type", "Rate", "Transaction/Receipt #", "Amount"],
        [None, None, None, None, 1000],
        [None, None, None, None, 250],
        ["Total Amt Credit Cards", None, None, None, None],
        ["Today New Credit(s)"],
        ["Creditor Name", "Type (1. Diesel 2. Petrol)", "In Ltrs", "Rate", "Amount", "Signature"],
        ["Ramesh", "1", 10, 105.36, None, None],
        ["Total Amt New Credits Today"],
        ["Old/Pending Credit Received [NOT part of today's Daily Sales Report]"],
        ["Customer Name", "Amount", "Old Credit Given Date", "Signature"],
        ["Suresh", 300, None, None],
        ["Summary - Cash Hand Off"],
        ["Cash (Gas+ Oils) Total Amt", None],
        ["Expenses Total Amt", None],
        ["Phone Pay Settled Total Amt as of 6:30 AM", 10],
        ["Phone Pay Not Settled Total Amt As of today ___ AM", 20],
        ["New Credits Total Amt", None],
        ["Credit Cards Swiping Total Amt", None],
        ["Night Cash Hand Off Total Amt", 5000],
        ["Net Bal Hand off (Cash - Expenses + Phone Pay Not Settled + "
         "New Credits + Card Swiping + Night Cash)", None],
        ["Total Amt - Old Credit Amt/Given by Customer Name"
         "(Do NOT Include in Today's Total)", None],
        ["Verified by"],
        ["Mgr Name", "Signature", "Date"],
    ]
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_natural_paper_layout_is_parsed_without_field_keys():
    payload, meta, warnings = parse_workbook(_natural_workbook())

    assert any("paper-form layout" in w for w in warnings)
    assert meta["pump_serial"] is None  # never guessed from free text - operator picks it

    assert payload["hs"]["current"] == 1317.52
    assert payload["hs"]["last"] == 1300
    assert payload["ms"]["current"] == 1000
    assert payload["ms"]["last"] == 900

    assert [o.get("qty") for o in payload["oils"]] == [4, None, 2, None, 3]

    assert payload["expenses"] == [600, 75, 5000]
    assert payload["credit_card_amounts"] == [1000, 250]
    assert payload["new_credits"] == [{"ltrs": 10, "rate": 105.36}]
    assert payload["old_credit_amounts"] == [300]
    assert payload["phone_pay_settled"] == 10
    assert payload["phone_pay_unsettled"] == 20
    assert payload["night_cash"] == 5000

    # Never trusts the sheet's own computed totals - recompute is authoritative
    # (SDD ADR-5). This sheet's totals were left blank on purpose to prove that.
    result = compute_payload(payload)
    assert result["hs"]["cons"] == 17.52
    assert result["net_bal_hand_off"] is not None


@pytest.mark.skipif(not _REAL_MULTI_SHEET.exists(), reason="real client sample not present")
def test_multi_sheet_workbook_picks_the_sheet_for_the_selected_pump():
    data = _REAL_MULTI_SHEET.read_bytes()

    road_payload, _, road_warnings = parse_workbook(data, pump_serial="12BC4523V-RD")
    assert not any("could not match" in w for w in road_warnings)
    assert road_payload["hs"] == {"current": 267859.1, "last": 267841.93}

    office_payload, _, office_warnings = parse_workbook(data, pump_serial="11CC2012V-OFF")
    assert not any("could not match" in w for w in office_warnings)
    assert office_payload["hs"] == {"current": 1488457.6, "last": 1487828.11}


@pytest.mark.skipif(not _REAL_MULTI_SHEET.exists(), reason="real client sample not present")
def test_multi_sheet_workbook_without_a_hint_warns_instead_of_guessing():
    payload, _, warnings = parse_workbook(_REAL_MULTI_SHEET.read_bytes())
    assert any("2 sheets" in w for w in warnings)
    # Still returns *something* usable (the active sheet) rather than failing outright.
    assert payload["hs"]["current"] is not None


def test_keyed_export_still_takes_priority_over_paper_layout():
    """A real SVR export/template must never fall through to the heuristic path."""
    _, meta, warnings = parse_workbook(blank_template("12BC4523V-RD"))
    assert not warnings
    assert meta["pump_serial"] == "12BC4523V-RD"


@pytest.mark.skipif(not _REAL_SAMPLE.exists(), reason="real client sample not present")
def test_real_client_workbook_reads_the_gas_and_expense_figures():
    """The actual file the client sent (2026-09-10), typed up from a handwritten
    Daily Sales Report. Confirms the fixture above isn't just a lucky guess at the
    real layout - Gas Sale(s), Expenses, and two Summary lines all reproduce the
    figures printed on the paper form exactly.
    """
    payload, meta, warnings = parse_workbook(_REAL_SAMPLE.read_bytes())

    assert any("paper-form layout" in w for w in warnings)
    assert meta["pump_serial"] is None  # never guessed - operator picks it

    assert payload["hs"] == {"current": 1487828.11, "last": 1487517.43}
    assert payload["ms"] == {"current": 661164.69, "last": 660581.14}
    assert payload["expenses"] == [1363.3, 117, 35500]
    assert payload["phone_pay_settled"] == 8560
    assert payload["night_cash"] == 36980.3
    # These sections are genuinely blank on this particular day's form.
    assert payload["credit_card_amounts"] == []
    assert payload["new_credits"] == []
    assert payload["old_credit_amounts"] == []

    result = compute_payload(payload)
    assert result["hs"]["cons"] == 310.68  # matches the paper form exactly
    assert result["ms"]["cons"] == 583.55
