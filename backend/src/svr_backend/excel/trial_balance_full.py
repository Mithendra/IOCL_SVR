"""The whole Daily Trial Balance as .xlsx — the client's own sheet, filled in.

Not a rebuilt approximation. The SEP12 tab of
``docs/01-BRD-Requirement-Gathering/ocr-samples/Trail_balance_12-SEP-2026.xlsx``
is shipped here as ``templates/trial_balance_template.xlsx`` (that one tab, 76 KB
out of the 18 MB original), and an export writes the day's figures into its input
cells and leaves everything else alone.

That means the file that comes out carries the station's own section bands, colour
codes, column widths, notes and — importantly — its own formulas, which Excel
recalculates on open. A hand-rebuilt copy would have been my approximation of
their sheet; this IS their sheet (client, 2026-09-12: "exactly the same thing").

Only cells the operator would type are written. Every total, and every
cross-reference between sections, is left as the template's formula, so the
exported workbook stays self-consistent even if someone edits it afterwards.

Two cross-sheet references (``='SEP11'!D51`` and ``='SEP11'!D79``) point at a tab
that does not exist in a one-tab export, so those two are replaced by the values
the record actually carries - otherwise Excel opens showing #REF!.
"""

from __future__ import annotations

import io
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from openpyxl import load_workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation

TEMPLATE = Path(__file__).with_name("templates") / "trial_balance_template.xlsx"
SHEET = "SEP12"

# Oil rows the station's own sheet has. It carries SEVEN - row 20 is all zeros on
# SEP12, which is why it reads as six at a glance.
#
# That row used to be labelled "2T/1.40 ML Total #". Client-confirmed 2026-09-13:
# there is no 1.40 pack and never was - the station sells 2T/1.50 and 2T/2.40, and
# 1.40 was a typo in their SEP12 tab. The template now carries 2T/2.40 ML Total#
# there, matching the app's own second oil item. (The client is correcting their
# master workbook by hand; the copy of it under docs/ is their record, not ours to
# edit.) Every export overwrites A19..A25 from the live item list anyway, so a
# stale label there could only ever show through on a row no item fills.
#
# The item list is editable now (migration 0023), so the two can disagree. These
# seven rows are FIXED in the template: F26 sums F19..F25 by name, and every row
# below 26 is referenced by absolute position from seven other places. Inserting a
# row would silently repoint all of that, so the export does not insert - it fills
# these seven in order and reports the rest rather than dropping them quietly.
_OIL_ROWS = (19, 20, 21, 22, 23, 24, 25)


def _num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# Every cell an operator types into. The template is the client's real SEP12 tab,
# so each one of these still holds SEP12's own figure until it is overwritten -
# and `num`/`text` below deliberately DON'T write when a day has nothing to put.
# The two together meant an export of a quiet day came out carrying SEP12's
# numbers: its Load/Unload readings, its Airtel balances, its 30-day ledger, an
# "Anil New Credit 1500" nobody entered (client, 2026-09-25: "incomplete and it
# has lot empty rows").
#
# So every input cell is blanked first and only then filled. A field the day has
# no value for now comes out EMPTY, which is true, instead of showing a figure
# from a fortnight ago, which is not. Formulas, labels, section bands, colours
# and column widths are never touched - only the input cells listed here.
_INPUT_CELLS: tuple[str, ...] = (
    "A2",
    # 1. IOCL Stock Readings
    "B3", "C3", "B4", "C4",
    # 2. Day Sales Report - per-pump reading and rate (D and F are formulas)
    "B7", "C7", "E7", "B8", "C8", "E8",
    "B11", "C11", "E11", "B12", "C12", "E12", "E15", "E16",
    # 3. Cash & bank
    "B29", "B30", "B31", "B32", "B33",
    "D36", "D37", "D38", "D39",
    # D40 is "Phone Pay Settled Amt", removed from the form on 2026-09-25 - it
    # double-counted money already in the Indian Bank statement. Still CLEARED so
    # the template's own figure cannot show through on an export.
    "D40",
    # 4. Reconciliation
    "D49", "D50", "F55",
    # 5. Stock Value - the buy rates
    "C67", "C68",
    # 7. Projected
    "D76",
    # 8. Management reporting
    "F88", "D97", "F98",
    "D103", "D104", "D105",
    # 10. Load/Unload
    "B133", "C133", "D133", "E133", "B134", "C134", "D134", "E134",
    # 11. Old/New Credit Sales
    "B138", "B139",
)
# Repeating blocks: (first row, last row, columns). The label column goes too -
# the template ships SEP12's creditor names, and leaving them behind put a name
# on a row whose amount had been cleared.
_INPUT_BLOCKS: tuple[tuple[int, int, tuple[str, ...]], ...] = (
    (19, 25, ("A", "B", "C", "D")),          # 2.1 Oil Sales
    (43, 46, ("A", "D")),                    # 3.14 New Credit / Salary Advance
    (55, 58, ("A", "D")),                    # 4.6 Expenses
    (60, 62, ("A", "C", "D")),               # 4.7 Credit Remittance
    (88, 90, ("A", "D")),                    # 8.6 Regular Expenses
    (93, 94, ("A", "C")),                    # 8.7 Old Credit Remittances
    # 9. Daily Mgr Calculation. D-G are the template's own formulas (=B-10,
    # =D*117.7) and are left alone; they recompute from B and C.
    (109, 127, ("A", "B", "C", "H", "I", "J", "K", "L", "M", "N", "O")),
)
# The ledger rows the template has. Section 9 keeps 7 days on the form, so this
# is never the binding limit - it is here so an overflow is reported, not dropped.
_LEDGER_ROWS = tuple(range(109, 128))
_LEDGER_COLS = (
    ("A", "date"), ("B", "total_ms_sale"), ("C", "total_hs_sale"),
    ("H", "total_sales_rs"), ("I", "daily_expenses"), ("J", "two_t_sale"),
    ("K", "total_sale"), ("L", "settled_phone_pay"), ("M", "unsettled_phone_pay"),
    ("N", "fleet_card_swipe"), ("O", "credit_card_swipe"),
)


# Which dropdown backs which block of the sheet. The template shipped its own
# Data Validation lists, frozen at SEP12 - "Salary Advance Viaj" (a typo), a
# salary advance still on the creditors list that migration 0037 has since taken
# off, and an expenses list that no longer matched the app's. THAT was the real
# defect behind "no dropdown values": the dropdowns worked, they offered the
# wrong values. They are rebuilt from `trial_balance_option` on every export
# (client, 2026-09-25), so the workbook and the screen cannot drift apart.
_VALIDATION_RANGES: tuple[tuple[str, str], ...] = (
    ("A43:A46", "creditors"),        # 3.14 New Credit / Salary Advance
    ("A55:A58", "expenses"),         # 4.6 Expenses
    ("A60:A62", "remittance"),       # 4.7 Credit Remittance
    ("A88:A90", "expenses"),         # 8.6 Regular Expenses
    ("A93:A94", "remittance"),       # 8.7 Old Credit Remittances
    ("D103:D105", "staff"),          # 8.16 Sign-off
)
LISTS_SHEET = "Lists"


def _apply_validations(wb, ws, lists: dict[str, list[str]] | None) -> None:
    """Put the dropdowns on the sheet, backed by a named range on a Lists tab.

    A correction, recorded because the wrong version of it was in this file for a
    while: the earlier inline `"a,b,c"` formulas WERE working. Driving real Excel
    over the client's own exported copy shows every one of them live -
    Validation.Type 3, InCellDropdown True, the right values behind it. The guess
    that Excel was repairing the workbook and discarding them (its dimension is
    A1:WZQ218, 16,241 columns) was wrong, and is not why the client reported "NO
    DROP DOWN VALUES"; most likely the validated cells simply were not the ones
    being clicked, since they are blank rows on a blank form.

    Named ranges are kept anyway, on their own merits and not as a bug fix:
      - the values land on a VISIBLE Lists tab, so the station can read and
        correct them instead of them being buried in a cell's properties, which
        is what the client asked for;
      - no 255-character ceiling, so a list can grow;
      - ShowError is on, so a typo is refused rather than silently accepted.

    Validated cells: A43:A46 (3.14), A55:A58 (4.6), A60:A62 (4.7), A88:A90 (8.6),
    A93:A94 (8.7), D103:D105 (8.16).
    """
    if not lists:
        return
    used = [(ref, key) for ref, key in _VALIDATION_RANGES if lists.get(key)]
    if not used:
        return

    if LISTS_SHEET in wb.sheetnames:
        del wb[LISTS_SHEET]
    sheet = wb.create_sheet(LISTS_SHEET)
    sheet.sheet_state = "visible"
    sheet["A1"] = "Dropdown values used by this form. Edit here and the lists above follow."
    sheet["A1"].font = Font(bold=True)

    ws.data_validations.dataValidation = []      # the template's stale ones
    column = 1
    placed: dict[str, str] = {}
    for _ref, key in used:
        if key in placed:
            continue
        values = [str(v) for v in lists[key] if str(v).strip()]
        letter = get_column_letter(column)
        sheet.cell(row=2, column=column, value=key).font = Font(bold=True)
        for i, value in enumerate(values):
            sheet.cell(row=3 + i, column=column, value=value)
        sheet.column_dimensions[letter].width = max(18, min(48, max(len(v) for v in values) + 2))
        ref = f"'{LISTS_SHEET}'!${letter}$3:${letter}${2 + len(values)}"
        # A workbook-level NAME as well as the range. This is what Excel itself
        # writes when you pick a range in the Data Validation dialog, and it is
        # the form every Excel version accepts - a bare cross-sheet reference is
        # fine in current Excel and has been refused by older ones. After two
        # rounds of "NO DROP DOWN VALUES" this takes the belt-and-braces route.
        name = f"SVR_{key}"
        if name in wb.defined_names:
            del wb.defined_names[name]
        wb.defined_names[name] = DefinedName(name, attr_text=ref)
        placed[key] = f"={name}"
        column += 1

    for ref, key in used:
        dv = DataValidation(
            type="list", formula1=placed[key], allow_blank=True,
            showDropDown=False,      # OOXML inverts this: False = SHOW the arrow
            showErrorMessage=True,
            error="Pick one of the listed values.",
            errorTitle="Not on the list",
        )
        ws.add_data_validation(dv)
        dv.add(ref)


def _export_stamp() -> str:
    """When this copy was produced, in IST."""
    return (
        datetime.now(ZoneInfo("Asia/Kolkata"))
        .strftime("%d-%b-%Y %I:%M %p")
        .replace(" 0", " ")
    )


def _clear_inputs(ws) -> None:
    for ref in _INPUT_CELLS:
        ws[ref] = None
    for first, last, cols in _INPUT_BLOCKS:
        for row in range(first, last + 1):
            for col in cols:
                ws[f"{col}{row}"] = None


class _Writer:
    def __init__(self, ws) -> None:
        self.ws = ws

    def num(self, ref: str, value) -> None:
        """Write a figure, leaving the cell untouched when there is nothing to put."""
        n = _num(value)
        if n is not None:
            self.ws[ref] = n

    def text(self, ref: str, value) -> None:
        if value not in (None, ""):
            self.ws[ref] = str(value)


def build_full_workbook(view: dict, option_lists: dict[str, list[str]] | None = None) -> bytes:
    """``view`` is the GET /daily-trial-balance/{date} payload."""
    wb = load_workbook(TEMPLATE)  # keep formulas and styling
    ws = wb[SHEET]
    _clear_inputs(ws)             # ...but never the template day's figures
    _apply_validations(wb, ws, option_lists)
    w = _Writer(ws)

    manual = view.get("manual") or {}
    inputs = view.get("inputs") or {}
    pulled = view.get("pulled") or {}
    day = view.get("shift_date")
    # Nothing reads view["computed"] on purpose: every figure the engine derives is
    # a formula in the template, and the sheet recalculates it from the inputs we
    # write. Pasting our own totals over those formulas would silently fork the
    # two - a hand-edit in Excel afterwards would then disagree with its own sheet.

    def sec(key: str) -> dict:
        v = manual.get(key)
        return v if isinstance(v, dict) else {}

    s3, s4, s7, s8, s10, s11 = (sec(k) for k in (
        "section3", "section4", "section7", "section8", "section10", "section11"))

    # ---- header line (A2 on the sheet: the day and who prepared it) ------------
    prepared = s8.get("prepared_by") or ""
    # ...and when this copy was produced. Client, 2026-09-25: "Should be in
    # Colour with logo with System Date on it." Two dates live on this sheet and
    # neither replaces the other: the RECORD's day names the Trial Balance, and
    # the export stamp says which printout you are holding when three of them are
    # on the desk. Asia/Kolkata explicitly, never the host timezone.
    ws["A2"] = (
        f"Trial Balance {day}"
        + (f" : {prepared}" if prepared else "")
        + f"   |   exported {_export_stamp()} IST"
    )

    # ---- 1. IOCL Stock Readings ----------------------------------------------
    w.num("B3", inputs.get("s1_hs_yesterday"))
    w.num("C3", inputs.get("s1_hs_current"))
    w.num("B4", inputs.get("s1_ms_yesterday"))
    w.num("C4", inputs.get("s1_ms_current"))

    # ---- 2. Day Sales Report, per pump then the combined rates ----------------
    # B = Current Reading, C = Last Reading, E = Rate (D and F are formulas).
    for row, side, fuel in ((7, "road", "hs"), (8, "road", "ms"),
                            (11, "office", "hs"), (12, "office", "ms")):
        pump = (view.get("day_sales") or {}).get(side) or {}
        f = pump.get(fuel) or {}
        w.num(f"B{row}", f.get("current"))
        w.num(f"C{row}", f.get("last"))
        w.num(f"E{row}", f.get("rate"))
    w.num("E15", pulled.get("sell_rate_hs"))
    w.num("E16", pulled.get("sell_rate_ms"))

    # ---- 2.1 Oil Sales: A Item, B Sold, C Rate, D Opening Stock ---------------
    # The label is written too, so a renamed or newly added item is named on the
    # exported sheet instead of appearing under the row the template shipped with.
    day_oils = (view.get("day_sales") or {}).get("oils") or []
    for row, oil in zip(_OIL_ROWS, day_oils, strict=False):
        w.text(f"A{row}", oil.get("label"))
        w.num(f"B{row}", oil.get("qty"))
        w.num(f"C{row}", oil.get("rate"))
        w.num(f"D{row}", oil.get("opening"))

    # More items than the sheet has rows. Rather than drop them silently - which
    # would make the exported Oil Total disagree with the screen's - they go in a
    # note beside the block, where a person will see them. Inserting real rows
    # would repoint F26's SUM and every absolute reference below it.
    if len(day_oils) > len(_OIL_ROWS):
        extra = day_oils[len(_OIL_ROWS):]
        w.text(
            "H18",
            "NOT SHOWN ABOVE - this sheet has "
            f"{len(_OIL_ROWS)} oil rows and the station now sells {len(day_oils)}: "
            + "; ".join(
                f"{o.get('label') or '?'} = {o.get('qty') or 0} x {o.get('rate') or 0}"
                for o in extra
            )
            + ". Their amounts are excluded from 2.1's total on this sheet.",
        )

    # ---- 3. Daily Cash & Bank Balances ---------------------------------------
    for ref, key in (("B29", "onhand"), ("B30", "night"), ("B31", "morning"),
                     ("B32", "daytotal"), ("B33", "oldcredit")):
        w.num(ref, s3.get(key))
    for ref, key in (("D36", "iocl"), ("D37", "indianbank"), ("D38", "yesbank"),
                     ("D39", "ppunsettled")):
        w.num(ref, s3.get(key))
    for i, row in enumerate(s3.get("new_credits") or []):
        if i > 3 or not isinstance(row, dict):
            break  # the template prints four New Credit lines
        w.text(f"A{43 + i}", row.get("type"))
        w.num(f"D{43 + i}", row.get("amount"))

    # ---- 4. Cash/Book Value Reconciliation -----------------------------------
    # D49 is ='SEP11'!D51 in the workbook; a one-tab export would show #REF!.
    w.num("D49", s4.get("yesterday"))
    w.num("D50", s4.get("todaysale"))
    for i, row in enumerate(s4.get("expenses") or []):
        if i > 3 or not isinstance(row, dict):
            break
        w.text(f"A{55 + i}", row.get("category"))
        w.num(f"D{55 + i}", row.get("amount"))
    w.num("F55", s4.get("yesbank_return"))
    for i, row in enumerate(s4.get("remittance") or []):
        if i > 2 or not isinstance(row, dict):
            break
        w.text(f"A{60 + i}", row.get("type"))
        w.text(f"C{60 + i}", row.get("given_on"))
        w.num(f"D{60 + i}", row.get("amount"))

    # ---- 5. Stock Value: the Buy Rates (Ltrs and Amount are formulas) ---------
    w.num("C67", pulled.get("buy_rate_hs"))
    w.num("C68", pulled.get("buy_rate_ms"))

    # ---- 7. Trial Balance Projected ------------------------------------------
    w.num("D76", s7.get("yesterday"))  # ='SEP11'!D79 in the workbook

    # ---- 8. Daily Management Reporting ---------------------------------------
    # The template hard-codes "8. Daily Management Reporting - SEPT 12, 12:00 PM
    # IST" from the day it was captured, so every export would otherwise claim to
    # be Sep 12. Re-stamp it.
    #
    # The DATE is the record's own day, not today's: that heading names the report,
    # and a SEP 12 Trial Balance queried and exported on the 14th is still the
    # SEP 12 report. (Taking the date off the clock looked right only while a day
    # was always worked on the day it happened - exporting SEP 12 at 7 a.m. the
    # next morning labelled it SEP 13.) The TIME is the live IST clock: when this
    # copy was produced.
    when = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p").lstrip("0")
    try:
        on = date.fromisoformat(str(day)).strftime("%b %d").upper()
    except (TypeError, ValueError):  # no/!ISO shift_date - fall back to the clock
        on = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%b %d").upper()
    ws["A81"] = f"8. Daily Management Reporting - {on}, {when} IST"
    for i, row in enumerate(s8.get("regular_expenses") or []):
        if i > 2 or not isinstance(row, dict):
            break
        w.text(f"A{88 + i}", row.get("category"))
        w.num(f"D{88 + i}", row.get("amount"))
    w.num("F88", s4.get("yesbank_return"))
    # 8.7 is CARRIED from 4.7 (client, 2026-09-24), so its rows live in the
    # engine's output, not in the manual blob. Reading `s8` here printed an empty
    # block on a day whose remittances had only ever been keyed in Section 4 -
    # the 14-Sep export went out without Anil/Nani's 1,500 (client, 2026-09-25).
    #
    # This is the one place the exporter reads `computed`, and the docstring's
    # rule still holds: it does NOT paste computed TOTALS over the template's
    # formulas. These are rows the template has no way to work out for itself.
    carried = (
        ((view.get("computed") or {}).get("derived") or {}).get("section8") or {}
    ).get("old_credit_rows") or []
    for i, row in enumerate(carried):
        if i > 1 or not isinstance(row, dict):
            break
        w.text(f"A{93 + i}", row.get("type"))
        w.num(f"C{93 + i}", row.get("amount"))
    w.num("D97", s8.get("mgmt_yesterday_tb"))
    w.num("F98", s4.get("yesbank_return"))
    w.text("D103", s8.get("prepared_by"))
    w.text("D104", s8.get("verified_by"))
    w.text("D105", s8.get("sent_by"))

    # ---- 9. Daily Mgr Calculation --------------------------------------------
    # Never written until 2026-09-25, so every export carried the TEMPLATE's
    # ledger - thirty rows dated 24-Aug to 11-Sep - no matter which day was being
    # exported. D..G are the sheet's own formulas and recompute from B and C.
    s9 = sec("section9")
    ledger = [r for r in (s9.get("ledger") or []) if isinstance(r, dict)]
    for row_no, entry in zip(_LEDGER_ROWS, ledger, strict=False):
        for col, key in _LEDGER_COLS:
            value = entry.get(key)
            if col == "A":
                w.text(f"A{row_no}", value)
            else:
                w.num(f"{col}{row_no}", value)
    if len(ledger) > len(_LEDGER_ROWS):
        w.text(
            "Q107",
            f"NOT SHOWN: this sheet has {len(_LEDGER_ROWS)} ledger rows and the "
            f"record carries {len(ledger)}. The oldest are printed above.",
        )

    # ---- 10. Load/Unload ------------------------------------------------------
    for row, fuel in ((133, "hs"), (134, "ms")):
        w.num(f"B{row}", s10.get(f"{fuel}_afterunload"))
        w.num(f"C{row}", s10.get(f"{fuel}_old"))
        w.num(f"D{row}", s10.get(f"{fuel}_new"))
        w.num(f"E{row}", s10.get(f"{fuel}_load"))

    # ---- 11. Old/New Credit Sales --------------------------------------------
    w.num("B138", s11.get("new_airtel"))
    w.num("B139", s11.get("old_airtel"))

    # ---- Special Notes: appended in column H, beside the section they belong to,
    # which is where the sheet already keeps its commentary.
    for ref, note in (("H28", s3.get("special_note")), ("H48", s4.get("special_note")),
                      ("H74", s7.get("special_note")), ("H81", s8.get("special_note")),
                      ("H95", s8.get("mgmt_note"))):
        w.text(ref, note)

    # Excel recalculates every formula on open rather than trusting cached values,
    # which matters because we have just changed the inputs underneath them.
    wb.calculation.fullCalcOnLoad = True

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_blank_workbook(
    oil_labels: list[str] | None = None,
    option_lists: dict[str, list[str]] | None = None,
) -> bytes:
    """The station's sheet with every input cell empty - a form to fill in.

    Client, 2026-09-25: "Export to Trail balance to Excel Sheet is empty one is
    also needed looks like it is working as an empty sheet to fill-out which is
    also good name is as Print Empty Excel."

    This is exactly _clear_inputs() with nothing written after it, which is also
    why the template stops shipping SEP12's figures to anyone who opens it: the
    same list of cells governs both the filled export and this one, so the two
    cannot drift apart.
    """
    wb = load_workbook(TEMPLATE)
    ws = wb[SHEET]
    _clear_inputs(ws)
    _apply_validations(wb, ws, option_lists)
    # The oil rows are NAMED, even though nothing is filled in. _clear_inputs
    # blanks column A of 2.1 along with the figures - right for a filled export,
    # which rewrites those labels from the live item list, and wrong for a form
    # somebody is about to write on: seven unlabelled rows tell them nothing.
    for row, label in zip(_OIL_ROWS, oil_labels or [], strict=False):
        if label:
            ws[f"A{row}"] = label
    ws["A2"] = f"Trial Balance   |   blank form printed {_export_stamp()} IST"
    ws["A81"] = "8. Daily Management Reporting"
    wb.calculation.fullCalcOnLoad = True
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
