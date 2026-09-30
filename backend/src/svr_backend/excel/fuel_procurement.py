"""Fuel Procurement -> .xlsx. One row per fuel-load record (client, 2026-09-30:
"export to Excel sheet format would be nice"), for month-end and year-end tax
reporting - the filtered list as it stands on screen, nothing recomputed.
"""

from __future__ import annotations

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

SHEET = "Fuel Procurement"

# The app's own colours (app.css --io-orange section bars, th { background:
# #eef1fa }), same as every other export in this app.
_TITLE_FILL = PatternFill("solid", fgColor="F37022")
_HEAD_FILL = PatternFill("solid", fgColor="EEF1FA")
_MONEY = "#,##0.00"
_LITRES = "#,##0"

_COLUMNS = (
    ("Date", "shift_date", None),
    ("Fuel", "fuel_type", None),
    ("IOCL Load (L)", "iocl_load_litres", _LITRES),
    ("Received After Unload (L)", "received_litres", _LITRES),
    ("Lost (L)", "lost_litres", _LITRES),
    ("Rate (₹/L)", "rate", _MONEY),
    ("Amount", "amount", _MONEY),
    ("Vehicle / Ref", "vehicle_ref", None),
    ("Status", "status", None),
)


def build_workbook(rows: list[dict]) -> bytes:
    """``rows`` is the same list GET /fuel-procurement returns - each dict
    already carries the computed ``lost_litres``/``amount`` fields."""
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET

    ws["A1"] = "SVR Indian Oil Service Station - Fuel Procurement"
    ws["A1"].font = Font(bold=True, size=13)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(_COLUMNS))
    ws["A2"] = f"{len(rows)} load line(s)"
    ws["A2"].font = Font(italic=True, size=9, color="666666")

    head_row = 4
    for col, (label, _key, _fmt) in enumerate(_COLUMNS, start=1):
        cell = ws.cell(row=head_row, column=col, value=label)
        cell.font = Font(bold=True, color="00246E")
        cell.fill = _HEAD_FILL
        cell.alignment = Alignment(horizontal="left", wrap_text=True)

    total_hs = total_ms = 0.0
    for r, row in enumerate(rows, start=head_row + 1):
        for col, (_label, key, fmt) in enumerate(_COLUMNS, start=1):
            cell = ws.cell(row=r, column=col, value=row.get(key))
            if fmt:
                cell.number_format = fmt
        if row.get("fuel_type") == "HS":
            total_hs += row.get("amount") or 0
        else:
            total_ms += row.get("amount") or 0

    total_row = head_row + len(rows) + 2
    ws.cell(row=total_row, column=1, value="Total Cost HS").font = Font(bold=True)
    c = ws.cell(row=total_row, column=2, value=round(total_hs, 4))
    c.number_format = _MONEY
    c.font = Font(bold=True)
    ws.cell(row=total_row + 1, column=1, value="Total Cost MS").font = Font(bold=True)
    c = ws.cell(row=total_row + 1, column=2, value=round(total_ms, 4))
    c.number_format = _MONEY
    c.font = Font(bold=True)
    ws.cell(row=total_row + 2, column=1, value="Grand Total").font = Font(bold=True, color="E31E24")
    c = ws.cell(row=total_row + 2, column=2, value=round(total_hs + total_ms, 4))
    c.number_format = _MONEY
    c.font = Font(bold=True, color="E31E24")

    widths = (12, 8, 16, 20, 12, 12, 16, 20, 12)
    for col, width in enumerate(widths, start=1):
        ws.column_dimensions[chr(64 + col)].width = width

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


_MONTH_SHEET = "Load Summary"
_MONTH_COLUMNS = (
    "Month", "Loads", "Litres HS", "Litres MS",
    "Lost HS", "Lost MS", "Cost HS", "Cost MS", "Total Cost",
)
_MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def build_monthly_workbook(rows: list[dict]) -> bytes:
    """One row per calendar month, from every load on file - the same
    aggregation the screen's own "Load Summary - Month by Month" shows
    (client, 2026-09-30: "you should have an export to Excel there" too, not
    just on the raw row list)."""
    by_month: dict[str, dict] = {}
    for row in rows:
        key = (row.get("shift_date") or "")[:7]
        m = by_month.setdefault(key, {
            "dates": set(), "hs": 0.0, "ms": 0.0,
            "lost_hs": 0.0, "lost_ms": 0.0, "cost_hs": 0.0, "cost_ms": 0.0,
        })
        m["dates"].add(row.get("shift_date"))
        if row.get("fuel_type") == "HS":
            m["hs"] += row.get("iocl_load_litres") or 0
            m["lost_hs"] += row.get("lost_litres") or 0
            m["cost_hs"] += row.get("amount") or 0
        else:
            m["ms"] += row.get("iocl_load_litres") or 0
            m["lost_ms"] += row.get("lost_litres") or 0
            m["cost_ms"] += row.get("amount") or 0

    wb = Workbook()
    ws = wb.active
    ws.title = _MONTH_SHEET

    ws["A1"] = "SVR Indian Oil Service Station - Fuel Procurement, Load Summary"
    ws["A1"].font = Font(bold=True, size=13)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(_MONTH_COLUMNS))

    head_row = 3
    for col, label in enumerate(_MONTH_COLUMNS, start=1):
        cell = ws.cell(row=head_row, column=col, value=label)
        cell.font = Font(bold=True, color="00246E")
        cell.fill = _HEAD_FILL

    grand_hs = grand_ms = 0.0
    r = head_row
    for key in sorted(by_month):
        r += 1
        m = by_month[key]
        year, month = key.split("-")
        label = f"{_MONTH_NAMES[int(month) - 1]} {year}"
        total = m["cost_hs"] + m["cost_ms"]
        grand_hs += m["cost_hs"]
        grand_ms += m["cost_ms"]
        values = (
            label, len(m["dates"]), m["hs"], m["ms"],
            m["lost_hs"], m["lost_ms"], m["cost_hs"], m["cost_ms"], total,
        )
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row=r, column=col, value=value)
            if col in (3, 4, 5, 6):
                cell.number_format = _LITRES
            elif col in (7, 8, 9):
                cell.number_format = _MONEY

    r += 2
    ws.cell(row=r, column=1, value="Grand Total").font = Font(bold=True, color="E31E24")
    c = ws.cell(row=r, column=7, value=round(grand_hs, 4))
    c.number_format = _MONEY
    c.font = Font(bold=True, color="E31E24")
    c = ws.cell(row=r, column=8, value=round(grand_ms, 4))
    c.number_format = _MONEY
    c.font = Font(bold=True, color="E31E24")
    c = ws.cell(row=r, column=9, value=round(grand_hs + grand_ms, 4))
    c.number_format = _MONEY
    c.font = Font(bold=True, color="E31E24")

    widths = (14, 8, 12, 12, 10, 10, 14, 14, 14)
    for col, width in enumerate(widths, start=1):
        ws.column_dimensions[chr(64 + col)].width = width

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
