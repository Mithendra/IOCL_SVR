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

# The station's own colour scheme (client, 2026-09-25: "Use IOCL colour codes
# for snapshot --> Clipboard"), already applied to the Section 8 clipboard
# snapshot (app.css .snap-band / .snap-red) - this export never got the same
# treatment, so it still went out in a generic navy nobody would recognise as
# the app's own report (client, 2026-09-27: "Color Codes are requested to use
# SVR standards ... not reflected").
#
# Orange section bands, matching .section-title / .snap-band, both driven by
# the same --io-orange the rest of the app uses.
_TITLE_FILL = PatternFill("solid", fgColor="F37022")
# The plain table header the app uses everywhere else (th { background:
# #eef1fa }), not a special case for this one export.
_HEAD_FILL = PatternFill("solid", fgColor="EEF1FA")
# .snap-red: a line management is meant to stop at. Applied to exactly the two
# lines the clipboard snapshot flags the same way - 8.8 and 8.15 - not every
# "Difference" line, which would be reading more escalation into the sheet
# than the app itself does.
_RED_FILL = PatternFill("solid", fgColor="FDECEB")
_RED_FONT = "E31E24"
_ESCALATION_PREFIXES = ("8.8 ", "8.15 ")
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
        # DERIVED, not the manual blob: 8.1/8.2/8.4, 8.10, 8.11 and 8.15 stopped
        # being typed on 2026-09-24 (they come from 4.1/4.2/4.4, 7.1, 7.2 and the
        # daily-expenses figure). Reading `s8` gave empty cells, and the client
        # got a workbook with the headline lines blank.
        ("8.1 Yesterday's SVR Cash/Book Value", _n(derived.get("f1"))),
        ("8.2 Today's Sales After Expenses, Testing and Density Adjustments",
         _n(derived.get("f2"))),
        ("8.3 Projected SVR Cash/Book Value", _n(derived.get("f3"))),
        ("8.4 Actual Reported SVR Cash/Book Value", _n(derived.get("f4"))),
        ("8.5 Difference - Actual Reported Minus Projected", _n(derived.get("f5"))),
        ("__section__", "8.6 Regular Expenses"),
    ]
    for row in s8.get("regular_expenses") or []:
        if isinstance(row, dict):
            rows.append((f"   {row.get('category') or '(uncategorised)'}", _n(row.get("amount"))))
    rows.append(("Total Regular Expenses", _n(derived.get("regular_expenses_total"))))

    # 8.7 is CARRIED from 4.7 Credit Remittance (client, 2026-09-24), so its rows
    # come from the engine, not the manual blob - a day where nothing was typed
    # into 8.7 still lists the day's remittances here.
    rows.append(("__section__", "8.7 Old Credit Remittances"))
    for row in derived.get("old_credit_rows") or []:
        if isinstance(row, dict):
            rows.append((f"   {row.get('type') or '(unspecified)'}", _n(row.get("amount"))))
    rows.append(("Total Old Credit Remittances", _n(derived.get("old_credit_total"))))

    # Every line numbered, the way the form numbers it (client, 2026-09-24:
    # "requested for Section 8.1 like line item numbers in the excel sheet").
    # An unnumbered line in a report sent to management cannot be pointed at in
    # a reply. 8.8-8.15 are the Management Summary; it carries no heading of its
    # own any more, because the numbers say what the block is.
    # Marks where the second Special Note panel starts, on the sheet - stripped
    # out again before the rows are written, so it costs nothing on the row.
    rows.append(("__panel2__", None))
    rows += [
        ("8.8 Cash Value Difference - escalate if above Rs 50", _n(derived.get("f5"))),
        ("8.9 Today's Actual Reported Trial Balance / SVR Net Worth",
         _n(derived.get("mgmt_actual_networth"))),
        ("8.10 Yesterday's Actual Reported Trial Balance",
         _n(derived.get("mgmt_yesterday_tb"))),
        ("8.11 Daily Profit Including 2T Sales", _n(derived.get("mgmt_profit"))),
        ("8.12 Projected SVR Net Worth", _n(derived.get("mgmt_projected_networth"))),
        ("8.13 Actual Reported SVR Net Worth", _n(derived.get("mgmt_actual_networth"))),
        ("8.14 Difference - Actual Reported Minus Projected",
         _n(derived.get("mgmt_networth_diff"))),
        ("8.15 Actual Profit after all Daily Expenses",
         _n(derived.get("mgmt_actual_profit"))),
        ("__section__", "8.16 Sign-off"),
        ("Prepared by", s8.get("prepared_by")),
        ("Verified by", s8.get("verified_by")),
        ("Sent to SVR and Bank Statement to Group Email", s8.get("sent_by")),
    ]

    # Client, 2026-09-27: "When There is special note within that Section 8
    # that should come on right hand side as you see in the Trail Entry form" -
    # the screen carries the note in a panel to the right of its own block
    # (screens/daily-trial-balance/sections.js: two "note" fields, section8's
    # own special_note beside 8.1-8.7, and mgmt_note beside 8.8-8.16), not as
    # rows tacked onto the bottom. Placed the same way here, one panel each,
    # rather than folded into the Line/Amount column they were never part of.
    #
    # Section 3's and Section 4's own notes are a different, earlier ask
    # (2026-09-25: "when there is a special note that should come as well") -
    # they are not part of THIS screen's two panels, so they still print below
    # rather than crowding either side panel with a note about a different
    # section.
    panel1_note = s8.get("special_note")
    panel2_note = s8.get("mgmt_note")
    other_notes = (
        ("Section 4 note", (manual.get("section4") or {}).get("special_note")),
        ("Section 3 note", (manual.get("section3") or {}).get("special_note")),
    )
    if any(n not in (None, "") for _, n in other_notes):
        rows.append(("__section__", "Other Notes"))
    for label, note in other_notes:
        if note not in (None, ""):
            rows.append((label, str(note)))

    hdr = 4
    for col, name in enumerate(("Line", "Amount"), 1):
        c = ws.cell(row=hdr, column=col, value=name)
        c.font = Font(bold=True)
        c.fill = _HEAD_FILL

    def _note_panel(top_row: int, bottom_row: int, text: str | None) -> None:
        if not text:
            return
        ws.cell(row=top_row, column=4, value="Special Note").font = Font(bold=True)
        ws.merge_cells(start_row=top_row + 1, start_column=4,
                        end_row=max(bottom_row, top_row + 3), end_column=5)
        cell = ws.cell(row=top_row + 1, column=4, value=text)
        cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        cell.font = Font(size=9)

    panel1_top = hdr + 1     # aligns with 8.1, the first real line
    panel2_top = None
    r = hdr + 1
    for label, value in rows:
        if label == "__panel2__":
            panel2_top = r
            continue
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
            if isinstance(value, str) and len(value) > 24:
                # A note, not a figure - let it wrap instead of running off the
                # right edge of a column sized for rupees.
                cell.alignment = Alignment(horizontal="left", wrap_text=True, vertical="top")
                ws.row_dimensions[r].height = 32
            else:
                cell.alignment = Alignment(horizontal="right")
            if label.startswith("Total"):
                # The same orange band the snapshot gives these two lines
                # (snapLine(..., { band: true })) - a total is a stopping
                # point, same as a section header.
                for col in (1, 2):
                    cc = ws.cell(row=r, column=col)
                    cc.font = Font(bold=True, color="FFFFFF")
                    cc.fill = _TITLE_FILL
            elif label.startswith(_ESCALATION_PREFIXES):
                for col in (1, 2):
                    ws.cell(row=r, column=col).fill = _RED_FILL
                ws.cell(row=r, column=1).font = Font(bold=True)
                ws.cell(row=r, column=2).font = Font(bold=True, color=_RED_FONT)
        r += 1

    # The two side panels, same placement as the screen: one beside 8.1-8.7,
    # one beside 8.8-8.16.
    _note_panel(panel1_top, (panel2_top or r) - 2, panel1_note)
    _note_panel(panel2_top or r, r - 1, panel2_note)

    ws.column_dimensions["A"].width = 62
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 2
    ws.column_dimensions["D"].width = 30
    ws.column_dimensions["E"].width = 20

    # The Special Note panels live in columns D/E, well past where A-B alone
    # would fit on a portrait page - which is exactly what put them on a
    # SECOND printed page, nowhere near the row they explain, the first time
    # this was tried (caught only by actually opening the file, not by reading
    # cell values). Landscape + fit-to-one-page-wide keeps the whole row,
    # figure and its note in the same view, the way the screen shows them.
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True

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
        f"8.1 Yesterday's Cash/Book: {money(derived.get('f1'))}",
        f"8.2 Today's Sales after Expenses: {money(derived.get('f2'))}",
        f"8.3 Projected Cash/Book: {money(derived.get('f3'))}",
        f"8.4 Actual Reported Cash/Book: {money(derived.get('f4'))}",
        f"8.5 Difference: {money(derived.get('f5'))}",
        "",
        f"8.9 Actual Reported Net Worth: {money(derived.get('mgmt_actual_networth'))}",
        f"8.10 Yesterday's Reported Trial Balance: {money(derived.get('mgmt_yesterday_tb'))}",
        f"8.11 Daily Profit Including 2T Sales: {money(derived.get('mgmt_profit'))}",
        f"8.12 Projected Net Worth: {money(derived.get('mgmt_projected_networth'))}",
        f"8.14 Difference: {money(derived.get('mgmt_networth_diff'))}",
        f"8.15 Actual Profit after Daily Expenses: {money(derived.get('mgmt_actual_profit'))}",
        "",
        f"Prepared by: {s8.get('prepared_by') or '-'}",
        f"Verified by: {s8.get('verified_by') or '-'}",
    ]
    return "\n".join(lines)
