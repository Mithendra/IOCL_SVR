"""Rate Master (SDD 5 / 9). Access (SDD 4.2):

* Sales   - blocked entirely
* Manager - view only
* Owner   - view + edit (the Dealership Owner is the only role that sets rates)

Editing appends a new ``effective_date`` row rather than mutating the current one,
so historical Daily Sales / Trial Balance records can always resolve the rate that
was active when they were created (SDD 19 item 7).
"""

from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from svr_backend.core.audit import record_write
from svr_backend.core.db import transaction
from svr_backend.core.rbac import get_db, require
from svr_backend.core.session import Principal
from svr_backend.rates import latest_effective_rates

router = APIRouter(prefix="/rate-master", tags=["rate-master"])


class RateOut(BaseModel):
    item_key: str
    item_label: str
    buy_rate: float | None
    sell_rate: float
    effective_date: str
    updated_by: str | None


class RateUpdate(BaseModel):
    item_key: str
    item_label: str | None = None
    buy_rate: float | None = None
    sell_rate: float = Field(gt=0)
    effective_date: str | None = None  # defaults to today


class RateHistoryRow(BaseModel):
    id: int
    effective_date: str
    item_key: str
    item_label: str
    buy_rate: float | None
    sell_rate: float
    prev_sell_rate: float | None
    updated_by: str | None


@router.get("/current", response_model=list[RateOut])
def current_rates(
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[RateOut]:
    rows = latest_effective_rates(conn)
    return [
        RateOut(
            item_key=r["item_key"],
            item_label=r["item_label"],
            buy_rate=r["buy_rate"],
            sell_rate=r["sell_rate"],
            effective_date=r["effective_date"],
            updated_by=r["updated_by"],
        )
        for r in sorted(rows.values(), key=lambda r: r["id"])
    ]


@router.get("/history", response_model=list[RateHistoryRow])
def rate_history(
    _: Principal = Depends(require("Manager", "Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[RateHistoryRow]:
    """Full versioned rate log, newest first, with the prior sell rate per item."""
    rows = conn.execute(
        """
        SELECT id, effective_date, item_key, item_label, buy_rate, sell_rate, updated_by,
               LAG(sell_rate) OVER (
                   PARTITION BY item_key ORDER BY effective_date, id
               ) AS prev_sell_rate
        FROM rate_master
        ORDER BY effective_date DESC, id DESC
        """
    ).fetchall()
    return [RateHistoryRow(**dict(r)) for r in rows]


@router.put("/", response_model=list[RateOut], status_code=200)
def update_rates(
    updates: list[RateUpdate],
    principal: Principal = Depends(require("Owner")),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[RateOut]:
    today = date.today().isoformat()
    with transaction(conn):
        for u in updates:
            eff = u.effective_date or today
            label = u.item_label
            if label is None:
                existing = conn.execute(
                    "SELECT item_label FROM rate_master WHERE item_key = ? "
                    "ORDER BY effective_date DESC, id DESC LIMIT 1",
                    (u.item_key,),
                ).fetchone()
                label = existing["item_label"] if existing else u.item_key
            cur = conn.execute(
                """
                INSERT INTO rate_master
                    (item_key, item_label, buy_rate, sell_rate, effective_date, updated_by)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (u.item_key, label, u.buy_rate, u.sell_rate, eff, principal.login_name),
            )
            record_write(
                conn,
                table="rate_master",
                record_id=cur.lastrowid,
                action="create",
                actor=principal.login_name,
                new={
                    "item_key": u.item_key,
                    "buy_rate": u.buy_rate,
                    "sell_rate": u.sell_rate,
                    "effective_date": eff,
                },
            )
    return current_rates(principal, conn)
