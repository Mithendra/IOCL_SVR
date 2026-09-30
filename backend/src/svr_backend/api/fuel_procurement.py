"""Fuel Procurement (new module, client 2026-09-30). Manager + Owner only -
this is a financial record, not a Sales-entry form, same access as Credit /
Remittance Master.

Explicitly separate from Daily Trial Balance's own "10. Load/Unload Details" -
that section stays exactly as-is, tracking the sensor/IOCL-load litres
reconciliation that feeds Section 1's benefit/loss numbers. This module tracks
the commercial side: what a load of HS/MS cost (the rate is read by hand off
the IOCL bank-debit statement - IOCL sends no separate invoice) and getting
that cost into Monthly Expenses.

A typical load is two rows sharing a date and vehicle reference (HS + MS,
~95% of the time per the client) - each fuel posts independently, since
Monthly Expenses already has two separate categories for them
(migration 0052, "Fuel Load - HS" / "Fuel Load - MS").
"""

from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from svr_backend.core.audit import record_write
from svr_backend.core.db import transaction
from svr_backend.core.rbac import get_db, require
from svr_backend.core.session import Principal
from svr_backend.excel.fuel_procurement import build_monthly_workbook, build_workbook

router = APIRouter(prefix="/fuel-procurement", tags=["fuel-procurement"])

TABLE = "fuel_load"
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class FuelLoadIn(BaseModel):
    shift_date: str
    fuel_type: str = Field(pattern="^(HS|MS)$")
    iocl_load_litres: float = Field(gt=0)
    received_litres: float = Field(gt=0)
    rate: float = Field(gt=0)
    vehicle_ref: str | None = None


class FuelLoadUpdate(BaseModel):
    shift_date: str | None = None
    iocl_load_litres: float | None = Field(default=None, gt=0)
    received_litres: float | None = Field(default=None, gt=0)
    rate: float | None = Field(default=None, gt=0)
    vehicle_ref: str | None = None


def _row(r: sqlite3.Row) -> dict:
    """The stored row plus the two figures that are never stored - Lost
    (informational, never affects cost) and Amount (IOCL Load x Rate, since
    IOCL debits on what they say they loaded, not on what arrived)."""
    d = dict(r)
    d["lost_litres"] = round(r["iocl_load_litres"] - r["received_litres"], 4)
    d["amount"] = round(r["iocl_load_litres"] * r["rate"], 4)
    return d


def _filters(
    start: str | None, end: str | None, fuel_type: str | None, status_: str | None
) -> tuple[str, list]:
    clauses, params = [], []
    if start:
        clauses.append("shift_date >= ?")
        params.append(start)
    if end:
        clauses.append("shift_date <= ?")
        params.append(end)
    if fuel_type:
        clauses.append("fuel_type = ?")
        params.append(fuel_type)
    if status_:
        clauses.append("status = ?")
        params.append(status_)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


@router.get("")
def list_loads(
    start: str | None = None,
    end: str | None = None,
    fuel_type: str | None = None,
    status_: str | None = Query(None, alias="status"),
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    where, params = _filters(start, end, fuel_type, status_)
    rows = conn.execute(
        f"SELECT * FROM {TABLE}{where} ORDER BY shift_date DESC, id DESC", params
    ).fetchall()
    return [_row(r) for r in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def add_load(
    body: FuelLoadIn,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    when = body.shift_date or date.today().isoformat()
    with transaction(conn):
        cur = conn.execute(
            f"""
            INSERT INTO {TABLE}
                (shift_date, fuel_type, iocl_load_litres, received_litres, rate,
                 vehicle_ref, created_by, last_updated_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                when, body.fuel_type, body.iocl_load_litres, body.received_litres,
                body.rate, body.vehicle_ref, principal.login_name, principal.login_name,
            ),
        )
        record_write(
            conn, table=TABLE, record_id=cur.lastrowid, action="create",
            actor=principal.login_name,
            new={"shift_date": when, "fuel_type": body.fuel_type,
                 "iocl_load_litres": body.iocl_load_litres, "rate": body.rate},
        )
    return _row(conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (cur.lastrowid,)).fetchone())


@router.put("/{load_id}")
def update_load(
    load_id: int,
    body: FuelLoadUpdate,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (load_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Load not found")
    if row["status"] == "posted":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This row is already posted to Monthly Expenses and is read-only",
        )
    values = {
        "shift_date": body.shift_date if body.shift_date is not None else row["shift_date"],
        "iocl_load_litres": body.iocl_load_litres if body.iocl_load_litres is not None
        else row["iocl_load_litres"],
        "received_litres": body.received_litres if body.received_litres is not None
        else row["received_litres"],
        "rate": body.rate if body.rate is not None else row["rate"],
        "vehicle_ref": body.vehicle_ref if body.vehicle_ref is not None else row["vehicle_ref"],
    }
    with transaction(conn):
        conn.execute(
            f"""
            UPDATE {TABLE} SET shift_date = ?, iocl_load_litres = ?, received_litres = ?,
                rate = ?, vehicle_ref = ?, last_updated_by = ?,
                last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE id = ?
            """,
            (*values.values(), principal.login_name, load_id),
        )
        record_write(
            conn, table=TABLE, record_id=load_id, action="update",
            actor=principal.login_name, new=values,
        )
    return _row(conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (load_id,)).fetchone())


@router.post("/{load_id}/post")
def post_load(
    load_id: int,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """The one-way step to Monthly Expenses. A direct insert, not a hook into
    posting.py's BLOCKS/sync_lines machinery - that machinery mirrors Daily
    Trial Balance's own `manual` JSON blob, and nothing here is a TB form
    section. Modelled on posting.post_line()'s expense branch."""
    row = conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (load_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Load not found")
    if row["status"] == "posted":
        raise HTTPException(status.HTTP_409_CONFLICT, "Already posted")
    category_name = f"Fuel Load - {row['fuel_type']}"
    category = conn.execute(
        "SELECT id FROM expense_category WHERE name = ? AND is_active = 1", (category_name,)
    ).fetchone()
    if category is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Expense category '{category_name}' is missing or inactive - "
            "check migration 0052 ran",
        )
    amount = round(row["iocl_load_litres"] * row["rate"], 4)
    ref_note = f" ({row['vehicle_ref']})" if row["vehicle_ref"] else ""
    description = f"Fuel Procurement {row['shift_date']} — {row['fuel_type']}{ref_note}"
    with transaction(conn):
        cur = conn.execute(
            """
            INSERT INTO monthly_expense
                (expense_date, category_id, amount, description, created_by, last_updated_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (row["shift_date"], category["id"], amount, description,
             principal.login_name, principal.login_name),
        )
        expense_id = cur.lastrowid
        record_write(
            conn, table="monthly_expense", record_id=expense_id, action="create",
            actor=principal.login_name,
            new={"amount": amount, "from": "fuel-procurement"},
        )
        conn.execute(
            f"""
            UPDATE {TABLE} SET status = 'posted', posted_expense_id = ?,
                last_updated_by = ?, last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE id = ?
            """,
            (expense_id, principal.login_name, load_id),
        )
        record_write(
            conn, table=TABLE, record_id=load_id, action="update",
            actor=principal.login_name,
            new={"status": "posted", "posted_expense_id": expense_id},
        )
    return _row(conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (load_id,)).fetchone())


@router.get("/export-excel")
def export_excel(
    start: str | None = None,
    end: str | None = None,
    fuel_type: str | None = None,
    status_: str | None = Query(None, alias="status"),
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> Response:
    where, params = _filters(start, end, fuel_type, status_)
    rows = conn.execute(
        f"SELECT * FROM {TABLE}{where} ORDER BY shift_date, id", params
    ).fetchall()
    data = build_workbook([_row(r) for r in rows])
    name = "SVR-FuelProcurement.xlsx"
    if start or end:
        name = f"SVR-FuelProcurement-{start or 'start'}-to-{end or 'end'}.xlsx"
    return Response(
        content=data, media_type=_XLSX,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/export-monthly-excel")
def export_monthly_excel(
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> Response:
    """The Month-by-Month Load Summary, exported (client, 2026-09-30) - always
    every load on file, same as the on-screen summary; no date/fuel/status
    filter, since a month-end/year-end view is the whole point of this one."""
    rows = conn.execute(f"SELECT * FROM {TABLE} ORDER BY shift_date, id").fetchall()
    data = build_monthly_workbook([_row(r) for r in rows])
    name = "SVR-FuelProcurement-MonthSummary.xlsx"
    return Response(
        content=data, media_type=_XLSX,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
