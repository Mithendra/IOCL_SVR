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
    # This side of the form is almost entirely the paper's own "-" markers -
    # every one of them reads back as blank, not as a literal dash (2026-09-11).
    # Rate is the exception: a blank Rate cell is a real 0, so it can never fall
    # back to Rate Master downstream (2026-09-11 oil-rate fix).
    assert road_payload["oils"] == [{"qty": None, "rate": 0, "opening": None}] * 5
    assert road_payload["credit_card_amounts"] == []
    assert road_payload["phone_pay_settled"] is None
    assert road_payload["night_cash"] is None

    office_payload, _, office_warnings = parse_workbook(data, pump_serial="11CC2012V-OFF")
    assert not any("could not match" in w for w in office_warnings)
    assert office_payload["hs"] == {"current": 1488457.6, "last": 1487828.11}
    assert office_payload["phone_pay_settled"] == 14698
    assert office_payload["phone_pay_unsettled"] == 4660


@pytest.mark.skipif(not _REAL_MULTI_SHEET.exists(), reason="real client sample not present")
def test_multi_sheet_workbook_without_a_hint_warns_instead_of_guessing():
    payload, _, warnings = parse_workbook(_REAL_MULTI_SHEET.read_bytes())
    assert any("2 sheets" in w for w in warnings)
    # Still returns *something* usable (the active sheet) rather than failing outright.
    assert payload["hs"]["current"] is not None


_REAL_ROAD_SEP9 = (
    Path(__file__).resolve().parents[2]
    / "docs" / "01-BRD-Requirement-Gathering" / "ocr-samples"
    / "SVR_Daily_Sales_09Sep2026_12BC4523V-RD_.xlsx"
)


@pytest.mark.skipif(not _REAL_ROAD_SEP9.exists(), reason="real client sample not present")
def test_zero_activity_repair_day_reads_current_equal_to_last():
    """The Road pump's real 2026-09-09 file (repair day) - Current Reading ==
    Last Shift Reading (the meter didn't move), not blank and not skipped."""
    payload, _, _ = parse_workbook(_REAL_ROAD_SEP9.read_bytes(), pump_serial="12BC4523V-RD")
    assert payload["hs"] == {"current": 267841.93, "last": 267841.93}
    assert payload["ms"] == {"current": 288877.28, "last": 288877.28}
    assert compute_payload(payload)["hs"]["cons"] == 0.0


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


def test_paper_layout_tolerates_real_world_label_variance():
    """Client-reported (2026-09-11): a differently-typed real workbook came back
    with Oil Sale(s) quantities and Phone Pay Settled missing entirely - the
    label-matching was exact-substring only, so minor real-world differences in
    spacing/punctuation (a hyphen instead of a slash, a missing space, "Amount"
    instead of "Total Amt") silently dropped fields it should have read. Every
    label below is deliberately reworded (never the exact form wording used
    elsewhere in this file) to lock in that this no longer happens."""
    wb = Workbook()
    ws = wb.active
    rows = [
        ["SVR Indian Oil Service Station - Daily Sales Report"],
        ["Gas Sale(s)"],
        ["Pump", "Current Reading", "Last Shift Reading"],
        ["Diesel(HS-Nz1)", 100, 90],  # no space before the paren
        ["Petrol(MS-Nz-2)", 50, 40],
        ["Total Amt"],
        ["Oil Sale(s)"],
        ["Item", "Quantity", "Rate", "Opening Stock", "Closing Stock", "Amount"],
        ["2T-1.20ML Total", 4, 60, 100, 96, None],   # hyphen, no space before ML
        ["2T-2.40ML Total", None, 65, 50, 50, None],
        ["Acid Water Total1Lts", 2, 20, 28, 26, None],  # no space before "1"
        ["Acid Water Total5Lts", None, 120, 19, 19, None],
        ["20-40 Engine Total in Lts", 3, 130, 42, 39, None],  # hyphen not slash
        ["Total Amt Oil(s)"],
        ["Expenses"],
        ["Description", "Amount"],
        ["Daily Diesel(5L) & Petrol(5L) + Density Testing + Beta = Total Amt", 600],
        ["Any Other Expenses", 75],
        ["Last Night Cash Hand-off Persons Name-Signature-Amount", 5000],
        ["Total Amt Expenses"],
        ["Credit Cards Swiping(s)"],
        ["Card Holder / Terminal ID", "Card Type", "Rate", "Transaction/Receipt #", "Amount"],
        ["Today New Credit(s)"],
        ["Creditor Name", "Type (1. Diesel 2. Petrol)", "In Ltrs", "Rate", "Amount", "Signature"],
        ["Old/Pending Credit Received"],
        ["Customer Name", "Amount", "Old Credit Given Date", "Signature"],
        ["Summary-Cash Hand Off"],  # no spaces around the hyphen
        ["Phone Pay Settled Amount as of 6:30 AM", 10],  # "Amount", not "Total Amt"
        ["Phone Pay Not-Settled Amount", 20],
        ["Night Cash Hand-Off Amount", 5000],  # hyphenated, "Amount" not "Total Amt"
    ]
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)

    payload, _, warnings = parse_workbook(buf.getvalue())
    assert any("paper-form layout" in w for w in warnings)

    assert payload["hs"] == {"current": 100, "last": 90}
    assert payload["ms"] == {"current": 50, "last": 40}
    assert [o.get("qty") for o in payload["oils"]] == [4, None, 2, None, 3]
    assert [o.get("opening") for o in payload["oils"]] == [100, 50, 28, 19, 42]
    assert payload["expenses"] == [600, 75, 5000]
    assert payload["phone_pay_settled"] == 10
    assert payload["phone_pay_unsettled"] == 20
    assert payload["night_cash"] == 5000


_A4_TEMPLATE = (
    Path(__file__).resolve().parents[2]
    / "docs" / "01-BRD-Requirement-Gathering" / "ocr-samples"
    / "SVR_DSR_Empty_11CC2012V-OFF_A4.xlsx"
)


@pytest.mark.skipif(not _A4_TEMPLATE.exists(), reason="real client sample not present")
def test_a4_template_reads_every_section_once_filled():
    """Client-reported (2026-09-11): Oil Sale(s) wasn't fully populating from a
    real filled sheet. Fills in the client's own blank A4 template (both sheets
    are identical multi-pump workbooks; the exact real column layout, including
    every merged-cell master, is used here - not a hand-built approximation) and
    confirms every section round-trips, in particular Oil Sale(s) Opening Stock
    (only Quantity was ever read before this fix) and every Summary figure."""
    from openpyxl import load_workbook

    wb = load_workbook(_A4_TEMPLATE)
    ws = wb["11CC2012V-OFF"]

    # 1. Gas Sale(s) - B/G are the merged-range masters for Current/Last Shift.
    ws["B7"], ws["G7"] = 1500.5, 1450.0  # Diesel (HS)
    ws["B8"], ws["G8"] = 900.25, 850.0  # Petrol (MS)

    # 2. Oil Sale(s) - C/J are the Quantity/Opening Stock masters per row.
    # Row 16 (Acid Water 5 Lts) has no sale today - Quantity genuinely blank -
    # but Opening Stock is still filled, proving the two are read independently.
    for row, qty, opening in ((13, 4, 100), (14, 2, 50), (15, 1, 28), (16, None, 19), (17, 3, 42)):
        ws.cell(row=row, column=3, value=qty)  # C
        ws.cell(row=row, column=10, value=opening)  # J

    # 3. Expenses - J22/J23/J24 are the Amount masters for the 3 fixed rows.
    ws["J22"], ws["J23"], ws["J24"] = 600, 75, 5000

    # 4. Credit Cards Swiping(s) - Q29/Q30 are the Amount masters for two rows.
    ws["Q29"], ws["Q30"] = 1000, 500

    # 5. Today New Credit(s) - H39/J39 are the In Ltrs/Rate masters for row 1.
    ws["H39"], ws["J39"] = 10, 105.36

    # 6. Old/Pending Credit Received - E46 is the Amount master for row 1.
    ws["E46"] = 300

    # 7. Summary - J52/J53/J56 are the only 3 operator-entered Summary values
    # (everything else in that section is computed and recomputed downstream).
    ws["J52"], ws["J53"], ws["J56"] = 8560, 200, 36980.3

    buf = io.BytesIO()
    wb.save(buf)

    payload, meta, warnings = parse_workbook(buf.getvalue(), pump_serial="11CC2012V-OFF")
    assert any("paper-form layout" in w for w in warnings)
    assert meta["pump_serial"] is None  # never guessed - operator picks it

    assert payload["hs"] == {"current": 1500.5, "last": 1450.0}
    assert payload["ms"] == {"current": 900.25, "last": 850.0}
    assert [o.get("qty") for o in payload["oils"]] == [4, 2, 1, None, 3]
    assert [o.get("opening") for o in payload["oils"]] == [100, 50, 28, 19, 42]
    assert payload["expenses"] == [600, 75, 5000]
    assert payload["credit_card_amounts"] == [1000, 500]
    assert payload["new_credits"] == [{"ltrs": 10, "rate": 105.36}]
    assert payload["old_credit_amounts"] == [300]
    assert payload["phone_pay_settled"] == 8560
    assert payload["phone_pay_unsettled"] == 200
    assert payload["night_cash"] == 36980.3

    result = compute_payload(payload)
    assert result["hs"]["cons"] == 50.5
    assert result["ms"]["cons"] == 50.25
    # Net Bal Hand off now includes Phone Pay Settled (2026-09-11 formula fix).
    assert result["net_bal_hand_off"] is not None
