"""Payment Receipt (SDD 5.20). Point-of-sale fuel receipt - creatable by Sales,
Manager, Owner; deletion Manager/Owner only. Rate defaults to the current Rate
Master Sell Rate for the fuel; total = liters x rate.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from svr_backend.calc.amounts import round4
from svr_backend.core.audit import record_write
from svr_backend.core.db import transaction
from svr_backend.core.rbac import get_db, get_principal, require
from svr_backend.core.session import Principal
from svr_backend.rates import latest_effective_rates
from svr_backend.summary import PUMP_SIDE

router = APIRouter(prefix="/receipts", tags=["receipts"])

TABLE = "payment_receipt"
_FUEL_KEY = {"Diesel": "HS", "Petrol": "MS"}


class ReceiptIn(BaseModel):
    receipt_date: str | None = None
    receipt_time: str | None = None
    pump_serial: str | None = None
    attendant: str | None = None
    vehicle_no: str | None = None
    fuel_type: str = Field(pattern="^(Diesel|Petrol)$")
    liters: float = Field(gt=0)
    rate: float | None = Field(default=None, gt=0)
    payment_mode: str = Field(pattern="^(Cash|Card|UPI|Credit)$")
    ref_no: str | None = None
    card_last4: str | None = None


@router.get("")
def list_receipts(
    start: str | None = None,
    end: str | None = None,
    _: Principal = Depends(get_principal),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    clauses, params = [], []
    if start:
        clauses.append("receipt_date >= ?")
        params.append(start)
    if end:
        clauses.append("receipt_date <= ?")
        params.append(end)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM {TABLE}{where} ORDER BY id DESC LIMIT 200", params
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/form-options")
def form_options(
    _: Principal = Depends(require("Sales", "Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """What the receipt form needs to fill its own dropdowns.

    Pump Serial# was a free-text box, so a receipt could be issued against a
    serial that does not exist and would never tie back to a pump (client,
    2026-09-25). The two serials come from summary.PUMP_SIDE, the same fixed map
    Daily Sales Entry classifies against, so there is one list and not two.

    Sell rates only - never buy rates. Sales may issue a receipt and has to see
    the price being charged, but the buy rate is the station's margin and stays
    behind /rate-master, which is Manager/Owner.
    """
    rates = latest_effective_rates(conn)
    sell: dict[str, float] = {}
    for fuel, key in _FUEL_KEY.items():
        if key in rates:
            sell[fuel] = rates[key]["sell_rate"]
    # The station's own name, address and phone go on the printed receipt - a
    # receipt handed to a customer with no address on it is not a receipt
    # (client, 2026-09-25). From station_profile so the Owner can correct them.
    station = {
        r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM station_profile")
    }
    return {"pumps": list(PUMP_SIDE), "sell_rates": sell, "station": station}

@router.get("/{receipt_id}")
def get_receipt(
    receipt_id: int,
    _: Principal = Depends(get_principal),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (receipt_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Receipt not found")
    return dict(row)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_receipt(
    body: ReceiptIn,
    principal: Principal = Depends(require("Sales", "Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    when = body.receipt_date or date.today().isoformat()
    rate = body.rate
    if rate is None:
        rates = latest_effective_rates(conn, when)
        key = _FUEL_KEY[body.fuel_type]
        if key not in rates:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"No Rate Master sell rate for {body.fuel_type}; pass rate explicitly",
            )
        rate = rates[key]["sell_rate"]
    total = round4(body.liters * rate)

    with transaction(conn):
        cur = conn.execute(
            f"""
            INSERT INTO {TABLE}
                (receipt_date, receipt_time, pump_serial, attendant, vehicle_no,
                 fuel_type, liters, rate, total, payment_mode, ref_no, card_last4, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                when, body.receipt_time, body.pump_serial, body.attendant, body.vehicle_no,
                body.fuel_type, body.liters, rate, total, body.payment_mode,
                body.ref_no, body.card_last4, principal.login_name,
            ),
        )
        rid = cur.lastrowid
        receipt_no = f"SVR-{rid:06d}"
        conn.execute(f"UPDATE {TABLE} SET receipt_no = ? WHERE id = ?", (receipt_no, rid))
        record_write(
            conn, table=TABLE, record_id=rid, action="create", actor=principal.login_name,
            new={"receipt_no": receipt_no, "fuel_type": body.fuel_type, "total": total},
        )
    return dict(conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (rid,)).fetchone())


@router.delete("/{receipt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_receipt(
    receipt_id: int,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> None:
    row = conn.execute(f"SELECT * FROM {TABLE} WHERE id = ?", (receipt_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Receipt not found")
    with transaction(conn):
        conn.execute(f"DELETE FROM {TABLE} WHERE id = ?", (receipt_id,))
        record_write(
            conn, table=TABLE, record_id=receipt_id, action="delete",
            actor=principal.login_name,
            old={"receipt_no": row["receipt_no"], "total": row["total"]},
        )
