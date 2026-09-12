"""Inventory Tracking API (SDD 5.10 / BRD 33/35).

Access (BRD 33): Sales has no access; Manager and Owner have full access.
Reorder-level changes are Owner-only (a pricing-adjacent policy knob).
"""

from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from svr_backend.core.audit import record_write
from svr_backend.core.db import transaction
from svr_backend.core.rbac import get_db, require
from svr_backend.core.session import Principal
from svr_backend.inventory import stock_levels

router = APIRouter(prefix="/inventory", tags=["inventory"])


class RestockIn(BaseModel):
    item_key: str
    quantity: float = Field(gt=0)
    supplier_ref: str | None = None
    restock_date: str | None = None  # defaults to today


class ReorderIn(BaseModel):
    reorder_level: float | None = Field(default=None, ge=0)
    on_hand: float | None = Field(default=None, ge=0)  # Owner stock correction


@router.get("")
def get_inventory(
    as_of: str | None = None,
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    return stock_levels(conn, as_of or date.today().isoformat())


@router.post("/restock", status_code=status.HTTP_201_CREATED)
def restock(
    body: RestockIn,
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    item = conn.execute(
        "SELECT * FROM inventory_item WHERE item_key = ?", (body.item_key,)
    ).fetchone()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown item '{body.item_key}'")

    when = body.restock_date or date.today().isoformat()
    with transaction(conn):
        cur = conn.execute(
            """
            INSERT INTO restock_entry (restock_date, item_key, quantity, supplier_ref, received_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (when, body.item_key, body.quantity, body.supplier_ref, principal.login_name),
        )
        record_write(
            conn, table="restock_entry", record_id=cur.lastrowid, action="create",
            actor=principal.login_name,
            new={"item_key": body.item_key, "quantity": body.quantity, "restock_date": when},
        )
    # on_hand (the Opening Stock) is NOT touched here - Received (Today) feeds the
    # Closing Stock formula directly and is folded into on_hand only at day close /
    # Daily Trial Balance finalization (not built yet).
    return {"item_key": body.item_key, "restock_id": cur.lastrowid, "restock_date": when}


@router.put("/{item_key}")
def set_item_policy(
    item_key: str,
    body: ReorderIn,
    # Manager as well as Owner (widened 2026-09-11): this is the only way to
    # *set* a stock level rather than add to it, and correcting a miscount is
    # day-to-day floor work, not an ownership decision. Restock stays additive -
    # it is a receipt log - so without this there was no correction path at all.
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    item = conn.execute(
        "SELECT * FROM inventory_item WHERE item_key = ?", (item_key,)
    ).fetchone()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown item '{item_key}'")

    reorder = item["reorder_level"] if body.reorder_level is None else body.reorder_level
    on_hand = item["on_hand"] if body.on_hand is None else body.on_hand
    with transaction(conn):
        conn.execute(
            "UPDATE inventory_item SET reorder_level = ?, on_hand = ?, last_updated_by = ?, "
            "last_updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE item_key = ?",
            (reorder, on_hand, principal.login_name, item_key),
        )
        record_write(
            conn, table="inventory_item", record_id=item_key, action="update",
            actor=principal.login_name,
            old={"reorder_level": item["reorder_level"], "on_hand": item["on_hand"]},
            new={"reorder_level": reorder, "on_hand": on_hand},
        )
    return {"item_key": item_key, "reorder_level": reorder, "on_hand": on_hand}
