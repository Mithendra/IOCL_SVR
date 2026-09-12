"""Section 8 (Daily Management Reporting) -> .xlsx.

Section 8 is the one part of the Trial Balance that leaves the station: it goes to
management daily, historically as a WhatsApp message (BRD; the client's own
mockup carries an "Export Section 8 to Excel" button and a WhatsApp number field,
confirmed again 2026-09-12). So it exports on its own, not as part of a
whole-form dump - a manager wants the five reporting lines and the net-worth
summary, not eleven sections.

Layout follows the SEP12 tab's own Section 8 block, in its own order, so a
recipient comparing the two is looking at the same rows in the same sequence.
"""

from __future__ import annotations

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

SHEET = "Daily Mgmt Reporting"

_TITLE_FILL = PatternFill("solid", fgColor="1F3B5C")
_HEAD_FILL = PatternFill("solid", fgColor="EEF1F5")
_MONEY = "#,##0.00"


def _n(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def build_section8_workbook(view: dict) -> bytes:
    """``view`` is the GET /daily-trial-balance/{date} payload."""
    manual = view.get("manual") or {}
    s8 = manual.get("section8") if isinstance(manual.get("section8"), dict) else {}
    derived = ((view.get("computed") or {}).get("derived") or {}).get("section8") or {}

    wb = Workbook()
    ws = wb.active
    ws.title = SHEET

    ws["A1"] = "SVR Indian Oil Service Station - Daily Management Reporting"
    ws["A1"].font = Font(bold=True, size=13)
    ws["A2"] = f"Section 8 · {view.get('shift_date')} · status: {view.get('status')}"
    ws["A2"].font = Font(italic=True, size=9, color="666666")

    rows: list[tuple[str, object]] = [
        ("__section__", "Daily Management Reporting"),
        ("8.1 Yesterday's SVR Cash/Book Value", _n(s8.get("f1"))),
        ("8.2 Today's Sales After Expenses, Testing and Density Adjustments", _n(s8.get("f2"))),
        ("8.3 Projected SVR Cash/Book Value", _n(derived.get("f3"))),
        ("8.4 Actual Reported SVR Cash/Book Value", _n(s8.get("f4"))),
        ("8.5 Difference - Actual Reported Minus Projected", _n(derived.get("f5"))),
        ("__section__", "8.6 Regular Expenses"),
    ]
    for row in s8.get("regular_expenses") or []:
        if isinstance(row, dict):
            rows.append((f"   {row.get('category') or '(uncategorised)'}", _n(row.get("amount"))))
    rows.append(("Total Regular Expenses", _n(derived.get("regular_expenses_total"))))

    rows.append(("__section__", "8.7 Old Credit Collections"))
    for row in s8.get("old_credit_collections") or []:
        if isinstance(row, dict):
            rows.append((f"   {row.get('type') or '(unspecified)'}", _n(row.get("amount"))))
    rows.append(("Total Old Credit Collections", _n(derived.get("old_credit_total"))))

    rows += [
        ("__section__", "8.8 Management Summary"),
        ("Cash Value Difference - escalate if above Rs 100", _n(derived.get("f5"))),
        ("Today's Actual Reported Trial Balance / SVR Net Worth",
         _n(derived.get("mgmt_actual_networth"))),
        ("Yesterday's Actual Reported Trial Balance", _n(s8.get("mgmt_yesterday_tb"))),
        ("Daily Profit Including 2T Sales", _n(s8.get("mgmt_profit"))),
        ("Projected SVR Net Worth", _n(derived.get("mgmt_projected_networth"))),
        ("Actual Reported SVR Net Worth", _n(derived.get("mgmt_actual_networth"))),
        ("Difference - Actual Reported Minus Projected", _n(derived.get("mgmt_networth_diff"))),
        ("Actual Profit after all Daily Expenses", _n(s8.get("mgmt_actual_profit"))),
        ("__section__", "8.9 Sign-off"),
        ("Prepared by", s8.get("prepared_by")),
        ("Verified by", s8.get("verified_by")),
        ("Sent to SVR and Bank Statement to Group Email", s8.get("sent_by")),
    ]

    hdr = 4
    for col, name in enumerate(("Line", "Amount"), 1):
        c = ws.cell(row=hdr, column=col, value=name)
        c.font = Font(bold=True)
        c.fill = _HEAD_FILL

    r = hdr + 1
    for label, value in rows:
        if label == "__section__":
            cell = ws.cell(row=r, column=1, value=value)
            for col in (1, 2):
                cc = ws.cell(row=r, column=col)
                cc.font = Font(bold=True, color="FFFFFF")
                cc.fill = _TITLE_FILL
            cell.alignment = Alignment(horizontal="left")
        else:
            ws.cell(row=r, column=1, value=label)
            cell = ws.cell(row=r, column=2, value=value)
            if isinstance(value, float):
                cell.number_format = _MONEY
            cell.alignment = Alignment(horizontal="right")
            if label.startswith("Total"):
                for col in (1, 2):
                    ws.cell(row=r, column=col).font = Font(bold=True)
        r += 1

    ws.column_dimensions["A"].width = 62
    ws.column_dimensions["B"].width = 18

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def section8_message(view: dict) -> str:
    """The same figures as one plain-text message, for WhatsApp.

    A phone is not going to open a spreadsheet on the road, and the station has
    always sent these numbers as a message. Kept short and in the sheet's order.
    """
    manual = view.get("manual") or {}
    s8 = manual.get("section8") if isinstance(manual.get("section8"), dict) else {}
    derived = ((view.get("computed") or {}).get("derived") or {}).get("section8") or {}

    def money(v) -> str:
        n = _n(v)
        return "-" if n is None else f"{n:,.2f}"

    lines = [
        f"SVR Daily Management Reporting - {view.get('shift_date')}",
        "",
        f"8.1 Yesterday's Cash/Book: {money(s8.get('f1'))}",
        f"8.2 Today's Sales after Expenses: {money(s8.get('f2'))}",
        f"8.3 Projected Cash/Book: {money(derived.get('f3'))}",
        f"8.4 Actual Reported Cash/Book: {money(s8.get('f4'))}",
        f"8.5 Difference: {money(derived.get('f5'))}",
        "",
        f"Actual Reported Net Worth: {money(derived.get('mgmt_actual_networth'))}",
        f"Projected Net Worth: {money(derived.get('mgmt_projected_networth'))}",
        f"Difference: {money(derived.get('mgmt_networth_diff'))}",
        "",
        f"Prepared by: {s8.get('prepared_by') or '-'}",
        f"Verified by: {s8.get('verified_by') or '-'}",
    ]
    return "\n".join(lines)
