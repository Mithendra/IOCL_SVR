"""Daily Sales Entry module API (SDD 5.4 / 9).

Access (SDD 4.2): Sales may create/edit their own submission and print/scan;
Manager and Owner have full access including delete (the only roles permitted to
delete a submitted daily form, SDD 4.2 audit-integrity rule).

Every write: RBAC check -> parse + recompute via the calculation engine (the engine
is authoritative, never the client) -> persist -> audit.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field

from svr_backend.calc.daily_sales_entry import OIL_KEYS, OIL_LABELS, compute_payload
from svr_backend.carry_forward import carried_last_readings
from svr_backend.core.audit import record_write
from svr_backend.core.config import get_settings
from svr_backend.core.db import transaction
from svr_backend.core.rbac import get_db, get_principal, require
from svr_backend.core.session import Principal
from svr_backend.excel import blank_template, build_workbook, parse_workbook
from svr_backend.inventory import on_hand_map
from svr_backend.ocr import pipeline as ocr_pipeline
from svr_backend.ocr.runtime import tesseract_version
from svr_backend.rates import latest_effective_rates

router = APIRouter(prefix="/daily-sales-entry", tags=["daily-sales-entry"])

TABLE = "daily_sales_entry"


# --------------------------------------------------------------------------- models


class CalcRequest(BaseModel):
    """The section 1-7 form, loosely typed - mirrors the mockup's field graph."""

    hs: dict = Field(default_factory=dict)
    ms: dict = Field(default_factory=dict)
    oils: list[dict] = Field(default_factory=list)
    expenses: list = Field(default_factory=list)
    credit_card_amounts: list = Field(default_factory=list)
    new_credits: list[dict] = Field(default_factory=list)
    old_credit_amounts: list = Field(default_factory=list)
    phone_pay_settled: float | str | None = None
    phone_pay_unsettled: float | str | None = None
    night_cash: float | str | None = None


class EntryCreate(CalcRequest):
    shift_date: str | None = None  # defaults to today
    pump_serial: str


class EntryOut(BaseModel):
    id: int
    shift_date: str
    pump_serial: str
    submitted_by: str
    entry_mode: str
    sell_rate_hs: float | None
    sell_rate_ms: float | None
    hs_last: float | None
    ms_last: float | None
    gas_total: float | None
    oil_total: float | None
    net_bal_hand_off: float | None
    payload: dict
    result: dict
    last_updated_by: str | None
    last_updated_at: str


class PrefillOut(BaseModel):
    shift_date: str
    pump_serial: str
    hs_last: float | None
    ms_last: float | None
    carried_from: str | None
    sell_rate_hs: float | None
    sell_rate_ms: float | None
    oil_rates: dict[str, float | None]
    oil_openings: dict[str, float | None]
    oil_labels: dict[str, str]


# ---------------------------------------------------------------------------- helpers


def _row_to_out(row: sqlite3.Row) -> EntryOut:
    return EntryOut(
        id=row["id"],
        shift_date=row["shift_date"],
        pump_serial=row["pump_serial"],
        submitted_by=row["submitted_by"],
        entry_mode=row["entry_mode"],
        sell_rate_hs=row["sell_rate_hs"],
        sell_rate_ms=row["sell_rate_ms"],
        hs_last=row["hs_last"],
        ms_last=row["ms_last"],
        gas_total=row["gas_total"],
        oil_total=row["oil_total"],
        net_bal_hand_off=row["net_bal_hand_off"],
        payload=json.loads(row["payload"]),
        result=json.loads(row["result"]),
        last_updated_by=row["last_updated_by"],
        last_updated_at=row["last_updated_at"],
    )


def _apply_locked_context(
    conn: sqlite3.Connection, payload: dict, shift_date: str, pump_serial: str
) -> tuple[dict, dict]:
    """Overlay carried Last Shift Readings and locked Sell/oil rates onto the payload.

    Client-supplied values for these fields are ignored - they are backend-owned
    (the mockup renders them disabled). Returns ``(payload, meta)``.
    """
    rates = latest_effective_rates(conn, shift_date)
    hs_rate = rates["HS"]["sell_rate"] if "HS" in rates else None
    ms_rate = rates["MS"]["sell_rate"] if "MS" in rates else None
    oil_rates = {k: (rates[k]["sell_rate"] if k in rates else None) for k in OIL_KEYS}
    oil_openings = on_hand_map(conn)  # Opening Stock pulled from Inventory Tracking

    carried = carried_last_readings(conn, pump_serial, shift_date)

    payload = json.loads(json.dumps(payload))  # deep copy
    payload.setdefault("hs", {})
    payload.setdefault("ms", {})
    payload["hs"]["last"] = carried.hs
    payload["ms"]["last"] = carried.ms
    payload["hs"]["rate"] = hs_rate
    payload["ms"]["rate"] = ms_rate

    oils = payload.get("oils") or []
    normalized = []
    for i, key in enumerate(OIL_KEYS):
        src = oils[i] if i < len(oils) else {}
        normalized.append(
            {
                "label": OIL_LABELS[key],
                "qty": src.get("qty"),
                "rate": oil_rates[key],
                "opening": oil_openings.get(key),  # backend-owned, from Inventory Tracking
            }
        )
    # keep any operator-added extra rows as-is (manual rate/opening)
    normalized.extend(oils[len(OIL_KEYS) :])
    payload["oils"] = normalized

    meta = {
        "sell_rate_hs": hs_rate,
        "sell_rate_ms": ms_rate,
        "oil_rates": oil_rates,
        "oil_openings": oil_openings,
        "carried_from": carried.source_date,
    }
    return payload, meta


# ----------------------------------------------------------------------------- routes


@router.post("/calc")
def calc(body: CalcRequest, _: Principal = Depends(get_principal)) -> dict:
    """Stateless recompute. The renderer calls this on input so it never owns math."""
    return compute_payload(body.model_dump())


@router.get("/prefill", response_model=PrefillOut)
def prefill(
    pump_serial: str,
    shift_date: str | None = None,
    _: Principal = Depends(get_principal),
    conn: sqlite3.Connection = Depends(get_db),
) -> PrefillOut:
    sd = shift_date or date.today().isoformat()
    _, meta = _apply_locked_context(conn, {}, sd, pump_serial)
    return PrefillOut(
        shift_date=sd,
        pump_serial=pump_serial,
        hs_last=carried_last_readings(conn, pump_serial, sd).hs,
        ms_last=carried_last_readings(conn, pump_serial, sd).ms,
        carried_from=meta["carried_from"],
        sell_rate_hs=meta["sell_rate_hs"],
        sell_rate_ms=meta["sell_rate_ms"],
        oil_rates=meta["oil_rates"],
        oil_openings=meta["oil_openings"],
        oil_labels=dict(OIL_LABELS),
    )


@router.get("/{entry_id}", response_model=EntryOut)
def get_entry(
    entry_id: int,
    _: Principal = Depends(get_principal),
    conn: sqlite3.Connection = Depends(get_db),
) -> EntryOut:
    row = conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (entry_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    return _row_to_out(row)


@router.get("", response_model=list[EntryOut])
def list_entries(
    shift_date: str | None = None,
    pump_serial: str | None = None,
    _: Principal = Depends(get_principal),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[EntryOut]:
    clauses, params = [], []
    if shift_date:
        clauses.append("shift_date = ?")
        params.append(shift_date)
    if pump_serial:
        clauses.append("pump_serial = ?")
        params.append(pump_serial)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM {TABLE}{where} ORDER BY shift_date DESC, id DESC", params
    ).fetchall()
    return [_row_to_out(r) for r in rows]


@router.post("", response_model=EntryOut, status_code=status.HTTP_201_CREATED)
def create_entry(
    body: EntryCreate,
    principal: Principal = Depends(require("Sales", "Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> EntryOut:
    shift_date = body.shift_date or date.today().isoformat()
    raw = body.model_dump(exclude={"shift_date", "pump_serial"})
    payload, meta = _apply_locked_context(conn, raw, shift_date, body.pump_serial)
    result = compute_payload(payload)

    with transaction(conn):
        cur = conn.execute(
            f"""
            INSERT INTO {TABLE} (
                shift_date, pump_serial, submitted_by, entry_mode,
                hs_current, ms_current, hs_last, ms_last,
                sell_rate_hs, sell_rate_ms, oil_rates_json,
                gas_total, oil_total, expenses_total, net_bal_hand_off,
                payload, result, last_updated_by
            ) VALUES (?, ?, ?, 'manual', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                shift_date,
                body.pump_serial,
                principal.login_name,
                _num(payload["hs"].get("current")),
                _num(payload["ms"].get("current")),
                meta_last(payload, "hs"),
                meta_last(payload, "ms"),
                meta["sell_rate_hs"],
                meta["sell_rate_ms"],
                json.dumps(meta["oil_rates"]),
                result["gas_total"],
                result["oil_total"],
                result["expenses_total"],
                result["net_bal_hand_off"],
                json.dumps(payload),
                json.dumps(result),
                principal.login_name,
            ),
        )
        entry_id = cur.lastrowid
        record_write(
            conn,
            table=TABLE,
            record_id=entry_id,
            action="create",
            actor=principal.login_name,
            new={
                "shift_date": shift_date,
                "pump_serial": body.pump_serial,
                "net_bal_hand_off": result["net_bal_hand_off"],
            },
        )
    row = conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (entry_id,)).fetchone()
    return _row_to_out(row)


@router.put("/{entry_id}", response_model=EntryOut)
def update_entry(
    entry_id: int,
    body: EntryCreate,
    principal: Principal = Depends(require("Sales", "Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> EntryOut:
    row = conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (entry_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    # Sales may only edit their own submission (SDD 4.2).
    if principal.role == "Sales" and row["submitted_by"] != principal.login_name:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Sales users can only edit their own submission"
        )

    shift_date = body.shift_date or row["shift_date"]
    raw = body.model_dump(exclude={"shift_date", "pump_serial"})
    payload, meta = _apply_locked_context(conn, raw, shift_date, body.pump_serial)
    result = compute_payload(payload)
    old_snapshot = {
        "net_bal_hand_off": row["net_bal_hand_off"],
        "payload": json.loads(row["payload"]),
    }

    with transaction(conn):
        conn.execute(
            f"""
            UPDATE {TABLE} SET
                shift_date = ?, pump_serial = ?,
                hs_current = ?, ms_current = ?, hs_last = ?, ms_last = ?,
                sell_rate_hs = ?, sell_rate_ms = ?, oil_rates_json = ?,
                gas_total = ?, oil_total = ?, expenses_total = ?, net_bal_hand_off = ?,
                payload = ?, result = ?,
                last_updated_by = ?, last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE id = ?
            """,
            (
                shift_date,
                body.pump_serial,
                _num(payload["hs"].get("current")),
                _num(payload["ms"].get("current")),
                meta_last(payload, "hs"),
                meta_last(payload, "ms"),
                meta["sell_rate_hs"],
                meta["sell_rate_ms"],
                json.dumps(meta["oil_rates"]),
                result["gas_total"],
                result["oil_total"],
                result["expenses_total"],
                result["net_bal_hand_off"],
                json.dumps(payload),
                json.dumps(result),
                principal.login_name,
                entry_id,
            ),
        )
        record_write(
            conn,
            table=TABLE,
            record_id=entry_id,
            action="update",
            actor=principal.login_name,
            old=old_snapshot,
            new={"net_bal_hand_off": result["net_bal_hand_off"]},
        )
    return _row_to_out(conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (entry_id,)).fetchone())


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: int,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> None:
    row = conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (entry_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    with transaction(conn):
        conn.execute(f"DELETE FROM {TABLE} WHERE id = ?", (entry_id,))
        record_write(
            conn,
            table=TABLE,
            record_id=entry_id,
            action="delete",
            actor=principal.login_name,
            old={
                "shift_date": row["shift_date"],
                "pump_serial": row["pump_serial"],
                "net_bal_hand_off": row["net_bal_hand_off"],
            },
        )


@router.get("/ocr/status")
def ocr_status(_: Principal = Depends(get_principal)) -> dict:
    """Whether the bundled Tesseract (SDD ADR-6) is present and runnable.

    Lets the post-install / clean-VM check confirm OCR shipped without a real
    scan. `bundled` is False in dev (no SVR_TESSERACT_CMD, no tesseract on PATH).
    """
    version = tesseract_version()
    cmd = get_settings().resolved_tesseract_cmd()
    return {
        "bundled": version is not None,
        "cmd": cmd,
        "version": version,
        # Draft-assist only: stock Tesseract does not read the handwritten forms
        # reliably (see docs/.../OCR-findings-2026-09-09.md). Every field is
        # flagged and nothing is saved without human review (SDD ADR-5).
        "pipeline": "draft-assist",
    }


@router.post("/ocr")
async def ocr_upload(
    file: UploadFile = File(...), _: Principal = Depends(get_principal)
) -> dict:
    """Best-effort draft from a scanned/photographed Daily Sales Report.

    Same review contract as /import-excel: never saves, recomputes every total,
    and returns a per-field confidence so the reviewer knows what to trust
    (which, on handwriting, is very little).
    """
    if tesseract_version() is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "OCR engine not available - check the bundled Tesseract (GET .../ocr/status)",
        )
    raw = await file.read()
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")
    try:
        res = ocr_pipeline.extract(raw, file.filename or "")
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {
        "payload": res.payload,
        "meta": {},  # operator picks pump + date; the scan's own values are unreliable
        "result": compute_payload(res.payload),
        "fields": [
            {"key": f.key, "value": f.value, "confidence": f.confidence, "raw": f.raw}
            for f in res.fields
        ],
        "warnings": res.warnings,
        "engine": res.engine,
        "page_text": res.page_text,
    }


_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx_response(data: bytes, filename: str) -> Response:
    return Response(
        content=data,
        media_type=_XLSX,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/import-excel/template")
def import_excel_template(
    pump_serial: str | None = None, _: Principal = Depends(get_principal)
) -> Response:
    """A blank .xlsx to fill offline and feed back through POST /import-excel."""
    return _xlsx_response(blank_template(pump_serial), "SVR-DailySalesEntry-template.xlsx")


@router.post("/import-excel")
async def import_excel(
    file: UploadFile = File(...), _: Principal = Depends(get_principal)
) -> dict:
    """Parse an uploaded .xlsx into a form payload for human review (SDD ADR-5).

    Does NOT save. The engine recomputes every total; `warnings` flags any cell
    whose value disagreed with the recomputed one. The reviewer edits + Saves
    through the normal POST/PUT path, which re-locks rates/readings.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")
    try:
        payload, meta, warnings = parse_workbook(raw)
    except HTTPException:
        raise
    except Exception as exc:  # surface any openpyxl parse failure as a 400
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Could not read the spreadsheet: {exc}"
        ) from exc
    return {
        "payload": payload,
        "meta": meta,
        "result": compute_payload(payload),
        "warnings": warnings,
    }


@router.get("/{entry_id}/export-excel")
def export_excel(
    entry_id: int,
    _: Principal = Depends(get_principal),
    conn: sqlite3.Connection = Depends(get_db),
) -> Response:
    row = conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (entry_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    data = build_workbook(
        {
            "shift_date": row["shift_date"],
            "pump_serial": row["pump_serial"],
            "submitted_by": row["submitted_by"],
            "entry_mode": row["entry_mode"],
            "payload": json.loads(row["payload"]),
            "result": json.loads(row["result"]),
        }
    )
    name = f"SVR-DSE-{row['shift_date']}-{row['pump_serial']}.xlsx"
    return _xlsx_response(data, name)


# ------------------------------------------------------------------------- tiny utils


def _num(value) -> float | None:
    from svr_backend.calc.amounts import is_blank, parse_amt

    return None if is_blank(value) else parse_amt(value)


def meta_last(payload: dict, fuel: str) -> float | None:
    return payload.get(fuel, {}).get("last")
