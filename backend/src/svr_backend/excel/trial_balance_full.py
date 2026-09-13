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
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from openpyxl import load_workbook

TEMPLATE = Path(__file__).with_name("templates") / "trial_balance_template.xlsx"
SHEET = "SEP12"

# Oil rows, in the template's own order. It carries SEVEN - row 20 ("2T/1.40 ML
# Total #") is all zeros on SEP12, which is why it reads as six at a glance. The
# order matches OIL_KEYS exactly, so the two line up one for one.
_OIL_ROWS = (19, 20, 21, 22, 23, 24, 25)


def _num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


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


def build_full_workbook(view: dict) -> bytes:
    """``view`` is the GET /daily-trial-balance/{date} payload."""
    wb = load_workbook(TEMPLATE)  # keep formulas and styling
    ws = wb[SHEET]
    w = _Writer(ws)

    manual = view.get("manual") or {}
    computed = view.get("computed") or {}
    derived = computed.get("derived") or {}
    inputs = view.get("inputs") or {}
    pulled = view.get("pulled") or {}
    day = view.get("shift_date")

    def sec(key: str) -> dict:
        v = manual.get(key)
        return v if isinstance(v, dict) else {}

    def der(key: str) -> dict:
        v = derived.get(key)
        return v if isinstance(v, dict) else {}

    s3, s4, s7, s8, s10, s11 = (sec(k) for k in (
        "section3", "section4", "section7", "section8", "section10", "section11"))

    # ---- header line (A2 on the sheet: the day and who prepared it) ------------
    prepared = s8.get("prepared_by") or ""
    ws["A2"] = f"Trial Balance {day}" + (f" : {prepared}" if prepared else "")

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

    # ---- 2.1 Oil Sales: B Sold, C Rate, D Opening Stock ----------------------
    for row, oil in zip(_OIL_ROWS, (view.get("day_sales") or {}).get("oils") or [], strict=False):
        w.num(f"B{row}", oil.get("qty"))
        w.num(f"C{row}", oil.get("rate"))
        w.num(f"D{row}", oil.get("opening"))

    # ---- 3. Daily Cash & Bank Balances ---------------------------------------
    for ref, key in (("B29", "onhand"), ("B30", "night"), ("B31", "morning"),
                     ("B32", "daytotal"), ("B33", "oldcredit")):
        w.num(ref, s3.get(key))
    for ref, key in (("D36", "iocl"), ("D37", "indianbank"), ("D38", "yesbank"),
                     ("D39", "ppunsettled"), ("D40", "ppsettled")):
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
    # IST" from the day it was captured. Re-stamp it with THIS record's date and
    # the time the export ran, in IST - otherwise every export claims to be Sep 12.
    stamp = datetime.now(ZoneInfo("Asia/Kolkata"))
    ws["A81"] = (
        f"8. Daily Management Reporting - "
        f"{stamp.strftime('%b %d').upper()}, {stamp.strftime('%I:%M %p').lstrip('0')} IST"
    )
    for i, row in enumerate(s8.get("regular_expenses") or []):
        if i > 2 or not isinstance(row, dict):
            break
        w.text(f"A{88 + i}", row.get("category"))
        w.num(f"D{88 + i}", row.get("amount"))
    w.num("F88", s4.get("yesbank_return"))
    for i, row in enumerate(s8.get("old_credit_collections") or []):
        if i > 1 or not isinstance(row, dict):
            break
        w.text(f"A{93 + i}", row.get("type"))
        w.num(f"C{93 + i}", row.get("amount"))
    w.num("D97", s8.get("mgmt_yesterday_tb"))
    w.num("F98", s4.get("yesbank_return"))
    w.text("D103", s8.get("prepared_by"))
    w.text("D104", s8.get("verified_by"))
    w.text("D105", s8.get("sent_by"))

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
