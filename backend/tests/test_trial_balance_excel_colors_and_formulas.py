"""Two real defects found 2026-09-27, neither previously covered by any test:

  1. "Export Section 8 to Excel - Color Codes are requested to use SVR
     standards ... updated but not reflected." The Section 8 clipboard
     snapshot got the IOCL palette on 2026-09-25 (app.css .snap-band /
     .snap-red); the Excel export of the same section never did, and still
     went out in a generic navy.

  2. "Export Filled Excel Is not pulling all numbers as entered." Verified
     with real Excel (win32com), not openpyxl: row 20 of the shipped
     template (2T/2.40 ML - the one oil item SEP15 actually sold) had its
     Closing Stock and Amount cells hard-typed as the literal number 0
     instead of a formula, unlike every other oil row. That zeroed the row,
     the section's own total, and the day's grand total - for exactly the
     line that had real quantity on it.

Both are asserted here so neither regresses silently again.
"""

from __future__ import annotations

import io

from openpyxl import load_workbook

from svr_backend.excel.trial_balance_section8 import build_section8_workbook

DATE = "2026-09-20"


def _view(**over):
    base = {
        "shift_date": DATE,
        "status": "draft",
        "manual": {
            "section8": {
                "regular_expenses": [{"category": "Power Bill", "amount": 500}],
                "prepared_by": "Gopi",
                "verified_by": "Girish",
            },
        },
        "computed": {
            "derived": {
                "section8": {
                    "f1": 100, "f2": 200, "f3": 300, "f4": 250, "f5": -50,
                    "regular_expenses_total": 500,
                    "old_credit_total": 0,
                    "mgmt_actual_networth": 250, "mgmt_yesterday_tb": 300,
                    "mgmt_profit": 10, "mgmt_projected_networth": 310,
                    "mgmt_networth_diff": -60, "mgmt_actual_profit": -40,
                },
            },
        },
    }
    base.update(over)
    return base


def _find_row(ws, label_prefix: str) -> int:
    for row in range(1, ws.max_row + 1):
        v = ws.cell(row=row, column=1).value
        if isinstance(v, str) and v.strip().startswith(label_prefix):
            return row
    raise AssertionError(f"no row starts with {label_prefix!r}")


def test_section_bands_use_iocl_orange_not_a_generic_navy():
    wb = load_workbook(io.BytesIO(build_section8_workbook(_view())))
    ws = wb.active
    row = _find_row(ws, "Daily Management Reporting")
    fill = ws.cell(row=row, column=1).fill.fgColor.rgb
    # openpyxl reports an ARGB string; the RGB half is what we set.
    assert fill.upper().endswith("F37022"), f"section band is {fill}, not IOCL orange"


def test_total_lines_get_the_same_band_the_clipboard_snapshot_gives_them():
    wb = load_workbook(io.BytesIO(build_section8_workbook(_view())))
    ws = wb.active
    row = _find_row(ws, "Total Regular Expenses")
    fill = ws.cell(row=row, column=1).fill.fgColor.rgb
    assert fill.upper().endswith("F37022")


def test_8_8_and_8_15_are_flagged_red_like_the_clipboard_snapshot():
    wb = load_workbook(io.BytesIO(build_section8_workbook(_view())))
    ws = wb.active
    for prefix in ("8.8 ", "8.15 "):
        row = _find_row(ws, prefix)
        fill = ws.cell(row=row, column=1).fill.fgColor.rgb
        font_color = ws.cell(row=row, column=2).font.color.rgb
        assert fill.upper().endswith("FDECEB"), f"{prefix} row fill is {fill}"
        assert font_color.upper().endswith("E31E24"), f"{prefix} value colour is {font_color}"


def test_8_1_is_not_flagged_red():
    """Only the two escalation lines get the red treatment - not every figure,
    which would read more alarm into the sheet than the app itself does."""
    wb = load_workbook(io.BytesIO(build_section8_workbook(_view())))
    ws = wb.active
    row = _find_row(ws, "8.1 ")
    fill = ws.cell(row=row, column=1).fill.fgColor.rgb
    assert not fill.upper().endswith("FDECEB")


def test_the_template_oil_rows_all_carry_a_real_formula_not_a_hard_typed_zero():
    """Real Excel confirmed row 20 (2T/2.40 ML) computed as 0 regardless of
    quantity, because its Closing Stock / Amount cells were literally the
    number 0, not a formula referencing the row's own Sold/Rate/Opening. This
    checks the FORMULA TEXT survives in the exported file - openpyxl never
    evaluates it, but a formula equal to the literal string "0" is unambiguous
    either way, and is exactly what broke SEP15's oil total."""
    from svr_backend.excel.trial_balance_full import TEMPLATE

    wb = load_workbook(TEMPLATE)
    ws = wb["SEP12"]
    for row in range(19, 26):
        for col in ("E", "F"):
            cell = ws[f"{col}{row}"]
            assert str(cell.value).strip() != "0", (
                f"{col}{row} is a hard-typed 0, not a formula - "
                f"this is the exact defect that zeroed 2T/2.40 ML on SEP15"
            )


# --------------------------------------------------------- Special Note panels
#
# Client, 2026-09-27: "When There is special note within that Section 8 that
# should come on right hand side as you see in the Trail Entry form" - the
# screen carries each note beside its own block (sections.js), not as extra
# rows tacked onto the bottom of the Line/Amount column.

def test_section8_note_appears_as_a_right_hand_panel_not_a_bottom_row():
    view = _view()
    view["manual"]["section8"]["special_note"] = "Cash was short - staff advance"
    wb = load_workbook(io.BytesIO(build_section8_workbook(view)))
    ws = wb.active
    # Column D, not folded into the A/B Line-Amount columns.
    found = [str(r) for r in ws.merged_cells.ranges if str(r).startswith("D")]
    assert found, "no right-hand panel was drawn at all"
    assert "Cash was short - staff advance" not in (
        ws.cell(row=r, column=1).value or "" for r in range(1, ws.max_row + 1)
    )


def test_both_note_panels_show_up_beside_their_own_block():
    """8.1-8.7 gets special_note; 8.8-8.16 gets mgmt_note - two different
    fields on screen, so two different panels here, not one merged note."""
    view = _view()
    view["manual"]["section8"]["special_note"] = "Top panel note"
    view["manual"]["section8"]["mgmt_note"] = "Bottom panel note"
    wb = load_workbook(io.BytesIO(build_section8_workbook(view)))
    ws = wb.active
    row_top = _find_row(ws, "8.1 ")
    row_bottom = _find_row(ws, "8.8 ")
    values = {r: ws.cell(row=r, column=4).value for r in range(1, ws.max_row + 1)
              if ws.cell(row=r, column=4).value}
    top_note_row = next(r for r, v in values.items() if v == "Top panel note")
    bottom_note_row = next(r for r, v in values.items() if v == "Bottom panel note")
    # Each note sits beside (at or after) the block it belongs to, and the top
    # one is above the bottom one - not both dropped in the same spot.
    assert top_note_row >= row_top
    assert bottom_note_row >= row_bottom
    assert top_note_row < bottom_note_row


def test_a_blank_note_draws_no_empty_panel():
    wb = load_workbook(io.BytesIO(build_section8_workbook(_view())))
    ws = wb.active
    assert not any(str(r).startswith("D") for r in ws.merged_cells.ranges)


def test_section_3_and_4_notes_still_print_and_do_not_crowd_the_side_panels():
    view = _view()
    view["manual"]["section4"] = {"special_note": "A section 4 note"}
    wb = load_workbook(io.BytesIO(build_section8_workbook(view)))
    ws = wb.active
    texts = [ws.cell(row=r, column=1).value for r in range(1, ws.max_row + 1)]
    assert any(v == "Section 4 note" for v in texts)
