"""Pre-install readiness check (2026-09-11): the three workflows the client asked
to verify before the next installer build, run end to end against the real
September files - not just individually-tested pieces.

1. Daily Sales import (PDF via Scan/Upload, Excel via Import from Excel) for
   2026-09-09 and 2026-09-10, both pumps.
2. Daily Sales Summary -> Daily Trial Balance: Section 3 pulls automatically
   (no manual "transfer" step) once both pumps have submitted; the remaining
   sections (Section 1 IOCL tank readings, Section 5.4 cash/book value, and
   the ADR-1 manual blob) are entered by hand, per day.
3. Inventory Tracking accepts real data (restock, on-hand) from 2026-09-10.

One real, by-design constraint this surfaced (not a bug - ADR-2's maker-
checker carry-forward, the same control that would have caught the legacy
workbook's SEP02 skip): a NEW Trial Balance date cannot be started while an
earlier date is still open. Testing both 09-09 and 09-10 means 09-09 must be
Closed & Signed Off (Manager/Owner) before 09-10's Trial Balance becomes
available - covered explicitly below so it isn't mistaken for a defect.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_SAMPLES = Path(__file__).resolve().parents[2] / "docs" / "01-BRD-Requirement-Gathering" / "ocr-samples"

OFFICE = "11CC2012V-OFF"
ROAD = "12BC4523V-RD"

# (shift_date, pump_serial) -> (pdf filename, xlsx filename)
_REAL_FILES = {
    ("2026-09-09", OFFICE): ("SVR_Daily_Sales_09Sep2026_ 12BC4523V-OFF.pdf",
                             "SVR_Daily_Sales_09Sep2026_11CC2012V-OFF.xlsx"),
    ("2026-09-09", ROAD): ("SVR_Daily_Sales_09Sep2026_12BC4523V-RD_.pdf",
                           "SVR_Daily_Sales_09Sep2026_12BC4523V-RD_.xlsx"),
    ("2026-09-10", OFFICE): ("SVR_Daily_Sales_10Sep2026_11CC2012V-OFF.pdf",
                             "SVR_Daily_Sales_10Sep2026_11CC2012V-OFF.xlsx"),
    ("2026-09-10", ROAD): ("SVR_Daily_Sales_10Sep2026_12BC4523V-RD.pdf",
                           "SVR_Daily_Sales_10Sep2026_12BC4523V-RD.xlsx"),
}

# Ground truth HS consumption per (date, pump), read directly off the paper forms.
_EXPECTED_HS_CONS = {
    ("2026-09-09", OFFICE): 310.68,
    ("2026-09-09", ROAD): 0.0,       # repair-day zero-activity report
    ("2026-09-10", OFFICE): 629.49,
    ("2026-09-10", ROAD): 17.17,
}


def _import_pdf(client, headers, name):
    path = _SAMPLES / name
    r = client.post(
        "/daily-sales-entry/ocr",
        files={"file": (name, path.read_bytes(), "application/pdf")},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()["payload"]


def _import_xlsx(client, headers, name, pump_serial):
    path = _SAMPLES / name
    r = client.post(
        f"/daily-sales-entry/import-excel?pump_serial={pump_serial}",
        files={"file": (name, path.read_bytes(), "application/octet-stream")},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()["payload"]


def test_workflow_1_daily_sales_import_both_formats_both_dates_both_pumps(
    client, auth_headers, conn
):
    if not all((_SAMPLES / pdf).exists() and (_SAMPLES / xlsx).exists()
               for pdf, xlsx in _REAL_FILES.values()):
        pytest.skip("real client samples not present")

    h = auth_headers("Sales")
    for (shift_date, pump), (pdf_name, xlsx_name) in _REAL_FILES.items():
        pdf_payload = _import_pdf(client, h, pdf_name)
        xlsx_payload = _import_xlsx(client, h, xlsx_name, pump)
        # Both formats agree on the figure that matters most - what actually
        # feeds carry-forward, the calc engine, and Trial Balance Section 3.
        assert str(pdf_payload["hs"]["current"]).rstrip("0").rstrip(".") == \
            str(xlsx_payload["hs"]["current"]).rstrip("0").rstrip(".")

        # Save via the PDF-derived payload, mirroring the real Scan/Upload ->
        # review -> Save flow (saving both would try to create a second row
        # for the same pump/day/submitter and 409, same as the real form).
        body = dict(pdf_payload)
        body["pump_serial"] = pump
        body["shift_date"] = shift_date
        r = client.post("/daily-sales-entry", json=body, headers=h)
        assert r.status_code == 201, r.text
        assert r.json()["result"]["hs"]["cons"] == _EXPECTED_HS_CONS[(shift_date, pump)]


def test_workflow_2_daily_summary_transfers_into_trial_balance_automatically(
    client, auth_headers
):
    """Each test gets its own fresh DB (conftest.py's ``conn`` fixture), so this
    seeds its own Daily Sales Entry data rather than depending on test order."""
    if not all((_SAMPLES / pdf).exists() for pdf, _ in _REAL_FILES.values()):
        pytest.skip("real client samples not present")

    hs = auth_headers("Sales")
    hm = auth_headers("Manager")
    for (shift_date, pump), (pdf_name, _) in _REAL_FILES.items():
        payload = _import_pdf(client, hs, pdf_name)
        body = dict(payload)
        body["pump_serial"] = pump
        body["shift_date"] = shift_date
        client.post("/daily-sales-entry", json=body, headers=hs)

    # Daily Sales Summary already shows both pumps for each date.
    s9 = client.get("/daily-sales-summary/2026-09-09", headers=hm).json()
    assert s9["both_present"] is True
    assert s9["combined"]["hs_liters"]["combined"] == 310.68  # 310.68 (office) + 0.0 (road)

    s10 = client.get("/daily-sales-summary/2026-09-10", headers=hm).json()
    assert s10["both_present"] is True
    assert s10["combined"]["hs_liters"]["combined"] == 646.66  # 629.49 + 17.17

    # Trial Balance for 2026-09-09 (the very first date ever - no earlier day
    # to block it). Section 3 pulls the combined total automatically, no
    # manual "transfer" step - just PUT the remaining manual figures.
    r = client.put(
        "/daily-trial-balance/2026-09-09",
        json={"s1_hs_current": 500000, "s1_ms_current": 300000, "s54_cash_book_value": 100000},
        headers=hs,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pulled"]["s3_source"] == "daily_sales_summary"
    assert body["pulled"]["s3_hs_consumption"] == 310.68

    # By design (ADR-2 maker-checker carry-forward): 2026-09-10 cannot be
    # started while 2026-09-09 is still open. Not a bug - the same control
    # that would have caught the legacy workbook's SEP02 skip directly.
    blocked = client.put("/daily-trial-balance/2026-09-10", json={"s1_hs_current": 1}, headers=hs)
    assert blocked.status_code == 409
    assert "2026-09-09" in blocked.json()["detail"]

    # Close & Sign Off 2026-09-09 (Manager/Owner only) - this is what unlocks
    # 2026-09-10 and auto-creates its draft, seeded from 09-09's own closing.
    fin = client.post("/daily-trial-balance/2026-09-09/finalize", headers=hm)
    assert fin.status_code == 200
    assert fin.json()["status"] == "finalized"

    ten = client.get("/daily-trial-balance/2026-09-10", headers=hs).json()
    assert ten["carried_from"] == "2026-09-09"
    assert ten["inputs"]["s1_hs_yesterday"] == 500000  # carried from 09-09's s1_hs_current
    assert ten["pulled"]["s3_hs_consumption"] == 646.66  # this day's own combined total

    # Now 2026-09-10 can be completed and finalized too.
    r = client.put(
        "/daily-trial-balance/2026-09-10",
        json={"s1_hs_current": 500100, "s1_ms_current": 300200, "s54_cash_book_value": 90000},
        headers=hs,
    )
    assert r.status_code == 200, r.text
    fin10 = client.post("/daily-trial-balance/2026-09-10/finalize", headers=hm)
    assert fin10.status_code == 200
    assert fin10.json()["status"] == "finalized"


def test_workflow_3_inventory_tracking_accepts_real_data_from_sep_10(client, auth_headers):
    hm = auth_headers("Manager")
    r = client.post(
        "/inventory/restock",
        json={"item_key": "oil1", "quantity": 10, "restock_date": "2026-09-10"},
        headers=hm,
    )
    assert r.status_code == 201, r.text

    rows = client.get("/inventory?as_of=2026-09-10", headers=hm).json()
    oil1 = next(x for x in rows if x["item_key"] == "oil1")
    assert oil1["opening_stock"] == 40  # seed on_hand, untouched by a restock
    assert oil1["received_today"] == 10
    assert oil1["closing_stock"] == 50  # 40 + 10 - 0
