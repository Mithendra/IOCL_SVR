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
from svr_backend.owner_secret import check_passphrase
from svr_backend.rates import latest_effective_rates

router = APIRouter(prefix="/inventory", tags=["inventory"])


class RestockIn(BaseModel):
    item_key: str
    quantity: float = Field(gt=0)
    supplier_ref: str | None = None
    restock_date: str | None = None  # defaults to today
    passphrase: str | None = None


class ReorderIn(BaseModel):
    reorder_level: float | None = Field(default=None, ge=0)
    on_hand: float | None = Field(default=None, ge=0)  # Owner stock correction
    # Required on the write itself, not just to open the form: an "unlocked"
    # screen left open is not by itself permission to change a stock level.
    passphrase: str | None = None


@router.get("")
def get_inventory(
    as_of: str | None = None,
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    return stock_levels(conn, as_of or date.today().isoformat())


class UnlockIn(BaseModel):
    passphrase: str | None = None


@router.post("/unlock")
def unlock_form(
    body: UnlockIn,
    # Manager or Owner - the passphrase is the authority, not the role
    # (client, 2026-09-25). /owner-reset/unlock is Owner-only and belongs to the
    # reading-reset form; a Manager calling it got a 403 and could never open
    # this one, which is why the form needs its own check.
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Check the Owner passphrase before enabling the form.

    Opening the form is not by itself permission: the passphrase is sent again
    with every write, so a screen left unlocked on a counter cannot be used by
    whoever walks past.
    """
    check_passphrase(conn, body.passphrase)
    return {"ok": True}


@router.post("/restock", status_code=status.HTTP_201_CREATED)
def restock(
    body: RestockIn,
    # Manager or Owner may edit, but ONLY with the Owner's passphrase, and every
    # row records who did it (client, 2026-09-25: "Manager can be updated but
    # secert password is need from the owner"). The passphrase is the authority;
    # the role is just who is at the keyboard; last_updated_by is the answer to
    # "who changed this".
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    check_passphrase(conn, body.passphrase)
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
    # Manager or Owner may edit, but ONLY with the Owner's passphrase, and every
    # row records who did it (client, 2026-09-25: "Manager can be updated but
    # secert password is need from the owner"). The passphrase is the authority;
    # the role is just who is at the keyboard; last_updated_by is the answer to
    # "who changed this".
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    check_passphrase(conn, body.passphrase)
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


class RatesIn(BaseModel):
    buy_rate: float | None = Field(default=None, ge=0)
    sell_rate: float | None = Field(default=None, ge=0)
    effective_date: str | None = None
    passphrase: str | None = None


@router.put("/{item_key}/rates")
def set_item_rates(
    item_key: str,
    body: RatesIn,
    # Manager or Owner may edit, but ONLY with the Owner's passphrase, and every
    # row records who did it (client, 2026-09-25: "Manager can be updated but
    # secert password is need from the owner"). The passphrase is the authority;
    # the role is just who is at the keyboard; last_updated_by is the answer to
    # "who changed this".
    principal: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Set an item's Buy/Sell Rate, written to rate_master.

    NOT to a column on inventory_item. rate_master is append-only by
    effective_date and is what Daily Sales Entry and the Trial Balance already
    resolve rates from, so a copy here would be a second figure to keep in step -
    and re-opening an old day would then price it at today's rate. Appending
    leaves every past day priced as it was.

    A rate left as None keeps whatever is in force, so setting one of the pair
    does not silently blank the other.
    """
    check_passphrase(conn, body.passphrase)
    item = conn.execute(
        "SELECT * FROM inventory_item WHERE item_key = ?", (item_key,)
    ).fetchone()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown item '{item_key}'")
    if body.buy_rate is None and body.sell_rate is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Give a Buy Rate, a Sell Rate, or both"
        )

    eff = body.effective_date or date.today().isoformat()
    rates = latest_effective_rates(conn, eff)
    in_force = rates[item_key] if item_key in rates else None
    held_buy = in_force["buy_rate"] if in_force is not None else None
    held_sell = in_force["sell_rate"] if in_force is not None else None
    buy = body.buy_rate if body.buy_rate is not None else held_buy
    sell = body.sell_rate if body.sell_rate is not None else held_sell
    if sell is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"{item_key} has no Sell Rate on file, so one must be given",
        )

    with transaction(conn):
        cur = conn.execute(
            "INSERT INTO rate_master (item_key, item_label, buy_rate, sell_rate, "
            "effective_date, updated_by) VALUES (?, ?, ?, ?, ?, ?)",
            (item_key, item["item_label"], buy, sell, eff, principal.login_name),
        )
        record_write(
            conn, table="rate_master", record_id=int(cur.lastrowid), action="create",
            actor=principal.login_name,
            old={"buy_rate": held_buy, "sell_rate": held_sell},
            new={"item_key": item_key, "buy_rate": buy, "sell_rate": sell,
                 "effective_date": eff, "from": "inventory-tracking"},
        )
    return {"item_key": item_key, "buy_rate": buy, "sell_rate": sell, "effective_date": eff}
