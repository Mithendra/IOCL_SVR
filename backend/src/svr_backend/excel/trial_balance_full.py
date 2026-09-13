"""The whole Daily Trial Balance — all eleven sections — as one .xlsx.

Section 8 exports on its own for the daily management send
(``trial_balance_section8.py``); this is the complete day's record, for the file
and for anyone who wants it in Excel. Client asked for it 2026-09-12.

Section order and numbering follow the station's own workbook, not the SDD's, so
a row here lands where the operator expects it.
"""

from __future__ import annotations

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

SHEET = "Daily Trial Balance"
_TITLE_FILL = PatternFill("solid", fgColor="1F3B5C")
_HEAD_FILL = PatternFill("solid", fgColor="EEF1F5")
_MONEY = "#,##0.00"


def _n(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return v  # a name, a date - keep it as text


class _Rows:
    """Collects (label, value) pairs; a label of None marks a section band."""

    def __init__(self) -> None:
        self.items: list[tuple[str | None, object]] = []

    def band(self, title: str) -> None:
        self.items.append((None, title))

    def line(self, label: str, value) -> None:
        self.items.append((label, _n(value)))

    def rows(self, block, label_key: str, prefix: str) -> None:
        for r in block or []:
            if isinstance(r, dict):
                self.line(f"   {prefix} {r.get(label_key) or ''}".rstrip(), r.get("amount"))


def build_full_workbook(view: dict) -> bytes:
    """``view`` is the GET /daily-trial-balance/{date} payload."""
    manual = view.get("manual") or {}
    computed = view.get("computed") or {}
    derived = computed.get("derived") or {}
    pulled = view.get("pulled") or {}
    inputs = view.get("inputs") or {}

    def sec(key: str) -> dict:
        v = manual.get(key)
        return v if isinstance(v, dict) else {}

    def der(key: str) -> dict:
        v = derived.get(key)
        return v if isinstance(v, dict) else {}

    s1c = computed.get("section1") or {}
    d1 = der("section1")
    r = _Rows()

    r.band("1. IOCL Stock Readings")
    for fuel, name in (("hs", "Diesel (HS)"), ("ms", "Petrol (MS)")):
        f = s1c.get(fuel) or {}
        r.line(f"{name} - IOCL Last", inputs.get(f"s1_{fuel}_yesterday"))
        r.line(f"{name} - IOCL Current", inputs.get(f"s1_{fuel}_current"))
        r.line(f"{name} - [Last-Current]", f.get("diff"))
        r.line(f"{name} - Actual Consump", f.get("consumption"))
        r.line(f"{name} - Consump Diff", f.get("computer_pump_diff"))
        r.line(f"{name} - Daily Testing", f.get("deduct_testing"))
        r.line(f"{name} - Margin", d1.get(f"{fuel}_margin"))
        r.line(f"{name} - IOCL Adv", d1.get(f"{fuel}_iocl_adv"))
    r.line("Margin Total", d1.get("margin_total"))
    r.line("2T Sales", d1.get("two_t_sales"))
    r.line("Total Sale Amt", d1.get("total_sale_amt"))
    r.line("IOCL Profit", d1.get("iocl_profit"))

    r.band("2. Day Sales Report (pulled from the day's Daily Sales Entries)")
    r.line("Actual Consump HS - both pumps", pulled.get("s3_hs_consumption"))
    r.line("Actual Consump MS - both pumps", pulled.get("s3_ms_consumption"))
    r.line("Oil Sale(s) Total", pulled.get("oil_total"))

    s3, d3 = sec("section3"), der("section3")
    r.band("3. Daily Cash & Bank Balances")
    for no, label, key in (
        ("3.1", "On Hand Old Cash", "onhand"),
        ("3.2", "Night Cash Hand off", "night"),
        ("3.3", "Morning Cash Hand off Total", "morning"),
        ("3.4", "Day Total", "daytotal"),
        ("3.5", "Old Credit Cash hand off", "oldcredit"),
    ):
        r.line(f"{no} {label}", s3.get(key))
    r.line("3.6 Total", d3.get("total6"))
    r.line("3.7 Old Cash + Current Day Total", d3.get("total7"))
    for no, label, key in (
        ("3.8", "IOCL Card End Balance (-)", "iocl"),
        ("3.9", "Indian Bank Statement Ending Balance", "indianbank"),
        ("3.10", "Yes Bank Statement Ending Balance", "yesbank"),
        ("3.11", "Phone Pay UnSettled Amt", "ppunsettled"),
        ("3.12", "Phone Pay Settled Amt", "ppsettled"),
    ):
        r.line(f"{no} {label}", s3.get(key))
    r.line("3.13 Total Amt", d3.get("total13"))
    r.rows(s3.get("new_credits"), "type", "3.14")
    r.line("3.15 Total Cash/Book Amount as of Today", d3.get("total15"))
    r.line("Special Note - Section 3", s3.get("special_note") or "")

    s4, d4 = sec("section4"), der("section4")
    r.band("4. Cash/Book Value Reconciliation")
    r.line("4.1 Yesterday SVR Cash/Book Value", s4.get("yesterday"))
    r.line("4.2 Total Today Sale Amount After Expenses", s4.get("todaysale"))
    r.line("4.3 Total - Projected", d4.get("total3"))
    r.line("4.4 Today SVR Cash/Book Value Reported", s4.get("reported"))
    r.line("4.5 Diff Reported - Projected", d4.get("diff"))
    r.rows(s4.get("expenses"), "category", "4.6")
    r.line("Total Expenses", d4.get("expenses_total"))
    r.rows(s4.get("remittance"), "type", "4.7")
    r.line("Total Credit Remittance", d4.get("remittance_total"))
    r.line("Yes Bank Return Amount", s4.get("yesbank_return"))
    r.line("Total Difference", d4.get("total_difference"))
    r.line("Special Note - Section 4", s4.get("special_note") or "")

    s6c = computed.get("section6") or {}
    s7c = computed.get("section7") or {}
    r.band("5. Stock Value")
    for fuel, name, rate in (
        ("hs", "Diesel (HS)", "buy_rate_hs"), ("ms", "Petrol (MS)", "buy_rate_ms")
    ):
        f = s1c.get(fuel) or {}
        r.line(f"{name} - Ltrs", f.get("stock_ltrs"))
        r.line(f"{name} - Rate", pulled.get(rate))
        r.line(f"{name} - Amount", f.get("stock_amount"))
    r.line("Total Stock Value", s6c.get("total"))

    r.band("6. Trial Balance - Actual Reported - Today")
    r.line("6.1 Actual Reported SVR Cash/Book Value", s7c.get("7_1_cash_book_value"))
    r.line("6.2 Closing Stock Value", s7c.get("7_2_stock_value"))
    r.line("6.3 Total Working Capital / Net Worth", s7c.get("7_3_total"))

    s7, d7 = sec("section7"), der("section7")
    r.band("7. Trial Balance - Projected - Today")
    r.line("7.1 Yesterday's Actual Reported Trial Balance", s7.get("yesterday"))
    r.line("7.2 Today's Profit Including 2T Sales", d7.get("profit"))
    r.line("7.3 Today's Projected Trial Balance", d7.get("total3"))
    r.line("7.4 Difference - Actual Reported Minus Projected", d7.get("diff"))
    r.line("7.5 Today's Actual Reported Trial Balance", d7.get("total5"))
    r.line("Special Note - Section 7", s7.get("special_note") or "")

    s8, d8 = sec("section8"), der("section8")
    r.band("8. Daily Management Reporting")
    r.line("8.1 Yesterday's SVR Cash/Book Value", s8.get("f1"))
    r.line("8.2 Today's Sales After Expenses, Testing and Density", s8.get("f2"))
    r.line("8.3 Projected SVR Cash/Book Value", d8.get("f3"))
    r.line("8.4 Actual Reported SVR Cash/Book Value", s8.get("f4"))
    r.line("8.5 Difference - Actual Reported Minus Projected", d8.get("f5"))
    r.rows(s8.get("regular_expenses"), "category", "8.6")
    r.line("Total Regular Expenses", d8.get("regular_expenses_total"))
    r.rows(s8.get("old_credit_collections"), "type", "8.7")
    r.line("Total Old Credit Collections", d8.get("old_credit_total"))
    r.line("Actual Reported SVR Net Worth", d8.get("mgmt_actual_networth"))
    r.line("Projected SVR Net Worth", d8.get("mgmt_projected_networth"))
    r.line("Difference - Actual Reported Minus Projected", d8.get("mgmt_networth_diff"))
    r.line("Actual Profit after all Daily Expenses", d8.get("mgmt_actual_profit"))
    r.line("Prepared by", s8.get("prepared_by") or "")
    r.line("Verified by", s8.get("verified_by") or "")
    r.line("Sent to SVR and Bank Statement to Group Email", s8.get("sent_by") or "")
    r.line("Special Note - Section 8", s8.get("special_note") or "")
    r.line("Special Note - Management Summary", s8.get("mgmt_note") or "")

    r.band("9. Daily Mgr Calculation")
    for row in sec("section9").get("ledger") or []:
        if isinstance(row, dict):
            r.line(f"   {row.get('date') or ''}".rstrip(), row.get("total_sale"))

    s10, d10 = sec("section10"), der("section10")
    r.band("10. Load/Unload Details")
    for fuel, name in (("hs", "Diesel (HS)"), ("ms", "Petrol (MS)")):
        r.line(f"{name} - After Unload Comp", s10.get(f"{fuel}_afterunload"))
        r.line(f"{name} - Old Reading", s10.get(f"{fuel}_old"))
        r.line(f"{name} - New Computer", s10.get(f"{fuel}_new"))
        r.line(f"{name} - IOCL Load", s10.get(f"{fuel}_load"))
        r.line(f"{name} - Lost", (d10.get(fuel) or {}).get("lost"))
        r.line(f"{name} - Total", (d10.get(fuel) or {}).get("total"))

    s11 = sec("section11")
    r.band("11. Old/New Credit Sales Details")
    r.line("11.1 NEW Airtel Balance", s11.get("new_airtel"))
    r.line("11.2 Old Airtel Balance", s11.get("old_airtel"))

    # ------------------------------------------------------------------ render
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET
    ws["A1"] = "SVR Indian Oil Service Station - Daily Trial Balance"
    ws["A1"].font = Font(bold=True, size=13)
    shift = (manual.get("header") or {}).get("shift") or ""
    ws["A2"] = f"{view.get('shift_date')} · status: {view.get('status')}" + (
        f" · {shift}" if shift else ""
    )
    ws["A2"].font = Font(italic=True, size=9, color="666666")

    hdr = 4
    for col, name in enumerate(("Line", "Amount"), 1):
        c = ws.cell(row=hdr, column=col, value=name)
        c.font = Font(bold=True)
        c.fill = _HEAD_FILL

    at = hdr + 1
    for label, value in r.items:
        if label is None:
            ws.cell(row=at, column=1, value=value)
            for col in (1, 2):
                cc = ws.cell(row=at, column=col)
                cc.font = Font(bold=True, color="FFFFFF")
                cc.fill = _TITLE_FILL
        else:
            ws.cell(row=at, column=1, value=label)
            cell = ws.cell(row=at, column=2, value=value)
            if isinstance(value, float):
                cell.number_format = _MONEY
                cell.alignment = Alignment(horizontal="right")
            else:
                cell.alignment = Alignment(horizontal="left", wrap_text=True)
            if label.startswith(("Total", "6.3", "3.15", "4.5", "7.5")):
                for col in (1, 2):
                    ws.cell(row=at, column=col).font = Font(bold=True)
        at += 1

    ws.column_dimensions["A"].width = 58
    ws.column_dimensions["B"].width = 22
    ws.freeze_panes = "A5"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
