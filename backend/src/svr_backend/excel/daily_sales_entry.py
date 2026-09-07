"""Daily Sales Entry <-> .xlsx.

Layout (one sheet, "Daily Sales Entry"):

    A: section / label   B: field   C: Value (input)   D: Computed   F: field key

Import reads **only column C keyed by column F** - cosmetic columns A/B/D may be
edited freely. Fill the Value column; do not delete the key column or reorder.
Per SDD ADR-5 the parsed payload is always recomputed; sheet totals are only
compared, never trusted.
"""

from __future__ import annotations

import io
import math
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from svr_backend.calc.amounts import is_blank
from svr_backend.calc.daily_sales_entry import OIL_KEYS, OIL_LABELS, compute_payload

SHEET = "Daily Sales Entry"
_MAX_OILS = 8  # 5 fixed + up to 3 operator-added
_MAX_ROWS = 10  # expenses / cards / new-credits / old-credits template rows
_EPS = 0.01

_Row = tuple[str, str, Any, Any, str | None]


def _r(label: str, field: str, value: Any = None, computed: Any = None,
       key: str | None = None) -> _Row:
    return (label, field, value, computed, key)


def _section(name: str) -> _Row:
    return (name, "", None, None, None)


# --------------------------------------------------------------------------- build


def _gas_rows(payload: dict, result: dict) -> list[_Row]:
    rows: list[_Row] = [_section("1. Gas Sale(s)")]
    for fuel, name in (("hs", "Diesel (HS)"), ("ms", "Petrol (MS)")):
        g = payload.get(fuel) or {}
        rg = result.get(fuel) or {}
        rows += [
            _r(name, "Current Reading", g.get("current"), key=f"{fuel}.current"),
            _r(name, "Last Shift Reading", g.get("last"), key=f"{fuel}.last"),
            _r(name, "Rate Per Pump", g.get("rate"), key=f"{fuel}.rate"),
            _r(name, "Consumption", computed=rg.get("cons"), key=f"_chk.{fuel}.cons"),
            _r(name, "Amount", computed=rg.get("amount"), key=f"_chk.{fuel}.amount"),
        ]
    rows.append(_r("", "Gas Total Amt", computed=result.get("gas_total"), key="_chk.gas_total"))
    return rows


def _oil_rows(payload: dict, result: dict) -> list[_Row]:
    oils = payload.get("oils") or []
    r_oils = result.get("oils") or []
    rows: list[_Row] = [_section("2. Oil Sale(s)")]
    for i in range(_MAX_OILS):
        o = oils[i] if i < len(oils) else {}
        ro = r_oils[i] if i < len(r_oils) else {}
        key = OIL_KEYS[i] if i < len(OIL_KEYS) else ""
        label = o.get("label") or OIL_LABELS.get(key, f"Oil {i + 1}")
        rows += [
            _r(label, "Quantity", o.get("qty"), key=f"oils.{i}.qty"),
            _r(label, "Rate", o.get("rate"), key=f"oils.{i}.rate"),
            _r(label, "Before Stock", o.get("opening"), key=f"oils.{i}.opening"),
            _r(label, "After Sale Stock", computed=ro.get("closing"), key=f"_chk.oils.{i}.closing"),
            _r(label, "Amount", computed=ro.get("amount"), key=f"_chk.oils.{i}.amount"),
        ]
    rows.append(_r("", "Total Amt Oil(s)", computed=result.get("oil_total"), key="_chk.oil_total"))
    return rows


def _list_section(title: str, label: str, values: list, base_key: str, total_key: str,
                  total_label: str, total_val: Any) -> list[_Row]:
    rows: list[_Row] = [_section(title)]
    for i in range(max(_MAX_ROWS, len(values))):
        v = values[i] if i < len(values) else None
        rows.append(_r(label, f"Row {i + 1}", v, key=f"{base_key}.{i}"))
    rows.append(_r("", total_label, computed=total_val, key=f"_chk.{total_key}"))
    return rows


def _new_credit_rows(payload: dict, result: dict) -> list[_Row]:
    nc = payload.get("new_credits") or []
    r_nc = result.get("new_credit_amounts") or []
    rows: list[_Row] = [_section("5. Today New Credit(s)")]
    for i in range(max(_MAX_ROWS, len(nc))):
        row = nc[i] if i < len(nc) else {}
        amt = r_nc[i] if i < len(r_nc) else None
        n = f"Row {i + 1}"
        rows += [
            _r("New credit", f"{n} - In Ltrs", row.get("ltrs"), key=f"new_credits.{i}.ltrs"),
            _r("New credit", f"{n} - Rate", row.get("rate"), key=f"new_credits.{i}.rate"),
            _r("New credit", f"{n} - Amount", computed=amt, key=f"_chk.new_credit_amounts.{i}"),
        ]
    rows.append(
        _r("", "Total Amt New Credits", computed=result.get("new_credits_total"),
           key="_chk.new_credits_total")
    )
    return rows


def _summary_rows(payload: dict, result: dict) -> list[_Row]:
    s = "Summary"
    return [
        _section("7. Summary - Cash Hand Off"),
        _r(s, "Cash (Gas+Oils) Total Amt", computed=result.get("sum_cash"), key="_chk.sum_cash"),
        _r(s, "Expenses Total Amt", computed=result.get("sum_expenses"), key="_chk.sum_expenses"),
        _r(s, "Phone Pay Settled Total Amt", payload.get("phone_pay_settled"),
           key="phone_pay_settled"),
        _r(s, "Phone Pay Not Settled Total Amt", payload.get("phone_pay_unsettled"),
           key="phone_pay_unsettled"),
        _r(s, "New Credits Total Amt", computed=result.get("sum_new_credits"),
           key="_chk.sum_new_credits"),
        _r(s, "Credit Cards Swiping Total Amt", computed=result.get("sum_credit_cards"),
           key="_chk.sum_credit_cards"),
        _r(s, "Night Cash Hand Off Total Amt", payload.get("night_cash"), key="night_cash"),
        _r(s, "Net Bal Hand Off", computed=result.get("net_bal_hand_off"),
           key="_chk.net_bal_hand_off"),
    ]


def _all_rows(payload: dict, result: dict, meta: dict) -> list[_Row]:
    rows: list[_Row] = [
        _r("Header", "Date", meta.get("shift_date"), key="meta.shift_date"),
        _r("Header", "Pump", meta.get("pump_serial"), key="meta.pump_serial"),
        _r("Header", "Submitted By", meta.get("submitted_by"), key="_info.submitted_by"),
        _r("Header", "Entry Mode", meta.get("entry_mode"), key="_info.entry_mode"),
    ]
    rows += _gas_rows(payload, result)
    rows += _oil_rows(payload, result)
    rows += _list_section(
        "3. Expenses", "Expense", payload.get("expenses") or [], "expenses",
        "expenses_total", "Total Amt Expenses", result.get("expenses_total"),
    )
    rows += _list_section(
        "4. Credit Cards Swiping(s)", "Card swipe", payload.get("credit_card_amounts") or [],
        "credit_card_amounts", "credit_cards_total", "Total Amt Credit Cards",
        result.get("credit_cards_total"),
    )
    rows += _new_credit_rows(payload, result)
    rows += _list_section(
        "6. Old/Pending Credit Received", "Old credit", payload.get("old_credit_amounts") or [],
        "old_credit_amounts", "old_credit_total", "Old Credit Total (reference only)",
        result.get("old_credit_total"),
    )
    rows += _summary_rows(payload, result)
    return rows


_SECTION_FILL = PatternFill("solid", fgColor="1F3B5C")
_HEADER_FILL = PatternFill("solid", fgColor="EEF1F5")


def build_workbook(record: dict) -> bytes:
    """`record` = {shift_date, pump_serial, submitted_by, entry_mode, payload, result}."""
    payload = record.get("payload") or {}
    result = record.get("result") or compute_payload(payload)
    meta = {k: record.get(k) for k in ("shift_date", "pump_serial", "submitted_by", "entry_mode")}

    wb = Workbook()
    ws = wb.active
    ws.title = SHEET
    ws["A1"] = "SVR Indian Oil Service Station - Daily Sales Report (data export)"
    ws["A1"].font = Font(bold=True, size=13)
    ws["A2"] = (
        "Fill the Value column. Do not delete column F (field key) or reorder rows. "
        "Totals recompute on import."
    )
    ws["A2"].font = Font(italic=True, size=9, color="666666")

    hdr = 4
    titles = ("Section / Label", "Field", "Value", "Computed", "", "field key (do not edit)")
    for col, name in enumerate(titles, 1):
        c = ws.cell(row=hdr, column=col, value=name)
        c.font = Font(bold=True)
        c.fill = _HEADER_FILL

    r = hdr + 1
    for label, field_name, value, computed, key in _all_rows(payload, result, meta):
        ws.cell(row=r, column=1, value=label)
        ws.cell(row=r, column=2, value=field_name)
        if value is not None:
            ws.cell(row=r, column=3, value=value)
        if computed is not None:
            ws.cell(row=r, column=4, value=computed)
        if key:
            ws.cell(row=r, column=6, value=key)
        if field_name == "" and key is None:  # section header row
            for col in range(1, 7):
                cc = ws.cell(row=r, column=col)
                cc.font = Font(bold=True, color="FFFFFF")
                cc.fill = _SECTION_FILL
        r += 1

    for col, w in {"A": 34, "B": 30, "C": 16, "D": 14, "E": 2, "F": 26}.items():
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=hdr + 1, min_col=3, max_col=4):
        for cell in row:
            cell.alignment = Alignment(horizontal="right")

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def blank_template(pump_serial: str | None = None) -> bytes:
    empty = {
        "hs": {}, "ms": {},
        "oils": [{"label": OIL_LABELS[k]} for k in OIL_KEYS],
        "expenses": [], "credit_card_amounts": [], "new_credits": [], "old_credit_amounts": [],
    }
    return build_workbook({
        "shift_date": None, "pump_serial": pump_serial, "submitted_by": None,
        "entry_mode": "excel", "payload": empty, "result": compute_payload(empty),
    })


# --------------------------------------------------------------------------- parse


def _num_or_str(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, str):
        return v.strip() or None
    return v


def _blank_payload() -> dict:
    return {
        "hs": {}, "ms": {},
        "oils": [{} for _ in range(_MAX_OILS)],
        "expenses": [None] * _MAX_ROWS,
        "credit_card_amounts": [None] * _MAX_ROWS,
        "new_credits": [{} for _ in range(_MAX_ROWS)],
        "old_credit_amounts": [None] * _MAX_ROWS,
    }


def _assign(payload: dict, key: str, value: Any) -> None:
    parts = key.split(".")
    head = parts[0]
    if head in ("hs", "ms") and len(parts) == 2:
        payload[head][parts[1]] = value
    elif head == "oils" and len(parts) == 3:
        payload["oils"][int(parts[1])][parts[2]] = value
    elif head == "new_credits" and len(parts) == 3:
        payload["new_credits"][int(parts[1])][parts[2]] = value
    elif head in ("expenses", "credit_card_amounts", "old_credit_amounts") and len(parts) == 2:
        payload[head][int(parts[1])] = value
    elif head in ("phone_pay_settled", "phone_pay_unsettled", "night_cash"):
        payload[head] = value


def parse_workbook(data: bytes) -> tuple[dict, dict, list[str]]:
    """bytes -> (payload, meta, warnings). Recompute downstream; never trust sheet totals."""
    warnings: list[str] = []
    wb = load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    ws = wb[SHEET] if SHEET in wb.sheetnames else wb.active

    kv: dict[str, Any] = {}
    checks: dict[str, Any] = {}
    for row in ws.iter_rows(min_col=1, max_col=6, values_only=True):
        key = row[5] if len(row) > 5 else None
        if not isinstance(key, str) or not key:
            continue
        if key.startswith("_chk."):
            checks[key[5:]] = _num_or_str(row[3])
        elif key.startswith("_info."):
            continue
        else:
            kv[key] = _num_or_str(row[2])

    if not kv and not checks:
        warnings.append("No SVR field keys found in column F - is this an SVR export or template?")

    payload = _blank_payload()
    for key, value in kv.items():
        if not key.startswith("meta."):
            _assign(payload, key, value)

    payload["oils"] = _trim_oils(payload["oils"])
    for k in ("expenses", "credit_card_amounts", "old_credit_amounts"):
        payload[k] = _rtrim(list(payload[k]))
    payload["new_credits"] = _rtrim_dicts(payload["new_credits"], ("ltrs", "rate"))

    meta = {
        "shift_date": _fmt_date(kv.get("meta.shift_date")),
        "pump_serial": str(kv["meta.pump_serial"]).strip() if kv.get("meta.pump_serial") else None,
    }

    _flag_mismatches(compute_payload(payload), checks, warnings)
    return payload, meta, warnings


def _trim_oils(oils: list[dict]) -> list[dict]:
    kept = list(oils[: len(OIL_KEYS)])  # always keep the 5 fixed rows
    for extra in oils[len(OIL_KEYS):]:
        if any(not is_blank(extra.get(f)) for f in ("qty", "rate", "opening")):
            kept.append(extra)
    return kept


def _rtrim(xs: list) -> list:
    while xs and is_blank(xs[-1]):
        xs.pop()
    return xs


def _rtrim_dicts(rows: list[dict], fields: tuple[str, ...]) -> list[dict]:
    while rows and all(is_blank(rows[-1].get(f)) for f in fields):
        rows.pop()
    return rows


def _fmt_date(v: Any) -> str | None:
    if v is None or v == "":
        return None
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d")
    return str(v).strip() or None


def _look(tree: Any, dotted: str) -> Any:
    cur = tree
    for p in dotted.split("."):
        if isinstance(cur, list):
            cur = cur[int(p)] if p.isdigit() and int(p) < len(cur) else None
        elif isinstance(cur, dict):
            cur = cur.get(p)
        else:
            return None
    return cur


def _flag_mismatches(recomputed: dict, checks: dict, warnings: list[str]) -> None:
    for key, sheet_val in checks.items():
        if is_blank(sheet_val):
            continue
        want = _look(recomputed, key)
        try:
            if want is not None and not math.isclose(float(sheet_val), float(want), abs_tol=_EPS):
                warnings.append(
                    f"{key}: sheet shows {sheet_val}, recomputes to {want} - using recomputed."
                )
        except (TypeError, ValueError):
            continue
