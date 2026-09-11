"""Excel import fallback: a natural, paper-shaped workbook (no SVR field keys).

This is what a person gets from asking an AI chat tool (or anyone else) to type up
a photographed handwritten Daily Sales Report into a spreadsheet - labels next to
values, shaped like the physical form, not our own keyed export/template. See
docs/01-BRD-Requirement-Gathering/OCR-findings-2026-09-09.md and the 2026-09-10
client report for the real-world case this covers.

The fixture below is a from-scratch reconstruction of that layout (not the actual
client file, which arrived corrupted in transit) - self-consistent test values, not
the real report's numbers. Once the real .xlsx is available in
docs/01-BRD-Requirement-Gathering/ocr-samples/, re-run this module's approach
against it directly to confirm the label-matching still lines up.
"""

from __future__ import annotations

import io

from openpyxl import Workbook

from svr_backend.calc.daily_sales_entry import compute_payload
from svr_backend.excel import blank_template, parse_workbook


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


def test_keyed_export_still_takes_priority_over_paper_layout():
    """A real SVR export/template must never fall through to the heuristic path."""
    _, meta, warnings = parse_workbook(blank_template("12BC4523V-OFF"))
    assert not warnings
    assert meta["pump_serial"] == "12BC4523V-OFF"
